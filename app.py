import asyncio
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import markdown as md
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

load_dotenv()

app = FastAPI(title="Analyse Sectorielle")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

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


def _send_email_sync(to_email: str, analysis_markdown: str, filename: str) -> None:
    """Envoie le rapport d'analyse par e-mail (exécuté dans un thread)."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        print("[EMAIL] Config SMTP manquante (SMTP_HOST/SMTP_USER/SMTP_PASSWORD)", flush=True)
        return

    html_body = md.markdown(
        analysis_markdown,
        extensions=["tables", "fenced_code"],
    )

    email_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"/>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background:#f5f7fa; margin:0; padding:0; }}
  .wrapper {{ max-width:700px; margin:2rem auto; background:white;
              border-radius:16px; overflow:hidden;
              box-shadow:0 4px 24px rgba(0,0,0,0.08); }}
  .header {{ background:linear-gradient(135deg,#0f1f45,#1e3a8a);
             color:white; padding:2rem; text-align:center; }}
  .header h1 {{ margin:0; font-size:1.5rem; }}
  .header p {{ margin:0.5rem 0 0; opacity:0.8; font-size:0.9rem; }}
  .content {{ padding:2rem; line-height:1.75; color:#374151; }}
  .content h1, .content h2, .content h3 {{ color:#0f1f45; }}
  .content h1 {{ font-size:1.4rem; border-bottom:2px solid #e5e7eb; padding-bottom:0.5rem; }}
  .content h2 {{ font-size:1.15rem; margin-top:1.5rem; }}
  .content h3 {{ font-size:1rem; color:#4f46e5; }}
  .content table {{ width:100%; border-collapse:collapse; margin:1rem 0; font-size:0.9rem; }}
  .content th {{ background:#f3f4f6; padding:0.6rem 1rem; text-align:left;
                 border:1px solid #e5e7eb; font-weight:600; }}
  .content td {{ padding:0.6rem 1rem; border:1px solid #e5e7eb; }}
  .content tr:nth-child(even) td {{ background:#f9fafb; }}
  .content blockquote {{ border-left:4px solid #4f46e5; padding-left:1rem;
                         color:#6b7280; font-style:italic; }}
  .footer {{ background:#f9fafb; border-top:1px solid #e5e7eb;
             padding:1.5rem 2rem; text-align:center;
             font-size:0.8rem; color:#9ca3af; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>📊 Analyse Sectorielle</h1>
    <p>Rapport complet — {filename}</p>
  </div>
  <div class="content">
    {html_body}
  </div>
  <div class="footer">
    Propulsé par Claude Opus 4.6 — Anthropic &nbsp;·&nbsp;
    Analyse à titre indicatif uniquement
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Votre analyse sectorielle — {filename}"
    msg["From"] = f"Javelaud Analyse <{SMTP_FROM}>"
    msg["To"] = to_email
    msg.attach(MIMEText(analysis_markdown, "plain", "utf-8"))
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.sendmail(SMTP_FROM, to_email, msg.as_bytes())


async def stream_analysis(
    file_content: bytes, filename: str, secteur: str, email: str
):
    """Upload le PDF vers l'API Files puis analyse en streaming."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    full_text_parts: list[str] = []
    uploaded = None

    try:
        uploaded = await client.beta.files.upload(
            file=(filename, file_content, "application/pdf"),
        )

        secteur_info = f"\nSecteur déclaré par l'entrepreneur : {secteur}" if secteur else ""
        user_message = f"""Voici la liasse fiscale de l'entreprise à analyser.{secteur_info}

Effectue une analyse sectorielle complète et détaillée en identifiant les points forts et les points de faiblesse de cette entreprise.
Compare ses ratios financiers avec les moyennes de son secteur et fournis des recommandations concrètes."""

        async with client.beta.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_message},
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
            async for text in stream.text_stream:
                full_text_parts.append(text)
                yield f"data: {json.dumps(text)}\n\n"

    except Exception as e:
        import traceback
        traceback.print_exc()
        err_msg = f"❌ **Erreur lors de l'analyse :** {e}"
        yield f"data: {json.dumps(err_msg)}\n\n"
    finally:
        if uploaded:
            try:
                await client.beta.files.delete(uploaded.id)
            except Exception:
                pass

    # Envoi de l'e-mail AVANT [DONE] pour éviter que la déconnexion client n'interrompe l'envoi
    if email and full_text_parts:
        try:
            await asyncio.to_thread(
                _send_email_sync, email, "".join(full_text_parts), filename
            )
            print(f"[EMAIL] Rapport envoyé à {email}", flush=True)
        except Exception as mail_err:
            print(f"[EMAIL ERROR] Échec envoi à {email} : {mail_err}", flush=True)

    yield "data: [DONE]\n\n"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyser")
async def analyser(
    fichier: UploadFile = File(...),
    secteur: str = Form(default=""),
    email: str = Form(default=""),
):
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY non configurée"}

    file_content = await fichier.read()
    filename = fichier.filename or "liasse_fiscale.pdf"

    return StreamingResponse(
        stream_analysis(file_content, filename, secteur, email),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
