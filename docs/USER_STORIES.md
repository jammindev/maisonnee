# Glossaire des user stories

> Le registre unique de ce que House **promet** à un foyer, story par story, et de
> ce qui le **prouve**. Il se complète module par module, au fil des parcours.

## À quoi ça sert

Une user story vit aujourd'hui dans trois endroits qui divergent : la doc produit
d'un parcours, l'issue GitHub d'un lot, et — parfois — un test. Trois copies d'une
même phrase finissent toujours par se contredire, et c'est alors l'utilisateur qui
arbitre. Ce fichier est **la** copie : la doc produit raconte *pourquoi*, l'issue
suit *l'avancement*, le glossaire dit *ce qui est promis et ce qui le vérifie*.

## Les trois règles

1. **Un identifiant stable, jamais réutilisé.** `<MODULE>-<NN>`, ex. `ORCH-04`. Une
   story supprimée garde sa ligne, barrée, avec la raison — un identifiant recyclé
   fait mentir tous les commits qui le citaient.
2. **Une story est vérifiée par un test Playwright qui cite son identifiant** dans
   son titre. Playwright, et pas un test unitaire : une user story est une promesse
   faite au foyer *à travers l'interface et jusqu'à la base*, et c'est la chaîne
   entière qui doit tenir. Les specs seedent par l'API avec le JWT du navigateur,
   puis pilotent l'UI — le test traverse donc le vrai backend.
3. **Une story qu'aucun test ne cite est marquée ⬜, jamais ✅.** Le tableau dit ce
   qui est prouvé, pas ce qu'on croit avoir fait.

> **État — c'est une direction, pas encore un contrat.** Le glossaire démarre avec
> le parcours 30 et se complétera module par module. Le jour où il couvre assez de
> surface pour qu'on s'y fie, il faudra le **tenir par un test** — une spec qui lit
> ce fichier, extrait les identifiants marqués ✅ et échoue si l'un d'eux n'apparaît
> dans le titre d'aucune spec. Sans ce contrôle il deviendra ce que devient toute
> documentation de couverture : un état des lieux d'il y a six mois qui a l'air
> d'être à jour. Tant que le test n'existe pas, **le tableau se relit à la main**,
> et une ligne ✅ n'engage que celui qui l'a écrite.

## Format d'une ligne

| Champ | Sens |
|---|---|
| **ID** | `<MODULE>-<NN>`, stable à vie |
| **Story** | « En tant que … je veux … afin de … », en une ligne |
| **Statut** | ✅ prouvé par un test · 🚧 livré, test manquant · ⬜ pas livré |
| **Preuve** | le fichier de spec, ou `—` |

## Relation avec `e2e/COVERAGE.md`

Les deux ne disent pas la même chose et ne doivent pas se recopier :
`e2e/COVERAGE.md` est une vue **par spec** (« que couvre `tasks.spec.ts` ? »), utile
quand on ouvre un fichier de test ; ce glossaire est une vue **par promesse**. Une
story peut traverser trois specs, une spec peut couvrir zéro story.

---

## Verger (`orchard`) — [parcours 30](parcours/PARCOURS_30_SUIVRE_LE_VERGER.md)

| ID | Story | Statut | Preuve |
|---|---|---|---|
| ORCH-01 | En tant que membre, je veux créer, modifier et supprimer les sujets de mon verger, afin de tenir le registre de ce que je possède | ✅ | `e2e/orchard.spec.ts` |
| ORCH-02 | En tant que membre, je veux que chaque sujet soit rattaché à une zone, afin de retrouver mon verger par l'endroit — et que supprimer une zone occupée me soit refusé plutôt que d'effacer l'historique | ✅ | `e2e/orchard.spec.ts` |
| ORCH-03 | En tant que membre, je veux consigner ce que je fais à un sujet (taille, traitement, observation), afin de m'en souvenir un an plus tard | ✅ | `e2e/orchard.spec.ts` |
| ORCH-04 | En tant que membre, je veux déclarer que « la taille d'hiver, c'est entre novembre et mars », afin de savoir en ouvrant l'app ce que la saison réclame | ✅ | `e2e/orchard-seasons.spec.ts` |
| ORCH-05 | En tant que membre, je veux transformer une règle échue en tâche datée, afin de la voir avec le reste de ce que j'ai à faire | ✅ | `e2e/orchard-seasons.spec.ts` |
| ORCH-06 | En tant que membre, je veux noter combien j'ai récolté et quand, afin de comparer les années | ✅ | `e2e/orchard-harvests.spec.ts` |
| ORCH-07 | En tant que membre, je veux voir ce que chaque sujet a donné année après année, afin de lire une production qui alterne naturellement | ✅ | `e2e/orchard-harvests.spec.ts` |
| ORCH-08 | En tant que membre, je veux être prévenu quand un gel menace des sujets en fleur, afin de pouvoir les protéger la veille | 🚧 | _livré, testé en Python — pas de spec Playwright_ |
| ORCH-09 | En tant que membre, je veux déclarer le prix d'achat d'un arbre, afin de suivre ce que mon verger m'a coûté sans double saisie | 🚧 | _livré, testé en Python — pas de spec Playwright_ |
| ORCH-10 | En tant que membre, je veux attacher des photos à un sujet, afin de le voir changer d'une année sur l'autre | 🚧 | _livré — pas de spec Playwright_ |
| ORCH-11 | En tant que membre, je veux voir l'essentiel du verger sur le dashboard, afin de ne pas rater une fenêtre saisonnière | ⬜ | — |
| ORCH-12 | En tant que membre, je veux interroger l'agent sur mon verger, afin d'obtenir des réponses citées sans naviguer | 🚧 | _livré, testé en Python — pas de spec Playwright_ |
| ORCH-13 | En tant que membre, je veux dicter « j'ai taillé le prunier » ou « note 12 kg de pommes », afin de consigner sans ouvrir l'app | 🚧 | _livré, testé en Python — pas de spec Playwright_ |
| ORCH-14 | En tant que membre non anglophone, je veux le module dans ma langue, afin de l'utiliser comme le reste de l'app | ✅ | `ui/src/locales/keys.test.ts` |

> **ORCH-11 reste ⬜** : l'alerte gel remonte bien dans le résumé d'alertes, mais
> aucune card ne l'affiche sur le tableau de bord. Le module est utilisable sans,
> et le tableau dit ce qui est prouvé — pas ce qu'on aurait aimé livrer.
>
> `ORCH-14` est la seule story de ce module **volontairement** hors Playwright : la
> parité des quatre catalogues et l'absence de `defaultValue` sont vérifiées
> statiquement par `ui/src/locales/keys.test.ts`, qui lit le *code* et pas un rendu.
> Un test navigateur ne dirait rien de plus et manquerait les clés jamais affichées.

---

## Chasse au trésor (`games`) — [parcours 31](parcours/PARCOURS_31_LA_CHASSE_AU_TRESOR.md)

| ID | Story | Statut | Preuve |
|---|---|---|---|
| CHAS-01 | En tant que membre, je veux imprimer une planche d'étiquettes QR, une par pièce, afin d'ancrer mes zones dans la maison en un seul geste | ✅ | `e2e/zone-qr.spec.ts` |
| CHAS-02 | En tant que membre, je veux que scanner l'étiquette d'une pièce m'ouvre cette pièce dans l'app, afin d'atteindre son contenu sans naviguer | ✅ | `e2e/zone-qr.spec.ts` |
| CHAS-03 | En tant que membre, je veux régénérer le jeton d'une pièce, afin de réimprimer une étiquette abîmée ou vue par les joueurs | ✅ | `e2e/zone-qr.spec.ts` |
| CHAS-04 | En tant que parent, je veux composer une chasse — les pièces, leur ordre, les énigmes, le texte du trésor — afin de la préparer avant d'appeler les enfants | ✅ | `e2e/hunt.spec.ts` |
| CHAS-05 | En tant que parent, je veux lancer la chasse et voir l'énigme courante en grand, afin de tendre le téléphone et laisser jouer | ✅ | `e2e/hunt.spec.ts` |
| CHAS-06 | En tant que joueur, je veux que scanner la bonne pièce dévoile l'énigme suivante, afin d'avancer sans qu'un adulte arbitre | ✅ | `e2e/hunt.spec.ts` |
| CHAS-07 | En tant que parent, je veux qu'une mauvaise pièce scannée ne révèle rien et ne fasse pas avancer, afin qu'on ne puisse pas gagner en scannant toute la maison | ✅ | `e2e/hunt.spec.ts` |
| CHAS-08 | En tant que joueur, je veux que la dernière étape révèle où est caché le trésor, afin que la partie ait une fin | ✅ | `e2e/hunt.spec.ts` |
| CHAS-09 | En tant que joueur, je veux que la partie survive à un rechargement et au passage sur un autre téléphone, afin qu'une fausse manœuvre ne l'annule pas | ✅ | `e2e/hunt.spec.ts` |
| CHAS-10 | En tant que foyer, je veux qu'une seule chasse soit active à la fois, afin que deux parties lancées en parallèle ne se mélangent pas | ✅ | `e2e/hunt.spec.ts` |
| CHAS-11 | En tant que parent, je veux demander des énigmes à l'assistant puis les relire et les corriger, afin de préparer une chasse en deux minutes au lieu de vingt | ✅ | `e2e/hunt-riddles.spec.ts` |
| CHAS-12 | En tant qu'auto-hébergeur sans clé Anthropic, je veux que l'écran ne me propose pas la génération et me laisse tout saisir, afin de jouer quand même | ✅ | `e2e/hunt-riddles.spec.ts` |
| CHAS-13 | En tant que parent, je veux rejouer une chasse terminée dans un ordre mélangé, afin de la ressortir sans tout ressaisir | ✅ | `e2e/hunt-replay.spec.ts` |
| CHAS-14 | En tant que foyer, je veux être invité à jouer un week-end pluvieux, afin d'y penser au bon moment | ✅ | `apps/games/tests/test_replay_and_ping.py` |
| CHAS-15 | En tant qu'owner, je veux désactiver le module Jeux, afin que ma sidebar ne porte pas ce que mon foyer n'utilise pas | ⬜ | — |
| CHAS-16 | En tant que membre non anglophone, je veux le module dans ma langue, afin de l'utiliser comme le reste de l'app | ⬜ | — |

> `CHAS-16` suit la même exception que `ORCH-14` : la parité des quatre catalogues
> et l'absence de `defaultValue` sont vérifiées statiquement par
> `ui/src/locales/keys.test.ts`, qui lit le *code* et pas un rendu.
>
> `CHAS-01` est vérifiable jusqu'à l'API (la planche renvoie un SVG par zone), mais
> **la lisibilité d'une étiquette imprimée puis scannée ne l'est pas** : c'est une
> recette manuelle, notée comme telle dans le compte rendu d'implémentation. Un ✅
> sur cette ligne ne couvre que la génération.

## Création assistée d'un chantier (`projects`) — [parcours 32](parcours/PARCOURS_32_RACONTER_UN_CHANTIER.md)

| ID | Story | Statut | Preuve |
|---|---|---|---|
| PROJ-01 | En tant que membre, je veux décrire mon chantier en une phrase et me faire poser des questions, afin de créer un projet sans connaître d'avance le budget ni les dates | ⬜ | — |
| PROJ-02 | En tant que membre, je veux que l'entretien s'arrête de lui-même au bout de six questions, afin qu'il ne s'éternise jamais | ⬜ | — |
| PROJ-03 | En tant que membre, je veux pouvoir couper court à tout moment, afin de générer dès que j'estime en avoir assez dit | ⬜ | — |
| PROJ-04 | En tant que membre, je veux répondre à une question d'argent dans un champ de montant, afin que « 12,5 » enregistre 12,50 € et non 512 € | ⬜ | — |
| PROJ-05 | En tant que membre, je veux que l'assistant me donne un ordre de grandeur sans remplir le champ, afin que le budget inscrit reste le mien | ⬜ | — |
| PROJ-06 | En tant que membre, je veux relire le plan et décocher ce qui ne me sert pas, afin que rien d'inutile ne soit créé | ⬜ | — |
| PROJ-07 | En tant que membre, je veux corriger le titre d'une tâche proposée avant sa création, afin de ne pas avoir à la rouvrir ensuite | ⬜ | — |
| PROJ-08 | En tant que membre, je veux qu'abandonner l'entretien n'écrive rien, afin de pouvoir essayer sans conséquence | ⬜ | — |
| PROJ-09 | En tant que membre, je veux que les tâches et notes créées portent les zones du projet, afin de retrouver mon chantier par l'endroit | ⬜ | — |
| PROJ-10 | En tant que membre, je veux qu'une tâche visant explicitement une autre pièce soit rangée dans cette pièce, afin que l'héritage ne mente pas | ⬜ | — |
| PROJ-11 | En tant que membre, je veux que la création échoue en entier plutôt qu'à moitié, afin de ne jamais hériter d'un chantier incomplet | ⬜ | — |
| PROJ-12 | En tant que membre, je veux une enveloppe budgétaire pour mon chantier, non plafonnée et pré-sélectionnée à l'achat, afin que ses dépenses soient classées sans y penser | ⬜ | — |
| PROJ-13 | En tant que membre, je veux joindre un devis pendant l'entretien et le retrouver sur le projet créé, afin de ne pas le ranger deux fois | ⬜ | — |
| PROJ-14 | En tant qu'auto-hébergeur sans clé Anthropic, je veux que l'écran ne me propose pas l'assistant, afin de créer mes projets par le formulaire sans buter sur une promesse | ⬜ | — |

> `PROJ-04` et `PROJ-05` ne se prouvent qu'en **vrai navigateur** : la première
> parce que le bug qu'elle ferme (« 12,5 » → 512 €) n'existe que dans un moteur
> réel et jamais en jsdom ; la seconde parce qu'un champ vide contre un champ
> pré-rempli est une propriété de l'écran, pas de la réponse HTTP.

---

---

## Modules antérieurs — à rétro-documenter

Les modules livrés avant l'existence de ce glossaire ont leurs user stories dans la
doc produit de leur parcours, et une couverture E2E décrite par spec dans
`e2e/COVERAGE.md`. Les rapatrier ici est un chantier à part : **ne pas les inventer
de mémoire**, les relire dans leur parcours d'origine.

Ordre suggéré, du plus couvert au moins couvert : tâches (parcours 03), zones
(05), projets (04), argent (08/21/25/26), poulailler (14), documents (02),
agent (07).
