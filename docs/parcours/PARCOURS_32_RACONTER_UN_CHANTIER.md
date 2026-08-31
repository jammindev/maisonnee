# Parcours 32 — Raconter un chantier plutôt que le remplir

> Un chantier se pense en marchant. Le formulaire, lui, demande de l'avoir déjà
> pensé : onze champs, dont le budget et les dates, à une personne qui vient
> d'avoir l'idée. Ce parcours retourne l'ordre — on raconte, l'app questionne,
> et le projet sort de la conversation.

- Fiche concept : [ENTRETIEN_DIRIGE.md](../fiches/ENTRETIEN_DIRIGE.md)
- Backlog technique : [PARCOURS_32_BACKLOG_TECHNIQUE.md](./PARCOURS_32_BACKLOG_TECHNIQUE.md)
- User stories : [USER_STORIES.md](../USER_STORIES.md) — `PROJ-01` à `PROJ-14`

## Résumé

> « Je veux faire une terrasse. »
>
> — et l'app répond par un formulaire de onze champs dont je ne connais aucun.

Créer un projet aujourd'hui demande un titre, une description, un type, une
priorité, deux dates, un budget prévisionnel, des zones, des étiquettes et un
groupe. Quelqu'un qui vient d'avoir l'idée d'une terrasse ne sait **rien** de
tout ça : ni le budget (c'est justement ce qu'il cherche), ni les dates (elles
dépendent du reste), ni comment découper. Le formulaire lui demande d'avoir
terminé sa réflexion avant de pouvoir commencer à la noter.

Et ce qui est réellement difficile — **décomposer** un chantier en tâches, se
souvenir qu'il faut vérifier les règles d'urbanisme, penser à demander trois
devis — le formulaire n'y aide pas du tout. Il enregistre une intention et
laisse la personne seule devant une page de projet vide.

Ce parcours remplace le formulaire par un **entretien**. On dit ce qu'on veut
faire, en une phrase. L'assistant pose une question à la fois — bois, composite
ou carrelage ? quelle surface ? un budget en tête ? — et s'arrête quand il en
sait assez, ou quand on le lui dit. Puis il **propose** : un projet renseigné,
des tâches, des notes de recherche, une enveloppe budgétaire. On relit, on
décoche ce qui ne va pas, on corrige un montant, on crée.

**Rien n'est écrit tant qu'on n'a pas relu.** C'est le point qui distingue ce
parcours de l'écriture conversationnelle déjà livrée (`create_entity`, lot 8 du
parcours 07) : là-bas l'agent crée un objet et propose de l'annuler, ce qui est
un contrôle suffisant pour *un* objet. Ici, un entretien produit une douzaine
d'objets d'un coup, et douze bulles « Annuler » ne sont pas un contrôle — c'est
un ménage.

## Positionnement produit

**Pourquoi maintenant.** L'app sait déjà faire écrire le modèle : les énigmes
d'une chasse au trésor (parcours 31), le bilan mensuel, le digest quotidien. Mais
elle ne lui a jamais fait produire autre chose que **du texte à lire**. Faire
produire des **objets métier** — un projet, des tâches, une enveloppe — est le
pas suivant, et le module projets est celui où il vaut le plus : c'est là que le
coût d'entrée est le plus élevé et l'aide la plus concrète.

**La limite qu'il lève.** Le module projets a un abandon structurel : un chantier
qui se pense en marchant se heurte à un écran qui exige une pensée finie. Le
résultat visible en base, c'est un projet au titre juste et au reste vide — créé
une fois, jamais rouvert. Ce parcours ne rend pas le formulaire plus court, il le
rend **facultatif** : il reste la porte de ceux qui savent déjà.

**Ce qu'il faut dire honnêtement.** Un chantier est un événement — quelques-uns
par an, pas une boucle quotidienne. Ce parcours n'achète pas de la rétention par
habitude, il achète le fait que **le premier projet existe vraiment**. Et il faut
le mesurer comme tel : le chiffre qui compte n'est pas « projets créés » mais
« projets créés qui ont au moins une tâche et qui sont rouverts une deuxième
fois ». Un assistant qui remplirait l'app de chantiers morts serait un échec
déguisé en adoption.

**Ce qui a déjà été tenté, et pourquoi ça a été retiré.** Une version de cette
feature a existé dans l'ancienne application Next.js
(`legacy/nextjs/.../projects/components/wizard/`) et a été retirée avec elle ;
les modèles Django qui l'accompagnaient — `ProjectAIThread`, `ProjectAIMessage` —
ont été supprimés comme code mort (#163). C'était un **formulaire à trois
étapes** : détails du projet, téléversement de documents, puis un plan généré en
un seul appel. Deux défauts, et ils sont la raison d'être du présent cadrage :

1. **L'étape 1 était le formulaire de onze champs**, simplement déplacé dans une
   fenêtre modale. Elle demandait toujours de tout savoir avant de parler — le
   mur qu'elle prétendait supprimer était le premier obstacle rencontré.
2. **Le plan arrivait en un coup, sans conversation.** Personne ne pouvait dire
   « non, ma terrasse est en composite » entre la question et la réponse. Le plan
   tombait juste, ou il fallait tout reprendre à la main — et un plan qu'on
   reprend à la main coûte plus cher que pas de plan du tout, parce qu'il faut
   d'abord le lire pour découvrir qu'il est faux.

## Ce que l'utilisateur gagne

| Question | Aujourd'hui | Après |
|---|---|---|
| « Je veux faire une terrasse » | onze champs, dont trois que j'ignore | une phrase, puis quatre questions |
| « Combien ça coûte, une terrasse ? » | un champ vide, et débrouille-toi | l'assistant donne un ordre de grandeur, **je saisis le chiffre** |
| « Par où je commence ? » | une page de projet vide | six tâches proposées, je décoche les deux qui ne servent pas |
| « Il fallait un permis ?! » | découvert trois semaines plus tard | une note « vérifier les règles d'urbanisme » dès le départ |
| « C'est dans quelle pièce ? » | à repréciser sur chaque tâche | les zones du projet suivent les tâches et les notes |
| « Où passent ces dépenses ? » | rattachées à la main, ou à rien | une enveloppe proposée, pré-sélectionnée aux achats du chantier |
| « J'ai le devis en PDF » | à joindre après coup, ailleurs | joint pendant l'entretien, relié au projet créé |

## Scénario de bout en bout

1. Sur la page Projets, à côté de « Nouveau », un bouton **« Créer avec
   l'assistant »**. Il n'apparaît que si l'instance a une clé — pas grisé,
   **absent** : un bouton grisé promet et dément dans le même geste.
2. Un champ, une phrase : « je veux refaire la terrasse ».
3. L'assistant demande : *bois, composite ou carrelage ?* → « bois ».
4. *Quelle surface, environ ?* → « une vingtaine de mètres carrés ».
5. *As-tu un budget en tête ? Pour un ordre de grandeur, une terrasse bois de
   20 m² se situe souvent entre 2 500 et 4 500 € en fournitures.* Le champ de
   réponse est un champ de montant — et il est **vide**. La fourchette est écrite
   à côté, elle n'est pas dans le champ.
6. *Pour quand ?* → « avant l'été ». À la quatrième question, le bouton « J'ai
   assez dit, génère » est là depuis le début ; il suffit de l'utiliser.
7. **L'écran de relecture.** Le projet est rempli — titre, type `renovation`,
   zone Jardin, budget 3 200 €, échéance au 21 juin. En dessous, six tâches et
   deux notes, chacune avec sa case cochée. On décoche « louer une bétonnière »,
   on corrige le titre d'une tâche, on ajoute le devis du menuisier en pièce
   jointe.
8. « Créer le projet ». Un seul enregistrement, une seule bascule vers la page du
   chantier — qui n'est pas vide.

## Ce qu'on ne fait pas en V1

- **Pas de correction de la façon dont l'assistant travaille.** Apprendre qu'un
  foyer veut toujours une tâche « demander trois devis », ou régler le niveau de
  détail, est une suite désirée mais délibérément hors V1 — elle demande de
  décider *où* vit cette préférence (foyer ? utilisateur ? mémoire de l'agent ?),
  et cette décision ne se prend pas en même temps que le reste.
- **Pas de génération sur un projet existant.** « Complète mon chantier en cours »
  suppose de lire ce qui existe déjà pour ne pas le redire — un autre problème.
  L'entretien part toujours d'une page blanche.
- **Pas de courses, d'équipement ni de stock générés.** « 24 lames et 6 plots »
  est tentant et faux : une liste de courses inventée sans voir le chantier est
  un devis déguisé.
- **Pas de sous-projets, de jalons ni de dépendances entre tâches.** Une liste
  plate. Le modèle sait ordonner un texte, pas planifier un chantier.
- **Pas de recherche web pendant l'entretien.** L'ordre de grandeur donné sur le
  budget est une connaissance générale annoncée comme telle, jamais un prix
  sourcé — et surtout jamais un prix écrit dans un champ à la place de
  l'utilisateur.
- **Pas de repli sans clé API.** Contrairement aux énigmes du parcours 31, il n'y
  a pas de « version manuelle » de cet écran : le formulaire de création existe
  déjà et **est** le repli. Sans clé, le bouton n'existe pas, et rien ne manque.
- **Pas d'entretien repris plus tard.** Fermer la fenêtre perd l'entretien. Le
  garder supposerait une table d'entretiens abandonnés à nettoyer, pour un geste
  qui dure trois minutes.
