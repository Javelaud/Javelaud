import os
import asyncio
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

load_dotenv()

app = FastAPI(title="Analyse Sectorielle")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = """Tu es un expert-comptable et analyste financier spécialisé dans l'analyse sectorielle des PME françaises.

Tu analyses les liasses fiscales (formulaires 2050 à 2058) pour produire un diagnostic financier complet.

Ton analyse doit systématiquement couvrir :
1. **Identification** : secteur d'activité (code NAF/APE si présent), taille de l'entreprise, exercice
2. **Résultats clés** : chiffre d'affaires, résultat net, EBE/EBITDA
3. **Rentabilité** : marges (brute, nette, opérationnelle)
4. **Structure financière** : capitaux propres, endettement, ratio d'autonomie financière
5. **Liquidité** : BFR, trésorerie, ratios de liquidité
6. **Points forts** : au moins 3 éléments positifs clairement identifiés
7. **Points de vigilance / faiblesses** : au moins 3 risques ou axes d'amélioration
8. **Benchmarks sectoriels** : comparaison avec les ratios moyens du secteur (utilise tes connaissances des données Banque de France / INSEE)
9. **Recommandations** : actions concrètes prioritaires

Présente ton analyse de façon claire et structurée, avec des titres en markdown.
Utilise des emojis pour rendre la lecture plus agréable (✅ pour les points forts, ⚠️ pour les vigilances, etc.).
Sois précis sur les chiffres et explique leur signification pour un entrepreneur non-financier.

Termine systématiquement chaque analyse par une section :

---
## 📚 Sources & Limites

**Sources utilisées pour les benchmarks sectoriels :**
- Banque de France — Ratios financiers des PME par secteur (code NAF)
- INSEE — Données structurelles des entreprises françaises
- FCGA / APCMA — Moyennes sectorielles PME et artisanat
- Observatoires de branches professionnelles

**Limites de cette analyse :**
- Les benchmarks sont basés sur des données mémorisées jusqu'en début 2025 et peuvent ne pas refléter les évolutions récentes du secteur
- Cette analyse est fournie à titre indicatif et ne remplace pas l'avis d'un expert-comptable
- Pour toute décision importante (financement, cession, investissement), il est recommandé de croiser ces résultats avec les dernières publications de la Banque de France et de l'INSEE"""


async def stream_analysis(file_content: bytes, filename: str, secteur: str):
    """Upload le PDF vers l'API Files puis analyse en streaming."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Upload du fichier vers l'API Files d'Anthropic
    uploaded = client.beta.files.upload(
        file=(filename, file_content, "application/pdf"),
    )

    try:
        secteur_info = f"\nSecteur déclaré par l'entrepreneur : {secteur}" if secteur else ""
        user_message = f"""Voici la liasse fiscale de l'entreprise à analyser.{secteur_info}

Effectue une analyse sectorielle complète et détaillée en identifiant les points forts et les points de faiblesse de cette entreprise.
Compare ses ratios financiers avec les moyennes de son secteur et fournis des recommandations concrètes."""

        with client.beta.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_message,
                        },
                        {
                            "type": "document",
                            "source": {"type": "file", "file_id": uploaded.id},
                            "title": filename,
                        },
                    ],
                }
            ],
            betas=["files-api-2025-04-14"],
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {text}\n\n"

    finally:
        # Nettoyage du fichier uploadé
        client.beta.files.delete(uploaded.id)

    yield "data: [DONE]\n\n"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyser")
async def analyser(
    fichier: UploadFile = File(...),
    secteur: str = Form(default=""),
):
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY non configurée"}

    file_content = await fichier.read()
    filename = fichier.filename or "liasse_fiscale.pdf"

    return StreamingResponse(
        stream_analysis(file_content, filename, secteur),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
