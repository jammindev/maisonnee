"""
Budget write service — single source of truth for create/update/delete.

Both the REST viewset and the agent's ``create_entity`` tool go through these
functions so validation (through ``BudgetSerializer``) and the household-scope
invariants live in one place. Never write budgets via the raw ORM from a
caller — always here.
"""
from __future__ import annotations

import unicodedata

from decimal import Decimal

import calendar
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Budget, BudgetCategory, RecurringExpense
from .serializers import (
    BudgetCategorySerializer,
    BudgetSerializer,
    RecurringExpenseSerializer,
)


def _save_scoped(serializer, household, user, *, creating: bool) -> Budget:
    """Persist through the serializer, mapping DB uniqueness clashes to 400s.

    The two unique constraints (one global per household, unique name per
    household) can only be checked at write time — a race or a duplicate name
    surfaces as ``IntegrityError`` which we translate into the same field errors
    a client expects from validation.
    """
    try:
        with transaction.atomic():
            if creating:
                return serializer.save(household=household, created_by=user)
            return serializer.save(updated_by=user)
    except IntegrityError as exc:
        message = str(exc).lower()
        if "one_global_budget_per_household" in message:
            raise ValidationError(
                {"is_global": "This household already has a global budget."}
            )
        if "unique_budget_name_per_household" in message:
            raise ValidationError({"name": "A budget with this name already exists."})
        raise ValidationError({"detail": "Could not save the budget."})


def create_budget(
    household,
    user,
    *,
    name: str,
    monthly_amount: Decimal | str | float | None = None,
    is_global: bool = False,
    category_id=None,
) -> Budget:
    """Create a budget for ``household`` on behalf of ``user``.

    ``monthly_amount=None`` creates a **tracked category with no ceiling** — the
    common case for « Cadeaux » or « Santé », which one wants to see totalled
    without pretending to cap them. The global budget still requires one.

    ``category_id`` files the envelope under a ``BudgetCategory``. It is a real
    parameter, not a passthrough: this signature is an **allowlist**, and the
    previous grouping feature shipped dead precisely because its field never
    appeared here — the viewset copied three keys by hand, the group was dropped
    in silence, and the tests that would have caught it built their parents
    straight through the ORM.

    Reuses ``BudgetSerializer`` for validation (positive amount when given,
    non-blank name, household-scoped category). Raises
    ``rest_framework.ValidationError`` on invalid input or a uniqueness clash
    (duplicate name, second global budget).
    """
    data = {
        "name": name,
        "monthly_amount": monthly_amount,
        "is_global": bool(is_global),
    }
    if category_id is not None:
        data["category_id"] = category_id

    serializer = BudgetSerializer(
        data=data, context={"request": _HouseholdContext(household)}
    )
    serializer.is_valid(raise_exception=True)
    return _save_scoped(serializer, household, user, creating=True)


def resolve_budget_by_name(household, name):
    """L'enveloppe que désigne ce mot, ou ``None`` — jamais une devinette.

    Le pendant de ``zones.services.resolve_zone`` pour l'argent, et il existe
    pour la même raison : un foyer dit « Travaux », pas un UUID, et un seul
    endroit doit décider ce que « Travaux » veut dire. Sans ce point unique, la
    création assistée d'un chantier (parcours 32) aurait rouvert un second chemin
    de désignation à côté des ids.

    La comparaison ignore la casse et les accents — « travaux » doit retrouver
    « Travaux », ce ne sont pas des différences de désignation. Le **budget
    global est exclu** : il ne classe rien, il plafonne tout, et imputer un
    chantier au plafond du foyer n'a pas de sens.

    Renvoie ``None`` plutôt que de lever : pour l'appelant, « ce nom n'existe pas
    encore » n'est pas une erreur, c'est la branche « alors on la crée ».
    """
    needle = _fold(name)
    if not needle:
        return None
    household_id = getattr(household, "id", household)
    for budget in Budget.objects.filter(household_id=household_id, is_global=False):
        if _fold(budget.name) == needle:
            return budget
    return None


def _fold(text) -> str:
    """Minuscule sans accents — même normalisation que ``zones.services._fold``."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold().strip()


def update_budget(household, user, budget: Budget, *, fields: dict) -> Budget:
    """Update ``budget`` — shared by the REST update and the agent's update.

    ``name``, ``monthly_amount``, ``is_global`` and ``category_id`` are editable.
    Validation and uniqueness handling mirror ``create_budget``.

    ``category_id`` is in the allowlist **and** ``None`` is forwarded rather than
    stripped: clearing the category is how a budget leaves it, so dropping the
    key would make the filing one-way. Callers that mean "leave it alone" simply
    omit the key.
    """
    allowed = {"name", "monthly_amount", "is_global", "category_id"}
    payload = {k: v for k, v in fields.items() if k in allowed}
    # ``validated_data`` echoes the resolved instance under ``category``; map it
    # back so a REST PATCH round-trips through the same key the agent uses.
    if "category" in fields and "category_id" not in payload:
        category = fields["category"]
        payload["category_id"] = getattr(category, "id", None)

    serializer = BudgetSerializer(
        budget,
        data=payload,
        partial=True,
        context={"request": _HouseholdContext(household)},
    )
    serializer.is_valid(raise_exception=True)
    return _save_scoped(serializer, household, user, creating=False)


class _HouseholdContext:
    """Minimal stand-in for ``request`` so the serializer can scope the category.

    ``BudgetSerializer._validate_category`` reads ``context['request'].household``
    to scope its lookup. The agent path has no HTTP request, and passing the real
    one from the viewset would make the service depend on the transport.
    """

    __slots__ = ("household",)

    def __init__(self, household):
        self.household = household


def delete_budget(household, user, budget: Budget) -> None:
    """Delete a budget — the undo of ``create_budget``.

    A hard delete. Thanks to ``Interaction.budget`` being ``on_delete=SET_NULL``,
    expenses attached to this budget are NOT deleted: they simply fall back to
    the "hors budget" bucket (AC of Lot 1). Scoped to the household defensively.
    """
    if budget.household_id != household.id:
        raise ValueError("delete_budget: budget belongs to another household")
    budget.delete()


# --- Budget categories ------------------------------------------------------


def _save_category_scoped(serializer, household, user, *, creating: bool) -> BudgetCategory:
    """Persist a category, mapping the name-uniqueness clash to a 400."""
    try:
        with transaction.atomic():
            if creating:
                return serializer.save(household=household, created_by=user)
            return serializer.save(updated_by=user)
    except IntegrityError as exc:
        if "unique_budget_category_name_per_household" in str(exc).lower():
            raise ValidationError({"name": "A category with this name already exists."})
        raise ValidationError({"detail": "Could not save the category."})


def create_budget_category(
    household,
    user,
    *,
    name: str,
    monthly_amount: Decimal | str | float | None = None,
) -> BudgetCategory:
    """Create a budget category — a heading that budgets are filed under."""
    serializer = BudgetCategorySerializer(
        data={"name": name, "monthly_amount": monthly_amount}
    )
    serializer.is_valid(raise_exception=True)
    return _save_category_scoped(serializer, household, user, creating=True)


def update_budget_category(
    household, user, category: BudgetCategory, *, fields: dict
) -> BudgetCategory:
    """Update a category. Only ``name`` and ``monthly_amount`` are editable."""
    allowed = {"name", "monthly_amount"}
    payload = {k: v for k, v in fields.items() if k in allowed}

    serializer = BudgetCategorySerializer(category, data=payload, partial=True)
    serializer.is_valid(raise_exception=True)
    return _save_category_scoped(serializer, household, user, creating=False)


def delete_budget_category(household, user, category: BudgetCategory) -> None:
    """Delete a category — its budgets survive, unfiled.

    ``Budget.category`` is ``SET_NULL``: deleting a heading must never take the
    envelopes that carry the money with it. The budgets simply return to the
    ungrouped list, keeping every euro they hold and every counter they feed.
    """
    if category.household_id != household.id:
        raise ValueError("delete_budget_category: category belongs to another household")
    category.delete()


# --- Recurring expenses (parcours 21 lot 2) ---------------------------------


_CADENCE_MONTHS = {
    RecurringExpense.Cadence.MONTHLY: 1,
    RecurringExpense.Cadence.QUARTERLY: 3,
    RecurringExpense.Cadence.YEARLY: 12,
}


def _add_months(d: date, months: int) -> date:
    """Add ``months`` to ``d``, clamping the day to the target month's length."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def advance_due_date(d: date, cadence: str) -> date:
    """Return the next occurrence date after ``d`` for ``cadence``."""
    months = _CADENCE_MONTHS.get(cadence)
    if months is None:
        raise ValueError(f"unknown cadence: {cadence!r}")
    return _add_months(d, months)


def catch_up_due_date(due: date, cadence: str, today: date) -> date:
    """La première occurrence **à venir**, en avançant d'autant de crans qu'il faut.

    `advance_due_date` avance d'**un** cran, ce qui suffit pour confirmer une
    échéance au fil de l'eau. Ça ne suffit pas quand on part d'une date ancienne :
    un cran depuis le 15 du mois dernier retombe le 15 de ce mois-ci, donc dans le
    passé dès qu'on est le 17.

    Fonction pure, et volontairement vérifiable sans base ni horloge gelée —
    c'est exactement le genre d'invariant qui tient tous les jours du mois sauf
    ceux où personne ne regarde.

    Idempotente sur une date déjà future, pour qu'un appelant n'ait pas à savoir
    s'il doit appeler.
    """
    if _CADENCE_MONTHS.get(cadence) is None:
        raise ValueError(f"unknown cadence: {cadence!r}")
    while due < today:
        due = advance_due_date(due, cadence)
    return due


def _resolve_recurring_budget(household_id, budget_id):
    """Resolve an optional budget for a recurrence (named budgets only).

    Reuses the interactions resolver so 'scoped to household' + 'not the global
    budget' stay defined in one place. Maps its ValueError to a DRF 400.
    """
    from interactions.services import _resolve_expense_budget

    try:
        return _resolve_expense_budget(household_id, budget_id)
    except ValueError as exc:
        raise ValidationError({"budget_id": str(exc)})


def create_recurring_expense(
    household,
    user,
    *,
    label: str,
    amount,
    cadence: str,
    next_due_date,
    supplier: str = "",
    notes: str = "",
    budget_id=None,
) -> RecurringExpense:
    """Create a recurring expense — shared by the REST viewset and the agent.

    Validates scalars through ``RecurringExpenseSerializer`` and resolves the
    optional budget separately (household-scoped, never the global budget).
    """
    # Le fournisseur d'une récurrence entre au catalogue comme celui d'une dépense :
    # c'est lui que ``banking.matching`` recopie sur l'occurrence confirmée, donc une
    # échéance saisie hors catalogue y ferait entrer une orthographe parallèle par la
    # petite porte.
    from interactions.services import register_supplier

    serializer = RecurringExpenseSerializer(
        data={
            "label": label,
            "amount": amount,
            "cadence": cadence,
            "next_due_date": next_due_date,
            "supplier": register_supplier(
                household_id=household.id, user=user, name=supplier or ""
            ),
            "notes": notes or "",
        }
    )
    serializer.is_valid(raise_exception=True)
    budget = _resolve_recurring_budget(household.id, budget_id)
    with transaction.atomic():
        return serializer.save(household=household, created_by=user, budget=budget)


def update_recurring_expense(household, user, recurring: RecurringExpense, *, fields: dict) -> RecurringExpense:
    """Update a recurring expense. ``budget_id`` (when present) re-resolves the FK."""
    if recurring.household_id != household.id:
        raise ValueError("update_recurring_expense: belongs to another household")
    allowed = {"label", "amount", "cadence", "next_due_date", "supplier", "notes"}
    payload = {k: v for k, v in fields.items() if k in allowed}
    if payload.get("supplier"):
        from interactions.services import register_supplier

        payload["supplier"] = register_supplier(
            household_id=household.id, user=user, name=payload["supplier"]
        )

    serializer = RecurringExpenseSerializer(recurring, data=payload, partial=True)
    serializer.is_valid(raise_exception=True)

    extra = {"updated_by": user}
    if "budget_id" in fields:
        extra["budget"] = _resolve_recurring_budget(household.id, fields.get("budget_id"))
    with transaction.atomic():
        return serializer.save(**extra)


def delete_recurring_expense(household, user, recurring: RecurringExpense) -> None:
    """Hard delete a recurring expense (the undo of ``create_recurring_expense``).

    Already-confirmed occurrences are real ``Interaction`` rows and are left
    untouched — only the schedule is removed.
    """
    if recurring.household_id != household.id:
        raise ValueError("delete_recurring_expense: belongs to another household")
    recurring.delete()


def confirm_recurring_occurrence(
    household,
    user,
    recurring: RecurringExpense,
    *,
    amount=None,
    occurred_at=None,
):
    """Confirm one due occurrence: create the expense and advance the schedule.

    Records a real ``Interaction(type='expense')`` via the interactions service
    (feeds the journal + budget counters), tagged ``kind='recurring'`` with a
    ``recurring_expense`` FK back-reference, then advances ``next_due_date`` by the
    cadence.

    Remains the **manual** path. Since parcours 26 lot 6 a statement import can
    confirm an occurrence by itself (``banking.matching.match_recurrences``); this
    stays for the bills no statement covers, and for the user who wants to record
    one ahead of the import. ``amount`` overrides the recurrence amount for this occurrence only
    (a bill varies). Never auto-called — always an explicit user action.

    Returns ``(interaction, recurring)``.
    """
    if recurring.household_id != household.id:
        raise ValueError("confirm_recurring_occurrence: belongs to another household")

    from interactions.services import create_manual_expense_interaction

    occurrence_amount = amount if amount is not None else recurring.amount
    with transaction.atomic():
        interaction = create_manual_expense_interaction(
            household=household,
            user=user,
            subject=recurring.label,
            amount=occurrence_amount,
            supplier=recurring.supplier,
            occurred_at=occurred_at or timezone.now(),
            notes=recurring.notes,
            budget_id=str(recurring.budget_id) if recurring.budget_id else None,
            kind="recurring",
            extra_metadata={"recurring_id": str(recurring.id)},
        )
        # La FK est ce que le contrôle de conformité requête (parcours 26 lot 6) ;
        # la clé JSON reste pour l'affichage. Écrite ici plutôt que passée au
        # créateur pour ne pas ajouter un paramètre `budget` à un service
        # `interactions` qui ne connaît pas les récurrences.
        interaction.recurring_expense = recurring
        interaction.save(update_fields=["recurring_expense"])
        recurring.next_due_date = advance_due_date(recurring.next_due_date, recurring.cadence)
        recurring.updated_by = user
        recurring.save(update_fields=["next_due_date", "updated_by", "updated_at"])

    return interaction, recurring
