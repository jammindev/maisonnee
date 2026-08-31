# Confidentialité intra-foyer : une frontière à l'intérieur du tenant

> Fiche liée au [parcours 33](../parcours/PARCOURS_33_CE_QUI_EST_PRIVE.md) — finir le drapeau `is_private` avant de l'étendre au projet.
> Voir aussi : [RAG.md](./RAG.md) (la couche de retrieval, qui est la porte qu'on oublie).

## 1. Le problème

House est multi-tenant : chaque donnée appartient à un foyer, et l'isolation entre
foyers est tenue par `HouseholdScopedManager`, testée par `test_tenant_isolation`.
C'est une frontière **franche** — deux foyers ne partagent rien, et une requête qui
oublie le scope renvoie des données manifestement étrangères, donc visibles au
premier coup d'œil.

La confidentialité intra-foyer est une deuxième frontière, tracée **à l'intérieur**
du tenant : moi contre les autres membres. Elle est plus difficile pour trois
raisons qui se cumulent.

**(a) Elle n'est pas dans le chemin normal.** Le scope foyer est dans le manager par
défaut : on l'obtient sans y penser. La confidentialité, elle, doit être ajoutée
explicitement à chaque lecture. Un `get_queryset()` qui l'oublie fonctionne
parfaitement.

**(b) Le défaut est invisible en revue.** Un queryset sans la clause ressemble trait
pour trait à celui qui la porte. Il n'y a rien à repérer : pas d'exception, pas de
type qui ne colle pas, pas de nom suspect. C'est la signature d'un travail à sortir
de l'espace latent.

**(c) Le défaut est invisible à l'usage.** Il faut **deux comptes dans le même
foyer** pour le constater — précisément ce qu'un développeur seul n'a jamais sous la
main. Une donnée entre foyers saute aux yeux ; le privé d'un colocataire ressemble à
une donnée normale du foyer.

Résultat mesuré dans ce dépôt : `is_private` a vécu des mois comme un drapeau
**décoratif** sur les modèles où il comptait le plus.

## 2. Le concept en deux phrases

Une **visibilité par lecteur** restreint une lecture non pas selon *à qui
appartiennent les données* (le tenant) mais selon *qui les regarde*. Elle n'est
tenable que si elle a **une seule définition** et **autant de points d'application
que de portes de lecture** — car deux définitions ne divergent jamais
symétriquement : c'est toujours la plus permissive qui gagne, et elle gagne en
silence.

## 3. Comment on l'a appliqué dans house

### 3.1 Une fonction, pas une convention

`core.visibility.visible_to_creator(queryset, viewer)` est la seule définition de
« public, plus ce que j'ai écrit moi-même ». Elle est **fail-closed** : `viewer=None`
ne voit que le public, de sorte qu'un chemin qui oublie de passer le lecteur
**sous-affiche** au lieu de fuiter. Un manque se remarque et se corrige ; une fuite,
non.

Elle filtre sur `created_by`, **jamais sur le rôle** : un owner de foyer n'est pas un
lecteur privilégié du privé des autres. C'est une décision produit, pas un oubli — un
foyer n'a pas de hiérarchie de lecture.

### 3.2 Le filtre vit dans le queryset, pas dans une permission objet

DRF offre `has_object_permission`, et `core.permissions.CanViewPrivateContent`
l'implémente. Ça ne suffit pas et ça ne peut pas suffire : **une permission ne se
prononce que sur un objet déjà chargé**, donc elle protège le détail et laisse
passer la liste — qui est justement l'endroit où l'on lit les secrets des autres.

### 3.3 Il y a sept portes, pas une

C'est la leçon la plus chère du parcours. Une entité se lit par :

1. la liste REST de son viewset ;
2. la palette de recherche globale (⌘K) ;
3. le tool agent `search_household` ;
4. `get_entity` ;
5. `get_related` ;
6. `list_entities` ;
7. le contexte d'une conversation ancrée.

Les six dernières ne passent **jamais** par le viewset : elles lisent le registre
`agent.searchables`. Un queryset borné ne borne donc pas ⌘K. Le premier correctif de
cette famille avait fermé les portes 2, 3 et 4 **pour les documents seulement** ; la
tâche privée d'Alice restait absente de sa propre liste et citable par l'assistant de
Bob par les sept portes.

D'où la forme retenue : **un registre**, `core.visibility.REGISTRY`, alimenté par
l'`apps.py` de chaque app propriétaire, et **un point d'application unique**,
`narrow_for`, que les sept portes appellent. Déclarer une fois ferme tout. Aucune
porte ne doit jamais grossir d'une liste de quels modèles se trouvent être privés —
sinon la prochaine s'ouvre.

La restriction a d'abord vécu sur le `SearchableSpec` de l'agent, et ce n'était pas
le bon endroit. Lier la confidentialité d'un modèle au fait qu'il soit *cherchable*
laisse deux trous, et le second est structurel :

1. un modèle privatisable **non searchable** (`briefings.Briefing`) n'a nulle part
   où se déclarer — son viewset réécrit donc la règle à la main, quatrième
   exemplaire du même `Q` ;
2. une confidentialité **héritée** — un tracker qui n'a pas de drapeau mais dont le
   projet en a un — ne porte **aucun champ**. Ni un `SearchableSpec` ni un `grep`
   de `is_private` ne peuvent la voir arriver. Un registre, si.

### 3.4 Le garde-fou est structurel, pas comportemental

`apps/core/tests/test_privacy_isolation.py` a quatre parties, et les quatre sont
nécessaires :

1. **aucune vue n'expose `is_private` en filtre** — sinon `?is_private=true` rouvre
   exactement ce que le queryset borne, comme un `defaultValue` rouvre une clé i18n ;
2. **un second membre ne voit pas l'item privé du premier** — le seul contrôle qui
   compare le code à ce que l'API sert vraiment ;
3. **complétude** : un modèle portant le drapeau est couvert ou exempté par écrit ;
4. **la déclaration** : un modèle privatisable est enregistré au registre. Le
   contrôle lit le **registre** et surtout pas le champ — c'est ce qui lui permet
   de couvrir la confidentialité héritée le jour où elle arrive.

La n°4 est structurelle exprès. Énumérer les sept portes dans un test finirait par en
oublier une huitième, alors que la déclaration les ferme toutes. On vérifie que le
mécanisme est **déclaré**, pas qu'il a été recopié partout — même choix que
`banking.compliance.REGISTRY`.

### 3.5 Une exception, écrite comme une décision

`Interaction(type="expense")` n'est **jamais** cachée d'une liste. Une dépense
alimente `interactions.queries.expenses()`, point de vérité unique de sept
agrégations. La retirer d'une liste sans la retirer des totaux donnerait au budget
« Bricolage » deux valeurs selon le lecteur.

Le secret d'une dépense porte donc sur son **contenu** et non sur son existence :
sujet, fournisseur et projet source seront remplacés par « Dépense privée ». C'est la
distinction **masquer / cacher**, et elle mérite son vocabulaire parce qu'elle
revient : ce qui alimente un compteur partagé se masque, ce qui n'alimente rien se
cache.

L'exception vit dans `interactions.visibility`, importée par la vue **et** par le
spec — un seul endroit décide, deux portes obéissent.

### 3.6 Le registre borne des querysets, il ne masque rien

`PrivacySpec` ne porte **pas** de champ `mode: hide | redact`, et l'omission est
délibérée : remplacer le sujet d'une dépense par « Dépense privée » est une
décision de **sérialisation**, pas de requêtage. La ranger dans un module qui borne
des querysets ferait croire qu'elle y est appliquée alors que rien ne la lirait —
un champ mort dans un module de visibilité est pire qu'une ligne à écrire plus tard.

Le masquage vivra donc dans le serializer, avec son producteur et son consommateur
dans le même diff. Ce que le registre exprime déjà de l'argent, il l'exprime au bon
niveau : le `narrow` d'`interactions` **ne cache pas** les dépenses, et c'est tout
ce qu'une couche de requête a à en dire.

## 4. Pourquoi cette implémentation

**Pourquoi un paramètre `never_hidden` sur le helper partagé, plutôt qu'un `Q` chez
l'appelant.** Ce qui ne doit jamais diverger, c'est la **règle du lecteur** : comment
on reconnaît un lecteur authentifié, quoi faire de `None`, filtrer sur `created_by` et
pas sur le rôle. Chaque app décide de son **exception** ; aucune ne redécide comment
reconnaître un lecteur.

**Pourquoi le compteur compte par lecteur.** Un onglet qui annonce « Tâches (3) » et
en sert deux ne se contente pas d'être faux : il **trahit l'existence** de la tâche
privée à qui sait soustraire. Hors argent, privé veut dire absent *sans trace* — un
compteur qui déborde est une trace.

**Pourquoi pas de marqueur « 1 élément privé ».** Le dépôt applique ailleurs la règle
inverse (parcours 26 : *toute entité est soit résolue, soit flaggée avec un motif ;
rien ne reste dans un entre-deux silencieux*). Ici elle ne s'applique pas, et il faut
savoir dire pourquoi : sur un foyer de deux personnes, un marqueur anonyme **désigne
son auteur**. Le silence n'est pas un orphelin quand il est le produit demandé.

## 5. Ce qu'on a écarté et pourquoi

**Le chiffrement côté client (E2EE).** Envisagé pour les documents
([NEXT_STEPS.md](../NEXT_STEPS.md), phase 2). Il exclut la pièce de l'OCR, du full-text et du RAG — un compromis assumé
pour un coffre, ruineux pour un drapeau posé sur une tâche. La confidentialité de ce
parcours est une règle de **lecture**, pas de stockage : le staff Django voit tout,
et c'est dit.

**Une visibilité par rôle** (l'owner voit tout). Elle rendrait le drapeau inutile
dans un foyer de deux personnes, où l'un est owner par construction.

**Des listes d'accès par item** (partager avec Alice mais pas Bob). Le besoin réel est
binaire — le cadeau, le bilan médical — et une ACL demande une interface de gestion
que personne n'ouvrira. Un drapeau qu'on comprend bat une permission qu'on configure.

**Propager le drapeau aux enfants à l'écriture.** Voir le parcours : la dénormalisation
perd l'information au décochage et heurte `tasks_private_not_assigned`.

## 6. Pour aller plus loin

- Row-Level Security PostgreSQL — l'équivalent au niveau base, que ce dépôt imite au
  niveau Django (`core.permissions` porte la trace de son origine Supabase).
- OWASP « Broken Object Level Authorization » (API1:2023) — la famille de défauts dont
  fait partie « la liste fuit ce que le détail protège ».
