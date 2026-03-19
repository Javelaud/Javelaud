"""Bot fiscal BOFIP — API FastAPI avec streaming SSE et historique de conversation."""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from bofip import format_bofip_context, search_bofip

load_dotenv()

app = FastAPI(title="Bot Fiscal BOFIP")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Historique en mémoire : {session_id: [{"role": ..., "content": ...}]}
conversations: dict[str, list[dict]] = {}

SYSTEM_PROMPT = """Tu es un expert-comptable et fiscaliste français spécialisé dans la fiscalité des entrepreneurs et des PME.

Tu réponds aux questions fiscales des entrepreneurs en t'appuyant prioritairement sur les articles du BOFIP (Bulletin Officiel des Finances Publiques - Impôts) qui te sont fournis dans le contexte de chaque message.

Tes réponses doivent :
- Être structurées et claires, avec des titres en markdown
- Citer explicitement les références BOFIP quand elles sont disponibles dans le contexte
- Expliquer les notions fiscales en termes accessibles à un entrepreneur non-expert
- Mentionner les régimes fiscaux applicables, les seuils importants et les options disponibles
- Utiliser des listes à puces pour les points clés
- Conclure par une note de prudence recommandant de consulter un professionnel pour les cas spécifiques

Si les articles BOFIP fournis ne couvrent pas totalement la question, tu peux compléter avec tes connaissances en fiscalité française, en le signalant clairement.

Ne réponds qu'aux questions liées à la fiscalité française des entreprises et des entrepreneurs. Pour toute autre question, explique poliment que tu es spécialisé en fiscalité d'entreprise."""


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ResetRequest(BaseModel):
    session_id: str


async def stream_chat(session_id: str, user_message: str):
    """Génère une réponse streamée en SSE avec contexte BOFIP et historique."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    # 1. Recherche BOFIP
    try:
        articles = await search_bofip(user_message, limit=5)
        bofip_context = format_bofip_context(articles)
    except Exception:
        bofip_context = ""

    # 2. Construction du message utilisateur enrichi
    if bofip_context:
        enriched_message = f"{user_message}\n\n---\n{bofip_context}"
    else:
        enriched_message = user_message

    # 3. Récupération et mise à jour de l'historique
    history = conversations.setdefault(session_id, [])
    history.append({"role": "user", "content": enriched_message})

    # 4. Streaming Claude
    full_response_parts: list[str] = []
    try:
        async with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=history,
        ) as stream:
            async for text in stream.text_stream:
                full_response_parts.append(text)
                # Encode le texte en JSON pour gérer les caractères spéciaux et sauts de ligne
                yield f"data: {json.dumps(text)}\n\n"

    except Exception as e:
        error_msg = f"❌ **Erreur :** {e}"
        yield f"data: {json.dumps(error_msg)}\n\n"
        # Retire le message utilisateur qui a échoué
        history.pop()
        yield "data: [DONE]\n\n"
        return

    # 5. Sauvegarde de la réponse dans l'historique
    if full_response_parts:
        history.append({"role": "assistant", "content": "".join(full_response_parts)})

    yield "data: [DONE]\n\n"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat")
async def chat(body: ChatRequest):
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY non configurée"}

    return StreamingResponse(
        stream_chat(body.session_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/nouvelle-conversation")
async def nouvelle_conversation(body: ResetRequest):
    conversations.pop(body.session_id, None)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
