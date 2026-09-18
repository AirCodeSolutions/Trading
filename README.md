# Trading

Application de trading intraday conçue autour des timeframes **M5** et **M15**.

## Stack

- Backend : Python 3.12 + FastAPI.
- Frontend : React 19 + TypeScript + Vite.
- Tests : pytest.
- CI : GitHub Actions.

## Principes

- séparation stricte entre données de marché, stratégie, risque et exécution ;
- mode `paper` par défaut ;
- trading live verrouillé par défaut ;
- stratégies indépendantes du broker ;
- décisions causales et rejouables ;
- mesure de performance après coûts.

## Lancer le backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

API : `http://localhost:8000/api/v1/health`.

## Lancer le frontend

```bash
cd frontend
npm install
npm run dev
```

UI : `http://localhost:5173`.

## État du premier incrément

Le socle accepte des bougies M5/M15, expose la configuration de sécurité, contient les contrats de domaine Strategy/Risk/Broker et fournit un premier dashboard React.

Voir `docs/ARCHITECTURE.md` pour la cible.
