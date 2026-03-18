"""
Bridge API - Module de récupération des écritures bancaires
"""

from .client import BridgeClient
from .transactions import TransactionsFetcher

__all__ = ["BridgeClient", "TransactionsFetcher"]
