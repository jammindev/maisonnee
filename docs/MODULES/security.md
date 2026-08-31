# Sécurité — modèle de menace et surfaces

> Écrit au **lot 1 du [parcours 28](../parcours/PARCOURS_28_OUVRIR_MAISONNEE.md)**
> (issue #487), après instrumentation des 88 classes de vue de l'API.
> Fiche concept associée : [`AUTO_HEBERGEMENT.md`](../fiches/AUTO_HEBERGEMENT.md).

## Ce qui a changé de nature

Le scoping `household` traverse 33 apps. Tant que le code était privé, il séparait
des gens qui vivent sous le même toit et se font confiance. Le dépôt étant public
depuis le 2025-09-21, il sépare désormais des inconnus dont l'un peut être
hostile — et **un trou de scoping ne se devine plus, il se lit**.

La bascule ne concerne pas que de futurs utilisateurs : l'instance de production
de l'auteur tourne pendant que ses sources sont lisibles.

## L'état réel, mesuré

Instrumentation des 88 classes de vue montées sous `/api/`, en inspectant le SQL
réellement produit :

| | |
|---|---|
| Contraintes par foyer | **57** |
| Contraintes par utilisateur seul | 1 — `NotificationViewSet` |
| Non contraintes | 1 — `ChangelogViewSet` |
| Sans queryset (`APIView`, JWT) | 26 |

Les 44 viewsets servant un modèle `HouseholdScopedModel` sont **tous** bornés, y
compris les cinq tables de liaison (`ProjectZone`, `TaskInteraction`,
`InteractionContact`, `InteractionStructure`, `EquipmentInteraction`) — l'endroit
où le scoping s'oublie d'ordinaire, ici traversé par `project__household` ou
`task__household`.

Les deux écarts sont **assumés et testés** :

- `NotificationViewSet` — une notification appartient à une **personne**, pas à un
  foyer. Borner par foyer serait plus permissif, pas moins.
- `ChangelogViewSet` — modèle global par conception (infra applicative, cf.
  `CLAUDE.md` § Changelog), protégé par `IsAdminUser`. Le test vérifie que cette
  permission est toujours là : une exemption sans contrepartie serait un trou
  avec un commentaire.

## Comment la propriété est tenue

`apps/core/tests/test_tenant_isolation.py` parcourt le **routeur DRF réel** et
vérifie, pour chaque endpoint enregistré, que la requête produite est bornée.
Ajouter un viewset non scopé le fait échouer sans que personne ait à y penser —
même mécanique que `banking.compliance.REGISTRY` ou que la parité i18n.

Trois choses à savoir avant d'y toucher :

1. **L'inspection porte sur ce qui suit le `FROM`, jamais sur le SQL entier.**
   La liste de colonnes d'un `SELECT` sur un modèle scoped contient toujours
   `"table"."household_id"` : chercher « household » n'importe où rendait le test
   vert sur un `Model.objects.all()` sans le moindre `WHERE`. Le fichier a eu ce
   défaut et il ne s'est vu qu'en **sabotant volontairement** un viewset. Un
   contrôle qu'on n'a jamais vu échouer n'est pas un contrôle.
2. **Un garde-fou vérifie que la découverte trouve encore plus de 50 vues.** Si un
   renommage d'URL cassait le parcours du routeur, le test passerait en ne
   vérifiant rien — et un contrôle qui ne contrôle plus ressemble exactement à une
   absence d'écart.
3. **Une exemption est une dette nommée.** Elle vit en tête du fichier, avec sa
   raison et sa contrepartie.

## L'écriture — un plancher partagé, pas six vigilances

> Ajouté au **lot 1bis** (issue #498).

Le test ci-dessus ne parcourt que les **lectures**. La différence de nature
compte : une lecture mal bornée se voit — la liste montre ce qu'elle ne devrait
pas. Une **écriture** mal bornée ne se voit pas : elle réussit, l'utilisateur lit
« enregistré », et l'objet d'un autre foyer entre dans le graphe sans un mot.

Six champs relationnels de serializer acceptaient `Model.objects.all()`, donc
n'importe quel identifiant. **Cinq étaient rattrapés en aval** — mais par trois
mécanismes différents, écrits indépendamment :

| Site | Ce qui protégeait |
|---|---|
| `InteractionDocumentSerializer` (×2) | `validate()` : les deux objets dans les foyers de l'user, même foyer, foyer sélectionné cohérent |
| `TaskDocumentLinkSerializer` (×2) | `TaskDocumentViewSet.perform_create` : tâche accessible, **créateur seul**, document du même foyer |
| `TrackerEntrySerializer` | `validate_tracker` + `services.add_entry` qui repasse toujours `household_id` |

**Le sixième n'avait rien.** `ShoppingListItemSerializer.stock_item` : ni
`validate_*`, ni contrôle dans la vue, ni dans `create_list_item`. Rattacher
l'article de stock d'un autre foyer à sa liste réussissait, et la réponse en
divulguait le **nom**, le statut et l'emoji via `get_stock_item_name`. Non
exploitable en pratique — il faut connaître l'UUID — mais rien ne l'arrêtait.

Il est révélateur de la manière dont il a été trouvé : **pas par relecture, pas
par `grep`** (il était écrit sur trois lignes, le motif de recherche l'a raté),
mais par le test générique, à sa première exécution.

### Le champ partagé

`core.serializers.HouseholdScopedPrimaryKeyRelatedField(model=…)` borne son
queryset au foyer résolu — contexte explicite, puis `request.household`, puis
les foyers de l'utilisateur, puis **rien**.

Ce dernier point est le comportement important : **sans contexte exploitable, le
champ n'accepte aucun identifiant.** Un champ qui laisse passer quand il ne sait
pas protège exactement tant que personne ne l'attaque ; fermer par défaut rend le
défaut bruyant, tout de suite, chez celui qui l'introduit.

**C'est un plancher, pas un plafond.** Il garantit « l'objet est dans un foyer
accessible » ; il ne dit rien de « les deux objets sont dans le *même* foyer » ni
de « seul le créateur peut attacher ». Les validations existantes vérifient ces
choses en plus et **n'ont pas été retirées** en posant le champ.

Régression : `apps/core/tests/test_write_isolation.py`, vérifié par sabotage.

### Ce qui reste ouvert en écriture

- **Les actions custom.** `test_tenant_isolation` n'exerce que `list`. Le risque
  n'est pas `get_object()`, qui passe par `get_queryset()` et est donc déjà
  couvert : c'est une `@action` qui fait sa **propre** requête ORM. Ça ne se
  détecte pas au SQL, seulement à la lecture.
- **Les 26 `APIView`.** Sans queryset, donc invisibles pour les deux tests
  génériques. À examiner une par une.

Les deux restent dans l'issue #498.

## Les surfaces qui ne passent pas par un queryset

Le test ci-dessus ne peut rien dire de ce qui n'interroge pas la base par un
viewset. Ces surfaces ont leurs propres contrôles.

### Les fichiers — `apps/core/views_media.py`

**C'est la seule porte du foyer qui ne passe ni par un viewset ni par un
queryset** : elle reçoit un chemin et rend des octets. Les 57 querysets peuvent
être parfaits sans que ça protège un seul fichier.

Deux défauts y ont été trouvés et corrigés au lot 1 :

- **Default-allow.** Seul `documents/` était contrôlé ; tout autre préfixe était
  servi à n'importe quel utilisateur authentifié. Les avatars fuyaient d'un foyer
  à l'autre, et un préfixe ajouté plus tard (exports, sauvegardes, pièces
  jointes) aurait été public par défaut, sans une ligne de code pour le trahir.
  La règle est inversée : **ce qui n'est pas déclaré dans `_CHECKS` est refusé**.
- **La vignette d'un document privé échappait au contrôle.** La confidentialité
  cherchait le document par `file_path` exact ; une vignette vit à un autre
  chemin, donc `DoesNotExist` puis `pass`. Pour un scan ou une photo, **l'aperçu
  *est* le document** : `is_private` ne protégeait que l'original. La fonction qui
  remonte de la vignette au document vit **à côté** de celle qui produit le
  chemin (`documents/thumbnails.py`), pour qu'elles ne puissent pas se désaligner.

⚠️ **Et le durcissement lui-même a produit le troisième défaut** (issue #517) :
`_CHECKS` déclare les préfixes que `Document.build_upload_path` écrit
**aujourd'hui**, alors que la base porte encore ceux d'hier. Les documents rangés
sous `<foyer>/<dossier>/…` sont tombés en 403 d'un bloc — **177 sur 202 en
production**, vignettes comprises, donc la page Photos vide et aucun document
consultable. Personne n'a pu le voir : les tests d'isolation fabriquaient leurs
fixtures avec le builder, c'est-à-dire dans la seule disposition qui marchait
encore. **Un test qui ne connaît qu'un schéma de chemin ne peut pas voir mourir
les autres** — d'où des chemins écrits en dur, sous la forme trouvée en base.

D'où la règle qui porte les deux premières :

> **Un fichier se rattache à un foyer en base, pas par la forme de son chemin.**

Un préfixe déclaré garde son contrôle ; tout le reste passe par
`_check_by_ownership`, qui demande à la base **quel document réclame ce
fichier** et contrôle sur le foyer *de ce document*. Ce qu'aucun document ne
réclame reste refusé — le default-deny est intact, et il ne dépend plus d'un
schéma de nommage qui, lui, changera encore.

Régression : `apps/core/tests/test_media_isolation.py`.

**Ajouter un emplacement de fichiers = ajouter sa ligne dans `_CHECKS`.** Sans
elle, le chemin doit se faire reconnaître en base ou il est refusé.

### La révocation d'accès — un invariant sur un fil

`request.household` vient de `User.active_household`, que
`ActiveHouseholdMiddleware` charge **par son id, sans revérifier l'appartenance**.
La révocation ne tient donc qu'au signal `post_delete` qui remet le champ à zéro
quand une adhésion disparaît.

Ça fonctionne — vérifié — mais c'est un fil, et un fil se coupe : un
`_raw_delete`, une suppression en SQL brut ou un `bulk_delete` mal branché le
sectionnerait sans bruit, et un membre exclu continuerait de tout lire. D'où trois
tests dans `test_tenant_isolation.py::TestLosingMembershipRevokesAccessImmediately`,
dont un sur la suppression en masse.

**Alternative écartée** : revérifier l'appartenance à chaque requête dans le
middleware. C'est une requête de plus sur *chaque* appel API pour couvrir un
événement rare. Le test est moins cher et attrape la même chose — mais si le
middleware devait changer, c'est la première option à reconsidérer.

### L'agent

Ses tools s'adressent en `entity_type:id`, ce qui contourne les URLs. Le scoping
est appliqué aux trois points d'entrée : `agent/tools.py::resolve_entity`
(`filter(household_id=household.id, pk=raw_id)`), la résolution des relations, et
les listes. Le tool d'écriture `create_entity` passe par les services métier, qui
portent la même contrainte.

### La confidentialité intra-foyer — la deuxième frontière

Le scoping tient la frontière **entre** foyers ; `is_private` en trace une seconde
**à l'intérieur** de chacun : moi contre les autres membres. Fiche complète :
`docs/fiches/CONFIDENTIALITE.md`. Ce qu'il faut savoir ici :

- Elle est **plus fragile** que la première, et pour une raison structurelle : le
  scope foyer vient du manager par défaut, donc on l'obtient sans y penser. La
  confidentialité doit être ajoutée explicitement à chaque lecture, et un
  `get_queryset()` qui l'oublie fonctionne parfaitement.
- Elle est **invisible deux fois** : en revue, la clause manquante ne se distingue
  pas de la clause présente ; à l'usage, il faut deux comptes dans le même foyer
  pour la voir manquer. C'est la définition d'un contrôle à écrire.
- **Une déclaration par modèle** (`core.visibility.REGISTRY`, alimenté depuis
  l'`apps.py` de l'app propriétaire) et **un seul point d'application**
  (`narrow_for`). L'implémentation du couple standard est `visible_to_creator`,
  fail-closed, adossée à `created_by` et jamais au rôle.
- **Sept portes.** La liste REST, plus les six chemins de retrieval (palette ⌘K,
  `search_household`, `get_entity`, `get_related`, `list_entities`, contexte
  ancré) — qui ne passent **jamais** par le viewset. Un modèle non déclaré est donc
  **absent de sa propre liste et citable par l'assistant** : c'est exactement ce qui
  a vécu en production pour les tâches et les notes, le correctif précédent n'ayant
  traité que les documents.
- **Masquer ≠ cacher.** Ce qui alimente un compteur partagé se masque (l'argent),
  ce qui n'alimente rien se cache. Une dépense privée reste dans toutes les
  agrégations : la cacher d'une liste sans la retirer des totaux donnerait deux
  valeurs au même compteur selon le lecteur.
- **Un compteur qui déborde est une fuite.** Un onglet annonçant « Tâches (3) » et
  en servant deux trahit l'existence de l'item privé à qui sait soustraire.

Régressions : `apps/core/tests/test_privacy_isolation.py` (quatre parties, dont la
n°4 qui refuse un modèle privatisable non enregistré — et qui lit le registre, pas
le champ, pour pouvoir voir arriver une confidentialité héritée) et
`apps/agent/tests/test_private_visibility.py`.

### Les liaisons polymorphes

`interactions.services.resolve_allocation_source` **récupère l'objet et compare
son `household_id`** plutôt que de faire confiance à l'identifiant reçu. Sans ça
un client gonflerait le coût d'un chantier qu'il ne peut pas voir. C'est
documenté dans la fonction elle-même, et c'est le modèle à suivre pour toute
future FK polymorphe.

## La configuration de production

Elle était déjà solide avant ce lot — le travail a consisté à la **figer**, pas à
la construire (`apps/core/tests/test_production_settings.py`) :

- `DEBUG = False` est une **constante**, pas une valeur d'environnement : rallumer
  le mode debug en production demande d'éditer un fichier ;
- `ALLOWED_HOSTS` n'a **pas de défaut** — sans lui, le démarrage échoue au lieu
  d'accepter n'importe quel `Host:` ;
- `CORS_ALLOWED_ORIGINS` **lève à l'import** s'il manque ;
- cookies `Secure`, HSTS d'un an avec sous-domaines et preload, `nosniff`,
  referrer policy `same-origin`, redirection HTTPS — avec `/health/` exempté,
  sinon la sonde du deploy casse ;
- clickjacking : `XFrameOptionsMiddleware` + `DENY`.

**Ces réglages sont exactement ceux dont l'absence ne se voit jamais à l'usage** :
l'app fonctionne à l'identique sans HSTS et sans cookie `Secure`. C'est pourquoi
ils sont testés plutôt que relus.

### Throttling

Déjà en place et vérifié : `login_ip` (20/min) **et** `login_email` (5/min) —
c'est le second qui borne une attaque par dictionnaire sur un compte, quelle que
soit l'origine ; plus `change_password`, `password_reset`, `invitation_join`,
`agent_burst`/`agent_sustained`, `search`.

Le test vérifie aussi que les portées déclarées sont **réellement branchées** sur
la vue de connexion : une portée définie mais jamais utilisée ne protège rien et
se lit comme une protection.

#### Le plancher — ce qu'un compte coûte, par défaut

> Ajouté après le constat que les limites ci-dessus étaient les **seules**.

`DEFAULT_THROTTLE_CLASSES` n'était pas posé : tout endpoint qui ne déclarait pas
son propre cap servait sans aucun. Ça ne se lit pas en revue — le diff d'une vue
bornée et celui d'une vue nue sont identiques, et la vue nue est celle qu'on écrit
sans y penser. Sur une instance dont les sources sont publiques, ça coûtait deux
choses : **des euros** (toute écriture d'entité déclenche un embedding, donc un
appel fournisseur) et **du disque**.

Désormais `core.throttles` pose `user_burst` / `user_sustained` / `anon` par
défaut, et deux caps nommés couvrent l'endpoint le plus cher de l'API :
`document_upload` (l'envoi déclenche un appel de vision **synchrone**) et
`ocr_reprocess` (une relance ne coûte rien en disque et tout en fournisseur).
Une vue qui déclare ses propres classes **remplace** le plancher : les caps
serrés de l'agent et de la connexion restent seuls maîtres chez eux.

`core/tests/test_rate_limits.py` refuse toute vue sans plafond, et toute portée
sans tarif — ce second contrôle a d'abord été écrit faux : il lisait
`cls.throttle_classes` et ne voyait donc **aucun** throttle posé par un
`get_throttles()` par action, c'est-à-dire précisément les nouveaux. Vérifié par
sabotage, comme au #487.

#### ⚠️ Un throttle vaut ce que vaut son cache

DRF compte dans `django.core.cache`, qui n'était pas configuré : donc
`LocMemCache`, **un compteur par process**. Avec quatre workers gunicorn, « 5
tentatives de connexion par minute » en autorisait vingt, « 100 questions à
l'agent par heure » quatre cents, et tout repartait à zéro à chaque deploy. Les
limites n'étaient pas fausses de peu — elles l'étaient d'un facteur égal au
nombre de workers, sans que rien ne le signale. C'est « un compteur ne peut pas
avoir deux définitions » appliqué au débit ; il en avait quatre.

Le cache est donc partagé (`DatabaseCache`, table créée par la migration
`core.0003`) : dans Postgres plutôt que dans un service de plus, parce qu'il est
déjà sauvegardé avec le reste et ne coûte pas de RAM. La suite de tests garde
`LocMemCache` — elle tourne dans un seul process, donc le compteur y est juste.

### L'inscription — ouverte par défaut, fermable par `.env`

`POST /api/accounts/users/` est en `AllowAny`, et le dépôt est public depuis le
2025-09-21 : n'importe qui pouvait créer un compte sur n'importe quelle instance
joignable, **sans validation de mot de passe** (`abc` passait — `set_password`
hache n'importe quoi, et rien n'appelait `validate_password` sur ce chemin) et
sans cap de débit. Chaque compte né là pouvait ensuite dépenser la clé de
l'instance.

Trois verrous, et ils visent des choses différentes :

- **`validate_password` à la création** — l'app était plus stricte sur un
  changement de mot de passe que sur le premier, ce qui est l'inverse de ce qu'il
  faut ;
- **`signup` (5/h par IP)** — le seul geste anonyme qui *écrit* ;
- **`ALLOW_OPEN_SIGNUP`** — deux publics, un seul code. L'auto-hébergeur qui
  lance `docker compose up` doit créer son premier compte sans lire un guide ;
  l'instance déjà en service ne doit pas laisser un inconnu s'en créer un. Ouvert
  par défaut, parce que le cas nominal du projet est l'auto-hébergement.

Deux détails qui ont chacun leur raison d'être :

- le refus se dit en **403**, pas en 401. DRF convertit tout refus de permission
  en 401 dès qu'un authenticator annonce un `WWW-Authenticate` — ce que fait
  `JWTAuthentication`. Or 401 veut dire « identifie-toi et recommence », et
  aucune paire d'identifiants n'ouvrira une inscription fermée ;
- `GET /api/accounts/signup-availability/` est **public**, seule lecture des
  comptes à l'être. L'écran de connexion doit pouvoir *ne pas* proposer « créer
  un compte » — sinon l'interface promet et le clic dément, exactement le défaut
  que le lot 3 a passé un lot entier à supprimer. Il n'expose rien que la
  première tentative ne dirait déjà en 403, contrairement à `/api/capabilities/`
  qui reste authentifié pour cette raison précise.

## Ce que tout ça ne prouve pas

Le lot ferme les classes de failles **connues** et installe les contrôles qui les
empêchent de revenir. Il ne démontre pas l'absence de faille — une `@action`
custom qui ouvre son propre chemin, un cas limite d'OCR, un tool d'agent détourné
par un prompt : rien de tout ça ne se prouve par un test paramétré.

C'est aussi la partie où l'ouverture aide : **des yeux extérieurs sur ce code
valent mieux que ceux de son auteur seul.** Le canal de signalement est dans
[`SECURITY.md`](../../SECURITY.md), et il est privé.

## Le risque qui n'est pas technique

Le job `deploy` s'exécute sur le VPS dès qu'un push atterrit sur `main`. **Donner
un accès write au dépôt revient donc à donner un shell sur cette machine.** Les
contributions extérieures passent par fork et pull request — le fonctionnement
normal d'un projet open source, ici avec une raison concrète. C'est écrit dans
`CONTRIBUTING.md`.

Si un contributeur régulier devait un jour obtenir les droits, il faut **d'abord**
sortir le deploy du runner : un VPS qui *tire* (webhook + `git pull`) au lieu d'un
GitHub qui *pousse* supprime la classe entière de problèmes.
