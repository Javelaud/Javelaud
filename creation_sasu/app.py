import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import auth
import documents as doc_service
import email_service
import oneflow as oneflow_service
from database import get_db, init_db
from models import (
    STATUS_LABELS,
    STATUS_ORDER,
    Document,
    Dossier,
    StatusHistory,
    User,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_expert_if_none()
    yield


app = FastAPI(title="Création SASU — Javelaud", lifespan=lifespan)

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Jinja2 globals
templates.env.globals["STATUS_LABELS"] = STATUS_LABELS
templates.env.globals["STATUS_ORDER"] = STATUS_ORDER


def _seed_expert_if_none():
    """Crée un compte expert par défaut si aucun n'existe."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        if db.query(User).filter(User.role == "expert").first():
            return
        expert_email = os.getenv("EXPERT_EMAIL", "expert@javelaud.fr")
        expert_password = os.getenv("EXPERT_PASSWORD", "changeme123")
        expert = User(
            email=expert_email,
            hashed_password=auth.hash_password(expert_password),
            role="expert",
            prenom="Expert",
            nom="Javelaud",
            is_active=True,
        )
        db.add(expert)
        db.commit()
        print(f"[SEED] Expert créé : {expert_email} / {expert_password}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes publiques
# ---------------------------------------------------------------------------


@app.get("/")
def root(user: Optional[User] = Depends(auth.get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.role == "expert":
        return RedirectResponse("/expert/dashboard", status_code=302)
    return RedirectResponse("/client/dashboard", status_code=302)


@app.get("/login")
def login_page(
    request: Request,
    user: Optional[User] = Depends(auth.get_current_user),
):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = auth.authenticate_user(email, password, db)
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Email ou mot de passe incorrect"},
            status_code=401,
        )
    token = auth.create_access_token(user.id, user.role)
    redirect_url = "/expert/dashboard" if user.role == "expert" else "/client/dashboard"
    response = RedirectResponse(redirect_url, status_code=302)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=auth.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@app.get("/invitation/{token}")
def invitation_page(request: Request, token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.invitation_token == token).first()
    if not user or user.invitation_used:
        return templates.TemplateResponse(
            request, "invitation_invalide.html", {}, status_code=400
        )
    if user.invitation_expires and datetime.utcnow() > user.invitation_expires:
        return templates.TemplateResponse(
            request, "invitation_invalide.html", {"expired": True}, status_code=400
        )
    return templates.TemplateResponse(
        request, "set_password.html", {"token": token, "prenom": user.prenom, "error": None}
    )


@app.post("/invitation/{token}")
def invitation_set_password(
    request: Request,
    token: str,
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.invitation_token == token).first()
    if not user or user.invitation_used:
        raise HTTPException(status_code=400, detail="Lien invalide")

    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "set_password.html",
            {"token": token, "prenom": user.prenom, "error": "Les mots de passe ne correspondent pas"},
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "set_password.html",
            {"token": token, "prenom": user.prenom, "error": "Le mot de passe doit contenir au moins 8 caractères"},
            status_code=400,
        )

    user.hashed_password = auth.hash_password(password)
    user.is_active = True
    user.invitation_used = True
    db.commit()

    jwt_token = auth.create_access_token(user.id, user.role)
    response = RedirectResponse("/client/formulaire", status_code=302)
    response.set_cookie(
        "access_token",
        jwt_token,
        httponly=True,
        samesite="lax",
        max_age=auth.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
    )
    return response


# ---------------------------------------------------------------------------
# Routes client
# ---------------------------------------------------------------------------


@app.get("/client/dashboard")
def client_dashboard(
    request: Request,
    user: User = Depends(auth.require_client),
    db: Session = Depends(get_db),
):
    dossier = db.query(Dossier).filter(Dossier.client_id == user.id).first()
    return templates.TemplateResponse(
        request,
        "client/dashboard.html",
        {"user": user, "dossier": dossier},
    )


@app.get("/client/formulaire")
def client_formulaire(
    request: Request,
    user: User = Depends(auth.require_client),
    db: Session = Depends(get_db),
):
    dossier = db.query(Dossier).filter(Dossier.client_id == user.id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    # Si le formulaire est déjà soumis, rediriger vers le dashboard
    if dossier.status != "invitation_envoyee":
        return RedirectResponse("/client/dashboard", status_code=302)
    return templates.TemplateResponse(
        request,
        "client/formulaire.html",
        {"user": user, "dossier": dossier, "error": None},
    )


@app.post("/client/formulaire")
def client_formulaire_submit(
    request: Request,
    user: User = Depends(auth.require_client),
    db: Session = Depends(get_db),
    # Dirigeant
    civilite: str = Form(...),
    nom: str = Form(...),
    prenom: str = Form(...),
    nom_jeune_fille: str = Form(""),
    date_naissance: str = Form(...),
    lieu_naissance: str = Form(...),
    departement_naissance: str = Form(...),
    nationalite: str = Form(...),
    situation_matrimoniale: str = Form(...),
    profession_anterieure: str = Form(""),
    # Adresse
    adresse_rue: str = Form(...),
    adresse_cp: str = Form(...),
    adresse_ville: str = Form(...),
    adresse_pays: str = Form("France"),
    # Filiation
    nom_pere: str = Form(...),
    prenom_pere: str = Form(...),
    nom_mere: str = Form(...),
    prenom_mere_naissance: str = Form(...),
    # Société
    denomination_sociale: str = Form(...),
    siege_social_rue: str = Form(...),
    siege_social_cp: str = Form(...),
    siege_social_ville: str = Form(...),
    capital_social: float = Form(...),
    objet_social: str = Form(...),
    duree: int = Form(99),
    date_cloture_exercice: str = Form("31/12"),
    regime_fiscal: str = Form("IS"),
):
    dossier = db.query(Dossier).filter(Dossier.client_id == user.id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    dossier.civilite = civilite
    dossier.nom = nom
    dossier.prenom = prenom
    dossier.nom_jeune_fille = nom_jeune_fille or None
    dossier.date_naissance = date_naissance
    dossier.lieu_naissance = lieu_naissance
    dossier.departement_naissance = departement_naissance
    dossier.nationalite = nationalite
    dossier.situation_matrimoniale = situation_matrimoniale
    dossier.profession_anterieure = profession_anterieure or None
    dossier.adresse_rue = adresse_rue
    dossier.adresse_cp = adresse_cp
    dossier.adresse_ville = adresse_ville
    dossier.adresse_pays = adresse_pays
    dossier.nom_pere = nom_pere
    dossier.prenom_pere = prenom_pere
    dossier.nom_mere = nom_mere
    dossier.prenom_mere_naissance = prenom_mere_naissance
    dossier.denomination_sociale = denomination_sociale
    dossier.siege_social_rue = siege_social_rue
    dossier.siege_social_cp = siege_social_cp
    dossier.siege_social_ville = siege_social_ville
    dossier.capital_social = capital_social
    dossier.objet_social = objet_social
    dossier.duree = duree
    dossier.date_cloture_exercice = date_cloture_exercice
    dossier.regime_fiscal = regime_fiscal
    dossier.status = "formulaire_rempli"
    dossier.form_submitted_at = datetime.utcnow()

    history = StatusHistory(
        dossier_id=dossier.id,
        old_status="invitation_envoyee",
        new_status="formulaire_rempli",
        changed_by=user.id,
        note="Formulaire soumis par le client",
    )
    db.add(history)
    db.commit()

    return RedirectResponse("/client/dashboard", status_code=302)


@app.get("/client/documents")
def client_documents(
    request: Request,
    user: User = Depends(auth.require_client),
    db: Session = Depends(get_db),
):
    dossier = db.query(Dossier).filter(Dossier.client_id == user.id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    uploaded_docs = [d for d in dossier.documents if not d.is_generated]
    generated_docs = [d for d in dossier.documents if d.is_generated]
    return templates.TemplateResponse(
        request,
        "client/documents.html",
        {
            "user": user,
            "dossier": dossier,
            "uploaded_docs": uploaded_docs,
            "generated_docs": generated_docs,
            "success": None,
            "error": None,
        },
    )


@app.post("/client/documents/upload")
async def client_upload_document(
    request: Request,
    user: User = Depends(auth.require_client),
    db: Session = Depends(get_db),
    doc_type: str = Form(...),
    file: UploadFile = File(...),
):
    dossier = db.query(Dossier).filter(Dossier.client_id == user.id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    allowed_types = {"piece_identite", "justificatif_domicile", "attestation_domiciliation"}
    if doc_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Type de document invalide")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB max
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 10 Mo)")

    safe_filename = f"{doc_type}_{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = doc_service.save_uploaded_file(dossier.id, safe_filename, content)

    # Supprimer l'ancien document du même type s'il existe
    old_doc = (
        db.query(Document)
        .filter(Document.dossier_id == dossier.id, Document.type == doc_type, Document.is_generated == False)
        .first()
    )
    if old_doc:
        Path(old_doc.file_path).unlink(missing_ok=True)
        db.delete(old_doc)

    new_doc = Document(
        dossier_id=dossier.id,
        type=doc_type,
        filename=file.filename,
        file_path=file_path,
        is_generated=False,
    )
    db.add(new_doc)

    # Vérifier si tous les justificatifs sont déposés
    required = {"piece_identite", "justificatif_domicile", "attestation_domiciliation"}
    existing_types = {
        d.type
        for d in dossier.documents
        if not d.is_generated and d.type in required
    }
    existing_types.add(doc_type)
    if required.issubset(existing_types) and dossier.status == "documents_signes":
        old_status = dossier.status
        dossier.status = "justificatifs_deposes"
        db.add(StatusHistory(
            dossier_id=dossier.id,
            old_status=old_status,
            new_status="justificatifs_deposes",
            changed_by=user.id,
            note="Tous les justificatifs déposés",
        ))

    db.commit()
    return RedirectResponse("/client/documents", status_code=302)


# ---------------------------------------------------------------------------
# Routes expert
# ---------------------------------------------------------------------------


@app.get("/expert/dashboard")
def expert_dashboard(
    request: Request,
    user: User = Depends(auth.require_expert),
    db: Session = Depends(get_db),
):
    dossiers = db.query(Dossier).order_by(Dossier.updated_at.desc()).all()
    stats = {
        "total": len(dossiers),
        "en_cours": sum(1 for d in dossiers if d.status != "kbis_recu"),
        "termines": sum(1 for d in dossiers if d.status == "kbis_recu"),
    }
    return templates.TemplateResponse(
        request,
        "expert/dashboard.html",
        {"user": user, "dossiers": dossiers, "stats": stats},
    )


@app.get("/expert/dossiers/create")
def expert_create_dossier_page(
    request: Request,
    user: User = Depends(auth.require_expert),
):
    return templates.TemplateResponse(
        request, "expert/create_dossier.html", {"user": user, "error": None, "success": None}
    )


@app.post("/expert/dossiers/create")
def expert_create_dossier(
    request: Request,
    user: User = Depends(auth.require_expert),
    db: Session = Depends(get_db),
    client_email: str = Form(...),
    client_prenom: str = Form(...),
    client_nom: str = Form(...),
):
    # Vérifier si l'email existe déjà
    existing = db.query(User).filter(User.email == client_email).first()
    if existing:
        return templates.TemplateResponse(
            request,
            "expert/create_dossier.html",
            {"user": user, "error": f"Un compte existe déjà pour {client_email}", "success": None},
            status_code=400,
        )

    # Créer le client
    token = str(uuid.uuid4())
    client = User(
        email=client_email,
        role="client",
        prenom=client_prenom,
        nom=client_nom,
        is_active=False,
        invitation_token=token,
        invitation_expires=datetime.utcnow() + timedelta(hours=72),
        invitation_used=False,
    )
    db.add(client)
    db.flush()

    # Créer le dossier
    dossier = Dossier(
        client_id=client.id,
        expert_id=user.id,
        status="invitation_envoyee",
    )
    db.add(dossier)
    db.commit()

    # Envoyer l'email d'invitation
    try:
        email_service.send_invitation_email(client_email, client_prenom, token)
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")

    return templates.TemplateResponse(
        request,
        "expert/create_dossier.html",
        {
            "user": user,
            "error": None,
            "success": f"Invitation envoyée à {client_email}. Dossier #{dossier.id} créé.",
        },
    )


@app.get("/expert/dossiers/{dossier_id}")
def expert_dossier_detail(
    request: Request,
    dossier_id: int,
    user: User = Depends(auth.require_expert),
    db: Session = Depends(get_db),
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return templates.TemplateResponse(
        request,
        "expert/dossier_detail.html",
        {
            "user": user,
            "dossier": dossier,
            "history": sorted(dossier.history, key=lambda h: h.changed_at, reverse=True),
            "success": None,
            "error": None,
        },
    )


@app.post("/expert/dossiers/{dossier_id}/status")
def expert_update_status(
    request: Request,
    dossier_id: int,
    user: User = Depends(auth.require_expert),
    db: Session = Depends(get_db),
    new_status: str = Form(...),
    note: str = Form(""),
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if new_status not in STATUS_ORDER:
        raise HTTPException(status_code=400, detail="Statut invalide")

    old_status = dossier.status
    dossier.status = new_status
    db.add(StatusHistory(
        dossier_id=dossier.id,
        old_status=old_status,
        new_status=new_status,
        changed_by=user.id,
        note=note or None,
    ))
    db.commit()

    # Notifier le client
    try:
        client = dossier.client
        email_service.send_status_update_email(
            client.email, client.prenom, STATUS_LABELS[new_status]
        )
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")

    return RedirectResponse(f"/expert/dossiers/{dossier_id}", status_code=302)


@app.post("/expert/dossiers/{dossier_id}/notes")
def expert_update_notes(
    dossier_id: int,
    user: User = Depends(auth.require_expert),
    db: Session = Depends(get_db),
    notes: str = Form(""),
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    dossier.notes = notes or None
    db.commit()
    return RedirectResponse(f"/expert/dossiers/{dossier_id}", status_code=302)


@app.get("/expert/dossiers/{dossier_id}/pdf/{doc_type}")
def expert_download_pdf(
    dossier_id: int,
    doc_type: str,
    user: User = Depends(auth.require_expert),
    db: Session = Depends(get_db),
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if dossier.status == "invitation_envoyee":
        raise HTTPException(status_code=400, detail="Le formulaire n'a pas encore été rempli")

    if doc_type == "statuts":
        pdf_bytes = doc_service.generate_statuts_pdf(dossier)
        filename = f"statuts_sasu_{dossier.denomination_sociale or dossier_id}.pdf"
        # Sauvegarder en DB
        file_path = doc_service.save_document(dossier_id, "statuts", filename, pdf_bytes)
        _upsert_document(db, dossier_id, "statuts", filename, file_path)
    elif doc_type == "attestation":
        pdf_bytes = doc_service.generate_attestation_pdf(dossier)
        filename = f"attestation_non_condamnation_{dossier_id}.pdf"
        file_path = doc_service.save_document(dossier_id, "attestation", filename, pdf_bytes)
        _upsert_document(db, dossier_id, "attestation", filename, file_path)
    else:
        raise HTTPException(status_code=400, detail="Type de document invalide")

    db.commit()

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _upsert_document(db, dossier_id: int, doc_type: str, filename: str, file_path: str):
    doc = (
        db.query(Document)
        .filter(Document.dossier_id == dossier_id, Document.type == doc_type, Document.is_generated == True)
        .first()
    )
    if doc:
        doc.filename = filename
        doc.file_path = file_path
        doc.created_at = datetime.utcnow()
    else:
        db.add(Document(
            dossier_id=dossier_id,
            type=doc_type,
            filename=filename,
            file_path=file_path,
            is_generated=True,
        ))


@app.post("/expert/dossiers/{dossier_id}/oneflow")
async def expert_send_oneflow(
    dossier_id: int,
    user: User = Depends(auth.require_expert),
    db: Session = Depends(get_db),
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    try:
        pdf_statuts = doc_service.generate_statuts_pdf(dossier)
        pdf_attestation = doc_service.generate_attestation_pdf(dossier)

        contract_id = await oneflow_service.send_to_oneflow(
            dossier=dossier,
            client_email=dossier.client.email,
            pdf_statuts=pdf_statuts,
            pdf_attestation=pdf_attestation,
        )

        dossier.oneflow_contract_id = contract_id
        old_status = dossier.status
        dossier.status = "documents_envoyes_signature"
        db.add(StatusHistory(
            dossier_id=dossier.id,
            old_status=old_status,
            new_status="documents_envoyes_signature",
            changed_by=user.id,
            note=f"Envoyé via Oneflow (contrat #{contract_id})",
        ))
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Oneflow : {str(e)}")

    return RedirectResponse(f"/expert/dossiers/{dossier_id}", status_code=302)


@app.get("/expert/dossiers/{dossier_id}/files/{doc_id}")
def expert_download_uploaded_file(
    dossier_id: int,
    doc_id: int,
    user: User = Depends(auth.require_expert),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.dossier_id == dossier_id,
        Document.is_generated == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur")

    content = file_path.read_bytes()
    media_type = "application/octet-stream"
    if doc.filename.lower().endswith(".pdf"):
        media_type = "application/pdf"
    elif doc.filename.lower().endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif doc.filename.lower().endswith(".png"):
        media_type = "image/png"

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )
