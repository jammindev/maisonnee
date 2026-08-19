# Module — projects

> Audit : 2026-04-28. Rôle : suivre un projet du foyer de bout en bout (rénovation, achat, vacances…) avec tâches, notes, dépenses et budget.

## État synthétique

- **Backend** : Présent
- **Frontend** : Complet dans `ui/src/features/projects/`
- **Locales (en/fr/de/es)** : ok
- **Tests** : oui — 4 fichiers (`test_api_projects.py`, `test_import_supabase_projects.py`, `test_import_supabase_project_links.py`, `test_import_supabase_user_pinned_projects.py`)
- **Migrations** : 7 total (0007 = suppression de `ProjectAIThread`/`ProjectAIMessage`)

## Modèles & API

- Modèles principaux : `Project` (status, type, dates, budget, cover_interaction) ; `ProjectGroup` ; `ProjectZone` (M2M zones) ; `ProjectDocument` ; `UserPinnedProject`
- Endpoints exposés : `/api/projects/projects/` (+ `pin/`, `unpin/`, `register-purchase/`, `assistant-step/`, filtres `?zone=`, `?status=`), `/project-groups/`, `/project-zones/`
- Permissions : `IsAuthenticated, IsHouseholdMember` (pas de custom)

## Création assistée — l'entretien (parcours 32)

Doc produit : `docs/parcours/PARCOURS_32_RACONTER_UN_CHANTIER.md`. Fiche concept :
`docs/fiches/ENTRETIEN_DIRIGE.md`. Régression : `apps/projects/tests/test_assistant.py`.

`POST /api/projects/projects/assistant-step/` (`projects.assistant.next_step`) mène
un entretien : le modèle pose **une** question à la fois, et finit par proposer un
plan (projet + tâches + notes). Ce que tout changement doit préserver :

- **L'entretien n'a pas d'état côté serveur.** L'historique voyage dans le corps de
  chaque requête. Ne jamais introduire une table d'entretiens : elle serait
  majoritairement peuplée d'abandons, donc une purge à maintenir, pour un geste qui
  dure trois minutes. `AgentConversation` persiste parce qu'on relit une
  conversation ; un entretien ne se relit pas.
- **Le plafond de questions est du code, jamais une consigne de prompt.**
  `MAX_QUESTIONS = 6`, compté sur la longueur de l'historique. Au-delà, on n'envoie
  pas au modèle une consigne de conclure : on lui envoie un **autre** prompt système,
  et `_parse` refuse une question. Une intention de prompt est respectée la plupart
  du temps — et le jour où elle ne l'est pas, c'est l'utilisateur qui découvre la
  boucle. Régression : `TestTheCapIsAGuaranteeNotAnInstruction`.
- **Cet endpoint n'écrit rien, et c'est structurel.** Il ne connaît aucun modèle en
  écriture ; la création est un endpoint séparé (lot 2). « Rien n'est écrit avant
  relecture » ne doit jamais dépendre d'un `if` — même arbitrage que
  `games/riddles.py`, où la génération est une action de liste parce qu'elle n'a
  aucune chasse à modifier.
- **Le modèle ne remplit jamais un montant.** Le prompt lui interdit de mettre un
  chiffre dans la question et lui demande de donner l'ordre de grandeur dans `hint` ;
  le champ de réponse reste vide côté écran. Un budget prévisionnel deviné sert
  ensuite de référence à la barre du chantier pendant des mois, et personne ne se
  souvient qu'il a été inventé — « des valeurs de départ, jamais des vérités ».
- **`input` type la réponse** (`text` / `amount` / `date` / `zones` / `choice`), et un
  type inconnu **lève** au lieu de retomber sur du texte libre : un montant qui
  repasse par une chaîne est un nombre qu'il faut relire, et c'est le chemin qui a
  déjà produit un faux montant en production (règle `DecimalInput` du `CLAUDE.md`).
- **Une valeur douteuse est retirée, jamais devinée.** Un `type` hors
  `Project.Type` et une priorité hors 1-5 sont supprimés du plan — écrire « autre »
  à la place de « rénovation » serait indistinguable d'un choix de l'utilisateur.
- **Le contexte est pauvre à dessein** : les zones du foyer (pour que le plan les
  désigne par **nom**) et la liste des types. Pas de projets existants, pas de RAG —
  l'entretien compose une page blanche et sa matière vient de qui répond.
- **Capacité `project_assistant`** (registre `app_settings`), distincte d'`assistant`
  bien qu'elle lise la même clé : « l'assistant ne peut pas répondre » et « les
  projets se créent au formulaire » ne disent pas la même chose. Le **prédicat**, lui,
  est importé d'`agent.capabilities` et non recopié. Sans clé, il n'y a **pas de
  version dégradée** : le formulaire de création est le repli, et il existe déjà.
- **Throttle dédié `project_assistant` (60/h)** : un entretien vaut jusqu'à sept
  appels au fournisseur. Le plancher global compte des requêtes, pas des euros.
- **Le rayon d'action d'une consigne injectée dans `goal` est borné, et c'est ce
  qui rend le texte libre acceptable.** Le contexte envoyé au modèle ne contient
  que les noms de zones du foyer — que l'appelant voit déjà — et la sortie n'est
  jamais écrite : au pire, un membre se fabrique à lui-même un plan absurde,
  qu'il lit avant de le créer. Cette phrase cesse d'être vraie le jour où le
  contexte s'enrichit (documents du lot 5, budgets du lot 4) ou où un plan se
  crée sans relecture : il faudra alors reposer la question.

## Notes / décisions produit

- **Onglets adaptatifs (parcours 20)** : le détail projet ne montre que les onglets
  qui ont du contenu. `overview` toujours visible ; les autres apparaissent quand
  leur compteur > 0 (ou s'ils sont l'onglet actif). Les compteurs viennent du champ
  `tab_counts` du `ProjectSerializer` (**detail seulement**, `null` en liste, via
  `services.project_tab_counts`). Les onglets vides restent atteignables par un menu
  « + » du `TabShell` (`moreTabs`) pour pouvoir y ajouter le premier item.
- **Onglet « Photos » (parcours 20)** : `<EntityPhotosTab entityType="project"
  objectId={id} />` — photos regroupées par phase avant/pendant/après + comparateur.
  Voir `docs/MODULES/photos.md`.
- V1 livrée dans le Parcours 04 : boutons de création rapide (tâche, note, dépense, activité) dans chaque onglet du détail projet, bandeau projet dans `InteractionCreateForm`, bloc de synthèse en tête (tâches ouvertes/retard, budget), `project_title` exposé, `?tab=` lu depuis l'URL — *source : `docs/JOURNAL_PRODUIT.md` lignes 81-96*.
- **Onglet « Assistant » (2026-07)** : le détail projet expose un onglet chat branché sur l'agent RAG générique. Il s'appuie sur `<EntityAssistant entityType="project" objectId={id} />` (`ui/src/features/agent/`), lui-même adossé à une conversation `agent.AgentConversation` **ancrée** sur le projet (`context_entity_type='project'`, `context_object_id=<id>`). Au démarrage, tout le contexte du projet (détails + documents + dépenses + tâches + zones liés, via `spec.related`) est pré-injecté : l'IA connaît déjà le projet sans avoir à chercher. Voir `docs/MODULES/agent.md`.
- `ProjectAIThread` / `ProjectAIMessage` (thread IA dédié, jamais consommé) **supprimés le 2026-07** (migration `0007`) : l'onglet Assistant passe par l'agent générique, ce thread parallèle était mort.
- Un projet a une seule zone "couverture" (`cover_interaction`) mais peut être lié à plusieurs zones via `ProjectZone` (M2M).
- Contraintes DB strictes : priorité 1-5, budgets >= 0, `due_date >= start_date`.
