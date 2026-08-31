# Parcours 25 — Backlog technique V1

> Cadrage réalisé le 2026-07-25. **Lots 1 à 6 livrés le 2026-07-26.**
> Restent : lot 7 (recettes & couverture), lot 8 (agent), lot 9 (PDF/photo, différé).
>
> **Écarts au cadrage, assumés et documentés dans les PR :**
> - `BankTransaction.line_no` ajouté au lot 4 — sans lui le contrôle de chaîne est
>   non déterministe sur les journées à plusieurs opérations, et `created_at` n'est
>   pas fiable après un `bulk_create`.
> - `with_allocated` et `coverage_ratio` retirés du lot 3 : ils dépendent de la FK
>   du lot 5. Le taux de couverture appartient au lot 7, qui le porte déjà.
> - `file_validation` non élargi au lot 2 : l'import lit le fichier sans créer de
>   `Document`, donc la validation par magic bytes n'est jamais sur le chemin.
> - Lot 6 : « candidat unique » raffiné en « pas de rival **qui change les
>   comptes** » — deux rivaux interchangeables se rapprochent quand même.

## Tableau de bord

**Issue parente : [#383](https://github.com/jammindev/maisonnee/issues/383)** — à fermer une fois tous les lots livrés et la recette faite.

| Lot | Sujet | Statut | Issue |
|---|---|---|---|
| 1 | Socle `apps/banking` — `BankAccount` + CRUD + module UI | ✅ Livré (#393) | #384 |
| 2 | Import CSV/XLSX — importers, registry, dédup, `StatementImport` | ✅ Livré (#399) | #385 |
| 3 | Journal bancaire — liste, filtres, qualification, flux | ✅ Livré (#395) | #386 |
| 4 | Soldes, continuité & espèces | ✅ Livré (#396) | #387 |
| 5 | Ventilation — FK `bank_transaction` + split + invariant | ✅ Livré (#397) | #388 |
| 6 | Rapprochement automatique + file de suggestions | ✅ Livré (#398) | #389 |
| 7 | Recettes, virements internes, couverture dans le bilan | ⬜ À faire | #390 |
| 8 | Intégration agent (lecture seule) | ⬜ À faire | #391 |
| 9 | **Différé V2** — import PDF/photo via le pipeline vision | ⬜ Différé | #392 |

## Doc associée

- Doc produit : [PARCOURS_25_RELEVES_BANCAIRES.md](./PARCOURS_25_RELEVES_BANCAIRES.md)
- Fiche concept : [IMPORT_ET_RAPPROCHEMENT.md](../fiches/IMPORT_ET_RAPPROCHEMENT.md)
- Cartographie de l'existant : [CARTOGRAPHIE_DEPENSES.md](../fiches/CARTOGRAPHIE_DEPENSES.md)
- **Pattern d'import de référence** : `apps/electricity/importers/` (`base.py`, `registry.py`, `generic_csv.py`, `enedis_xlsx.py`) et `apps/electricity/services.py::import_consumption_file`
- Pattern backend service/agent : `apps/tasks/` et `apps/budget/`
- `CLAUDE.md`, sections « Interaction vs modèle dédié », « Pattern standard — Feature page », « Agent — actions d'écriture »

## Flow cible

1. L'utilisateur déclare ses comptes (2 banques + 1 compte espèces), avec solde d'ouverture.
2. Il dépose l'export CSV/XLSX de sa banque → mapping de colonnes décrit **une fois**, mémorisé sur le compte.
3. Les opérations apparaissent dans le journal bancaire ; réimporter ne duplique rien.
4. Le solde calculé est confronté au relevé ; une rupture de chaîne est signalée.
5. Il qualifie : mouvement interne (retrait, virement inter-banques), note.
6. Il **ventile** une opération en un ou plusieurs postes (budget + zone), ou la rattache à un achat déjà saisi.
7. À l'import, les achats saisis dans l'app se rapprochent **automatiquement** de leur ligne ; les cas douteux tombent dans une file de suggestions.
8. Les recettes et les mouvements internes sont exclus des agrégats de dépense ; le bilan mensuel gagne un taux de couverture.

## Décisions de cadrage (toutes tranchées)

- **Formats V1 : CSV + XLSX.** Les deux banques du foyer exportent ça. PDF/photo → lot 9 différé, OFX/CAMT hors V1.
- **Il n'y a pas de table `Allocation`. Une `Interaction(type='expense')` EST une ventilation.** Une ligne de 120 € splittée 80/40 = deux interactions pointant la même `BankTransaction` via une FK nullable. Justification complète : fiche concept §4.1. **Conséquence opérationnelle : `amount` reste une colonne scalaire, et les 9 `Sum("amount")` du projet ne bougent pas.**
- **`BankAccount` / `StatementImport` / `BankTransaction` sont des modèles dédiés** — la contrainte `unique(account, dedup_hash)` fonde l'idempotence de l'import, critère explicite de la règle du `CLAUDE.md`.
- **Le budget vit sur la ventilation**, donc sur l'`Interaction` — la FK `Interaction.budget` existante est réutilisée telle quelle, aucune migration de budget.
- **`Interaction.amount` est toujours positif ; `BankTransaction.amount` est signé.** Un remboursement n'est jamais une interaction négative (ça casserait `top_expenses` et `_spent_by_budget`) → colonne `direction` explicite.
- **On n'additionne jamais un total banque et un total interactions.** Les agrégats budget/dépenses lisent les `Interaction` exclusivement. Le pont est un taux de couverture, pas une somme.
- **Soldes suivis**, ancrés sur `balance_after` quand la banque l'exporte, dérivés de `opening_balance + Σ` sinon. **Jamais dénormalisés en colonne.**
- **Espèces = un `BankAccount(kind='cash')`**, alimenté par une contrepartie de retrait (`transfer_counterpart`). Proposée, jamais imposée.
- **Auto-match seulement sur montant strictement égal.** Tout écart produit une suggestion. Justification : fiche concept §3.3.
- **`DELETE` interdit sur `StatementImport`** — supprimer puis réimporter recrée les lignes avec de nouveaux UUID et perd toutes les ventilations.
- **Règle API héritée de l'électricité** : un échec **métier** (fichier illisible) renvoie **201** avec `status='failed'`, pas une erreur HTTP. Seules les erreurs de requête sont 400.

---

## Lot 1 — Socle `apps/banking` : les comptes (#384)

### But

Poser l'app et le modèle `BankAccount`, avec son CRUD et son module de navigation. Aucun import, aucune transaction. Débloque tous les autres lots.

### Fichiers

**Backend**
- `apps/banking/{__init__,apps,models,serializers,services,views,urls,admin}.py`
- `apps/banking/models.py` → `BankAccount(HouseholdScopedModel)` : `name` (120), `bank_label` (120), `kind` (`bank`|`cash`, défaut `bank`), `currency` (3, défaut `EUR`), `iban_last4` (4), `opening_balance` (Decimal 14,2, défaut 0), `opening_balance_date` (Date, null), `default_provider` (50), `import_options` (JSON), `archived` (bool). `db_table='bank_accounts'`, `UniqueConstraint(household, name)`, index `(household, archived)`.
- `apps/banking/services.py` → `create_account(*, household, user, **fields) -> BankAccount` ; `update_account(*, account, user, fields: dict) -> BankAccount` ; `archive_account(*, account, user) -> BankAccount`
- `apps/banking/views.py` → `BankAccountViewSet(ModelViewSet)`, `perform_create`/`perform_update` délèguent au service (pattern `apps/budget/views.py`), permission `IsHouseholdMember`
- `config/settings/base.py` (INSTALLED_APPS `"banking"`), `config/urls.py` (`path("api/banking/", include("banking.urls"))`)
- `apps/banking/tests/{factories,test_models,test_services,test_views_accounts}.py`

**Frontend**
- `ui/src/lib/api/banking.ts` → types `BankAccount`, `BankAccountPayload` + CRUD
- `ui/src/features/banking/{hooks,BankingPage,AccountCard,AccountDialog}.tsx` — pattern Feature page du `CLAUDE.md` (`bankingKeys`, `useDeleteWithUndo` pour l'archivage, `Card`/`CardTitle`/`CardActions`, `EmptyState`, `useDelayedLoading`)
- `ui/src/router.tsx` (route lazy), `ui/src/lib/modules.ts` (`{ key: 'banking', group: 'tracking', optional: true }`)
- `apps/households/modules.py` → `'banking'` dans `OPTIONAL_MODULES` **et** `PINNABLE_MODULES`
- Locales ×4 : namespace `banking.*`

### Critères

1. CRUD compte scopé foyer ; nom dupliqué → 400 avec message exploitable.
2. Compte `kind='cash'` créable sans `bank_label` ni `iban_last4`.
3. Archiver masque le compte de la liste par défaut sans rien supprimer ; `?archived=true` le retrouve.
4. `opening_balance` accepte un négatif (découvert) ; `opening_balance_date` nullable.
5. Module désactivable depuis les réglages foyer → l'entrée sidebar disparaît.
6. Aucun IBAN complet stocké nulle part (revue de code + test).
7. `npm run gen:api:refresh` passé, types committés.

---

## Lot 2 — Import CSV/XLSX (#385)

### But

Déverser un export bancaire de façon idempotente, avec trace d'import. C'est le lot qui décalque `apps/electricity/importers/`.

### Fichiers

- `apps/banking/importers/base.py` → `ImporterError`, `ImporterFormatError`, `decode_text(raw: bytes) -> str`, `@dataclass(frozen=True) NormalizedTransaction` (`booked_on: date`, `value_on: date|None`, `label_raw: str`, `amount: Decimal`, `currency: str`, `balance_after: Decimal|None`, `external_id: str`), `BaseStatementImporter(ABC)` (`key`, `label`, `detect(raw)->bool`, `parse(raw, *, options)->list[NormalizedTransaction]`, `sample_lines(raw)`)
- `apps/banking/importers/registry.py` → `register`, `get_importer`, `importer_choices`, `detect_importer` (copie conforme de l'électricité) ; auto-enregistrement dans `importers/__init__.py`
- `apps/banking/importers/parsing.py` → `parse_amount(text, *, decimal_separator=None) -> Decimal` ; `parse_date(text, *, fmt=None) -> date` ; `normalize_label(raw: str) -> str`
- `apps/banking/importers/generic_csv.py` → `GenericStatementCsvImporter` (`detect()` renvoie toujours `False`). Options : `date_column`, `label_column`, `amount_column` **OU** (`debit_column` + `credit_column`), `balance_column?`, `reference_column?`, `value_date_column?`, `date_format?`, `decimal_separator?`, `delimiter?`, `skip_rows?`, `invert_sign?`
- `apps/banking/importers/generic_xlsx.py` → même contrat via `openpyxl` (`read_only=True, data_only=True`), détection par magic `PK\x03\x04`
- `apps/banking/models.py` → `StatementImport` (`account` FK CASCADE, `provider`, `filename`, `status`, `created_count`, `skipped_count`, `auto_matched_count`, `error`, `period_start/end`) ; `BankTransaction` (voir schéma ci-dessous) ; `ImportStatus(TextChoices)`
- `apps/banking/dedup.py` → `compute_dedup_hash(*, account_id, booked_on, label_norm, amount, currency, discriminant) -> str` ; `assign_discriminants(rows: list[NormalizedTransaction]) -> list[str]`
- `apps/banking/services.py` → `import_statement_file(household, user, *, account, uploaded_file, provider=None, options=None) -> StatementImport` ; `preview_statement_file(raw: bytes) -> dict`
- `apps/banking/views.py` → `StatementImportViewSet` (`http_method_names = ["get","post","head","options"]`) + action `preview`
- `apps/banking/tests/{test_dedup,test_services_imports,test_importer_generic_csv,test_importer_generic_xlsx}.py` + `tests/fixtures/*.csv|.xlsx`
- `ui/src/features/banking/{StatementImportDialog,ColumnMappingForm,ImportHistoryCard}.tsx`

**`BankTransaction`** : `account` FK PROTECT, `booked_on` (Date), `value_on` (Date, null), `label_raw` (500, `editable=False`), `label_norm` (255, `editable=False`), `amount` (Decimal 14,2, **signé**), `currency` (3), `direction` (`out`|`in`), `is_internal` (bool), `balance_after` (Decimal 14,2, null), `external_id` (64), `dedup_hash` (64, `editable=False`), `source_import` FK SET_NULL, `notes`.
Contraintes : `UniqueConstraint(account, dedup_hash)`, `CheckConstraint(~Q(amount=0))`, `CheckConstraint` cohérence `direction`/signe. Index : `(household, booked_on)`, `(account, booked_on)`, `(household, direction, is_internal)`.

### Critères

1. Le fichier est **entièrement parsé et validé avant toute écriture** ; une ligne fautive → `StatementImport(status='failed', created_count=0)` en **201**, zéro transaction écrite, message portant le n° de ligne.
2. Réimporter le même fichier : `created_count=0`, `skipped_count=N`.
3. Deux fichiers chevauchants : seules les lignes nouvelles sont créées.
4. Deux lignes rigoureusement identiques le même jour, fichier **sans** colonne solde → 2 transactions créées ; les mêmes réimportées → 0 création.
5. Colonnes Débit/Crédit séparées **et** colonne signée donnent tous deux les bons signes.
6. `1 234,56` avec espace insécable (`\xa0` et ` `) → `Decimal("1234.56")` ; `(1 234,56)` → négatif.
7. Préambule de 6 lignes avant l'en-tête → toléré.
8. Contrainte `direction`/signe testée au niveau DB.
9. Le mapping est mémorisé sur le compte et pré-rempli à l'import suivant.
10. `DELETE /api/banking/imports/<id>/` → **405**.

---

## Lot 3 — Journal bancaire (#386)

### But

Lire, filtrer et qualifier ses opérations. Pas encore de lien vers les dépenses.

### Fichiers

- `apps/banking/queries.py` → `transactions(*, household_id=None, base=None) -> QuerySet` ; `with_allocated(qs) -> QuerySet` (annotation `allocated`, préparée pour le lot 5) — miroir de `interactions/queries.py`
- `apps/banking/aggregations.py` → `compute_account_flow(*, household, account=None, date_from, date_to) -> dict`
- `apps/banking/views.py` → `BankTransactionViewSet` (filtres `account`, `date_from`, `date_to`, `direction`, `is_internal`, `q` sur `label_norm`) + action `qualify` (PATCH `is_internal` / `notes`)
- `apps/banking/serializers.py` → `BankTransactionSerializer` (`label_raw`, `amount`, `dedup_hash` en lecture seule)
- `ui/src/features/banking/{TransactionList,TransactionRow,TransactionFilters,FlowSummaryCards}.tsx`
- `apps/banking/tests/{test_views_transactions,test_aggregations}.py`

### Critères

1. Liste paginée triée `-booked_on`, scopée foyer, filtrable sur les 6 critères.
2. `is_internal=True` exclut la ligne de `compute_account_flow`.
3. `label_raw` et `amount` sont en lecture seule via l'API (PATCH → 400 ou ignoré, testé).
4. **Aucune modification d'un des 9 `Sum("amount")` existants** — vérifiable au diff de la PR. Critère de succès du choix d'architecture.
5. Filtre `q` insensible à la casse et aux accents (il porte sur `label_norm`).

---

## Lot 4 — Soldes, continuité & espèces (#387)

### But

Rendre le solde de chaque compte lisible et **auto-vérifiable**. Placé tôt à dessein : le solde est le meilleur test de l'import — s'il tombe juste sur le relevé papier, l'import est bon.

### Fichiers

- `apps/banking/balances.py` → `compute_balance(*, account, as_of=None) -> BalanceResult` (dataclass : `amount`, `source` ∈ `anchored`|`derived`, `as_of`, `is_reliable`) ; `check_balance_chain(*, account) -> list[ChainGap]` (dataclass : `after_transaction_id`, `expected`, `actual`, `gap_start`, `gap_end`)
- `apps/banking/models.py` → `BankTransaction.transfer_counterpart` (self-FK `SET_NULL`, null, `related_name='counterpart_of'`)
- `apps/banking/services.py` → `record_cash_withdrawal(*, user, transaction, cash_account, amount=None) -> BankTransaction` (crée la contrepartie créditrice, marque les deux `is_internal=True`, les lie symétriquement) ; `unlink_counterpart(*, user, transaction) -> None`
- `apps/banking/views.py` → action `balance` sur `BankAccountViewSet` ; action `withdraw_to_cash` sur `BankTransactionViewSet`
- `ui/src/features/banking/{AccountCard,BalanceBadge,ChainGapAlert,WithdrawToCashDialog}.tsx`
- `apps/banking/tests/{test_balances,test_chain_check,test_cash_counterpart}.py`

### Critères

1. Compte **avec** colonne solde → `source='anchored'`, valeur = `balance_after` de la transaction la plus récente.
2. Compte **sans** colonne solde → `source='derived'`, valeur = `opening_balance + Σ(amount)` depuis `opening_balance_date`.
3. Un trou volontaire dans le fichier (lignes retirées au milieu) est **détecté** : `check_balance_chain` renvoie l'intervalle, l'UI affiche « chaîne rompue entre le JJ/MM et le JJ/MM », et le solde est marqué non fiable.
4. Chaîne intacte → aucun gap remonté.
5. Retrait de 100 € → contrepartie `+100` sur le compte espèces, les deux `is_internal=True`, liées dans les deux sens.
6. Solde espèces = contrepartie − dépenses en liquide (test bout en bout).
7. Une transaction avec `transfer_counterpart` **n'apparaît ni dans `inflow` ni dans `outflow`**.
8. Supprimer un côté de la contrepartie ne laisse pas l'autre pointer dans le vide.
9. Le solde n'est stocké dans **aucune colonne** (revue de code).

---

## Lot 5 — Ventilation (#388)

### But

**Le cœur du parcours.** Une opération porte N dépenses ; le budget vit sur la dépense.

### Fichiers

- `apps/interactions/models.py` → `bank_transaction` FK `'banking.BankTransaction'` SET_NULL null `related_name='interactions'` ; `reconciled_by` (`auto`|`manual`, blank) ; index partiel `idx_int_unreconciled_amount` sur `(household, amount)` condition `Q(type='expense', bank_transaction__isnull=True)`
- `apps/interactions/migrations/00XX_add_bank_transaction.py` — ⚠ `dependencies` sur la migration `banking` qui crée `BankTransaction`
- `apps/interactions/kinds.py` **(nouveau)** → `EXPENSE_KINDS: frozenset[str]` + constantes `KIND_BANK`, `KIND_MANUAL`, `KIND_RECURRING`, `KIND_STOCK_PURCHASE`… (rembourse la dette ⑤ de la cartographie)
- `apps/interactions/services.py` → `create_bank_expense_interaction(*, household, user, transaction, subject, amount, budget_id=None, zone_ids=None, notes="") -> Interaction` (passe par `_build_expense_metadata`, `occurred_at` = **midi tz foyer** de `booked_on`)
- `apps/banking/validators.py` → `assert_allocation_fits(*, transaction, interactions, extra_amount=Decimal("0")) -> None`
- `apps/banking/services.py` → `set_allocations(*, household, user, transaction, lines: list[dict]) -> list[Interaction]` (sémantique **set**, `select_for_update` sur la transaction) ; `link_interaction(*, user, transaction, interaction, by="manual")` ; `unlink_interaction(*, user, interaction)` ; `delete_transaction(*, user, transaction)`
- `apps/interactions/serializers.py` → `bank_transaction` en lecture seule + appel de `assert_allocation_fits` dans `validate()` quand `amount` change sur une interaction rapprochée
- `apps/banking/views.py` → actions `allocations` (PUT), `link` (POST), `unlink` (DELETE)
- `ui/src/features/banking/AllocationDialog.tsx` (lignes budget/montant, « reste à ventiler » live) ; `ui/src/features/expenses/ExpenseList.tsx` (regroupement visuel par `bank_transaction`)
- `apps/banking/tests/test_services_allocations.py`, `apps/interactions/tests/test_bank_link.py`

### Critères

1. 120 € ventilés 80/40 → 2 interactions, 2 budgets, `_spent_by_budget` **inchangé dans sa forme** et exact dans son résultat.
2. Sur-ventilation (80 + 50 sur 120) → 400, rien écrit.
3. `PATCH /api/interactions/<id>/` portant `amount` 80 → 100 sur une opération de 120 déjà ventilée 80/40 → **400** (l'invariant tient aussi hors du service de ventilation).
4. Supprimer l'opération : l'achat de stock rapproché **survit** avec `bank_transaction=NULL` ; les interactions `kind='bank'` sont supprimées.
5. Retirer une ligne de la ventilation d'un achat de stock rapproché → l'interaction est **détachée**, jamais supprimée.
6. Une interaction ne peut être liée qu'à une opération du même foyer.
7. Une opération avec `transfer_counterpart` n'est pas ventilable (400).
8. `Project.actual_cost` inchangé sur une dépense projet rapprochée.
9. Une dépense née d'une opération n'a **pas de zone** → `ExpenseList` et le détail interaction ne cassent pas (`InteractionViewSet.perform_create` exige ≥ 1 zone : passage obligatoire par le service).
10. Le « reste à ventiler » consomme `interactions.queries.sum_amount()` — pas un 10ᵉ `Sum("amount")` en dur.

---

## Lot 6 — Rapprochement automatique (#389)

### But

Le lot qui décide de l'adoption. Sans lui, l'utilisateur ventile ~160 lignes par mois à la main et décroche.

### Fichiers

- `apps/banking/matching.py` → `@dataclass(frozen=True) MatchCandidate` (`interaction_id`, `transaction_id`, `score`, `amount_delta`, `day_gap`, `label_ratio`) ; `score_pair(interaction, transaction, *, tz) -> MatchCandidate | None` ; `find_candidates(*, household, transactions, tz) -> list[MatchCandidate]` ; `auto_reconcile(*, household, user, transactions=None, date_from=None, date_to=None) -> dict` (glouton stable) ; `suggestions_for(*, transaction, tz, limit=5) -> list[MatchCandidate]`
- `apps/banking/services.py` → appel de `auto_reconcile` en fin de `import_statement_file`, **dans le même `atomic()`**, sur les seules transactions créées ; alimente `auto_matched_count`
- `apps/banking/views.py` → action `reconcile` (POST, détail=False) ; action `suggestions` (GET, détail=True)
- `config/settings/base.py` → `BANKING_MATCH_WINDOW_BEFORE_DAYS = 7`, `BANKING_MATCH_WINDOW_AFTER_DAYS = 3`, `BANKING_MATCH_AUTO_THRESHOLD = 0.85`, `BANKING_MATCH_SUGGEST_THRESHOLD = 0.55`
- `ui/src/features/banking/{ReconcileQueue,SuggestionRow}.tsx`
- `apps/banking/tests/test_matching.py`

### Critères

1. Achat de stock 32,50 € du 12/07 + ligne `CB LECLERC` −32,50 € du 14/07 → **auto-lié**, `reconciled_by='auto'`.
2. Même cas avec 32,45 € côté banque → **suggestion**, aucun lien écrit.
3. 2 achats de 20 € face à 2 lignes de 20 € → 2 liens distincts, aucune interaction liée deux fois, aucune opération sur-ventilée.
4. Une opération déjà entièrement ventilée n'est jamais candidate.
5. Un `kind='recurring'` (confirmation d'échéance) se rapproche de son prélèvement — test explicite.
6. Import de 300 lignes : pas de N+1 (`django_assert_num_queries` borné).
7. `reconcile` est **idempotent** : relancer ne change rien.
8. `undo_purchase` sur un achat de stock rapproché rend l'opération partiellement ventilée sans erreur.

---

## Lot 7 — Recettes, virements internes, couverture (#390)

### But

Le flux entrant et l'exclusion des mouvements internes, **sans polluer** les agrégats de dépense.

### Fichiers

- `apps/banking/aggregations.py` → `compute_month_flow(*, household, month: str) -> dict` (`inflow`, `outflow`, `net`, `internal_count`, `unallocated_outflow`, `coverage_ratio`)
- `apps/banking/rules.py` **(nouveau)** → `guess_internal(label_norm: str) -> bool` (motifs `VIREMENT INTERNE`, `RETRAIT DAB`, `VIR SEPA`…) appliqué à l'import comme **valeur par défaut modifiable**, jamais comme vérité
- `apps/budget/report/stats.py` → **bloc `bank` additionnel** dans le snapshot (`{inflow, outflow, coverage_ratio}`), sans toucher aux clés existantes ni aux `Sum("amount")`
- `apps/budget/report/render.py` → une phrase sur la couverture, localisée
- `ui/src/features/banking/FlowSummaryCards.tsx`, `ui/src/features/budget/ReportsPage.tsx`
- `apps/banking/tests/test_flow.py`, `apps/budget/tests/test_report_bank_block.py`

### Critères

1. Les totaux dépenses/budget restent **exclusivement** issus des `Interaction` — test de non-régression sur `compute_budget_overview` avec des opérations non ventilées en base.
2. `is_internal=True` exclu de `inflow` **et** de `outflow`.
3. Un rapport mensuel généré **avant** ce lot reste lisible (bloc `bank` optionnel, snapshot rétro-compatible).
4. Le rapport affiche « X % de vos sorties sont ventilées ».
5. `guess_internal` est un défaut : l'utilisateur peut le contredire, et son choix n'est jamais réécrit par un import ultérieur.

---

## Lot 8 — Intégration agent, lecture seule (#391)

### But

« Combien j'ai dépensé chez Leclerc ce mois-ci ? » via le RAG, sans toucher à `apps/agent/`.

### Fichiers

- `apps/banking/apps.py::ready()` → `SearchableSpec(entity_type='bank_transaction', search_fields=('label_norm','notes'), label_attr, url_template)` ; `ListableSpec` avec `ListFilter` (`account`, `direction`, `booked_after`, `booked_before`, `is_internal`) + `describe` + `amount_of`
- `apps/banking/agent.py` → `_describe_transaction`, `_filter_*`, `_resolve_*`
- `apps/agent/tools.py` → extension de la **description** de `list_entities` (seule retouche autorisée dans `apps/agent/`)

### Critères

1. L'agent trouve une opération par libellé et agrège les montants d'une période.
2. **Aucun `WritableSpec`** : l'agent ne peut ni créer ni supprimer une opération (une ligne bancaire n'est pas une donnée saisissable).
3. Le `describe` ne fuit ni IBAN ni solde.
4. Zéro modification de la logique de `apps/agent/`.

---

## Lot 9 — Différé V2 : import PDF / photo (#392)

### But

Capturer le besoin exprimé au départ sans le traiter en V1 — les deux banques exportent du CSV, il n'est donc pas bloquant.

### Ce qui manque aujourd'hui

- `agent.llm.vision_extract` renvoie du **texte brut** ; `run()` n'a ni `tool_choice` ni forced-JSON → il manque un helper « image/PDF → **JSON structuré** ».
- `vision_extract` ne prend **qu'une image par appel** (pas de bloc `document` natif Anthropic).
- L'OCR est **synchrone dans la requête HTTP** (`apps/documents/views.py::_run_extraction`) — un relevé de 10 pages, c'est 10 appels vision à 200 DPI, donc un risque de timeout. Aucune queue dans le projet.
- `apps/core/file_validation.py` n'autorise ni CSV ni XLSX (à élargir dès le lot 2), et `AIUsageLog.Feature` devra gagner une valeur.

### Contrat à préserver

Tout adaptateur produit des `NormalizedTransaction` : rien de « CSV » ne fuit dans `services.py`, et l'extraction vision se branche comme un `BaseStatementImporter` de plus.

---

## Ordre recommandé

**1 → 2 → 3 → 4 → 5 → 6 → 7 → 8.**

- Les lots 1-2 sont le socle ; rien n'est utilisable avant.
- Le **lot 4 est délibérément placé avant la ventilation** : il valide que l'import est juste *avant* qu'on ventile six mois de dépenses sur des données fausses.
- Le **lot 6 décide de la survie du système**. À prototyper sur des données réelles avant d'investir dans 7-8.
- Les lots 7-8 sont du confort et peuvent glisser.

## Points de vigilance

1. **Ordre inter-apps des migrations** : la migration `interactions` (lot 5) doit déclarer `dependencies` sur la migration `banking` créant `BankTransaction`. Référencer le modèle par chaîne `'banking.BankTransaction'` pour éviter l'import circulaire.
2. **`banking` dans `INSTALLED_APPS` avant** de générer la `0001`, sinon `makemigrations` ne voit rien.
3. `CheckConstraint` → `condition=` (Django 5), pas `check=` (déprécié).
4. **Surface de l'invariant** : `Interaction.amount` est écrit par 6 producteurs + `InteractionSerializer` (PATCH direct) + `stock.services.undo_purchase`. Aucun ne connaît la ligne bancaire → `assert_allocation_fits` doit être appelé depuis le serializer **et** depuis le service.
5. **Fuseau horaire** : `occurred_at` est un datetime aware, `booked_on` une date nue. Toute conversion passe par la tz du foyer (motif `budget/aggregations.py::current_month_range`), et **à midi** — à minuit, une opération du 1er ou du 31 changerait de mois, donc de budget.
6. **`dedup_hash` jamais recalculé** (`editable=False`). Faire évoluer la recette = bumper le préfixe `v1` + commande de recalcul explicite.
7. **Ne jamais persister d'IBAN complet.** Un `label_raw` de virement peut en contenir un : acceptable, mais à mentionner dans `docs/MODULES/banking.md`.
8. **Nouveau `kind='bank'`** à propager : `ExpenseFilters.tsx`, `_describe_interaction` (`apps/interactions/apps.py`), labels de rapport, i18n ×4.
9. **`interactions.queries.sum_amount()` n'a aucun appelant** aujourd'hui — le « reste à ventiler » du lot 5 doit l'utiliser.
10. `npm run gen:api:refresh` après chaque lot backend (serveur Django sur :8001).

## Définition de done technique

Pour **chaque** lot, avant merge :

1. Le service est le point d'entrée unique des écritures ; le viewset y délègue (aucune logique métier dans la view).
2. `pytest` vert, y compris les tests d'idempotence et d'invariant du lot.
3. `npm run lint` propre ; types API régénérés et committés si le backend a bougé.
4. i18n : toutes les clés dans les **4 locales** (en/fr/de/es), **jamais de `defaultValue`** (skill `/translate`).
5. Composants partagés réutilisés (`Card`, `CardTitle`, `CardActions`, `BackLink`, `EmptyState`, `formatAmount`) — aucun formatteur de montant local, aucune couleur Tailwind hardcodée.
6. **Fiche `docs/MODULES/banking.md`** créée au lot 1 puis tenue à jour à chaque lot.
7. **Tutoriels** (skill `/tutorials`) : le module `banking` change le parcours utilisateur → guide créé au lot 3 et complété ensuite, registre + 4 locales, dans la même PR.
8. Commit conventionnel `feat(banking): …` ; PR fermant l'issue du lot (`Closes #N`). L'**issue parente** ne se ferme qu'une fois tous les lots livrés.
