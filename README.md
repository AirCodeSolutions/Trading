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
- décisions causales et rejouables ;
- entrée historique sur la bougie suivante, jamais sur la bougie qui crée le signal ;
- performance mesurée avec spread, slippage et contraintes de lot ;
- aucun trade si lot minimum, spread ou marge rendent le risque incompatible avec le capital ;
- aucune stratégie expérimentale ne peut atteindre l'exécution avant admission `ACTIVE`.

## Capital de référence

Le projet est calibré sur **200 EUR** de capital économique, même lorsque le compte MT4 de démonstration dispose d'un solde très supérieur.

Politique initiale :

- risque de base : 1 % par trade ;
- plafond absolu : 2 % par trade ;
- perte journalière maximale : 3 % ;
- spread maximal : 15 % de la distance au stop ;
- marge maximale : 25 % du capital.

Ces valeurs sont des garde-fous d'exécution, pas une preuve d'edge.

## Opportunity Engine

Le contexte est déterminé en M15. Les déclencheurs sont recherchés en M5.

Mécanismes de recherche actuels :

- `post_shock_continuation` ;
- `break_retest_reaccel` ;
- `failed_auction_reversal`.

Le backtester :

- simule Bid/Ask ;
- applique le spread et un slippage configurable ;
- donne priorité au stop lorsque stop et target sont touchés dans la même bougie ;
- arrondit le lot selon MT4 ;
- sépare les rejets d'exécution des pertes de stratégie ;
- produit train / validation / holdout ;
- passe le résultat au contrat d'admission REJECTED / SHADOW / ACTIVE.

La matrice portefeuille teste tous les couples marché × mécanisme disponibles. Si aucun couple n'est `ACTIVE`, elle renvoie explicitement aucune stratégie qualifiée.

## MT4

`mt4/TradingMarketExporter.mq4` exporte les spécifications broker nécessaires au sizing.

Le backend accepte deux formats d'historique :

- `SYMBOL-M5.csv` / `SYMBOL-M15.csv` ;
- `mt4_research_bars_SYMBOL_M5.csv` / `M15.csv`, fermés uniquement et horodatés en epoch.

Les exports research fermés sont prioritaires lorsqu'ils existent.

Configuration :

```bash
TRADING_MT4_FILES_DIR=/path/to/MetaQuotes/Terminal/<id>/MQL4/Files
TRADING_MT4_SERVER_TIMEZONE=Europe/Athens
```

## API de recherche

- `GET /api/v1/market/mt4/specs`
- `POST /api/v1/research/mt4/backtest`
- `POST /api/v1/research/mt4/matrix`

Ces routes sont de recherche et n'envoient aucun ordre broker.

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

Voir `docs/ARCHITECTURE.md` et les fichiers `docs/RESEARCH_*.md`.


## Runtime portfolio and safety layers

The deployed runtime now includes:

- multi-market inventory for MT4 history, broker quotes and symbol specifications;
- prospective SHADOW/paper ledgers per market × mechanism;
- persistent historical admission registry;
- Portfolio Manager with `NO_TRADE`, `PAPER_ONLY` and `DEMO_ELIGIBLE`;
- consolidated paper PnL, open risk and drawdown;
- observed spread history;
- USD macro blackout gate using verified Fed/BLS/BEA dates;
- MT4 DEMO execution bridge guarded by account type, portfolio qualification,
  macro blackout, approval status and live-trading lock;
- cron-based restart/watchdog because user-level systemd is unavailable.

The DEMO bridge is disabled by default. Real-money execution remains locked.

### Deployed ports

The operational deployment uses configurable ports; the current Bot-IA deployment reserves:

- frontend: `5180`;
- backend: `8020`.

`ops/start_trading.sh` refuses to start a duplicate service when those ports are
already listening.

### Historical admission refresh

`backend/scripts/refresh_research_admissions.py` reproduces the frozen research
split and persists the admission registry. The split boundaries do not roll
forward automatically, which prevents the historical holdout from silently
changing over time.
