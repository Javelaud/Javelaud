# Bridge - Récupération des écritures bancaires

Ce module permet de récupérer les écritures bancaires (transactions) depuis l'[API Bridge](https://docs.bridgeapi.io).

## Configuration

1. Copiez `.env.example` en `.env` et renseignez vos identifiants Bridge :

```
BRIDGE_CLIENT_ID=...
BRIDGE_CLIENT_SECRET=...
BRIDGE_USER_TOKEN=...   # obtenu après authentification
```

2. Installez la dépendance :

```bash
pip install httpx
```

## Utilisation

### Récupérer toutes les écritures

```python
from bridge import BridgeClient, TransactionsFetcher

with BridgeClient() as client:
    fetcher = TransactionsFetcher(client)

    # Toutes les écritures de 2024
    ecritures = fetcher.fetch_all(since="2024-01-01", until="2024-12-31")

    # Résumé
    print(fetcher.summary(ecritures))

    # Export
    fetcher.export_csv(ecritures, "ecritures_2024.csv")
    fetcher.export_json(ecritures, "ecritures_2024.json")
```

### Filtrer par compte

```python
ecritures = fetcher.fetch_all(account_id=123456, since="2024-01-01")
```

### Pagination manuelle

```python
for page in fetcher.iter_pages(since="2024-01-01"):
    for tx in page:
        print(tx["date"], tx["amount"], tx["label"])
```

### Authentifier un utilisateur

```python
with BridgeClient() as client:
    token = client.authenticate_user("email@exemple.fr", "motdepasse")
    comptes = client.list_accounts()
```

## Structure des fichiers

```
bridge/
├── __init__.py         # Exports principaux
├── client.py           # Client HTTP et authentification
├── transactions.py     # Récupération et export des écritures
├── .env.example        # Template des variables d'environnement
└── README.md           # Ce fichier
```

## Champs d'une écriture

| Champ | Description |
|-------|-------------|
| `id` | Identifiant unique |
| `date` | Date de valeur (ISO 8601) |
| `amount` | Montant (négatif = débit, positif = crédit) |
| `currency_code` | Devise (ex: `EUR`) |
| `label` | Libellé brut |
| `clean_description` | Libellé nettoyé |
| `category_id` | Catégorie Bridge |
| `account_id` | Identifiant du compte |
