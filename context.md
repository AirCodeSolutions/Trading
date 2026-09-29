# Trading-New — context.md

> Point d'entrée obligatoire pour tout agent travaillant sur ce dépôt.
> Lire ensuite `PROJECT_CONTEXT.md` et `TRADING_NEW_V2_PLAN.md`.
> En cas de conflit, les règles de sécurité/risk les plus conservatrices prévalent et le conflit doit être signalé.

## Mission

Reconstruire Trading-New pour obtenir davantage de belles opportunités réellement exécutables et rentables, avec meilleur PnL risk-adjusted et drawdown contrôlé, sans relâcher artificiellement le risque.

Le chantier actif est **Trading-New V2**, défini dans `TRADING_NEW_V2_PLAN.md`.

## Mode de travail

- ChatGPT garde la maîtrise du chantier : architecture, priorité économique, validation, revue des PR, décisions de merge et déploiement.
- Codex Luna exécute uniquement le prompt borné de l'étape en cours.
- Codex Luna ne doit jamais décider seul d'un merge, d'un déploiement, d'une promotion de stratégie ou d'une modification de risque.
- Une étape à la fois.
- Une hypothèse économique à la fois.
- Pas d'audits infinis ni de rustines sans impact économique démontrable.
- Le dashboard doit suivre chaque évolution fonctionnelle du moteur.

## Périmètre

Repo : `AirCodeSolutions/Trading`
Checkout canonique : `/home/laetitia/trading/Trading`
Runtime : `/home/laetitia/trading/Trading-runtime`
Backend : port 8020
Frontend : port 5180
Broker : MT4 DEMO
Magic Trading-New : `560619`
LIVE : interdit, `live_trading_enabled=false`

Actifs :
- BTCUSD
- EURUSD
- GBPUSD
- XAUUSD
- XAGUSD

Actifs définitivement hors périmètre :
- US500Cash
- USA500IDXUSD
- USATECHIDXUSD
- Volatility
- VOLIDXUSD

## Invariants risque et broker

- sizing basé sur l'equity MT4 DEMO réelle ;
- hard cap 5 lots par trade ;
- `max_spread_to_stop=0.15` ;
- aucun cap artificiel du nombre de trades par jour en DEMO ;
- aucune augmentation du risque/lots/caps sans preuve ;
- macro guards conservés ;
- ne jamais toucher aux positions Freezebee ou externes ;
- un `broker_observed_positions > 0` ne signifie pas que Trading-New n'est pas flat.

Flatness Trading-New :
- `bridge_open_positions == 0`
- aucun PAPER ouvert
- `pending_command == null`
- `pending_close_command == null`

## Déploiement

Aucun merge/pull/restart/deploy avec position Trading-New ouverte.

Séquence obligatoire :
1. réconcilier main / PR / CI ;
2. vérifier health, preflight, DEMO et flatness ;
3. drain ON ;
4. nouvelle preuve BOOK_FLAT ;
5. merge/pull ;
6. restart uniquement des composants modifiés ;
7. postflight ;
8. drain OFF ;
9. vérifier armed / bridge / pending.

Ne jamais redémarrer le shadow worker sans nécessité.

## Architecture cible V2

`Market Data -> Market State -> Setup -> Armed -> Triggered -> Executable Entry Zone -> Risk/Sizing -> Position Manager -> Adaptive Exit -> Evidence/Learning`

Trois sources de vérité fonctionnelles à terme :
1. Market State
2. Trading Decision
3. Position Management

La recherche écoute ces événements mais ne possède aucune autorité broker.

## Les 10 étapes

1. Opportunity Engine V2 — setup state machine
2. Market State V2 multi-horizon
3. Executable Entry Zone
4. Trigger Engine M1/M5
5. Position Manager V2 / sorties adaptatives
6. Spécialisation par actif
7. Learning Champion / Challengers
8. Portfolio Opportunity Allocator
9. Simplification des pipelines
10. Validation économique et déploiement V2

Le détail, les critères d'acceptation et le contrat dashboard sont dans `TRADING_NEW_V2_PLAN.md`.

## Dashboard obligatoire

Le dashboard n'est pas un chantier secondaire. Chaque étape backend doit définir son rendu frontend.

Le dashboard doit distinguer clairement :
- Trading opérationnel ;
- Opportunities ;
- Position Management ;
- Research sans autorité.

Il doit exposer progressivement :
- equity et PnL ;
- état marché ;
- setup / armed / triggered ;
- zone d'entrée ;
- why now / why waiting / why invalidated ;
- stop initial/courant ;
- target/extension ;
- MFE/MAE ;
- risque ouvert / lots ;
- macro ;
- champion/challengers.

## Validation développement

Avant PR significative :
- test RED si bug ;
- tests ciblés ;
- full backend ;
- Ruff ;
- frontend production build si frontend touché ;
- MetaEditor si MT4 touché ;
- `git diff --check` ;
- CI GitHub verte.

Aucun test ne doit être rendu vert en modifiant artificiellement le comportement production.

## Politique de recherche

Populations à garder séparées :
1. admitted PAPER/DEMO ;
2. executable unqualified probes ;
3. blocked probes ;
4. waiting/market opportunities.

Ne jamais mélanger ces populations pour fabriquer de l'edge.
Les métriques M1/tick-pressure ne sont pas du Level-2 OFI.
Toute donnée utilisée pour décider doit être causale et disponible avant la décision.

## Sorties V2

Le système actuel utilise encore largement `target_r` et `max_holding_bars`.
Le V2 doit les retirer du rôle de logique de sortie principale.

Objectif :
- stop initial structurel ;
- jamais élargi ;
- no-follow-through ;
- protection ;
- trailing structurel ;
- extension si continuation ;
- sortie si régime/thèse invalidée ;
- safety timeout seulement comme garde finale.

## Suivi de chantier obligatoire dans chaque chat

Toujours donner :
1. HEAD main ;
2. PR ouvertes / créées / fusionnées ;
3. CI/tests ;
4. étape V2 actuelle ;
5. état du dashboard pour cette étape ;
6. runtime ;
7. drain ;
8. flatness Trading-New ;
9. positions externes vues mais non touchées ;
10. évolution économique réalisée ;
11. recherche uniquement descriptive ;
12. blocages ;
13. prochaine étape ;
14. prompt Codex Luna.

Si le runtime n'est pas accessible, le dire explicitement au lieu d'inventer son état.

## État initial de la reconstruction

Au démarrage du plan, le 2026-09-29 :
- `main` observé : `334bdc92bece9ed34dc1d1c9b994258c072ae5d6` après #176 ;
- #177 est ouverte et sépare collecte research et autorité DEMO ;
- #177 ne constitue pas à elle seule une amélioration de PnL ;
- priorité V2 : Étape 1, Opportunity Engine V2 ;
- aucun guard risque ne doit être relâché pour accélérer cette reconstruction.

Tout état HEAD/runtime/chiffre de performance est périssable et doit être revalidé avant utilisation.
