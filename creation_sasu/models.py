from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    role = Column(String, nullable=False)  # "client" | "expert"
    prenom = Column(String, nullable=False)
    nom = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)
    invitation_token = Column(String, unique=True, nullable=True)
    invitation_expires = Column(DateTime, nullable=True)
    invitation_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    dossiers_client = relationship("Dossier", foreign_keys="Dossier.client_id", back_populates="client")
    dossiers_expert = relationship("Dossier", foreign_keys="Dossier.expert_id", back_populates="expert")


class Dossier(Base):
    __tablename__ = "dossiers"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expert_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="invitation_envoyee", nullable=False)

    # Dirigeant / Associé unique
    civilite = Column(String, nullable=True)  # M. / Mme
    nom = Column(String, nullable=True)
    prenom = Column(String, nullable=True)
    nom_jeune_fille = Column(String, nullable=True)
    date_naissance = Column(String, nullable=True)  # "YYYY-MM-DD"
    lieu_naissance = Column(String, nullable=True)
    departement_naissance = Column(String, nullable=True)
    nationalite = Column(String, nullable=True)
    situation_matrimoniale = Column(String, nullable=True)
    profession_anterieure = Column(String, nullable=True)

    # Adresse du dirigeant
    adresse_rue = Column(String, nullable=True)
    adresse_cp = Column(String, nullable=True)
    adresse_ville = Column(String, nullable=True)
    adresse_pays = Column(String, default="France", nullable=True)

    # Filiation (pour attestation)
    nom_pere = Column(String, nullable=True)
    prenom_pere = Column(String, nullable=True)
    nom_mere = Column(String, nullable=True)
    prenom_mere_naissance = Column(String, nullable=True)

    # Société
    denomination_sociale = Column(String, nullable=True)
    siege_social_rue = Column(String, nullable=True)
    siege_social_cp = Column(String, nullable=True)
    siege_social_ville = Column(String, nullable=True)
    capital_social = Column(Float, nullable=True)
    objet_social = Column(Text, nullable=True)
    duree = Column(Integer, nullable=True)  # années, max 99
    date_cloture_exercice = Column(String, nullable=True)  # ex: "31/12"
    regime_fiscal = Column(String, default="IS", nullable=True)

    # Oneflow
    oneflow_contract_id = Column(String, nullable=True)

    # Notes expert
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    form_submitted_at = Column(DateTime, nullable=True)

    client = relationship("User", foreign_keys=[client_id], back_populates="dossiers_client")
    expert = relationship("User", foreign_keys=[expert_id], back_populates="dossiers_expert")
    documents = relationship("Document", back_populates="dossier", cascade="all, delete-orphan")
    history = relationship("StatusHistory", back_populates="dossier", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    dossier_id = Column(Integer, ForeignKey("dossiers.id"), nullable=False)
    type = Column(String, nullable=False)
    # statuts | attestation | piece_identite | justificatif_domicile | attestation_domiciliation
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    is_generated = Column(Boolean, default=True)  # True = généré par app, False = uploadé client
    created_at = Column(DateTime, default=datetime.utcnow)

    dossier = relationship("Dossier", back_populates="documents")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True)
    dossier_id = Column(Integer, ForeignKey("dossiers.id"), nullable=False)
    old_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    note = Column(Text, nullable=True)

    dossier = relationship("Dossier", back_populates="history")


# Ordre logique des statuts
STATUS_ORDER = [
    "invitation_envoyee",
    "formulaire_rempli",
    "documents_envoyes_signature",
    "documents_signes",
    "justificatifs_deposes",
    "journal_annonce_legale",
    "envoi_inpi",
    "kbis_recu",
]

STATUS_LABELS = {
    "invitation_envoyee": "Invitation envoyée",
    "formulaire_rempli": "Formulaire rempli",
    "documents_envoyes_signature": "Documents envoyés pour signature",
    "documents_signes": "Documents signés",
    "justificatifs_deposes": "Justificatifs déposés",
    "journal_annonce_legale": "Journal d'annonce légale",
    "envoi_inpi": "Envoi INPI",
    "kbis_recu": "KBIS reçu",
}
