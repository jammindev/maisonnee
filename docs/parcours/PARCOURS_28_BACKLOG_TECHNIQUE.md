# Parcours 28 — Backlog technique : ouvrir Maisonnée

> **État au 2026-08-22** — lots 0, 1, 1ter, 2, 3, 4, 5, 6 et 8 livrés ; lot 1bis
> partiel ; **il ne reste que le lot 7** (recette pilote).
> Quatre releases publiées — `v0.1.0` (2026-08-04), `v0.2.0` (08-13), `v0.3.0`
> (08-15), **`v0.4.0` (08-18)** — et l'image est **publique depuis le 2026-08-13** :
> `docker pull ghcr.io/jammindev/maisonnee:latest` répond sans aucun compte, en
> `amd64` et `arm64`. Les trois lignes du README sont vraies.
> **Une vitrine publique existe depuis le 2026-08-18** :
> [demo.maisonnee.jammin-dev.com](https://demo.maisonnee.jammin-dev.com) — voir
> plus bas, c'est devenu un **prérequis du lot 7**.
>
> ⚠️ **Trois issues de lot sont livrées sans être fermées** (#491 lot 5, #492 lot 6,
> #494 lot 8), chacune avec son reliquat nommé dans sa section. Ce tableau est donc
> la source de vérité, pas l'état des issues — et c'est un défaut à corriger, pas
> une convention : un lot dont l'issue reste ouverte se relit comme un lot en cours.
> Chantier technique transverse : rendre le projet publiable, installable par un
> tiers et défendable une fois exposé. Aucune feature métier.

Doc produit : [PARCOURS_28_OUVRIR_MAISONNEE.md](./PARCOURS_28_OUVRIR_MAISONNEE.md)
Fiches concept (le cours) : [docs/fiches/AUTO_HEBERGEMENT.md](../fiches/AUTO_HEBERGEMENT.md)
et [docs/fiches/DISTRIBUTION_ET_REGISTRE.md](../fiches/DISTRIBUTION_ET_REGISTRE.md)
Socle dont on hérite : `DEPLOYMENT.md` (§3.4 résilience du proxy), `CLAUDE.md`
(§ Déploiement), `nginx/test-resilience.sh`, `apps/core/management/commands/seed_demo_data.py`

## Tableau de bord

Issue ombrelle : **#485**

| Lot | Sujet | Statut | Issue |
|---|---|---|---|
| 0 | Hygiène du dépôt + durcissement CI (**urgent — dépôt déjà public**) | ✅ Livré (PR #495) | #486 |
| 1 | Durcissement multi-tenant + test générique d'isolation (**bloquant**) | ✅ Livré (PR #497) | #487 |
| 1bis | Isolation **en écriture** : FK de serializer ✅ (PR #499) ; actions custom + 26 `APIView` restants | 🔄 Partiel | #498 |
| 1ter | Débit et inscription : plancher global, cache partagé, `ALLOW_OPEN_SIGNUP`, mot de passe validé | ✅ Livré | — |
| 2 | `docker compose up` — première installation en une commande | ✅ Livré | #488 |
| 3 | Dégradation propre sans service tiers (IA, SMTP, push, Telegram) | ✅ Livré | #489 |
| 4 | LICENSE AGPL-3.0 + gouvernance (CONTRIBUTING, SECURITY, DCO, templates) | ✅ Livré (PR #496) | #490 |
| 5 | Exploitation par un tiers : sauvegarde, restauration testée, mises à jour, releases | ✅ Livré (PR #549, #561) — `v0.1.0` publiée | #491 |
| 6 | Façade Maisonnée : README bilingue, captures, identité | ✅ Livré (PR #572, #574) — **sans le GIF d'import** (voir lot 6) | #492 |
| 7 | Recette pilote (5-10 foyers) puis annonce et mesure de la rétention | ⬜ À faire — **débloqué** depuis la publication de l'image | #493 |
| 8 | Identité visuelle : logo, palette de marque, icônes, aperçu social | ✅ Livré (PR #571, #573, #581) — reste l'upload de l'aperçu social (clic GitHub) | #494 |

> Le lot 8 porte un numéro tardif mais s'exécute **avant le lot 6** : les captures
> d'écran contiennent le logo et les icônes.

### La vitrine — un prérequis du lot 7 qui n'était dans aucun lot

Montée le **2026-08-18**, hors backlog : `demo.maisonnee.jammin-dev.com`, un compte
partagé sur un foyer fictif, remis à zéro chaque nuit à 4 h. Infra :
`deploy/demo/` (compose + `reset.sh` + unités systemd), doc dans `DEPLOYMENT.md`
§ 11. Elle tourne sur le **paquet publié**, jamais sur les sources — donc elle ne
profite d'un correctif qu'après un **tag**.

Elle n'appartient à aucun lot et pourtant elle en conditionne un, parce que le
parcours 28 avait laissé un angle mort : **celui qui installe n'est jamais celui
qui décide si ça sert.** Les lots 2 à 6 rendent le produit installable et
présentable à un *développeur* ; ils ne donnent rien à montrer à son foyer. Or le
lot 7 exige « au moins un foyer où un non-développeur se sert de l'app » — un
critère qu'on ne peut pas recruter avec des captures d'écran.

D'où la place dans la séquence : **la vitrine se répare avant qu'on recrute**, pas
après. Une démo à moitié vide dépense le « seul coup par communauté » du lot 7 sans
rien apprendre.

Ce que ça a déjà appris, et qui vaut plus que la vitrine elle-même : le 2026-08-19,
**cinq des 22 entrées de la sidebar** n'avaient rien à afficher en production
(Électricité, Verger, Chasse au trésor, Documents, Photos) alors que le test censé
le garantir était **vert** — sa liste de modèles était écrite à la main et se
décrivait elle-même. Corrigé en dérivant la couverture de `PINNABLE_MODULES`
(PR #649). La leçon est dans `CLAUDE.md` § « Deux espaces » : un garde-fou se
dérive du registre, jamais de ce qu'il a sous la main.

## Flow cible

Le parcours d'un inconnu, de bout en bout, après ce chantier :

1. Il tombe sur le dépôt (r/selfhosted, awesome-selfhosted, un lien) et voit
   **une capture avant une ligne de texte technique**.
2. Il copie trois lignes : `curl -O .../docker-compose.yml`, `docker compose up`,
   `open localhost:8000`. Aucun venv, aucun `npm`, aucune clé à souscrire.
3. Il arrive sur un foyer de démonstration pré-rempli (« Famille Mercier ») et
   **clique dans un produit** au lieu de lire une promesse.
4. Il crée son propre foyer, invite son conjoint par **lien copiable** (sans SMTP),
   importe un relevé bancaire, le ventile.
5. Les capacités qu'il n'a pas — assistant, récap, recherche sémantique, push —
   sont **visiblement indisponibles avec le moyen de les activer**, jamais cassées
   ni silencieuses.
6. Il met à jour d'un `docker compose pull && up -d`, sauvegarde d'une commande, et
   sait comment **restaurer** parce que c'est écrit et vérifié.

## Décisions de cadrage (toutes tranchées)

- **Nom** : *Maisonnée* en façade (dépôt, README, UI, manifeste PWA, e-mails,
  image Docker) ; `house` conservé dans les paquets Python, la base et les
  settings. Pas de renommage transverse.
- **Licence** : **AGPL-3.0-only**, copyright détenu par l'auteur seul → l'option
  « hébergement payant » reste ouverte sans relicenciement.
- **Contributions** : **DCO** (`Signed-off-by`), pas de CLA.
- **Dépôt** : `jammindev/house` est **déjà public** (depuis le 2025-09-21, 0★, 0
  fork, aucune licence). On ne bascule donc rien : on assume l'exposition
  existante et on choisit **quand annoncer**. Historique conservé (778 commits,
  aucun secret ni média jamais commité) — après scan de secrets sur *tout*
  l'historique, pas seulement l'arbre courant. Corollaire : le lot 0 et le lot 4
  ne sont pas des préparatifs, ce sont des **écarts ouverts aujourd'hui**.
- **Distribution** : image **`ghcr.io`** multi-arch **amd64 + arm64** (Raspberry Pi,
  Synology, N100) publiée par la CI sur tag. Un self-hoster ne construit pas
  l'image.
- **Base de données** : PostgreSQL uniquement (`pgvector/pgvector:pg16`, déjà
  requis par le parcours 21), embarqué dans le compose. Pas de support SQLite en
  production — il n'a jamais été testé hors CI.
- **Reverse proxy** : nginx inclus dans le compose, **mais** le port applicatif
  reste exposable pour qui a déjà Traefik ou Caddy. Pas de gestion de certificat
  intégrée en V1 (documentée, pas automatisée).
- **Secrets** : `SECRET_KEY` **généré au premier démarrage** et persisté, jamais
  réclamé à l'utilisateur.
- **Langue** : façade bilingue FR/EN (README, `CONTRIBUTING`, `SECURITY`, modèles
  d'issue) ; code, commentaires et `docs/` restent en **français**, et
  `CONTRIBUTING` le **déclare** au lieu de le cacher. Mesuré : le code est déjà
  majoritairement anglais, le français ne coûte qu'aux contributeurs — pas aux
  utilisateurs, qui sont l'objectif de V1. Détail et chiffres : doc produit,
  section « La langue ».
- **Contenu personnel** : audité le 2026-07-31 → **232 issues, 0 image, 0 donnée
  personnelle** (8 remontées, 8 faux positifs sur le mot « adresse »). Question
  close : elle ne justifie pas un dépôt neuf.
- **Pas de télémétrie**, pas de démo en ligne (voir doc produit, § différé).
- **Le déploiement de l'auteur est intouchable.** Le VPS, `docker-compose.prod.yml`,
  le job `deploy`, la séquence `--no-deps`, la migration sur conteneur jetable
  avant bascule et `nginx/test-resilience.sh` **restent tels quels**. Le
  self-hosting s'ajoute **à côté**, il ne remplace rien. Ce que chaque lot a le
  droit de faire à la prod :

  | Lot | Effet sur le déploiement existant |
  |---|---|
  | 0 (CI) | ⚠️ **modifie la garde du job `deploy`** — le seul lot à risque, à vérifier sur un vrai push |
  | 1 (isolation) | code applicatif ; `DEBUG`/`ALLOWED_HOSTS` durcis → vérifier le `.env` de prod avant de livrer |
  | 2 (compose) | **aucun** — nouveau `docker-compose.yml` à côté, `Dockerfile` inchangé |
  | 3 (capacités) | additif (nouvel endpoint, lien d'invitation) |
  | 4 (licence) | aucun, sauf un lien « source » dans l'UI |
  | 5 (exploitation) | `backup_db.sh` généralisé (tes options actuelles conservées) ; `DEPLOYMENT.md` **reste**, il est simplement renommé « le déploiement de l'auteur » |
  | 6 / 8 (façade, logo) | cosmétique, visible sur ta prod (nom, icônes, manifeste) |

- **Annonce publique** (premier lien posté quelque part) : après les lots 0→6,
  jamais avant. Les lots 1 (isolation) et 4 (licence) sont **bloquants** au sens
  strict ; les lots 0 et 4 se traitent **tout de suite**, hors séquence.

---

## Lot 0 — Hygiène du dépôt + durcissement CI (#486) — **urgent**

**But.** Faire en sorte que l'exposition publique — **déjà effective depuis le
2025-09-21** — n'offre rien d'involontaire, ni donnée, ni ressource de calcul. Le
dépôt est propre à 90 % ; ce lot ferme les 10 % restants et vérifie la totalité de
l'historique plutôt que de la supposer.

Ce lot ne prépare pas une ouverture future : il corrige des écarts **ouverts
aujourd'hui**. À faire en premier, indépendamment du reste du parcours.

Deux risques concrets déjà identifiés, tous deux liés à la CI plutôt qu'au code :

- le job `deploy` de `ci.yml` tourne sur un runner **`self-hosted`** — sur un dépôt
  public, un runner self-hosted qui exécute du code de PR est la faille classique.
  Il est aujourd'hui gardé par `if: github.ref == 'refs/heads/main' && push`, ce
  qui est correct mais implicite ; il faut le rendre explicite et le vérifier ;

  > **Audit du 2026-07-31 — la structure est déjà saine, rien à refondre.** Un
  > seul job est `self-hosted` (`deploy`) ; `backend`, `frontend` et `proxy` sont
  > sur `ubuntu-latest`. Une PR de fork est un `pull_request`, donc `deploy` est
  > sauté et **le runner ne prend jamais le job**. Aucun `pull_request_target`
  > (le déclencheur qui exécuterait du code de fork avec les secrets) nulle part.
  > `default_workflow_permissions` vaut déjà `read`.

  Restent quatre réglages de dépôt, tous en clics, aucun code :

  | Réglage | Aujourd'hui | Cible |
  |---|---|---|
  | Approbation des workflows de fork | `first_time_contributors` | **`all_external_contributors`** — sinon la 2ᵉ PR d'un contributeur tourne sans validation |
  | `allowed_actions` | `all` | `selected` (GitHub + liste explicite) |
  | `sha_pinning_required` | `false` | **`true`** — un tag d'action peut être déplacé sous toi |
  | Protection de `main` | `enforce_admins: false`, 0 review requise | à assumer explicitement (voir ci-dessous) |

  > ⚠️ **Le vrai risque n'est pas technique, il est social.** `deploy` s'exécute
  > sur le VPS dès qu'un push atterrit sur `main`, et la protection de branche est
  > décorative (`enforce_admins: false`). Donc **donner un accès write, c'est
  > donner un shell sur le VPS**. Sans objet tant que l'auteur est seul. Règle à
  > tenir : les contributions extérieures passent par **fork + PR**, jamais par un
  > accès write. Et si un contributeur régulier devait un jour obtenir les droits,
  > il faut **d'abord sortir le deploy du runner** — un VPS qui *tire* (webhook +
  > `git pull` côté serveur) au lieu d'un GitHub qui *pousse* supprime la classe
  > entière de problèmes.
- `claude.yml` déclenche sur `issue_comment` contenant `@claude` avec
  `secrets.CLAUDE_CODE_OAUTH_TOKEN` : sur un dépôt public, **n'importe qui** peut
  consommer le quota Claude de l'auteur en commentant.

**Fichiers**

- `.gitignore` — ajouter `coverage.json`, `issues/`, `playwright-report/`,
  `.claude/worktrees/`
- `git rm --cached coverage.json issues/tasks.md` (fichiers suivis à tort ;
  contenu conservé localement)
- `.github/agents/`, `.github/prompts/` — supprimer les gabarits *speckit*
  inutilisés (19 fichiers) : ils décrivent un workflow qui n'est pas celui du
  projet et désorientent un contributeur
- `.github/workflows/claude.yml` — restreindre le déclencheur par
  `github.event.comment.author_association` ∈ {OWNER, MEMBER, COLLABORATOR}
- `.github/workflows/claude-code-review.yml` — même garde
- `.github/workflows/ci.yml` — expliciter la garde du job `deploy` (commentaire +
  condition sur `github.repository == '<owner>/<repo>'` pour neutraliser les forks)
- `.github/workflows/secrets-scan.yml` (nouveau) — `gitleaks` sur l'arbre à chaque
  PR
- `docs/journal/2026-XX-XX_parcours-28_audit-historique.md` — trace du scan complet
- Audit ponctuel : `docs/SYNC_CONTACTS_STRUCTURES.md` et
  `docs/journal/2026-03-09_parcours-02_cadrage_initial.md` citent des données
  personnelles réelles (seuls fichiers détectés) → anonymiser ou archiver
- Vérifier `.env.e2e` (suivi ? ignoré ?) et l'absence de valeurs réelles dans
  `.env.example` / `.env.production.example`

**Critères**

1. `gitleaks detect --no-git=false` sur **les 778 commits** ne remonte aucun secret,
   et le rapport est archivé dans `docs/journal/`.
2. `git ls-files` ne contient aucun artefact de build, de couverture ni de note
   personnelle.
3. Une PR ouverte depuis un **fork** exécute `backend`/`frontend`/`proxy` et
   **jamais** `deploy` — vérifié en conditions réelles, pas par lecture.
4. Un `@claude` posté par un compte extérieur ne déclenche aucun workflow.
5. `grep -riE "benjamin|vandamme|<domaine perso>"` sur l'arbre suivi ne renvoie que
   des occurrences volontaires (copyright, `AUTHORS`).
6. Les quatre réglages de dépôt sont posés, et **un deploy réel passe encore**
   après coup — un dépôt bien gardé qui ne déploie plus est une régression, pas
   un durcissement.
7. La règle « aucun accès write à un contributeur tant que le deploy est sur le
   runner » est écrite dans `CONTRIBUTING` (lot 4) — elle protège le VPS, pas le
   code.

---

## Lot 1 — Durcissement multi-tenant + test générique d'isolation (#487)

**But.** Passer d'un scoping qui sépare des membres d'une famille de bonne foi à
un scoping qui résiste à quelqu'un qui cherche à passer à travers — et surtout,
rendre cette propriété **vérifiée en continu** plutôt qu'auditée une fois. C'est le
lot bloquant du parcours.

Le livrable central n'est pas une liste de correctifs : c'est un **test paramétré
sur le routeur DRF** qui, pour chaque endpoint enregistré, crée deux foyers et
vérifie qu'aucune lecture ni écriture ne traverse. Ajouter un endpoint devient
alors un acte couvert par défaut — même mécanique que
`banking.compliance.REGISTRY` (« ajouter un mécanisme à l'argent = ajouter son
détecteur ») et que le test de parité i18n.

**Fichiers**

- `apps/core/tests/test_tenant_isolation.py` (nouveau) — parcourt les routeurs DRF
  (`config/urls.py`), instancie deux foyers via factories, et vérifie
  `list`/`retrieve`/`update`/`destroy` croisés → 404/403. Liste d'exemptions
  **explicite et commentée** pour les endpoints légitimement globaux
  (`releases`, `/health/`, auth)
- `apps/core/permissions.py` — revue de `IsHouseholdMember`, `IsHouseholdOwner`,
  `CanViewPrivateContent` : vérifier que `has_object_permission` est bien atteint
  sur toutes les actions custom (`@action`)
- `apps/interactions/services.py::resolve_allocation_source` — déjà vérifie le
  foyer ; ajouter le test adverse correspondant
- `apps/agent/tools.py`, `apps/agent/writables.py`, `apps/agent/search_api.py` —
  vérifier le scope sur l'adressage `entity_type:id` en **lecture et en écriture**
- `apps/core/views_media.py` — contrôle d'accès sur les fichiers servis
  (documents, avatars, photos) : un chemin deviné ne doit rien rendre
- `apps/households/throttles.py` + `config/settings/base.py` — throttling sur les
  endpoints d'authentification, d'invitation et d'import
- `config/settings/production.py` — revue : `DEBUG=False` non contournable,
  `ALLOWED_HOSTS` obligatoire (échec au démarrage plutôt que `*`), cookies
  `Secure`/`HttpOnly`/`SameSite`, `SECURE_HSTS_*` documentés
- `apps/accounts/` — politique de mot de passe et verrouillage après échecs répétés
- `docs/MODULES/security.md` (nouveau) — modèle de menace, surfaces, exemptions

**Critères**

1. `test_tenant_isolation.py` couvre **tous** les endpoints du routeur ; toute
   exemption porte un commentaire justifiant pourquoi elle est légitime.
2. Le test échoue si on ajoute un viewset non scopé (vérifié en le cassant
   volontairement une fois).
3. Un `/security-review` est passé sur **l'ensemble du dépôt**, pas sur un diff ;
   les conclusions sont tracées et arbitrées une par une.
4. Un fichier de `media/` appartenant au foyer A est inaccessible au foyer B, même
   avec l'URL exacte.
5. `DEBUG=True` en production échoue au démarrage.
6. `SECURITY.md` (lot 4) décrit le canal de signalement — les deux lots se
   rejoignent ici.

---

## Lot 1ter — Débit et inscription : ce qu'un compte peut coûter

**But.** Le lot 1 a démontré qu'un inconnu ne peut pas *lire* le foyer d'un autre.
Il ne disait rien de ce qu'un inconnu peut **dépenser**. Constat fait en préparant
l'ouverture, et c'est un écart ouvert, pas un travail préparatoire : le dépôt est
public depuis le 2025-09-21, `POST /api/accounts/users/` est en `AllowAny`, et
l'instance de l'auteur tourne derrière.

Ce qui était atteignable sans rien savoir de plus que ce que le dépôt publie :

1. **créer un compte** — sans validation de mot de passe (`abc` était accepté :
   `set_password` hache n'importe quoi, et rien n'appelait `validate_password` sur
   ce chemin), sans vérification d'adresse, sans cap de débit ;
2. **dépenser la clé de l'instance** — `EMBEDDING_INDEXING_ENABLED` fait de toute
   écriture d'entité un appel fournisseur, et `documents/upload` déclenche un
   appel de **vision synchrone** par document non-photo. Ni l'un ni l'autre
   n'était borné, parce que `DEFAULT_THROTTLE_CLASSES` n'était pas posé ;
3. **remplir le disque** — 20 Mo par envoi, sans plafond de fréquence.

Mesuré sur `ai_usage_log` en production : un appel `agent_ask` coûte ~0,7 c€
(Sonnet 4.6, 1 531 tokens en entrée, 203 en sortie). Au plafond de l'agent — le
seul qui existait — un compte pouvait déjà brûler ~40 €/jour ; l'OCR et les
embeddings, eux, n'avaient pas de plafond du tout.

**Le défaut le plus coûteux n'était pas l'absence de limite, c'était le cache.**
DRF compte dans `django.core.cache`, qui n'était pas configuré : donc
`LocMemCache`, un compteur **par process**. Avec quatre workers gunicorn, chaque
limite existante valait quatre fois sa valeur affichée — la garde anti-dictionnaire
à « 5/min » en autorisait vingt — et repartait à zéro à chaque deploy. Poser un
plancher sans corriger ça aurait ajouté un compteur qui ment aux trois qui
mentaient déjà.

**Livré**

- `apps/core/throttles.py` (nouveau) — plancher `user_burst` / `user_sustained` /
  `anon`, posé en `DEFAULT_THROTTLE_CLASSES`
- `config/settings/base.py` — `CACHES` en `DatabaseCache` (dans Postgres : déjà
  sauvegardé, pas de RAM en plus, pas de service de plus), tarifs, et
  `ALLOW_OPEN_SIGNUP`
- `apps/core/migrations/0003_cache_table.py` (nouveau) — la table de cache est
  créée par une **migration**, pas par une commande à lancer : sans elle l'API
  entière tombe à la première requête. Le nom de table est passé explicitement,
  sinon `createcachetable` lit `settings.CACHES` et ne crée rien sous les réglages
  de test — une migration décrit un schéma, elle ne lit pas un réglage
- `apps/core/introspection.py` (nouveau) — le parcours du routeur, extrait de
  `test_tenant_isolation` pour être partagé au lieu d'être recopié
- `apps/accounts/permissions.py` (nouveau) — `OpenSignupAllowed`
- `apps/accounts/serializers.py` — `validate_password` à la création **et** à la
  mise à jour
- `apps/accounts/throttles.py` — `signup` (5/h par IP)
- `apps/accounts/views/api.py` — cap et permission sur `create`, refus en **403**
  et non 401 (DRF convertit sinon, à cause du `WWW-Authenticate` de JWT), plus
  `GET /api/accounts/signup-availability/`, public
- `apps/documents/throttles.py` (nouveau) — `document_upload`, `ocr_reprocess`
- `apps/core/tests/test_rate_limits.py` (nouveau) — 12 régressions, **sabotage
  vérifié deux fois** (voir ci-dessous)
- `docs/MODULES/security.md`, `.env.example`

**Deux leçons de méthode, à garder**

1. **Le contrôle « toute portée a un tarif » a d'abord été écrit faux.** Il lisait
   `cls.throttle_classes`, donc ne voyait **aucun** throttle posé par un
   `get_throttles()` par action — c'est-à-dire exactement les trois qu'on venait
   d'ajouter. Retirer le tarif de `document_upload` le laissait vert. Le sabotage
   l'a montré ; une relecture ne l'aurait pas montré.
2. **La découverte du routeur ne pouvait pas s'importer d'un test à l'autre** :
   `apps/core/tests` n'est pas un paquet et ne peut pas le devenir tant que
   `apps/core/tests.py` existe à côté (même situation dans `documents`,
   `households`, `zones`). D'où `core/introspection.py` — un seul parcours, deux
   lectures, plutôt que deux parcours qui divergent.

**Ce que ça ne fait pas** — il n'y a **pas de plafond de dépense**.
`AIUsageLog` observe, il ne coupe pas. Un quota par foyer (stockage et tokens)
reste à faire, et n'est nécessaire que le jour où l'instance héberge des foyers
tiers : c'est l'issue #531 côté stockage.

---

## Lot 2 — `docker compose up` : première installation en une commande (#488)

**But.** Une machine nue avec Docker, trois lignes copiées, une app fonctionnelle
en moins de cinq minutes — sans venv, sans `npm`, sans clé d'API, sans
`SECRET_KEY` à générer soi-même. C'est le lot qui décide si quelqu'un essaie ou
ferme l'onglet.

`docker-compose.prod.yml` existe mais suppose une image construite localement, un
`.env` rempli et des migrations lancées à part par le pipeline de déploiement.

**Fichiers**

- `docker-compose.yml` (nouveau, à la racine) — pile complète : `db`
  (`pgvector/pgvector:pg16`), `web` (image **`ghcr.io/<owner>/maisonnee:latest`**,
  pas `build:`), `nginx`, `scheduler`. Volumes nommés pour `postgres-data` et
  `media-files`. Profil `demo` qui lance `seed_demo_data`
- `scripts/selfhost-init.sh` (nouveau) — génère et persiste `SECRET_KEY` si
  absent, attend la base, applique `migrate` et `collectstatic`, **puis sort**.
  Il est lancé par un service `init` **one-shot** du nouveau
  `docker-compose.yml`, dont `web` dépend
  (`depends_on: init: condition: service_completed_successfully`)
- `Dockerfile` — **surtout pas d'`ENTRYPOINT`** (voir ci-dessous) ; seul le build
  multi-arch est à vérifier

> ⚠️ **Pourquoi un service `init` et pas un `ENTRYPOINT`.** Le `Dockerfile` porte
> une note explicite : *« Pas d'ENTRYPOINT : le CMD reste remplaçable, ce qui
> permet au deploy de lancer `compose run --rm web python manage.py migrate` sur
> l'image neuve — donc de migrer AVANT de basculer le trafic. »* Un entrypoint qui
> migre au démarrage ferait migrer le conteneur `web` en même temps qu'il commence
> à servir, ce qui est exactement l'invariant que le déploiement de l'auteur
> protège (`CLAUDE.md` § Déploiement). Le service `init` donne la même
> installation sans configuration au self-hoster **sans toucher à l'image**, qui
> reste identique pour les deux usages.
- `.env.example` — réduit au strict minimum pour démarrer ; tout le reste passe en
  section « optionnel » clairement séparée
- `apps/core/management/commands/create_admin.py` (nouveau) — création du premier
  compte depuis des variables d'environnement, idempotente
- `apps/tasks/management/commands/seed_demo_data.py` → **déplacée** vers
  `apps/core/management/commands/` (la seed couvre 30 apps, pas les tâches) et
  vérifier qu'elle couvre les modules Argent (relevé bancaire fictif, budgets,
  ventilations) — c'est ce que la démo doit montrer en premier
- `.github/workflows/release.yml` (nouveau) — build multi-arch amd64/arm64 +
  publication `ghcr.io` sur tag `v*`
- `docker-compose.prod.yml` — inchangé (le déploiement de l'auteur ne bouge pas)

> **Livré — trois écarts au plan, tous assumés.**
>
> **① Pas de Nginx dans la pile auto-hébergée.** Le plan en prévoyait un ; il
> aurait fallu monter sa configuration, donc distribuer un dépôt au lieu d'un
> fichier — ou en recopier le contenu dans le compose, c'est-à-dire créer un
> second texte qui dérive du premier. La pile tient en **db + init + web +
> deux schedulers** : whitenoise sert les fichiers statiques (il est déjà dans le
> middleware, la production s'y appuie depuis toujours), et Django sert les
> médias protégés lui-même. Le TLS d'une instance exposée se termine dans le
> reverse proxy de l'hébergeur, qui existe déjà chez tous ceux qui exposent.
>
> **② Un module de réglages, pas des variables dans le compose.**
> `config/settings/selfhost.py` **importe** `production.py` après avoir rempli
> ses défauts. Le durcissement de l'auteur et celui d'un inconnu sont donc le
> même texte, et `test_production_settings.py` continue de surveiller le seul
> fichier qui compte. Un unique bouton facultatif, `MAISONNEE_PUBLIC_URL` : le
> déclarer resserre `ALLOWED_HOSTS` à ce seul hôte et rallume cookies `Secure` et
> HSTS — **la liste d'hôtes se referme au moment exact où l'exposition
> s'élargit**.
>
> **③ Deux défauts trouvés en chemin, réparés ici.** Le mécanisme de service des
> médias se déduisait de `DEBUG` : `DEBUG=False` sans Nginx — la pile
> auto-hébergée exactement — renvoyait une réponse vide portant un
> `X-Accel-Redirect` que personne n'allait interpréter. Il se déclare désormais
> (`PROTECTED_MEDIA_ACCEL`). Et `STATICFILES_STORAGE` ne faisait **rien** depuis
> Django 5.1, qui l'a supprimé au profit de `STORAGES` : le bundle React partait
> brut, 900 Ko par visite froide, masqué en production par le `gzip on` de Nginx.
> Rétabli en brotli au `collectstatic`, donc au build : **215 Ko**.

**Critères**

1. Sur une VM Linux neuve avec Docker seul : `curl -O`, `docker compose up`,
   l'app répond sur `:8000` **sans aucune édition de fichier**.
2. Le profil `demo` donne un foyer rempli où l'onglet Argent montre un relevé
   importé et ventilé.
3. Aucune variable obligatoire n'est demandée avant le premier écran.
4. L'image démarre sur **arm64** (testé sur Raspberry Pi ou émulation `qemu`).
5. `docker compose down && up` conserve les données ; `docker compose pull && up -d`
   applique les migrations tout seul.
6. Le pipeline de déploiement existant (`docker-compose.prod.yml`, job `deploy`,
   `nginx/test-resilience.sh`) reste **vert et inchangé**.

---

## Lot 3 — Dégradation propre sans service tiers (#489)

**But.** Un foyer qui s'auto-héberge n'a ni clé Anthropic, ni Voyage, ni SMTP, ni
VAPID, ni bot Telegram. Aujourd'hui l'app ne plante pas — `agent.service.ask`
renvoie proprement « je ne sais pas » — mais **l'interface promet quand même** ce
qu'elle ne peut pas tenir, et l'utilisateur en conclut que le produit est mauvais
plutôt qu'il lui manque une clé. Une capacité absente doit se **déclarer**.

Un cas est bloquant et non cosmétique : **sans SMTP, inviter un second membre part
dans le vide**, donc le foyer reste à une personne — ce qui vide de son sens un
produit dont l'unité est le foyer.

**Fichiers**

- `apps/app_settings/capabilities.py` (nouveau) — registre des capacités
  optionnelles (`assistant`, `semantic_search`, `recap_ai`, `email`, `push`,
  `telegram`), chacune avec : clé, disponibilité dérivée des settings, libellé i18n
  et lien de documentation. Alimenté depuis `apps.py::ready()` — même modèle que
  `agent.searchables` et `banking.compliance.REGISTRY`
- `apps/app_settings/views.py` — endpoint `GET /api/capabilities/`
- `ui/src/lib/api/capabilities.ts`, `ui/src/features/settings/hooks.ts` — accès +
  hook `useCapabilities()`
- `ui/src/features/agent/`, `ui/src/features/recap/`, `ui/src/features/search/` —
  masquer ou désactiver avec un message actionnable (« nécessite une clé
  Anthropic — voir la doc »), jamais un écran vide
- `apps/households/services.py` + `ui/src/features/households/` — **lien
  d'invitation copiable**, l'e-mail devenant un confort et non le véhicule unique
- `config/settings/base.py` — backend e-mail `console` par défaut hors production
- Locales : `ui/src/locales/{en,fr,de,es}/*.json` — clés `capabilities.*`
- `docs/MODULES/app_settings.md` — documenter le registre
- **`docs/self-hosting/ai-providers.md` (nouveau, anglais)** — la cible du « lien
  de documentation » de chaque capacité. Une clé par section : où l'obtenir, quelle
  variable la porte (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `LLM_PROVIDER`,
  `LLM_TEXT_MODEL`, `EMBEDDING_PROVIDER`…), **ce que l'app fait sans elle**, et
  l'ordre de grandeur du coût mensuel pour un foyer

> **Pourquoi cette page appartient au lot 3 et pas au lot 5.** Le registre de
> capacités promet à chaque écran de dire *comment activer* ce qui manque : sans la
> page, ces liens sont morts le jour où ils sont écrits, et « nécessite une clé
> Anthropic » redevient exactement le mur qu'on voulait supprimer. Le lot 5 (doc
> d'exploitation) arrive après et ne fait que la référencer.

> ⚠️ **Deux pièges à écrire noir sur blanc dans cette page.** ① Changer
> `EMBEDDING_PROVIDER` ou `EMBEDDING_MODEL` **après** un premier indexage impose un
> `backfill_embeddings` complet : la colonne pgvector est figée à
> `EMBEDDING_DIMENSIONS`, et un index mélangeant deux modèles rend la recherche
> sémantique silencieusement fausse (`_check_dimensions` n'attrape que le
> changement de *largeur*, pas le changement de *modèle* à largeur égale).
> ② Les clés se configurent **par instance** (`.env`), jamais par foyer : le `.env`
> **est** le BYOK du self-hoster. Une saisie de clé dans l'interface ferait de
> `get_llm_client()` une décision d'appelant — ce que `apps/agent/llm.py` interdit
> explicitement — et n'a de sens que le jour où quelqu'un héberge des foyers tiers.

> **Livré — trois écarts au plan, tous assumés.**
>
> **① Le point bloquant du lot n'existait déjà plus.** « Sans SMTP, inviter un
> second membre part dans le vide » a été corrigé le 2026-07-29 par le fix #461 :
> `create_invitation` produit un `/join/<token>` que `InvitePanel` copie, et
> `join_with_new_account` fait entrer quelqu'un qui n'a pas de compte. Le lot ne
> l'a donc pas refait — il l'a **documenté** comme la voie normale
> (`ai-providers.md`, section e-mail), parce qu'un chemin qui existe mais que
> personne ne connaît ne rattrape rien.
>
> **② Le récap n'est pas gaté, et c'est le sujet du lot.** Le plan listait
> `features/recap/` parmi les écrans à masquer ; sans clé le récap **sort quand
> même**, avec ses gabarits. Y poser un bandeau « nécessite une clé » aurait
> annoncé cassé ce qui marche — exactement le malentendu qu'on supprime. La
> capacité `recap_ai` se déclare dans la liste des Réglages, là où elle répond à
> la vraie question (« qu'est-ce qui dort ici ? ») sans en inventer une fausse.
>
> **③ Deux définitions trouvées en chemin, ramenées à une.** Telegram avait déjà
> son 503 « channel is not enabled » écrit à la main, et le front du push
> déduisait la configuration d'une **clé publique vide** — un 200 portant une
> réponse que le serveur connaissait déjà, suivi d'un `InvalidAccessError`
> illisible après le clic. Les deux passent par le registre : un état de
> configuration ne peut pas avoir deux définitions.
>
> Défaut réparé au passage : `EMAIL_BACKEND` n'était posé nulle part dans
> `base.py`, donc le défaut de Django (`smtp` sur `localhost:25`) s'appliquait à
> tout module de réglages qui ne le surchargeait pas — un échec au moment de
> l'envoi, loin de l'écran qui l'avait promis.

**Critères**

1. Une pile démarrée **sans aucune clé** ne montre nulle part un écran cassé, un
   spinner infini ou une erreur technique.
2. Chaque capacité indisponible affiche **pourquoi** et **comment l'activer**.
3. Un second membre rejoint un foyer **sans serveur SMTP configuré**.
4. Ajouter une capacité optionnelle = une entrée dans le registre + une clé i18n,
   aucune modification d'écran (vérifié par un test de couverture du registre,
   miroir de `test_global_search.py::TestThePaletteCoversTheRegistry`).
5. Une capacité désactivée n'est pas seulement masquée côté client : l'endpoint
   correspondant répond proprement (409/503 nommé), jamais 500.
6. Chaque capacité du registre porte un lien qui **atteint une section existante**
   de `docs/self-hosting/ai-providers.md` — vérifié par un test, sinon la page et
   le registre dérivent (même raison que la parité des catalogues i18n).
7. En partant d'une pile sans aucune clé, un lecteur active l'assistant **en
   suivant la page seule**, sans lire le code ni `config/settings/base.py`.

---

## Lot 4 — LICENSE AGPL-3.0 + gouvernance (#490)

**But.** Donner le droit d'usage, dire comment contribuer, et ouvrir un canal de
signalement de vulnérabilité — sans lequel une faille se découvre sur Twitter.
Lot court mais bloquant : sans `LICENSE`, personne n'a légalement le droit
d'utiliser le code et `awesome-selfhosted` refuse l'entrée.

**Urgence particulière** : le code est lisible publiquement depuis dix mois *sans
licence*, c'est-à-dire sous « tous droits réservés » par défaut. La situation
actuelle est la plus mauvaise des deux — visible mais inutilisable. À traiter avec
le lot 0, sans attendre le reste du parcours.

**Fichiers**

- `LICENSE` — texte intégral AGPL-3.0
- `AUTHORS` / en-tête de copyright — détenteur unique
- `CONTRIBUTING.md` (EN + `CONTRIBUTING.fr.md`) — DCO `Signed-off-by`, format des
  commits conventionnels (contrat du changelog, déjà tenu — pointer `CLAUDE.md`),
  comment lancer les tests, où lire `docs/fiches/`. **Porte la déclaration de
  langue**, en tête et telle quelle :
  > This project was built for one real household, in French. The interface speaks
  > English, French, German and Spanish; the internal documentation and some code
  > comments are in French. Issues and pull requests in English are welcome.
- `docs/README.en.md` (nouveau) — **le guide anglais de la documentation
  française**. Ce n'est pas une traduction : c'est un **index commenté** qui dit,
  pour chaque famille de docs, de quoi il s'agit et pourquoi ça peut valoir la
  peine d'aller la lire (au traducteur automatique s'il le faut). Il transforme
  « tout est en français » d'un mur en menu. Structure :

  | Where | What it is | Why you may care |
  |---|---|---|
  | `CLAUDE.md` | The project's rulebook. Every rule is tied to a bug that actually happened in production, with the reasoning kept and the name of the regression test that guards it. | The fastest way to understand *why* the code looks like it does — and the file to read before changing anything. |
  | `docs/fiches/` | Concept notes ("the lesson"): RAG, embeddings, idempotent import, self-hosting… Each one states the problem, the concept, how it was applied here, the trade-offs, and **what was rejected and why**. | Background on the non-obvious parts, and the decisions you would otherwise re-litigate. |
  | `docs/parcours/` | One folder per feature effort: a product document (what problem, for whom) and a technical backlog split into deliverable lots. | What is planned, what is deliberately out of scope, and where the current work sits. |
  | `docs/MODULES/` | Status of each Django app: what to fix, what to build, what to improve. | Where to start on a given module. |
  | `docs/journal/` | Dated notes from working sessions — decisions as they were made. | Archaeology: why a choice was made on a given day. |
  | Commit messages & issues | In French, conventional commits (`type(scope): …`). | The changelog is generated from them. |

  Il se termine par l'invitation explicite, dans les termes ci-dessous.
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `SECURITY.md` — versions supportées, canal privé de signalement, délai de réponse
  annoncé et tenable pour une personne seule
- `.github/ISSUE_TEMPLATE/{bug_report,feature_request,config.yml}`,
  `.github/PULL_REQUEST_TEMPLATE.md`
- **L'invitation à traduire**, à poser à la fin de `docs/README.en.md` et à
  reprendre en une ligne dans `CONTRIBUTING.md` :

  > **Translating any of these is a genuinely useful contribution** — probably the
  > easiest way to make a first, meaningful one. Two rules keep it from backfiring:
  > the French file stays the source of truth, and a translation records the date
  > and commit of the version it mirrors. A translation nobody updates is worse
  > than no translation at all: it looks authoritative while being wrong. If one
  > goes stale and you can't refresh it, delete it — that is a contribution too.

  Convention de nommage : `<NOM>.en.md` à côté de l'original (jamais un dossier
  `en/` parallèle, qui rend la dérive invisible).
- `package.json` — champ `license`
- `README.md` — badge et mention de licence
- `ui/src/features/settings/` — mention de licence et lien source dans l'app
  (obligation AGPL §13 : l'utilisateur d'une instance doit pouvoir obtenir la source)

**Critères**

1. `LICENSE` reconnu par GitHub (bandeau « AGPL-3.0 » sur la page du dépôt).
2. L'app expose un lien vers son code source depuis l'interface (conformité §13).
3. `CONTRIBUTING.md` permet à un inconnu de faire tourner les tests sans poser de
   question, et **annonce la langue du projet** dès le premier paragraphe — un
   contributeur ne doit pas le découvrir en ouvrant un fichier.
3bis. `docs/README.en.md` existe et **couvre toutes les familles de docs** : un
   anglophone sait ce que contient chaque dossier sans en lire une ligne, et
   l'invitation à traduire énonce les deux garde-fous (source de vérité française,
   traduction datée — périmée, on la supprime). Le README anglais y renvoie.
4. `SECURITY.md` donne un canal **privé** qui aboutit réellement.
5. Les modèles d'issue reprennent les labels existants (`bug`, `feat`,
   `app:<module>`).

---

## Lot 5 — Exploitation par un tiers : sauvegarde, restauration, mises à jour (#491)

**But.** Quelqu'un va mettre ses relevés bancaires et ses contrats d'assurance
là-dedans. `DEPLOYMENT.md` est excellent mais écrit pour *un* VPS OVH avec son
auteur dans la boucle. Il faut la version pour une machine quelconque — et surtout
une **restauration vérifiée**, parce qu'une sauvegarde jamais restaurée n'est pas
une sauvegarde.

**Fichiers**

- `docs/self-hosting/README.md` (nouveau) — sommaire ; **référence**
  `ai-providers.md`, livré au lot 3, sans le réécrire
- `docs/self-hosting/install.md` — installation, reverse proxy externe
  (Traefik/Caddy) ou nginx inclus, certificat TLS, exposition Internet vs LAN/VPN
- `docs/self-hosting/backup-restore.md` — sauvegarde (base **et** `media/`),
  rotation, procédure de restauration **pas à pas**
- `docs/self-hosting/upgrade.md` — `pull` + `up -d`, migrations automatiques, et la
  règle **« une migration destructive se livre en deux fois »** promue de règle
  interne à **promesse de compatibilité publique** (personne ne contrôle plus quand
  les utilisateurs mettent à jour)
- `docs/self-hosting/troubleshooting.md` — page de maintenance nginx, `/health/`,
  logs, base injoignable
- `backup_db.sh` — généraliser (déjà paramétré : `--out-dir`, `--db-url`,
  `--keep`) + inclure `media/`
- `restore_db.sh` (nouveau) — pendant en lecture, avec confirmation explicite
- `scripts/test-backup-restore.sh` (nouveau) — sauvegarde → base neuve →
  restauration → assertions ; appelé par la CI
- `.github/workflows/ci.yml` — job `backup` (non bloquant pour le deploy, bloquant
  pour une release)
- `DEPLOYMENT.md` — devient explicitement « le déploiement de l'auteur », et
  renvoie vers `docs/self-hosting/` pour tout le reste
- `docs/self-hosting/releases.md` — versionnement semver, tags `v*`, notes de
  release alimentées par `generate_changelog`

> ⚠️ **Un tag `v1.0.0` existe déjà, et il faudra trancher son sort ici.** Il a été
> posé à la main le 2025-10-12 sur un commit de configuration TypeScript sans
> rapport ; **rien ne le lit** (`ChangelogEntry` est adossé au `commit_sha`, pas à
> une version, et `package.json` est resté à `0.0.0`). Publier `v0.1.0` derrière
> lui afficherait donc une release *antérieure* à une release déjà présente — sans
> rien casser (`latest` est posé sur tout tag non-préversion, l'ordre n'intervient
> pas) mais en faisant croire à un lecteur qu'il a raté une étape.
> **Préférence : supprimer `v1.0.0` et partir de `v0.1.0`.** Un tag que personne
> ne lit et qui désigne un commit sans rapport ne vaut pas les explications qu'il
> coûte. Le `0` reste juste : un `1.0` qui ne sait pas se restaurer promet plus
> qu'il ne tient — et c'est précisément ce lot qui lui apprend.
>
> **Reste aussi à lever ici le critère 4 du lot 2** (démarrage arm64) : le
> workflow `release.yml` est écrit mais **n'a jamais été exécuté**, puisqu'il ne se
> déclenche que sur un tag. Le premier tag le prouve ou le casse. Et le paquet
> `ghcr` naît **privé**, même sur un dépôt public : sans un passage manuel en
> public, le `docker compose up` d'un inconnu échoue sur `denied` — ce qui
> ressemble à un bug et n'en est pas un.

> **Partiellement livré — tout sauf le tag.**
>
> **Livré** : `docs/self-hosting/` (README, install, backup-restore, upgrade,
> releases, troubleshooting — en anglais, sans OVH ni domaine ni chemin
> personnel) ; `backup_db.sh --state-dir` ; `restore_db.sh` ;
> `scripts/test-backup-restore.sh` **exécuté pour de vrai** (89 tables, ligne
> témoin, extension `vector`, clé secrète et fichier téléversé restaurés sur une
> base neuve) ; workflow réutilisable `backup-restore.yml` appelé par `ci.yml`
> (informatif) **et** `release.yml` (bloquant, `image` en `needs`) ;
> `DEPLOYMENT.md` annonce en première ligne qu'il décrit le déploiement de
> l'auteur et renvoie vers `docs/self-hosting/`.
>
> **Le tag, posé le 2026-08-04.** `v1.0.0` supprimé (aucune Release ne lui était
> attachée, rien ne le lisait) ; **`v0.1.0`** publiée. Le run a fait ce qu'on lui
> demandait : round-trip de sauvegarde **bloquant** vert, image `amd64` +
> `arm64` poussée, image démarrée, notes de première release générées — et la
> branche « pas de tag antérieur » a bien produit l'intro courte au lieu de
> dérouler huit cents commits.
>
> **Deux défauts trouvés en vérifiant la release, corrigés.** ① Le test de
> démarrage tournait **sans `--platform`** : il ne lançait que l'amd64, et le
> manifeste arm64 partait sans que personne ne l'ait jamais démarré — alors que
> le workflow porte lui-même la phrase « une image qu'on n'a pas démarrée est un
> espoir publié ». Construire ne prouve rien du démarrage : une roue native pour
> la mauvaise architecture ne se voit qu'à l'import. ② Le chemin
> `workflow_dispatch` de republication nommait l'image d'après `github.ref`,
> donc `main` : l'entrée existait pour republier sans re-tagger, et elle ne
> décidait pas du nom.
>
> **Reste un clic, non scriptable** : le paquet `ghcr` naît **privé** même sur un
> dépôt public — GitHub n'expose aucun endpoint REST pour sa visibilité. Sans ce
> passage en public, le `docker compose up` d'un inconnu échoue sur `denied`, ce
> qui ressemble à un bug et n'en est pas un. C'est aussi ce qui bloque la
> vérification finale du critère 4 du lot 2 : tant que le paquet est privé, on ne
> peut pas tirer l'image arm64 depuis l'extérieur pour la démarrer.
>
> **Trois écarts au plan.** ① `backup_db.sh` **n'archive pas** `media/` en
> propre : il archive le **répertoire d'état**, qui porte les fichiers *et* la
> clé secrète. Le volume `maisonnee-state` les réunit exprès (lot 2) — ce qu'une
> sauvegarde doit prendre en plus de la base est ainsi un nom à retenir, pas deux
> à oublier. ② Le job de CI est un **workflow réutilisable**, pas un job copié
> dans `ci.yml` et `release.yml` : deux copies auraient divergé au premier
> changement de format de dump, c'est-à-dire exactement ce que ce job existe pour
> attraper. ③ La doc donne des commandes **`docker compose` autonomes** plutôt
> que d'exiger un clone du dépôt : un auto-hébergeur a téléchargé un fichier, pas
> une arborescence. Les scripts restent l'implémentation testée de la même
> procédure, pour l'auteur et pour la CI ; la convention d'horodatage est
> commune aux deux chemins.

**Critères**

1. Une sauvegarde prise sur une instance A est restaurée sur une instance B neuve,
   et le foyer y est intact — **exécuté**, pas décrit.
2. `scripts/test-backup-restore.sh` tourne en CI et échoue si le format de dump
   change.
3. Un tag `v0.1.0` produit une image `ghcr.io` multi-arch et des notes de release.
4. La doc ne mentionne ni OVH, ni un domaine, ni un chemin personnel.

---

## Lot 6 — Façade Maisonnée : README bilingue, captures, identité (#492)

**But.** C'est la seule page que 95 % des visiteurs verront. Aujourd'hui elle
ouvre sur « backend Django (SSR + API REST) avec mini-SPA React par page via
Vite » — une stack, et personne n'installe une stack. Elle est aussi périmée (elle
annonce deux langues d'interface, il y en a quatre). Et il n'y a **aucune capture
dans tout le dépôt**, alors que c'est le point le plus rentable du parcours.

**Fichiers**

- `README.md` (EN) et `README.fr.md` — dans l'ordre : nom + promesse en une phrase,
  capture principale, ce que ça fait (modules, en langage d'usage), quickstart
  Docker en trois lignes, captures par module, ce que ça **ne** fait **pas**,
  licence, statut du projet
- `docs/assets/screenshots/` (nouveau) — 6 captures depuis le foyer de démo
  (dashboard, Argent/Contrôle, import de relevé, budgets, tâches, assistant) —
  **`seed_demo_data` uniquement**, aucune donnée réelle
- `docs/assets/demo-import.gif` — l'import d'un relevé qui se ventile ; surveiller
  le poids (le dépôt fait 9,7 Mio, ne pas le tripler)
- `ui/public/manifest.webmanifest`, `ui/index.html`, templates Django — nom
  d'affichage *Maisonnée*
- `ui/src/locales/{en,fr,de,es}/*.json` — occurrences du nom produit
- `apps/*/templates/**` + gabarits d'e-mail — expéditeur et signature
- `docs/README.md` — hub documentaire : ajouter l'entrée self-hosting
- `AGENTS.md`, `CLAUDE.md` — mention du nom produit (le code reste `house`)

**Critères**

1. Un visiteur comprend ce que fait le produit **avant** de lire un mot de stack.
2. Les captures sont générées depuis la seed de démo, reproductibles, sans donnée
   réelle.
3. Aucune donnée d'un foyer réel dans `docs/assets/`.
4. Le README dit la vérité sur le périmètre (quatre langues, ce qui manque, l'état
   du projet).
5. `npm run build` + `pytest` restent verts après le renommage de façade.

---

## Lot 7 — Recette pilote, publication, mesure de la rétention (#493)

**But.** On n'a **qu'un seul coup par communauté** : trente personnes qui tombent
sur une installation cassée partent et ne reviennent pas. Ce lot impose la
séquence et définit ce qu'on mesure — la rétention, pas les étoiles.

**Prérequis, à lever avant de recruter le premier foyer.** Ce ne sont pas des
tâches du lot ; ce sont les raisons pour lesquelles il n'a pas encore commencé.

| | Sujet | État |
|---|---|---|
| Vitrine complète | Cinq modules vides en production, corrigés par la PR #649 | ⬜ à merger **et à tagguer** — `reset.sh` tire la dernière release, pas `main` |
| Vitrine crédible | #645 — la démo ne peut pas répondre à la question posée par la capture héros du README | ⬜ |
| CI débloquée | #651 — le scan de secrets lit toutes les branches, donc une branche voisine rougit toutes les PR | ⬜ |
| Isolation en écriture | Lot 1bis (#498) : actions custom + 26 `APIView` non couvertes | 🔄 partiel |

Le dernier est le seul qui soit un risque et non un désagrément : inviter des
inconnus multi-foyers avant que l'isolation en écriture soit tenue par un test
générique, c'est faire porter à des tiers un risque qu'on n'a pas mesuré.

**Fichiers**

- `docs/parcours/PARCOURS_28_RECETTE_PILOTE.md` (nouveau) — protocole : recrutement
  de 5 à 10 foyers, script d'installation à leur donner, questions posées à J+1,
  S+2, S+6, journal des plantages et des corrections
- `docs/journal/2026-XX-XX_parcours-28_retours-pilotes.md` — les retours bruts
- `docs/NEXT_STEPS.md` — arbitrage post-recette (quel module retient, que faire
  ensuite)
- Issues `idea` créées au fil des retours, labellisées `app:<module>`

**Critères**

1. Au moins **cinq foyers** ont installé sans assistance en direct, et chaque
   blocage rencontré a produit une issue.
2. **Au moins un foyer où un non-développeur se sert de l'app** — un ingénieur qui
   teste une soirée n'est pas le même signal qu'une famille qui a rangé ses
   factures dedans.
3. Les canaux publics (r/selfhosted, awesome-selfhosted, Show HN, lobste.rs) ne
   sont ouverts **qu'après** la correction des blocages pilotes.
4. La question « quel module retient ? » reçoit une réponse écrite à S+6, fondée
   sur des conversations et non sur des logs.
5. Cinq utilisateurs ont été interrogés **en direct** — un utilisateur qui
   abandonne ne laisse aucune trace exploitable.
6. **Le jour de l'annonce, les nouvelles issues passent en anglais** : le tracker
   cesse d'être un carnet personnel pour devenir un espace partagé. Les anciennes
   ne se traduisent pas. Règle : `CLAUDE.md` § « Langue ».

---

## Lot 8 — Identité visuelle : logo, palette de marque, icônes (#494)

**But.** Donner un visage à Maisonnée. Aujourd'hui il n'y en a pas : l'icône PWA
est un **placeholder générique** — une maison blanche sur un dégradé bleu, de
qualité clipart — et le `TopBar` n'affiche aucun logo, seulement l'icône `Home` de
lucide.

Ce placeholder dit deux fois le contraire de ce qu'on vient de décider : c'est un
**bâtiment**, alors que *maisonnée* désigne les **gens** ; et il n'y a **rien du
dehors**, alors que le potager et l'élevage arrivent. Un visiteur de
r/selfhosted lit l'icône avant le README.

**Contrainte structurante à ne pas rater** : `ui/src/styles/themes.css` contient
**17 thèmes de couleur** que l'utilisateur choisit (`theme-blue`, `theme-house`,
`theme-emerald`, `theme-midnight`…). La marque ne peut donc **pas** être
`--primary` : elle serait repeinte par le thème du foyer. Le logo doit être
lisible en **monochrome / `currentColor`** dans l'app, et la couleur de marque ne
vit qu'aux endroits que le thème ne touche pas — favicon, icônes PWA, aperçu
social, README.

Deuxième point, moins évident et lié au lot 4 : **l'AGPL ne couvre pas les
marques.** Le code se copie et se modifie librement ; le nom et le logo, non. Ça
se dit une fois, clairement, sinon un fork redistribue une app qui se présente
comme la tienne.

**Fichiers**

- `docs/assets/brand/` (nouveau) — sources vectorielles (`logo.svg`,
  `logo-mark.svg`, `logo-wordmark.svg`), variantes claire/sombre/monochrome
- `docs/assets/brand/README.md` — règles d'usage : ce que l'AGPL couvre (le code)
  et ce qu'elle ne couvre pas (le nom, le logo) ; un fork doit se renommer
- `static/icons/` — remplacer `icon-192.png`, `icon-512.png`,
  `apple-touch-icon.png` ; ajouter une variante `maskable` **distincte** de `any`
  (aujourd'hui les deux `purpose` pointent le même fichier, donc Android rogne
  dans le dessin)
- `templates/manifest.json` — `name`/`short_name` **Maisonnée**, `description`
  (aujourd'hui « Gestionnaire de maison »), `theme_color` et `background_color`
  (aujourd'hui `#f3f4f6`, un gris qui n'est la marque de personne)
- `favicon.ico` / `favicon.svg` + `<link>` dans les templates Django
- `ui/src/components/TopBar.tsx` — composant `<Logo />` en `currentColor`
- `ui/src/design-system/logo.tsx` (nouveau) — mark seul + wordmark, une prop de
  taille, aucun PNG dans le bundle
- `ui/src/styles/themes.css` — **ne pas y toucher** ; si une couleur de marque
  doit exister dans l'app, elle passe par un token dédié (`--brand`) indépendant
  de `--primary`
- Écran de connexion, gabarits d'e-mail, bot Telegram — mêmes marques
- Aperçu social GitHub (1280×640) + description + topics du dépôt
  (`self-hosted`, `household`, `personal-finance`, `homestead`, `django`,
  `react`) — visibilité gratuite, aujourd'hui vide

**Direction à trancher avant de dessiner** (ce lot ne l'impose pas) : qui produit
le dessin — commande à un illustrateur, génération assistée, ou tracé à la main.
Et quel motif : le lot 6 vendra « dedans comme dehors », donc un signe qui tient
les deux (un toit **et** quelque chose qui pousse, un enclos, une clé de voûte)
plutôt qu'une n-ième maison stylisée.

**Critères**

1. Le logo reste lisible à **16 px** et en **une seule couleur** — c'est le test
   qui élimine les dessins trop détaillés.
2. Il ne se casse sur **aucun des 17 thèmes**, en clair comme en sombre.
3. Aucune maison-bâtiment isolée : le signe doit pouvoir accueillir le dehors.
4. Icônes PWA `any` et `maskable` **distinctes** ; l'installation sur Android ne
   rogne rien d'important.
5. `docs/assets/brand/README.md` énonce la règle de marque, et `CONTRIBUTING`
   (#490) y renvoie.
6. L'aperçu social GitHub s'affiche correctement quand on colle le lien du dépôt
   dans Slack, Discord et Mastodon — vérifié en collant réellement.

**Appris en livrant (PR #581) : l'aperçu social est un deuxième exemplaire du
README, donc il dérive.** Le README a été recadré sur l'assistant le 13 août
(PR #574) ; l'image, faite trois heures plus tôt, ouvrait encore sa liste sur
l'argent et s'arrêtait avant « *and a memory that can answer for it* » — la moitié
de la promesse qui distingue le produit. Rien n'a rougi : une image reste une
image valide. Or c'est elle que voit en premier quelqu'un à qui on partage le
lien, avant un README qu'il n'ouvrira peut-être jamais.

D'où trois choses, du même genre que `LOGO_MARK_PATH` vs `logo-mark.svg` :
le texte se corrige dans **`scripts/brand/social-preview.html`** et jamais dans un
éditeur d'image ; `npm run brand:social` réécrit le PNG versionné (une image de
marque qu'on ne sait pas refaire en une commande ne se corrige jamais, on la
garde) ; et `test_brand_assets.py::test_the_social_preview_says_what_the_readme_says`
compare la **source du harnais** au `README.md` — jamais le PNG, un pixel ne
disant pas ce qu'il raconte.

---

## Ordre recommandé d'implémentation

```
Lot 0  (hygiène + CI)          ← court, prérequis absolu à toute exposition
  └─ Lot 1  (isolation)        ← le plus long, non négociable : le démarrer tôt
       └─ Lot 2  (compose)     ← rend le produit testable par un tiers
            └─ Lot 3  (dégradation)  ← ses défauts se découvrent en lançant le lot 2 à nu
                 └─ Lot 4  (licence) ← court, obligatoire avant toute publication
                      └─ Lot 5  (exploitation)
                           └─ Lot 8  (identité visuelle)  ← le logo doit exister avant les captures
                                └─ Lot 6  (façade)  ← les captures montrent l'app finale, logo compris
                                     └─ Vitrine  ← hors lot : ce qu'on montre au foyer, pas au dev
                                          └─ Lot 7  (pilotes → annonce)
```

Les lots 1 et 2 peuvent avancer en parallèle (backend vs packaging). Le lot 6
**doit** venir après le 3 : une capture d'un onglet Assistant qui promet ce qu'il
ne peut pas tenir est une capture à refaire. Il doit aussi venir après le **8**,
pour la même raison : une capture avec l'ancienne icône est une capture à refaire.
Le lot 8 est le seul du parcours qui peut démarrer à tout moment — il ne dépend de
rien.

**Le dépôt étant déjà public**, il n'y a pas de bascule à placer dans cette
séquence. Ce qui se place entre le lot 6 et le lot 7, c'est **l'annonce** — le
premier lien posté quelque part. Les lots 0 et 4, eux, ne s'ordonnancent pas :
ils rattrapent une exposition en cours et passent devant tout le reste.

## Points de vigilance

- **Ne rien casser du déploiement existant.** `docker-compose.prod.yml`, le job
  `deploy` et `nginx/test-resilience.sh` sont un socle éprouvé et testé. Le
  nouveau `docker-compose.yml` s'ajoute **à côté** ; les invariants du §3.4 de
  `DEPLOYMENT.md` (résolveur nginx, montage par répertoire, `--no-deps`, migration
  avant bascule) restent intégralement valables. **Le piège est le confort du
  self-hoster** : tout ce qui rend l'installation « magique » (migrer au
  démarrage, deviner une valeur, se relancer tout seul) est précisément ce que le
  déploiement de l'auteur interdit. La sortie est toujours la même — mettre le
  confort **dans le compose de self-hosting**, jamais dans l'image partagée. Cas
  déjà attrapé au cadrage : l'`ENTRYPOINT` du lot 2, devenu un service `init`.
- **Un seul lot touche vraiment la prod : le 0.** Il modifie la garde du job
  `deploy`. Vérifier sur un push réel qu'un deploy passe encore *avant* de
  considérer le lot livré — un dépôt public bien gardé mais qui ne déploie plus
  est une régression, pas un durcissement.
- **Le lot 1 ne se déclare pas fini sur une relecture.** Un audit est vrai le jour
  où il est fait ; c'est le test générique qui tient la propriété dans le temps.
  S'il n'existe pas, le lot n'est pas livré.
- **Les captures sont un livrable, pas une illustration.** C'est le point le plus
  rentable du parcours ; les bâcler annule le reste.
- **Le poids du dépôt.** 9,7 Mio aujourd'hui, ce qui rend le clone instantané.
  Captures optimisées, GIF borné, aucune vidéo dans le dépôt.
- **La compatibilité devient une promesse publique.** Une fois des instances
  tierces en service, un changement destructif se livre en deux étapes — la règle
  interne du deploy devient une règle de release.
- **La première ligne du README n'est tenue par aucun test.** `docker compose up`
  dépend d'un artefact qui vit **hors du dépôt**, dans un registre au modèle de
  permissions indépendant de celui du dépôt. Deux portes s'y ferment par défaut, et
  aucune n'est visible depuis le code : un paquet `ghcr.io` neuf est **privé** même
  poussé depuis un dépôt public, et une **politique d'organisation** peut interdire
  les paquets publics en grisant le bouton sous un message qui ne nomme ni le
  réglage ni la page (`Org → Settings → Packages → Package creation`). Les deux
  étaient fermées ; l'image n'était donc tirable par personne pendant les neuf
  jours qui ont suivi `v0.1.0`. La vérification se fait **sans être
  authentifié** — `docker logout ghcr.io && docker pull …` — et porte aussi sur ce
  qu'il y a derrière : les deux architectures, et l'URL brute du
  `docker-compose.yml`. Le cours : [DISTRIBUTION_ET_REGISTRE.md](../fiches/DISTRIBUTION_ET_REGISTRE.md).
- **Ne pas confondre installer et revenir.** Le succès du lot 7 se mesure à S+6.
- **La seed de démo est aussi une vitrine.** Elle doit montrer le module Argent en
  premier : c'est la seule partie avec une promesse que personne d'autre ne tient.
  Et depuis qu'elle est **servie publiquement** (2026-08-18), la couverture de la
  sidebar est une propriété à tenir par un test, pas par une relecture : cinq
  modules sont restés vides en production pendant que le contrôle affichait vert.
  Corollaire pour la suite du parcours : **livrer un module et le semer sont un seul
  travail.** Verger et Chasse au trésor sont arrivés le 2026-08-15 et la vitrine ne
  les a jamais montrés — un module qu'on ne peut pas montrer n'existe pas pour le
  lot 7.

## Définition de done technique

1. Aucun secret dans l'arbre **ni dans les 778 commits** (scan archivé).
2. Test générique d'isolation multi-tenant vert sur **tous** les endpoints, avec
   exemptions justifiées ; `/security-review` complet passé et arbitré.
3. `docker compose up` sur machine nue → app fonctionnelle, amd64 **et** arm64.
4. Aucune capacité tierce absente ne produit d'écran cassé ; second membre
   invitable sans SMTP.
5. `LICENSE` AGPL-3.0, `CONTRIBUTING`, `SECURITY`, `CODE_OF_CONDUCT`, templates
   d'issue en place ; lien source exposé dans l'app (AGPL §13).
6. Sauvegarde **et restauration** exécutées de bout en bout, testées en CI.
7. README bilingue orienté promesse + 6 captures + 1 GIF, générés depuis la seed
   — **après** le remplacement du logo et des icônes.
7bis. Logo lisible à 16 px et en monochrome, valide sur les 17 thèmes ; icônes PWA
   `any` et `maskable` distinctes ; aperçu social GitHub en place ; règle de marque
   écrite (l'AGPL ne couvre pas le nom ni le logo).
8. i18n : clés `capabilities.*` présentes dans les **4** catalogues
   (`ui/src/locales/keys.test.ts` vert, aucun `defaultValue`).
9. `npm run lint`, `tsc -b`, `pytest` et la suite E2E verts ; `nginx/test-resilience.sh`
   vert ; pipeline de déploiement inchangé et fonctionnel.
10. Fiches `docs/MODULES/security.md` et `docs/MODULES/app_settings.md`
    créées/à jour ; `docs/MODULES/` inchangé par ailleurs.
11. **Tutoriels** (`/tutorials`) : le parcours d'installation change pour un
    nouvel utilisateur → guide « Bien démarrer » revu, dont l'activation des
    capacités optionnelles.
12. `docs/JOURNAL_PRODUIT.md` + `docs/NEXT_STEPS.md` à jour ; entrée `docs/journal/`
    datée pour l'annonce publique.
