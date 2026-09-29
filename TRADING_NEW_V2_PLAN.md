# Trading-New V2 — Master Rebuild Plan

> Statut : plan directeur de reconstruction.
> Orchestration : ChatGPT garde la maîtrise fonctionnelle, économique, risque, revue PR et déploiement.
> Exécution de code : Codex Luna reçoit des prompts limités à une étape à la fois.
> Référence permanente : lire `context.md` puis `PROJECT_CONTEXT.md` avant toute action.

## 0. Point de départ

Au 2026-09-29, `main` est au commit `334bdc92bece9ed34dc1d1c9b994258c072ae5d6` après #176.
PR ouverte : #177 `Separate research collection from DEMO authority`.

Le diagnostic directeur est le suivant :
- Trading-New mesure beaucoup mais transforme encore trop peu les mouvements en trades utiles ;
- les signaux restent trop binaires et tardifs ;
- `target_r` et `max_holding_bars` structurent encore trop fortement les sorties ;
- le trailing adaptatif existe mais n'est pas encore le moteur principal de gestion ;
- l'exécutabilité est trop souvent contrôlée après détection au lieu de participer au timing d'entrée ;
- le dashboard doit devenir le reflet opérationnel direct du moteur V2 et non un empilement de cartes research.

Ce plan remplace toute fuite en avant par nouvelles briques research tant que le coeur Trading Decision V2 n'est pas construit.

## Principes non négociables

- Broker MT4 DEMO, `live_trading_enabled=false`.
- Sizing basé sur l'equity réelle MT4 DEMO.
- Hard cap : 5 lots par trade.
- `max_spread_to_stop=0.15`.
- Pas de cap artificiel du nombre de trades en DEMO.
- Ne jamais augmenter risque/lots/caps pour créer des opportunités.
- Ne jamais toucher aux positions Freezebee ou externes.
- Une hypothèse économique à la fois.
- Tests RED/GREEN avant correction significative.
- Pas de merge/pull/restart/deploy avec position Trading-New ouverte.
- Séquence de déploiement : drain ON -> preuve BOOK_FLAT -> merge/pull -> restart ciblé -> postflight -> drain OFF.
- Toute recherche descriptive reste sans autorité broker.

## Architecture cible

Pipeline cible :

`Market Data -> Market State -> Setup -> Armed -> Triggered -> Executable Entry Zone -> Risk/Sizing -> Position Manager -> Adaptive Exit -> Evidence/Learning`

La recherche devient une couche latérale alimentée par ces mêmes événements, pas un deuxième pipeline concurrent.

## Étape 1 — Opportunity Engine V2 : état de setup

### Objectif
Remplacer la logique binaire "pattern complet ou NO_SIGNAL" par une machine d'état commune :
- `NONE`
- `SETUP`
- `ARMED`
- `TRIGGERED`
- `INVALIDATED`
- `EXPIRED`

### Travail
- introduire des types de domaine communs ;
- encapsuler les mécanismes existants derrière une interface de setup ;
- ne supprimer aucun mécanisme encore ;
- produire une transition causale et explicable ;
- conserver les anciens scanners comme référence de comparaison pendant la migration.

### Critères d'acceptation
- aucune autorité broker ajoutée ;
- aucune modification de risque ;
- transitions testées causalement ;
- V1 et V2 peuvent être comparés sur les mêmes barres ;
- dashboard : carte "Opportunity State" par actif avec setup, direction, âge, état et raison.

## Étape 2 — Market State V2 multi-horizon

### Objectif
Construire un état de marché continu commun M1/M5/M15.

### Features
- direction et persistance ;
- volatilité/ATR ;
- efficacité du chemin ;
- accélération/décélération ;
- extension/exhaustion ;
- session et landmarks ;
- proximité macro ;
- spread/liquidité observée ;
- M1 tick-pressure existante, sans la présenter comme Level-2 OFI.

### Critères d'acceptation
- aucune feature future ;
- toute feature timestampée causalement ;
- aucune règle BUY/SELL opaque issue d'un score ML ;
- dashboard : Market State compact et lisible par actif.

## Étape 3 — Executable Entry Zone

### Objectif
Faire de l'exécutabilité une partie du timing d'entrée.

### Travail
Pour chaque setup armé, calculer une zone de prix où :
- le stop structurel reste valide ;
- le spread/stop respecte 15 % ;
- le lot minimum est compatible avec le budget risque ;
- le potentiel restant reste économiquement intéressant ;
- l'entrée n'arrive pas après consommation excessive du mouvement.

Si le setup est valide mais le prix mauvais, attendre la zone au lieu de relâcher les gardes.

### Critères d'acceptation
- aucune relaxation du spread guard ;
- sizing toujours basé equity MT4 ;
- max 5 lots ;
- comparaison "signal détecté / zone atteinte / trade déclenché / opportunité perdue".
- dashboard : zone d'entrée, prix courant, distance, raison d'attente.

## Étape 4 — Trigger Engine M1/M5

### Objectif
Déclencher plus tôt sans anticiper aveuglément.

### Travail
- utiliser les setups armés de l'étape 1 ;
- déclencheurs M1/M5 causaux ;
- confirmation de reprise, rejet, re-accélération ou exhaustion selon famille ;
- interdire les triggers qui contredisent l'invalidation structurelle ;
- mesurer le mouvement consommé au trigger.

### Critères d'acceptation
- pas de threshold optimisé sur 1-2 exemples ;
- comparaison V1 vs V2 : délai, prix, MFE, MAE, résultat R ;
- dashboard : "why now" et "why not yet".

## Étape 5 — Position Manager V2 : sorties adaptatives

### Objectif
Retirer `target_r` et `max_holding_bars` du rôle de logique principale.

### Machine de gestion
- initial risk ;
- no-follow-through ;
- protect ;
- trail ;
- extend ;
- regime-loss exit ;
- safety timeout uniquement en dernier recours.

### Contraintes
- stop initial jamais élargi ;
- aucun ajout de risque monétaire ;
- target dynamique possible seulement après protection ou preuve de continuation ;
- gestion broker fidèle au PAPER.

### Critères d'acceptation
- replay comparatif V1 vs V2 ;
- suivi MFE capturé / MFE laissé ;
- incident XAU #153 couvert par régressions ;
- dashboard : SL initial, SL courant, target/extension, état de gestion, raison de prochaine action.

## Étape 6 — Spécialisation par actif

### Objectif
Arrêter de traiter les cinq marchés comme des copies.

### Direction de travail
- BTCUSD : momentum, transition, retest, post-shock si confirmé ;
- XAUUSD : session/landmarks, sweep, macro, continuation/exhaustion ;
- EURUSD/GBPUSD : session, breakout/retest, pullback, expansion ;
- XAGUSD : uniquement familles économiquement viables sous spread/stop.

Ce sont des hypothèses de structure, pas des admissions automatiques.

### Critères d'acceptation
- matrice explicite actif x famille ;
- aucune stratégie activée sans validation ;
- familles inutiles retirées du runtime seulement après preuve ;
- dashboard : familles actives/research par actif.

## Étape 7 — Learning : Champion / Challengers

### Objectif
Transformer le learning en boucle d'amélioration contrôlée.

### Contrat
- un champion par actif/famille ;
- quelques challengers maximum ;
- un seul changement économique par challenger ;
- walk-forward + holdout + coûts réels + prospective DEMO ;
- aucune promotion automatique vers le broker ;
- toute promotion reste revue humaine.

### Critères d'acceptation
- provenance complète des versions ;
- champion/challenger comparables ;
- pas d'optimisation libre de dizaines de thresholds ;
- dashboard : champion, challengers, échantillon, expectancy, PF, DD, statut.

## Étape 8 — Portfolio Opportunity Allocator

### Objectif
Autoriser plusieurs opportunités simultanées sans faux cap journalier.

### Travail
- allocation à partir de l'equity MT4 ;
- prise en compte de la somme des risques ouverts ;
- corrélation / concentration directionnelle ;
- priorité à l'exécutabilité et à l'edge prouvé ;
- ne pas empêcher un bon trade simplement parce qu'un autre actif a déjà tradé aujourd'hui.

### Critères d'acceptation
- aucun cap de nombre de trades ;
- cap 5 lots par trade conservé ;
- contraintes de risque portefeuille explicites et testées ;
- dashboard : exposition totale, risque ouvert, risque par actif et positions simultanées.

## Étape 9 — Simplification / suppression de l'usine à gaz

### Objectif
Réduire les pipelines parallèles une fois V2 prouvé.

### Travail
- cartographier doublons scanner/research/sequence/precursor/trailing ;
- garder une source de vérité pour Market State ;
- garder une source de vérité pour Trading Decision ;
- garder une source de vérité pour Position Management ;
- recherche branchée sur les événements produits par ces couches.

### Critères d'acceptation
- suppression uniquement après tests d'équivalence ou remplacement prouvé ;
- baisse du nombre de chemins critiques ;
- docs architecture mises à jour ;
- dashboard débarrassé des cartes research obsolètes ou reléguées dans un onglet Research.

## Étape 10 — Validation économique et déploiement V2

### Objectif
Décider sur preuves si V2 améliore réellement le système.

### Comparaison obligatoire
- opportunités détectées ;
- setups armés ;
- triggers ;
- trades exécutables ;
- trades DEMO ;
- expectancy R ;
- PF ;
- drawdown R ;
- win rate ;
- MFE/MAE ;
- capture du MFE ;
- coût d'exécution ;
- slippage ;
- PnL par actif/famille ;
- opportunités manquées et raison exacte.

### Déploiement
1. tests ciblés ;
2. full backend ;
3. Ruff ;
4. frontend build ;
5. MetaEditor si MT4 modifié ;
6. CI verte ;
7. drain ON ;
8. BOOK_FLAT prouvé ;
9. merge/pull ;
10. restart uniquement des composants modifiés ;
11. postflight ;
12. drain OFF ;
13. observation DEMO.

## Dashboard — chantier transversal obligatoire

Le dashboard évolue à chaque étape et doit permettre de comprendre la situation en un coup d'oeil.

### Vue Trading
- equity MT4 ;
- PnL jour / 7 jours ;
- risque ouvert ;
- positions Trading-New ;
- actifs READY / CLOSED / DEGRADED ;
- Market State ;
- setup/armed/triggered ;
- zone d'entrée exécutable ;
- ordre/position et management adaptatif ;
- événements macro.

### Vue Opportunities
Pour chaque actif :
- état du setup ;
- sens ;
- mécanisme ;
- qualité de l'exécution ;
- prix attendu / zone ;
- stop structurel ;
- spread/stop ;
- lots calculés ;
- "why now / why waiting / why invalidated".

### Vue Position Management
- ticket ;
- entrée ;
- SL initial/courant ;
- objectif courant ;
- MFE/MAE ;
- état : INITIAL / PROTECT / TRAIL / EXTEND / EXIT ;
- raison de la dernière modification.

### Vue Research
Tout ce qui ne détient aucune autorité trading y reste clairement séparé.

## Règle d'exécution Codex Luna

Codex Luna ne reçoit jamais "fais les 10 étapes".
Il reçoit une étape bornée, avec :
- fichiers à lire ;
- contrat fonctionnel ;
- invariants risque ;
- tests à écrire ;
- critères d'arrêt ;
- livrable PR ;
- interdiction de merge/deploy.

ChatGPT relit le diff, les tests, les impacts économiques et décide du prompt suivant.

## Suivi de chantier obligatoire à chaque chat

Chaque réponse de pilotage doit contenir :
- HEAD main ;
- branche/PR en cours ;
- CI/tests ;
- étape V2 actuelle ;
- dashboard : état de synchronisation avec cette étape ;
- runtime / drain / flatness si disponibles ;
- positions externes observées mais jamais touchées ;
- changements économiques réalisés ;
- changements purement research ;
- blocages ;
- prochaine action ;
- prompt Codex Luna courant ou suivant.

## Ordre d'exécution

Ordre strict par défaut :
1. Opportunity Engine V2
2. Market State V2
3. Executable Entry Zone
4. Trigger Engine
5. Position Manager V2
6. Spécialisation actifs
7. Champion/Challengers
8. Portfolio Allocator
9. Simplification
10. Validation/déploiement

Toute déviation doit être motivée par un incident P0 ou une dépendance technique réelle.
