# Parcours 28 — Ouvrir Maisonnée (open source, auto-hébergeable)

> Cadrage : 2026-07-31. **Chantier technique transverse** — il n'ajoute aucun
> usage métier. Il transforme un déploiement personnel en un **produit que
> quelqu'un d'autre peut installer, comprendre et faire tourner chez lui**.

Comme le parcours 21 (recherche sémantique), celui-ci ne crée quasiment aucune
surface utilisateur nouvelle. Ce qu'il change est ailleurs : jusqu'ici l'app avait
**un** utilisateur qui était aussi son auteur, son opérateur et son support. Après,
elle a des utilisateurs qui ne sont rien de tout ça.

Fiche concept (le cours) : [docs/fiches/AUTO_HEBERGEMENT.md](../fiches/AUTO_HEBERGEMENT.md).
Backlog technique : [PARCOURS_28_BACKLOG_TECHNIQUE.md](./PARCOURS_28_BACKLOG_TECHNIQUE.md).

## Résumé

Le problème que ce chantier résout, du point de vue de quelqu'un qui découvre le
dépôt :

> « J'ai trouvé ton projet et il a l'air d'être exactement ce que je cherche.
> Mais je ne peux pas voir à quoi il ressemble, je ne peux pas l'essayer sans
> lire un guide de déploiement de 400 lignes écrit pour ton VPS, et rien ne me
> dit si j'ai seulement le droit de m'en servir. »

Aucune de ces trois phrases ne parle de la qualité du code. Elles disent que le
dépôt est aujourd'hui **le plan de travail d'un auteur**, pas la **porte d'entrée
d'un produit**. Le `README.md` ouvre sur « backend Django (SSR + API REST) avec
mini-SPA React par page via Vite » — c'est une stack, et personne n'installe une
stack. Il n'y a **aucune capture d'écran** dans tout le dépôt, alors qu'une app
auto-hébergée est impossible à évaluer sans l'installer : les gens décident depuis
les images. Et il n'y a **pas de fichier LICENSE**, ce qui veut dire qu'en droit,
personne n'a l'autorisation d'utiliser ce code.

Ce chantier livre les quatre choses qui manquent — une **installation en une
commande**, une **licence et une gouvernance**, une **façade** (README, captures,
nom), et surtout le **durcissement** qui rend défendable une app qui contient les
relevés bancaires de gens qu'on ne connaît pas — puis s'arrête sur une **recette
par cinq à dix foyers pilotes** avant toute publication bruyante.

## Positionnement produit

Le projet a été construit pour un foyer réel, pas pour un marché. C'est ce qui
l'a rendu bon, et c'est aussi ce qui le rend difficile à vendre : une suite
horizontale, en solo, face à un spécialiste sur chaque axe (YNAB sur le budget,
Bankin' sur la banque, Todoist sur les tâches). La voie retenue n'est donc pas le
SaaS payant mais le modèle **Home Assistant** : publier, auto-hébergeable, et
laisser l'usage désigner le produit.

L'argument qui rend ce chantier court plutôt que long : **le codebase est déjà
écrit comme un projet open source.** Ce n'est pas une reconversion, c'est une
publication. Ce que la plupart des projets doivent construire *après* avoir
décidé de s'ouvrir existe déjà ici :

- un `CLAUDE.md` qui explique le *pourquoi* de chaque règle, adossé à un bug qui a
  réellement eu lieu en prod — c'est un document d'onboarding contributeur, il se
  trouve qu'il s'adresse à une IA ;
- `docs/MODULES/`, `docs/parcours/`, `docs/fiches/` — la doc par module et par
  chantier ;
- des tests de régression **nommés d'après le défaut qu'ils empêchent**
  (`TestTheTwoScreensAgree`, `TestSavingASplitNeverUndoesAReconciliation`) : un
  contributeur qui casse un invariant comprend immédiatement lequel ;
- un déploiement documenté **et testé** (`nginx/test-resilience.sh`, bloquant en
  CI) ;
- un changelog généré depuis le `git log`, avec un contrat de forme de commit déjà
  tenu ;
- quatre langues d'interface et un test de parité des catalogues ;
- une seed de démo **déjà fictive** (`seed_demo_data`, « Famille Mercier »,
  adresses `@demo.local`) — le travail le plus fastidieux d'une démo publique est
  fait depuis longtemps.

La plupart des projets s'ouvrent avec un README et de la dette invisible. Celui-ci
s'ouvre avec le raisonnement conservé.

**Ce qu'on cherche à apprendre.** L'objectif n'est pas d'être installé, c'est
d'être **réutilisé la semaine suivante**. Cent installations et zéro retour en
semaine trois est un résultat négatif, même si le post a bien marché ; dix foyers
qui saisissent encore leurs dépenses au bout de six semaines est un résultat
positif, même si personne n'a rien remarqué. Les étoiles GitHub mesurent la
qualité d'un post. La rétention mesure le produit. Trois questions, dans l'ordre :

1. **Est-ce que ça tient une vraie vie ?** Un autre foyer arrive avec une banque
   dont le CSV n'a pas de colonne solde, une famille de cinq, un compte joint. Les
   invariants du module Argent n'ont jamais été éprouvés hors d'un seul échantillon.
2. **Quel module retient ?** Dix portes ont été construites ; l'usage dira laquelle
   est franchie, et c'est probablement une seule.
3. **Est-ce que le problème existe ailleurs que chez soi ?** La réponse honnête
   peut être non. Ce serait une information qui vaut un an.

## Ce que le chantier change, concrètement

| Question d'un visiteur | Aujourd'hui | Après |
|---|---|---|
| « À quoi ça ressemble ? » | ❌ aucune capture dans le dépôt | ✅ 6 captures + un GIF de l'import d'un relevé qui se ventile |
| « Comment j'essaie ? » | ❌ venv, `pip install -r` ×3, `npm`, deux serveurs, des `.env` | ✅ `docker compose up`, un foyer de démo pré-rempli |
| « J'ai le droit ? » | ❌ pas de LICENSE — donc non | ✅ AGPL-3.0, et l'auto-hébergement est explicitement le cas nominal |
| « Ça fait quoi, au juste ? » | 🟡 un README qui décrit une stack | ✅ un README qui ouvre sur la promesse : *chaque euro est rangé ou signalé* |
| « Je n'ai pas de clé d'API Anthropic. » | 🟡 l'assistant répond « je ne sais pas », mais l'onglet promet quand même | ✅ une capacité indisponible **se déclare**, elle ne se casse pas et ne ment pas |
| « Je n'ai pas de serveur SMTP. » | ❌ l'invitation d'un second membre part dans le vide — le foyer reste à une personne | ✅ lien d'invitation copiable, l'e-mail devient une commodité |
| « Mes relevés bancaires sont dedans. Et si je perds tout ? » | 🟡 un `backup_db.sh` écrit pour un VPS précis, restauration jamais décrite | ✅ sauvegarde et **restauration testée**, documentées pour une machine quelconque |
| « Et si un autre foyer voit mes données ? » | 🟡 le scope `household` protège des membres d'une famille | ✅ il protège de gens qui *cherchent* à passer à travers, et un test générique le vérifie sur chaque endpoint |
| « Ça a l'air de quoi ? » | ❌ une icône clipart : maison blanche sur dégradé bleu, aucun logo dans l'app | ✅ une identité qui tient à 16 px, en monochrome, sur les 17 thèmes |

## Le dehors arrive — et ça change les captures

Deux modules sont annoncés à la suite de ce chantier : **potager** et **élevage**.
Ils ne font pas partie du parcours 28, mais ils en fixent deux contraintes :

- le **nom** ne doit pas enfermer le produit dans le bâti (traité ci-dessus) ;
- les **captures** du lot 6 et le **logo** du lot 8 ne peuvent pas montrer un
  produit d'intérieur. Un tableau de budgets et une liste de tâches racontent un
  gestionnaire de comptes ; ce qui distingue Maisonnée d'un YNAB auto-hébergé,
  c'est que les poules, l'eau, l'électricité et le potager sont dans le même
  registre que l'argent. La vitrine doit montrer ça, sinon elle vend le produit
  générique plutôt que le vrai.

## Le nom : Maisonnée

Le produit publié s'appelle **Maisonnée** — le foyer comme **groupe de personnes**,
pas comme bâtiment. C'est ce que l'app modélise depuis le premier jour
(`Household`, `HouseholdMember`), et c'est ce que « house » ne dit pas.

**Pourquoi un nom de gens et pas un nom de lieu.** La question s'est posée au
cadrage, en voyant arriver les modules **potager** et **élevage** : « maisonnée »
ne rétrécit-il pas le produit au dedans ? C'est l'inverse. Dans l'usage rural, la
maisonnée englobait tous ceux qui faisaient tourner le lieu — le poulailler et le
jardin lui appartiennent parce que c'est elle qui les tient. Et surtout : **un nom
de gens s'étend à n'importe quel module, un nom de lieu se referme.** `Closerie`,
`Enclos`, `Bastide` (tous libres, vérifiés) décrivent un périmètre — et un
périmètre finit toujours par être débordé, par un véhicule, une résidence
secondaire, un contrat. Le dehors est donc porté par la **baseline**, pas par le
nom :

> **Maisonnée** — tout ce qu'un foyer fait vivre. Dedans comme dehors : les
> comptes, les chantiers, les compteurs, le potager, les bêtes.

Le seul défaut assumé est l'accent : `maisonnée` ne peut être ni un nom de dépôt,
ni une image Docker, ni un domaine. On écrit **`maisonnee`** partout où l'on tape,
et les deux orthographes cohabitent — comme *café/cafe*.

Décision de portée, tranchée : **le nom change en façade, pas dans le code.**
README, interface, manifeste PWA, e-mails, image Docker, dépôt : *Maisonnée*. Les
paquets Python (`config/`, `apps/`), la base, les settings et le pipeline de
déploiement gardent `house`. Renommer le code coûterait une réécriture transverse
et un risque de casse sur le déploiement, pour zéro bénéfice utilisateur — un
self-hoster ne lit jamais un nom de module Python.

**Fait le 2026-08-18** : le dépôt est passé de `jammindev/house` à
`jammindev/maisonnee` — dernière pièce de façade qui portait encore l'ancien nom,
alors que l'image (`ghcr.io/jammindev/maisonnee`) et la démo
(`demo.maisonnee.jammin-dev.com`) l'avaient déjà quitté. Deux noms publics du même
produit, c'est la règle « deux définitions qui divergent font perdre leur crédit
aux deux » appliquée à une marque.

Ce que ce renommage a appris, et qui vaut pour tout renommage futur : **trois
`if: github.repository == 'jammindev/house'`** gardaient le job `deploy` de
`ci.yml` et les deux workflows Claude. Une égalité littérale sur le slug ne casse
pas quand elle devient fausse — **elle rend la condition fausse, le job est
sauté, et la CI reste verte.** Un push sur `main` aurait cessé de déployer sans
qu'aucun signal ne l'annonce : exactement la famille de défaut que ce dépôt sort
de l'espace latent. D'où le garde-fou
`apps/core/tests/test_brand_assets.py::TestTheRepositoryHasASingleName`, qui
refuse l'ancien slug hors des trois documents où il est un **fait daté** (ce
fichier, son backlog, le journal de cadrage) et vérifie que chaque littéral
`github.repository ==` nomme le dépôt courant.

## Ce qu'on ne fait pas en V1

Explicitement différé, et pourquoi :

- **Une instance de démo en ligne** (`demo.maisonnee.app`). Meilleur taux d'essai,
  mais un VPS de plus, un cron de remise à zéro, une surface d'abus publique et
  une promesse de disponibilité dès le premier post. Les captures font le travail
  d'évaluation. Une démo tombée le jour du post vaut pire que pas de démo.
- **Toute télémétrie, même anonyme.** Une app auto-hébergée qui appelle la maison
  par défaut trahit la raison pour laquelle on l'auto-héberge. La mesure de la
  rétention passe par **cinq conversations**, pas par un mouchard. Réévaluable
  plus tard, en opt-in franc.
- **Le packaging communautaire** (Unraid, Umbrel, CasaOS, TrueNAS, Helm). Ça se
  mérite après avoir prouvé qu'une installation Docker nue tient chez cinq
  inconnus.
- **La traduction du code et de la doc interne en anglais** — voir la section
  « La langue » ci-dessous, qui documente la mesure et la décision.
- **L'hébergement payant** (séquence Home Assistant → Nabu Casa) et
  **l'agrégation bancaire**. Ce sont les portes de sortie que l'AGPL garde
  ouvertes, pas des chantiers de ce parcours.
- **Un renommage du code en `maisonnee`** — voir ci-dessus.

## Le dépôt est déjà public — depuis dix mois, sans que personne le sache

Constat fait au cadrage : `jammindev/house` est **public depuis le 21 septembre
2025**. Zéro étoile, zéro fork, zéro watcher, **aucune licence**. Le code est
lisible par n'importe qui depuis dix mois ; il n'a simplement jamais été annoncé.

Trois conséquences, et elles réordonnent le chantier :

- **Ce parcours ne « rend pas public » quoi que ce soit.** Il assume une
  exposition qui existe déjà. La question n'est plus *quand ouvrir* mais *quand
  annoncer* — et ce qui doit être vrai avant.
- **Ce qui devait être un prérequis est un retard.** Le durcissement de la CI (un
  runner `self-hosted`, un déclencheur `@claude` payé par l'auteur et actionnable
  par n'importe quel commentateur) et l'absence de `LICENSE` — qui, en droit, veut
  dire *tous droits réservés* — ne sont pas des travaux préparatoires : ce sont
  des écarts ouverts aujourd'hui.
- **Un scoping faible se lit dans le code.** L'instance de production du foyer
  tourne pendant que ses sources sont publiques. Le durcissement multi-tenant
  n'est donc pas une précaution pour de futurs utilisateurs : c'est la protection
  des données réelles du foyer, maintenant.

Le bon côté : **rien n'a été gaspillé.** La règle « on n'a qu'un seul coup par
communauté » est intacte, puisque aucune communauté n'est encore passée.

## La langue : une caractéristique déclarée, pas un défaut caché

La question s'est posée franchement au cadrage — « tout est en français, est-ce
que je ne devrais pas repartir d'un dépôt neuf ? » — et elle mérite d'être
tranchée avec des chiffres plutôt qu'à l'intuition, parce qu'elle reviendra.

**Ce que le dépôt contient réellement** (mesuré le 2026-07-31) :

| Mesure | Résultat |
|---|---|
| Issues (ouvertes + fermées) | **232**, toutes techniques (lots de parcours, bugs) |
| Issues avec image ou pièce jointe | **0** |
| Issues contenant une donnée personnelle | **0** — 8 remontées par la recherche, 8 faux positifs (le mot « adresse » dans « adresse email ») |
| Secrets ou médias dans les 778 commits | **0** |
| Docs citant des données réelles | **2 fichiers**, déjà dans les critères du lot 0 |
| Langue du code | majoritairement **anglais** (structure, noms, docstrings d'en-tête) ; le français apparaît là où le raisonnement se densifie |
| Sujets de commit en français | ~25 % — et ceux-là sont repolis par l'IA pour le changelog public |

**Un dépôt neuf réglerait donc un problème qui n'existe pas, et laisserait intact
celui qui existe** : le code partirait en français à l'identique.

**À qui le français coûte-t-il ?** À des contributeurs, pas à des utilisateurs. Un
self-hoster fait un `docker compose pull` et n'ouvre jamais
`apps/banking/queries.py`. Or l'objectif de V1 est la **rétention de foyers
réels**, pas les pull requests. Ce qui doit être en anglais pour servir cet
objectif l'est déjà dans le plan : README, `CONTRIBUTING`, `SECURITY`, modèles
d'issue — et l'interface parle quatre langues depuis longtemps.

**Ce que le dépôt neuf coûterait**, lui, est mesurable : 778 commits de
raisonnement ; **tous les liens croisés** des docs (chaque backlog dit « ✅ Livré
(PR #333) ») qui deviendraient des liens morts, transformant la documentation en
labyrinthe ; et `generate_changelog`, câblé au job de deploy, qui lit ce `git log`.
Sans compter le signal d'un « initial commit » de 40 000 lignes.

**Décision** : garder le dépôt, et **déclarer** la langue au lieu de la cacher —
une phrase en anglais dans `CONTRIBUTING` (lot 4) désamorce la gêne et dit la
vérité : ce projet vient de quelque part.

> This project was built for one real household, in French. The interface speaks
> English, French, German and Spanish; the internal documentation and some code
> comments are in French. Issues and pull requests in English are welcome.

Si des contributeurs arrivent, traduire des commentaires est **incrémental,
délégable et réversible**. Jeter un historique ne l'est pas.

**Le cadre est écrit, et il tient dans le temps** : le tableau surface par surface
vit dans `CLAUDE.md` § « Langue — l'audience décide, jamais l'habitude », donc il
est chargé à chaque session de travail plutôt qu'oublié dans un parcours.

Il n'a **qu'une frontière** : ce qui est interne (docs, `CLAUDE.md`, commentaires,
**commits**, issues) reste en français ; ce qu'un inconnu lit en premier (README,
`docs/self-hosting/`, `CONTRIBUTING`, `SECURITY`, templates, description du dépôt)
est en anglais, comme les identifiants de code et les noms de tests, qui le sont
déjà. Les commits y sont restés français à dessein : dans ce projet leur lecteur
est d'abord `generate_changelog`, qui les **repolit**, et le contrat n'a jamais
porté que sur la structure `type(scope):`. Exiger la précision dans une langue
étrangère rend un commit plus vague, pas plus lisible.

Une seule bascule est datée : les **nouvelles issues** passent en anglais **le jour
de l'annonce** (lot 7), quand le tracker cesse d'être un carnet personnel pour
devenir un espace partagé. Les anciennes ne se traduisent pas.

**Et l'anglophone n'est pas laissé devant un mur.** Le lot 4 livre
`docs/README.en.md` : pas une traduction, un **index anglais commenté** de la doc
française — pour chaque famille (`CLAUDE.md`, `fiches/`, `parcours/`, `MODULES/`,
`journal/`), ce que c'est et pourquoi ça peut valoir la peine d'aller la lire, au
traducteur automatique s'il le faut. « Tout est en français » devient un menu au
lieu d'une porte fermée, et la page invite explicitement à traduire — c'est
probablement la première contribution utile la plus accessible du projet.

Deux garde-fous rendent cette invitation tenable, et ils sont la règle générale du
projet appliquée aux textes : **le fichier français reste la source de vérité**, et
**une traduction périmée se supprime**. Une traduction que personne ne met à jour
a l'air de faire autorité en étant fausse — c'est « un compteur ne peut pas avoir
deux définitions » transposé à la prose : deux textes qui divergent font perdre
leur crédit aux deux, et celui qu'on lit n'est jamais celui qu'on corrige.

## Le risque assumé

Publier une app qui contient les relevés bancaires, les documents et l'adresse
d'un foyer change la nature des défauts. Un bug de scoping n'est plus « ma femme
voit ma liste de courses », c'est « un inconnu lit mes factures ». Le lot de
durcissement multi-tenant est donc **non négociable et bloquant** : rien ne
s'annonce avant lui.

Le contrepoids est que l'ouverture est aussi ce qui améliore ce point — des yeux
extérieurs sur ce code valent mieux que les seuls yeux de son auteur — et qu'un
`SECURITY.md` avec un canal de signalement fait partie du lot licence pour cette
raison précise.

Enfin : **rien ne presse.** Le projet ne prend l'argent de personne et ne porte
aucune promesse de disponibilité. L'open source n'a pas de date d'échéance, ce qui
autorise à ne pas conclure trop vite — dans un sens comme dans l'autre.
