# Parcours 33 — Ce qui est privé le reste

> `is_private` existe depuis l'origine sur quatre modèles. Aucun ne le tient de
> bout en bout, et le cinquième que l'usage réclame — le projet — ne l'a pas du
> tout. Ce parcours **finit** le drapeau avant de l'**étendre**.

- Fiche concept : [CONFIDENTIALITE.md](../fiches/CONFIDENTIALITE.md)
- Backlog technique : [PARCOURS_33_BACKLOG_TECHNIQUE.md](./PARCOURS_33_BACKLOG_TECHNIQUE.md)
- Issue ombrelle : [#660](https://github.com/jammindev/maisonnee/issues/660)

## Résumé

> « Je prépare une surprise pour Bob. » — et l'app l'affiche dans la liste de Bob.

Un foyer n'est pas une équipe : il partage presque tout, et c'est le presque qui
compte. Le cadeau d'anniversaire, le bilan médical, le devis qu'on ne montrera
qu'une fois arbitré. House avait la bonne intuition dès le départ — un drapeau
`is_private` sur les tâches, les documents, les notes et les briefings — mais le
drapeau n'a jamais été tenu partout où il fallait, et personne ne pouvait le voir :
il faut **deux comptes dans le même foyer** pour s'en apercevoir, c'est-à-dire
exactement ce qu'un développeur seul n'a jamais sous la main.

Ce parcours ferme les portes ouvertes, se dote d'un registre qui empêche la
prochaine de s'ouvrir, donne enfin une interface au drapeau, puis l'étend au
projet — avec une cascade : **un projet privé rend privé tout ce qu'il contient.**

## L'état de départ, mesuré

| Modèle | champ | filtre liste REST | filtre agent / ⌘K / RAG | bascule UI |
|---|---|---|---|---|
| `tasks.Task` | ✅ | ✅ | ❌ | ✅ |
| `documents.Document` | ✅ | ✅ | ✅ | ❌ |
| `briefings.Briefing` | ✅ | ✅ | n/a (non searchable) | ✅ |
| `interactions.Interaction` | ✅ | ❌ | ❌ | ❌ |
| `projects.Project` | ❌ | — | — | — |

Trois fuites vivantes en découlaient :

1. **La note privée était servie à tout le foyer.** `InteractionViewSet` ne
   filtrait pas — l'exemption était écrite, argumentée sur les **dépenses**, et
   couvrait les **notes** par ricochet alors qu'une note n'alimente aucun compteur.
2. **Seul `documents` déclarait `visibility=` sur son `SearchableSpec`.** La tâche
   privée d'Alice était donc absente de sa propre liste et **citable par l'agent
   de Bob**, par six portes : la palette ⌘K, `search_household`, `get_entity`,
   `get_related`, `list_entities` et le contexte d'une conversation ancrée.
3. **`project_tab_counts` comptait sans lecteur.** Bob lisait « Tâches (3) » et
   l'onglet lui en servait deux.

## Les six règles, et pourquoi elles ont été arbitrées ainsi

### 1. La visibilité se calcule, elle ne se propage pas

Un enfant garde son propre drapeau ; sa visibilité effective vaut
`enfant.privé OU projet.privé`, évaluée **à la lecture**. C'est « le solde n'est
jamais dénormalisé » appliqué à la visibilité.

L'alternative — écrire `is_private=True` sur tous les enfants au moment où on coche
la case — rend toutes les lectures existantes correctes sans y toucher, et c'est
son seul avantage. Elle coûte trois choses : décocher ne sait plus ce qui était
privé avant (perte d'information) ; tout enfant créé plus tard doit passer par un
service qui privatise, ce qui n'est pas vrai aujourd'hui ; et la contrainte
`tasks_private_not_assigned` désassignerait les tâches au passage, c'est-à-dire
qu'elle détruirait de l'information pour cocher une case.

### 2. On ne privatise pas le travail d'autrui

Privatiser un projet contenant des items d'un autre membre répond **400 nommé**,
avec le compte de ce qui appartient à qui.

Les deux autres réponses possibles étaient mauvaises symétriquement. « Le projet
gagne » confisque à Bob ce qu'il a écrit : sa tâche disparaît sans un mot et il ne
peut pas la retrouver. « Le créateur garde » ne confisque rien mais fait mentir la
case : le projet cesse d'être privé dès qu'un autre membre y a touché. Le refus, lui,
se voit — et le cas réel (le projet surprise, créé par une seule personne) passe.

**Corollaire, et il simplifie tout le reste :** la cascade ne porte jamais que sur
ce que le demandeur a créé lui-même.

### 3. Le secret porte sur *quoi*, jamais sur *combien*

Une dépense de projet privé **reste** dans `interactions.queries.expenses()`, donc
dans la barre de budget, `coverage_ratio`, `Project.actual_cost`, le bilan mensuel
figé et les quatorze détecteurs de conformité. Ce sont son sujet, son fournisseur
et sa source qui sont **masqués** pour les autres membres.

C'est le seul arbitrage du parcours où une erreur casse une règle existante. La
masquer des totaux donnerait au budget « Bricolage » deux valeurs selon le lecteur —
*un compteur ne peut pas avoir deux définitions* — et afficherait à Bob des écarts
de conformité qu'il ne pourrait ni voir ni résoudre, alors qu'*une liste
irrésoluble ne se lit pas*. La laisser entière ferait fuiter le titre du projet en
clair : le sujet auto-généré est `"Achat — {name}"` avec `name = project.title`.

C'est aussi la seule position tenable sur un **compte joint** : l'argent sorti du
compte commun est un fait du foyer ; ce qu'on a acheté est un secret légitime.

### 4. Cinq enfants, et les zones jamais

Tâches, notes, dépenses (masquées), documents/photos, trackers. Une zone est une
pièce de la maison : structurelle, partagée par vingt features. La privatiser
privatiserait la maison.

### 5. Un compteur ne mentionne pas ce qu'il cache

Hors argent, privé veut dire **absent**, sans trace : pas de « 1 élément privé »
en marge. Sur un foyer de deux personnes, un marqueur anonyme dit immédiatement
de qui. Conséquence : `project_tab_counts` et `ProjectGroup.projects_count`
comptent par lecteur. (La file « À trier » et l'album passaient déjà par le
queryset filtré.)

### 6. Le privé d'un membre parti n'est lu par personne

`created_by` est en `SET_NULL` : un item privé orphelin reste invisible pour
tous, owner du foyer compris. Fail-closed assumé — un manque se remarque et se
corrige ; une fuite, non.

## La conséquence d'architecture

Avec une cascade **dérivée**, le garde-fou de complétude ne peut plus être un
`grep` du champ : un `Tracker` héritera de la confidentialité de son projet **sans
porter de drapeau**, donc `test_privacy_isolation.py` ne le verrait pas. Et un
catalogue qui ne voit pas le nouveau venu rassure à tort.

D'où un **registre déclaratif** dans `core.visibility` (lot 2), du même modèle que
`banking.compliance.REGISTRY` et `agent.searchables` : chaque modèle déclare,
**depuis son app**, comment sa visibilité se restreint et si le refus est *cacher*
ou *masquer*. `visible_to_creator` reste l'implémentation partagée du couple
`is_private` / `created_by`, `SearchableSpec.visibility` délègue, et le test refuse
tout modèle non déclaré.

## Lots

- **Lot 1** — [#661](https://github.com/jammindev/maisonnee/issues/661) : fermer les trois fuites. Aucune décision restante, livrable seul.
- **Lot 2** — [#662](https://github.com/jammindev/maisonnee/issues/662) : le registre de visibilité. Zéro changement de comportement.
- **Lot 3** — [#663](https://github.com/jammindev/maisonnee/issues/663) : l'UI de la confidentialité. Un contrôle partagé, 4 locales.
- **Lot 4** — [#664](https://github.com/jammindev/maisonnee/issues/664) : le projet privé. Drapeau, refus nommé, cascade, masquage de l'argent.

Palier utilisable : **1** seul ferme les fuites. **2 → 3 → 4** livre la demande.
