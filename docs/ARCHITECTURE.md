# Architecture

## Objectif

Construire une application de trading M5/M15 testable, observable et indépendante du broker, avec un chemin identique entre recherche causale et runtime.

## Flux cible

1. **MT4 Market Data** — bougies fermées, quotes et spécifications broker.
2. **Market Selector** — élimine les instruments incompatibles avec le capital.
3. **Regime Engine M15** — classe le contexte avant toute recherche d'entrée.
4. **Opportunity Engine M5** — produit des candidats propres au régime.
5. **Causal Backtester** — exécute la bougie suivante avec modèle Bid/Ask.
6. **Strategy Admission** — REJECTED, SHADOW ou ACTIVE.
7. **Portfolio Matrix** — compare marché × mécanisme et ne qualifie que les couples ACTIVE.
8. **Capital Risk Engine** — sizing depuis le capital économique de référence courant (400 EUR depuis le 2026-09-22), jamais depuis le gros solde démo.
9. **Approval Gate** — mode AUTO ou CONFIRM.
10. **Macro Gate** — bloque les nouvelles entrées autour des événements USD à fort impact.
11. **MT4 DEMO Execution Adapter** — bridge isolé, désactivé par défaut, avec rapprochement commandes/résultats/positions.
12. **Ledger / Analytics** — décisions, rejets, paper trades, PnL, coûts et drawdown.
13. **React UI** — univers marché, portefeuille, macro, SHADOW/paper et état DEMO.
14. **Ops watchdog** — autostart/recovery via cron lorsque systemd utilisateur n'est pas disponible.

## Regime Engine

Le moteur M15 utilise uniquement l'historique disponible au moment de la décision.

États :

- `warmup` ;
- `dead` ;
- `balanced_auction` ;
- `directional_expansion` ;
- `post_shock`.

Les seuils initiaux sont des définitions fixes de recherche, pas les meilleurs paramètres trouvés par grid search.

## Opportunity Engine

Six mécanismes de recherche sont actuellement implémentés :

### post_shock_continuation

Après un choc M15 directionnel, le M5 doit fournir une confirmation alignée. Une barre M5 trop grande est refusée pour éviter de poursuivre un mouvement déjà consommé.

### break_retest_reaccel

Uniquement en régime M15 directionnel : cassure locale M5, retest causal du niveau, puis clôture de ré-accélération.

### failed_auction_reversal

Uniquement en régime M15 équilibré : sweep d'un extrême local M5, mèche significative et réintégration causale.

### directional_transition

Déclenché une seule fois à la clôture M15 qui bascule vers `directional_expansion`.
L'entrée se fait sur la M5 suivante, avec stop structurel fixe à 0,8 ATR M15,
target 1,8R et horizon 18 M5. Ce mécanisme reste SHADOW tant que la validation
prospective et le holdout sont insuffisants.

### asia_range_sweep_reversal

Range asiatique causal 02:00–10:00 Europe/Athens, puis première sweep/reclaim
qualifiante pendant Londres 10:00–13:00. Le stop reste derrière l'extrême du
sweep avec buffer ATR et l'entrée se fait sur la M5 suivante. Le mécanisme est
partagé entre backtest et runtime, mais son admission reste spécifique au couple
actif × mécanisme.

### directional_pullback_resumption

Actif en runtime SHADOW **uniquement pour GBPUSD**. En régime M15 directionnel :

1. deux M5 consécutives corrigent contre le régime ;
2. la M5 suivante repart dans le sens du régime et clôture au-delà de l'extrême
   de la seconde bougie de pullback ;
3. entrée sur la M5 suivante ;
4. stop derrière l'extrême du pullback avec buffer 0,10 ATR M5 ;
5. target 2R, horizon 12 M5.

La restriction GBPUSD est fondée sur le replay figé : les autres actifs n'ont
pas une évidence suffisante/positive pour autoriser la collecte paper de ce
mécanisme.

Aucun de ces mécanismes n'est ACTIVE pour l'exécution broker à ce stade.

## Backtest causal

Le signal est calculé à la clôture d'une bougie.

L'entrée est réalisée sur l'ouverture de la bougie M5 suivante.

Le modèle d'exécution :

- BUY : entrée Ask, sorties sur Bid ;
- SELL : entrée Bid, sorties sur Ask ;
- spread de recherche issu d'un modèle gelé/versionné ;
- slippage par défaut : 0.25 spread ;
- si stop et target sont tous les deux touchés dans la même bougie, le stop gagne ;
- un seul trade simultané par couple marché × mécanisme ;
- lot calculé avec tick size, tick value, min lot, lot step et marge MT4.

Les rejets d'exécution sont comptabilisés séparément des résultats de trading.

## Limite de coût historique

Les fichiers HST v401 locaux ont été inspectés : le champ spread existe dans le
format mais vaut zéro sur les historiques disponibles BTC/EUR/GBP/XAU/XAG.

La recherche utilise donc un spread proxy **gelé et versionné**, calibré sur la
médiane des spreads broker réellement observés, plus le slippage modèle. Le
runtime, lui, continue d'utiliser le spread live réel et le veto spread/stop.

Cette approche rend les admissions reproductibles sans prétendre reconstruire
le spread historique tick par tick.

## Replay causal

`RegimeReplay.push()` est le chemin incrémental.

`RegimeReplay.replay()` appelle ce même chemin pour l'historique. Un test d'équivalence protège contre une divergence batch/runtime.

## Strategy Admission

Une stratégie n'est jamais activée parce qu'elle gagne sur le train.

- preuve indépendante insuffisante -> `SHADOW` ;
- critères indépendants suffisamment observés mais défaillants -> `REJECTED` ;
- validation et holdout satisfaisants -> `ACTIVE`.

La matrice portefeuille ne renvoie un `qualified_strategy_id` que pour une stratégie ACTIVE.

## Capital

Configuration courante :

- capital de référence : 400 EUR ;
- risque de base : 1 % = 4 EUR ;
- plafond absolu : 2 % = 8 EUR ;
- perte journalière maximale : 3 % = 12 EUR ;
- spread maximal : 15 % du stop ;
- marge maximale : 25 % du capital.

Augmenter le risque ne constitue jamais un moyen de réparer un edge négatif.

## AUTO et CONFIRM

- `confirm` : proposition en attente d'approbation humaine ;
- `auto` : proposition autorisée automatiquement si tout le pipeline l'autorise.

Une proposition autorisée n'est pas encore un ordre broker. Le live reste verrouillé.

## Passage paper -> demo -> live

Le projet démarre en `paper + confirm`.

Avant le mode démo automatisé :

- au moins un couple doit être ACTIVE ;
- le scanner runtime doit reproduire le même événement causal que le backtest ;
- le ledger doit rapprocher proposition, ordre et fill ;
- les limites journalières et le kill switch doivent être testés.

Avant le live, ces preuves doivent être reproduites avec coûts et comportement broker observés.

## Active universe

The architecture is currently constrained to five markets:

- BTCUSD
- EURUSD
- GBPUSD
- XAUUSD
- XAGUSD

US500Cash, USA500IDXUSD, USATECHIDXUSD, Volatility and VOLIDXUSD are explicitly
outside the active project scope.

## Prochains incréments

Runtime infrastructure is considered sufficient for the current phase. The next
increments must improve trading evidence rather than add more plumbing:

- one new causal, execution-feasible hypothesis for EURUSD/GBPUSD;
- tighter but genuinely structural opportunity definitions for XAUUSD/XAGUSD;
- continued BTC prospective collection under unchanged risk/cost guards;
- historical/runtime equivalence tests for every new mechanism;
- SHADOW first, DEMO only after historical ACTIVE plus prospective
  SUPPORTS_DEMO.


## Portfolio Manager runtime

Le runtime découvre les ledgers paper de chaque couple marché × mécanisme. Une
stratégie ne devient `DEMO_ELIGIBLE` que si deux preuves indépendantes convergent :

1. admission historique `ACTIVE` issue de la matrice gelée ;
2. qualification prospective paper suffisante.

Sinon l'action reste `NO_TRADE` ou `PAPER_ONLY`.

## Macro Gate

Le calendrier USD combine une base vérifiée Fed/BLS/BEA et une synchronisation
BLS best-effort. En cas d'échec réseau, la base locale n'est jamais effacée.

Les événements HIGH appliquent une fenêtre de blackout avant/après la
publication. Ce gate intervient aussi dans la garde DEMO.

## DEMO bridge

`TradingDemoExecutionBridge.mq4` refuse une commande si :

- `AllowDemoExecution=false` ;
- le compte MT4 n'est pas DEMO ;
- le magic number ne correspond pas ;
- la proposition n'est pas `authorized` ;
- une position du bridge est déjà ouverte ;
- le lot ou la géométrie SL/TP est invalide.

Le backend ajoute ses propres gardes avant même de créer le fichier de commande.
Le bridge n'est pas une voie d'accès au live réel.


## Prospective evidence versioning

PR #13 fixed paper entry-bar causality. Evidence used by prospective admission is
versioned from `2026-09-20T12:53:56+03:00`.

PR #27 separates:

- post-cutover evidence used for qualification;
- legacy pre-cutover trades retained for audit.

No trade ledger is deleted or rewritten by this separation.

## Spécialisation par actif

L'architecture ne suppose pas qu'une même stratégie doit fonctionner sur tous
les marchés. L'infrastructure (données, régime, risk engine, backtest, SHADOW,
PAPER, bridge) est commune, mais l'unité d'admission est le couple
`symbol × mechanism`.

Conséquences :

- un mécanisme peut être PAPER-éligible sur BTCUSD et REJECTED sur EURUSD ;
- un mécanisme peut rester SHADOW sur un actif sans être lancé sur les autres ;
- les mécanismes spécifiques, comme `directional_pullback_resumption` GBPUSD,
  ne sont pas étendus à d'autres actifs sans preuve ;
- le Portfolio Manager sélectionne parmi les couples admis, pas parmi des
  stratégies globales appliquées uniformément ;
- aucun actif n'est forcé à trader : `RESEARCH ONLY` est un état normal lorsque
  l'évidence n'est pas suffisante.

Le dashboard expose désormais cette carte de spécialisation directement depuis
le registre d'admission courant.


## PAPER vs isolated DEMO collection

PAPER admission and broker DEMO collection share one source of truth.

- `paper_entry_allowed(admission)` decides whether a strategy may open a new
  PAPER trade;
- REJECTED is always false;
- ACTIVE is PAPER-eligible;
- SHADOW is PAPER-eligible only under the centralized evidence policy
  (positive weakest independent expectancy or the explicit under-sampled
  train+validation exception);
- `demo_collection_allowed(admission)` is restricted to SHADOW and requires
  `paper_entry_allowed(admission)=true`.

The special `paper_collection_candidate` field is evidence metadata for the
under-sampled exception. It is not, by itself, the transport policy.

When a collectable SHADOW PAPER trade is open and the runtime is in DEMO
collection mode, the Portfolio Manager may select `DEMO_COLLECTION`. The
broker adapter then mirrors exactly that PAPER trade's side, lot, stop and
target. LIVE remains a separate locked path.
