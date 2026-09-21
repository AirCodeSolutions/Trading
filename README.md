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
- admissions historiques basées sur un modèle de spread gelé et versionné,
  jamais sur le spread live instantané du refresh ;
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

## Active market scope

The active development/runtime scope is deliberately limited to:

- BTCUSD
- EURUSD
- GBPUSD
- XAUUSD
- XAGUSD

US500Cash, USA500IDXUSD, USATECHIDXUSD, Volatility and VOLIDXUSD are out of
scope and must not be reintroduced into the active watchlist without an explicit
scope decision.

## Opportunity Engine

Le contexte est déterminé en M15. Les déclencheurs sont recherchés en M5.

Mécanismes de recherche actuels :

- `post_shock_continuation` ;
- `break_retest_reaccel` ;
- `failed_auction_reversal` ;
- `directional_transition` — première transition causale M15 vers `directional_expansion` ;
- `directional_pullback_resumption` — GBPUSD SHADOW only: régime M15 directionnel,
  deux M5 de pullback puis clôture de reprise au-delà de l'extrême de la seconde
  bougie, stop derrière le swing local.

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
forward automatically.

Historical spread is also frozen through
`backend/config/research_execution_model.json`, calibrated from observed median
broker spreads. Runtime execution still uses the current live spread. This
prevents admissions from changing merely because the refresh ran at a different
time of day.


## Multi-market MT4 bridge

`TradingMarketExporter.mq4` is a read-only Expert Advisor. When attached to one
MT4 chart it exports `trading_symbol_specs.csv` every few seconds with sanitized
quotes and broker specifications for the configured symbol list.

The backend consumes that single file for:

- live BID/ASK display;
- symbol specification discovery;
- spread history;
- paper-readiness of additional markets.

Unavailable aliases are skipped instead of emitting zero prices. The EA never
creates, modifies or closes orders.

`TradingDemoExecutionBridge.mq4` is separate and remains disabled unless
`AllowDemoExecution=true` is explicitly configured in MT4 and all backend
qualification guards pass.


## Session preflight

The runtime exposes `/api/v1/session/preflight` for market-reopen readiness.

It combines:

- SHADOW worker heartbeat freshness;
- broker quote freshness;
- M5/M15 history availability;
- broker symbol specification availability;
- paper readiness;
- macro blackout state;
- Portfolio Manager action;
- DEMO execution guard.

The UI classifies the runtime as:

- `READY`: at least one watched non-BTC market is paper-ready and the worker is healthy;
- `WAITING_MARKET`: infrastructure is healthy but non-BTC quotes are not live yet;
- `DEGRADED`: an open-market quote is live while required history/specs are incomplete;
- `BLOCKED`: the worker heartbeat is missing, failed or older than 180 seconds.

The watchdog runs every minute. A stale worker heartbeat causes only the SHADOW
worker to restart; backend, frontend and MT4 are left untouched.


## Session reopen continuity guard

A large M5 discontinuity (>20 minutes) is treated as a session/data reopen, not as
a tradable information shock. The first three closed M5 bars after the gap are
warmup-only:

- SHADOW signals are suppressed;
- historical candidate generation applies the same rule;
- the worker heartbeat reports warming markets;
- Session Preflight displays `WARMING_UP` until three full M5 bars are available.

This prevents weekend gaps or feed interruptions from becoming artificial
`post_shock`, breakout or transition opportunities.


## Session recovery timeline and stalled-feed detection

Session Preflight persists a small runtime state per watched market:

- first broker quote observed LIVE;
- first fresh closed M5 after reopening;
- end of warmup / READY timestamp;
- first M5 stall detection timestamp;
- latest closed M5 timestamp.

A market with a LIVE broker quote but no fresh closed M5 remains WARMING_UP.
If that condition lasts more than 20 minutes after the quote returned, it becomes
M5_STALLED and the global preflight becomes DEGRADED.

The runtime state is stored atomically in
`runtime/shadow/session_state.json`.

The watchdog uses `worker_healthy`, not only the worker PID: a live process with
an error heartbeat or a heartbeat older than 180 seconds is terminated and only
the SHADOW worker is restarted. Backend, frontend and MT4 remain untouched.


## Evidence cutover

Paper entry-bar causality was corrected in PR #13. Prospective qualification now
uses only trades opened from `2026-09-20T12:53:56+03:00` onward.

Older trades remain visible as legacy evidence and are never deleted. At the
2026-09-21 status checkpoint the ledger contains:

- post-cutover: 1 closed GBPUSD trade / +1.5R / +2.7329 EUR;
- legacy: 7 BTC trades / -7R / -10.8621 EUR.

See `docs/PROJECT_STATUS.md` and `docs/EVOLUTIONS.md` for the current source of
truth.
