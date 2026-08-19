# L'entretien dirigé — faire poser les questions par le modèle sans lui confier l'état

> Fiche du [parcours 32](../parcours/PARCOURS_32_RACONTER_UN_CHANTIER.md).
> Voir aussi : [RAG.md](RAG.md) (l'agent conversationnel, l'autre façon de parler
> au foyer) et [SNAPSHOT_ET_RECIT.md](SNAPSHOT_ET_RECIT.md) (l'autre endroit où le
> modèle produit une sortie structurée qu'on ne réécrit jamais).

## 1. Le problème

Deux façons connues de recueillir de l'information, et chacune échoue à un
endroit précis.

**Le formulaire** connaît ses questions d'avance, les pose toutes, et sait quand
il a fini. C'est sa force et sa limite : ses questions sont les **champs du
modèle de données**. Pour créer un projet il demande un titre, un type, une
priorité, deux dates, un budget. Il ne demandera jamais « bois, composite ou
carrelage ? » — parce que ce n'est pas une colonne. Or c'est *exactement* la
question qui fait la différence entre un chantier bien posé et un titre vide.

**Le chat** peut poser n'importe quelle question, y compris la bonne. Mais il ne
sait ni combien de questions il lui reste, ni quand s'arrêter, ni ce qu'il doit
avoir appris avant de conclure. Livré à lui-même, un modèle conversationnel fait
l'une des deux erreurs : il conclut au deuxième tour avec la moitié des
informations, ou il enchaîne les questions jusqu'à ce que l'utilisateur ferme la
fenêtre. Et surtout, sa sortie est **du texte**, alors qu'on a besoin d'objets.

Il manque une forme intermédiaire : un échange dont le modèle choisit le
*contenu* des questions, mais dont le programme garde le *cadre* — combien de
tours, quand ça s'arrête, ce qui sort à la fin, et sous quelle forme.

## 2. Le concept en deux phrases

Un **entretien dirigé** est une boucle où, à chaque tour, le modèle reçoit un but,
le schéma de ce qu'il doit finir par produire, et l'historique des échanges — et
répond par **exactement l'une de deux choses** : la question suivante, ou le
résultat structuré.

L'état de l'entretien n'est pas gardé par le serveur : il **est** l'historique, et
c'est le client qui le renvoie à chaque tour. Le serveur, lui, ne garde qu'une
seule chose que le modèle n'a pas le droit de décider — le nombre de tours
restants.

## 3. Comment on l'a appliqué dans house

Un tour d'entretien est un `POST` sans mémoire. Le client envoie l'objectif de
départ (« je veux refaire la terrasse ») et la liste des questions déjà posées
avec leurs réponses ; le serveur rend un objet dont le champ `state` vaut
`asking` ou `ready` :

```jsonc
// tour 2 — il manque encore des choses
{ "state": "asking", "question": "Quelle surface, environ ?",
  "field": "surface", "input": "text", "hint": null, "asked": 2, "remaining": 4 }

// tour 5 — le modèle a de quoi conclure
{ "state": "ready", "plan": { "project": {…}, "tasks": […], "notes": […] } }
```

Trois éléments font le travail :

- **`input` type la réponse.** Le modèle décide *quelle* question poser ; le
  serveur décide *comment* on y répond — `text`, `amount`, `date`, `zones`,
  `choice`. Le front rend le contrôle correspondant : un `DecimalInput` pour un
  montant, le sélecteur de zones pour une zone.
- **Le compteur vit dans le code.** `asked` et `remaining` sont calculés à partir
  de la longueur de l'historique, jamais annoncés par le modèle. Au-delà du
  plafond, le serveur **force** `state: "ready"` : il ne demande pas au modèle de
  conclure, il ne lui laisse plus le choix.
- **`plan` n'est écrit nulle part.** L'endpoint d'entretien ne connaît aucun
  modèle Django en écriture. Créer est un **second** endpoint, appelé après
  relecture, qui reçoit le plan corrigé par l'utilisateur et passe par les
  services métier existants (`tasks.services.create_task`,
  `interactions.services.create_note_interaction`, `ProjectSerializer`).

## 4. Pourquoi cette implémentation

**Pourquoi le serveur ne garde pas l'entretien.** Un entretien dure trois minutes
et une personne sur trois l'abandonne au deuxième tour. Le persister crée une
table dont la majorité des lignes sont des déchets, donc une purge, donc une
tâche planifiée, donc une chose de plus qui peut tomber — pour un bénéfice
(« reprendre demain ») que personne ne demande sur un geste de trois minutes.
`AgentConversation` existe et fait l'inverse : elle persiste **parce qu'**on
relit une conversation, et qu'elle est ancrée à une entité durable. Les deux
choix sont cohérents avec ce qu'ils portent.

Le coût est réel et assumé : l'historique repart en entier à chaque tour, donc
six tours coûtent six appels dont le dernier porte tout. Sur un entretien de six
questions, l'historique fait quelques centaines de tokens — l'ordre de grandeur
du prompt système, pas de quoi arbitrer.

**Pourquoi le plafond est du code et pas une consigne.** « Pose au plus six
questions » dans un prompt système est une **intention**, pas une garantie : le
modèle la respecte la plupart du temps, et le jour où il ne la respecte pas,
c'est l'utilisateur qui découvre la boucle. C'est la règle des deux espaces
appliquée telle quelle : « combien de questions ai-je déjà posées » a une seule
bonne réponse par définition, donc ça se compte, ça ne se demande pas. Le prompt
porte quand même la consigne — mais comme un guide de style, pas comme une
barrière.

**Pourquoi deux endpoints et pas un.** « Rien n'est écrit avant relecture » doit
être **structurellement vrai**, pas tenu par une convention. Un endpoint unique
qui écrirait « seulement quand `state == ready` » repose sur une branche `if`,
et une branche `if` se casse. Séparer les endpoints fait mieux : celui qui parle
au modèle **ne sait pas où écrire**. C'est le même arbitrage que
`games/riddles.py`, où la génération d'énigmes est une action de liste
précisément parce qu'elle n'a aucune chasse à modifier.

**Pourquoi typer le champ de réponse plutôt que tout laisser en texte libre.**
Un montant saisi en texte doit être reparsé, et le reparsage d'un nombre est un
piège documenté de ce dépôt : « 12,5 » tapé sur un clavier français a déjà
enregistré **512 €** en production (voir la règle `DecimalInput` de `CLAUDE.md`).
Faire répondre à une question d'argent dans le composant qui sait déjà lire un
décimal, c'est refuser de rouvrir un bug qu'on a fermé. Le type n'est pas une
contrainte pour autant : le champ accepte toujours « je ne sais pas », et
l'entretien continue.

**Pourquoi le modèle ne remplit jamais le montant lui-même.** Il annonce un ordre
de grandeur *à côté* du champ, et le champ reste vide. Un budget prévisionnel
pré-rempli par un modèle est indistinguable d'un budget décidé par le foyer —
c'est la règle « des valeurs de départ, jamais des vérités » (`banking.rules`),
et elle mord ici plus fort qu'ailleurs : ce chiffre sert ensuite de référence à
la barre d'avancement du chantier pendant des mois, et personne ne se souviendra
qu'il a été inventé.

**Pourquoi une relecture en lot plutôt que « créer + Annuler ».** L'écriture
conversationnelle de l'agent (lot 8 du parcours 07) a tranché en faveur de
`créer + Undo` contre `needs_review`, et c'est le bon arbitrage **pour un
objet** : une bulle « Annuler » offre le même contrôle final sans la friction
d'une validation. La bascule tient à la cardinalité. Un entretien produit un
projet, six tâches, deux notes et une enveloppe : douze bulles « Annuler » ne
sont pas un contrôle, c'est un ménage — et l'utilisateur qui veut retirer *une*
tâche sur six devrait tout annuler puis tout refaire. À partir du lot, la
relecture coûte moins cher que l'annulation.

## 5. Ce qu'on a écarté et pourquoi

**Le formulaire multi-étapes.** C'est la version qui a existé dans l'ancienne
application et qui a été retirée : détails → documents → plan généré en un coup.
Sa première étape était le formulaire complet, donc elle demandait toujours de
tout savoir avant de parler ; et son plan arrivait sans qu'aucune question n'ait
été posée, donc il tombait juste ou il fallait tout refaire. Le remède n'est pas
« mieux découper les étapes », c'est de renverser l'ordre : questionner d'abord,
structurer ensuite.

**Le chat libre avec `create_entity`.** Presque gratuit à construire — le tool
existe, il suffirait de l'étendre au projet. Écarté pour trois raisons qui
tiennent ensemble : le modèle décide seul quand il a fini (et il finit trop tôt) ;
il n'y a pas d'écran de relecture, donc pas de correction avant écriture ; et
l'undo est par item. On garderait la conversation en perdant précisément ce qui
fait la valeur — le cadre.

**Un questionnaire fixe piloté par les champs du modèle.** « Pour chaque colonne
non renseignée, poser la question associée. » Déterministe, testable, sans
modèle. Et sans intérêt : les questions utiles ne sont pas les colonnes. Personne
n'a besoin d'aide pour répondre à « priorité de 1 à 5 » ; tout le monde en a
besoin pour « bois ou composite ». Un questionnaire fixe reproduit le formulaire
en plus lent.

**Le streaming de la réponse.** Une question de dix mots ne gagne rien à
apparaître lettre par lettre, et le streaming interdirait de valider la forme
JSON avant de l'afficher — on rendrait visible une réponse mal formée avant de
savoir qu'elle l'est. `ask_stream` existe pour le chat, où la réponse est longue
et où l'attente est le problème ; ici l'attente est d'une seconde.

**Persister l'entretien dans `AgentConversation`.** Traité au § 4 : la
persistance est justifiée par la relecture, et un entretien ne se relit pas.

## 6. Pour aller plus loin

- [Structured outputs — Anthropic](https://docs.claude.com/en/docs/build-with-claude/structured-outputs)
  — forcer une forme de sortie plutôt que la valider après coup.
- [Building effective agents — Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
  — la distinction *workflow* (le programme garde le contrôle) / *agent* (le
  modèle garde le contrôle) ; un entretien dirigé est un workflow, et c'est
  volontaire.
- `apps/games/riddles.py` — le précédent le plus proche dans ce dépôt : une
  génération structurée, validée strictement, qui n'écrit rien.
- [PARCOURS_IA_TRANSVERSE.md](../parcours/PARCOURS_IA_TRANSVERSE.md) — les modes
  de validation `auto` / `needs_review` / `draft`, et l'arbitrage « créer + Undo »
  du parcours 07 que ce parcours nuance pour les créations en lot.
