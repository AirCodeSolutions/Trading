# Architecture

## Objectif

Construire une application de trading intraday M5/M15 testable, observable et indépendante du broker.

## Flux cible

1. **Market Data** — normalise les bougies et événements de marché.
2. **Feature Engine** — calcule uniquement des variables disponibles au moment de la décision.
3. **Strategy Engine** — produit une décision explicable et versionnée.
4. **Risk Engine** — décide si le risque est acceptable et calcule l'exposition.
5. **Execution Adapter** — traduit un ordre canonique vers le broker choisi.
6. **Ledger** — enregistre décisions, rejets, ordres, fills, positions et PnL.
7. **Analytics** — mesure expectancy, profit factor, drawdown, coûts et capture d'opportunités.
8. **React UI** — visualise état, opportunités, risque, exécution et résultats.

## Contraintes initiales

- Timeframes admis : M5 et M15.
- Le mode par défaut est `paper`.
- Le trading live est verrouillé par défaut.
- Les stratégies ne doivent pas connaître l'API du broker.
- Les décisions et mesures de performance doivent intégrer les coûts de transaction.
- Un même moteur doit pouvoir être rejoué historiquement et exécuté progressivement sans modifier sa logique métier.

## Prochain incrément

- connecter une source de données historique + temps réel ;
- persister bougies et ledger ;
- définir le moteur de stratégie ;
- développer le backtester causal M5/M15 ;
- brancher l'adaptateur broker ;
- afficher positions, PnL, drawdown et décisions dans le dashboard.
