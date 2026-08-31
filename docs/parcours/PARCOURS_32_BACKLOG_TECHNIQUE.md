# Parcours 32 — Backlog technique V1

> **Cadré le 2026-08-19.** L'implémentation d'un lot se fait avec le skill
> `/new-feature`, qui consomme ce document comme point de départ.

## Tableau de bord

Issue parente : **#652**.

| Lot | Sujet | Statut | Issue |
|---|---|---|---|
| 1 | Le moteur d'entretien — capacité, plafond, sortie stricte, aucune écriture | ⬜ À faire | #653 |
| 2 | La création en lot — un plan relu devient projet + tâches + notes | ⬜ À faire | #654 |
| 3 | L'écran — entretien, relecture éditable, gating par capacité | ⬜ À faire | #655 |
| 4 | L'enveloppe du chantier — `Project.default_budget`, non plafonnée | ⬜ À faire | #656 |
| 5 | Les pièces jointes — joindre pendant l'entretien, lier au projet créé | ⬜ À faire | #657 |
| — | *(différé)* Corriger la façon dont l'assistant travaille | 💡 Idée | #658 |

## Doc associée

- Doc produit : [PARCOURS_32_RACONTER_UN_CHANTIER.md](./PARCOURS_32_RACONTER_UN_CHANTIER.md)
- Fiche concept : [ENTRETIEN_DIRIGE.md](../fiches/ENTRETIEN_DIRIGE.md) — **à lire
  avant le lot 1**
- Doctrine transverse : [PARCOURS_IA_TRANSVERSE.md](./PARCOURS_IA_TRANSVERSE.md)
  — modes de validation, contrat de provenance
- User stories : [USER_STORIES.md](../USER_STORIES.md) — `PROJ-01` à `PROJ-14`
- `CLAUDE.md` — « Capacités optionnelles », « Débit », « Pattern standard — Feature
  page », « Saisie d'un décimal », « Un champ de saisie fait 16px sur mobile »,
  « Fraîcheur des données », « Le budget est la catégorie »
- Patterns de référence — **les lire avant de coder** :
  - `apps/games/riddles.py` + `apps/games/views.py::generate_riddles` — génération
    structurée, validation stricte, capacité + throttle dédiés, aucune écriture
  - `apps/tasks/services.py::create_task` et
    `apps/interactions/services.py::create_note_interaction` — les deux services
    métier que la création en lot **réutilise** (jamais d'ORM brut)
  - `apps/zones/services.py::resolve_zone_ids` — la seule définition de « quelle
    pièce désigne ce mot »
  - `apps/banking/views.py::set_allocations` — le patron du 400 préfixé du numéro
    de ligne
  - `e2e/hunt-riddles.spec.ts` — comment on teste un écran adossé au modèle sans
    dépendre d'une clé

## Flow cible

1. l'utilisateur ouvre « Créer avec l'assistant » depuis la page Projets et écrit
   une phrase
2. `POST /api/projects/projects/assistant-step/` renvoie **une** question typée,
   ou le plan — le double préfixe est celui du routeur, qui enregistre
   `projects` sous `api/projects/`, comme `register-purchase`
3. tours 2 à 6 — le client renvoie l'historique complet à chaque fois ; le serveur
   ne garde rien
4. au 7ᵉ tour, ou sur « J'ai assez dit », le serveur **force** la production du
   plan
5. l'écran de relecture affiche projet, tâches, notes, enveloppe — tout est
   éditable, chaque item est décochable
6. `POST /api/projects/projects/assistant-create/` crée l'ensemble en **une**
   transaction,
   par les services métier existants
7. bascule vers `/app/projects/:id`, qui n'est pas vide

## Décisions de cadrage

- **L'entretien est sans état côté serveur.** L'historique voyage dans le corps de
  chaque requête. Pas de table, pas de purge, pas de reprise le lendemain — un
  entretien dure trois minutes (justification complète dans la fiche).
- **Le plafond de questions est du code, jamais une consigne de prompt.**
  `MAX_QUESTIONS = 6`, compté sur la longueur de l'historique. Au-delà, le serveur
  ne demande pas au modèle de conclure : il ne lui laisse plus le choix.
- **Deux endpoints, et c'est structurel.** Celui qui parle au modèle ne connaît
  aucune écriture. « Rien n'est écrit avant relecture » ne doit pas dépendre d'un
  `if`.
- **Le modèle ne remplit jamais un montant.** Il donne un ordre de grandeur à côté
  du champ ; le champ reste vide et c'est un `DecimalInput`. Seule exception, au
  lot 5 : un montant **lu dans une pièce jointe** peut être proposé, parce qu'il a
  une source consultable — et il se recopie sur un clic explicite, jamais tout
  seul.
- **La relecture remplace l'undo, à partir du lot.** Le parcours 07 a tranché
  « créer + Undo » pour une écriture conversationnelle ; ça reste vrai pour un
  objet et faux pour douze. La bascule tient à la cardinalité, pas au principe.
- **Le plan édité par l'utilisateur se valide comme une saisie, pas comme une
  sortie de modèle.** Entre la génération et la création, l'humain a réécrit des
  titres et décoché des lignes : ce qui arrive sur `assistant-create` est du
  contenu utilisateur, et passe par un serializer DRF comme n'importe quel POST.
- **Aucune provenance `metadata.ai.*` en V1**, et c'est un choix documenté contre
  la note transverse. Trois raisons : la relecture transfère la paternité (le
  texte créé est celui que l'utilisateur a validé, pas celui que le modèle a
  proposé) ; `Project` n'a pas de champ `metadata`, donc le marquage serait
  **partiel** — deux entités sur trois, ce qui est pire que rien pour un axe censé
  se compter ; et le lot 8 du parcours 07 a déjà acté la même divergence pour les
  écritures synchrones. À rouvrir le jour où un plan se crée **sans** relecture.
- **Les zones héritent, puis s'affinent.** Tâches et notes prennent les zones du
  projet ; si le plan nomme une pièce plus précise, elle est résolue par
  `zones.services.resolve_zone_ids`. Un nom introuvable ou ambigu **retombe sur
  les zones du projet**, jamais sur rien — une tâche sans zone est un orphelin
  silencieux, et le service `create_task` la rangerait dans la zone racine, ce qui
  est pire qu'un rattachement approximatif au bon chantier.
- **Un budget de chantier n'est pas plafonné** (`monthly_amount = NULL`).
  `Budget` est une enveloppe **mensuelle** et un chantier est un one-shot :
  dériver un plafond mensuel de `planned_budget` inventerait un chiffre, et une
  fois le chantier fini la barre afficherait « 0 € / 3 200 € » tous les mois pour
  toujours. Le plafond du chantier reste `Project.planned_budget` ; le `Budget`
  n'est qu'un **axe de classement**, ce qui est exactement sa définition.
- **Pas de repli sans clé.** Le formulaire de création existe et **est** le repli.
  Sans capacité, le bouton est absent (pas grisé), et aucune fonction ne manque.
- **Un document téléversé pendant un entretien abandonné reste dans la
  bibliothèque.** L'entretien ne le possède pas : téléverser est un geste
  délibéré, et le foyer a une page Documents. Faire l'inverse demanderait une
  transaction qui embrasse un envoi de fichier.

---

## Lot 1 — Le moteur d'entretien (#653)

### But

Poser la bonne question suivante, s'arrêter à temps, et rendre un plan de forme
garantie — **sans rien écrire en base**. Livrable testable seul par l'API.

### Backend

- `apps/projects/assistant.py` — nouveau module :
  - `MAX_QUESTIONS = 6` et `INPUT_KINDS = ("text", "amount", "date", "zones", "choice")`
  - `@dataclass(frozen=True) class Question` — `text`, `field`, `input`, `hint`,
    `choices: tuple[str, ...]`
  - `@dataclass(frozen=True) class Plan` — `project: dict`, `tasks: list[dict]`,
    `notes: list[dict]`
  - `@dataclass(frozen=True) class Step` — `state: Literal["asking", "ready"]`,
    `question: Question | None`, `plan: Plan | None`, `asked: int`, `remaining: int`
  - `next_step(household, user, *, goal, history, force_ready=False, language=None) -> Step`
    — un appel modèle par tour, via `agent.llm.get_llm_client()`, `feature="project_assistant"`
  - `_household_context(household) -> str` — zones du foyer (nom + id), types de
    `Project.Type`, langue. **Rien d'autre** : l'entretien n'est pas un RAG.
  - `_parse(text, *, expecting_plan) -> Step` — strict, `ValueError` sur tout
    écart, tolère un bloc fencé (copier `games.riddles._parse`)
- `apps/projects/throttles.py` — `ProjectAssistantThrottle(scope="project_assistant")`
- `config/settings/base.py` — `"project_assistant": "60/hour"` dans
  `DEFAULT_THROTTLE_RATES`. **Une portée sans tarif lève `ImproperlyConfigured` à
  la première requête, donc en production.**
- `apps/projects/apps.py` — `ready()` enregistre
  `CapabilitySpec(key="project_assistant", doc_anchor="assistant-anthropic",
  env_vars=("ANTHROPIC_API_KEY",), available=…)`. Ancre **réutilisée** comme le
  fait `games` : elle existe déjà dans `docs/self-hosting/ai-providers.md`.
- `apps/projects/views.py` —
  `@action(detail=False, methods=["post"], url_path="assistant-step")`.
  `capabilities.require("project_assistant")` **avant tout effet de bord**.
  `get_throttles()` installe le throttle dédié pour cette action seule.
  ⚠️ `url_path` explicite : DRF ne dérive pas le chemin d'un `url_name`, et un
  test passant par `reverse()` resterait vert sur `/assistant_step/`.
  Et la forme fautive ne répond pas 404 mais **405** : `assistant_step` est pris
  pour un identifiant de projet par la route de détail. Un front qui se
  tromperait n'aurait donc aucun indice pointant vers `url_path`.
- `apps/projects/serializers.py` — `AssistantStepSerializer` (entrée : `goal`,
  `history: [{question, field, answer}]`, `force_ready: bool`).
- i18n backend : **aucun**. Les libellés sortent du modèle dans la langue de
  l'utilisateur (`translation.get_language()`), comme `games.riddles`.

### Critères

- Un historique de 6 réponses renvoie `state: "ready"` — **jamais** une 7ᵉ
  question, quelle que soit la réponse du modèle (test avec un client stubé qui
  insiste pour questionner).
- `force_ready=True` au premier tour rend un plan.
- Une réponse mal formée (JSON invalide, `state` inconnu, plan sans `project`)
  lève et l'API répond une erreur nommée, **sans plan partiel**.
- Sans clé : 503 nommé, et **aucun appel au fournisseur** (test sur le mock).
- Le compte d'objets en base est identique avant et après un entretien complet —
  le test le vérifie sur `Project`, `Task` et `Interaction`.
- `test_rate_limits.py` reste vert (la portée a son tarif).

---

## Lot 2 — La création en lot (#654)

### But

Transformer un plan **relu et corrigé** en objets, par les services métier
existants, en une transaction — ou en aucun objet.

### Backend

- `apps/projects/services.py` :
  - `create_project_from_plan(household, user, *, plan: dict) -> Project`,
    `@transaction.atomic`. Ordre : projet (via `ProjectSerializer`), puis tâches
    (`tasks.services.create_task`), puis notes
    (`interactions.services.create_note_interaction`).
  - `resolve_item_zone_ids(household, *, project_zone_ids, zone_names) -> list[str]`
    — délègue à `zones.services.resolve_zone_ids` ; sur `ValueError` (introuvable
    ou ambigu) retombe sur `project_zone_ids`. **Jamais une liste vide.**
- `apps/projects/serializers.py` — `ProjectPlanSerializer` : valide la forme
  reçue du client (titre requis, `type` dans `Project.Type`, `planned_budget ≥ 0`,
  bornes sur le nombre de tâches et de notes). C'est une saisie utilisateur, pas
  une sortie de modèle.
- `apps/projects/views.py` —
  `@action(detail=False, methods=["post"], url_path="assistant-create")`.
  **Pas de `capabilities.require`** : créer un projet ne demande aucune clé, et un
  plan déjà obtenu doit rester créable si la clé tombe entre-temps.
- Erreur sur une ligne → **400 préfixé du numéro de ligne** (patron de
  `banking.views.set_allocations`) : un mauvais id de zone ne doit pas donner un
  500.

### Frontend

Rien — le lot est consommé par le lot 3. Le contrat d'API se fige ici.

### Critères

- Un plan de 1 projet + 6 tâches + 2 notes crée exactement 9 objets, ou 0 : le
  test injecte une zone invalide sur la 5ᵉ tâche et vérifie qu'aucun projet ne
  subsiste.
- Une tâche créée par ce chemin est **indiscernable** d'une tâche créée par
  `POST /api/tasks/` — même zones, mêmes défauts, même validation (test qui
  compare les deux).
- Sans zone précisée, tâches et notes portent exactement les zones du projet.
- Une zone nommée qui existe est posée ; un nom inconnu ou ambigu retombe sur
  les zones du projet et n'échoue pas.
- Un plan de 400 tâches est refusé en 400, pas exécuté.

---

## Lot 3 — L'écran (#655)

### But

Rendre l'entretien utilisable : une question à la fois, un contrôle adapté à
chaque question, une relecture où tout se corrige et se décoche.

### Frontend

- `ui/src/features/projects/assistant/ProjectAssistantDialog.tsx` — **SheetDialog**
  (convention du dépôt pour toute modale de formulaire), deux phases internes.
- `.../ProjectAssistantInterview.tsx` — la boucle Q/R, l'historique affiché
  au-dessus, le bouton **« J'ai assez dit, génère »** présent **dès la première
  question**.
- `.../AnswerField.tsx` — rend le contrôle selon `input` :
  `amount` → **`DecimalInput`** de `@/design-system/decimal-input` (jamais un
  `<input type="number">`) ; `date` → le sélecteur de date déjà utilisé par
  `ProjectDialog` ; `zones` → le `ZonePicker` existant ; `choice` → des pilules ;
  `text` → champ libre. Tout champ ajouté ici passe par `fieldBase` — **16px sur
  mobile**, sinon iOS zoome à l'ouverture.
- `.../ProjectAssistantReview.tsx` — projet éditable, listes de tâches et de
  notes avec case à cocher et titre éditable inline.
- `ui/src/features/projects/hooks.ts` — `useAssistantStep()`,
  `useCreateFromPlan()` ; le `onSuccess` déclare **`invalidate('projects')`**, et
  la fermeture transitive de `DERIVED_FROM` doit couvrir `tasks`, `interactions`
  et `dashboard` — **vérifier, et compléter le graphe si ce n'est pas le cas**.
- `ui/src/lib/api/projects.ts` — `assistantStep`, `assistantCreate`.
- `ui/src/features/projects/ProjectsPage.tsx` — bouton « Créer avec l'assistant »,
  rendu **conditionnellement** à `useCapability('project_assistant')`.
- i18n `projects.assistant.*` dans les **4** catalogues (skill `/translate`).

### Points de vigilance

- Le bouton « Annuler » ne se désactive **jamais** pendant `isPending` ; seul le
  submit se désactive — et il le doit, c'est le seul garde-fou contre une double
  création (la création n'est pas idempotente).
- Une erreur de forme au retour du modèle s'affiche comme « je n'ai pas réussi,
  reformule » avec la question précédente conservée — l'entretien ne se perd pas.

### Critères

- Sans la capacité, le bouton est **absent du DOM** — pas désactivé (test e2e).
- Décocher une tâche la retire du corps envoyé (test unitaire sur la construction
  du payload).
- `e2e/project-assistant.spec.ts` : l'endpoint d'entretien est **stubé**
  (`page.route`, comme `hunt-riddles.spec.ts`), l'endpoint de **création ne l'est
  pas** — le chemin d'écriture doit être prouvé de bout en bout, c'est lui qui
  porte le risque.
- `ui/src/locales/keys.test.ts` vert : parité des 4 catalogues, zéro
  `defaultValue`.

---

## Lot 4 — L'enveloppe du chantier (#656)

### But

Donner au chantier un axe de classement pour ses dépenses, sans inventer un
plafond mensuel.

### Backend

- `apps/projects/models.py` — `Project.default_budget = FK("budget.Budget",
  null=True, blank=True, on_delete=SET_NULL, related_name="default_for_projects")`.
  `SET_NULL` : supprimer une enveloppe est supprimer une rubrique, ça ne doit
  jamais emporter le chantier.
- Migration de schéma (additive — pas de livraison en deux temps nécessaire).
- `apps/projects/assistant.py` — le contexte injecté liste les budgets existants
  du foyer (id + nom) ; le plan porte
  `project.budget: {"mode": "existing", "id": …} | {"mode": "new", "name": …} | null`.
  Le prompt exige de **proposer un budget existant** quand un nom colle, et de
  n'en créer un que sinon.
- `apps/projects/services.py` — `create_project_from_plan` crée le cas échéant un
  `Budget(monthly_amount=None)` et le pose en `default_budget`.
- `apps/projects/serializers.py` — `default_budget` exposé en lecture/écriture.

### Frontend

- `ui/src/features/projects/ProjectPurchaseDialog.tsx` — pré-sélectionne
  `project.default_budget` dans le sélecteur `budget_id`, **modifiable**.
- Relecture (lot 3) : une ligne « Enveloppe », avec le choix entre un budget
  existant, un nouveau, ou aucun.
- i18n `projects.assistant.budget.*` × 4.

### Critères

- Un budget créé par ce chemin a `monthly_amount = NULL` et l'aperçu Budgets
  l'affiche **`uncapped`**, jamais `ok` — et le payload renvoie `"amount": null`,
  jamais `"0.00"`.
- Supprimer le budget laisse le projet debout, `default_budget` à `NULL`.
- Un achat enregistré sur le projet part avec le budget pré-sélectionné.
- L'assistant propose l'enveloppe existante quand elle existe : test avec un
  budget « Travaux » déjà en base et un plan de rénovation.

---

## Lot 5 — Les pièces jointes (#657)

### But

Laisser joindre un devis ou une photo **pendant** l'entretien, s'en servir pour
poser de meilleures questions, et relier les pièces au projet créé.

⚠️ **Ce lot n'est pas l'étape 2 de l'ancien wizard.** Là-bas, le téléversement
était un passage **obligé placé avant** la génération ; ici il est **facultatif et
disponible à partir du deuxième tour** — on parle d'abord, on joint si on a
quelque chose.

### Backend

- `apps/projects/serializers.py` — `document_ids: list[UUID]` accepté par
  `assistant-step` et par `assistant-create`.
- `apps/projects/assistant.py` — le contexte injecte, par document joint, son
  `extracted_text` **tronqué** et son nom de fichier. L'extraction a déjà eu lieu
  au téléversement (`documents/views.py::_run_extraction`) : aucun appel de vision
  supplémentaire ici, donc aucun cap à ajouter.
- `apps/projects/services.py` — `create_project_from_plan` crée les
  `documents.DocumentLink` vers le projet créé.

### Frontend

- Un bouton « Joindre » dans l'entretien, qui réutilise **`DocumentUploadDialog`**
  et **`EntityAttachDocumentDialog`** (déjà écrits, `ui/src/features/documents/`).
- Quand un montant est lu dans une pièce, la question de budget affiche la
  citation exacte (« le devis joint indique 3 180 € ») et un bouton **« utiliser
  ce montant »** — le champ reste vide tant que personne ne clique.

### Critères

- Un entretien abandonné après un téléversement laisse le document dans la
  bibliothèque, sans lien — comportement **attendu**, couvert par un test qui le
  fige.
- Le projet créé porte un `DocumentLink` par pièce jointe.
- Le montant d'un devis n'atterrit jamais dans le champ sans clic (test e2e).
- Un document d'un autre foyer envoyé dans `document_ids` répond 403, jamais un
  contexte fuité.

---

## Ordre recommandé d'implémentation

**1 → 2 → 3**, et à ce point la V1 est utilisable de bout en bout : c'est le
palier à livrer et à faire vivre quelques jours avant d'ajouter le reste.
Puis **4**, puis **5**. Les lots 4 et 5 sont indépendants l'un de l'autre.

Chaque lot est livrable seul : 1 et 2 sont testables par l'API, 3 rend le tout
visible, 4 et 5 enrichissent sans rien casser.

## Points de vigilance

- **Ne jamais faire écrire le modèle directement.** Toute création passe par
  `create_task` / `create_note_interaction` / `ProjectSerializer`. Un chemin
  d'écriture parallèle rouvrirait tous les invariants que ces services tiennent.
- **`resolve_zone_ids` est la seule définition de « la chambre ».** Ne pas
  réimplémenter un appariement de nom dans `assistant.py`.
- **La création n'est pas idempotente.** Le seul garde-fou V1 est le submit
  désactivé pendant `isPending`. Si un double envoi est constaté en usage réel,
  la suite est une clé d'idempotence dans le corps — pas un `get_or_create` sur
  le titre, qui casserait deux chantiers homonymes légitimes.
- **Le throttle compte des euros, pas des requêtes.** Un entretien vaut jusqu'à
  sept appels au fournisseur : c'est la raison d'être de la portée dédiée, comme
  `document_upload` et `hunt_riddles`.
- **Le module projets est core**, non désactivable : pas de `module=` sur la
  capacité, et rien à ajouter à `PINNABLE_MODULES`.
- **Le tutoriel du module projets change** : la V1 introduit un nouveau chemin de
  création. Skill `/tutorials`, dans la PR du lot 3.

## Définition de done technique

1. `pytest` vert, y compris `apps/core/tests/test_rate_limits.py` et
   `apps/app_settings/tests/test_capabilities.py`.
2. `npm run build` vert (le vrai typecheck — `tsc --noEmit` ne vérifie rien ici)
   et `npm run lint` propre.
3. `ui/src/locales/keys.test.ts` vert : les 4 catalogues à parité, zéro
   `defaultValue`.
4. `ui/src/lib/invalidate.test.ts` vert, et `DERIVED_FROM` complété si la création
   en lot touche une racine non déclarée.
5. `e2e/project-assistant.spec.ts` écrit, entretien stubé et création réelle.
6. Les user stories `PROJ-01` à `PROJ-14` citées dans les titres des specs, et
   `docs/USER_STORIES.md` mis à jour (⬜ → ✅ seulement quand un test cite l'id).
7. `docs/MODULES/projects.md` à jour — la section « Création assistée » décrit le
   contrat des deux endpoints et la règle des zones.
8. Page Tutoriel à jour (skill `/tutorials`) — le parcours de création change.
9. Aucun secret dans le diff ; `gitleaks` vert.
10. Compte rendu d'implémentation dans la dernière PR (soucis rencontrés,
    arbitrages pris), puis fermeture de l'issue parente.
