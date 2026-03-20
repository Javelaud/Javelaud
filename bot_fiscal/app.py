import asyncio
import os
import uuid
from pathlib import Path

import anthropic
from bofip import BOT_FISCAL_SYSTEM_PROMPT
from bofip_rag import fetch_bofip_context
from legifrance import search_jurisprudence_ce
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Bot Fiscal")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Stockage en mémoire des sessions : session_id -> liste de messages
sessions: dict[str, list[dict]] = {}
# Fichiers Anthropic associés à chaque session (pour nettoyage)
session_files: dict[str, list[str]] = {}

MAX_SESSIONS = 1000
MAX_MESSAGES_PER_SESSION = 100
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 Mo

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


class MessageRequest(BaseModel):
    content: str
    file_id: str | None = None
    filename: str | None = None


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/sessions")
async def create_session():
    """Crée une nouvelle session de bot fiscal. Retourne un session_id."""
    if len(sessions) >= MAX_SESSIONS:
        # Supprimer la session la plus ancienne si la limite est atteinte
        oldest = next(iter(sessions))
        del sessions[oldest]
        session_files.pop(oldest, None)

    session_id = str(uuid.uuid4())
    sessions[session_id] = []
    session_files[session_id] = []
    return JSONResponse({"session_id": session_id, "message_count": 0})


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Retourne l'historique d'une session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session introuvable")
    history = sessions[session_id]
    return JSONResponse({
        "session_id": session_id,
        "message_count": len(history),
        "messages": history,
    })


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Supprime une session, son historique et ses fichiers uploadés."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session introuvable")
    del sessions[session_id]
    file_ids = session_files.pop(session_id, [])
    if file_ids:
        asyncio.create_task(_cleanup_files(file_ids))
    return JSONResponse({"deleted": True})


async def _cleanup_files(file_ids: list[str]):
    """Supprime les fichiers uploadés sur l'API Anthropic."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    for fid in file_ids:
        try:
            await client.beta.files.delete(fid)
        except Exception:
            pass


@app.post("/sessions/{session_id}/upload")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    """Upload un document (PDF, image) et le stocke via l'API Files d'Anthropic."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session introuvable")

    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY non configurée")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté. Formats acceptés : PDF, JPEG, PNG, GIF, WebP",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 20 Mo)")

    filename = file.filename or "document"
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    uploaded = await client.beta.files.upload(
        file=(filename, file_bytes, content_type),
    )

    session_files[session_id].append(uploaded.id)
    return JSONResponse({"file_id": uploaded.id, "filename": filename})


@app.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest):
    """Envoie un message dans la session et retourne la réponse en streaming (SSE)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session introuvable")

    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY non configurée")

    user_text = body.content.strip()
    if not user_text and not body.file_id:
        raise HTTPException(status_code=400, detail="Le message ne peut pas être vide")

    history = sessions[session_id]

    # Limiter la taille de l'historique
    if len(history) >= MAX_MESSAGES_PER_SESSION:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de {MAX_MESSAGES_PER_SESSION} messages atteinte pour cette session",
        )

    # Construire le contenu du message utilisateur
    if body.file_id:
        user_msg_content: str | list = [
            {
                "type": "document",
                "source": {"type": "file", "file_id": body.file_id},
                "title": body.filename or "document",
            },
            {"type": "text", "text": user_text or "Analyse ce document."},
        ]
    else:
        user_msg_content = user_text

    history.append({"role": "user", "content": user_msg_content})

    question_for_rag = user_text or (body.filename or "document")

    return StreamingResponse(
        _stream_response(session_id, history, question_for_rag),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_response(session_id: str, history: list[dict], question: str):
    """Génère la réponse en streaming et la sauvegarde dans l'historique."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    assistant_parts: list[str] = []

    # Enrichissement RAG : BOFiP et jurisprudence CE en parallèle
    bofip_context, jurisprudence = await asyncio.gather(
        fetch_bofip_context(question),
        search_jurisprudence_ce(question[:200]),
    )
    system_prompt = BOT_FISCAL_SYSTEM_PROMPT
    if bofip_context:
        system_prompt += f"\n\n{bofip_context}"
    if jurisprudence:
        system_prompt += jurisprudence

    # Utiliser le beta endpoint si l'historique contient des documents
    uses_files = any(isinstance(msg.get("content"), list) for msg in history)

    try:
        stream_kwargs = dict(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=history,
        )
        if uses_files:
            stream_kwargs["betas"] = ["files-api-2025-04-14"]
            async with client.beta.messages.stream(**stream_kwargs) as stream:
                async for text in stream.text_stream:
                    assistant_parts.append(text)
                    escaped = text.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"
        else:
            async with client.messages.stream(**stream_kwargs) as stream:
                async for text in stream.text_stream:
                    assistant_parts.append(text)
                    escaped = text.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"

    except Exception as e:
        import traceback
        traceback.print_exc()
        yield f"data: ❌ **Erreur :** {e}\n\n"
        # Retirer le dernier message utilisateur en cas d'erreur
        if sessions.get(session_id) and sessions[session_id][-1]["role"] == "user":
            sessions[session_id].pop()
        yield "data: [DONE]\n\n"
        return

    # Sauvegarder la réponse de l'assistant dans l'historique
    if assistant_parts and session_id in sessions:
        sessions[session_id].append({
            "role": "assistant",
            "content": "".join(assistant_parts),
        })

    yield "data: [DONE]\n\n"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
