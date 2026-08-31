# Module — documents

> Audit : 2026-04-29. Rôle : fichiers attachés (factures, manuels, photos, etc.) reliés au contexte métier (parcours 02 — traiter un document entrant).

## État synthétique

- **Backend** : Présent et complet. Modèle `Document`, pipeline OCR (Vision + pypdf), thumbnails photos, privacy `is_private`, signals cleanup storage.
- **Frontend** : Complet dans `ui/src/features/documents/` (`DocumentsPage`, `DocumentDetailPage`, `DocumentUploadDialog`, `DocumentEditDialog`, `DocumentCard`, `hooks.ts`). Route câblée dans `router.tsx:60-61`.
- **Locales (en/fr/de/es)** : ok — namespace `documents` présent dans les 4 fichiers avec toutes les clés utilisées.
- **Tests** : 6 fichiers pytest (`test_api_documents.py`, `test_extraction.py`, `test_thumbnails.py`, `test_image_processing.py`, `test_extract_documents_text_command.py`, `test_download_supabase_bucket_files.py`). **3 tests en échec** (divergence tests/code). 0 couverture E2E Playwright.
- **Migrations** : 4 (initiale → `interaction_document` index → `alter_options` → `avatar_upload_path + is_private`).
- **Couverture parcours métier** : parcours 02 (document entrant → activité), parcours 03 (tâche depuis document), parcours 04 (projets).
- **Issues GH ouvertes** : #80 (multi-upload interactions), #39 (séparation Documents/Photos), #36 (OCR automatique — obsolète, implémenté).

---

## Modèles & API

### Modèle `Document` (`apps/documents/models.py`)

- Hérite de `HouseholdScopedModel` → `household` FK avec `on_delete=CASCADE` (suppression household → cascade sur tous ses documents).
- `created_by` / `updated_by` → `on_delete=SET_NULL` (suppression user → documents conservés, `created_by=null`).
- `file_path` : `CharField(500)` — chemin de stockage custom, pas de `FileField` Django. Pattern : `documents/{household_id}/{YYYY}/{MM}/{uuid}-{safe_name}`.
- `type` : choix parmi `photo`, `document`, `invoice`, `manual`, `warranty`, `receipt`, `plan`, `certificate`, `other`.
- `ocr_text` : texte extrait (vide si photo ou extraction échouée).
- `metadata` : JSONField libre — contient `size`, `ocr_method`, `ocr_extracted_at`, `normalized`, `resized`, `dimensions`.
- `taken_at` : `DateTimeField(null=True, db_index=True)` — date de **prise de vue**, lue dans l'EXIF à l'upload (`apps/documents/exif.py`). Voir « Date de prise de vue » plus bas.
- `purpose` : `CharField` (`technical` / `observation` / `memory`, vide = **non trié**) — l'**intention** d'une photo. Voir « L'intention d'une photo » plus bas.
- `is_private` : boolean — filtre appliqué dans le queryset (seul `created_by` voit ses propres privés).
- `interaction` : FK nullable vers `Interaction` (`on_delete=CASCADE`). FK "legacy" conservée par rétro-compat. La relation principale passe désormais par `InteractionDocument` (M2M).
- **Pas de soft-delete** — suppression physique + cascade complète.
- Index : `idx_docs_hh_type` (household+type), `idx_docs_interaction` (interaction), `idx_docs_creator` (created_by), `idx_docs_hh_purpose` (household+purpose).

### Tables de liaison (autres apps)

| Liaison | FK Document `on_delete` | Comportement si document supprimé |
|---|---|---|
| `InteractionDocument` (`interactions/models.py:223`) | `CASCADE` | Lien supprimé |
| `ZoneDocument` (`zones/models.py:132`) | `CASCADE` | Lien supprimé |
| `ProjectDocument` (`projects/models.py`) | `CASCADE` | Lien supprimé |
| `TaskDocument` (`tasks/models.py`) | `CASCADE` | Lien supprimé |

> Comportement correct : supprimer un document nettoie tous ses liens sans laisser d'orphelins dans les tables de liaison. Les entités parentes (zone, interaction, task, project) survivent.

### Endpoints (`/api/documents/`)

| Méthode | URL | Action |
|---|---|---|
| GET | `documents/` | Liste filtrée (type, interaction, search, zone, project, qualification_state) |
| POST | `documents/` | Création sans upload (file_path manuel) |
| GET | `documents/{id}/` | Détail enrichi (linked_interactions, zone_links, project_links, recent candidates) |
| PATCH/PUT | `documents/{id}/` | Mise à jour (nom, notes, type, is_private) |
| DELETE | `documents/{id}/` | Suppression (déclenche signal → fichier physique + thumbnails) |
| POST | `documents/upload/` | Upload multipart (magic bytes, normalization, OCR) |
| GET | `documents/by_type/` | Comptage par type |
| GET | `documents/purpose_counts/` | Compte des photos par intention, dont « à trier » |
| GET | `documents/triage/` | Ce que personne n'a trié, **par grappes de session** |
| POST | `documents/set_purpose/` | Pose une intention sur un lot ; n'écrase rien sans `overwrite` |
| POST | `documents/{id}/reprocess_ocr/` | Relancer l'extraction OCR |

Permissions : `IsHouseholdMember` partout. Seul le `created_by` peut changer `is_private` (`views.py:140-144`).

**`is_private` vaut aussi pour l'assistant.** La règle est déclarée une fois, au
registre de `apps/documents/apps.py`
(`PrivacySpec(model=Document, narrow=visible_to_creator)`), et **toutes** les portes
de lecture l'appliquent par `core.visibility.narrow_for` — la liste REST comme les
six chemins du retrieval. Elle ne vivait auparavant
que dans `get_documents_queryset_for_request` : l'`ocr_text` d'une pièce privée était
donc cherchable et citable par tout le foyer via la palette, `search_household`,
`get_entity`, et le contexte ancré d'un projet auquel la pièce était attachée. Détail
du mécanisme et de ce qu'il refuse de faire : `docs/MODULES/agent.md`, section
« Confidentialité ».

### Phase avant/après sur un lien (`DocumentLink.phase`, parcours 20)

- `DocumentLink.phase` : `CharField` (`before` / `during` / `after`, vide = non
  classée). **Contextuel au lien**, pas au document — une même photo peut être
  l'« après » d'un projet sans polluer un autre usage. Générique à tous les types
  liables ; seul l'UI photos des projets l'écrit en V1.
- Écriture via `documents.services` : `link_document(..., phase=)` à l'attache,
  `set_document_phase(entity, document_id, phase)` pour retaguer (valide la phase,
  retourne le nombre de liens mis à jour).
- Exposé par le mixin `DocumentLinkActionsMixin` (monté sur les viewsets d'entités
  liables, ex. `ProjectViewSet`) :
  - `POST {entity}/{id}/attach_document/` accepte `phase` (en plus de `role`/`note`).
  - `POST {entity}/{id}/set_document_phase/` → `{document_id, phase}` (404 si non
    lié, 400 si phase invalide).
- Lecture : `GET /api/documents/documents/?project={id}` (ou `?zone=`/`?linked_to=`)
  renseigne `phase` par document **pour l'entité filtrée** (champ `phase` du
  serializer liste, via le contexte `link_entity_id`). `None` hors contexte.

### Date de prise de vue (`Document.taken_at`, `apps/documents/exif.py`)

La galerie se rangeait par `created_at` — la date d'**ajout dans House**. Une série prise
en juin et importée en juillet apparaissait donc sous « juillet ». `taken_at` porte la
date du déclenchement, lue dans l'EXIF.

- **⚠️ La lecture doit précéder `normalize_image`.** Celui-ci ré-encode en JPEG **sans
  transmettre l'EXIF**, donc il le détruit — pour tout HEIC/HEIF (le défaut iPhone,
  toujours transcodé) et pour toute image dépassant `MAX_DIMENSION` sur son plus grand
  côté, soit l'essentiel des photos réelles. Inverser les deux appels dans
  `views.upload` laisse `taken_at` vide sans qu'aucun test d'upload existant ne s'en
  aperçoive. Régression :
  `documents/tests/test_taken_at.py::TestUploadCapturesTheDate::test_a_LARGE_photo_keeps_its_capture_date_although_the_exif_is_destroyed`
  (vérifié par mutation : c'est le seul test qui tombe).
- **On ne réinjecte volontairement pas l'EXIF dans le fichier stocké.** Ce serait la
  correction symétrique, mais elle réintroduirait les **coordonnées GPS** dans des
  originaux qui n'en portent plus, et il faudrait penser à retirer le tag `Orientation`
  (`exif_transpose` ayant déjà appliqué la rotation aux pixels, le garder ferait pivoter
  l'image une seconde fois). La date partant dans une colonne, la conserver dans le
  fichier n'apporte rien.
- **C'est une colonne, pas une clé `metadata`** : la galerie trie et regroupe dessus, et
  `metadata` doit rester affiché, jamais requêté ni contraint (même mouvement que
  `amount`/`kind`/`supplier` promus sur `Interaction`).
- **`NULL` est un état, pas un zéro.** Une capture d'écran, un scan, une image strippée
  n'ont pas de date de prise. Ne jamais y écrire `created_at` en repli : ça fabriquerait
  une donnée fausse indistinguable d'une vraie. Le repli est à la **lecture**
  (`COALESCE`), là où on peut encore dire laquelle des deux on affiche — d'où
  `photos.takenOn` vs `photos.addedOn` dans la visionneuse.
- **`taken_at` est read-only dans le serializer.** L'exposer en écriture permettrait de
  contredire l'EXIF par un PATCH, et le tri cesserait de vouloir dire quelque chose.
- **L'EXIF est une heure locale sans fuseau.** `OffsetTimeOriginal` (EXIF 2.31+) le donne
  quand il est là ; sinon on interprète dans le **fuseau du foyer** (`core.timezones`) —
  le choix le moins faux, et le seul cohérent avec la règle « le fuseau du foyer, et rien
  d'autre ». Conséquence assumée : le même fichier importé par deux foyers distants ne
  donne pas le même instant absolu.
- `DateTime` (tag 306) est **volontairement ignoré** : c'est la date de *modification*
  du fichier. Sur une photo retouchée elle vaut la date de l'export, et la lire ferait
  passer une donnée fausse pour une date de prise.
- Une date en dehors de `[1900, maintenant + 2 jours]` est rejetée : une pile morte remet
  l'horloge d'un appareil à une date lointaine, et sans borne la photo resterait perchée
  en tête de galerie pour toujours. Un tri faux est pire qu'une date absente.
- **Tri de la galerie** : l'`ordering_fields` expose `effective_date`, annotation
  `COALESCE(taken_at, created_at)` calculée **en SQL** — trier en Python obligerait à
  charger tout le foyer pour afficher une page. Le front demande
  `ordering=-effective_date`, et `grouping.ts::effectiveDate` applique la même règle
  pour les en-têtes de mois : s'ils divergeaient, une photo apparaîtrait sous un en-tête
  « juillet » entre deux photos de juin.

### L'intention d'une photo (`Document.purpose`, parcours 29 lot 2)

Une photo portait trois axes — la zone dit *où*, le lien d'entité dit *sur quoi*,
`DocumentLink.phase` dit *quand dans le chantier*. Aucun ne disait **pourquoi elle
existe**, et c'est la question qui sépare une preuve d'un souvenir : le numéro de série
d'une chaudière, une fissure inquiétante et l'anniversaire d'une fille finissaient au
même endroit, dans le même ordre. Même raisonnement que « le budget est la catégorie »
côté argent : un projet et une zone disent sur quoi porte un euro, jamais de quelle
nature il est.

- **⚠️ Le vide n'est pas `memory`.** Vide = personne n'a regardé (un écart, qui alimente
  la file « À trier ») ; `memory` = quelqu'un a choisi. Les confondre rendrait la file
  aveugle et l'utilisateur croirait avoir rangé. C'est la déclinaison photo de
  `inflow_nature == ""` qui n'est pas `"other"`, et du principe du parcours 26 : *toute
  entité est soit résolue, soit flaggée ; rien ne reste dans un entre-deux silencieux*.
  Régression : `test_photo_purpose.py::TestEmptyIsNotAMemory`.
- **Le marqueur du filtre s'écrit** : `?purpose=untriaged`, jamais `?purpose=` vide, qui
  répond **400** — comme une valeur inconnue. Un paramètre vide qui voudrait dire
  « toutes » ferait afficher la galerie entière sous la pastille « À trier », et le
  compteur d'à côté dirait autre chose que la liste.
- **Aucun backfill, jamais.** Marquer `technical` ce qui est lié à un projet écrirait une
  devinette en base, indistinguable d'un choix de l'utilisateur — ce que `banking.rules`
  interdit (« des valeurs de départ, jamais des vérités »). Tout l'existant part donc
  dans « À trier », et c'est le tri **par grappe** qui rend la contrepartie tenable.
- **Le tri se fait par grappe de session, calculée à la lecture** (`queries.py::
  cluster_sessions`, `SESSION_GAP = 2 h`). Aucune colonne de groupe : un regroupement
  stocké devrait être recalculé à chaque correction de date, et une date de prise de vue
  se corrige. La grappe se calcule sur `effective_date`, **pas** sur la date d'ajout :
  quinze photos envoyées d'un coup depuis la feuille de partage contiennent la chaudière
  de mardi *et* l'anniversaire de samedi — les grouper par envoi reformerait exactement
  le mélange qu'on défait. Régression :
  `test_triage_clusters.py::TestTheTriageEndpointGroupsByCapture`.
- **Un lot n'écrase jamais un choix déjà posé.** `set_purpose` laisse intactes les photos
  qui portent une autre intention et les renvoie dans `skipped` ; écraser est un geste
  explicite (`overwrite: true`). Reposer la **même** intention n'est pas un conflit — un
  lot idempotent ne doit pas se dire à moitié appliqué. Une intention **vide** est
  refusée en lot (« détrier » trente photos serait une destruction de masse déguisée en
  raccourci) mais admise sur une photo, par PATCH ou en recliquant la pastille dans la
  visionneuse. Régression : `test_photo_purpose.py::TestABatchNeverOverwritesAChoice`.
- **Le compteur est un `COUNT(*)`**, servi par `purpose_counts/` — un endpoint à part, et
  non un bloc de la réponse de `triage/` : la galerie affiche ces compteurs en
  permanence, et les obtenir en chargeant une fenêtre de photos ferait payer un écran de
  lecture au prix d'un écran de tri (même exigence que les badges du Contrôle).
- **La file est bornée, et le dit.** `TRIAGE_WINDOW = 500` photos lues, `TRIAGE_CLUSTERS
  = 20` grappes rendues, la grappe de queue d'une fenêtre pleine étant abandonnée
  (peut-être coupée). Le panneau affiche `total` **et** ce qu'il montre : annoncer le
  compte de l'écran ferait croire la file finie. Cette borne remplace la pagination
  curseur du lot 1, pas encore livrée — à réviser quand elle le sera.
- **Propre aux photos** : le serializer et le lot refusent un `purpose` sur un
  `type != 'photo'`, sinon la file se peuplerait de factures qu'elle ne sait pas montrer.
  **Et l'intention ne survit pas au reclassement** : passer une photo en `invoice`
  efface son `purpose` au lieu de bloquer. Les deux chemins diffèrent exprès — *poser*
  une intention sur autre chose qu'une photo est une erreur du client (400), *reclasser*
  est un geste légitime. Sans cet effacement, la facture gardait `purpose='technical'`
  pour toujours : invisible partout (la file et les compteurs filtrent `type='photo'`),
  donc jamais corrigeable — et un état qu'aucun écran ne montre est celui qu'on ne
  rattrape jamais. Même règle que le budget d'un remboursement reclassé en salaire.
  Régression : `test_photo_purpose.py::test_reclassifying_a_photo_drops_the_purpose_it_carried`.
- **Le retrait optimiste d'une suppression porte sur le cache affiché.** La suppression
  est différée de cinq secondes (le temps d'annuler) : en mode tri, ne retirer la photo
  que de `photoKeys.list()` la laissait à l'écran pendant tout ce temps, et un second
  clic partait supprimer un identifiant déjà condamné. `removeFromTriage` (dans
  `hooks.ts`, testé à part) met à jour la file, y compris le `total` et la grappe qui se
  vide.
- Côté front, les trois intentions ont **une seule définition**
  (`ui/src/features/photos/purposes.ts`) : icône, libellé, phrase d'aide. « À trier » n'y
  est délibérément pas — ce n'est pas une quatrième intention, c'est l'absence de choix.

### Pipeline OCR / extraction (`apps/documents/extraction.py`)

- Images (JPEG, PNG, WebP, GIF) → Claude Haiku 4.5 Vision (base64).
- PDF → pypdf (text-based uniquement — PDFs scannés renvoient `pypdf_empty`).
- Fail-soft : tout échec → `("", "skipped")`. Le doc est toujours créé et utilisable.
- Méthodes retournées : `vision_haiku`, `vision_empty`, `pypdf`, `pypdf_empty`, `skipped`.
- HEIC/HEIF → normalisé en JPEG avant extraction (`image_processing.py`), resize si > 2000px.
- Photos (`type='photo'`) : pipeline thumbnails (Pillow) à la place de l'OCR (`views.py:274-277`).

### Sécurité fichiers (`apps/core/views_media.py`, `apps/core/file_validation.py`)

- Upload : magic bytes validés côté serveur via `validate_upload()` — le `Content-Type` client est ignoré (`file_validation.py:65-73`).
- Taille max : 20 MB (`DOCUMENT_MAX_SIZE`).
- Accès media : `serve_protected_media` vérifie l'appartenance au household avant de servir. En prod : `X-Accel-Redirect` → Nginx. Privacy : 403 si `is_private=True` et non-uploader (`views_media.py:41-43`).
- Pas d'URL signée / temporaire — accès direct via `/media/{file_path}` protégé par le middleware Django.
- Path traversal : `get_valid_filename()` à la construction du chemin (`models.py:92`) et extraction de `Path(filename).name` (pas de sous-dossiers depuis le client).

### Cleanup intégrité

- Signal `post_delete` sur `Document` → supprime le fichier physique + les thumbnails (`signals.py:9-21`). Couvre aussi les QuerySet.delete() bulks (post_delete est bien déclenché par Django pour les M2M cascade).
- Si la création DB échoue après `default_storage.save`, le fichier physique est supprimé dans le `except` (`views.py:269-272`).
- Pas de commande de cleanup pour fichiers orphelins sur le storage (fichiers sans `Document` en base).

### Commandes de gestion

- `extract_documents_text` : backfill OCR sur documents existants. Options : `--household`, `--force`, `--type`, `--limit`, `--include-photos`, `--dry-run`.
- `regenerate_photo_thumbnails` : backfill thumbnails.
- `backfill_photo_taken_at` : relit l'EXIF des fichiers stockés dans `Document.taken_at`. Options : `--household`, `--force`, `--dry-run`. **Rapporte combien de photos restent sans date récupérable** — pour celles dont l'EXIF a été détruit au ré-encodage de l'upload, il n'y a rien à retrouver, et un compteur qui n'annoncerait que ses succès laisserait croire la galerie triable de bout en bout.
- `download_supabase_bucket_files` : migration legacy depuis Supabase storage.

---

### Envoyer des photos depuis un téléphone

Deux chemins, et ils ne coûtent pas la même chose — l'asymétrie vient de Safari, qui
ne prend pas en charge le *Web Share Target*, pas de House.

| | iOS | Android |
|---|---|---|
| Mécanisme | Raccourci Shortcuts | `share_target` du manifeste PWA |
| Authentification | Jeton d'appareil (`docs/MODULES/accounts.md`) | La session existante |
| Installation | Importer un raccourci, coller un jeton | Installer la PWA |
| Serveur | — | — (aucun code spécifique) |

**Android — pourquoi la page téléverse et pas le service worker.** Le partage
système envoie un POST multipart sur `/app/photos/share`. Le service worker
l'intercepte (`templates/sw.js`), car sans interception la requête part au réseau
comme un chargement de page et le SPA ne voit rien. Mais **un service worker ne peut
pas lire `localStorage`**, où vit le jeton du SPA : il ne peut donc pas fabriquer
l'en-tête `Authorization` et ne doit **pas** tenter l'envoi. Il met les fichiers
dans un cache, redirige en 303, et `features/photos/SharePage.tsx` — qui, elle, lit
`localStorage` — téléverse. Tenter l'envoi depuis le worker donne des 401 qu'on
cherche longtemps.

Le cache de partage est **consommé** à la lecture (`features/photos/sharedFiles.ts`) :
sans ça un simple rechargement renverrait le même lot, en doublons. Régression :
`sharedFiles.test.ts`.

#### L'aide vit dans l'app, pas seulement dans le dépôt

L'écran *Réglages → Appareils* explique la marche à suivre **selon l'appareil qui le
lit** (`devicePlatform()`), et le guide Photos des tutoriels porte la même étape.

Sans ça, l'écran livrait un jeton sans dire quoi en faire, et la seule explication
vivait dans `docs/` — que personne d'autre que nous n'ouvre. La fonctionnalité
existait sans être trouvable. Trois publics, trois réponses différentes, et aucun
moyen pour l'utilisateur de deviner laquelle est la sienne :

| Lecteur | Ce qu'on lui dit |
|---|---|
| Android | Rien à configurer — installer l'app suffit, le jeton ne le concerne pas |
| iOS | Les trois étapes, et les deux pièges (corps `Form`, champ `type`) |
| Ordinateur | Cet écran sert à connecter un téléphone, ouvrez-le depuis le vôtre |

Afficher les trois reviendrait à n'en afficher aucune. Régression :
`ui/src/features/settings/components/DevicesSection.test.tsx`.

#### Le raccourci iOS, avec un jeton

Deux actions, contre quatre avec l'authentification par mot de passe — et surtout
**plus aucun parsing JSON**, qui est ce qui cassait le plus souvent au montage
manuel :

1. `Repeat with Each` sur **Shortcut Input**
2. `Get Contents of URL` → `https://<instance>/api/documents/documents/upload/`
   - `Method` : `POST`
   - `Headers` : `Authorization` = `Device <jeton>`
   - `Request Body` : **Form** (jamais JSON — c'est lui qui transporte le fichier)
     - `file` → type **File** → *Repeat Item*
     - `type` → **Text** → `photo`

**Le raccourci se distribue déjà construit.** Le monter à la main prend une
quarantaine de minutes et se trompe cinq fois : personne ne le refera. Il se publie
par lien iCloud et pose ses **Import Questions** à l'installation — l'adresse de
l'instance et le jeton. Le domaine ne doit **pas** être codé en dur : il change d'un
foyer auto-hébergé à l'autre.

⚠️ **Le lien iCloud se crée depuis un iPhone**, il ne peut pas être produit par le
dépôt. C'est le seul livrable de ce mécanisme qui vit hors du code — et c'est
précisément pourquoi il ne doit être qu'un **confort, jamais un prérequis** : un
lien iCloud est attaché à un compte personnel, et une installation auto-hébergée ne
peut pas dépendre du compte de l'auteur. La recette complète vit donc en anglais
dans `docs/self-hosting/sending-photos-from-your-phone.md` ; celui qui a le lien
gagne deux minutes, celui qui ne l'a pas reconstruit le raccourci en cinq.

**`type=photo` n'est pas cosmétique.** Il décide de la branche serveur : vignettes
pour une photo, **OCR de vision** pour un document. L'oublier fait décrire par un
modèle payant une image sans texte, et la photo n'apparaît pas dans la galerie.
Constaté en production le 2026-08-03 en montant le raccourci iOS à la main.

## Notes / décisions produit

- **Architecture "double relation" interaction → document** : la FK `Document.interaction` est une relation legacy (migration Supabase). Le vrai lien M2M est `InteractionDocument`. Les deux coexistent — `legacy_interaction` est exposé dans le sérialiseur pour ne pas casser les clients. Ne pas supprimer la FK sans migration de données (`apps/documents/models.py:69-76`).
- **Photos vs Documents** : `type='photo'` a une logique d'affichage séparée côté frontend (`fetchDocuments` filtre les photos, `fetchPhotoDocuments` les isole — `lib/api/documents.ts:92`). La séparation complète en deux modules distincts est en cours de réflexion (issue #39, label `idea`).
- **OCR synchrone** : l'extraction tourne dans le thread de la requête HTTP d'upload. Sur un PDF lourd ou une image haute résolution, cela peut allonger la réponse. Pas de queue (Celery, etc.) actuellement — décision assumée de garder simple en phase solo.
- **Pas de pagination** : `DocumentViewSet` n'a pas de `pagination_class`. La liste complète est chargée d'un coup. À surveiller dès que le nombre de documents croît (pas de `PAGE_SIZE` dans `REST_FRAMEWORK` settings non plus — `config/settings/base.py:145`).
- **Lien au module agent/RAG** : `apps/agent/` n'existe pas encore. Le champ `Interaction.enriched_text` (`interactions/models.py:78`) est prévu pour un futur pipeline qui consolidera le texte OCR des documents. Les documents ne sont pas encore indexés dans un moteur de recherche vectoriel.
- **Le lot est côté client, l'endpoint reste par fichier.** `DocumentUploadDialog`
  (le composant partagé par les **cinq** surfaces d'upload : galerie Photos, onglet
  Photos d'une entité, page Documents, onglet Documents, fiche dépense) accepte
  plusieurs fichiers et les envoie **séquentiellement** à `POST /upload/`, un par
  requête. Trois raisons de ne pas fusionner en une requête de lot : l'endpoint
  normalise l'image, lit l'EXIF et lance l'OCR **synchrone** (note ci-dessus), donc
  un lot serait une requête longue ; un échec au milieu serait tout-ou-rien ; et le
  parallélisme ferait attendre le foyer sur son propre import. Conséquences à
  préserver : `onSaved` est appelé **une fois par document créé** — c'est ce qui
  laisse les appelants rattacher/invalider sans rien changer — et les fichiers
  **déjà arrivés** sont mémorisés, pour qu'une relance après échec ne les recrée
  pas en doublon. Le champ « nom » ne s'affiche qu'à un seul fichier : appliqué à
  un lot, il donnerait vingt documents homonymes. Régressions :
  `ui/src/features/documents/DocumentUploadDialog.test.tsx` et
  `e2e/project-detail-tabs.spec.ts` (le `multiple` d'un `<input type="file">` ne
  s'atteste que dans un vrai navigateur — jsdom pose `input.files` à la main).
- **Upload multipart via action custom** : l'endpoint `POST /upload/` est une action custom séparée du `POST documents/` classique. Le `POST documents/` accepte un `file_path` manuel (cas import legacy). Les deux coexistent — ne pas confondre dans les tests ou le client.
- Parcours 02 cadré dans `docs/parcours/PARCOURS_02_TRAITER_UN_DOCUMENT_ENTRANT_ET_LE_RELIER_AU_BON_CONTEXTE.md` et `PARCOURS_02_BACKLOG_TECHNIQUE.md`.

### Envoyer des photos depuis un iPhone (feuille de partage)

**Aucun code ne le permet — c'est déjà possible**, et c'est utile de savoir
pourquoi : `ActiveHouseholdMiddleware` résout le foyer depuis
`user.active_household_id`, **jamais depuis un en-tête**. Un client authentifié
n'a donc rien d'autre à fournir que son jeton pour que `POST /upload/` sache dans
quel foyer écrire. Sur iOS, la seule route est un raccourci Shortcuts : Safari ne
prend pas en charge le *Web Share Target*, donc une PWA installée sur iPhone ne
peut pas recevoir de contenu partagé (sur Android, un `share_target` dans le
manifeste suffirait, sans jeton, la session étant déjà là).

Le raccourci, dans l'ordre : `POST /api/auth/token/` en JSON (`email` +
`password` — `USERNAME_FIELD` est l'email), on en tire la clé `access`, puis pour
chaque image de l'entrée un `POST /api/documents/documents/upload/` avec
`Authorization: Bearer …`, **corps de type Formulaire** (multipart), champs
`file` et `type=photo`. Pas de champ `name` : chaque photo garde le nom de son
fichier, même règle que le lot multiple.

Deux points à ne pas perdre :

- **`type=photo` n'est pas cosmétique** : `fetchDocuments` filtre les photos hors
  de la page Documents et `fetchPhotoDocuments` les isole dans la galerie. Sans
  lui, la photo atterrit dans les documents.
- **L'access token vit 15 minutes**, donc le raccourci se réauthentifie à chaque
  exécution et stocke les identifiants en clair. C'est la faiblesse assumée de
  cette version, et la seule raison d'être du jeton d'appareil qui doit la
  remplacer — un jeton révocable, sans mot de passe sur le téléphone.
- **⚠️ Le piège du jeton d'appareil, à connaître avant de l'implémenter** :
  `ActiveHouseholdMiddleware` s'exécute **avant** l'authentification DRF et ne
  connaît que le JWT, la session Django et le `_force_auth_user` des tests. Une
  simple classe d'authentification supplémentaire authentifierait l'utilisateur
  au niveau de la vue, mais le middleware aurait déjà posé `request.household =
  None` — et l'upload répondrait « A valid household context is required ». Le
  jeton d'appareil se pose donc **aux deux endroits**, pas seulement dans
  `DEFAULT_AUTHENTICATION_CLASSES`.
- **À vérifier sur un vrai iPhone, jamais à supposer** : que les Raccourcis
  préservent l'EXIF. Si `taken_at` revient vide, la galerie se range par date
  d'import et non par date de prise de vue, et la date devra voyager comme champ
  à part. Le contrôle se fait à l'œil : une photo envoyée doit afficher « Prise
  le … », pas seulement « Ajoutée le … ».

---

## Violations CLAUDE.md identifiées (code en place)

- `defaultValue` interdit dans `t()` — 3 occurrences actives :
  - `DocumentsPage.tsx:73` : `t(\`documents.type.${v}\`, { defaultValue: v })`
  - `DocumentCard.tsx:52` : `t(\`documents.type.${doc.type}\`, { defaultValue: doc.type })`
  - `DocumentEditDialog.tsx:61` : `t(\`documents.type.${v}\`, { defaultValue: v })`
- Couleur hardcodée dans le skeleton du `DocumentsPage.tsx:143` : `bg-slate-100` → devrait être `bg-muted`.
- Couleurs hardcodées dans `DocumentCard.tsx` :
  - `text-blue-500 dark:text-blue-400` (icône fichier, ligne 34) — pas de token équivalent dans le design system, mais à aligner.
  - `border-amber-200 bg-amber-50 text-amber-700` (badge "sans contexte", ligne 76) — à passer en token ou composant Badge.
