"""
Client HTTP pour l'API Bridge (https://docs.bridgeapi.io)
Gère l'authentification et les appels à l'API.
"""

import os
import httpx
from typing import Optional


BRIDGE_API_BASE_URL = "https://api.bridgeapi.io/v3"


class BridgeClient:
    """Client pour l'API Bridge avec gestion de l'authentification."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_token: Optional[str] = None,
    ):
        self.client_id = client_id or os.environ["BRIDGE_CLIENT_ID"]
        self.client_secret = client_secret or os.environ["BRIDGE_CLIENT_SECRET"]
        self.user_token = user_token or os.environ.get("BRIDGE_USER_TOKEN", "")
        self._http = httpx.Client(
            base_url=BRIDGE_API_BASE_URL,
            headers={
                "Client-Id": self.client_id,
                "Client-Secret": self.client_secret,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _auth_header(self) -> dict:
        return {"Authorization": f"Bearer {self.user_token}"}

    # ------------------------------------------------------------------
    # Authentification
    # ------------------------------------------------------------------

    def create_user(self, email: str, password: str) -> dict:
        """Crée un utilisateur Bridge et retourne son token d'accès."""
        resp = self._http.post(
            "/users",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.user_token = data.get("access_token", "")
        return data

    def authenticate_user(self, email: str, password: str) -> str:
        """Authentifie un utilisateur existant et retourne son access token."""
        resp = self._http.post(
            "/authenticate",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.user_token = data.get("access_token", "")
        return self.user_token

    # ------------------------------------------------------------------
    # Comptes
    # ------------------------------------------------------------------

    def list_accounts(self) -> list[dict]:
        """Retourne la liste des comptes bancaires de l'utilisateur."""
        resp = self._http.get("/accounts", headers=self._auth_header())
        resp.raise_for_status()
        return resp.json().get("resources", [])

    # ------------------------------------------------------------------
    # Transactions (écritures bancaires)
    # ------------------------------------------------------------------

    def get_transactions(
        self,
        account_id: Optional[int] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 500,
        after: Optional[str] = None,
    ) -> dict:
        """
        Récupère les transactions d'un compte (une page).

        Args:
            account_id: Identifiant du compte (None = tous les comptes).
            since: Date de début au format ISO 8601 (ex: "2024-01-01").
            until: Date de fin au format ISO 8601 (ex: "2024-12-31").
            limit: Nombre maximum de transactions par page (max 500).
            after: Curseur de pagination (valeur `next_uri` de la réponse précédente).

        Returns:
            Dictionnaire avec les clés `resources` (liste) et `pagination`.
        """
        params: dict = {"limit": limit}
        if account_id is not None:
            params["account_id"] = account_id
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if after:
            params["after"] = after

        resp = self._http.get(
            "/transactions",
            params=params,
            headers=self._auth_header(),
        )
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
