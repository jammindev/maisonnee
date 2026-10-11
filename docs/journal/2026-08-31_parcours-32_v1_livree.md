# 2026-08-31 — Parcours 32, V1 complète (lots 1 à 5)

> Compte rendu d'implémentation. Ce document dit ce qui a été écrit, **ce qui a
> résisté**, et comment chaque arbitrage a été tranché. Les décisions de *cadrage*
> sont dans [le backlog](../parcours/PARCOURS_32_BACKLOG_TECHNIQUE.md) ; celles-ci
> ont été prises **pendant** l'écriture, et aucune n'était prévue.
>
> ⚠️ **Écrit le 31/08 avant le merge, quand « complète » voulait dire écrite et
> pas déployée.** Les lots 3, 4 et 5 ont été mergés dans la foulée — voir
> « [Suite — le train de merge](#suite--le-train-de-merge-3108) » en fin de
> document, qui porte l'état réel et une neuvième chose qui a résisté.

## Contexte

Parcours 32 — **raconter un chantier plutôt que le remplir**. Le formulaire de
création demandait onze champs (titre, type, priorité, deux dates, budget
prévisionnel, zones…) à quelqu'un qui vient d'avoir l'idée d'une terrasse et ne
connaît aucune de ces réponses. L'assistant mène un entretien, une question à la
fois, puis propose le projet, ses tâches, ses notes et son enveloppe. Rien n'est
écrit avant relecture.

| Lot | Issue | PR | État |
|---|---|---|---|
| 1 — le moteur d'entretien | #653 | **#665** | en production |
| 2 — l'écriture du plan | #654 | **#668** | en production |
| 3 — l'écran et la relecture | #655 | **#672** | en production |
| 4 — l'enveloppe du chantier | #656 | **#675** | en production |
| 5 — les pièces jointes | #657 | **#687** | en production |
| Issue parente **#652** | | | fermée au merge des trois |

Ordre de merge tenu : **#672 → #675 → #687**, sans `--delete-branch` sur les
intermédiaires — supprimer la base d'une PR empilée ferme la suivante. Ce que ça
a coûté est raconté en fin de document.

Différé exprès : **#658** (corriger la façon dont l'assistant construit un
chantier). Il demande de décider *où vit la préférence du foyer* avant d'écrire
une ligne, ce qui est un cadrage et pas un lot.

## Ce qui est livré

**Lot 1 — le moteur.** `projects.assistant.next_step`, un appel par tour, sortie
à deux états (`asking` ou `ready`, jamais les deux), `ValueError` sur toute forme
hors contrat. L'historique voyage dans les arguments : aucune table d'entretiens
abandonnés à purger. Capacité `project_assistant` au registre, throttle dédié
60/h.

**Lot 2 — l'écriture.** `create_project_from_plan`, **une** transaction pour les
trois familles d'objets, et aucun objet créé à la main : `ProjectSerializer`,
`tasks.services.create_task`, `interactions.services.create_note_interaction`.

**Lot 3 — l'écran.** `ui/src/features/projects/assistant/` (dialogue à deux
phases, entretien, champ de réponse typé, relecture), bouton « Créer avec
l'assistant » sur la page Projets, tutoriel du module réécrit.

**Lot 4 — l'enveloppe.** `Project.default_budget`,
`budget.services.resolve_budget_by_name`, la ligne « Enveloppe » de la relecture,
et l'enveloppe pré-sélectionnée à l'achat.

**Lot 5 — les pièces jointes.** Le texte déjà extrait au téléversement entre dans
le contexte, une citation de montant peut être *proposée*, et le chantier créé
porte un `DocumentLink` par pièce.

**Autour.** `docs/MODULES/projects.md` (une section par lot), `PROJ-01` à
`PROJ-14` passées à ✅ avec leur preuve dans `docs/USER_STORIES.md`,
`e2e/project-assistant.spec.ts` (7 tests), tutoriel à jour en quatre langues.

## Soucis rencontrés, et comment ils ont été tranchés

### 1. Résoudre les noms de zones à l'écriture rendait l'erreur invisible

Le contrat du lot 1 rendait des **noms** de zones, que le lot 2 devait résoudre à
la création. Écrit comme ça, une pièce mal nommée par le modèle retombait sur les
zones du projet **après** que l'utilisateur avait validé sa relecture : il ne
pouvait ni le voir ni le corriger. C'est le silence exact que le registre des
writables a supprimé ailleurs dans l'app.

**Tranché** : la résolution remonte au **tour d'entretien**
(`assistant.resolve_plan_references`), et `assistant-create` n'accepte que des
**ids**. Accepter aussi des noms rouvrirait un second chemin de désignation, donc
deux définitions de « la chambre ». Ce qui est relu est exactement ce qui sera
écrit — et c'est cette correction du cadrage qui a fixé la forme du lot 4 (même
traitement pour l'enveloppe) et du lot 5 (les `document_ids` sont résolus avant
l'appel, ce qui est ce qui rend le contrôle de citation possible).

### 2. Un tour raté affichait la question deux fois

L'historique était commité **avant** l'appel au modèle. Quand la réponse était
illisible, la question restait dans l'historique *et* revenait comme question
courante : le même texte, deux fois à l'écran, sans que rien n'ait échoué de
façon visible.

**Tranché** : l'historique n'est commité qu'au succès. Corollaire trouvé dans le
même mouvement — « J'ai assez dit, génère » emporte la réponse en cours si elle a
été tapée, sinon quelqu'un qui saisit son budget puis conclut voit son montant
disparaître et le plan sortir sans budget.

### 3. Les clés de `Document` sont des entiers, pas des UUID

Le cadrage du lot 5 écrivait `document_ids: list[UUID]`. Un `UUIDField` dans le
serializer répond **400 « Must be a valid UUID »** sur une saisie parfaitement
normale : `Document` est l'un des rares modèles du dépôt à clé entière. Et le type
TS `DocumentItem.id: string` **mentait** de son côté — l'API rend un nombre.

**Tranché** : `IntegerField` côté serializer, `Number(...)` local et commenté côté
dialogue, et la nature entière de la clé figée par un test
(`TestADocumentKeyIsAnInteger`) pour que la coercition ne devienne pas un mystère.
Corriger le type TS traverserait tous les écrans documents — hors périmètre,
relevé comme tel.

### 4. Un document d'un autre foyer : 403 ou silence ?

Le critère du backlog demandait un **403**. Écrit, il s'est révélé faux : à ce
point du code, un id d'un autre foyer et un id **supprimé entre l'entretien et la
validation** sont indistinguables. Répondre 403 sur le premier tout en créant sur
le second ferait de l'endpoint un **oracle d'existence** sur la bibliothèque du
voisin, et coûterait la règle « un id inconnu ne fait pas échouer la création ».

**Tranché** : le document est **ignoré**, jamais lu, jamais lié — et l'écart au
cadrage est écrit dans `docs/MODULES/projects.md`. Un cadrage qu'on contredit sans
l'écrire redevient faux en silence.

### 5. La citation d'un montant contredisait l'invariant du lot 1

« Le modèle ne remplit jamais un montant » est l'invariant le plus dur du parcours,
et le lot 5 avait besoin d'une exception : un devis joint *dit* un chiffre.

**Tranché** : l'exception ne tient pas au chiffre, elle tient à la **source
consultable**. `_parse_suggestion` n'accepte une citation que si son `source`
nomme une pièce **réellement jointe à ce tour** — sinon « le devis indique
3 180 € » est une phrase qu'un modèle peut écrire sans avoir rien lu, avec en
prime l'autorité d'une source inventée. Et une citation ne remplit rien toute
seule : elle s'affiche **à côté** du champ, avec un bouton. Un clic, un geste
délibéré. Une suggestion douteuse est **retirée** sans faire échouer le tour :
perdre l'entretien pour un champ facultatif serait disproportionné.

### 6. Une enveloppe de chantier plafonnée aurait pollué tous les mois suivants

Dériver `monthly_amount` de `planned_budget` était tentant et faux : `Budget` est
une enveloppe **mensuelle**, un chantier est un one-shot. Une fois les travaux
finis, la barre aurait affiché « 0 € / 3 200 € » tous les mois pour toujours.

**Tranché** : `monthly_amount=None`. L'enveloppe est un **axe de classement**, pas
un plafond ; le plafond du chantier reste `planned_budget`. Le budget global,
lui, n'est jamais une option — ni dans le contexte du modèle, ni par
`resolve_budget_by_name`, ni par un id venu du client : il ne classe rien, il
plafonne tout, et un modèle à qui on montre une option la choisit un jour.

### 7. Le tutoriel voulait une cinquième étape

Ajouter « créer avec l'assistant » à côté de « créer le projet » aurait fait deux
étapes d'un même geste.

**Tranché** deux fois de la même façon. Au lot 3, l'étape `create` est **réécrite**
pour décrire les deux portes — son ancien texte (« donnez-lui un nom, une
description et un budget prévisionnel ») décrivait exactement la friction que
l'entretien supprime. Au lot 5, une **phrase** est ajoutée à cette même étape pour
les pièces jointes. Créer un projet reste une idée, pas deux.

### 8. Le tableau des user stories est resté entièrement ⬜ pendant trois lots

Le point 6 de la définition de done demandait `docs/USER_STORIES.md` à jour ; les
lots 3 et 4 l'ont sauté. Deux stories (`PROJ-04`, `PROJ-07`) étaient **déjà
prouvées** par des tests qui ne citaient pas leur id — donc invisibles pour la
règle « ✅ seulement quand un test cite l'id », qui se contourne d'elle-même dès
qu'on ne l'applique pas.

**Tranché** au lot 5 : les quatorze lignes passent à ✅ avec leur preuve, et les
deux ids manquants sont cités dans les tests qui les prouvaient déjà. Un tableau
entièrement ⬜ sur une feature complète n'est pas un état, c'est un reliquat.

## Ce qui a résisté sans rapport avec le code

- **Base de test partagée entre worktrees.** Une autre session recréait la base de
  test sans les migrations de cette branche → `column "default_budget_id" does not
  exist`. Contourné par un `TEST_DATABASE_NAME=test_house_p32` dans le `.env.local`
  **de ce worktree** (gitignoré). À généraliser dès qu'une branche porte une
  migration non mergée.
- **Collision de migration `projects/0009`** avec le parcours 33, dont le fichier
  n'était pas commité — donc invisible à un `git ls-tree`. Tranché entre sessions :
  #675 passe en premier, le parcours 33 renumérote en `0010`. #675 est mergée
  depuis, donc **la renumérotation est due** avant que #680 puisse l'être.
- **`gh pr checks` retarde d'environ 30 s sur `gh run list`** : « no checks
  reported » ne veut pas dire « rien ne tourne ». Et une PR **en conflit** n'a
  *aucun* run — GitHub ne calcule pas la ref de merge, donc n'arme pas la CI.
  Changer la base d'une PR émet `edited`, qui n'est pas dans les types écoutés par
  `ci.yml` : il faut `gh pr close && gh pr reopen` pour déclencher `reopened`.

## Suite — le train de merge (31/08)

Les trois PR ont été mergées le soir même, dans l'ordre, en **squash** (c'est ce
que le dépôt avait fait pour les lots 1 et 2). Chaque merge a déclenché son
déploiement ; celui du lot 5 (run `33441328105`) a bien un job
`Deploy to Production` en **`success`**, pas en `skipped` — la distinction a déjà
coûté une demi-journée sur un autre chantier, elle se vérifie à chaque fois.

### 9. Une squash-merge met sa propre PR empilée en conflit

Constaté deux fois, à l'identique. Après le squash de #672, la PR #675 est passée
`mergeable: false / dirty` sur neuf fichiers ; après le squash de #675, #687 en a
eu quatorze. Ce n'est **pas** un désaccord de contenu : le commit d'origine du lot
mergé n'est plus un ancêtre de `main`, donc les fichiers qu'il crée arrivent des
deux côtés en `add/add`, et git ne peut pas savoir que c'est le même travail. Les
catalogues i18n conflictaient en plus pour une vraie raison — d'autres PR y avaient
ajouté des clés entre-temps.

**Tranché** : ne rien arbitrer à la main. Pour chaque fichier en conflit, la
version de `main` (qui porte déjà le lot précédent squashé *et* ce que les autres
PR y ont ajouté), puis le diff du lot courant rejoué par-dessus — quinze lignes de
shell, rejouables. Ce qui rend la méthode sûre est son **contrôle** : le résultat
doit valoir exactement `main` **plus le diff d'origine du lot**, au fichier et à la
ligne près. Lot 4 : 17 fichiers, 721 insertions, 10 suppressions. Lot 5 : 19
fichiers, 1217 insertions, 71 suppressions. Les deux ont coïncidé.

C'est la règle des deux espaces appliquée à un merge : « ce diff est-il le bon ? »
a une réponse **calculable**, et une résolution relue à l'œil sur vingt-trois
fichiers ne l'aurait pas prouvée — un conflit résolu de travers ressemble
exactement à un conflit résolu juste, et c'est du code de production qui part
tout seul derrière. Rejouer les tests après chaque résolution a confirmé :
964 tests serveur, 451 vitest, 7 Playwright, `build` et `lint` verts.

**À retenir pour la prochaine pile** : le conflit n'est pas un accident, c'est la
conséquence mécanique du squash. Il se produira à chaque étage, et il se résout
par un calcul, jamais par un arbitrage.

## Réserves connues, non traitées ici

- **`e2e/COVERAGE.md` ignore `project-assistant.spec.ts`** — comme il ignore les
  specs des parcours 30 et 31. Y ajouter une seule section donnerait à ce catalogue
  une apparence de fraîcheur qu'il n'a plus : à reprendre en entier ou à supprimer,
  dans une issue à part. C'est la règle des traductions périmées appliquée à un
  index — deux textes qui divergent font perdre leur crédit aux deux.
- **`DocumentItem.id` reste typé `string` côté front** alors que l'API rend un
  entier. Borné par une coercition locale et commentée.
- **`POST /api/tasks/tasks/` rend un 500 sur un `zone_ids` inconnu** (défaut
  préexistant, `TaskSerializer.create` fait un `.get()` dont le `DoesNotExist` ne
  se convertit pas). Borné dans ce parcours par `_numbered`, suivi par **#666**.
- **La création n'est pas idempotente.** Le seul garde-fou est le submit désactivé
  pendant `isPending`. Si un double envoi est constaté en usage réel, la suite est
  une clé d'idempotence dans le corps — pas un `get_or_create` sur le titre, qui
  casserait deux chantiers homonymes légitimes.
