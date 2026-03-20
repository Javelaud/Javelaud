"""
legifrance.py — Intégration API Légifrance (PISTE) pour la jurisprudence fiscale du Conseil d'État.
"""

import os
import time

import httpx

PISTE_TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
LEGIFRANCE_API_BASE = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"

# Cache du token OAuth (évite un appel réseau à chaque requête)
_token_cache: dict = {"token": None, "expires_at": 0.0}


async def _get_token(client: httpx.AsyncClient) -> str | None:
    """Obtient un token OAuth 2.0 depuis PISTE (avec cache automatique)."""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]

    client_id = os.getenv("LEGIFRANCE_CLIENT_ID")
    client_secret = os.getenv("LEGIFRANCE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    resp = await client.post(
        PISTE_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "openid",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


async def search_jurisprudence_ce(query: str, max_results: int = 3) -> str:
    """
    Recherche des décisions pertinentes du Conseil d'État sur un sujet fiscal.
    Retourne un bloc de texte à injecter dans le contexte du bot.
    Retourne une chaîne vide en cas d'erreur ou d'absence de résultats.
    """
    async with httpx.AsyncClient() as client:
        try:
            token = await _get_token(client)
            if not token:
                return ""

            resp = await client.post(
                f"{LEGIFRANCE_API_BASE}/search",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "recherche": {
                        "champs": [
                            {
                                "criteres": [
                                    {
                                        "valeur": query,
                                        "operateur": "ET",
                                        "typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP",
                                    }
                                ],
                                "operateur": "ET",
                                "typeChamp": "ALL",
                            }
                        ],
                        "pageNumber": 1,
                        "pageSize": max_results,
                        "operateur": "ET",
                        "sort": "PERTINENCE",
                        "typePagination": "DEFAUT",
                    },
                    "fond": "CETAT",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                return ""

            lines = ["\n## Jurisprudence Conseil d'État (source : Légifrance)\n"]
            for r in results:
                titles = r.get("titles", [])
                title = titles[0].get("title", "Décision CE") if titles else r.get("title", "Décision CE")
                date = r.get("dateDecision") or r.get("date", "")
                num = r.get("numDecision") or r.get("numero") or r.get("numberDecision", "")
                extract = (r.get("extract") or r.get("resume") or "")[:400]

                lines.append(f"**{title}**")
                if num:
                    lines.append(f"N° {num} — {date}")
                if extract:
                    lines.append(f"> {extract}...")
                lines.append("")

            return "\n".join(lines)

        except Exception:
            return ""
