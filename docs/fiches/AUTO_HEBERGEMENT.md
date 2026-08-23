# Auto-hébergement — d'un déploiement à un produit installable

> Fiche concept du [parcours 28](../parcours/PARCOURS_28_OUVRIR_MAISONNEE.md).
> Ce qui change quand le logiciel quitte la machine de son auteur : le modèle de
> menace, le contrat de licence, et la différence — beaucoup plus large qu'elle
> n'en a l'air — entre *déployable* et *installable*.
>
> **Mise à jour.** Les sections 1 à 3 ont été écrites au cadrage, avant le code ;
> elles disent maintenant ce qui **existe**, lot par lot. La section 4 est
> nouvelle : elle rassemble ce que l'implémentation a appris et que le cadrage
> n'avait pas pu voir — c'est la partie qu'on ne peut écrire qu'après.

## 1. Le problème

Maisonnée tourne en production depuis des mois. Le déploiement est documenté
(`DEPLOYMENT.md`), testé (`nginx/test-resilience.sh`, bloquant en CI), résilient
(le proxy ne tombe pas avec l'app). On pourrait croire le travail fait.

Il ne l'est pas, parce que **tout ce déploiement s'exécute avec son auteur dans la
boucle**. Il suppose un VPS choisi, un domaine à soi, un `.env` rempli à la main,
des clés d'API souscrites, un serveur SMTP, une base déjà migrée, et surtout
quelqu'un qui sait *ce qu'il voulait obtenir*. Aucune de ces conditions n'est
vraie pour un inconnu.

Trois questions distinctes, qu'on confond facilement :

- **Est-ce que ça se déploie ?** Oui, depuis longtemps — par son auteur.
- **Est-ce que ça s'installe ?** C'est-à-dire : quelqu'un sans contexte
  obtient-il une app qui marche, sans lire le code ni deviner une valeur ?
- **Est-ce que ça s'exploite ?** C'est-à-dire : cette personne peut-elle la
  mettre à jour, la sauvegarder, la **restaurer**, et comprendre ce qui casse ?

Les trois demandent des livrables différents. La deuxième est un problème de
valeurs par défaut. La troisième est un problème de documentation *et* d'outils.

## 2. Le concept en deux phrases

**Auto-héberger, c'est transférer à l'utilisateur le rôle d'opérateur** — donc
tout ce que l'auteur savait sans l'écrire doit devenir soit une valeur par défaut
qui marche, soit une question posée explicitement, soit une page de documentation.

Et comme ce transfert expose le logiciel à des réseaux et à des gens que son
auteur n'a pas choisis, il change aussi le **modèle de menace** : d'un logiciel
qui sépare les membres d'une famille de bonne foi, on passe à un logiciel qui doit
résister à quelqu'un qui *cherche* à passer à travers.

## 3. Comment on l'applique dans Maisonnée

### 3.1 Le défaut est l'interface

Un self-hoster ne lit pas la doc avant de lancer la commande, il la lit **quand
ça casse**. Chaque valeur qu'il doit fournir avant d'avoir vu l'app est un endroit
où il abandonne. D'où la règle du parcours : **`docker compose up` sur une machine
nue doit donner une app fonctionnelle**, avec un `SECRET_KEY` généré au premier
démarrage plutôt que réclamé, une base incluse, les migrations appliquées et un
foyer de démonstration déjà rempli (`seed_demo_data`, « Famille Mercier », déjà
fictive depuis le début).

Ce qui reste à saisir — un domaine, un mot de passe — se demande **après** que la
personne a vu de quoi il s'agit.

### 3.2 Une capacité absente se déclare ; elle ne se casse pas et elle ne ment pas

Maisonnée s'appuie sur des services tiers : Claude pour l'assistant, le récap et
le changelog, Voyage pour les embeddings, un SMTP pour les e-mails, VAPID pour le
push, Telegram pour le canal bot. Un foyer qui s'auto-héberge n'a **aucun** de
ces comptes le premier jour, et n'en aura peut-être jamais.

Il y a trois façons de traiter ça, et une seule est acceptable :

- **planter** — l'app ne démarre pas sans clé : disqualifiant ;
- **faire semblant** — l'onglet Assistant s'ouvre, la question part, la réponse
  est « je ne sais pas ». C'était l'état avant le lot 3 : `agent.service.ask`
  dégradait proprement, mais l'interface promettait quand même quelque chose
  qu'elle ne pouvait pas tenir. L'utilisateur en conclut que le produit est
  mauvais, pas qu'il lui manque une clé ;
- **déclarer** — le serveur dit ce dont il est capable, l'interface s'aligne, et
  l'endroit où la capacité manque explique comment l'obtenir.

C'est la même règle que la conformité de l'argent, transposée à la configuration :
**un zéro a deux sens** — « rien à dire » et « rien d'évaluable » — et les
confondre produit un silence qu'on prend pour une réponse.

C'est la troisième qui a été retenue (lot 3) : le registre
`app_settings.capabilities`, alimenté depuis l'`apps.py::ready()` de l'app qui
possède le réglage — `app_settings` ne connaît pas la liste —, exposé par
`GET /api/capabilities/`, et adossé à `docs/self-hosting/ai-providers.md` dont
**chaque ancre est vérifiée par un test**. Sans ce contrôle, le lien meurt le
jour où il est écrit et « nécessite une clé Anthropic » redevient le mur qu'on
voulait supprimer.

Un cas mérite d'être isolé parce qu'il n'est pas cosmétique : **sans SMTP,
l'invitation d'un second membre part dans le vide.** Un « système d'exploitation du
foyer » qui ne peut pas dépasser une personne n'est pas dégradé, il est inutile.
L'invitation doit donc produire un **lien copiable** ; l'e-mail n'en est que le
véhicule de confort. *(Livré avant le lot 3, et pas par lui — voir § 4.1.)*

### 3.3 Le modèle de menace change de nature

Le scope `household` traverse 33 apps. Aujourd'hui il sépare des gens qui vivent
sous le même toit ; publié, il sépare des inconnus dont l'un peut être hostile.
Trois zones concentrent le risque, parce qu'elles contournent le chemin normal :

- **les FK polymorphes** (`Interaction.source`, `resolve_allocation_source`,
  `EmbeddingChunk`) — un identifiant arbitraire y désigne un objet d'un autre
  foyer si personne ne revérifie ;
- **l'agent**, dont les tools s'adressent en `entity_type:id` et qui *écrit*
  (`create_entity`) ;
- **les fichiers** (`core/views_media.py`) — un document servi par son chemin
  n'est protégé que par ce que fait cette vue.

Le livrable qui compte ici n'est pas un audit : un audit est vrai le jour où il
est fait. C'est un **test générique** qui parcourt le routeur DRF et vérifie,
pour chaque endpoint enregistré, qu'un foyer B ne lit ni n'écrit rien du foyer A.
Ajouter un endpoint, c'est alors le faire passer sous ce test sans y penser —
même logique que `banking.compliance.REGISTRY` (« ajouter un mécanisme à l'argent
= ajouter son détecteur ») ou que le test de parité des catalogues i18n.

Livré au lot 1 (`apps/core/tests/test_tenant_isolation.py`), étendu à l'écriture
au lot 1bis (`test_write_isolation.py`, et le plancher
`HouseholdScopedPrimaryKeyRelatedField` qui borne un champ relationnel au foyer).
Ce qui reste ouvert est **nommé** plutôt que supposé sûr : les
`@action(detail=True)` et les `APIView` sans queryset, que le test générique ne
peut pas voir, sont recensées dans `docs/MODULES/security.md`.

### 3.4 La sauvegarde est une fonctionnalité, pas une consigne

Les gens vont mettre leurs relevés bancaires, leurs factures et leurs contrats
d'assurance dedans. Sur un VPS d'auteur, une sauvegarde ratée se rattrape. Chez
un inconnu, elle ne se rattrape pas et c'est le logiciel qu'on accuse.

Donc : une commande de sauvegarde qui marche sans contexte, une procédure de
**restauration écrite et vérifiée** (une sauvegarde jamais restaurée n'est pas une
sauvegarde), et la règle déjà tenue en interne — **une migration destructive se
livre en deux fois** — devient une promesse publique de compatibilité, puisque
personne ne contrôle plus quand ses utilisateurs mettent à jour.

Livré au lot 5 : `backup_db.sh --state-dir`, `restore_db.sh`, et
`scripts/test-backup-restore.sh` — rejoué à chaque PR, **bloquant pour une
release**, informatif pour le deploy.

### 3.5 La promesse d'installation vit hors du dépôt

Le README ouvre sur trois lignes dont la deuxième est `docker compose up`, et
cette ligne ne dépend d'**aucun fichier du dépôt** : elle dépend d'un artefact
hébergé dans un registre, sous un modèle de permissions qui n'a rien à voir avec
celui du dépôt. C'est le seul énoncé du projet qu'aucun test ne peut tenir.

D'où la règle, qui prolonge exactement celle du § 3.4 : *une promesse dont la
vérité vit hors du dépôt se vérifie **de dehors**, dans la position du lecteur* —
en tirant l'image sans être authentifié, jamais en relisant le workflow qui la
pousse. Le détail (index multi-architecture, tag contre empreinte, et les trois
étages de permissions de GitHub Packages, dont deux fermés par défaut) est dans
sa propre fiche : [DISTRIBUTION_ET_REGISTRE.md](DISTRIBUTION_ET_REGISTRE.md).

## 4. Ce que l'implémentation a appris

Les trois sections précédentes ont été pensées avant d'écrire une ligne, et elles
ont tenu. Ce qui suit ne pouvait pas s'écrire à l'avance : chaque point vient d'un
moment où le code a démenti le plan, ou l'a dépassé.

Deux leçons de cette famille ont leur propre fiche parce qu'elles dépassaient le
paragraphe — la construction multi-architecture et la visibilité d'un paquet
publié : [DISTRIBUTION_ET_REGISTRE.md](DISTRIBUTION_ET_REGISTRE.md).

### 4.1 Un cadrage a une date de péremption

Le lot 3 déclarait **bloquant** le fait que, sans SMTP, on ne puisse pas inviter
un second membre. Au moment de le corriger, c'était déjà fait : un correctif sans
rapport, un mois plus tôt, avait introduit le lien `/join/<token>` et la création
de compte depuis ce lien. Le point le plus grave du lot s'était résolu ailleurs,
sans que le plan le sache.

La conséquence n'est pas « le cadrage était mauvais » — il avait raison sur le
fond, et c'est bien pour cette raison que quelqu'un l'avait corrigé entre-temps.
C'est qu'**il faut vérifier l'état réel avant de coder ce qu'on a spécifié**, sous
peine de réécrire ce qui existe. Ce que le lot a fait à la place : le
**documenter** comme la voie normale. Un chemin qui existe mais que personne ne
connaît ne rattrape rien.

### 4.2 Gater ce qui marche annonce cassé ce qui ne l'est pas

Le plan listait l'écran du récap parmi ceux à masquer sans clé d'IA. Or sans clé,
le récap **sort quand même** : les chiffres sont justes, les phrases sont
seulement plus sèches. Y poser un bandeau « nécessite une clé » aurait fabriqué
exactement le malentendu que le lot existait pour supprimer.

D'où une règle plus fine que « masquer ce qui dépend d'un tiers » : **on ne
déclare indisponible que ce qui l'est**. Une capacité de confort se dit dans la
liste des réglages — qui répond à la question de celui qui installe, *qu'est-ce
qui dort ici ?* — et pas sur l'écran, qui répondrait à une question que personne
ne se pose.

### 4.3 Un état de configuration ne peut pas avoir deux définitions

En câblant le registre, deux définitions concurrentes de « configuré » sont
apparues, chacune écrite de bonne foi à un endroit différent :

- Telegram avait **son propre 503**, écrit à la main dans la vue ;
- le front du push déduisait « configuré » d'une **clé publique vide** — le
  serveur répondait 200 en portant une réponse qu'il connaissait déjà, et l'échec
  réel arrivait après le clic, sous la forme d'un `InvalidAccessError` que
  personne ne peut lire.

C'est le corollaire direct de la règle déjà écrite pour l'argent — *un compteur ne
peut pas avoir deux définitions* — appliquée à la configuration. Deux textes qui
disent la même chose finissent par diverger, et c'est l'utilisateur qui arbitre.

### 4.4 Ce qu'on ne déclare pas, la plateforme l'a déclaré pour nous

`EMAIL_BACKEND` n'était posé nulle part dans `base.py`. Le défaut de Django est
donc resté : SMTP sur `localhost:25`. Tout module de réglages qui ne le
surchargeait pas envoyait ses e-mails vers un serveur inexistant, et l'échec
tombait **au moment de l'envoi**, loin de l'écran qui l'avait promis.

Un défaut non déclaré n'est pas une absence de décision : c'est une décision prise
par quelqu'un d'autre, souvent raisonnable pour son contexte et rarement pour le
nôtre.

### 4.5 Une sauvegarde est une paire, et l'appariement doit être mécanique

Le plan disait « inclure `media/` ». L'implémentation a montré que la bonne unité
n'est pas `media/` mais le **répertoire d'état**, qui porte les fichiers *et* la
clé secrète. Les deux se perdent ensemble ou pas du tout : une base restaurée
seule donne une instance dont chaque document est référencé et absent, et dont la
clé neuve déconnecte tout le monde — le tout avec un tableau de bord parfaitement
normal.

Et il ne suffit pas de le documenter. Les deux archives partagent un
**horodatage**, ce qui permet à `restore_db.sh` de retrouver la seconde tout seul
et de **refuser** tant qu'on n'a pas dit `--db-only`. Une consigne se contourne
par distraction ; un appariement mécanique, non.

### 4.6 Un outil peut réussir en ayant échoué

`psql` continue après une erreur et **sort 0**. Sans `ON_ERROR_STOP=1`, une
restauration se déclare réussie en ayant perdu une table — le seul résultat pire
qu'un échec, parce qu'il ne déclenche aucune enquête.

Même famille : `restore_db.sh` refuse de **commencer** quand l'extension `vector`
manque sur la cible, plutôt que d'échouer à mi-parcours en laissant une base à
moitié peuplée. Quand l'échec partiel est pire que l'échec total, le bon moment
pour vérifier est avant d'avoir rien détruit.

### 4.7 Un test qui garde un format ne doit pas dépendre du métier

La première version du test de restauration insérait sa ligne témoin dans la table
des foyers. Elle a cassé tout de suite — cette table porte un `db_table`
personnalisé — et elle aurait recassé au premier champ obligatoire ajouté au
modèle : un rouge qui n'apprend **rien** sur la restauration.

La ligne témoin vit donc dans une table à elle. Le schéma réel reste
intégralement sauvegardé et restauré ; ce sont le compte de tables et la présence
de l'extension qui l'attestent. **Un test doit dépendre de ce qu'il garde, et de
rien d'autre** — sinon il devient une taxe qu'on finit par désactiver.

### 4.8 Une porte de secours non exercée n'existe pas

Le workflow de release portait depuis le lot 2 une entrée `workflow_dispatch`
pour « republier une image sans re-tagger ». La première fois qu'on en a eu
besoin, elle ne marchait pas : elle nommait l'image d'après la branche de
déclenchement et non d'après le tag demandé, si bien que republier `v0.1.0`
aurait poussé une image appelée `main`.

Le chemin de secours n'avait jamais été emprunté, donc il n'avait jamais été
faux — jusqu'au jour où il fallait s'en servir. Écrire une porte de sortie et ne
pas l'ouvrir une fois, c'est écrire un commentaire, pas un mécanisme.

### 4.9 Les réglages de test décrivent une instance, et il faut choisir laquelle

Poser le garde de capacité sur les endpoints de l'agent a fait tomber vingt-six
tests d'un coup. Aucun n'était faux : les réglages de test décrivaient une
instance **sans clé**, et ces tests mesuraient donc le refus au lieu du
comportement qu'ils vérifiaient.

Le choix — décrire une instance **configurée**, et tester l'absence de clé là où
c'est précisément le sujet — est un choix qu'il faut faire explicitement. Une
suite de tests est un environnement d'exécution ; laisser ses défauts se décider
par accumulation, c'est finir par mesurer autre chose que ce qu'on croit.

### 4.10 Un artefact fantôme coûte ses explications

Un tag `v1.0.0` traînait depuis un an, posé à la main sur un commit de
configuration TypeScript sans rapport. Rien ne le lisait — le changelog est
adossé au `commit_sha`, `package.json` était resté à `0.0.0`. Publier `v0.1.0`
derrière lui n'aurait rien cassé, mais aurait fait croire à un lecteur qu'il
avait raté une étape. Il a été supprimé.

**Un artefact que personne ne lit et qui désigne autre chose que ce que son nom
annonce ne vaut pas les explications qu'il coûte.**

### La forme qui revient

La moitié des points ci-dessus sont le même défaut : **quelque chose réussit alors
que rien ne marche.** Le dump se charge à moitié en sortant 0, l'abonnement push
s'enregistre sans pouvoir notifier, l'e-mail part vers `localhost:25`, la
republication nomme son image `main` — et, au § 3.2, l'assistant répond « je ne
sais pas » sans avoir de clé. Les deux cas de la fiche voisine sont de la même
famille : une image publiée sans avoir jamais démarré, un paquet publié qui répond
`denied`.

C'est la signature du passage de *déployable* à *installable*. Sur la machine de
son auteur, chacun de ces silences est rattrapé par quelqu'un qui sait ce qu'il
attendait. Chez un inconnu, personne ne sait — et le logiciel est jugé sur ce
qu'il a l'air de faire, pas sur ce qu'il fait.

D'où l'orientation de ces lots, et la seule phrase à retenir si on n'en garde
qu'une : **transformer chaque silence en phrase, et chaque phrase en test.**

## 5. Pourquoi cette implémentation — décisions et trade-offs

**AGPL-3.0 plutôt qu'une licence permissive.** Le copyleft *réseau* — l'obligation
de publier ses modifications quand on **héberge** le logiciel pour d'autres, pas
seulement quand on le distribue — est la seule qui corresponde à un produit dont
l'usage normal est d'être hébergé. Elle laisse l'auto-hébergement totalement libre
(un foyer n'est pas un public), elle n'empêche pas l'auteur de vendre un
hébergement puisqu'il détient seul le copyright, et elle empêche un tiers de
fermer une version hébergée du travail. C'est la licence de Nextcloud, Mastodon,
Immich. Le coût : quelques entreprises l'interdisent par politique interne — un
non-sujet pour un logiciel domestique.

**Le dépôt existant devient public, historique compris.** 778 commits, 9,7 Mio,
aucun secret ni média jamais commité (`.env*` et `media/` sont ignorés depuis le
début). Cet historique est le seul élément qu'un visiteur ne peut pas fabriquer :
il montre le raisonnement, les corrections, les tests nommés d'après le bug qu'ils
empêchent. Un « initial commit » de 40 000 lignes envoie le signal inverse — du
code jeté par-dessus un mur — et remettrait à zéro un changelog dont la génération
lit précisément ce `git log`.

**Le nom change en façade seulement.** *Maisonnée* pour le produit, `house` pour
les paquets Python et la base. Un renommage transverse coûterait une réécriture et
un risque de casse au déploiement, pour un bénéfice nul : personne n'installe un
logiciel en lisant ses noms de modules.

**Pas de télémétrie, même anonyme.** Une app auto-hébergée qui téléphone chez elle
par défaut contredit la raison pour laquelle on l'auto-héberge. La question à
laquelle on veut répondre — *est-ce que les gens reviennent ?* — se traite par cinq
conversations avec des foyers pilotes. Un utilisateur qui abandonne ne laisse
aucune trace exploitable de toute façon : l'analytique dit qu'il est parti, jamais
pourquoi.

**Pas de démo en ligne en V1.** Le taux d'essai serait meilleur, mais ça ajoute un
serveur, un cron de remise à zéro, une surface d'abus et une astreinte implicite
le jour même du lancement. Les captures d'écran couvrent 90 % du besoin
d'évaluation pour 0 € par mois.

**L'ordre est un livrable à part entière.** On n'a **qu'un seul coup par
communauté** : trente personnes qui tombent sur une installation cassée partent et
ne reviennent pas, et on ne reposte pas. D'où la séquence imposée — installation
qui marche, puis façade, puis **cinq à dix foyers en privé** dont on corrige les
plantages, et *seulement ensuite* les canaux publics.

## 6. Ce qu'on a écarté et pourquoi

- **Ne publier que le module Argent.** C'est la seule partie avec une promesse que
  personne d'autre ne tient (*chaque euro est rangé ou signalé avec un motif*), et
  ce serait le bon découpage pour *vendre*. Mais en auto-hébergé, la suite est un
  atout : le module poules-et-œufs à côté d'un moteur de rapprochement bancaire
  est exactement ce qui fait qu'un projet est **aimé** plutôt que toléré — il dit
  qu'il a été écrit pour un foyer réel.
- **Un CLA** (transfert de droits par les contributeurs). Utile seulement pour
  relicencier plus tard ; c'est une friction immédiate contre une option lointaine.
  On retient le **DCO** (`Signed-off-by`), qui atteste l'origine sans rien céder.
- **Réécrire l'historique** (`git filter-repo`) « par précaution ». Une réécriture
  sans fuite à supprimer détruit un actif pour traiter un risque déjà mesuré comme
  nul. La vérification, elle, reste obligatoire : un scan de secrets sur les 778
  commits, pas seulement sur l'arbre courant.
- **Vendre un SaaS tout de suite.** Une suite horizontale construite en solo est
  la chose la plus difficile à vendre qui soit, et chaque axe affronte un
  spécialiste. L'ouverture construit une audience et une crédibilité sans porter la
  DPA, la TVA de vingt-sept pays, ni le support téléphonique de gens dont on
  détient les relevés bancaires.
- **Traduire le code et la doc interne en anglais.** `CLAUDE.md` et `docs/` valent
  par la fidélité du raisonnement conservé. Une traduction figée qui dérive vaut
  moins qu'une doc vraie en français, et l'interface est déjà en quatre langues.

## 7. Pour aller plus loin

- [Choose a License — AGPL-3.0](https://choosealicense.com/licenses/agpl-3.0/) — le
  texte et ses obligations en clair.
- [Developer Certificate of Origin](https://developercertificate.org/) — les onze
  lignes du DCO.
- [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) —
  critères d'entrée : licence, doc d'installation, captures.
- [Home Assistant](https://github.com/home-assistant/core) puis
  [Nabu Casa](https://www.nabucasa.com/) — la séquence de référence : projet
  auto-hébergé d'abord, hébergement payant ensuite, pour ceux qui ne veulent pas
  gérer un serveur.
- [Immich](https://github.com/immich-app/immich) — comparable en nature (données
  personnelles très sensibles, AGPL, install Docker en une commande) ; son
  `docker-compose.yml` et sa page « backup & restore » sont de bons modèles.
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
  — grille de vérification pour le lot de durcissement.

---

Fiches connexes : [DISTRIBUTION_ET_REGISTRE.md](DISTRIBUTION_ET_REGISTRE.md) et
[DEPENDANCES_ET_PAQUETS.md](DEPENDANCES_ET_PAQUETS.md) (nées du même parcours :
ce qui se passe une fois l'image publiée, et ce qu'on exécute sans l'avoir
écrit), [CARTOGRAPHIE_DEPENSES.md](CARTOGRAPHIE_DEPENSES.md) (ce que le
durcissement doit protéger côté argent), [RAG.md](RAG.md) et
[EMBEDDINGS.md](EMBEDDINGS.md) (les capacités qui dépendent d'une clé d'API tierce).
