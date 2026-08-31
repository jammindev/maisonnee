# Journal produit

Ce document est le point d'entrée vivant pour suivre :

- l'état actuel du produit
- ce qui a été livré récemment
- les décisions prises
- les prochaines priorités
- les idées futures à ne pas perdre

Il sert de mémoire opérationnelle entre plusieurs sessions de travail.

## Comment l'utiliser

Après chaque session produit importante :

1. mettre à jour le statut ci-dessous si nécessaire
2. ajouter une entrée datée dans `docs/journal/`
3. enregistrer les idées non traitées comme issue GitHub avec le label `idea`

## État actuel

Dernière mise à jour : 2026-07-08

### Parcours métier

- Parcours 01 — Capturer un événement du foyer et le retrouver facilement : **socle V1 livré**
- Parcours 02 — Traiter un document entrant et le relier au bon contexte : **V1 manuelle en pré-livraison**
- Parcours 03 — Transformer un besoin en action suivie : **V1 livrée**
- Parcours 04 — Suivre un projet de bout en bout : **V1 livrée**
- Parcours 05 — Naviguer par zone ou équipement pour comprendre et agir : **V1 livrée**
- Parcours 06 — Recevoir les bons rappels au bon moment pour ne rien rater : **cadrage initial — à démarrer**
- Parcours 07 — Poser une question en langage naturel sur son foyer : **V1 livrée** (lot 6 #109 reste à finir, non bloquant) ; lot 9 canal Telegram : **livré le 2026-07-08** (#221–#224 ; recette avec un vrai bot @BotFather à faire ; V2 différée #225)
- Parcours 08 — Suivre les dépenses : **lots V1 fermés** (#122, #123, #124)
- Parcours 09 — Voir et piloter la maison connectée : **cadré le 2026-07-03 — à démarrer** (issues #183, #185–#188 ; V2 différée #189)
- Parcours 10 — Analyser la consommation électrique : **V1 livrée le 2026-07-05** (PRs #204–#207 ; recette avec le fichier Enedis réel à faire ; V2 différée #202)
- Parcours 11 — Tracker des valeurs dans le temps : **V1 livrée le 2026-07-05** (PRs #209, #213, #212 ; recette manuelle du chat agent à faire ; V2 différée #197)
- Parcours 25 — Les relevés bancaires comme source de vérité des dépenses : **cadré le 2026-07-25 — à démarrer** (9 lots ; doc produit, fiche `IMPORT_ET_RAPPROCHEMENT.md`, backlog ; lot 9 PDF/photo différé)

Le parcours 25 retourne l'hypothèse des parcours 08 et 21 : la dépense cesse d'être une déclaration (« ce que j'ai pensé à saisir ») pour devenir un fait constaté (« ce qui est sorti du compte »). C'est ce qui rend un budget fiable plutôt qu'indicatif. Décision structurante : **il n'y a pas de table `Allocation`** — une `Interaction(type='expense')` *est* une ventilation de ligne bancaire, ce qui laisse `amount` en colonne scalaire et épargne la réécriture des 9 agrégations existantes.

Les parcours 01 à 05 couvrent le flux de vie d'un foyer : capturer, traiter, agir, piloter et naviguer. Le parcours 06 ouvre la couche proactive : le produit signale ce qui mérite l'attention. Le parcours 07 ouvre la couche IA : la mémoire du foyer est désormais interrogeable en langage naturel.

## Ce qui est considéré comme livré sur le parcours 01

- entrée rapide depuis le dashboard via un CTA unique
- sélecteur de type avant création
- formulaire unique avec variantes utiles par type
- possibilité de lier des documents existants directement depuis le formulaire activité
- possibilité d'ajouter un document simple depuis le formulaire activité puis de le lier immédiatement
- vocabulaire produit plus naturel
- tags et zones mieux outillés
- recherche visible dans l'historique
- retour cohérent après création avec mise en évidence de l'élément créé
- traduction frontend et serveur réalignée pour les principaux libellés du parcours

Références :

- [docs/parcours/PARCOURS_01_CAPTURER_ET_RETROUVER_UN_EVENEMENT.md](../docs/parcours/PARCOURS_01_CAPTURER_ET_RETROUVER_UN_EVENEMENT.md)
- [docs/parcours/PARCOURS_01_BACKLOG_TECHNIQUE.md](../docs/parcours/PARCOURS_01_BACKLOG_TECHNIQUE.md)
- couche IA consolidée dans [docs/parcours/PARCOURS_07_AGENT_CONVERSATIONNEL.md](../docs/parcours/PARCOURS_07_AGENT_CONVERSATIONNEL.md) (section "Évolutions ultérieures")

## Décisions produit actives

- `Interaction` reste le concept technique central
- l'interface privilégie `Activité`, `Historique` et `Ajouter un événement`
- le dashboard est le point d'entrée rapide
- la page interactions est la source de vérité du parcours
- la future couche IA devra produire une interaction candidate structurée, pas remplir un formulaire visuellement
- **(2026-07-31)** le produit ne sera pas vendu en SaaS : il est publié en open
  source auto-hébergeable sous le nom **Maisonnée**, licence **AGPL-3.0**, modèle
  Home Assistant. Ce qu'on cherche à apprendre est la **rétention** de foyers
  réels, pas l'audience — voir [parcours 28](./parcours/PARCOURS_28_OUVRIR_MAISONNEE.md)

## Ce qui est considéré comme livré sur le parcours 03

- page tâches reconstruite en liste mobile-first avec sections par statut (En retard, En cours, À faire, Backlog, Fait)
- chips de filtre rapides par statut
- carte tâche enrichie : zone, date relative, badge retard, indicateurs événement/document source
- création de tâche standalone depuis la page tâches
- création de tâche depuis un événement de l'historique avec lien stocké dans `metadata`
- création de tâche depuis un document avec lien `InteractionDocument`
- édition d'une tâche après création via dialog prérempli
- tâches en retard détectées côté frontend et signalées en tête de liste
- traductions Django et frontend réalignées (fr, en, de, es)
- 2 tests backend couvrant les nouveaux points d'entrée

Références :

- [docs/parcours/PARCOURS_03_TRANSFORMER_UN_BESOIN_EN_ACTION_SUIVIE.md](../docs/parcours/PARCOURS_03_TRANSFORMER_UN_BESOIN_EN_ACTION_SUIVIE.md)
- [docs/parcours/PARCOURS_03_BACKLOG_TECHNIQUE.md](../docs/parcours/PARCOURS_03_BACKLOG_TECHNIQUE.md)

## Ce qui est considéré comme livré sur le parcours 04

- boutons de création rapide (tâche, note, dépense, activité) dans chaque onglet du détail projet avec contexte pré-lié
- `AppInteractionNewView` enrichi avec `project_id` : zones pré-remplies, redirection vers le projet avec `?tab=<onglet>`
- `InteractionCreateForm` : bandeau projet en mode contexte, sélecteur projet en mode général
- bloc de synthèse en tête du détail projet : tâches ouvertes, tâches en retard, budget
- `project_title` exposé dans `InteractionSerializer`
- nom du projet visible et cliquable dans `TaskCard` et `InteractionList`
- tab initial lu depuis l'URL (`?tab=`) dans `ProjectDetail`
- 5 tests backend couvrant les nouveaux flux

Références :

- [docs/parcours/PARCOURS_04_SUIVRE_UN_PROJET_DE_BOUT_EN_BOUT.md](../docs/parcours/PARCOURS_04_SUIVRE_UN_PROJET_DE_BOUT_EN_BOUT.md)
- [docs/parcours/PARCOURS_04_BACKLOG_TECHNIQUE.md](../docs/parcours/PARCOURS_04_BACKLOG_TECHNIQUE.md)
- [docs/journal/2026-03-10_parcours-04_v1_livree.md](../docs/journal/2026-03-10_parcours-04_v1_livree.md)

## Ce qui est considéré comme livré sur le parcours 05

- filtre `?zone=<id>` ajouté sur `/api/projects/projects/`
- `ZoneDetailNode` : sections contextuelles (sous-zones, équipements, tâches ouvertes, activité récente, projets actifs)
- boutons `Ajouter une activité` et `Ajouter une tâche` dans le détail zone avec zone pré-liée
- zone parente cliquable dans le header du détail zone
- `EquipmentDetail` : zone cliquable, badge garantie tricoloré, date prochaine maintenance
- bouton `Enregistrer une intervention` depuis la fiche équipement
- support `equipment_id` dans `AppInteractionNewView` : props, zone automatique, redirection
- bandeau contexte équipement dans `InteractionCreateForm`
- création du lien `EquipmentInteraction` post-création
- 5 tests backend couvrant les nouveaux flux

Références :

- [docs/parcours/PARCOURS_05_NAVIGUER_PAR_ZONE_OU_EQUIPEMENT.md](../docs/parcours/PARCOURS_05_NAVIGUER_PAR_ZONE_OU_EQUIPEMENT.md)
- [docs/parcours/PARCOURS_05_BACKLOG_TECHNIQUE.md](../docs/parcours/PARCOURS_05_BACKLOG_TECHNIQUE.md)
- [docs/journal/2026-03-10_parcours-05_v1_livree.md](../docs/journal/2026-03-10_parcours-05_v1_livree.md)

## Ce qui est considéré comme livré sur le parcours 07

V1 livrée le 2026-05-02 (lots 0a → 3) :

- pipeline OCR à l'upload (HEIC + resize + Vision Haiku pour images, `pypdf` pour PDFs texte, fallback Vision multi-page sur PDFs scannés)
- backfill OCR via management command + bouton "Re-extraire" sur la fiche document
- recherche full-text Postgres scopée household, registry par app (10 entités V1 indexées)
- service agent `apps/agent/service.ask()` orchestrant retrieval → prompt → LLM → parsing citations
- abstraction `LLMClient` Protocol + `AnthropicClient` concret, factory keyed sur `LLM_PROVIDER`
- citations honnêtes : intersection regex des marqueurs avec les hits du retrieval, pas d'invention
- endpoint `POST /api/agent/ask/` (504 timeout, 503 erreur LLM, 400 sans household)
- surface React `/app/agent/` : input, bulles, citations cliquables (chips numérotés inline + panneau Sources), mention de confidentialité one-shot, i18n en/fr/de/es
- table `AIUsageLog` qui logue chaque appel agent (skeleton lot 6, KPIs/UI à finir dans #109)
- 62 tests backend (agent + ai_usage) + 5 tests E2E Playwright (mock backend)

Validé en prod sur le foyer "Les Petits Bonheur" (188 docs) : citations multi-entités cohérentes (documents + interactions + assurance + projet), latence 2-4s, IDK propre sur les questions hors-domaine.

Lot 4 (mémoire conversationnelle multi-tour) basculé V2 — décision : valider l'usage one-shot d'abord. Lot 6 (#109, observabilité KPIs + page admin) reste ouvert mais non bloquant pour l'utilisateur.

Références :

- [docs/parcours/PARCOURS_07_AGENT_CONVERSATIONNEL.md](../docs/parcours/PARCOURS_07_AGENT_CONVERSATIONNEL.md)
- [docs/parcours/PARCOURS_07_BACKLOG_TECHNIQUE.md](../docs/parcours/PARCOURS_07_BACKLOG_TECHNIQUE.md)
- [docs/fiches/RAG.md](../docs/fiches/RAG.md)
- [docs/journal/2026-05-02_parcours-07_v1_livree.md](../docs/journal/2026-05-02_parcours-07_v1_livree.md)

## Prochain focus recommandé

Deux pistes complémentaires :

1. **Recette manuelle parcours 07** — utiliser l'agent pendant 1-2 semaines sur le foyer réel pour repérer ce qui craque (questions qui ratent un match évident → déclencheur de #113, format de citation qui dérape, latence inacceptable, etc.). Ouvrir des issues ciblées plutôt que sur-investir à l'aveugle.
2. **Parcours 06 — Alertes et rappels proactifs** : prochain parcours métier à démarrer si on veut élargir au lieu d'approfondir.

Le **lot 6 (#109)** — observabilité IA — peut être livré en parallèle quand le besoin de métriques se fait sentir (taux d'IDK, latence p95, etc.).

Références :

- [docs/parcours/PARCOURS_06_ALERTES_ET_RAPPELS_PROACTIFS.md](../docs/parcours/PARCOURS_06_ALERTES_ET_RAPPELS_PROACTIFS.md)
- [docs/parcours/PARCOURS_06_BACKLOG_TECHNIQUE.md](../docs/parcours/PARCOURS_06_BACKLOG_TECHNIQUE.md)

Axes suivants :

- couche IA : capture assistée depuis WhatsApp / email (parcours 01 — RFC documentée dans la fiche parcours 07, section "Évolutions ultérieures")
- parcours 02 V1 complète : traitement automatisé des documents entrants (s'appuie sur l'OCR du parcours 07)
- amélioration de la navigation et des performances frontend (chunks, pagination)

## Journal des sessions

- [docs/journal/2026-03-08_parcours-01_v1_et_projection_ia.md](../docs/journal/2026-03-08_parcours-01_v1_et_projection_ia.md)
- [docs/journal/2026-03-09_parcours-02_cadrage_initial.md](../docs/journal/2026-03-09_parcours-02_cadrage_initial.md)
- [docs/journal/2026-03-09_parcours-02_prelivraison_v1_manuelle.md](../docs/journal/2026-03-09_parcours-02_prelivraison_v1_manuelle.md)
- [docs/journal/2026-03-09_formulaire-activite_documents.md](../docs/journal/2026-03-09_formulaire-activite_documents.md)
- [docs/journal/2026-03-09_parcours-03_v1_livree.md](../docs/journal/2026-03-09_parcours-03_v1_livree.md)
- [docs/journal/2026-03-10_parcours-04_cadrage_initial.md](../docs/journal/2026-03-10_parcours-04_cadrage_initial.md)
- [docs/journal/2026-03-10_parcours-04_v1_livree.md](../docs/journal/2026-03-10_parcours-04_v1_livree.md)
- [docs/journal/2026-05-02_parcours-07_v1_livree.md](../docs/journal/2026-05-02_parcours-07_v1_livree.md)

## Backlog d'idées futures

- [GitHub issues — label `idea`](https://github.com/jammindev/maisonnee/issues?q=is%3Aopen+is%3Aissue+label%3Aidea)