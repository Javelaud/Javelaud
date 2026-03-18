"""
Récupération et export des écritures bancaires depuis l'API Bridge.

Usage rapide :
    from bridge import BridgeClient, TransactionsFetcher

    with BridgeClient() as client:
        fetcher = TransactionsFetcher(client)
        ecritures = fetcher.fetch_all(since="2024-01-01", until="2024-12-31")
        fetcher.export_csv(ecritures, "ecritures_2024.csv")
"""

import csv
import json
from datetime import date
from typing import Generator, Optional

from .client import BridgeClient


class TransactionsFetcher:
    """Récupère l'ensemble des écritures bancaires avec pagination automatique."""

    def __init__(self, client: BridgeClient):
        self.client = client

    # ------------------------------------------------------------------
    # Récupération
    # ------------------------------------------------------------------

    def iter_pages(
        self,
        account_id: Optional[int] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 500,
    ) -> Generator[list[dict], None, None]:
        """Itère sur toutes les pages de transactions et génère chaque liste."""
        after = None
        while True:
            page = self.client.get_transactions(
                account_id=account_id,
                since=since,
                until=until,
                limit=limit,
                after=after,
            )
            resources = page.get("resources", [])
            if not resources:
                break
            yield resources

            pagination = page.get("pagination", {})
            next_uri = pagination.get("next_uri")
            if not next_uri:
                break
            # Extraction du curseur `after` depuis l'URI
            # ex: /v3/transactions?after=<cursor>&...
            after = _extract_after_cursor(next_uri)
            if not after:
                break

    def fetch_all(
        self,
        account_id: Optional[int] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> list[dict]:
        """Retourne toutes les écritures bancaires en une seule liste."""
        transactions: list[dict] = []
        for page in self.iter_pages(account_id=account_id, since=since, until=until):
            transactions.extend(page)
        return transactions

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(self, transactions: list[dict], filepath: str) -> None:
        """
        Exporte les écritures au format CSV.

        Colonnes : id, date, amount, currency, description, category, account_id.
        """
        if not transactions:
            return

        fieldnames = ["id", "date", "amount", "currency", "description", "category_id", "account_id"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for tx in transactions:
                writer.writerow({
                    "id": tx.get("id"),
                    "date": tx.get("date"),
                    "amount": tx.get("amount"),
                    "currency": tx.get("currency_code"),
                    "description": tx.get("label") or tx.get("clean_description", ""),
                    "category_id": tx.get("category_id"),
                    "account_id": tx.get("account_id"),
                })

    def export_json(self, transactions: list[dict], filepath: str) -> None:
        """Exporte les écritures brutes au format JSON."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(transactions, f, ensure_ascii=False, indent=2, default=str)

    # ------------------------------------------------------------------
    # Résumé
    # ------------------------------------------------------------------

    def summary(self, transactions: list[dict]) -> dict:
        """Retourne un résumé statistique des écritures."""
        if not transactions:
            return {"count": 0, "total_credit": 0.0, "total_debit": 0.0, "balance": 0.0}

        total_credit = sum(tx["amount"] for tx in transactions if tx.get("amount", 0) > 0)
        total_debit = sum(tx["amount"] for tx in transactions if tx.get("amount", 0) < 0)
        return {
            "count": len(transactions),
            "total_credit": round(total_credit, 2),
            "total_debit": round(total_debit, 2),
            "balance": round(total_credit + total_debit, 2),
            "date_min": min((tx.get("date", "") for tx in transactions), default=None),
            "date_max": max((tx.get("date", "") for tx in transactions), default=None),
        }


# ------------------------------------------------------------------
# Utilitaires
# ------------------------------------------------------------------

def _extract_after_cursor(next_uri: str) -> Optional[str]:
    """Extrait le paramètre `after` d'une URI de pagination Bridge."""
    if "after=" not in next_uri:
        return None
    for part in next_uri.split("&"):
        if part.startswith("after=") or "?after=" in part:
            return part.split("after=")[-1]
    return None
