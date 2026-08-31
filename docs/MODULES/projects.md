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
- Endpoints exposés : `/api/projects/projects/` (+ `pin/`, `unpin/`, `register-purchase/`, `assistant-step/`, `assistant-create/`, filtres `?zone=`, `?status=`), `/project-groups/`, `/project-zones/`
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

### L'écriture du plan (lot 2)

`POST /api/projects/projects/assistant-create/` →
`projects.services.create_project_from_plan`. Régression :
`apps/projects/tests/test_assistant_create.py`.

- **Tout, ou rien.** Une seule `transaction.atomic()` couvre le projet, les tâches
  **et** les notes. Un chantier créé avec quatre tâches sur six est un demi-succès
  qui ressemble exactement à un succès, et personne ne saurait dire lesquelles
  manquent. Une ligne fautive lève une `ValidationError` **préfixée de son
  numéro** (`_numbered`, patron de `banking.views.set_allocations`) : « une ou
  plusieurs zones n'appartiennent pas au foyer » sur un plan de huit tâches
  n'aide personne.
- **Aucun objet n'est créé à la main.** Le projet passe par `ProjectSerializer`,
  chaque tâche par `tasks.services.create_task`, chaque note par
  `interactions.services.create_note_interaction`. Le test compare le résultat des
  deux chemins plutôt que les deux codes — un service dupliqué ne se voit pas en
  revue, les deux diffs se ressemblent.
- **Le projet naît en `draft`, comme celui du formulaire.** L'assistant ne
  s'octroie pas un statut plus avancé sous prétexte que l'utilisateur vient de
  relire. Et il ne porte **aucune marque** de provenance : ce qui a été validé est
  de l'utilisateur (arbitrage du cadrage, à rouvrir le jour où un plan se crée
  sans relecture).
- **⚠️ Les zones sont résolues au tour d'entretien, jamais à l'écriture**
  (`assistant.resolve_plan_zones`). C'est l'invariant le plus facile à casser en
  « simplifiant » : si la résolution nom → id avait lieu ici, une pièce mal nommée
  par le modèle retomberait sur celles du projet **après** validation, sans que
  personne puisse le voir ni le corriger — le silence exact que le registre des
  writables a supprimé ailleurs. Conséquences : `assistant-create` n'accepte que
  des **ids** (accepter des noms rouvrirait un second chemin de désignation, donc
  deux définitions de « la chambre »), la désignation passe par
  `zones.services.resolve_zone` **exclusivement**, ce qui est nommé prime sur
  l'héritage, un nom introuvable ou ambigu est **rendu à l'écran**
  (`unresolved_zone_names`) et l'item hérite du projet — jamais rien, sinon
  `create_task` le rangerait dans la zone racine.
- **Une erreur de contenu se dit en 400, jamais en 500.** Deux dates dans le
  mauvais ordre sont refusées par `PlanProjectSerializer.validate` et pas par le
  `CheckConstraint` `projects_dates_consistent`. Et `_numbered` rattrape aussi
  `ObjectDoesNotExist`, parce que `TaskSerializer.create` fait un
  `Zone.objects.get(...)` par zone : une zone supprimée entre l'entretien et la
  création donnerait sinon un 500. Le même trou existe sur `POST /api/tasks/tasks/`
  — défaut préexistant, suivi par l'issue #666 ; la borne posée ici est locale et
  se retire quand `TaskSerializer` validera lui-même.
- **La création ne demande aucune clé** (pas de `capabilities.require`). Un plan
  déjà obtenu doit rester créable si la clé tombe entre-temps : refuser ferait
  perdre une relecture que l'utilisateur vient de faire, pour une raison qui ne le
  concerne plus. Elle n'est pas non plus soumise au cap `project_assistant` —
  écrire ne coûte pas d'euros.
- **Le plan reçu se valide comme une saisie utilisateur**, pas comme une sortie de
  modèle : entre la génération et cet appel, l'humain a réécrit des titres et
  décoché des lignes. Les plafonds de `ProjectPlanSerializer` sont ceux du moteur
  (`MAX_TASKS` / `MAX_NOTES`) pour que le refus soit le même des deux côtés.

### L'écran (lot 3)

`ui/src/features/projects/assistant/` — `ProjectAssistantDialog` (SheetDialog, deux
phases), `ProjectAssistantInterview`, `AnswerField`, `ProjectAssistantReview`, et
`plan.ts` pour la construction du payload. Régressions :
`plan.test.ts` et `e2e/project-assistant.spec.ts`.

- **Le bouton est absent sans la capacité, jamais grisé** (`useCapability('project_assistant')`).
  Un bouton grisé promet et dément dans le même geste — et il n'y a rien à
  promettre : le formulaire de création est juste à côté et **est** le repli.
- **La bascule vers la relecture est décidée par le serveur** (`state === 'ready'`),
  jamais par un compte de questions tenu dans le composant. Deux compteurs pour la
  même chose finissent par se contredire, et c'est celui du serveur qui décide.
- **`AnswerField` ne pose aucune taille de police.** `tailwind-merge` fait gagner
  le dernier de la même famille : un `text-sm` ajouté pour tasser un champ
  effacerait le `text-base` du design-system et ferait zoomer iOS à l'ouverture du
  dialogue. La décision vit dans `fieldBase`, à un seul endroit.
- **Une question d'argent se répond dans un `DecimalInput`, et le champ arrive
  vide.** La fourchette de prix est rendue *à côté* (`question.hint`) — jamais
  dedans. Vérifié en vrai navigateur, parce qu'un champ vide contre un champ
  pré-rempli est une propriété du rendu et pas de la réponse HTTP.
- **Un tour raté ne perd rien** : l'historique n'est commité qu'au succès de
  l'appel. La version naïve (écrire l'historique avant) affichait la question
  **deux fois** quand le modèle répondait de travers — une fois dans l'historique,
  une fois comme question courante. Et « J'ai assez dit » emporte la réponse en
  cours si elle a été tapée : sans ça, quelqu'un qui saisit son budget puis conclut
  voit son montant disparaître.
- **La mutation de création déclare trois racines** :
  `invalidate('projects', 'tasks', 'interactions')`. Un `invalidate('projects')`
  seul ne suffirait pas — le graphe de `lib/invalidate.ts` dit « le projet *lit*
  les tâches et les interactions », donc écrire `projects` périme le dashboard mais
  **pas** la liste des tâches ni le journal. Or cette écriture y crée vraiment des
  lignes.
- **Le brouillon ne partage aucune référence avec la réponse en cache** (`toDraft`
  copie) : sinon éditer la relecture muterait la réponse de React Query, et
  rouvrir le dialogue afficherait les corrections comme si elles venaient du
  modèle.
- **`unresolved_zone_names` est de l'affichage et ne repart jamais** dans la
  requête. C'est le pendant écran de la règle du lot 2 : ce que le serveur n'a pas
  su rattacher se **dit**, une fois, en tête de relecture.
- **Le test e2e stube l'entretien et pas la création.** « Le fournisseur répond-il »
  n'a rien à faire dans un test ; « le plan relu arrive-t-il en base, et seulement
  ce qui était coché » ne se prouve qu'en traversant le vrai backend.

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
