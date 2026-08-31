# Parcours 33 — Backlog technique

> Découpage en lots de [PARCOURS_33_CE_QUI_EST_PRIVE.md](./PARCOURS_33_CE_QUI_EST_PRIVE.md).
> Fiche à lire d'abord : [CONFIDENTIALITE.md](../fiches/CONFIDENTIALITE.md).

Palier utilisable : **1** seul ferme les fuites. **2 → 3 → 4** livre la demande.

---

## Lot 1 — Fermer les trois fuites ([#661](https://github.com/jammindev/maisonnee/issues/661)) — **livré**

Aucune décision d'architecture : rien ici ne dépend du projet privé.

| Fichier | Changement |
|---|---|
| `apps/core/visibility.py` | `visible_to_creator(qs, viewer, *, never_hidden=None)` — l'exception est passée par l'app propriétaire, la règle du lecteur reste unique |
| `apps/interactions/visibility.py` | **nouveau** — `MONEY_IS_NEVER_HIDDEN` + `visible_interactions`, importés par la vue *et* par le spec |
| `apps/interactions/views.py` | clause de confidentialité dans `get_queryset` ; le commentaire du `filterset_fields` cesse de dire « pas encore » |
| `apps/tasks/apps.py` | `visibility=visible_to_creator` sur le `SearchableSpec` |
| `apps/interactions/apps.py` | `visibility=visible_interactions` sur le `SearchableSpec` |
| `apps/documents/views.py` | le `Q` écrit à la main passe par `visible_to_creator` — c'était la seconde définition de la règle |
| `apps/projects/services.py` | `project_tab_counts(project, viewer=None)`, six compteurs alignés sur les listes qu'ils annoncent |
| `apps/projects/serializers.py` | transmet `request.user` |

**Régressions.** `core/tests/test_privacy_isolation.py` (la note, la dépense jamais
cachée, et la 4ᵉ partie : la porte de l'agent) ;
`agent/tests/test_private_visibility.py` (tâche et note sur les portes agent, y
compris le contexte ancré) ; `projects/tests/test_tab_counts.py`
(`TestTheCountAgreesWithTheTab`).

**Vérifié en échec avant correctif** : `test_note` et la partie n°4 rouges ; cinq
tests agent rouges dont le contexte ancré ; quatre compteurs rouges à signature
égale. `TestAPrivateExpenseIsNeverHidden` reste verte des deux côtés — c'est son
rôle : elle n'attrape pas le défaut, elle attrape la **sur-correction**.

---

## Lot 2 — Le registre de visibilité ([#662](https://github.com/jammindev/maisonnee/issues/662)) — **livré**

Zéro changement de comportement observable. C'est le socle que le lot 4 exige,
livré à part pour que sa PR reste relisible.

| Fichier | Changement |
|---|---|
| `apps/core/visibility.py` | `PrivacySpec(model, narrow)`, `REGISTRY`, `register()`, `find_spec`, `has_spec`, `narrow_for` — **le** point d'application |
| `apps/{tasks,documents,briefings,interactions}/apps.py` | enregistrement depuis `ready()` ; `briefings` gagne un `ready()` qu'il n'avait pas |
| `apps/agent/searchables.py` | le champ `visibility` **disparaît** (voir plus bas) |
| `apps/agent/retrieval.py` | `apply_visibility` et `filter_visible_instances` lisent le registre |
| `apps/{tasks,briefings,documents,interactions}/views.py` | les quatre `Q` écrits à la main appellent `narrow_for` |
| `core/tests/test_privacy_isolation.py` | la partie 4 lit le **registre** et non plus le champ |

**Deux écarts assumés par rapport au cadrage initial, tous deux vers le plus
strict :**

1. **`SearchableSpec.visibility` est supprimé, pas rendu optionnel.** Le laisser en
   surcharge aurait maintenu deux mécanismes pour une même règle. Surtout, le champ
   était **mal placé** : il liait la confidentialité d'un modèle au fait d'être
   *cherchable*, ce qui laissait `briefings.Briefing` sans domicile (son viewset
   réécrivait donc le `Q`) et ne pourra jamais voir une confidentialité héritée, qui
   ne porte aucun champ.
2. **Pas de champ `mode: hide | redact`.** Le masquage est une décision de
   **sérialisation**, pas de requêtage : le ranger dans un module qui borne des
   querysets ferait croire qu'il y est appliqué alors que rien ne le lirait. Un champ
   mort dans un module de visibilité coûte plus qu'une ligne à écrire au lot 4, avec
   son producteur et son consommateur dans le même diff. Ce que la couche requête a à
   dire de l'argent, elle le dit déjà : le `narrow` d'`interactions` ne cache pas les
   dépenses.

**Critère principal tenu** : aucun test existant ne change de valeur. Seule la
partie 4 est réécrite — parce que son sujet, la déclaration, a changé de place.
Suite complète : `4870 passed`.

---

## Lot 3 — L'UI de la confidentialité ([#663](https://github.com/jammindev/maisonnee/issues/663)) — **livré**

Le drapeau existe sur quatre modèles et n'a d'interface que sur deux, avec deux
dessins différents.

| Fichier | Changement |
|---|---|
| `ui/src/design-system/visibility-field.tsx` | **nouveau** — deux boutons radio « Partagé / Privé », les deux états nommés |
| `ui/src/components/PrivateBadge.tsx` | **nouveau** — un composant, deux rendus (`pill`, `icon`), **un** libellé |
| `NewTaskDialog` | la case à cocher devient le contrôle partagé |
| `BriefingDialog` | le menu déroulant aussi |
| `InteractionNewPage` / `InteractionEditPage` | **première** bascule pour une note |
| `DocumentEditDialog` | **première** bascule pour un document, grisée si on n'est pas le déposant |
| `TaskCard`, `TaskDetailPage`, `BriefingCard` | les trois marqueurs deviennent `PrivateBadge` |
| `ui/src/lib/api/{documents,interactions}.ts` | les types écrits à la main exposent `is_private` |
| 4 locales | namespace `privacy.*` ; les clés mortes `tasks.fieldPrivate` et `briefings.visibility.*` supprimées |
| `features/tutorials/content.ts` + 4 locales | une étape `privacy` sur les guides tâches, activité et documents |

**Deux boutons plutôt qu'une case à cocher, et ce n'est pas cosmétique** : une case
à cocher **ne nomme qu'un seul état**. Décochée, elle laisse deviner ce qu'elle veut
dire — et sur un réglage dont l'erreur se paie en « tout le foyer a vu mon cadeau »,
deviner ne suffit pas. Ce sont de vrais `<input type="radio">` dans un `<fieldset>` :
clavier, lecteur d'écran et exclusion mutuelle viennent du navigateur.

**Ce que le lot corrige au passage** : les deux marqueurs de tâche étaient des
cadenas **nus**, sans libellé ni `aria-label` — invisibles pour un lecteur d'écran.
La variante `icon` porte le libellé.

**Régression** : `ui/src/design-system/visibility-field.test.tsx` — les deux états
sont nommés, l'actif est reflété sur le bon bouton, l'exclusion mutuelle passe par
un `name` partagé, et la conséquence propre à l'écran ne s'affiche que quand elle
s'applique. ⚠️ Le test charge le **vrai** catalogue français : sans i18n,
`t('privacy.shared')` renvoie la clé brute, et « privacy.shared » contient « priv » —
une recherche par nom accessible trouverait les deux boutons, donc le test ne
prouverait rien sur un composant dont c'est justement la fonction de les distinguer.

**Déjà tenu, vérifié** : `tasks_private_not_assigned` est désamorcé côté client
(choisir « privé » retire l'assignation, et le contrôle l'annonce) ; `radio` ne
déclenche pas le zoom iOS, donc `field-font-size.test.ts` reste vert.

**Hors périmètre, constaté** : `design-system/checkbox-field.tsx` code ses couleurs
en dur (`border-slate-300`, `checked:bg-slate-800`, `dark:border-slate-600`) au lieu
des tokens du design-system. Non corrigé ici — un correctif non demandé rend le diff
irrelisable.

---

## Lot 4 — Le projet privé ([#664](https://github.com/jammindev/maisonnee/issues/664)) — **livré**

| Fichier | Changement |
|---|---|
| `apps/projects/models.py` + `0009` | `Project.is_private` |
| `apps/projects/visibility.py` | **nouveau** — `hidden_project_ids` (sous-select), `exclude_hidden_projects`, `visible_projects` |
| `apps/{tasks,trackers,documents}/visibility.py` | **nouveaux** — le `narrow` hérité de chaque enfant, déclaré par son app |
| `apps/interactions/visibility.py` | l'héritage **et** l'exception de l'argent |
| `apps/core/visibility.py` | `PrivacySpec.readable` + `readable_for` — voir ≠ lire |
| `apps/interactions/serializers.py` | le masquage (`REDACTED`, `is_redacted`) |
| `apps/agent/{retrieval,tools}.py` | l'illisible n'est ni cité, ni rendu par `get_entity`, ni nommé dans `list_entities` — mais **compté** dans `sum_amount` |
| `apps/projects/services.py` | `foreign_content_counts`, `assert_can_privatise` (400 nommé), `retract_notifications_for` |
| `apps/projects/serializers.py` | la garde au `validate`, la rétractation à l'`update`, `projects_count` par lecteur |
| `apps/{projects,trackers}/views.py` | `narrow_for` |
| Front | contrôle dans le formulaire, pastille sur la carte, dépense masquée nommée « Dépense privée », 4 locales, étape de tutoriel |

### Le concept que ce lot a dû introduire

**Voir qu'une ligne existe et lire ce qu'elle dit sont deux questions.** Pour presque
tout, elles ont la même réponse — ce qu'on ne peut pas lire, on ne le voit pas, et
`narrow` suffit. L'argent est l'exception : une dépense reste dans la liste parce que
sept agrégations la lisent, mais son sujet auto-généré est `"Achat — {titre du
chantier}"`. Sans cette seconde question, privatiser un chantier aurait fait fuiter
son titre en clair dans la liste des dépenses, dans la ligne bancaire rapprochée
**et** dans les citations de l'assistant — c'est-à-dire partout sauf là où on venait
de le cacher.

D'où `PrivacySpec.readable` / `core.visibility.readable_for`, introduits **avec leur
producteur et leurs quatre consommateurs dans le même diff** — exactement ce que le
lot 2 s'était engagé à faire plutôt que de poser un champ mort par anticipation.

### Trois défauts attrapés par les tests pendant l'écriture

1. **Le viewset des trackers n'était pas branché.** Le spec était déclaré, la
   restriction écrite — et la liste servait quand même les trackers d'un chantier
   privé. Déclarer ne suffit pas si personne n'applique.
2. **Le piège du `NULL`.** `exclude(project__in=…)` sur un champ nullable : en SQL,
   `NOT (project_id IN (…))` vaut NULL — donc « faux » — pour une ligne sans projet.
   Écrit à la main avec un `~Q(...)`, ce filtre aurait fait disparaître **toutes les
   tâches sans chantier**. Le symptôme, une liste vide, ne ressemble pas du tout à un
   problème de confidentialité. Régression : `TestAnItemWithoutAProjectStaysVisible`.
3. **`TASK_COMPLETED` n'existe pas.** Un type de notification inventé de bonne foi.
   `retract_by_payload` ne lève pas sur un type inconnu : il ne matche rien, et la
   rétractation serait devenue un no-op silencieux.

### Régressions

- `projects/tests/test_private_project.py` — la cascade sur cinq enfants, l'arrêt aux
  zones, le piège du NULL, l'aller-retour (une tâche privée à titre propre le reste),
  la tâche assignée qui garde son assignation, le refus nommé, les compteurs.
- `projects/tests/test_private_money_agrees.py` — **le test qui compte.**
- `core/tests/test_privacy_isolation.py` — `Project` au catalogue, `Tracker` déclaré
  comme confidentialité **héritée** (aucun drapeau à inspecter : c'est ce que le
  registre du lot 2 existait pour rendre visible).
- `agent/tests/test_private_visibility.py` — l'argent compté sans être nommé.

⚠️ **Collision de migration connue.** `projects/0009_project_is_private` (ce lot) et
`projects/0009_project_default_budget` (PR #675, parcours 32) dépendent toutes deux de
`0008`. Une fois les deux mergées, `projects` aura deux nœuds feuilles. Celui qui merge
en second renumérote en `0010` et repointe `dependencies`. Signalé par la session
`house-76`, vérifié depuis les deux branches.

**Le test qui compte** : la barre du budget, `coverage_ratio`, `Project.actual_cost`
et le bilan mensuel donnent le **même** chiffre aux deux lecteurs, avant et après la
privatisation. C'est le seul endroit du parcours où « un compteur ne peut pas avoir
deux définitions » peut casser.
