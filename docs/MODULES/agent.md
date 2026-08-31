# Module — agent

> Rôle : assistant conversationnel du foyer (RAG + function calling). Répond en langage naturel sur les données du foyer, avec citations vérifiables. Accessible en pleine page (`/app/agent/`) **ou** ancré sur une entité précise (onglet « Assistant » d'un projet, etc.).

## État synthétique

- **Backend** : `apps/agent/` — orchestrateur (`service.py`), tools function-calling (`tools.py`), retrieval full-text (`retrieval.py`), registry des entités searchables (`searchables.py`), prompts (`prompts.py`), contexte ancré (`context.py`), persistance conversations (`models.py`).
- **Frontend** : `ui/src/features/agent/` — `AgentPage` (pleine page, sidebar de conversations), `EntityAssistant` (chat ancré sans sidebar), `ContextPanel` + `AddContextDialog` (panneau « Ce que je sais » : contexte visible + épinglage), `ChatBubble` (markdown + citations), `PrivacyNotice`.
- **Locales (en/fr/de/es)** : namespace `agent` (dont `agent.entity.*` pour le chat ancré, `agent.context.*` pour le panneau de contexte, `agent.memory.*` pour la mémoire utilisateur).
- **Mémoire utilisateur** : `apps/agent/memory.py` (service), modèle `AgentMemory`, tool `manage_memory`, page `ui/src/features/agent/MemoryPage.tsx`, toggle `AgentMemorySection` dans les réglages.
- **Tests** : `apps/agent/tests/` — `test_service.py`, `test_tools.py`, `test_context.py`, `test_conversations_api.py`, `test_retrieval.py`, `test_prompts.py`, `test_registry.py`, `test_query_expansion.py`, `test_retention.py`, `test_llm.py`, `test_models.py`, `test_views.py`, `test_memory.py`, `test_digest_*.py`.
- **Proactif (l'agent parle en premier)** : `apps/agent/digest/` — résumé
  quotidien agrégeant les signaux du foyer, poussé sur Telegram via le socle
  pings. Sous-package autonome, doc dédiée : [digest.md](./digest.md) (parcours 19).

## Boucle agent (function calling)

`service.ask(question, household, *, user, history, context_entity)` : boucle
tool-use bornée par `AGENT_MAX_TOOL_ITERATIONS`. Trois tools read-only enregistrés
dans `tools.REGISTRY` :

- `search_household(query)` — expansion de requête + retrieval scellé au foyer ;
- `get_entity(entity_type, id)` — contenu complet d'un item ;
- `get_related(entity_type, id)` — tout ce qui est lié à un item (via `spec.related`).

Les citations `<cite id="type:id"/>` sont intersectées avec le pool de hits
réellement retournés (citations honnêtes, cf. `_resolve_citations`).

Un **4ᵉ tool, d'écriture**, complète les trois de lecture :

- `create_entity(entity_type, fields)` — crée un item du foyer (aujourd'hui :
  `task`, `note`). Un seul tool générique, adossé au registry `writables` (cf. plus bas).
  L'item créé est renvoyé comme Hit citable + remonté dans
  `metadata.created_entities` pour l'Undo côté client. Livré au **lot 8** (voir
  `docs/parcours/PARCOURS_07_LOT8_ACTIONS_ECRITURE.md`).

Une app peut aussi **enregistrer son propre tool de lecture** via
`agent.tools.register(AgentTool(...))` depuis son `apps.py::ready()`, sans toucher
`apps/agent/` — utile pour une source sans modèle DB (donc hors `searchables`).
Exemple : `get_weather` (module météo, parcours 17 Lot 5) rend prévisions + alertes.

## Registry d'écriture `writables` — rendre une entité créable

Miroir de `searchables`, pour l'écriture. Chaque app déclare depuis
`apps.py::ready()` :

```python
from agent.writables import WritableSpec, register as register_writable

register_writable(WritableSpec(
    entity_type='task',
    create=_create_task_from_agent,   # (household, user, fields, *, anchor) -> instance
    label_attr='subject',
    url_template='/app/tasks/{id}',
))
```

Règles :
- `create` **réutilise le service métier** de l'app (jamais l'ORM brut) — ex.
  `tasks.services.create_task` qui passe par `TaskSerializer` (validation, scope
  foyer, fallback zone racine).
- `create` reçoit l'`anchor` de la conversation ancrée `(entity_type, object_id)`
  et l'utilise pour pré-remplir un lien (ancre `project` → tâche liée au projet).
- Rendre une entité créable = **registrer un `WritableSpec`** + étendre la
  description du tool `create_entity`. Zéro touche à `apps/agent/tools.py` sur le
  fond.

### ⚠️ L'ancre est un défaut, jamais la seule source d'un lien

Un `create` qui ne lit un rattachement (zone, projet…) que dans l'`anchor` est
**aveugle dans l'assistant global** — et c'est le seul chemin qui reste depuis que
les onglets « Assistant » ont quitté les vues de détail. Une note demandée « dans
la salle de bain » n'atterrissait donc dans **aucune** zone : `fields['zone']`
n'était pas lu, et le tool ne documentait aucun champ de zone, donc le modèle
n'avait rien à remplir. Deux moitiés de la même cause — un `create` qui lit
`fields` sans que le schéma l'annonce ne sert à rien, et l'inverse non plus.
Corollaires (#579) :

- **La désignation par nom est la règle, pas une commodité.** Un utilisateur dit
  « la chambre », jamais un UUID — même contrat que `stock_item`, `tracker`,
  `meter`. Pour les zones, tout passe par `zones.services.resolve_zone` /
  `resolve_zone_ids` : un seul endroit décide ce que « la chambre » veut dire,
  **borne au foyer** (c'est là que se refuse l'écriture dans la pièce d'un autre
  foyer), tolère la casse, les accents et la tournure entière (« dans la salle de
  bain » — le nom le plus précis qui tienne dans la phrase gagne).
- **Ce qui est nommé explicitement prime sur l'ancre**, qui ne comble que le vide.
- **L'ambigu se dit, il ne se devine pas** : deux chambres qui correspondent lèvent
  un `ValueError` nommant les candidates, que le tool relaie au modèle. Ranger au
  hasard en confirmant que c'est fait est pire qu'une question — même règle que
  `banking.rules` (« des valeurs de départ, jamais des vérités »).
- **Un rattachement introuvable n'écrit rien.** Créer l'item sans sa pièce
  produirait exactement le silence d'origine, cette fois avec une confirmation.

Régression : `agent/tests/test_create_entity_zones.py`.

**Garde-fous d'écriture** : prompt strict (créer seulement sur demande explicite),
anti-doublon par tour (`service.ask`), et **Undo** côté client (toast « Annuler »
qui supprime l'item). Une écriture est un effet de bord réversible, pas une
proposition à valider.

**Undo backend (`delete`)** : `WritableSpec` porte un champ optionnel
`delete(household, user, object_id)` — miroir serveur des `UNDO_HANDLERS` du
front, appelé par les canaux non-web (bouton « Annuler » de Telegram) via le
point d'entrée unique `writables.delete_created(...)`. Il réutilise le service
métier de la DELETE API (`task` → archive, `note` → delete) et lève `LookupError`
si l'item est déjà parti (double-tap idempotent). Voir
[telegram.md](./telegram.md).

## Conversation, tous canaux — `conversations.py`

`agent.conversations` factorise les deux gestes autour de `ask()` quand une
conversation persistée est en jeu : `ask_inputs(conversation)` (historique borné
+ ancre) et `persist_turns(conversation, question, user, result)` (écriture
atomique des deux tours, auto-titre, `last_message_at`). Les vues DRF **et** le
canal Telegram s'en servent — même sémantique partout, pas de re-dérivation.

## Registry searchable — ajouter une entité

Chaque app déclare ses entités depuis `apps.py::ready()` via
`agent.searchables.register(SearchableSpec(...))` (entity_type, model,
search_fields, label_attr, url_template, `related` optionnel). L'agent ne connaît
pas la liste — ajouter un module = ~5 lignes, zéro touche à `apps/agent/`.

### Confidentialité — le foyer dit à qui, le lecteur dit à quoi

La restriction n'est **pas** déclarée sur le `SearchableSpec` — elle l'a été, et
c'était le mauvais endroit : lier la confidentialité d'un modèle au fait qu'il soit
*cherchable* laissait sans domicile les modèles privatisables non searchables
(`briefings.Briefing`), et ne pourra jamais voir une confidentialité **héritée**,
qui ne porte aucun champ. Elle vit donc dans `core.visibility.REGISTRY`, alimenté
depuis l'`apps.py` de chaque app propriétaire — même modèle que `agent.searchables`
lui-même.

- **Le point d'application est unique** : `core.visibility.narrow_for` pour les
  chemins qui tiennent un queryset (lexical, sémantique, `resolve_entity`,
  `list_entities`), `retrieval.filter_visible_instances` pour ceux qui tiennent
  déjà des objets (`get_related`, contexte ancré — groupé par type, donc une
  requête par type présent, jamais une par item). Les deux lisent le **même**
  registre : pas de seconde règle qui pourrait dériver. Et c'est le même
  `narrow_for` que les viewsets REST appellent, donc l'assistant et la liste ne
  peuvent pas se contredire.
- **`viewer` omis est fermé, pas ouvert.** `core.visibility.visible_to_creator`
  ne renvoie alors que le public. Un appelant qui oublie le lecteur montre moins,
  jamais plus — un manque se remarque, une fuite non.
- **Une ligne non lisible est « introuvable », jamais « refusée ».** Répondre
  « il existe un document privé que je ne peux pas te montrer » est déjà une
  divulgation ; une ancre non lisible est donc traitée exactement comme une ancre
  orpheline, et la conversation continue sans contexte.
- **Le filtre porte sur `created_by`, jamais sur le rôle** : un owner de foyer
  n'est pas un lecteur privilégié du privé des autres.

**Pourquoi ce mécanisme plutôt qu'un filtre au point d'appel.** La couche de
retrieval ne connaissait que le **foyer** ; le privé d'un document n'était appliqué
que dans `documents/views.py`. Trois portes le contournaient — la palette du haut,
`search_household`, `get_entity` — plus une quatrième que personne n'aurait pensé à
énumérer : une facture privée attachée à un projet partagé entrait dans le contexte
ancré de quiconque ouvrait ce projet. C'est « un écart ne se dit jamais deux fois
avec deux voix » appliqué à la visibilité, avec une asymétrie propre à la sécurité :
**des deux définitions, c'est toujours la plus permissive qui gagne, et en silence.**
Régression : `agent/tests/test_private_visibility.py`, dont le test de forme
`TestTheTwoDoorsAgree` compare l'ensemble trouvable par l'assistant à celui que la
liste affiche, plutôt que d'énumérer des portes — la prochaine ne serait pas couverte.

> ✅ **Corrigé (parcours 33, lot 1).** `Task.is_private` et `Interaction.is_private`
> n'étaient appliqués nulle part côté retrieval : la tâche privée d'un membre était
> absente de sa propre liste et citable par l'assistant de tous les autres. Les deux
> modèles sont désormais déclarés au registre, donc bornés sur les sept portes à la
> fois. Seule exception, écrite comme une décision : une `Interaction(type="expense")`
> n'est jamais cachée — sept agrégations la lisent, et son secret portera sur le
> contenu (masquage, lot 4) et non sur l'existence.

### Gating par modules du foyer (parcours 15)

Les trois specs (`SearchableSpec`, `ListableSpec`, `WritableSpec`) portent un champ
déclaratif `module: str | None` (clé de `households.modules.OPTIONAL_MODULES`,
`None` = socle jamais filtré). Quand le foyer a désactivé un module
(`Household.disabled_modules`), `retrieval.search`/`search_multi` sautent ses specs
et les tools (`resolve_entity`, `list_entities`, `create_entity`, `update_entity`)
refusent ses entity_types avec un message recoverable. Helpers dans
`apps/agent/modules.py` ; tests dans `apps/agent/tests/test_module_gating.py`.
Déclarer une entité d'un module optionnel = ajouter `module='<clé>'` au spec.

## Conversation ancrée sur une entité (2026-07)

Une `AgentConversation` peut porter une ancre optionnelle
`(context_entity_type, context_object_id)` — mêmes strings que l'adressage des
tools. Quand elle est présente, chaque `ask` **pré-injecte** le contexte de
l'entité (contenu complet + items liés, via `agent.context.build_entity_context`)
en tête de conversation et seed ces hits dans le pool de citations ; le system
prompt reçoit `ANCHORED_ADDENDUM` (réponds/cite sans chercher). Le contexte est
ré-injecté à chaque tour (reste frais), borné par les budgets `RELATED_*`.

### Réutiliser ailleurs (zones, équipements…) — mode d'emploi

1. **Prérequis** : l'entité doit être enregistrée dans `agent.searchables` (elle
   l'est déjà pour project/zone/equipment/…). Un `related` sur le spec enrichit le
   contexte injecté, mais n'est pas obligatoire.
2. **Frontend** : poser le composant générique dans la vue de l'entité —
   `<EntityAssistant entityType="zone" objectId={zone.id} />`. Rien d'autre.
3. **Sous le capot** : `EntityAssistant` appelle
   `GET /api/agent/conversations/for_context/?entity_type=…&object_id=…` qui
   **get-or-create** l'unique conversation `(household, user, entité)`, puis
   réutilise `POST conversations/{id}/messages/` — la view détecte l'ancre et
   passe `context_entity` à `service.ask`.

Aucune modification de `apps/agent/` n'est nécessaire pour brancher une nouvelle
entité.

### Contexte visible + épinglage (2026-07)

`EntityAssistant` affiche au-dessus du chat un panneau **« Ce que je sais »**
(`ContextPanel`) : la liste, en chips, de tout ce que l'agent a en contexte —
l'ancre, ses items liés, et les entités **épinglées** par l'utilisateur. Le but :
rendre le contexte transparent et laisser l'utilisateur y ajouter un projet, une
interaction, un équipement… sans quitter la conversation.

- **Source de vérité unique** : `context.describe_conversation_context(conversation,
  household)` renvoie une liste de `ContextItem` `(entity_type, object_id, label,
  url, origin, available)` en **réutilisant `build_entity_context`** — donc un chip
  n'apparaît que si le modèle reçoit effectivement l'item. `origin` ∈
  `anchor | related | pinned` ; seuls les `pinned` sont retirables. Exposé en
  lecture via `ConversationDetailSerializer.injected_context`.
- **Épingles persistées** : champ `AgentConversation.pinned_contexts` (JSON, liste
  de `{entity_type, object_id}`, plafond `MAX_PINNED_CONTEXTS = 10`). Mêmes strings
  que l'ancre — pas de table dédiée (petit set de pointeurs, jamais requêté seul).
  Helpers dans `conversations.py` : `pin_context` / `unpin_context` (idempotents,
  tolérants) + `pinned_entities`.
- **Injection** : `service.ask(..., pinned_entities=[...])` pré-injecte **chaque**
  épingle exactement comme l'ancre (contexte complet + items liés, hits citables,
  paire de messages synthétique). `anchored` est vrai dès qu'il y a une ancre *ou*
  une épingle résoluble ; une épingle orpheline est silencieusement ignorée (le
  chip reste visible en `available=false` pour être retiré).
- **Picker** : `GET conversations/search_context/?q=` réutilise `retrieval.search`
  (même ranking, même gating modules que `search_household`) → `AddContextDialog`
  liste les candidats, grise ceux déjà présents. `pin_context` / `unpin_context`
  (POST) renvoient la conversation avec son `injected_context` rafraîchi ; le front
  fait un toast + undo (re-pin) sur retrait.

## Mémoire utilisateur (2026-07)

L'agent retient des **faits durables sur l'utilisateur** (préférences, habitudes,
contexte perso) au fil des conversations — distinct des données du foyer, qui
vivent dans leurs propres modèles et **priment** toujours en cas de conflit.

- **Modèle `AgentMemory`** (`HouseholdScopedModel`, champ `content` ≤ 500 car.),
  scopé `(household, created_by)` : privé par utilisateur, jamais partagé entre
  membres. Comme les conversations, **pas** dans `searchables` — les mémoires
  sont injectées telles quelles dans le system prompt, jamais retrouvées/citées.
- **Service `apps/agent/memory.py`** = source de vérité des écritures (comme
  `tasks/services.py`) : `save`/`update`/`forget`/`clear`, `user_memories`,
  `resolve_memory`, cap `MEMORY_LIMIT=50` (les plus anciennes sont élaguées
  silencieusement). Le tool ET le viewset REST passent par lui.
- **Tool `manage_memory(action, content, memory_id)`** (`save`/`update`/`forget`).
  Chaque écriture remonte dans `ToolResult.memories` → `metadata.memory_events`
  (`{action, id, content, previous?}`), pour l'undo front + l'indication 📌.
- **Injection + capture** (`service.ask_stream` + `prompts.build_system_prompt`) :
  - `agent_memory_enabled=True` → mode `auto` : mémoires injectées (avec leur
    `memory_id`) + capture spontanée autorisée.
  - flag `False` → mode `manual` : le tool reste décrit (pour un « retiens
    que… » explicite) mais **rien n'est injecté ni capté automatiquement**.
  - pas d'`user` (bare `ask`, tests) → la mémoire n'est pas mentionnée du tout.
- **Toggle** : champ `User.agent_memory_enabled` (défaut `True`), exposé par
  `UserSerializer` et patchable via `PATCH /accounts/users/me/`.
- **Frontend** : `MemoryPage` (`/app/agent/memory`) liste/édite/supprime (undo) +
  « tout effacer » (confirm) ; `AgentMemorySection` (réglages) = toggle + lien ;
  `useAgentMemoryEvents` (toast undo) + `MemoryNotice` (ligne 📌 persistante dans
  la bulle, rejouée depuis `metadata.memory_events`).

## Recherche web (tool serveur Anthropic, 2026-07)

L'agent peut consulter le **web public** via le tool **serveur** Anthropic
`web_search` (`web_search_20260209`) — pas un `AgentTool` du registry : Anthropic
exécute la recherche côté serveur et renvoie les résultats (avec URLs sources)
dans le même round-trip, sans handler client.

- **Activation** : `AGENT_WEB_SEARCH_ENABLED` (défaut **False**). Off par défaut
  car (a) ça appelle le web (coût + contenu externe) et (b) le *dynamic filtering*
  des résultats exige l'agent sur **Sonnet 4.6+** (`LLM_TEXT_MODEL`). `AGENT_WEB_SEARCH_MAX_USES`
  borne le nombre de recherches par question (0 = pas de plafond).
- **Injection** : `AnthropicClient._run_create_kwargs` ajoute le schéma serveur à
  la liste des tools **uniquement** quand des tools custom sont aussi offerts —
  jamais sur la passe finale sans tool (réponse forcée). Le service passe
  `web_search=_web_search_enabled()` à `run`/`run_stream`. Le registry provider-neutre
  (`tools.schemas()`) reste inchangé ; le détail Anthropic vit dans `llm.py`.
- **Boucle** : les blocs `server_tool_use` / `web_search_tool_result` sont
  préservés verbatim par `_normalize_blocks` (via `_dump_block`) pour rejouer un
  `pause_turn` ; `service.ask` gère `stop_reason == "pause_turn"` en rejouant le
  tour assistant sans tool_result (le serveur reprend).
- **Sources** : `_extract_web_sources` collecte `{url, title}` depuis les blocs
  résultat ; `service.ask` les dédoublonne par URL dans `metadata.web_sources`.
  Le front les rend sous la bulle (`WebSourcesPanel`, clé `agent.web_sources_label`),
  distinct des citations foyer (`<cite/>`). `answer_kind = "web"` quand la réponse
  vient du web sans donnée foyer.
- **Prompt** : `WEB_SEARCH_ADDENDUM` (ajouté par `build_system_prompt(web_search=True)`)
  cadre l'usage : web seulement pour le factuel courant/externe, jamais pour les
  faits foyer ni la connaissance générale stable.

## API

Sous `/api/agent/` :

- `POST ask/` — one-shot (sans persistance).
- `conversations/` (CRUD, privé par user × foyer) ; `POST {id}/messages/` — pose
  une question dans une conversation (history = tours précédents, bornée).
- `POST {id}/messages/stream/` — variante **SSE** du même appel, utilisée par
  l'UI : événements `delta` (morceau de texte), `tool` (tool en cours
  d'exécution), puis un terminal `done` (le message agent persisté, même
  payload que l'endpoint non-streamé) ou `error`. Persistance identique (les
  deux tours ne sont écrits qu'une fois la réponse obtenue). Chaîne interne :
  `AnthropicClient.run_stream` (SDK `messages.stream`) → `service.ask_stream`
  (générateur, `ask()` le draine pour les appels non-streamés) → view SSE.
- `GET conversations/for_context/?entity_type=&object_id=` — get-or-create de la
  conversation ancrée d'une entité pour l'utilisateur courant.
- `POST {id}/pin_context/` / `POST {id}/unpin_context/` (body `{entity_type,
  object_id}`) — épingle/retire une entité du contexte de la conversation ; renvoie
  la conversation avec son `injected_context` rafraîchi.
- `GET conversations/search_context/?q=` — recherche full-text foyer pour le picker
  « Ajouter du contexte » ; délègue à `search_api.search_household_entities` (voir
  juste en dessous) ; `q` vide → `[]`.

Hors de `/api/agent/`, parce que ce n'est pas une conversation :

- `GET /api/search/?q=&limit=&semantic=` — **recherche globale de l'app** (palette de
  la barre du haut), `apps/agent/search_api.py`. Même retrieval, même ranking, même
  gating par modules que le tool `search_household` ; renvoie `{results:
  [{entity_type, object_id, label, url, snippet}]}` dans les deux cas.
  - sans `semantic` : **étape lexicale** (`hybrid=False`), quelques requêtes SQL
    indexées — c'est ce qui part à chaque frappe débouncée ;
  - `semantic=1` : **étape sémantique** (`retrieval.semantic_only`), qui renvoie ce
    que la jambe vectorielle trouve **moins** ce que l'étape lexicale a déjà renvoyé,
    et `[]` quand `AGENT_HYBRID_RETRIEVAL_ENABLED` est off (sans appeler le
    fournisseur).
  - Throttle propre (`search`, 120/min) : le plein-texte ne coûte aucun appel
    provider, mais un endpoint de type-ahead reste ce qu'on laisse tourner en boucle
    le plus facilement. Doc :
    `docs/MODULES/shell-and-design-system.md` § « Recherche globale ».
- `memories/` (CRUD, privé par user × foyer) + `DELETE memories/clear/` (efface
  tout, renvoie `{deleted: n}`) — mémoire utilisateur.
- Permissions : `IsAuthenticated, IsHouseholdMember` ; `ask`, `messages` et
  `messages/stream` sont throttlés (`agent_burst`/`agent_sustained`).

## Notes / décisions

- Les modèles `AgentConversation`/`AgentMessage` ne sont **pas** enregistrés dans
  `searchables` : ce sont les transcripts de l'agent, jamais de la connaissance
  foyer.
- Ancre = couple de strings (pas de GenericFK) pour rester cohérent avec le
  langage `entity_type:id` des tools. Entité supprimée → ancre orpheline →
  `build_entity_context` renvoie `None`, la conversation continue sans contexte.
- `AIUsageLog` trace chaque appel LLM (feature, provider, model, durée, tokens),
  **pas** le contenu des prompts/réponses.
- Confidentialité : modale non-dismissible avant première utilisation
  (`PrivacyNotice` + `privacyStorage`), partagée entre `AgentPage` et
  `EntityAssistant`.

## Retrieval hybride (parcours 21) — full-text + sémantique

Le retrieval combine deux jambes, fusionnées par **Reciprocal Rank Fusion** :

- **lexicale** — `tsvector` / `simple_unaccent` (comme avant) ;
- **sémantique** — embeddings `pgvector`, pour retrouver par le sens quand le
  vocabulaire de la question diverge des documents (« chauffage » → facture
  « pompe à chaleur »).

**`apps/agent/` reste transparent au changement** : la fusion vit **dans**
`retrieval.search()`, dont la signature et le type de retour (`list[Hit]`) ne
bougent pas ; tools (`search_household`…), service, conversation ancrée, digest et
Telegram n'en savent rien.

Artefacts : `embeddings.py` (`EmbeddingClient`, miroir de `llm.py` ; provider
`voyage` par défaut, `ollama` en cible), modèle `EmbeddingChunk` (+ `indexing.py`
write-time, gated par `EMBEDDING_INDEXING_ENABLED`), command `backfill_embeddings`,
et les fonctions `_vector_search` / `_fuse_rrf` de `retrieval.py`.

**Deux flags, off par défaut** (rollout maîtrisé) :
- `EMBEDDING_INDEXING_ENABLED` — indexation write-time sur `post_save`/`post_delete` ;
- `AGENT_HYBRID_RETRIEVAL_ENABLED` — jambe sémantique dans `search()` (off =
  full-text à l'octet près). À activer une fois `VOYAGE_API_KEY` posé et le corpus
  indexé (`manage.py backfill_embeddings`).

**⚠️ La recherche-à-la-frappe ne fusionne pas, elle sert en deux temps.** Une
*question* posée à l'agent paie un embedding par tour : négligeable, donc `search()`
lit le flag. Une boîte de recherche envoie une requête tous les 250 ms de frappe, et
l'embedding coûte **211 ms en moyenne, 1,6 s au pire** (mesuré sur 808 appels de prod).
D'où le découpage : l'étape lexicale passe `hybrid=False`, l'étape sémantique
(`retrieval.semantic_only`) lit le flag et renvoie la **différence** des deux jambes.
Ne pas remplacer par un héritage du flag dans `search()` — ce serait remettre les deux
legs en série derrière le fournisseur. Régressions :
`agent/tests/test_global_search.py::TestTheSemanticLegIsASecondStage` (dont : l'agent
continue d'honorer le flag, ce n'est pas un kill switch) et
`::TestTheSecondStageAddsWhatTheFirstCannotFind` (le gain de rappel, et l'absence de
doublon avec l'étape une).

Fiche concept (le cours) : [docs/fiches/EMBEDDINGS.md](../fiches/EMBEDDINGS.md).
Backlog : [PARCOURS_21_BACKLOG_TECHNIQUE.md](../parcours/PARCOURS_21_BACKLOG_TECHNIQUE.md).

Voir aussi : fiche concept [docs/fiches/RAG.md](../fiches/RAG.md) (section « conversation ancrée »), parcours [PARCOURS_07](../parcours/PARCOURS_07_AGENT_CONVERSATIONNEL.md).
