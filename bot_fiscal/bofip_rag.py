"""
bofip_rag.py — Retrieval-Augmented Generation via l'API publique BOFiP.

Interroge l'API open data du Ministère de l'Économie pour récupérer
les passages du BOFiP pertinents à une question fiscale, et les injecte
dans le contexte Claude.

API : https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/bofip-vigueur/records
"""

import re
import httpx

BOFIP_API_URL = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
    "/bofip-vigueur/records"
)

# Séries BOFiP pertinentes pour la fiscalité entreprise
SERIES_ENTREPRISE = ["IS", "TVA", "BIC", "CF", "BA", "TCA", "RPPM"]

# Mots-clés → séries prioritaires
KEYWORD_SERIES: list[tuple[list[str], str]] = [
    (["tva", "taxe sur la valeur", "déduction tva", "assujetti"], "TVA"),
    (["impôt sur les sociétés", " is ", "résultat fiscal", "déficit reportable"], "IS"),
    (["bic", "bénéfice industriel", "micro-entreprise", "régime réel"], "BIC"),
    (["contrôle fiscal", "vérification", "redressement", "lpf"], "CF"),
    (["agricole", "ba ", "bénéfice agricole"], "BA"),
]


def _detect_series(question: str) -> str | None:
    """Détecte la série BOFiP la plus pertinente en fonction de la question."""
    q = question.lower()
    for keywords, serie in KEYWORD_SERIES:
        if any(kw in q for kw in keywords):
            return serie
    return None


def _clean_html(text: str) -> str:
    """Supprime les balises HTML d'un texte."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


async def fetch_bofip_context(question: str, max_results: int = 5) -> str:
    """
    Interroge l'API BOFiP et retourne un bloc de contexte prêt à injecter
    dans le system prompt Claude.

    Args:
        question: La question posée par l'utilisateur.
        max_results: Nombre maximum d'articles à récupérer.

    Returns:
        Bloc texte formaté avec les articles pertinents, ou chaîne vide.
    """
    serie = _detect_series(question)

    # Construction du filtre
    if serie:
        where_clause = f'serie="{serie}"'
    else:
        # Fallback : toutes les séries entreprise
        series_filter = " OR ".join(f'serie="{s}"' for s in SERIES_ENTREPRISE)
        where_clause = f"({series_filter})"

    # Recherche textuelle sur le titre
    words = [w for w in re.findall(r"\w{4,}", question.lower()) if w not in STOPWORDS]
    if words:
        search_term = " ".join(words[:5])
        where_clause += f' AND search(titre, "{search_term}")'

    params = {
        "where": where_clause,
        "select": "identifiant,titre,serie,date_publication,url_source",
        "order_by": "date_publication DESC",
        "limit": max_results,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(BOFIP_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return ""

    records = data.get("results", [])
    if not records:
        return ""

    lines = ["## Références BOFiP pertinentes\n"]
    for rec in records:
        titre = rec.get("titre", "Sans titre")
        identifiant = rec.get("identifiant", "")
        date = rec.get("date_publication", "")[:10] if rec.get("date_publication") else ""
        url = rec.get("url_source", "")

        lines.append(f"**{identifiant}** — {titre}")
        if date:
            lines.append(f"  Publié le : {date}")
        if url:
            lines.append(f"  Source : {url}")
        lines.append("")

    return "\n".join(lines)


# Mots vides français à ignorer dans la recherche
STOPWORDS = {
    "dans", "avec", "pour", "une", "les", "des", "que", "qui", "est",
    "sont", "peut", "doit", "cette", "comment", "quels", "quelle",
    "quelles", "quel", "quand", "puis", "aussi", "donc", "mais", "plus",
    "comme", "leur", "leurs", "entre", "nous", "vous", "faire", "avoir",
    "être", "fait", "ment",
}
