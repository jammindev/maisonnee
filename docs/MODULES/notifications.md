# Module — notifications

> Audit : 2026-04-28. Rôle : notifications in-app user-scoped (génériques via type + payload JSON).

## État synthétique

- **Backend** : Présent
- **Frontend** : Présent — `ui/src/features/notifications/` (cloche de la `TopBar`, page `/app/notifications`, carte, aperçu)
- **Locales (en/fr/de/es)** : namespace manquant : `notifications` absent dans les 4 locales
- **Tests** : oui — 2 fichiers (`test_notifications.py`, `test_notifications_extra.py`)
- **Migrations** : 2 (`0001_initial.py`, `0002_notification_soft_delete.py`)

## Modèles & API

- Modèles principaux : `Notification` (user-scoped, pas household-scoped) avec enum `Type` (`HOUSEHOLD_INVITATION`, `HOUSEHOLD_MEMBER_JOINED`, `STOCK_LOW`, `STOCK_OUT`), payload JSON, soft-delete — *source : `apps/notifications/models.py`*
- Endpoints exposés : `/api/notifications/` (ReadOnly liste + détail)
  - `GET /api/notifications/unread-count/`
  - `POST /api/notifications/{id}/mark-read/`
  - `POST /api/notifications/mark-all-read/`
- Permissions : `IsAuthenticated` (filtrage par `user=request.user` + `deleted_at__isnull=True`) — *source : `apps/notifications/views.py:11-16`*
- Service : `apps/notifications/service.py` expose `send(user, type, title, body, payload)` comme point d'entrée unique pour créer une notification

## Notes

- **User-scoped, pas household-scoped** — chaque notification appartient à un utilisateur (FK `user`), pas à un foyer — *source : `apps/notifications/models.py:23-28`*
- Modèle générique : `type` + `payload` JSON permet d'ajouter de nouveaux types sans migration — *source : `apps/notifications/models.py` docstring*
- Soft-delete via `deleted_at` (le viewset filtre `deleted_at__isnull=True`) — *source : `apps/notifications/views.py:16`*
- Service `send()` est le **point d'entrée unique** : tous les callers (households, projects, tasks…) doivent passer par lui — *source : `apps/notifications/service.py:14`*

## Prévenir un foyer — `notify_household`, et rien d'autre

Toute notification de la famille « **un membre a fait quelque chose** » (une
tâche cochée, une dépense saisie, un arrivant dans le foyer) passe par
`notifications.service.notify_household`. Ajouter un émetteur, c'est écrire ce
qu'il dit — pas comment il le diffuse.

```python
from notifications.service import notify_household

notify_household(
    household,
    Notification.Type.STOCK_LOW,
    actor=request.user,               # exclu des destinataires, tracé dans payload
    text=lambda: (title, body),       # appelé SOUS la locale de chaque destinataire
    url=f"/app/stock/{item.id}",      # où mène la notification
    dedup_key=f"stock:{item.id}:low", # optionnel
    payload={...},
)
```

Les quatre garanties, et pourquoi chacune est du métier :

- **`text` est un callable, jamais deux strings.** Il est appelé une fois par
  destinataire dans `translation.override(sa locale)`. Le texte est stocké en
  clair (règle write-time du `CLAUDE.md`) : il n'y a **pas** de seconde chance à
  l'affichage, donc un appelant qui rend sa phrase une seule fois poste à tout le
  foyer la langue de celui qui a agi. Ce bug était en production dans
  `stock/notifications.py`, invisible parce que la phrase était parfaitement
  valide — simplement pas dans la bonne langue. Régression :
  `stock/tests/test_api_stock_extra.py::TestTheWarningIsWrittenInEachReadersLanguage`.
- **`actor` est exclu**, et c'est la règle partagée de toute la famille : on ne
  notifie personne de sa propre action. `actor=None` pour un fait sans auteur
  (un seuil de stock franchi, une alerte météo) — tout le monde est prévenu.
- **`url` est porté par la ligne, pas par le type.** `_DEEP_LINKS` reste un
  **fallback** pour les notifications qui mènent à un *endroit* ; une famille
  entité-scopée mène à une *chose*, et « Bob a terminé Tondre la pelouse » qui
  atterrit sur la liste des tâches fait refaire au lecteur la recherche que la
  notification venait de faire pour lui. Ordre de résolution :
  `notif.url` → `_DEEP_LINKS[type]` → `/app/dashboard` (`service.deep_link_for`).
- **`dedup_key` remplace trois anti-doublons maison** (weather avait le sien sur
  `payload__day`, stock n'en avait aucun). Portée : `(user, type, key)` **vivant**
  — soft-supprimer, c'est l'utilisateur qui dit qu'il en a fini, donc la
  prochaine occurrence est de nouveau une nouvelle.

### Un émetteur part d'un geste, jamais d'un service partagé

Les émetteurs vivent dans un `notifications.py` par app (`stock`, `households`,
`tasks`, `interactions`) : un effet de bord qui atteint les *autres* utilisateurs
se lit mieux seul que fondu dans une vue. Ce module ne sait que **quoi dire**.

**D'où on l'appelle est une décision, pas un détail.** `task_created` et
`note_created` sont posés sur `TaskViewSet.perform_create`,
`InteractionViewSet.perform_create` et les deux `create` des writables de
l'agent — **jamais** sur `tasks.services.create_task` ni
`interactions.services.create_note_interaction`. Ces services sont la porte
commune : `chickens` y crée la corvée du poulailler, qui a **déjà** son
`chicken_chore_due` ; `orchard` ses travaux saisonniers ; `seed_demo_data` trois
ans de données. Une émission posée dans le service ferait doublon chez le
premier et bavardage chez les deux autres. Le critère est « **un membre vient
d'agir** », et l'agent en fait partie : il ne crée que sur demande explicite, et
le laisser muet ferait dépendre la notification du bouton utilisé.

**Le titre se tronque.** `Notification.title` est un `varchar(255)` là où
`Task.subject` et `Interaction.subject` en acceptent 500. Sans `Truncator`,
Postgres refuse l'insertion et **l'action principale part en 500** : un effet de
bord qui casse ce que l'utilisateur voulait faire est le pire des deux mondes.
Le sujet entier reste dans le `payload`.

**Ce qui est privé ne sonne pas.** Le titre *est* le sujet : notifier une tâche
ou une note `is_private` la publierait mot pour mot à tout le foyer, en allant
chercher le lecteur au lieu d'attendre qu'il regarde. C'est la fuite que
`TaskViewSet.get_queryset` a fermée en liste, par une porte que le filtre ne
surveille pas.

**Et une annonce ne survit pas à son sujet.** Une note se supprime pour de bon
(une tâche, elle, s'archive et garde sa page) : sans `retract_note_created`, la
cloche des autres membres mène à un écran mort, et le lecteur ne peut pas savoir
si c'est l'app ou lui qui se trompe. `service.retract_by_payload` est **non
scopé à un utilisateur**, précisément parce que l'annonce a été fan-outée à tout
le foyer — la retirer chez son seul auteur, qui ne l'a justement jamais reçue, ne
retirerait rien. À appeler depuis **tous** les chemins de suppression d'un objet
notifié (ici le `perform_destroy` de l'API *et* `delete_note_interaction` pour
l'undo de l'agent), pas seulement celui qu'on a sous la main.

Régressions : `tasks/tests/test_creation_notification.py` et
`interactions/tests/test_note_creation_notification.py`.

### Ce que l'utilisateur peut faire taire — et ce qu'il ne peut pas

`User.muted_notification_types` est un opt-**out** (vide = tout arrive), et il ne
peut contenir que des types de `notifications.models.MUTABLE_TYPES`.

- **Certaines notifications ne se coupent pas.** Une invitation est le seul moyen
  d'apprendre quelque chose que personne ne peut faire à votre place ; laisser une
  case la masquer transforme une préférence en piège. Le serializer **refuse en
  400** au lieu d'ignorer : croire qu'on a coupé une invitation est pire que
  s'entendre dire qu'on ne peut pas.
- **Le filtre est dans `send()`, pas à l'écran.** Un type peut sortir de
  `MUTABLE_TYPES` (il s'est avéré important) ; une préférence enregistrée du temps
  où il était silenciable doit cesser de s'appliquer tout de suite, pas attendre
  que l'utilisateur rouvre un écran qu'il ne rouvrira peut-être jamais.
- **La liste est servie** (`GET /api/notifications/mutable-types/`), jamais
  redéclarée dans le front : une liste en dur finirait par proposer une case que
  l'API refuse. Et la couverture i18n (`notifications.type.*` dans les 4
  catalogues) est vérifiée **depuis Python**, seul côté qui connaît la liste —
  même pattern que la palette de recherche.

### Le catalogue des types est l'enum, sans exception

`choices` n'est pas contraint en base et `.create()` ne fait pas de `full_clean` :
une string littérale persiste sans broncher. `weather_alert` a vécu ainsi, absent
de l'affichage admin, absent de `MUTABLE_TYPES`, invisible pour qui lisait la
liste des types. Tout nouveau type se déclare dans `Notification.Type`, et son
appartenance à `MUTABLE_TYPES` est une décision explicite.

### La cloche montre ce que le badge annonce

`ui/src/features/notifications/preview.ts::buildBellPreview` décide des lignes de
l'aperçu. Il existe parce que l'aperçu était un `slice(0, 5)` de la liste triée
par date : l'état lu/non-lu n'entrait pas dans le choix des lignes affichées,
alors qu'il **fonde** le badge. Cinq notifications lues arrivées après un non-lu
suffisaient à rendre ce non-lu introuvable dans la cloche pendant que le badge
affichait « 1 ». C'est « un compteur ne peut pas avoir deux définitions »
appliqué à un aperçu — sauf qu'ici l'écart ne se voit pas : les deux chiffres
sont justes chacun selon sa propre règle.

- **Lire n'est pas supprimer.** Retirer les lues de l'aperçu ferait disparaître
  la ligne sous le curseur au moment même où on la clique, et personne ne
  pourrait revenir sur ce qu'il vient d'ouvrir. `deleted_at` existe pour
  écarter, et écarter reste un geste explicite — même arbitrage que les
  arbitrages de conformité. Les lues restent donc affichées, elles cessent
  seulement de passer devant un non-lu.
- **L'ordre est figé à l'ouverture** (`pinnedIds`), et seul l'ordre : le contenu
  de chaque ligne est relu frais. Sans ce gel, cliquer un non-lu le fait glisser
  derrière les autres non-lus et la ligne suivante monte sous le curseur — on
  clique à côté. Même règle que la jambe sémantique de la recherche globale : on
  ajoute au bas de ce que l'utilisateur lit, on ne réordonne pas sous ses yeux.
- **Une ligne de la cloche mène à ce qu'elle annonce**, en lisant le même
  `notification.url` que `NotificationCard` sur `/app/notifications`. Le
  dropdown se contentait de `mark-read` : le même objet menait quelque part dans
  un écran et nulle part dans l'autre, ce qui laissait des notifications lues
  s'empiler sans qu'on ait jamais pu en faire quoi que ce soit. Une invitation
  reste l'exception — l'envelopper dans un lien avalerait ses propres boutons.

Régressions : `ui/src/features/notifications/preview.test.ts` et le bloc
« l'aperçu tient la promesse du badge » de `NotificationsBell.test.tsx`.

### Le lien servi est le lien résolu

`deep_link_for(notif)` = `notif.url` → `_DEEP_LINKS[type]` → `/app/dashboard`.
Elle n'était appelée que par `_mirror_to_web_push`, pendant que
`NotificationSerializer` exposait la **colonne brute** : une alerte météo (seul
émetteur à ne pas passer d'`url`) menait à sa page depuis la notification
système et **nulle part** depuis la cloche. Le serializer sert désormais le lien
résolu — un même fait n'a qu'une destination, et les deux canaux lisent la même
fonction.

- **Tout type de `Notification.Type` déclare sa destination.** Un catalogue
  incomplet est invisible : le repli est toujours une page valide, donc un type
  oublié atterrit sur le dashboard sans que rien ne le signale. `weather_alert`
  s'était déjà fait oublier dans `MUTABLE_TYPES` et dans l'affichage admin —
  c'était la troisième fois. Tenu par
  `test_deep_links.py::TestTheDeepLinkCatalogueCoversEveryType`.
- **Un émetteur passe quand même son `url`.** Le repli par type rattrape l'oubli,
  il ne dispense pas de viser juste : « Stock bas : café » mène à l'article, pas à
  200 lignes d'inventaire. Le repli est pour ce qui mène à un *endroit*.
- **Il n'y a pas de page de détail de notification, et il n'en faut pas.** Une
  notification mène à la *chose* qu'elle annonce ; une page qui répéterait son
  titre et son corps — déjà lus dans la ligne — serait un cul-de-sac. C'est
  pourquoi le test du catalogue porte sur des destinations métier
  (`/app/stock`, `/app/weather`, `/app/chickens`) et non sur `/app/notifications/{id}`.
