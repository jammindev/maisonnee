"""Un chantier privé ne change aucun chiffre pour personne.

C'est **le** test du lot 4 du parcours 33, et le seul endroit où ce parcours peut
casser une règle existante du dépôt.

L'arbitrage était : « le secret porte sur *quoi*, jamais sur *combien* ». Une
dépense de chantier privé reste dans ``interactions.queries.expenses()``, point de
vérité unique de sept agrégations — barre de budget, ``coverage_ratio``,
``Project.actual_cost``, bilan mensuel figé, détecteurs de conformité. L'en retirer
donnerait au budget « Bricolage » **deux valeurs selon le lecteur**, ce que
``CLAUDE.md`` interdit sous « un compteur ne peut pas avoir deux définitions ».

Pourquoi ce test et pas une relecture
-------------------------------------

Le défaut qu'il attrape n'est pas un oubli, c'est une **correction bien
intentionnée**. Quelqu'un lira un jour ``interactions.queries.expenses()``,
remarquera qu'il ne filtre pas la confidentialité, et « corrigera ». Le diff aura
l'air juste : il ressemblera trait pour trait à tous les autres filtres de
visibilité du dépôt. Rien ne rougira — sauf ici.

Le test compare donc **deux lecteurs**, jamais une valeur écrite en dur : une
valeur en dur devient fausse au premier changement de fixture, alors que l'égalité
entre deux lecteurs reste exactement la propriété qu'on veut tenir.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from budget.models import Budget
from households.models import Household, HouseholdMember
from interactions.models import Interaction
from projects.models import Project
from projects.services import project_actual_cost


@pytest.fixture
def duo(db):
    household = Household.objects.create(name="Foyer à deux")
    alice = UserFactory(email="money-alice@example.com")
    bob = UserFactory(email="money-bob@example.com")
    HouseholdMember.objects.create(household=household, user=alice, role="owner")
    HouseholdMember.objects.create(household=household, user=bob, role="member")
    for user in (alice, bob):
        user.active_household = household
        user.save(update_fields=["active_household"])
    return household, alice, bob


def _as(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def chantier_with_an_expense(duo):
    """Un chantier d'Alice, une dépense de 250 € imputée à « Bricolage »."""
    household, alice, _bob = duo
    budget = Budget.objects.create(
        household=household, created_by=alice,
        name="Bricolage", monthly_amount=Decimal("400.00"),
    )
    project = Project.objects.create(
        household=household, created_by=alice, title="Cabane surprise",
    )
    Interaction.objects.create(
        household=household, created_by=alice,
        subject="Achat — Cabane surprise", type="expense",
        amount=Decimal("250.00"), supplier="Leroy Merlin",
        occurred_at=timezone.now(), budget=budget,
        source_content_type=ContentType.objects.get_for_model(Project),
        source_object_id=project.id,
    )
    return project, budget


def _budget_overview_rows(user):
    response = _as(user).get(reverse("budget-overview"))
    assert response.status_code == 200, response.data
    payload = response.data
    return payload["budgets"] if isinstance(payload, dict) and "budgets" in payload else payload


@pytest.mark.django_db
class TestPrivatisingAProjectMovesNoNumber:
    def test_the_projects_actual_cost_is_the_same_before_and_after(
        self, duo, chantier_with_an_expense
    ):
        project, _budget = chantier_with_an_expense
        before = project_actual_cost(project)

        project.is_private = True
        project.save(update_fields=["is_private"])

        assert project_actual_cost(project) == before == Decimal("250.00")

    def test_the_budget_panel_says_the_same_thing_to_both_members(
        self, duo, chantier_with_an_expense
    ):
        """La barre « Bricolage » ne peut pas valoir 250 € chez l'une et 0 € chez l'autre."""
        _household, alice, bob = duo
        project, _budget = chantier_with_an_expense
        project.is_private = True
        project.save(update_fields=["is_private"])

        seen = {}
        for user in (alice, bob):
            rows = _budget_overview_rows(user)
            seen[user.email] = {row["name"]: row["spent"] for row in rows}

        assert seen[alice.email] == seen[bob.email], (
            "La barre de budget donne deux chiffres selon le lecteur : "
            f"{seen}. Une dépense de chantier privé DOIT rester dans les totaux — "
            "c'est son contenu qui se masque, pas son montant."
        )
        assert seen[bob.email]["Bricolage"] == "250.00"

    def test_the_expense_is_still_listed_to_the_other_member(
        self, duo, chantier_with_an_expense
    ):
        """Le pendant du test du dessus côté liste : le total doit se recomposer.

        Si la ligne disparaissait pendant que le total la compte, Bob lirait
        « 250 € dépensés » au-dessus d'une liste vide — et ne pourrait pas savoir
        lequel des deux se trompe.
        """
        _household, _alice, bob = duo
        project, _budget = chantier_with_an_expense
        project.is_private = True
        project.save(update_fields=["is_private"])

        response = _as(bob).get(reverse("interaction-list"), {"type": "expense"})
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        assert len(rows) == 1
        assert rows[0]["amount"] == "250.00"

    def test_but_the_row_names_nothing(self, duo, chantier_with_an_expense):
        _household, _alice, bob = duo
        project, _budget = chantier_with_an_expense
        project.is_private = True
        project.save(update_fields=["is_private"])

        response = _as(bob).get(reverse("interaction-list"), {"type": "expense"})
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        assert rows[0]["is_redacted"] is True
        assert "Cabane surprise" not in str(rows[0]), (
            "Le sujet auto-généré d'un achat de chantier est « Achat — <titre> » : "
            "sans masquage, privatiser ferait fuiter le titre dans la liste des "
            "dépenses."
        )
