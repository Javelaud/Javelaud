import os
import httpx
from models import Dossier

ONEFLOW_API_TOKEN = os.getenv("ONEFLOW_API_TOKEN", "")
ONEFLOW_WORKSPACE_ID = os.getenv("ONEFLOW_WORKSPACE_ID", "")
BASE_URL = "https://api.oneflow.com/v1"


def _headers() -> dict:
    return {
        "x-oneflow-api-token": ONEFLOW_API_TOKEN,
        "Accept": "application/json",
    }


async def send_to_oneflow(
    dossier: Dossier,
    client_email: str,
    pdf_statuts: bytes,
    pdf_attestation: bytes,
) -> str:
    """
    Crée un contrat Oneflow, upload les PDFs, ajoute le signataire et publie.
    Retourne le contract_id Oneflow.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Créer le contrat
        contract_payload = {
            "name": f"SASU {dossier.denomination_sociale or 'Nouvelle société'}",
            "workspace": {"id": int(ONEFLOW_WORKSPACE_ID)},
            "parties": [
                {
                    "name": f"{dossier.prenom or ''} {dossier.nom or ''}".strip(),
                    "type": 1,  # individual
                    "participants": [
                        {
                            "name": f"{dossier.prenom or ''} {dossier.nom or ''}".strip(),
                            "email": client_email,
                            "delivery_channel": 1,  # email
                            "signatory": True,
                        }
                    ],
                }
            ],
        }
        resp = await client.post(
            f"{BASE_URL}/contracts",
            json=contract_payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        contract_id = resp.json()["id"]

        # 2. Upload statuts
        files_statuts = {
            "file": (
                f"statuts_sasu_{dossier.denomination_sociale or dossier.id}.pdf",
                pdf_statuts,
                "application/pdf",
            )
        }
        resp = await client.post(
            f"{BASE_URL}/contracts/{contract_id}/documents",
            files=files_statuts,
            headers=_headers(),
        )
        resp.raise_for_status()

        # 3. Upload attestation
        files_attestation = {
            "file": (
                f"attestation_non_condamnation_{dossier.id}.pdf",
                pdf_attestation,
                "application/pdf",
            )
        }
        resp = await client.post(
            f"{BASE_URL}/contracts/{contract_id}/documents",
            files=files_attestation,
            headers=_headers(),
        )
        resp.raise_for_status()

        # 4. Publier le contrat (envoi des invitations de signature)
        resp = await client.post(
            f"{BASE_URL}/contracts/{contract_id}/publish",
            headers=_headers(),
        )
        resp.raise_for_status()

        return str(contract_id)


async def get_contract_status(contract_id: str) -> dict:
    """Retourne le statut du contrat Oneflow."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}/contracts/{contract_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
