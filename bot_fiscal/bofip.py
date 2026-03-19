"""Client pour l'API publique BOFIP via Opendatasoft (data.economie.gouv.fr)."""

import httpx

BOFIP_API_URL = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
    "/bofip-impots/records"
)

BOFIP_VIGUEUR_API_URL = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
    "/bofip-vigueur/records"
)


async def search_bofip(query: str, limit: int = 5) -> list[dict]:
    """
    Recherche des articles BOFIP en vigueur correspondant à la requête.

    Retourne une liste de dicts avec 'titre' et 'extrait'.
    En cas d'échec de l'API, retourne une liste vide.
    """
    params = {
        "where": f'search(*, "{query}")',
        "limit": limit,
        "select": "title,content,url",
    }

    results = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Essai sur le dataset "en vigueur" en priorité
        for url in (BOFIP_VIGUEUR_API_URL, BOFIP_API_URL):
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                records = data.get("results", [])
                if records:
                    for r in records:
                        titre = r.get("title", "Article BOFIP")
                        content = r.get("content", "")
                        lien = r.get("url", "")
                        # Tronque le contenu à 1 500 caractères pour le contexte
                        extrait = content[:1500].strip() if content else ""
                        if extrait:
                            results.append(
                                {"titre": titre, "extrait": extrait, "lien": lien}
                            )
                    break  # On a des résultats, on arrête
            except (httpx.HTTPError, Exception):
                continue

    return results


def format_bofip_context(articles: list[dict]) -> str:
    """Formate les articles BOFIP en bloc de contexte pour le prompt Claude."""
    if not articles:
        return ""

    lines = ["### Articles BOFIP pertinents\n"]
    for i, art in enumerate(articles, 1):
        lines.append(f"**Article {i} — {art['titre']}**")
        if art.get("lien"):
            lines.append(f"Source : {art['lien']}")
        lines.append(art["extrait"])
        lines.append("")

    return "\n".join(lines)
