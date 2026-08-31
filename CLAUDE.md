# Règles du projet house

> Ce fichier a deux moitiés. **Celle-ci** — les six sections qui suivent — dit
> *comment travailler*, et vaut pour toute session, y compris celles qui
> n'invoquent aucun skill. Le reste du fichier dit *ce que ce code sait* : des
> règles adossées à des bugs réels, avec le pourquoi conservé. La première moitié
> se lit avant la demande ; la seconde se consulte quand on touche au domaine
> concerné.

## Comment travailler — le livrable est le produit fini

Le coût marginal de la complétude est proche de zéro. **Faire la chose entière** :
le code, le test de régression, les quatre locales, le tutoriel si le parcours
change, la doc du module. Ne jamais proposer « on verra plus tard » quand la
solution définitive tient dans la même session, ni présenter un contournement
quand le vrai correctif existe. Quand on demande une chose, la réponse est la
chose faite, pas un plan pour la faire.

**Complet ne veut pas dire large.** Finir jusqu'au bout ce qui est demandé, oui ;
élargir le périmètre au passage, non. Un refactor non demandé qui accompagne un
correctif rend le correctif irrelisable, et c'est la revue qui paie. Si un vrai
problème apparaît à côté du périmètre : le dire en une phrase, ouvrir une issue,
continuer.

**On peut déléguer la frappe, pas la compréhension.** Avant de déclarer une chose
finie, il faut pouvoir dire *pourquoi elle est correcte* **et** *où elle
casserait*. Des tests verts ne sont pas une compréhension : ils prouvent que ce
qu'on a pensé à vérifier passe. Si on ne sait pas énoncer les modes de défaillance
à voix haute, on ne conclut pas, on devine. C'est la seule raison pour laquelle ce
fichier existe sous cette forme — chaque règle d'ici est le mode de défaillance de
quelqu'un, écrit une fois pour ne pas être redécouvert.

## Deux espaces — ce qui se calcule ne se devine pas

Tout travail appartient à l'un des deux espaces, et se tromper d'espace est la
façon la plus courante de produire du faux avec assurance.

- **Espace latent** = le modèle. Jugement, prose, entrées ambiguës, analyse
  ouverte. Coût : des tokens. Variabilité : haute. Inspectable : pas du tout.
- **Espace déterministe** = du code. Même entrée, même sortie. Coût : une écriture,
  une fois. Variabilité : zéro. Inspectable : totalement.

**La règle** : si la même question posée deux fois a la même bonne réponse *par
définition*, elle n'a rien à faire dans l'espace latent. Arithmétique, conversion
de fuseau, calcul de date, parité de catalogues, résolution d'URL, comptage,
parsing : on écrit le contrôle. Si un raisonnement fait ça de tête, il s'arrête et
écrit le script.

**La boucle qui rend ça payant** : le modèle écrit le contrôle, puis le contrôle
contraint le modèle pour toujours. Un bug de l'espace latent devient une garantie
de l'espace déterministe, et l'ancien chemin d'échec devient structurellement
inatteignable. Face à une tâche mixte, on la coupe : la moitié déterministe devient
un test, la moitié latente reste un jugement — assumé comme tel.

Ce dépôt le fait déjà partout, et **à chaque fois parce qu'une relecture avait
échoué** : `ui/src/locales/keys.test.ts` (une clé i18n absente),
`apps/core/tests/test_prose_is_translated.py` (un `msgstr` vide, donc un bilan
mensuel en anglais dans les quatre langues), `ui/src/lib/invalidate.test.ts` (un
`onSuccess` qui oublie une racine), `agent/tests/test_registry.py` (un
`url_template` qui mène à un écran blanc), `nginx/test-resilience.sh` (un
`proxy_pass` littéral), `scripts/test-backup-restore.sh` (une restauration jamais
rejouée). Le point commun des six est déjà écrit plus bas, mot pour mot : **en
revue, le diff fautif ressemble exactement au diff juste.** Quand cette phrase est
vraie d'un défaut, c'est la signature d'un travail à sortir de l'espace latent —
pas d'une relecture à faire plus sérieusement.

## Chercher avant de construire

Trois couches, dans l'ordre :

1. **Ce qui existe déjà ici.** Le helper du dépôt, avant tout le reste.
2. **L'outil standard ou une lib avec une traction réelle** (étoiles, dernier
   commit, issues traitées) — et on nomme la raison du choix, pas une liste.
3. **Le premier principe**, et alors on **écrit pourquoi** le conventionnel ne
   s'applique pas, dans le commit ou la doc du module.

La couche 1 gagne presque toujours, et ici elle a un sens précis : `formatAmount`,
`DecimalInput`, `core.timezones`, `interactions.queries.expenses`, `useInvalidate`,
`notify_household`, `create_expense_interaction`. **Chacun est né de la
consolidation de quatre à seize copies divergentes** — en écrire une dix-septième
n'est pas neutre, c'est rouvrir le bug que la consolidation a fermé.

Si deux options se valent vraiment, nommer l'arbitrage et demander (voir plus bas).

## Fait deux fois à la main, la troisième est une commande

Un échec se transforme en test ; un **succès répété** se transforme en skill. Les
treize skills de `.claude/skills/` sont nés comme ça. Une invite ponctuelle ne
capitalise rien, un flux réutilisable oui : le levier est dans le travail qu'on
cesse d'avoir à penser. Dès la deuxième exécution manuelle du même enchaînement,
s'arrêter et le coder — script, skill ou hook.

## Ambiguïté à fort enjeu — s'arrêter et poser la question

Quatre déclencheurs, et seulement ceux-là :

- deux architectures plausibles pour le même besoin ;
- une demande qui contredit un pattern établi de ce fichier ;
- une opération destructive dont la portée n'est pas claire ;
- un contexte manquant qui changerait l'approche.

Alors : **STOP**. Nommer l'ambiguïté en une phrase, présenter 2-3 options avec
leurs vrais arbitrages — pas un faux éventail où une seule réponse tient debout —
et demander. Ne jamais deviner sur une décision d'architecture. **Ne s'applique
pas** au codage courant, aux petites features ni aux changements évidents : y
appliquer ce protocole transforme une session en questionnaire et fait perdre au
protocole le crédit dont il a besoin les quatre fois où il compte.

## Fin de tâche — un statut, pas une impression

Toute tâche se conclut par l'un de ces quatre mots :

- **FINI** — tout est fait, avec une preuve pour chaque affirmation : test de
  régression dans le diff, i18n dans les quatre locales, tutoriel à jour si le
  parcours change. Prêt à merger.
- **FINI AVEC RÉSERVES** — livré, mais avec des points à connaître. Chacun est
  nommé, avec sa gravité et la suite proposée.
- **BLOQUÉ** — impossible d'avancer. Dire sur quoi, et ce qui a déjà été tenté.
- **CONTEXTE MANQUANT** — il manque une information qui change l'approche. Dire
  exactement laquelle.

« Partiellement fait » n'est pas un statut : soit ça part en PR, soit c'est bloqué.
Un lot annoncé livré avec un reliquat passé sous silence se retrouve trois mois
plus tard dans une note de mémoire au lieu d'une issue, et une note de mémoire ne
se priorise pas.

**Dire aussi ce qu'il faut redémarrer** : quel service, quelle commande. Si rien
n'est à redémarrer, le dire explicitement. Une commande en `sudo` se liste, elle ne
se lance pas.

## Sûreté

- **Jamais de secret dans un commit.** Si un `.env*` est touché, vérifier
  `.gitignore` avant de committer. `gitleaks` tourne en CI ; ce n'est pas une
  raison pour lui laisser le premier rôle.
- **Jamais `--no-verify`.** Un hook qui échoue se corrige, il ne se contourne pas.
- **Jamais `rm -rf`, `git reset --hard`, `git push --force`, `DROP TABLE`** sans
  confirmation explicite. ⚠️ Ici le risque est plus proche qu'ailleurs : des
  sessions tournent **en parallèle dans le même checkout**, et un `reset --hard`
  emporte le travail non commité d'une autre session sans rien afficher. C'est la
  raison d'être de la règle du worktree.
- **Jamais de binaire commité** — à l'exception des images de marque, et
  seulement parce qu'elles se régénèrent en une commande (`npm run brand:social`).
- **`main` se déploie tout seul : un merge *est* une action de production.** Avant
  toute action qui touche la prod, dire ce qui va être fait et attendre.

## Workflow Git

- Trunk-based : `main` est la seule branche long-lived. Push sur `main` → auto-deploy prod.
- Pour les changements non-triviaux, créer une feature branch depuis `main`, ouvrir une PR vers `main`, merger.
- Pour les fix triviaux (typo, doc, micro-bug), commit direct sur `main` accepté.
- Nommage des branches : `<type>/<app>-<description-courte>` (ex: `fix/general-theme-logout`, `feat/tasks-delete`).
- Pas de branche `develop` ni d'environnement staging — tester localement (settings.production possible) avant de pusher.

### Format des commits — contrat pour le changelog

Les messages de commit alimentent **automatiquement** la page « Nouveautés »
(`/app/admin/changelog`, réservée au staff — voir plus bas). Le sujet DOIT être un commit conventionnel :

```
<type>(<scope>): <description>
```

- **`type`** : `feat`, `fix`, `perf` apparaissent dans le changelog ; `refactor`,
  `chore`, `docs`, `test`, `ci`, `build`, `style` sont ignorés (internes).
- **`scope`** = le module concerné (`projects`, `tasks`, `agent`…) → devient le
  **filtre/chip** de l'entrée. **Toujours mettre un scope** ; sans lui l'entrée
  tombe dans `general`.
- **`description`** : peut rester technique — elle est **repolie par l'IA** en
  phrase grand-public à la génération. Ce qui compte, c'est la **structure**
  (bon type, bon scope), pas la prose.

Le n° de PR de merge (`(#238)`) est extrait automatiquement pour le lien GitHub.

## Langue — l'audience décide, jamais l'habitude

Le dépôt est **public** (depuis 2025-09-21) et le [parcours 28](docs/parcours/PARCOURS_28_OUVRIR_MAISONNEE.md)
prépare son annonce sous le nom **Maisonnée**. À partir de maintenant, chaque
surface écrite a une langue, et elle se déduit de **qui la lit** :

| Surface | Langue | Lecteur |
|---|---|---|
| Interface (`ui/src/locales/`) | **en · fr · de · es** | l'utilisateur |
| `README.md`, `docs/self-hosting/`, notes de release | **anglais** (README aussi en `README.fr.md`) | l'inconnu qui découvre |
| `CONTRIBUTING`, `SECURITY`, `CODE_OF_CONDUCT`, modèles d'issue/PR, description et topics du dépôt | **anglais** | l'inconnu qui veut aider |
| Identifiants de code, noms de tests, noms de branches | **anglais** | tout le monde |
| **Messages de commit** (sujet et corps) | **français** | toi, et l'IA qui les lit |
| Issues et PRs | **français** jusqu'à l'annonce, **anglais** après | toi, puis tout le monde |
| `docs/parcours/`, `docs/fiches/`, `docs/MODULES/`, `docs/journal/`, `CLAUDE.md` (= `AGENTS.md`, lien symbolique), `DEPLOYMENT.md` | **français** | toi et l'assistant |
| Commentaires et docstrings | **français** admis là où le raisonnement se densifie | toi et l'assistant |
| Changelog in-app (`/app/admin/changelog`) | **français** | staff uniquement |

**Pourquoi la doc interne reste en français.** Elle porte du raisonnement dense —
chaque règle d'ici est adossée à un bug réel, avec le pourquoi conservé. Une
traduction qui dérive vaut moins qu'un texte juste, et c'est exactement ce qui
rend ce dépôt inhabituel. Le français ne coûte qu'aux **contributeurs**, jamais
aux **utilisateurs** : un self-hoster fait un `docker compose pull` et n'ouvre
jamais `apps/banking/queries.py`. Or l'objectif de la V1 publique est la
**rétention de foyers réels**, pas les pull requests. Mesuré au cadrage : 232
issues, 0 image, 0 donnée personnelle, et un code déjà majoritairement anglais.

**Pourquoi les commits restent en français.** Le message de commit a déjà un
lecteur machine assumé dans ce projet : `generate_changelog` le lit et le
**repolit** en phrase grand-public — c'est le contrat écrit juste au-dessus, qui
n'a jamais porté que sur la **structure** (`type(scope):`), jamais sur la langue.
Le reste du temps, un historique se consulte de moins en moins ligne à ligne : on
demande à une IA, qui lit le français aussi bien que l'anglais. Ce qu'un commit
doit être, c'est **précis** ; l'exiger dans une langue étrangère le rend plus vague,
pas plus lisible.

Le bénéfice secondaire est le plus solide : **une seule frontière au lieu de deux.**
Tout ce qui est interne est en français, tout ce qu'un inconnu lit en premier est
en anglais. Une règle à une frontière se tient ; une règle à exceptions dérive.

**Ce qui ne se cache pas se déclare.** `CONTRIBUTING` annonce la langue du projet
dès son premier paragraphe (livrable du lot 4, issue #490) : un contributeur ne
doit pas la découvrir en ouvrant un fichier.

> This project was built for one real household, in French. The interface speaks
> English, French, German and Spanish; the internal documentation and some code
> comments are in French. Issues and pull requests in English are welcome.

**Le jour de l'annonce, une seule chose change** : les nouvelles issues passent en
anglais. Le tracker devient un espace partagé, et un tracker exclusivement
français dit à un anglophone qu'il n'est pas le public. Les anciennes ne se
traduisent pas — réécrire l'histoire coûte plus que de l'assumer.

### Une traduction est additive, datée, et supprimable

`docs/README.en.md` (lot 4, issue #490) n'est pas une traduction : c'est un
**index anglais commenté** de la doc française — quoi, où, et pourquoi ça vaut la
peine d'aller lire. Il transforme « tout est en français » d'un mur en menu, et il
invite explicitement à traduire.

Ce qui **doit** venir avec, sinon l'invitation se retourne :

- **Le fichier français reste la source de vérité.** Toujours. Une traduction ne
  se corrige pas à la place de l'original.
- **Une traduction porte la date et le commit de la version qu'elle reflète**, et
  se nomme `<NOM>.en.md` **à côté** de l'original — jamais dans un dossier `en/`
  parallèle, qui rend la dérive invisible.
- **Périmée, elle se supprime.** Une traduction que personne ne met à jour est
  pire que pas de traduction : elle a l'air de faire autorité en étant fausse.
  C'est la même règle que les catalogues i18n (`keys.test.ts`) et que « un
  compteur ne peut pas avoir deux définitions » — **deux textes qui divergent font
  perdre leur crédit aux deux**, et celui qu'on lit n'est jamais celui qu'on
  corrige.

## Déploiement — le proxy ne tombe pas avec l'app

Doc : `DEPLOYMENT.md` § 3.4. Régression : `nginx/test-resilience.sh` (job `proxy`
de la CI, bloquant pour le deploy). Ce que tout changement doit préserver :

- **nginx atteint Django par une variable, jamais par un nom littéral.** Un
  `proxy_pass http://web:8000` est résolu **une seule fois, au chargement de la
  config**, et l'IP est gardée pour la vie du process : chaque recréation du
  conteneur `web` — donc chaque deploy — laissait nginx taper une IP morte. Il faut
  le `resolver 127.0.0.11` **et** le `proxy_pass http://$django` ; l'un sans l'autre
  ne résout rien. Le `valid=5s` **borne** la bascule sans la rendre instantanée — le
  DNS de Docker annonce un TTL de 600 s, que nginx respecterait : c'est cette valeur
  qui décide combien de temps il peut viser l'IP morte.
- **Le conf de nginx se monte par RÉPERTOIRE, jamais fichier par fichier.** Un bind
  mount de fichier unique **épingle l'inode** ; or `git reset --hard` n'édite pas le
  fichier en place, il en écrit un neuf et le renomme par-dessus. Le conteneur reste
  donc sur l'ancien inode pour toujours — `nginx -s reload` compris, qui recharge
  l'ancien contenu. Un correctif de conf a semblé livré sans l'être : la prod
  affichait `gzip_types` d'avant pendant que le repo avait celui d'après. Le test
  refuse tout `*.conf` monté seul.
- **Un trou se montre, il ne s'affiche pas en erreur technique.** 502/503/504 →
  `nginx/html/maintenance.html` en 503, et du **JSON** sur `/api/` (l'intercepteur
  axios lit `detail`). La page sonde `/health/` et se recharge seule.
- **`--no-deps` dans toutes les étapes du deploy.** Sans lui compose recrée nginx
  dans la foulée de `web`, et une page de maintenance servie par un proxy qui tombe
  au même moment ne sert à rien.
- **On migre avant de basculer**, sur un conteneur jetable de l'image neuve. D'où :
  une migration **destructive** (colonne supprimée ou renommée) se livre **en deux
  fois**, puisque l'ancien code voit le nouveau schéma le temps du basculement.
- **`/health/` reste une preuve de vie, pas de santé** — aucune requête en base. Le
  healthcheck y sert de porte au `up -d --wait` : un hoquet de postgres marquerait
  `web` malade alors qu'il va bien, et le deploy suivant attendrait pour rien.

## Débit — un compteur par process n'est pas un compteur

Doc : `docs/MODULES/security.md` § Throttling. Régression :
`apps/core/tests/test_rate_limits.py`.

- **Toute vue DRF a un plafond**, par le plancher `DEFAULT_THROTTLE_CLASSES`
  (`core.throttles`). Une vue qui déclare ses propres classes **remplace** ce
  plancher — c'est la sémantique de DRF, donc un `throttle_classes` posé pour
  serrer une limite ne doit jamais être posé pour en retirer une.
- **⚠️ Un throttle vaut ce que vaut son cache.** DRF compte dans
  `django.core.cache`. Le `LocMemCache` par défaut donne **un compteur par
  worker** : à quatre workers gunicorn, « 5 tentatives de connexion par minute »
  en autorisait vingt et tout repartait à zéro à chaque deploy. Ne jamais
  reconfigurer `CACHES` vers un backend local en production — c'est « un compteur
  ne peut pas avoir deux définitions » appliqué au débit, et il en avait quatre.
  La table de cache est créée par la migration `core.0003`, pas par une commande
  à lancer : sans elle l'API tombe à la première requête.
- **Ajouter un throttle = ajouter son tarif** dans `DEFAULT_THROTTLE_RATES`.
  Une portée sans tarif lève `ImproperlyConfigured` à la **première requête**,
  donc en production. Le test l'attrape — mais seulement depuis qu'il balaye les
  classes du projet et non `cls.throttle_classes`, qui ne voit rien de ce qu'un
  `get_throttles()` par action installe.
- **Ce qui coûte de l'argent se borne à part de ce qui coûte une requête.** Un
  envoi de document déclenche un appel de vision **synchrone** et une écriture
  d'entité un embedding : `document_upload` et `ocr_reprocess` existent pour ça.
  Le plancher compte des requêtes, pas des euros.

## Le premier compte — dans l'interface, jamais dans les logs

`GET|POST /api/accounts/setup/` (`AllowAny`) est l'assistant de premier
démarrage : une instance neuve n'a aucun compte, et le premier visiteur crée le
sien à l'écran. Avant, `create_admin` générait un mot de passe et l'imprimait
dans la sortie de `docker compose up` — où les logs de gunicorn le faisaient
défiler en quinze secondes, avec pour consigne « note-le, il n'est stocké nulle
part ». Le terminal était devenu une **étape du parcours**, alors que le README
promet que tout se fait depuis l'interface. Doc : `docs/self-hosting/install.md`.

- **La garde est « aucun compte n'existe », jamais « ce compte n'existe pas ».**
  Une configuration initiale qui se rouvre est une prise de contrôle offerte à
  qui trouve l'URL. Elle est prise **sous `pg_advisory_xact_lock`** dans la
  transaction : deux `POST` simultanés verraient tous deux zéro compte et
  créeraient deux administrateurs dans deux foyers différents, dont un fantôme.
- **⚠️ Et rien ne doit pouvoir rendre l'instance neuve à nouveau.** La garde étant
  « aucun compte n'existe », **tout mécanisme qui vide la base rouvre la porte**.
  La remise à zéro de la démonstration committait ses suppressions *hors*
  transaction avant de resemer pendant 1 min 45 : une fenêtre par nuit où la
  vitrine publique offrait son compte administrateur au premier visiteur qui
  passait — dans un foyer né hors de « Famille Mercier », que le `--flush`, borné
  à ce nom, n'aurait jamais purgé. Une purge et sa reconstruction partagent donc
  **une seule transaction** (`seed_demo_data`), ce qui ferme la fenêtre et fait
  d'une reseed échouée un retour à l'ancien foyer plutôt qu'une vitrine vide.
  `ALLOW_OPEN_SIGNUP=False` n'en protège pas : ce n'est pas la même porte.
  Régression : `test_first_run.py::TestAResetNeverLooksLikeANewInstance`.
- **Le refus se dit en 403, jamais en 401** — même raison que le refus
  d'inscription : 401 veut dire « recommence avec des identifiants », et aucun
  identifiant n'ouvrira une configuration déjà faite.
- **Seul le `POST` est serré** (`SignupRateThrottle`, 5/h/IP) ; le `GET` retombe
  sur le plancher global. L'écran de connexion l'interroge à chaque visite pour
  savoir s'il doit rediriger — le serrer casserait la page.
- **Une seule définition du premier compte** :
  `accounts.services.create_first_account` crée compte **+** foyer **+**
  appartenance **+** foyer actif, et les deux appelants (l'assistant et
  `create_admin`) passent par elle. Un compte sans foyer arrive sur une app vide
  de tout — « un demi-succès qui ressemble exactement à un échec ». Régression :
  `test_setup.py::TestTheUnattendedPathAgreesWithTheAssistant`.
- **`MAISONNEE_ADMIN_PASSWORD` reste le chemin non surveillé**, et il ne laisse
  aucune fenêtre : le compte existe avant le premier visiteur. Sans lui,
  `create_admin` ne crée **rien** — ne jamais réintroduire un mot de passe généré,
  c'est exactement ce que cet écran supprime.

## L'inscription — ouverte par défaut, fermable par `.env`

`POST /api/accounts/users/` est en `AllowAny` : c'est la seule façon pour un
auto-hébergeur de créer son premier compte. `ALLOW_OPEN_SIGNUP` (défaut `True`)
permet à une instance déjà en service de fermer la porte sans forker le code.

- **`validate_password` est appelé à la création comme à la mise à jour.**
  `set_password` hache n'importe quoi : sans cet appel, `AUTH_PASSWORD_VALIDATORS`
  n'était consulté nulle part sur le chemin d'inscription et `abc` était accepté
  en production. L'app était plus stricte sur un changement que sur le premier
  mot de passe — l'inverse de ce qu'il faut.
- **Un refus d'inscription se dit en 403, jamais en 401.** DRF convertit tout
  refus de permission en 401 dès qu'un authenticator annonce un
  `WWW-Authenticate` (`JWTAuthentication` le fait) ; or 401 veut dire
  « identifie-toi et recommence », et aucun identifiant n'ouvrira une inscription
  fermée. D'où le `permission_denied` surchargé sur l'action `create`.
- **`GET /api/accounts/signup-availability/` est public**, seule lecture des
  comptes à l'être : l'écran de connexion doit pouvoir *ne pas* proposer « créer
  un compte ». Sinon l'interface promet et le clic dément — le défaut que le lot 3
  du parcours 28 a supprimé partout ailleurs. Il n'expose rien que la première
  tentative ne dirait déjà en 403, contrairement à `/api/capabilities/` qui reste
  authentifié pour cette raison précise.

## Commandes utiles

### Backend Django

Toujours activer le venv avant toute commande Python/Django :

```bash
source venv/bin/activate
```

Installation des dépendances (3 niveaux) :

```bash
pip install -r requirements/base.txt   # prod uniquement
pip install -r requirements/test.txt   # base + pytest/coverage/factories
pip install -r requirements/dev.txt    # test + ipython et outils dev
```

```bash
python manage.py runserver          # démarre sur 127.0.0.1:8001
python manage.py migrate
python manage.py makemigrations
python manage.py shell
```

### Frontend React

```bash
npm run dev          # serveur Vite (dev, HMR)
npm run dev:watch    # rebuild continu des assets (mode prod watch)
npm run build        # build production
npm run lint         # ESLint sur ui/src
```

### Tests

Venv requis pour pytest (voir ci-dessus).

```bash
pytest                          # tous les tests Python (coverage inclus)
pytest apps/<app>/              # tests d'une app spécifique
pytest -k "nom_du_test"         # filtre par nom
pytest -m "not slow"            # exclure les tests lents
```

Tests E2E Playwright (serveur Django requis sur :8001) :

```bash
npm run test:e2e                # headless
npm run test:e2e:headed         # navigateur visible
npm run test:e2e:ui             # interface interactive
```

### Génération de types API

```bash
npm run gen:api:refresh   # régénère ui/src/gen/api depuis le schéma OpenAPI (serveur doit tourner sur :8001)
```

## Traductions (i18next)

Ne jamais utiliser de `defaultValue` dans les appels `t()` :

```ts
// ❌ Interdit
t('tasks.title', 'Tasks')
t('tasks.title', { defaultValue: 'Tasks' })

// ✅ Correct
t('tasks.title')
```

**Pourquoi :** les `defaultValue` masquent les traductions manquantes. Sans eux, une clé absente du fichier JSON affiche la clé brute, ce qui permet de repérer immédiatement ce qui n'est pas traduit.

**La règle est tenue par un test**, `ui/src/locales/keys.test.ts`, lancé en CI. Il
fait trois choses, et les trois sont nécessaires :

1. **toute clé `t('…')` littérale existe en français** — c'est le seul contrôle
   qui compare le *code* au catalogue ;
2. **aucun fichier ne contient `defaultValue:`** — sans quoi le premier contrôle
   se laisse contourner ;
3. **les quatre catalogues ont exactement les mêmes clés.**

Le n° 3 existait déjà de fait, et il n'a rien vu quand le lot 4 a écrasé les douze
clés de `banking.cash.*` : la clé manquait **partout**, donc la parité était
verte. Comparer les langues entre elles ne suffit jamais.

Les 111 `defaultValue` historiques masquaient trois vrais défauts en production —
un titre de dialogue réduit à « Créer », deux échecs distincts fondus en « Échec
de la requête », une `<legend>` affichant `tagSelector.legend`.

**Limite connue :** une clé construite (`t(\`documents.type.${v}\`)`, `t(labelKey)`)
n'est pas vérifiable statiquement. Pour une énumération, la contrepartie est que le
catalogue doit couvrir **toutes** ses valeurs — c'est ce qui rend le `defaultValue`
inutile là aussi, et non un mal nécessaire.

## Auto-création d'`Interaction` — pattern write-time + service helper

Quand une action utilisateur auto-crée une `Interaction` (ex: achat de stock ou d'équipement → interaction `expense`), le titre est rendu **dans la langue de l'utilisateur au moment de la création**, puis stocké en clair dans `subject`. Pas de localisation à l'affichage — admin, RAG, citation, CSV, `__str__`, edit user : tout consomme `interaction.subject` brut.

### Liaison polymorphe

`Interaction` est lié à son objet source via une FK polymorphe `(source_content_type, source_object_id)` + un `GenericForeignKey('source')`. Cela permet à n'importe quel modèle (`StockItem`, `Equipment`, `Project`, etc.) d'être source d'une interaction sans toucher au schéma.

### Service helper `create_expense_interaction`

Pour le cas standard « achat sur un objet », utiliser le service partagé :

```python
from interactions.services import create_expense_interaction

interaction = create_expense_interaction(
    source=stock_item_or_equipment,        # n'importe quel HouseholdScopedModel
    user=request.user,
    amount=Decimal("199.00"),
    supplier="Wood Co.",
    occurred_at=timezone.now(),
    notes="...",
    kind="stock_purchase",                 # optionnel, défaut = "<app_label>_purchase"
    extra_metadata={"delta": "3.8", "unit": "stère"},  # contexte feature-spécifique
)
```

Le service :
- localise le subject via `gettext_lazy` + le template enregistré dans `apps/interactions/services.py::AUTO_SUBJECT_TEMPLATES`
- renseigne les **colonnes** `amount`, `kind` (discriminateur), `supplier` (voir « Champs promus en colonnes » plus bas)
- ajoute `metadata.source_name`, `metadata.unit_price` + les extras feature (`delta`, `unit`, `brand`…)
- lie via la FK polymorphe
- attache la zone du source si elle existe

Les **side-effects** spécifiques au modèle source (ajuster une quantité, snapshot prix sur l'objet, etc.) restent dans la view appelante — le service ne touche pas à l'objet source.

### Service helper `create_manual_expense_interaction` (dépense ad-hoc)

Pour les dépenses **sans objet source** (resto, cinéma, cadeau…) — saisies depuis `/app/expenses/` :

```python
from interactions.services import create_manual_expense_interaction

interaction = create_manual_expense_interaction(
    household=request.household,
    user=request.user,
    subject="Restaurant Le Bistrot",   # saisi par l'user, pas templaté
    amount=Decimal("32.00"),
    supplier="Le Bistrot",
    occurred_at=timezone.now(),
    notes="...",
    zone_ids=[zone_id],                # optionnel
)
```

Différences vs `create_expense_interaction` :
- `subject` est **saisi par l'user**, pas templaté via gettext (le texte est stocké tel-quel)
- `metadata.kind = "manual"`, `metadata.source_name = None`
- Pas de FK polymorphe (`source_content_type=None`, `source_object_id=None`)
- `household` doit être passé explicitement (pas dérivé d'un source)

### Builder partagé `_build_expense_metadata`

Les deux fonctions (`create_expense_interaction` + `create_manual_expense_interaction`) flow through un helper interne `_build_expense_metadata` qui garantit le shape `metadata` uniforme : `{source_name, unit_price}` + extra optionnel. Les champs monétaires **requêtés** (`amount`, `kind`, `supplier`) ne sont **pas** dans `metadata` — ce sont des colonnes (voir juste en dessous).

### Champs promus en colonnes : `amount` / `kind` / `supplier`

Les trois champs **requêtés/agrégés** d'une dépense sont des **vraies colonnes**
sur `Interaction` (plus seulement dans `metadata`) : `amount`
(`DecimalField(14,2)`), `kind` (indexé), `supplier`. Raison : ils étaient castés
depuis le JSON (`Cast(KeyTextTransform(...))`) dans 4 agrégations dupliquées.
Voir `docs/fiches/CARTOGRAPHIE_DEPENSES.md`.

- **Toute lecture/agrégation passe par `interactions.queries.expenses()`** (helper
  unique) et somme la colonne `amount` — ne jamais réintroduire un cast JSON.
- Le write path renseigne les colonnes ; un `kind` non-standard (ex: `recurring`
  depuis `confirm_recurring_occurrence`) se passe via le **param `kind`** des
  créateurs, **jamais** via `extra_metadata`.
- **Le front et l'API consomment les colonnes** : `amount`/`kind`/`supplier` sont
  des champs de premier niveau du serializer (`InteractionSerializer`), lus et
  écrits directement. Ces clés ne sont **plus** dans `metadata` (strippées par la
  migration `interactions.0024`). `unit_price` et `source_name` restent en
  `metadata` (non requêtés), avec les extras feature (`delta`, `unit`, `brand`…).
- Le `kind` d'une entrée **non-dépense** (ex: `renovation`) reste en `metadata` —
  la colonne `kind` est propre aux dépenses ; l'endpoint liste générique filtre
  donc `Q(kind=…) | Q(metadata__kind=…)` pour couvrir les deux.

### Relevés bancaires — une dépense est une ventilation (parcours 25)

**Livré** (lots 1-6). Doc : `docs/parcours/PARCOURS_25_RELEVES_BANCAIRES.md` +
`docs/fiches/IMPORT_ET_RAPPROCHEMENT.md` + `docs/MODULES/banking.md`.

- **Il n'y a pas de table `Allocation`.** Une ligne de relevé (`banking.BankTransaction`)
  ventilée 80 € / 40 € produit **deux `Interaction(type='expense')`**, chacune avec
  son `amount` et son `budget`, reliées à la ligne par la FK nullable
  `Interaction.bank_transaction` (`SET_NULL`). Conséquence à préserver :
  **`amount` reste une colonne scalaire** — ne jamais le rendre dérivé, sous peine
  de réécrire les 9 `Sum("amount")` avec un risque de double comptage par JOIN 1-N.
- **`Interaction.amount` est toujours positif** ; `BankTransaction.amount` est
  **signé** (négatif = sortie). Un remboursement n'est jamais une interaction
  négative — ça casserait `top_expenses` et `_spent_by_budget`.
- **Ne jamais additionner un total « banque » et un total « interactions ».** Les
  agrégats budget/dépenses lisent les `Interaction` exclusivement ; les totaux
  bancaires (et les **recettes**, qui n'entrent pas dans le journal) sont une vue à
  part. Le pont est un **taux de couverture**, pas une somme.
- **Le solde n'est jamais dénormalisé** (même règle que le « dépensé » du parcours
  21) : calculé à la lecture, ancré sur `BankTransaction.balance_after`.
- Une dépense créée depuis une ligne bancaire prend `occurred_at` à **midi dans la
  tz du foyer** — à minuit, une opération du 1er ou du 31 changerait de mois, donc
  de budget.
- Toute écriture de montant sur une interaction rapprochée passe par
  `banking.validators.assert_allocation_fits` — y compris le PATCH générique de
  `InteractionSerializer`.

### Conformité de l'argent — aucun orphelin silencieux (parcours 26)

Doc : `docs/parcours/PARCOURS_26_CONFORMITE_ARGENT.md` + section « Conformité » de
`docs/MODULES/banking.md`. Règle structurante :

> Toute entité est soit **résolue**, soit **flaggée avec un motif**.
> Rien ne reste dans un entre-deux silencieux.

- **Ajouter un mécanisme à l'argent = ajouter son détecteur.** Le registre
  `banking.compliance.REGISTRY` est alimenté depuis `apps.py::ready()` (même modèle
  que `agent.searchables`). C'est cette règle — à vérifier en revue — qui empêche
  le catalogue des orphelins de prendre du retard sur le code.
- **Écarter n'est pas cacher.** Un écart s'arbitre via `banking.ComplianceWaiver` :
  motif **requis**, daté, signé, **révocable**. Ne jamais introduire un
  `dismissed_at` / `ignored` / `accepted` sur une table métier — des états
  hétérogènes qu'on ne peut pas compter ensemble sont exactement l'orphelin qu'on
  supprime.
- **Un arbitrage périme.** Le waiver stocke le `fingerprint` de ce qu'il arbitre ;
  quand la situation bouge, l'écart resurgit `is_stale`. Tout nouveau détecteur
  doit donc faire entrer dans son `fingerprint` ce qui *fonde* l'écart (le reste à
  ventiler, le montant manquant…) et **rien de cosmétique**, sinon chaque édition
  invaliderait chaque arbitrage.
- **Certains écarts ne s'arbitrent pas** (`waivable=False`) : solde d'ouverture
  manquant, espèces à découvert, double confirmation. Ce sont des incohérences ou
  des prérequis, pas des choix — le service répond 400.
- **La conformité est bornée.** Tout détecteur qui raisonne sur « de l'argent qu'on
  devrait connaître » se scope par `banking.coverage` : hors de la fenêtre
  `[opening_balance_date, dernière date connue]`, un écart n'est pas un écart. Sans
  cette borne le contrôle afficherait des centaines d'écarts irrésolubles, et une
  liste irrésoluble ne se lit pas.
- **⚠️ Un compteur à zéro a deux sens : « rien à signaler » et « rien d'évaluable ».**
  Les confondre a produit un silence total en prod (compte dont la date de solde
  d'ouverture postdatait ses lignes → fenêtre vide → coche verte « tout est
  affecté »). Deux conséquences permanentes : `coverage.window_status()` renvoie une
  **raison** et jamais un simple `None` — un compte sans données est normal, un compte
  hors fenêtre ne l'est pas ; et tout affichage de compteur passe par
  `ui/src/features/money/prerequisites.ts`, qui distingue les deux. Ne jamais afficher
  « conforme » sans avoir vérifié que le contrôle a pu s'exécuter.
- **Le badge doit rester bon marché** : `DetectorSpec.count` est un `COUNT(*)`
  indexé, `findings` est paginé et ne tourne que pour le groupe ouvert. Ne jamais
  matérialiser les écarts en Python pour les compter. Et **ouvrir un groupe ne
  recompte que lui** (`compliance.group_result`) : passer par `summary()` pour
  sérialiser un seul en-tête relançait les quatorze détecteurs, dont la marche
  arithmétique sur les soldes.
- **Un détecteur non-SQL passe par `compliance.apply_window_to_pairs`.** La moitié
  du catalogue raisonne sur ce qu'aucun `COUNT(*)` n'exprime (une chaîne de soldes,
  une reconstruction, un solde espèces) et renvoie `[(objet, détail), …]` ; le
  filtrage `pks / exclude_pks / limit / offset` est le même pour tous et n'a pas à
  être réécrit — il l'a été six fois.
- **Toute écriture sur l'argent invalide tout l'argent** (`useInvalidateMoney`,
  `ui/src/features/money/invalidate.ts`). Les cinq racines de cache — `banking`,
  `interactions`, `expenses`, `budget`, `compliance` — sont déclarées dans
  `money/keys.ts` et jamais en littéral au point d'appel. Chaque hook listait sa
  propre combinaison et elles avaient dérivé : importer un relevé n'invalidait que
  `banking`, rattacher une dépense ne touchait pas la conformité. Invalider trop
  large coûte quelques requêtes ; invalider trop étroit coûte la confiance dans
  les chiffres, et ne se voit pas en revue.
- Le libellé utilisateur d'un `kind` vit dans le namespace i18n **`money`** du
  front, pas en `gettext` backend : ajouter un détecteur ne doit pas imposer un
  passage dans quatre `.po`.
- **Un écart ne se dit jamais deux fois avec deux voix.** Le marqueur du journal
  (`allocation_state`, servi par le serializer) et le compteur du Contrôle lisent
  la **même** fonction `banking.queries.allocation_state` / `with_allocation`. Ne
  jamais recalculer un état de traitement côté client à partir d'un montant : le
  verdict dépend de la fenêtre de conformité, et une ligne verte dans un écran
  face à un écart dans l'autre fait perdre leur crédit aux deux. Régression :
  `banking/tests/test_journal_marker.py::TestTheMarkerAgreesWithTheControl`.
- **Et la même règle vaut depuis l'autre rive.** « Cette dépense est-elle
  justifiée par un relevé ? » se lit dans `reconciliation_state`
  (`banking.queries`, servi par `InteractionSerializer`, rendu par
  `money/ReconciliationBadge.tsx`), **jamais** dérivé de `bank_transaction == null`
  côté client : sans la fenêtre, le badge accusait en rouge des dépenses
  antérieures au premier relevé, insolubles par construction et que le Contrôle ne
  réclamait pas. Corollaires : `cash` se déduit du **type du compte** de la ligne,
  jamais de `reconciled_by` (que le créateur met toujours à `manual`, ce qui
  rendait la branche morte) ; et le badge **mène à l'opération**
  (`/app/money/transactions/:id`) — « rapprochée » sans pouvoir aller voir à quoi
  est invérifiable. Régression :
  `banking/tests/test_expense_marker.py::TestTheMarkerAgreesWithTheControl`.

#### Le groupe « Argent » — trois pages, une seule famille d'URLs

Comptes, dépenses et budgets sont **trois pages d'un groupe de sidebar** (`money`),
dans cet ordre : Budgets (`/app/money/budgets`), Dépenses (`/app/money/expenses`),
Comptes (`/app/money/accounts`). Doc : `docs/MODULES/money.md`.

- **Contrôle et « À ranger » restent des onglets de la page Comptes**, qui ouvre
  sur Comptes. Ils ne portent que sur ce que les relevés laissent en suspens : en
  faire des destinations obligerait à changer d'écran pour agir sur ce qu'on vient
  d'y lire. Et une entrée de sidebar qui annonce les comptes et ouvre autre chose
  fait douter du clic.
- **Les clés de module sont `money_budgets` / `money_expenses` / `money_accounts`**,
  identiques des deux côtés (`ui/src/lib/modules.ts`,
  `households.modules.PINNABLE_MODULES`). Ne pas ressusciter `banking`, `expenses`,
  `budget` ni `money` : ce sont des `LEGACY_MONEY_MODULES`. Toutes sont **core**
  (non désactivables) — conséquence assumée : les comptes bancaires ne sont plus un
  opt-in. ⚠️ **Renommer une clé de nav se livre avec sa data migration** : la
  sidebar renvoie la liste **entière** de `pinned_modules` au prochain épinglage,
  donc une clé morte ne perd pas seulement un raccourci, elle transforme un geste
  sans rapport en 400 (`accounts.0014` puis `accounts.0018`).
- Toute nouvelle URL de la famille argent vit sous `/app/money` — y compris
  `/app/money/recurring` et `/app/money/reports`, entrées dans la famille en juillet
  2026. Les anciennes redirigent en **préservant la query string** :
  `MoneyTabRedirect` pour `/app/money` et les trois anciennes pages (l'agent
  produisait `/app/budget?b={id}`), `PreserveQueryRedirect` pour les sous-pages
  (`?r={id}`) — ne pas remplacer par un `<Navigate to>` en dur, qui perd le
  paramètre et transforme un lien précis en lien faux. `MoneyTabRedirect` **lit
  `?tab=` pour choisir la page** et ne le laisse survivre que sur Comptes, seule
  page à avoir encore des onglets : un paramètre qui ne pilote plus rien se recopie
  dans un favori en promettant le contraire. La résolution vit dans
  `ui/src/lib/moneyRedirect.ts`, testée sans routeur.
- **Un `url_template` d'agent de cette famille doit pointer directement sur la
  page**, jamais via une redirection — ni `/app/budget`, ni `/app/money?tab=budgets`
  qui n'est plus qu'une redirection à son tour. Une redirection rattrape un ancien
  lien, elle ne justifie pas d'en produire de nouveaux. Tenu par
  `agent/tests/test_registry.py::test_the_money_family_links_stay_inside_the_money_module`.
- Les panneaux (`AccountsPanel`, `ExpensesPanel`, `BudgetsPanel`) n'ont **pas** de
  `PageHeader` : la page qui les enveloppe porte le titre. Un panneau qui en ajoute
  un produit deux `h1`.
- Une pastille de budget de la file « À ranger » n'apparaît que sur une ligne
  **entièrement** non ventilée : l'écriture d'une ventilation est un remplacement
  complet, donc un raccourci sur une ligne partielle détruirait le travail déjà
  fait. Même raison pour la sélection multiple.

#### Le budget est la catégorie — et son plafond est optionnel

`Interaction.budget` est le **seul axe qui classe un euro** (projet et zone
disent *sur quoi* et *où*, pas *de quelle nature*), et le détecteur
`expense_without_budget` en réclame un sur chaque dépense de la fenêtre.

- **`Budget.monthly_amount` est nullable** : `NULL` = « catégorie suivie, non
  plafonnée ». Exiger un plafond pour obtenir une catégorie forçait à inventer un
  montant pour « Cadeaux » — et un panneau de plafonds inventés rend illisibles
  jusqu'aux vraies barres.
- **`uncapped` est un état à part, jamais `ok`.** Une catégorie sans plafond ne
  peut être ni respectée ni dépassée ; une barre verte à 0 % sur ce qui n'a pas
  d'échelle est le même mensonge que la coche verte d'un contrôle qui n'a rien
  vérifié. Et le payload renvoie `"amount": null`, **jamais `"0.00"`** — un
  plafond à zéro est perpétuellement dépassé.
- **Le budget global garde son montant obligatoire** (400 sinon) : plafonner est
  sa seule raison d'être. Un plafond à zéro reste refusé partout — ce n'est pas
  « pas de plafond ».
- Un `stats` de bilan **déjà figé** porte `"amount": "400.00"` ; `report/render.py`
  doit accepter la string *et* le `null` pour toujours.
- **Le dépensé se dit en deux chiffres, jamais en un filtre.** Chaque ligne de
  l'aperçu porte `spent_attested` / `spent_pending` **en plus** de `spent` — la part
  qu'une ligne de relevé justifie, et le reste. Ne jamais filtrer
  `bank_transaction__isnull=False` pour ne compter que le prouvé : une dépense saisie
  hier est réelle avant l'import du relevé, donc le compteur reculerait au fil du mois
  pour remonter d'un coup — **un plafond qui recule est pire qu'un plafond
  incertain**. `spent` reste le compteur du plafond ; `spent_pending` est calculé **par
  différence** (deux sommes indépendantes divergent d'un centime d'arrondi, et un total
  qui ne se recompose pas ne se lit pas) ; et les deux chiffres sortent d'**un seul**
  `GROUP BY` avec `Sum(filter=…)`, l'aperçu étant rechargé à chaque visite de l'onglet.

#### Ventilation — budget et projet sont deux axes indépendants

Une ligne de ventilation porte un **budget** *et* un **objet** (projet, équipement,
article de stock) *et* des **zones**. 90 € des 150 € dépensés chez Leroy Merlin
comptent dans le chantier **et** dans l'enveloppe « Bricolage ».

- **⚠️ La règle de propriété de l'éditeur de ventilation lit `kind` seul**
  (`OWNED_BY_ALLOCATION_EDITOR`). Ne jamais y rajouter une clause sur
  `source_content_type_id` : avec elle, une ligne rattachée à un projet cesse
  d'être « possédée » et se retrouve *détachée* au lieu d'être supprimée à la
  ré-édition — **chaque ré-édition laisse une dépense fantôme** toujours comptée
  dans le coût du projet. Test de régression :
  `banking/tests/test_allocation_axes.py::TestOwnershipRuleRegression`.
- **⚠️ Et la portée de l'éditeur s'arrête là.** Il supprime ses lignes `kind='bank'`
  et **ne touche à rien d'autre** — ni suppression, ni *détachement*. Enregistrer une
  ventilation dé-rapprochait autrefois tout ce qu'elle ne possède pas : un achat de
  projet rapproché à la main sur la même ligne redevenait « non rapproché » en
  silence, et comme le dialogue rechargeait *toutes* les ventilations dans son
  brouillon, il recréait une dépense `bank` pour le même argent — 180 € de dépenses
  sur 150 €, chantier facturé deux fois. Corollaire : le montant déjà rattaché est un
  **plancher** compté contre l'`outflow` (renvoyer la ligne rattachée = 400), et
  détacher est un **geste explicite** (`unlink_interaction`, bloc « Dépenses déjà
  rattachées » du dialogue), jamais l'effet de bord d'un enregistrement. Régression :
  `banking/tests/test_allocation_axes.py::TestSavingASplitNeverUndoesAReconciliation`.
- `kind` reste `bank` même avec une source : il dit *d'où vient* la dépense, pas
  *sur quoi elle porte*.
- Toute résolution de source passe par
  `interactions.services.resolve_allocation_source`, qui **vérifie le foyer** —
  sans ça un client gonflerait le coût d'un projet qu'il ne peut pas voir.
- `set_allocations` convertit les `ValueError` du créateur en **400 préfixé du
  numéro de ligne**. Ne pas les laisser remonter : un mauvais id de zone donnait un
  500 sur une simple erreur client.

#### Recettes, mouvements internes, taux de couverture

- **`banking.rules` produit des valeurs de départ, jamais des vérités.** `is_internal`
  décide si l'argent compte comme dépense : une devinette appliquée comme vérité fait
  disparaître une vraie dépense des totaux, en silence. `guess_internal` renvoie
  `False` sur l'inconnu (défaut sûr), l'utilisateur corrige, et l'idempotence de
  l'import protège son choix. Ne pas grossir la liste de motifs pour « mieux faire » :
  une liste maligne finit par mal étiqueter la seule ligne de l'année qui compte.
- **`inflow_nature == ""` n'est pas `"other"`.** Vide = personne n'a regardé (écart) ;
  `other` = choix de l'utilisateur. Confondre les deux rend le détecteur aveugle.
- **Un remboursement est une ligne bancaire avec une nature, jamais une dépense
  négative.** `Interaction.amount` reste toujours positif. Ce qu'il porte en plus,
  c'est **`BankTransaction.refund_budget`** : l'enveloppe qu'il recrédite. Un
  article de 40 € rendu sur un achat de 150 € veut dire que le budget a consommé
  110 €, et sans ce champ « 150 € / 400 € » restait faux pour toujours.
  - **`spent` reste le brut, `net_spent = spent − refunded` est le chiffre du
    plafond** (`ratio`/`state` le mesurent). Ne pas redéfinir `spent` : sept
    agrégations le lisent, et sa décomposition attesté/en attente perdrait son
    sens.
  - **C'est la seule soustraction admise entre banque et journal**, et elle
    n'enfreint pas la règle du dessus parce qu'elle ne retranche pas un *total*
    bancaire : seulement des lignes que l'utilisateur a désignées une par une.
    Une recette sans `refund_budget` ne retire rien à personne — et c'est l'écart
    `refund_without_budget`.
  - **Un remboursement compte dans son mois**, jamais dans celui de l'achat :
    l'imputer rétroactivement réécrirait un bilan mensuel déjà figé. Conséquence
    assumée : un mois peut être net négatif.
  - **Le bilan mensuel recalcule son propre « dépensé »** (`report/stats.py`) : il
    a donc fallu l'y ajouter aussi, sinon il annonçait « dépassé » là où l'aperçu
    affichait « ok ». Régression :
    `budget/tests/test_refunds.py::TestTheMonthlyReportAgreesWithThePanel`.
  - Un `CheckConstraint` interdit un `refund_budget` sur autre chose qu'une
    recette de nature `refund`, et reclasser un remboursement en salaire efface
    le budget avec lui.
- **Le pont banque ↔ interactions est `coverage_ratio`, jamais une somme.** Il vaut
  `1.0` quand rien n'est sorti — rien à expliquer n'est pas un reproche.
  `unallocated_outflow` se calcule **par différence sur la requête bancaire**, jamais
  en soustrayant une somme de dépenses.
- Le bloc `bank` du bilan mensuel est **additionnel** : ne jamais modifier les clés
  existantes du snapshot, le rendu et le digest les lisent.

#### Récurrences confirmées par le relevé

- **`Interaction.recurring_expense` est une FK, pas `metadata['recurring_id']`.** La
  clé JSON reste pour l'affichage, mais tout **groupement ou filtre** passe par la
  FK : le détecteur de double confirmation fait un `GROUP BY`, ce qu'une clé JSON ne
  permet ni d'indexer ni de contraindre. Ne jamais réintroduire un filtre
  `metadata__recurring_id`.
- **Auto-confirmer exige un montant strictement égal.** Une facture qui varie de
  cinq centimes reste non confirmée : la confirmer écrirait une occurrence à un
  montant que l'utilisateur n'a jamais vu.
- **Ordre à l'import : dépenses d'abord, récurrences ensuite**, sur ce qui reste
  libre. Une dépense déjà saisie est une information plus sûre qu'une échéance
  prévue.
- Une confirmation ventile **intégralement** la ligne. Sinon confirmer créerait un
  écart « sortie partiellement ventilée » — l'app fabriquerait son propre travail.
- Le passage sur les lignes libres se fait en **une requête**
  (`interactions__isnull=True`), jamais un `exists()` par ligne : la version naïve
  coûtait 160 allers-retours sur un relevé réel.

#### Continuité et provenance

- **`opening_balance_date` est requise à la création** d'un compte, jamais à
  l'édition. Sans elle le compte n'a pas de fenêtre de conformité ; mais l'exiger à
  chaque PATCH rendrait un simple renommage impossible — le détecteur du lot 1 traite
  l'existant.
- `statement_period_gap`, `account_chain_broken` et `account_anchor_stale` sont
  **complémentaires**, et aucun ne voit l'angle mort des deux autres : le deuxième
  attrape les opérations manquantes *dans* une période importée par l'arithmétique
  des soldes imprimés ; le premier une période jamais importée, qui ne laisse aucune
  trace arithmétique ; le troisième la dérive d'un solde d'ouverture **reconstruit**,
  que les deux premiers ne peuvent pas voir sur un fichier sans colonne solde. Ne pas
  fusionner.
- **Ne jamais demander une information que House peut calculer.** Le solde
  d'ouverture d'un compte se lit dans le relevé quand il y figure, et se **retrouve
  par soustraction** sinon (`banking.anchoring`) : une appli bancaire n'affiche que
  le solde du *jour*, jamais celui d'une date passée. Exiger le second sans offrir de
  le dériver du premier a produit en prod des comptes ouverts « aujourd'hui »,
  fenêtre vide, contrôle muet.
- **Une reconstruction qu'on ne peut pas re-vérifier est un orphelin.** D'où
  `attested_balance`/`attested_on` : ce ne sont pas des soldes dénormalisés (règle du
  lot 4 intacte) mais les **saisies** dont `opening_balance` a été dérivé, gardées
  pour que `opening_balance + Σ mouvements == attested_balance` soit re-testé à
  chaque recalcul. Tout mécanisme futur qui *dérive* une valeur d'une déclaration
  utilisateur doit conserver la déclaration, sinon la dérive devient invisible.
- Le partage est explicite : ce que House **peut réfuter** (lecture antérieure aux
  lignes détenues, période manquante *dans l'intervalle*) est un **400 nommé** ; ce
  que seul l'utilisateur **peut attester** est demandé à côté de la dernière
  opération connue, jamais dans le vide.
- `skipped_count > 0` n'est un écart que sur un fichier **sans référence ni solde** —
  ailleurs c'est la signature normale d'un ré-import. La présence de ces colonnes est
  dérivée des lignes créées, pas stockée.

### Ajouter un nouveau template d'auto-subject

1. Ajouter l'entrée dans `AUTO_SUBJECT_TEMPLATES` (`apps/interactions/services.py`)
2. `python manage.py makemessages -l fr -l de -l es`
3. Éditer les 3 `.po` (`locale/fr|de|es/LC_MESSAGES/django.po`) pour ajouter la traduction
4. `python manage.py compilemessages`

> **`makemessages` est overridé** (`apps/core/management/commands/makemessages.py`) :
> `venv/`, `node_modules/` et `htmlcov/` sont ignorés par défaut. Sans ça, la
> commande scanne le venv (présent dans le repo) et injecte des centaines de
> `#:` vers Django/DRF dans les `.po`. Ne jamais réintroduire ces refs : si un
> diff `.po` fait apparaître des chemins `venv/lib/...`, c'est que l'override a
> été contourné. **Ne pas traduire les strings tierces** — Django fournit les
> siennes.

### `gettext` a le même garde-fou que i18next — `test_prose_is_translated.py`

Toute prose que le foyer **lit** (bilan mensuel, récap, pings) voit ses littéraux
`_("…")` vérifiés dans les catalogues **compilés** de `fr`/`de`/`es`. Ajouter un
module qui écrit une phrase à l'utilisateur = l'ajouter à `PROSE_MODULES`.

- **Un `msgstr` vide ne casse rien, il traduit en anglais.** Le bilan mensuel a
  vécu en prod en anglais dans les quatre langues : ses quatorze chaînes étaient
  vides dans les trois `.po`. Rien de rouge, un texte parfaitement valide —
  simplement pas dans la bonne langue. C'est exactement ce que produisaient les
  `defaultValue` côté front, et ça se corrige avec le même outil : un test.
- **Une entrée `#, fuzzy` est absente du `.mo`**, donc invisible au runtime mais
  bien présente dans le `.po` — et `msgmerge` la remplit en devinant depuis une
  chaîne voisine. Deux entrées du bilan portaient ainsi les placeholders d'un
  message de stock (`%(qty)s`, `%(unit)s`) : les « défuzzifier » sans relire
  aurait levé un `KeyError` au rendu. Une traduction devinée se relit avant de
  se garder.
- **Le test lit le catalogue compilé, jamais le rendu.** Une traduction a le droit
  d'être identique à l'original (`%(name)s: %(spent)s.` en allemand) : comparer
  deux rendus ne prouverait rien, alors que `msgfmt` n'écrit que les entrées non
  vides et non fuzzy.
- **Portée : la prose, pas les `help_text`.** ~180 chaînes d'admin et de
  validation restent non traduites ; c'est un autre chantier, et l'y inclure
  rendrait le garde-fou rouge en permanence, donc inutile.

### Frontend — formulaire partagé

Pour la partie UI, `ui/src/features/interactions/PurchaseForm.tsx` est le composant partagé (champs prix/fournisseur/date/notes + delta optionnel). Chaque feature wrappe ce form dans son propre dialog (`StockPurchaseDialog`, `EquipmentPurchaseDialog`, etc.) qui gère :
- son contexte (item courant, mutation appelée)
- le titre du dialog
- les éventuels affichages spécifiques (quantité courante pour stock)

Les clés i18n `purchase.*` (génériques au form) sont **shared** ; les clés `stock.purchase.*` / `equipment.purchase.*` sont **feature-spécifiques** (titre, message créé, libellé du bouton sur la card).

### Pourquoi ce pattern

- 1 user = 1 langue (pas de multi-langue par user dans le projet)
- Le subject reste lisible dans la DB pour l'admin Django, l'agent RAG (search vector), les exports CSV
- L'user édite son subject via `InteractionEditPage` → son texte écrase l'auto, sans logique de flag/snapshot
- FK polymorphe → toute feature peut auto-créer une interaction liée à n'importe quel objet, sans migration de schéma à chaque fois

**Limite acceptée** : si l'user change sa langue plus tard, ses anciennes interactions auto-créées restent dans l'ancienne langue. Acceptable car rare.

### Interaction vs modèle dédié — règle de décision

`Interaction` est le **journal du foyer**, pas une table générique. Une entrée y a sa
place parce qu'elle bénéficie gratuitement des quatre consommateurs transverses :
fil d'activité du dashboard, page dépenses + agrégations (`Project.actual_cost`),
RAG de l'agent (recherche/citation/`sum_amount`), liaisons génériques (zones M2M,
documents, tâches).

**Utiliser `Interaction`** (type existant + discriminateur `metadata.kind`) tant que
l'entrée est **un fait daté, plat, sans invariant** : dépenses (`*_purchase`,
`manual`), notes, carnet de rénovation (`renovation`).

**Créer un modèle dédié** dès qu'UN de ces besoins apparaît :

- machine à états / transitions (ex : `Task`, historiquement **extraite**
  d'`Interaction` — voir `Task.source_interaction`) ;
- contrainte DB (unicité, check) sur les données métier — impossible dans
  `metadata` JSON (ex : `EggLog` et son `unique(household, date)` qui fonde l'upsert) ;
- FK typée avec cascade / timeline par objet (ex : `ChickenEvent.chicken`) ;
- types métier sans équivalent dans `INTERACTION_TYPES` (couvaison, mue…) ;
- requêtes ou filtres sur les champs structurés (dans `metadata`, ils doivent rester
  **affichés, jamais requêtés ni contraints** — c'est la limite du carnet de rénovation).

Coûts du pattern à garder en tête : `metadata.kind` est stringly-typed (aucune
contrainte DB, une faute de frappe crée une catégorie silencieuse), les invariants ne
tiennent que si toutes les écritures passent par `interactions/services.py`, et les
filtres `metadata__kind=` sont dispersés dans plusieurs apps (renommer un kind est un
chantier transverse). Le type `todo` (et le champ `status` qui l'accompagnait) a été
retiré d'`Interaction` — les données ont été purgées vers `Task`
(`interactions.0018_purge_todo_interactions`).

## Composants UI

### Cartes (`Card`)

Toujours utiliser le composant `Card` du design-system pour les éléments de type carte, jamais un `<div>` avec des classes manuelles :

```tsx
// ❌ Interdit
<div className="rounded-lg border bg-white p-3 shadow-sm">...</div>

// ✅ Correct
import { Card } from '@/design-system/card';
<Card className="p-3">...</Card>
```

### Titre de carte (`CardTitle`)

Toujours utiliser `CardTitle` pour le titre principal d'une card. Supporte une prop `emoji` optionnelle qui reste immune aux styles hover/underline du parent (ex: quand le titre est dans un `<Link>`) :

```tsx
import { Card, CardTitle } from '@/design-system/card';

// Statique
<CardTitle>Mon équipement</CardTitle>

// Avec emoji — détecté automatiquement depuis le texte
<CardTitle>🔧 Mon équipement</CardTitle>

// Interactif — l'emoji ne bouge pas au hover
// NE PAS mettre hover:underline sur le Link (underline tous les spans y compris emoji)
// Utiliser group + [&>span:last-child]:group-hover:underline pour cibler uniquement le texte
<Link to="/app/equipment/123" className="group text-foreground hover:text-primary">
  <CardTitle className="text-inherit [&>span:last-child]:group-hover:underline">🔧 Mon équipement</CardTitle>
</Link>
```

### Actions en bout de carte (`CardActions`)

Pour les actions contextuelle (éditer, supprimer…) en bout de carte, utiliser le composant générique `CardActions` qui expose un dropdown `MoreHorizontal` :

```tsx
import CardActions, { type CardAction } from '@/components/CardActions';

const actions: CardAction[] = [
  { label: t('common.edit'), icon: Pencil, onClick: () => onEdit(item) },
  { label: t('common.delete'), icon: Trash2, onClick: () => onDelete(item.id), variant: 'danger' },
];

<CardActions actions={actions} />
```

### Retour contextuel (`BackLink` + `pushBack`)

Toute page de détail utilise `BackLink` : le lien retour ramène à la **page
d'origine** (ex: détail projet) si elle est connue, sinon à la liste par défaut.
L'origine circule via une pile d'URLs dans `location.state.back` — elle survit
aux reloads mais pas à un accès direct par URL (→ fallback).

```tsx
// Page de détail — lien retour + navigation après suppression
import BackLink from '@/components/BackLink';
import { useNavigateBack } from '@/lib/backNavigation';

<BackLink fallback="/app/tasks" fallbackLabel={t('tasks.title')} />
const navigateBack = useNavigateBack('/app/tasks');   // deleteMutation onSuccess

// Page d'origine — tout Link/navigate() vers une page de détail empile l'URL courante
import { pushBack } from '@/lib/backNavigation';
const location = useLocation();
<Link to={`/app/tasks/${id}`} state={pushBack(location)}>
navigate(`/app/tasks/${id}`, { state: pushBack(location) });
```

Ne jamais utiliser `navigate(-1)` pour un lien retour de page de détail (casse
sur accès direct / nouvel onglet) ni coder la liste en dur si la page peut être
ouverte depuis un autre contexte.

### Couleurs — pas de hardcode

Toujours utiliser les tokens CSS du design-system, jamais des classes Tailwind à couleur fixe :

```tsx
// ❌ Interdit
<div className="bg-white border-slate-200 text-slate-900">
<span className="bg-blue-100 text-blue-700">
<div className="bg-slate-100 animate-pulse">  // skeleton

// ✅ Correct
<div className="bg-card border-border text-foreground">
<span className="bg-primary/10 text-primary">
<div className="bg-muted animate-pulse">  // skeleton
```

Tokens disponibles : `bg-card`, `bg-background`, `bg-muted`, `bg-primary/10`, `bg-destructive/10`, `text-foreground`, `text-muted-foreground`, `text-primary`, `text-destructive`, `border-border`, `border-destructive/30`.

### La marque n'est pas une couleur de thème

Le logo passe par `Logo` de `@/design-system/logo`, en **`currentColor`**, jamais
en `--primary` : les 17 thèmes de `themes.css` repeindraient la marque, qui
serait donc verte chez un foyer et violette chez un autre. La couleur de marque
(`#3F5741`) ne vit que là où le thème ne va pas — favicon, icônes PWA,
`theme_color` du manifeste, aperçu social. Règles d'usage et de marque :
`docs/assets/brand/README.md`. Régressions : `ui/src/design-system/logo.test.tsx`
et `apps/core/tests/test_brand_assets.py` — ce dernier tient aussi la validité XML
des SVG (un `--` dans un commentaire rend le fichier invalide et le logo
invisible, sans un mot) et le fait que les icônes `any` et `maskable` soient deux
**fichiers** distincts, sans quoi Android rogne dans le dessin.

**Une image de marque qui porte du texte se régénère, elle ne se retouche pas.**
`docs/assets/brand/social-preview.png` répète l'accroche et le sous-titre du
`README.md` : c'est un deuxième exemplaire d'un texte, donc ça dérive — et ça a
dérivé dans la journée, le README étant recadré pendant que l'image restait sur
la promesse d'avant. Le texte se corrige dans `scripts/brand/social-preview.html`,
`npm run brand:social` réécrit le PNG, et un test compare la **source du harnais**
au README (`test_the_social_preview_says_what_the_readme_says`) — jamais le PNG,
un pixel ne disant pas ce qu'il raconte. Corollaire général : une image de marque
qu'on ne sait pas refaire **en une commande** ne se corrige jamais, on la garde
parce que la refaire coûte trop cher.

**Ce qui est promis hors du dépôt se vérifie hors du dépôt.** La première ligne du
README — `docker compose up` — dépend d'une image de registre qu'aucun test ne
peut atteindre, et deux réglages GitHub la ferment par défaut (un paquet `ghcr.io`
neuf est privé même poussé depuis un dépôt public ; une politique d'org peut
interdire les paquets publics). Le contrôle consiste à se mettre dans la position
du lecteur — `docker logout ghcr.io && docker pull …` — et non à relire le
workflow. Même famille que « une sauvegarde jamais restaurée n'est pas une
sauvegarde ». Le cours : `docs/fiches/DISTRIBUTION_ET_REGISTRE.md`.

### Montants — un seul formatter

Tout affichage de montant passe par **`formatAmount` de `@/lib/format`** (Intl
devise EUR, locale-aware, option `{ fractionDigits }` pour les montants ronds).
Ne jamais réintroduire un `formatAmount` local ni un `.toFixed() + ' €'` /
`Intl.NumberFormat` inline (dette ② de `docs/fiches/CARTOGRAPHIE_DEPENSES.md`).

```tsx
import { formatAmount } from '@/lib/format';
formatAmount('12.50')                      // « 12,50 € » (fr)
formatAmount(420, { fractionDigits: 0 })   // « 420 € »
```

### Saisie d'un décimal — jamais `<input type="number">`

Le pendant en écriture de `formatAmount` : tout champ portant un décimal (montant,
prix, index de compteur, tarif, quantité, surface) est un **`DecimalInput` de
`@/design-system/decimal-input`**. Les `type="number"` restants sont les
**compteurs entiers**, qui gardent leurs flèches.

```tsx
import { DecimalInput } from '@/design-system/decimal-input';

<DecimalInput value={amount} onChange={setAmount} />              // 2 décimales
<DecimalInput value={index} onChange={setIndex} decimals={3} />   // index compteur
<DecimalInput value={balance} onChange={setBalance} allowNegative />  // découvert
```

- L'état du parent est **canonique** (séparateur point, tel qu'il part vers
  l'API) ; le champ affiche celui de la locale. Donc **plus aucun
  `.replace(',', '.')` au moment du submit** — il y en avait seize, tous morts.
- `onChange` reçoit **la valeur**, pas l'événement.
- Le pas fractionnaire est remplacé par `decimals`, et il **borne la frappe** au
  lieu de la signaler invalide après coup ; `min="0"` est remplacé par le refus du
  moins (`allowNegative` pour un solde, qui peut être à découvert).

**Pourquoi c'est du métier et pas de la plomberie :** le HTML impose au `value`
d'un champ `number` d'être un *valid floating-point number* — le séparateur y est
**toujours** le point. Une virgule rend la valeur invalide, `e.target.value`
renvoie du tronqué, React réécrit ce tronqué dans le DOM et détruit le tampon de
saisie. Taper « 12,5 » sur un clavier français donnait **512 €** sur Chromium et
**5 €** sur Safari et Firefox : pas un champ qui refuse une touche, **un montant
faux enregistré sans un mot**. C'est la règle « un compteur ne peut pas avoir deux
définitions » à l'entrée : ce que l'utilisateur tape et ce que le foyer enregistre
doivent être le même nombre. Régressions : `ui/src/design-system/decimal-input.test.tsx`
(dont le garde-fou « aucun pas fractionnaire dans le front ») et
`e2e/decimal-input.spec.ts` — **le bug n'existait que dans un vrai moteur, jamais
en jsdom : il fallait un test navigateur pour l'attester.**

### Un fichier stocké se télécharge — une PWA installée n'a pas de retour

La section précédente invoquait déjà « en PWA installée aucun geste ne ramène » ;
voici la forme générale de cette phrase. Tout lien vers un fichier du foyer
(`/media/…`) porte **`download`**, jamais `target="_blank"`. Régression :
`ui/src/lib/pwa/stored-file-links.test.ts`.

**Pourquoi c'est du métier et pas de la plomberie :** en mode standalone il n'y a
**pas de barre de navigation**, et `target="_blank"` n'ouvre pas d'onglet — un
fichier servi par `/media/` est same-origin et *dans le `scope` du manifeste*
(`/`), donc la fenêtre de l'app l'honore **sur place**. Le foyer touchait
« Télécharger » sur un PDF et se retrouvait devant le fichier, sans bouton, sans
geste : il fallait fermer l'app. Toute navigation qui sort du SPA est une porte à
sens unique. `PhotoLightbox` portait déjà `download` ; la page document non,
alors que son libellé disait « Télécharger » — l'interface promettait, le clic
démentait.

- **Le scope du manifeste ne peut pas régler ça.** Le réduire à `/app/` sortirait
  aussi `/login`, `/setup`, `/join/:token` et `/z/:token` de l'app : se
  déconnecter éjecterait vers le navigateur. La règle vit donc **au niveau du
  lien**, et c'est le contrôle statique qui la tient.
- **⚠️ Un `<a download>` reste une navigation pour le service worker.** Chromium
  lui passe l'événement en `mode: 'navigate'` ; `templates/sw.js` stockait
  *toute* réponse de navigation réussie comme coquille hors-ligne, donc ouvrir un
  document remplaçait le tableau de bord hors-ligne par le PDF. Deux gardes
  indépendantes, et il faut les deux : `/media/` n'est **pas intercepté**, et
  seule une réponse **HTML** devient la coquille. Sans la seconde, corriger le
  lien reproduisait le défaut ; sans la première, chaque téléchargement
  transiterait par la logique de coquille. Régression :
  `ui/src/lib/pwa/service-worker-shell.test.ts`, qui exécute `sw.js` dans un
  `self` factice — il n'a ni import ni build, donc il est testable tel quel.
- **Le contrôle est statique, et il ne peut pas être autre chose** — même raison
  qu'à la section précédente : le piège n'existe qu'en display-mode standalone,
  que ni jsdom ni un navigateur piloté ne reproduisent (il n'y a pas de chrome à
  retirer dans un onglet). La propriété, elle, est déterministe : c'est un
  attribut, il se lit dans la source. Et **en revue, `target="_blank"` sur un
  fichier ressemble exactement à `download`.**
- Limite assumée, même forme que les clés i18n construites : un `href` qui passe
  par un alias (`const url = doc.file_url`) échappe au contrôle. Ce qui est tenu,
  c'est la forme que le dépôt écrit.

### Dates de calendrier — jamais `toISOString()`

Même règle, pour la même raison. Une date `YYYY-MM-DD` passe par
**`toLocalISODate` / `todayISO` de `@/lib/format`**, jamais par
`new Date().toISOString().slice(0, 10)`.

```ts
// ❌ Interdit — convertit en UTC avant de formater
const from = new Date(y, m, 1).toISOString().slice(0, 10);

// ✅ Correct
import { todayISO, toLocalISODate } from '@/lib/format';
```

**Pourquoi :** `toISOString()` passe en UTC. À Paris, minuit local recule d'un
jour, et tout ce qui se produit entre minuit et 2 h est daté de la veille. Les
quatre périodes de l'onglet Dépenses partaient décalées aux deux bouts (« ce mois-ci »
= 30 juin → 30 juillet), et dix formulaires proposaient « hier » comme date du
jour pendant deux heures chaque nuit. Régression :
`ui/src/features/expenses/period.test.ts`.

Côté serveur, le pendant est `core.timezones` (voir plus bas).

### Le fuseau du foyer — `core.timezones`, et rien d'autre

Toute borne de période, toute notion d'« aujourd'hui », passe par
`apps/core/timezones.py` : `household_tz`, `household_today`, `start_of_day`,
`end_of_day`, `month_range`, `current_month_range`.

- **Jamais `date.today()`** (horloge du serveur, UTC en conteneur) ni
  `timezone.localdate()` (le `TIME_ZONE` du projet, UTC aussi) quand la question
  est « quel jour est-on **chez le foyer** ».
- **Jamais un `try: ZoneInfo(...) except:` local** — le helper existait en six
  exemplaires, et c'est cette dispersion qui a produit le bug ci-dessous.
- **Une date nue en fin d'intervalle vaut fin de journée.** Un `__lte` la lit
  sinon à minuit et exclut le dernier jour de la période.

**Pourquoi c'est du métier et pas de la plomberie :** « ce mois-ci » avait deux
définitions — fuseau du foyer pour le panneau Budgets, UTC pour le résumé des
dépenses. La borne d'un mois décide de quel budget relève un euro, donc cliquer
sur « 340 € / 400 € » pouvait ouvrir une page annonçant 352 €, chacune juste
selon sa propre borne. C'est la règle « un écart ne se dit jamais deux fois avec
deux voix » appliquée à un montant : **un compteur ne peut pas avoir deux
définitions.** Régression :
`apps/interactions/tests/test_period_bounds.py::TestTheTwoScreensAgree`.

### La clôture d'un mois — `core.month_close`, et un délai de grâce

Un mois n'est **clos qu'au 5e jour ouvré du suivant** (`CLOSING_BUSINESS_DAY`).
Tout ce qui demande « quel est le dernier mois clos » passe par
`core.month_close.last_closed_month` : les deux pings mensuels (récap, bilan
budget) et les deux endpoints `latest`.

- **Un snapshot gelé ne se recalcule jamais — donc la date du gel est du métier.**
  Le mois basculait le 1er à minuit, et le premier membre qui ouvrait le dashboard
  ce matin-là figeait le mois pour toujours : le ticket saisi le 3, le relevé
  arrivé le 4 n'entraient jamais dans le récap, sans un mot. Le délai de grâce
  n'existe que pour ça.
- **Décaler le garde-jour d'un ping ne suffit pas** : `latest` gèle avant lui. Une
  date de clôture qui ne vaudrait que pour la notification laisserait l'app se
  contredire elle-même — c'est la même règle qu'au-dessus, appliquée à une date.
- **Jour ouvré = lundi-vendredi ; les fériés ne comptent pas.** Un foyer déclare un
  fuseau, pas un pays : un calendrier de fériés serait une devinette, et une
  devinette sur une date de clôture déplace le rendez-vous sans que personne
  puisse dire pourquoi.
- Conséquence assumée : pendant le délai, `latest` renvoie encore le mois d'avant —
  un récap déjà lu, jamais un récap à moitié gelé.

Régressions : `apps/core/tests/test_month_close.py` et
`apps/recap/tests/test_api.py::TestAMonthDoesNotFreezeBeforeItCloses`.

### Fraîcheur des données — une écriture déclare ce qu'elle écrit, jamais ce qu'elle rafraîchit

Le pendant de la règle du dessus dans le temps : un chiffre juste affiché après
coup est un chiffre faux. Toute la fraîcheur du front tient dans **deux règles,
tenues par `ui/src/lib/invalidate.test.ts`** :

1. **Une mutation vit dans le `hooks.ts` de sa feature.** Une fonction
   d'écriture de `lib/api/` ne s'importe **que** là — un composant qui appelle
   `updateInteraction()` en direct doit redéclarer l'invalidation, et ce doublon
   a dérivé dix fois. Le test refuse l'import.
2. **Le `onSuccess` déclare la racine écrite, pas la liste des caches** :
   `invalidate('tasks')`, via `useInvalidate` de `ui/src/lib/invalidate.ts`. Ce
   qui **dérive** de cette racine est déclaré une fois dans le graphe
   `DERIVED_FROM` du même fichier, et la fermeture est **transitive** — ventiler
   une ligne bancaire crée des dépenses, qui changent le coût d'un projet, qui
   s'affiche sur le dashboard.

**Ajouter un écran qui lit les données d'une autre feature = ajouter sa ligne
dans `DERIVED_FROM`.** Sans elle, l'écran s'affiche juste à sa première écriture
puis mentira jusqu'à la fin du `staleTime`.

**Pourquoi un test et pas une relecture :** le défaut est invisible deux fois. En
revue, le diff d'un `onSuccess` qui oublie une racine ressemble exactement à
celui qui la liste. En développement, Vite recharge le cache à chaque
sauvegarde : l'écran qu'on vient d'écrire est toujours frais chez celui qui
l'écrit. Il ne se voit qu'en prod, et il se dit toujours pareil : « je dois
recharger la page ». Constaté sur l'édition d'une dépense (fournisseur corrigé,
liste inchangée au retour), puis retrouvé sur neuf autres composants, et sur
trois racines que **personne** n'invalidait : `dashboard`, `alerts`, et
`projects` vu depuis l'argent — alors que le coût réel d'un chantier est une
somme de dépenses.

Le `staleTime` de 5 min du `QueryClient` (avec `refetchOnWindowFocus: false`) est
l'**amplificateur**, pas la cause : rien ne rattrape l'oubli avant l'expiration.
Ne pas le baisser pour masquer un cache mal invalidé — ce serait une requête à
chaque montage pour cacher le défaut au lieu de le corriger.

---

## Pattern standard — Feature page

Toutes les nouvelles features doivent suivre ce pattern, établi sur Tasks et Electricity.

### Structure de fichiers

```
ui/src/features/<feature>/
  <Feature>Page.tsx     # page principale
  <Feature>Card.tsx     # card item (ou inline si simple)
  <Feature>Dialog.tsx   # dialog create/edit (ou un par entité)
  hooks.ts              # query keys + hooks fetch/mutation
```

### 1. Data layer (`hooks.ts`)

```ts
// Factory de query keys
export const featureKeys = {
  all: ['feature'] as const,
  list: () => [...featureKeys.all, 'list'] as const,
  detail: (id: string) => [...featureKeys.all, id] as const,
};

// Mutations avec toast + invalidation
export function useCreateItem() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (payload: ItemPayload) => createItem(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: featureKeys.list() });
      toast({ description: t('feature.created'), variant: 'success' });
    },
    onError: () => toast({ description: t('common.saveFailed'), variant: 'destructive' }),
  });
}
```

### 2. Suppression — toujours avec undo

```tsx
const { deleteWithUndo } = useDeleteWithUndo({
  label: t('feature.deleted'),
  onDelete: (id) => deleteMutation.mutateAsync(id),
});
```

### 3. Page principale

```tsx
// Filtres persistés
const [activeFilter, setActiveFilter] = useSessionState<FilterKey>('feature.filter', 'all');

// Skeleton
const showSkeleton = useDelayedLoading(isLoading);
if (showSkeleton) return (
  <div className="space-y-2">
    {[1, 2, 3].map((i) => <div key={i} className="h-14 animate-pulse rounded-lg bg-muted" />)}
  </div>
);

// Layout
<PageHeader title={t('feature.title')}>
  <Button onClick={() => setDialogOpen(true)}>{t('feature.new')}</Button>
</PageHeader>

<div className="flex flex-wrap gap-1.5 pb-4">
  {FILTERS.map((f) => <FilterPill key={f.key} ... />)}
</div>

{isEmpty ? <EmptyState ... /> : <div className="space-y-2">{items.map(...)}</div>}
```

### 4. Cards

```tsx
// Layout standard
<Card className="p-3">
  <div className="flex items-start justify-between gap-2">
    <div className="min-w-0 flex-1">
      {/* contenu principal */}
    </div>
    <CardActions actions={actions} />
  </div>
</Card>
```

### 5. Dialogs (create/edit)

```tsx
interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  existing?: Item;  // undefined = create, défini = edit
}

export default function FeatureDialog({ open, onOpenChange, existing }: Props) {
  const isEditing = Boolean(existing);

  // Reset/init à l'ouverture
  React.useEffect(() => {
    if (!open) return;
    if (existing) {
      setName(existing.name);
    } else {
      setName('');
    }
  }, [open, existing]);
}
```

Boutons du footer — **ne jamais désactiver « Annuler »/« Fermer » pendant
`isPending`** : si la mutation traîne ou reste bloquée, l'utilisateur doit
toujours pouvoir sortir du dialog. Seul le bouton submit se désactive :

```tsx
<Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
  {t('common.cancel')}
</Button>
<Button type="submit" disabled={isPending}>
  {t('common.save')}
</Button>
```

---

## Assistant IA ancré sur une entité (agent générique)

L'agent conversationnel (`apps/agent/`, RAG + function calling) peut être embarqué
dans la vue de détail de n'importe quelle entité, avec **tout le contexte de
l'objet pré-injecté au démarrage** (l'IA connaît déjà l'entité sans chercher).
Première intégration : onglet « Assistant » du détail projet.

### Brancher une nouvelle entité (zone, équipement…)

Une seule ligne côté UI — poser le composant générique dans la vue de l'entité :

```tsx
import EntityAssistant from '@/features/agent/EntityAssistant';

<EntityAssistant entityType="zone" objectId={zone.id} />
```

**Prérequis** : l'entité doit être enregistrée dans `agent.searchables` (via
`apps.py::ready()`). Un `related` sur le `SearchableSpec` enrichit le contexte
injecté (items liés), mais reste optionnel. Aucune modification de `apps/agent/`
n'est nécessaire.

### Sous le capot

- `AgentConversation` porte une ancre optionnelle
  `(context_entity_type, context_object_id)` — mêmes strings que l'adressage des
  tools (`entity_type:id`).
- `EntityAssistant` appelle
  `GET /api/agent/conversations/for_context/?entity_type=&object_id=` qui
  **get-or-create** l'unique conversation `(household, user, entité)` (pas de
  sidebar : 1 conversation persistante par entité et par user).
- À chaque `ask`, `service.ask(..., context_entity=(type, id))` pré-injecte le
  contexte via `agent.context.build_entity_context` (contenu complet + items liés,
  rendu citable) et bascule sur un system prompt ancré : le modèle répond et cite
  directement, sans appeler `search_household` pour l'objet courant.

Doc complète : `docs/MODULES/agent.md` + section « conversation ancrée » de
`docs/fiches/RAG.md`.

---

## Agent — actions d'écriture (`create_entity`)

L'agent peut **créer** des items du foyer depuis le chat via un unique tool
générique `create_entity` (pas un `create_<type>` par entité — on ne gonfle pas le
nombre de définitions de tools). Il est adossé au registry `agent.writables`,
miroir écriture de `agent.searchables`. Entités créables : **tâche**, **note**
(`Interaction` type=note).

### Rendre une nouvelle entité créable (~5 lignes)

Dans le `apps.py::ready()` de l'app, en plus du `SearchableSpec` :

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
- **`create` réutilise le service métier de l'app, jamais l'ORM brut.** Ex.
  `tasks/services.py::create_task` passe par `TaskSerializer` (validation, scope
  foyer, fallback zone racine). Créer un service dédié si absent.
- `create` reçoit l'`anchor` de la conversation ancrée `(entity_type, object_id)`
  → l'utiliser pour pré-remplir un lien (ancre `project` → item lié au projet).
- Étendre aussi la **description** du tool `create_entity` (`apps/agent/tools.py`)
  pour lister les champs de la nouvelle entité.
- **⚠️ L'ancre est un défaut, jamais la seule source d'un rattachement.** Un
  `create` qui ne lit la zone (ou le projet) que dans l'`anchor` est aveugle dans
  l'assistant global — le seul chemin depuis que les onglets « Assistant » ont
  quitté les vues de détail, et où l'ancre vaut toujours `None`. Une note demandée
  « dans la salle de bain » n'atterrissait dans **aucune** zone : `fields['zone']`
  n'était pas lu, et le schéma du tool n'annonçant aucun champ de zone, le modèle
  n'avait rien à remplir. Les deux moitiés comptent — lire `fields` sans le
  documenter ne sert à rien, et l'inverse non plus. Corollaires : la désignation
  **par nom** est la règle (un foyer dit « la chambre », jamais un UUID), via
  `zones.services.resolve_zone` / `resolve_zone_ids` **exclusivement** — un seul
  endroit décide ce que « la chambre » veut dire, et c'est lui qui borne au foyer ;
  ce qui est nommé explicitement **prime** sur l'ancre ; l'ambigu lève un
  `ValueError` qui nomme les candidates plutôt que de ranger au hasard ; et un
  rattachement introuvable **n'écrit rien**, sinon on reproduit le silence d'origine
  avec une confirmation par-dessus. Régression :
  `agent/tests/test_create_entity_zones.py`.

### Sécurité : créer + Undo

Une écriture est un **effet de bord réversible**, pas un brouillon à valider :
l'item est créé immédiatement, remonté dans `metadata.created_entities`, et le
front affiche un toast « Annuler » (`useAgentCreatedUndo`) qui le supprime. Ajouter
l'undo d'une nouvelle entité = une entrée dans `UNDO_HANDLERS`
(`ui/src/features/agent/hooks.ts`). Garde-fous : prompt strict (créer seulement sur
demande explicite) + anti-doublon par tour dans `service.ask`.

Doc complète : `docs/MODULES/agent.md` + `docs/parcours/PARCOURS_07_LOT8_ACTIONS_ECRITURE.md`.

---

## Recherche globale — la barre du haut cherche dans le RAG

La boîte de recherche de la `TopBar` (⌘K, `ui/src/features/search/`) n'a **pas** de
moteur : elle appelle `GET /api/search/?q=`, qui exécute `agent.retrieval.search`.
Enregistrer un `SearchableSpec` rend donc une entité trouvable dans toute l'app sans
une ligne de front. Doc : `docs/MODULES/shell-and-design-system.md` § « Recherche
globale ».

- **Une seule recherche, trois portes.** La palette, le picker « Ajouter du contexte »
  de l'agent et le tool `search_household` passent par
  `agent.search_api.search_household_entities` — même ranking, même payload, même
  gating par modules. Ne jamais rouvrir un second chemin : trouver un document dans la
  barre du haut et s'entendre répondre « je ne le connais pas » dans le chat ne dit
  pas lequel des deux se trompe, ça décrédibilise les deux. C'est la règle « un écart
  ne se dit jamais deux fois avec deux voix » appliquée à la connaissance du foyer.
  Régression : `agent/tests/test_global_search.py::TestTheTwoSearchBoxesAgree`.
- **⚠️ La recherche répond en deux temps, et jamais en un seul appel hybride.**
  `?q=` est l'étape lexicale (quelques requêtes SQL indexées, millisecondes) ;
  `?q=&semantic=1` est l'étape sémantique, qui renvoie **ce que la première n'a pas
  trouvé** (`retrieval.semantic_only`, différence des deux jambes). Raison mesurée sur
  la prod : embedder une requête coûte **211 ms en moyenne, jusqu'à 1,6 s** — attendre
  ça mettrait toute la boîte à cette vitesse et la placerait derrière la disponibilité
  du fournisseur. Conséquences à préserver :
  - l'étape lexicale passe `hybrid=False` **explicitement** et n'hérite pas de
    `AGENT_HYBRID_RETRIEVAL_ENABLED` ; l'étape sémantique, elle, lit le flag et
    renvoie `[]` sans appeler le fournisseur quand il est off ;
  - le serveur renvoie la **différence**, pas la fusion, précisément pour que le front
    **ajoute un groupe sans réordonner ce que l'utilisateur lit déjà** — une liste qui
    se réorganise 200 ms après son apparition fait cliquer à côté ;
  - l'exclusion se calcule **côté serveur** (la jambe lexicale est rejouée, c'est du
    SQL) et jamais depuis une liste de clés envoyée par le client, qui dériverait au
    premier changement de ranking ou de gating ;
  - un échec de l'étape deux n'est **pas** une erreur affichée : les résultats
    mot-clé sont déjà à l'écran et forment une réponse complète.
  Régressions : `test_global_search.py::TestTheSemanticLegIsASecondStage` et
  `::TestTheSecondStageAddsWhatTheFirstCannotFind` côté serveur ;
  `e2e/global-search.spec.ts` pour le non-blocage, qui ne se prouve que dans un vrai
  navigateur.
- **Le surlignage se parse, il ne s'injecte pas.** `ts_headline` renvoie des `<<…>>` ;
  `features/search/highlight.ts` les transforme en segments rendus en `<mark>`. Le
  texte vient du foyer (OCR d'un PDF, note) : un `dangerouslySetInnerHTML` ferait de
  chaque `<` saisi un point d'injection.
- **Ajouter une entité searchable = ajouter son icône et son libellé de groupe**
  (`features/agent/entityIcons.ts`, `search.entity.*` dans les 4 locales). Sans ça le
  nouveau type arrive dans la palette avec un glyphe générique et une clé i18n brute.
  Vérifié depuis Python, seul côté qui connaît la liste des `entity_type` :
  `test_global_search.py::TestThePaletteCoversTheRegistry`.
- **⚠️ Un `url_template` est une promesse d'adresse, et le registre est le seul à
  savoir quels liens l'app fabrique.** Citation de l'agent, résultat de la palette,
  lien du toast « Annuler » : aucun n'est écrit en dur dans le front, donc aucun
  contrôle du front ne les voit — et en revue un template faux ressemble
  exactement à un template juste. Cinq liens morts vivaient en prod :
  `contact`, `structure` et `insurance_contract` visaient des pages de détail qui
  n'ont **jamais existé** (ces modules n'ont que des cartes et un dialogue) → 404 ;
  `tree_event` et `harvest` avaient recopié le template de l'**arbre**, donc la
  page chargeait un `Tree` avec l'uuid d'un événement, n'en trouvait aucun, et
  rendait un écran **blanc**. D'où deux garde-fous, et il faut les deux —
  `test_registry.py::TestEveryLinkTheAgentProducesLandsSomewhere` :
  - le chemin résout vers une route déclarée de `ui/src/router.tsx` (« cette
    adresse existe ») ;
  - un `{id}` **dans le chemin** n'appartient qu'à un seul modèle (« cette adresse
    est à toi ») — sans quoi le premier contrôle passe et la page reste vide.
- **Une entité sans page à elle se redirige, elle ne se décore pas.** Le lien porte
  l'id de l'entité *citée*, jamais celui de son parent : la bonne forme est une
  route qui résout l'entrée et renvoie vers son sujet (`TrackerEntryRedirect`,
  `TreeEntryRedirect`), pas un `?event={id}` sur la page de liste. Un paramètre que
  personne ne lit se recopie dans un favori en promettant le contraire — même
  raison que le `?tab=` de la famille argent.
- **Un `search_fields` ne contient que des champs locaux.** `_search_one` annote
  un `SearchHeadline` par champ et Django refuse un `__` dans un alias
  d'annotation : un `tree__name` ne dégrade pas, il lève.

---

## Sauvegarde — ce qui n'a jamais été restauré n'est pas sauvegardé

Doc : `docs/self-hosting/backup-restore.md`. Régression :
`scripts/test-backup-restore.sh`, rejoué par la CI sur chaque PR et **bloquant
pour une release** (`.github/workflows/backup-restore.yml`, appelé par `ci.yml`
et `release.yml` — un seul texte pour les deux).

- **Une sauvegarde, c'est une paire.** La base **et** le répertoire d'état, qui
  porte la clé secrète et les fichiers téléversés. Les deux archives partagent un
  **horodatage**, et c'est fonctionnel : `restore_db.sh` retrouve la seconde
  toute seule et **refuse** une restauration à moitié tant qu'on n'a pas dit
  `--db-only`. Une base restaurée seule donne une instance dont chaque document
  est référencé et absent, et dont la clé neuve déconnecte tout le monde — le
  tout avec un tableau de bord parfaitement normal.
- **`ON_ERROR_STOP=1` sur tout `psql` de restauration.** Sans lui, `psql`
  continue après une erreur et **sort 0** : une restauration qui se déclare
  réussie en ayant perdu une table est le seul résultat pire qu'un échec.
- **Un refus vaut mieux qu'une restauration partielle.** Le dump contient
  `CREATE EXTENSION vector` ; sur un Postgres nu il échoue à mi-parcours en
  laissant une base à moitié peuplée. `restore_db.sh` vérifie
  `pg_available_extensions` **avant** de vider quoi que ce soit.
- **Le test tient le format, pas la prose.** Une procédure de restauration écrite
  est vraie le jour où on l'écrit ; ce qui la périme (une extension ajoutée au
  schéma, une option de `pg_dump` qui change de sens) ne se voit dans aucune
  relecture. Le test migre un schéma **réel**, sauvegarde, restaure sur une base
  **neuve**, et vérifie le compte de tables, une ligne témoin, l'extension, la
  clé et un fichier. La ligne témoin vit dans une table à elle : l'accrocher à un
  modèle métier ferait rougir le test le jour où ce modèle gagne une colonne
  obligatoire — un rouge qui n'apprendrait rien sur la restauration.
- **Non bloquant pour le deploy, bloquant pour la release.** La prod de l'auteur
  a ses sauvegardes ; bloquer un correctif urgent sur un round-trip ferait payer
  à la production un risque qui pèse sur les instances tierces. Au moment de
  distribuer une image, l'arbitrage s'inverse.
- **Une migration destructive se livre en deux fois** — règle interne du deploy,
  devenue **promesse publique** dès qu'on distribue une image : plus personne ne
  contrôle quand les instances mettent à jour.

---

## Capacités optionnelles — une absence se déclare, elle ne se devine pas

Un foyer qui s'auto-héberge n'a ni clé Anthropic, ni Voyage, ni SMTP, ni VAPID,
ni bot Telegram. Rien ne plantait pour autant — l'agent répondait « je ne sais
pas », la jambe sémantique renvoyait `[]`, l'e-mail partait dans les logs. Le
défaut était ailleurs : **l'interface promettait quand même**, et l'utilisateur
en concluait que le produit était mauvais plutôt qu'il lui manquait une clé.
D'où le registre `app_settings.capabilities`. Doc : `docs/MODULES/app_settings.md`
+ `docs/self-hosting/ai-providers.md`.

- **Ajouter une capacité optionnelle = une entrée au registre + ses clés i18n**,
  aucune modification d'écran. Le `CapabilitySpec` s'enregistre depuis
  l'`apps.py::ready()` de **l'app qui possède le réglage** — même modèle que
  `agent.searchables` et `banking.compliance.REGISTRY`.
- **`available` est un callable, jamais une valeur figée à l'import.** Un
  booléen calculé au chargement gèlerait l'état du premier démarrage, et aucun
  test ne pourrait le simuler par `override_settings`.
- **L'inconnu vaut indisponible** (fournisseur non implémenté, moitié d'une paire
  de clés) — même défaut sûr que `guess_internal`. Une devinette optimiste fait
  promettre à l'écran ce que le premier clic dément.
- **Chaque capacité porte l'ancre d'une section existante** de
  `docs/self-hosting/ai-providers.md`, vérifiée par test : sans ce contrôle le
  lien meurt le jour où il est écrit, et « nécessite une clé Anthropic »
  redevient le mur qu'on voulait supprimer. Le libellé, lui, vit dans le
  namespace i18n `capabilities` du **front** — ajouter une capacité ne doit pas
  imposer un passage dans quatre `.po`. Sa couverture est vérifiée **depuis
  Python**, seul côté qui connaît la liste.
- **Les clés se posent par instance, jamais par foyer** : le `.env` *est* le BYOK
  de l'auto-hébergeur, et l'endpoint `/api/capabilities/` est donc **global**.
  Une saisie de clé dans l'interface ferait de `get_llm_client()` une décision
  d'appelant, ce que `apps/agent/llm.py` interdit. Le payload ne transporte
  jamais une valeur, seulement le nom de la variable.
- **Refuser se dit en 503 nommé** (`capabilities.require`), posé **avant tout
  effet de bord** : un abonnement push ou un tour de conversation que rien ne
  pourra honorer coûte plus cher qu'un refus immédiat. La garde est dans la
  **vue**, pas dans le service — `service.ask` doit continuer à répondre « je ne
  sais pas » à ses appelants non-HTTP (digest, pings), mais servi à travers
  l'API ce même « je ne sais pas » est un mensonge.
- **Une capacité n'a qu'une définition.** Telegram avait déjà son 503 écrit à la
  main, et le front du push déduisait la configuration d'une clé publique vide :
  deux définitions du même test finissent par diverger, et c'est l'utilisateur
  qui arbitre. Tout passe par le registre.

Régressions : `apps/app_settings/tests/test_capabilities.py`,
`agent/tests/test_views.py::TestAnUnconfiguredInstanceSaysSo`.

---

## Notifications — prévenir un foyer passe par `notify_household`

Toute notification de la famille « **un membre a fait quelque chose** » (tâche
cochée, dépense saisie, arrivant dans le foyer) passe par
`notifications.service.notify_household`. Ajouter un émetteur, c'est écrire ce
qu'il dit, pas comment il le diffuse. Doc : `docs/MODULES/notifications.md`.

- **`text` est un callable `() -> (title, body)`, jamais deux strings.** Il est
  appelé une fois par destinataire dans `translation.override(sa locale)`. Le
  texte est stocké en clair (même règle write-time que le `subject` d'une
  `Interaction`) : il n'y a **pas** de seconde chance à l'affichage, donc un
  appelant qui rend sa phrase une seule fois poste à tout le foyer la langue de
  celui qui a agi. Ce bug a vécu en prod dans `stock/notifications.py`,
  invisible parce que la phrase était parfaitement valide — simplement pas dans
  la bonne langue. Régression :
  `stock/tests/test_api_stock_extra.py::TestTheWarningIsWrittenInEachReadersLanguage`.
- **L'`actor` est exclu des destinataires** — on ne notifie personne de sa propre
  action. `actor=None` pour un fait sans auteur (seuil de stock, alerte météo).
- **`url` est porté par la ligne, `_DEEP_LINKS` n'est qu'un fallback.** La famille
  est entité-scopée : « Bob a terminé Tondre la pelouse » doit ouvrir *cette*
  tâche. Une notification qui annonce sans mener fait refaire au lecteur la
  recherche qu'elle venait de faire pour lui.
- **`dedup_key` remplace les anti-doublons maison** (il y en avait trois formes).
  Portée `(user, type, key)` **vivant** : soft-supprimer libère la clé, parce que
  c'est l'utilisateur qui dit qu'il en a fini.
- **Un type se déclare dans `Notification.Type`, sans exception.** `choices` n'est
  pas contraint en base et `.create()` ne fait pas de `full_clean` : une string
  littérale persiste sans broncher, et `weather_alert` a ainsi vécu hors de
  l'affichage admin, hors de `MUTABLE_TYPES`, invisible pour qui lisait la liste.
- **Ce qui est fréquent se coupe, ce qui est actionnable ne se coupe pas.**
  `MUTABLE_TYPES` liste ce que `User.muted_notification_types` a le droit de
  faire taire ; une invitation n'en fait pas partie, et le serializer **refuse en
  400** plutôt que d'ignorer — croire qu'on a coupé une invitation est pire que
  s'entendre dire qu'on ne peut pas. Le filtre vit dans `send()`, pas à l'écran :
  un type qui sort de `MUTABLE_TYPES` doit cesser d'être silencié tout de suite.
- **⚠️ Un émetteur se pose sur un geste, jamais sur un service partagé.**
  `task_created` / `note_created` partent des `perform_create` et des `create`
  des writables de l'agent — jamais de `tasks.services.create_task` ni de
  `interactions.services.create_note_interaction`, qui sont aussi la porte de
  `chickens` (qui a **déjà** son `chicken_chore_due` : on doublonnerait), d'
  `orchard` et de `seed_demo_data` (trois ans de démo dans la cloche). Le critère
  est « un membre vient d'agir », et l'agent en fait partie — il ne crée que sur
  demande explicite, et le laisser muet ferait dépendre la notification du bouton
  utilisé. Corollaires : **ce qui est `is_private` ne sonne pas** (le titre *est*
  le sujet — notifier publierait mot pour mot ce que le drapeau garde, en allant
  chercher le lecteur au lieu d'attendre qu'il regarde), et **le titre se
  tronque** (`varchar(255)` contre un `subject` à 500 : sans `Truncator`,
  Postgres refuse et l'action principale part en 500).
- **Une annonce ne survit pas à son sujet.** Une note se supprime pour de bon là
  où une tâche s'archive et garde sa page : `retract_by_payload` retire l'entrée
  de **toutes** les cloches — non scopé à un utilisateur, puisque l'annonce a été
  fan-outée à tout le foyer et que la retirer chez son seul auteur, qui ne l'a
  justement jamais reçue, ne retirerait rien. À appeler depuis **tous** les
  chemins de suppression, pas seulement celui qu'on a sous la main. Sinon `url`
  promet une adresse et livre un écran mort, que le lecteur ne peut attribuer ni
  à l'app ni à lui-même.

---

## Photos — l'intention est un axe, et le vide n'en est pas une valeur

`Document.purpose` (`technical` / `observation` / `memory`, vide = **non trié**) dit
**pourquoi une photo existe**. Les trois autres axes disent autre chose : la zone dit
*où*, le lien d'entité *sur quoi*, `DocumentLink.phase` *quand dans le chantier* — et
c'est l'intention qui sépare une preuve d'un souvenir. Doc :
`docs/MODULES/documents.md` § « L'intention d'une photo ».

- **⚠️ Le vide n'est pas `memory`.** Vide = personne n'a regardé (un écart, qui alimente
  la file « À trier ») ; `memory` = quelqu'un a choisi. Troisième occurrence du même
  principe après `inflow_nature == ""` ≠ `"other"` et le parcours 26 : *toute entité est
  soit résolue, soit flaggée ; rien ne reste dans un entre-deux silencieux.* Un compteur
  qui les confond annonce « rien à trier » en montrant une photothèque en vrac.
- **Un marqueur s'écrit** : `?purpose=untriaged`. Un `?purpose=` vide répond **400**,
  comme une valeur inconnue — jamais « toutes ». Un paramètre oublié ne doit pas pouvoir
  se lire comme un filtre.
- **Aucun backfill sur un axe que l'utilisateur pose.** Marquer `technical` ce qui est
  lié à un projet écrirait une devinette indistinguable d'un choix (`banking.rules` :
  « des valeurs de départ, jamais des vérités »).
- **Un lot n'écrase jamais un choix déjà posé** : `set_purpose` renvoie `{updated,
  skipped}`, et écraser demande `overwrite: true`. Le tri se fait **par grappe de
  session** calculée à la lecture — une file qui demande trente gestes pour trente
  photos ne se vide jamais, et une file qu'on ne vide jamais cesse d'être lue.
- **Une file bornée le dit** : `total` (ce qui reste) **et** ce que l'écran montre,
  jamais l'un pour l'autre.

Régressions : `documents/tests/test_photo_purpose.py::TestEmptyIsNotAMemory` et
`::TestABatchNeverOverwritesAChoice`, `test_triage_clusters.py`.

---

## Page Tutoriel (`ui/src/features/tutorials/`)

Page `/app/tutorial` (sidebar, section Compte) : checklist « Bien démarrer » +
un guide pas à pas par module. Le contenu est **du code** : registre typé
`content.ts` + prose dans le namespace `tutorials` des 4 locales — aucune table
backend. La progression est une liste de clés opaques sur
`User.completed_tutorials` (validation de forme uniquement : ajouter un guide ne
touche jamais le backend). Les guides adossés à un module (`moduleKey`) héritent
de son icône et sont masqués si le module est désactivé pour le foyer.

**Règle : toute feature qui change le parcours utilisateur met à jour les
tutoriels dans la même PR** — skill `/tutorials` (étape intégrée au skill
`/new-feature`). Doc : `docs/MODULES/tutorials.md`.

---

## Changelog / « Nouveautés » (`apps/releases/`)

Page `/app/admin/changelog` (**réservée au staff/superuser Django**, section Admin
de la sidebar) : liste, à un coup d'œil, ce qui a été livré en prod, avec un résumé
lisible par changement. Alimentée **automatiquement** par le `git log` — pas de
saisie manuelle. C'est de l'infra applicative : modèle **global** (pas
household-scoped), lecture seule via l'API (permission `IsAdminUser`).

### Comment ça marche

- `ChangelogEntry` = un commit user-facing (`feat`/`fix`/`perf`) sur `main`.
- La command `python manage.py generate_changelog` parse le `git log`, extrait
  `type(scope): description (#PR)`, repolit la description via Claude (SDK direct,
  fallback = description brute si pas de clé), et persiste. Idempotent.
- `ChangelogState` (singleton) garde le tip de `main` à la dernière génération →
  carte « Production à jour » en tête de page.
- Le contrat de forme des commits est documenté plus haut (« Format des commits »).

### Générer

```bash
python manage.py generate_changelog            # incrémental (nouveaux commits)
python manage.py generate_changelog --all      # backfill historique complet
python manage.py generate_changelog --dry-run  # aperçu sans écrire ni appeler l'IA
python manage.py generate_changelog --rebuild  # purge + reconstruit
```

**Câblé au déploiement** : le job `deploy` de `.github/workflows/ci.yml` lance
`generate_changelog --from-stdin` après chaque push sur `main` (le conteneur n'a
pas le `.git` : le runner pipe le `git log`). `continue-on-error` — un échec de
génération ne bloque jamais le deploy. Voir `docs/MODULES/releases.md`.
