import os
from pathlib import Path
from datetime import datetime

import weasyprint
from jinja2 import Environment, FileSystemLoader

from models import Dossier

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
TEMPLATE_DIR = Path(__file__).parent / "document_templates"

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


def _format_date(date_str: str | None) -> str:
    if not date_str:
        return "________________"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return date_str


def generate_statuts_pdf(dossier: Dossier) -> bytes:
    template = jinja_env.get_template("statuts_sasu.html")
    html = template.render(
        dossier=dossier,
        date_today=datetime.now().strftime("%d/%m/%Y"),
        date_naissance=_format_date(dossier.date_naissance),
    )
    return weasyprint.HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()


def generate_attestation_pdf(dossier: Dossier) -> bytes:
    template = jinja_env.get_template("attestation.html")
    html = template.render(
        dossier=dossier,
        date_today=datetime.now().strftime("%d/%m/%Y"),
        date_naissance=_format_date(dossier.date_naissance),
    )
    return weasyprint.HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()


def save_document(dossier_id: int, doc_type: str, filename: str, content: bytes) -> str:
    folder = Path(UPLOAD_DIR) / str(dossier_id)
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / filename
    file_path.write_bytes(content)
    return str(file_path)


def save_uploaded_file(dossier_id: int, filename: str, content: bytes) -> str:
    return save_document(dossier_id, "upload", filename, content)
