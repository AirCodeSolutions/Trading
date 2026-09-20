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
8. **Capital Risk Engine** — sizing depuis 200 EUR, jamais depuis le gros solde démo.
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

Trois mécanismes de recherche sont actuellement implémentés :

### post_shock_continuation

Après un choc M15 directionnel, le M5 doit fournir une confirmation alignée. Une barre M5 trop grande est refusée pour éviter de poursuivre un mouvement déjà consommé.

### break_retest_reaccel

Uniquement en régime M15 directionnel : cassure locale M5, retest causal du niveau, puis clôture de ré-accélération.

### failed_auction_reversal

Uniquement en régime M15 équilibré : sweep d'un extrême local M5, mèche significative et réintégration causale.

Aucun de ces mécanismes n'est actif en production à ce stade.

## Backtest causal

Le signal est calculé à la clôture d'une bougie.

L'entrée est réalisée sur l'ouverture de la bougie M5 suivante.

Le modèle d'exécution :

- BUY : entrée Ask, sorties sur Bid ;
- SELL : entrée Bid, sorties sur Ask ;
- spread issu du snapshot broker ;
- slippage par défaut : 0.25 spread ;
- si stop et target sont tous les deux touchés dans la même bougie, le stop gagne ;
- un seul trade simultané par couple marché × mécanisme ;
- lot calculé avec tick size, tick value, min lot, lot step et marge MT4.

Les rejets d'exécution sont comptabilisés séparément des résultats de trading.

## Limite de coût historique

Les historiques actuels ne contiennent pas encore une série complète de spread tick-par-tick.

Le backtest applique donc le spread du snapshot broker sur l'historique, plus un slippage modèle. Il s'agit d'une approximation conservatrice, mais pas d'une reconstruction parfaite des coûts historiques.

La collecte d'un historique de spread fait partie des améliorations suivantes.

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

Configuration initiale :

- capital de référence : 200 EUR ;
- risque de base : 1 % ;
- plafond absolu : 2 % ;
- perte journalière maximale : 3 % ;
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

## Prochains incréments

- analyser les sous-régimes du candidat BTC break/retest récent ;
- collecter le spread dans le temps ;
- ajouter le scanner runtime SHADOW ;
- persister le ledger de recherche et les opportunités ;
- enrichir le dashboard portefeuille ;
- connecter ensuite l'exécution MT4 en démo.


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
