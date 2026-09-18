# Trading

Application de trading intraday conçue autour des timeframes **M5** et **M15**.

## Stack

- Backend : Python 3.12 + FastAPI.
- Frontend : React 19 + TypeScript + Vite.
- Broker cible : MT4, via un adaptateur isolé du moteur de stratégie.
- Tests : pytest.
- CI : GitHub Actions.

## Principes

- séparation stricte entre données de marché, stratégie, risque et exécution ;
- capital de référence indépendant du solde du compte démo ;
- mode `paper` par défaut et trading live verrouillé ;
- stratégies indépendantes du broker ;
- décisions causales et rejouables ;
- performance mesurée après coûts ;
- aucun trade si le lot minimum, le spread ou la marge rendent le risque incompatible avec le capital.

## Capital de référence

Le projet est actuellement calibré sur **200 €** de capital économique, même lorsque le compte MT4 de démonstration dispose d’un solde très supérieur.

Politique initiale :

- risque de base : 1 % par trade ;
- plafond absolu : 2 % par trade ;
- perte journalière maximale : 3 % ;
- spread maximal : 15 % de la distance au stop.

Ces valeurs sont des garde-fous d’exécution, pas une preuve d’edge.

## MT4

`mt4/TradingMarketExporter.mq4` exporte les spécifications broker nécessaires au sizing : bid/ask, tick size/value, lots, marge et autres contraintes.

Les historiques `SYMBOL-M5.csv` et `SYMBOL-M15.csv` peuvent être lus directement par le backend via `TRADING_MT4_FILES_DIR`.

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

Voir `docs/ARCHITECTURE.md` pour la cible.
