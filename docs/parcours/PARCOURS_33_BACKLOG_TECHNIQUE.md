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

## Lot 3 — L'UI de la confidentialité ([#663](https://github.com/jammindev/maisonnee/issues/663))

Le drapeau existe sur quatre modèles et n'a d'interface que sur deux, avec deux
dessins différents.

- `ui/src/design-system/visibility-field.tsx` — contrôle unique « Partagé / Privé »
  et sa phrase d'explication. Le dessin de `BriefingDialog` gagne : un radio nomme
  les deux états, une case à cocher n'en nomme qu'un.
- `ui/src/components/PrivateBadge.tsx` — le badge, aujourd'hui recopié dans
  `TaskCard`, `TaskDetailPage` et `BriefingCard`.
- Postes : `NewTaskDialog`, `BriefingDialog` (migration), dialogue de note, panneau
  document/photo.
- `ui/src/locales/{en,fr,de,es}.json` — namespace `privacy.*`, **sans
  `defaultValue`**.
- ⚠️ `fieldBase` : pas de `text-sm` sans préfixe de variante, sinon iOS zoome à
  l'ouverture du dialogue (`field-font-size.test.ts`).
- ⚠️ Cocher « privé » sur une tâche assignée se refuse **avant** l'appel réseau :
  `tasks_private_not_assigned` existe, et un 500 sur une case à cocher est un
  mauvais professeur.
- Tutoriel `/app/tutorial` mis à jour dans la même PR.

---

## Lot 4 — Le projet privé ([#664](https://github.com/jammindev/maisonnee/issues/664))

- `apps/projects/models.py` + migration — `is_private` sur `Project`.
- `apps/projects/services.py` — `assert_can_privatise(project, user)` : le 400 nommé,
  avec le compte de ce qui appartient à d'autres.
- `apps/core/visibility.py` — le `narrow` hérité, `Q(projet public) | Q(créateur du
  projet)`. ⚠️ Les dépenses sont liées par **FK polymorphe**
  (`source_content_type` / `source_object_id`) : sous-select sur les ids de projets
  privés, pas de `select_related`.
- `apps/interactions/serializers.py` — le masquage, **au singulier**.
- `apps/projects/apps.py` — `visibility=` sur le spec `project`, et
  `_project_related` filtré par lecteur.
- `apps/trackers/apps.py` — déclaration au registre : pas de drapeau propre,
  héritage seul.
- `apps/notifications/` — `retract_by_payload` à la privatisation.
- Front, 4 locales, tutoriel.

**Le test qui compte** : la barre du budget, `coverage_ratio`, `Project.actual_cost`
et le bilan mensuel donnent le **même** chiffre aux deux lecteurs, avant et après la
privatisation. C'est le seul endroit du parcours où « un compteur ne peut pas avoir
deux définitions » peut casser.
