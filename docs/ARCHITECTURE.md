# Architecture

## Objectif

Construire une application de trading intraday M5/M15 testable, observable et indépendante du broker.

## Flux cible

1. **MT4 Market Data** — normalise bougies, quotes et spécifications broker.
2. **Market Selector** — élimine les instruments dont spread, lot minimum ou marge sont incompatibles avec 200 EUR.
3. **Regime Engine M15** — classe le marché avant toute recherche d'entrée.
4. **Strategy Engine M5** — applique uniquement les mécanismes admis pour le régime courant.
5. **Strategy Admission** — REJECTED, SHADOW ou ACTIVE selon validation et holdout.
6. **Capital Risk Engine** — calcule le sizing depuis le capital économique, jamais depuis le gros solde démo.
7. **Approval Gate** — mode AUTO ou CONFIRM.
8. **MT4 Execution Adapter** — future couche d'envoi et rapprochement broker.
9. **Ledger / Analytics** — décisions, rejets, fills, PnL, coûts et drawdown.
10. **React UI** — vision portefeuille, régimes, opportunités et contrôle humain.

## Regime Engine

Le moteur M15 utilise uniquement l'historique disponible au moment de la décision.

États initiaux :

- `warmup` : historique insuffisant ;
- `dead` : volatilité localement comprimée ;
- `balanced_auction` : aucun mouvement directionnel dominant ;
- `directional_expansion` : efficacité directionnelle et volatilité suffisantes ;
- `post_shock` : grande bougie d'information directionnelle relative à l'ATR antérieur.

Les seuils initiaux sont des définitions de recherche fixes, pas des paramètres optimisés pour maximiser le PnL.

## Replay causal

`RegimeReplay.push()` est le chemin incrémental utilisé barre par barre.

`RegimeReplay.replay()` appelle exactement ce même chemin pour l'historique. Un test d'équivalence garantit que le traitement batch et le traitement progressif produisent les mêmes snapshots.

## Strategy Admission

Une stratégie n'est jamais activée parce qu'elle gagne sur la période d'entraînement.

- données insuffisantes en validation/holdout -> `SHADOW` ;
- expectancy non positive, PF insuffisant ou drawdown excessif -> `REJECTED` ;
- critères satisfaits sur validation **et** holdout -> `ACTIVE`.

Ces garde-fous limitent le data mining ; ils ne garantissent pas la rentabilité future.

## Capital

Configuration initiale :

- capital de référence : 200 EUR ;
- risque de base : 1 % par trade ;
- plafond absolu : 2 % ;
- perte journalière maximale : 3 % ;
- spread maximal : 15 % de la distance au stop ;
- marge maximale : 25 % du capital.

Le sizing est arrondi vers le bas au pas de lot MT4. Si le lot minimum dépasse le budget de risque, le trade est rejeté.

## AUTO et CONFIRM

Deux modes de décision existent :

- `confirm` : une proposition reste en attente jusqu'à approbation humaine ;
- `auto` : une proposition est autorisée sans clic humain.

Une proposition « authorized » n'est pas encore un ordre broker. L'adaptateur MT4 d'exécution reste une couche séparée et le live est toujours verrouillé.

## Timeframes

- M15 : contexte, régime, volatilité et structure.
- M5 : déclenchement et exécution.
- Une position peut durer plusieurs bougies.

## Passage paper -> demo -> live

Le code démarre en `paper` et `confirm`.

Le mode `demo` utilisera le même pipeline que le futur live, tout en conservant un capital économique de 200 EUR.

Le mode `live` restera verrouillé tant que le backtest walk-forward, le replay incrémental, le sizing, le rapprochement des fills, les limites de perte et le kill switch ne sont pas validés.

## Prochains incréments

- lire automatiquement toutes les spécifications exportées par MT4 ;
- construire le backtester de trades net de spread/slippage ;
- coder les mécanismes conditionnels au régime en SHADOW ;
- ajouter le ledger persistant et le dashboard portefeuille ;
- connecter l'exécution MT4 en démo.
