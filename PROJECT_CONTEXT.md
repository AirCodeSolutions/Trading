# Trading-New — PROJECT_CONTEXT.md

> Référence permanente à lire avant tout travail sur Trading-New.
> Les règles stables ci-dessous sont contraignantes. Les métriques, HEAD, PR et états runtime sont périssables et doivent être revalidés au début de chaque chantier.

## 1. Périmètre canonique

- Repo : `AirCodeSolutions/Trading`
- Checkout : `/home/laetitia/trading/Trading`
- Runtime : `/home/laetitia/trading/Trading-runtime`
- Backend : `http://127.0.0.1:8020`
- Frontend : `http://127.0.0.1:5180`
- Broker : MT4
- Mode : DEMO
- `live_trading_enabled=false`
- Magic Trading-New : `560619`

Univers actif : BTCUSD, EURUSD, GBPUSD, XAUUSD, XAGUSD.
Univers abandonné : US500Cash, USA500IDXUSD, USATECHIDXUSD, Volatility, VOLIDXUSD.

## 2. Objectif permanent

Rendre le système économiquement meilleur :
- davantage de trades réellement gagnants ;
- meilleur PnL risk-adjusted ;
- drawdown contrôlé ;
- meilleure capture des mouvements ;
- meilleure détection et mesure de l'edge ;
- apprentissage prospectif sans sur-ajustement ;
- meilleure fidélité PAPER / broker.

Ne jamais présenter comme amélioration :
- réduire artificiellement le nombre de trades ;
- ajouter un cap journalier DEMO ;
- relâcher un guard pour créer des trades ;
- ajouter un veto sur 1–2 pertes ;
- optimiser un threshold sur petit échantillon ;
- accumuler des patches sans hypothèse économique.

## 3. Règles absolues de risque

- Sizing basé sur l'equity MT4 DEMO.
- Hard cap : 5 lots maximum par trade.
- `max_spread_to_stop=0.15`.
- Pas de plafond journalier artificiel en DEMO.
- Ne pas augmenter risque/lots/caps sans preuve.
- Macro guards conservés.
- Une hypothèse économique à la fois.

## 4. Ownership broker

Ne jamais toucher aux positions Freezebee ou externes.

`broker_observed_positions > 0` ne signifie pas automatiquement que Trading-New n'est pas flat.

Flatness Trading-New :
- `bridge_open_positions == 0`
- aucun PAPER ouvert
- `pending_command == null`
- `pending_close_command == null`

Les états PAPER vivent dans :
`/home/laetitia/trading/Trading-runtime/shadow/*_paper_state.json`

## 5. Déploiement obligatoire

Avant merge/pull/restart/deploy :
1. relire ce fichier ;
2. relire la fin de `docs/PROJECT_STATUS.md`, `docs/EVOLUTIONS.md`, `docs/RESEARCH_2026-09-21.md` ;
3. réconcilier Git/PR/CI ;
4. vérifier health/preflight/demo status ;
5. vérifier flatness Trading-New ;
6. drain ON ;
7. merge/pull ;
8. redémarrer uniquement les composants réellement modifiés ;
9. ne pas redémarrer le shadow worker inutilement ;
10. postflight ;
11. drain OFF ;
12. vérifier armed/bridge/pending.

Ne jamais merger/puller/redémarrer/déployer pendant une position Trading-New ouverte.

## 6. Validation

Avant PR significative :
- test RED dédié si correction de bug ;
- tests ciblés ;
- full backend ;
- Ruff ;
- frontend production build ;
- `git diff --check` ;
- CI GitHub verte.

Le runtime DEMO peut polluer certains tests via `.env`. Neutraliser cela uniquement dans le contexte de test ; ne jamais modifier la production pour faire passer un test.

## 7. Qualification prospective

Minimum : 20 trades.

Critères de revue connus :
- expectancy > 0
- PF >= 1.05
- max DD <= 12R

`SUPPORTS_REVIEW` ne donne aucune autorité automatique.
Toute revue reste `requires_human_decision=true`.

États descriptifs existants :
- `COLLECT_MORE`
- `TIMING_RESEARCH`
- `SELECTION_RESEARCH`
- `COST_GRANULARITY_RESEARCH`
- `REVIEW_READY`

Ne jamais activer timing/sélection/coût sans contrat causal explicite et données prospectives suffisantes.

## 8. Populations de preuve à garder séparées

1. Trades admis PAPER/DEMO : référence économique principale.
2. Probes exécutables non qualifiés : apprentissage prospectif.
3. Blocked probes : contrefactuels, avec raison exacte de blocage.
4. Waiting / market opportunities : Value of Waiting, mouvement consommé, précursors.

Ne jamais mélanger ces populations pour fabriquer un edge.

## 9. Microstructure M1

Disponible :
- bid/ask MT4 ;
- M1 ;
- `mid_up_ticks`, `mid_down_ticks` ;
- `directional_tick_samples` ;
- `mid_tick_imbalance` ;
- path efficiency ;
- déplacement 5m/15m ;
- spread.

Ce n'est PAS du Level-2 OFI.

Causalité stricte : une M1 n'est utilisable que si elle est entièrement fermée avant `signal_at`.

Attribution des trous de couverture :
- `pre_collector`
- `insufficient_closed_m1`
- `m1_no_directional_ticks`
- `tick_pressure_available`
- collector state indisponible explicite

Aucun score ni threshold ne doit être dérivé automatiquement de ces états.

## 10. Market-session-aware preflight

États :
- `ready`
- `market_closed`
- `degraded`
- `unknown_session`

Contrat :
- BTCUSD : 24/7 dans le profil Trading-New.
- EURUSD/GBPUSD/XAUUSD/XAGUSD : semaine broker.
- Timezone centrale MT4 : `Europe/Athens`.
- Toute date aware doit être convertie vers cette timezone avant décision.
- Un marché fermé normalement ne doit pas devenir `degraded`.
- Un marché ouvert avec M5 stale doit rester `degraded`.
- Ne jamais inventer une heure de réouverture si la metadata broker ne la fournit pas.

## 11. Incident XAU à ne jamais oublier

Ticket MT4 `185418955`, XAUUSD SELL, 5 lots, asia_range_sweep_reversal.

PAPER : timeout ~-0.3475R, MFE ~+0.0765R, MAE ~0.9802R.
Broker : position non fermée au timeout puis stop, -3220.99 EUR.

Cause technique : commentaire MT4 vide + perte de mapping ticket/strategy après fill.
Correction #153 : conserver ticket exact + strategy_id jusqu'à fermeture ; fallback ownership uniquement sur ticket exact mémorisé.

Ne jamais fermer une position externe à commentaire vide.

## 12. Contrat de revue

- `POST /api/v1/research/probe-review`
- `GET /api/v1/research/probe-review/contract`
- timezone : Europe/Athens
- train end : 2026-07-01
- validation end : 2026-09-01
- prospective evidence window : 168 h

Pas de dates cachées ou dupliquées dans le frontend.

## 13. Recherche économique active

Hypothèse importante : certaines continuations arrivent après qu'une partie trop importante du mouvement a déjà été consommée.

Features gelées :
- déplacement M1 side-aligned 5m/15m en R ;
- tick-pressure ;
- multi-horizon agreement ;
- path efficiency ;
- precursor ;
- spread/risk ;
- MFE/MAE ;
- waiting cost.

Observations historiques de travail, non-thresholds :
- BTC post-shock winner ~0.54R de déplacement 15m avant signal ;
- perte ~2.19R ;
- plusieurs pertes XAU post-shock ~1.8–2.46R.

Continuer la collecte winners/losers comparables.

## 14. Rituel permanent : « on continue »

Quand l'utilisateur dit de continuer, le chantier comprend automatiquement :

### Début
- lire ce fichier ;
- relire les dernières sections des trois docs canoniques ;
- vérifier HEAD local/origin/main ;
- vérifier PR/CI ;
- vérifier runtime, drain, flatness, preflight ;
- recalculer les métriques prospectives avant d'en citer.

### Pendant
- une hypothèse économique à la fois ;
- pas d'audits infinis ;
- pas de duplication de pipeline ;
- agir quand la preuve permet une action ;
- vérifier que le chantier reste relié au PnL.

### Fin
- mettre à jour docs/PR/EVOLUTIONS/PROJECT_STATUS ;
- mettre à jour RESEARCH si l'hypothèse ou la mesure change ;
- fournir un suivi de chantier clair ;
- préciser ce qui est terminé, déployé, en collecte, bloqué et la prochaine étape.

## 15. Recherche internet / veille

Faire de la veille externe si elle peut améliorer une décision ou une hypothèse :
- microstructure ;
- exécution intraday ;
- regime detection ;
- timing ;
- mean reversion / continuation ;
- BTC/XAU/FX/métaux ;
- volatilité/macros/FOMC ;
- validation robuste.

Règles :
- ne jamais copier une stratégie web directement ;
- distinguer littérature externe / hypothèse / données Trading-New ;
- vérifier que les données nécessaires existent ;
- transformer toute idée externe en hypothèse mesurable et prospective ;
- privilégier sources primaires, récentes et techniques ;
- documenter les références utiles dans RESEARCH.

La veille forme les hypothèses ; elle ne remplace jamais la preuve prospective.

## 16. Hiérarchie des sources de vérité

Règles permanentes :
1. ce fichier ;
2. code `main` ;
3. docs canoniques.

État du code :
1. GitHub main ;
2. HEAD local ;
3. branche/PR.

État runtime :
1. endpoints live ;
2. fichiers runtime ;
3. processus ;
4. docs de dernier déploiement.

Résultats research :
1. données runtime prospectives actuelles ;
2. artefacts causaux ;
3. docs historiques.

Ne jamais remplacer une mesure actuelle par un chiffre mémorisé.

## 17. État de référence au 2026-09-26

Dernier HEAD vérifié après #165 :
`9e7bc21a5f59a31f85b56926248deadd71c17799`

PR structurantes récentes :
- #161 gap attribution
- #162 docs
- #163 market-session-aware readiness
- #164 docs
- #165 timezone normalization

Snapshot prospectif connu mais périssable :
- BTC directional : 6/20, 4W/2L, +4.02R, exp +0.67R, PF 3.01, DD 1R.
- GBP failed auction : 7/20, 3W/4L, +1.20R, exp +0.17R, PF 1.37, DD 2.30R.
- XAU directional : 5/20, 2W/3L, +0.60R, exp +0.12R, PF 1.20, DD 2R.

Toujours recalculer avant décision.

## 18. Suivi de chantier attendu

Rapporter au minimum :
1. HEAD ;
2. PR créées/fusionnées/ouvertes ;
3. CI/tests ;
4. évolutions terminées/déployées ;
5. runtime ;
6. drain ;
7. flatness Trading-New ;
8. positions externes vues mais non touchées ;
9. candidats prospectifs ;
10. diagnostic économique ;
11. recherche en cours ;
12. blocages ;
13. prochaine étape.

## 19. Consigne courte pour tout agent

> Lis PROJECT_CONTEXT.md avant toute action. Réconcilie ensuite main, les docs canoniques et le runtime live. Respecte flatness/drain, ne touche jamais aux positions externes, conserve le hard cap 5 lots et max_spread_to_stop=0.15, n'ajoute aucun threshold sur petit échantillon, et ne confonds jamais recherche descriptive avec autorité trading. Une hypothèse économique à la fois, tests avant merge, déploiement seulement book Trading-New flat.


## 20. Reconstruction Trading-New V2 — directive 2026-09-29, état 2026-10-01

Le plan directeur V2 est versionné dans :
- `context.md`
- `TRADING_NEW_V2_PLAN.md`

Ordre directeur :
1. Opportunity Engine V2 ;
2. Market State V2 ;
3. Executable Entry Zone ;
4. Trigger Engine M1/M5 ;
5. Position Manager V2 ;
6. spécialisation par actif ;
7. Champion / Challengers ;
8. Portfolio Opportunity Allocator ;
9. simplification ;
10. validation économique et déploiement V2.

Au 2026-10-01, les dix étapes sont implémentées et mergées (#179 à #188). La suite du chantier est économique et prospective : convertir les briques V2 en meilleures décisions de trading sans ajouter de filtres opportunistes ni diminuer les garde-fous.

Correctifs post-plan déployés :
- #189 sépare PAPER collection et broker DEMO : `SUPPORTS_DEMO` est requis pour toute nouvelle autorité broker ;
- #190 permet à une admission SHADOW d’accéder à PAPER lorsque ses probes prospectifs atteignent les seuils existants, mais interdit toute promotion probe → broker et toute promotion REJECTED → PAPER.

### Gouvernance des agents

- ChatGPT conserve la maîtrise du chantier : architecture, économie, risque, revue PR, merge et déploiement.
- Codex Luna exécute uniquement des prompts bornés à l’étape/hypothèse courante quand il est utilisé.
- Aucun agent ne modifie risque, lots, spread guard ou autorité broker sans preuve et revue.
- Une hypothèse économique à la fois.

### Dashboard transversal

Toute évolution backend V2 doit conserver un contrat de visibilité dashboard. PAPER, research probes et broker DEMO doivent rester distingués visuellement et sémantiquement.

### Suivi de chantier obligatoire

À chaque chat Trading-New, rapporter : HEAD main, PR/CI, étape ou hypothèse active, dashboard, runtime/drain/flatness, changements économiques, research-only, blocages, prochaine action et prompt Codex si pertinent.


## 2026-10-01 — Post-V2 economic acceleration chantier

The technical 10-step V2 rebuild is complete. The next chantier is
`docs/POST_V2_ECONOMIC_ACCELERATION.md`.

Priorities:
- P0: paired economic contracts and versioned evidence cutovers;
- P1: authority-regret measurement, controlled actual-equity admission refresh,
  and causal regime/session attribution;
- P2: execution-cost stress and family-specific exit challengers.

The first active experiment is XAU structural displacement 1R champion vs 1.5R
challenger on exactly paired PAPER signals. This comparison is research-only and
cannot create broker authority.


## 2026-10-01 — P1-A Authority Regret

Post-V2 economic acceleration P1-A is implemented as a research-only ledger.
It measures accepted PAPER/DEMO outcomes, executable authority rejections and
economic-guard counterfactuals without changing any authority path.

Critical interpretation: only resolved unqualified executable probes count
toward winners-missed / losses-avoided. Blocked probes remain a separate guard
counterfactual population. Broker-net costs are not fabricated when exact fills
are unavailable.


## 2026-10-01 — P1-B admission refresh control

P1-B replaces the previous immediate runtime-admission refresh surface with a
preview/apply contract. Preview is read-only. Apply is permitted only with drain
ON, Trading-New BOOK_FLAT and complete research coverage for active assets.

The heavy replay remains on-demand and outside the shadow-worker heartbeat.
Dashboard users can preview the diff but cannot apply it from the UI.


## 2026-10-01 — P1-C regime/session attribution

P1-C is scoped only to XAU structural displacement 1.5R. Session and M15 regime
partitions are fixed before interpretation, validation and holdout are separate,
and no cross-product/ranking is produced.

Current read-only replay reconstructs 25 validation and 14 holdout outcomes.
The report is descriptive only and cannot alter admission, PAPER or broker
authority.
