# Architecture

## Objectif

Construire une application de trading intraday M5/M15 testable, observable et indépendante du broker.

## Flux cible

1. **MT4 Market Data** — normalise bougies, quotes et spécifications broker.
2. **Market Selector** — élimine les instruments dont le spread, le lot minimum ou la marge rendent le trade économiquement incohérent.
3. **Feature Engine** — calcule uniquement des variables disponibles au moment de la décision.
4. **Regime Engine** — classe le marché avant de choisir le mécanisme de trading.
5. **Strategy Engine** — produit une décision explicable et versionnée.
6. **Capital Risk Engine** — calcule le sizing depuis un capital économique indépendant du solde broker.
7. **Execution Adapter** — traduit un ordre canonique vers MT4.
8. **Ledger** — enregistre décisions, rejets, ordres, fills, positions et PnL.
9. **Analytics** — mesure expectancy, profit factor, drawdown, coûts et capture d'opportunités.
10. **React UI** — visualise état, opportunités, risque, exécution et résultats.

## Capital

Le solde du compte démo n'est jamais utilisé comme budget de risque.

Configuration initiale :

- capital de référence : 200 EUR ;
- risque de base : 1 % par trade ;
- plafond absolu : 2 % ;
- perte journalière maximale : 3 % ;
- spread maximal : 15 % de la distance au stop ;
- marge maximale : 25 % du capital de référence.

Le sizing est arrondi vers le bas au pas de lot MT4. Si le lot minimum dépasse le budget de risque, le trade est rejeté.

## Timeframes

- M15 : contexte, régime, volatilité et structure.
- M5 : déclenchement et exécution.
- Une stratégie peut conserver une position plusieurs bougies ; les timeframes décrivent la décision, pas une obligation de scalping.

## Passage paper -> demo -> live

Le code démarre en `paper`.

Le mode `demo` utilisera le même pipeline de décision et l'adaptateur MT4, mais les métriques économiques resteront calculées sur le capital de référence de 200 EUR.

Le mode `live` reste verrouillé tant que :

- les backtests walk-forward net de coûts ne sont pas satisfaisants ;
- le replay incrémental est équivalent au backtest batch ;
- le sizing MT4 et le rapprochement des fills sont validés ;
- les limites de perte et le kill switch sont testés.

## Prochains incréments

- lire automatiquement le snapshot de symboles exporté par MT4 ;
- construire le backtester causal M5/M15 ;
- ajouter le moteur de régimes ;
- tester des stratégies conditionnelles, sans grid search massif ;
- ajouter le ledger persistant et le dashboard de portefeuille ;
- brancher ensuite l'exécution MT4 en démo.
