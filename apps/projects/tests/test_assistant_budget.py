"""L'enveloppe du chantier — un axe de classement, jamais un plafond inventé.

Ce que ces tests défendent, dans l'ordre d'importance :

1. **une enveloppe de chantier n'est jamais plafonnée.** `Budget` est une
   enveloppe *mensuelle* et un chantier est un one-shot : dériver un plafond de
   `planned_budget` inventerait un chiffre, et une fois les travaux finis la barre
   afficherait « 0 € / 3 200 € » tous les mois pour toujours ;
2. **une enveloppe existante est réutilisée, pas dupliquée.** Et un `mode='new'`
   sur un nom déjà pris rend l'existante au lieu de heurter
   `unique_budget_name_per_household` — sinon renommer dans l'écran de relecture
   donnerait un 500 sur une saisie ordinaire ;
3. **le budget global n'est jamais une option.** Il ne classe rien, il plafonne
   tout ; imputer un chantier au plafond du foyer n'a aucun sens ;
4. **la désignation se fait par nom, résolue au tour d'entretien** — comme les
   zones, et par un seul point (`budget.services.resolve_budget_by_name`) ;
5. **supprimer une enveloppe ne touche pas au chantier** (`SET_NULL`) : une
   rubrique qui disparaît n'emporte pas ce qui la citait.

Couvre `PROJ-12`.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from budget.models import Budget
from budget.services import resolve_budget_by_name
from households.models import Household, HouseholdMember
from projects.assistant import Plan, resolve_plan_references
from projects.models import Project
from zones.models import Zone

CREATE_URL = "/api/projects/projects/assistant-create/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(db):
    return UserFactory(email="envelope-owner@example.com")


@pytest.fixture
def household(db, owner):
    instance = Household.objects.create(name="Envelope House")
    HouseholdMember.objects.create(
        user=owner, household=instance, role=HouseholdMember.Role.OWNER
    )
    owner.active_household = instance
    owner.save(update_fields=["active_household"])
    return instance


@pytest.fixture
def garden(household, owner):
    return Zone.objects.create(household=household, name="Jardin", created_by=owner)


@pytest.fixture
def works(household):
    return Budget.objects.create(household=household, name="Travaux", monthly_amount="400.00")


@pytest.fixture
def owner_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


def _plan(garden, budget=None) -> dict:
    return {
        "project": {
            "title": "Terrasse en bois",
            "description": "20 m² côté jardin.",
            "type": "renovation",
            "zone_ids": [str(garden.id)],
            **({"budget": budget} if budget is not None else {}),
        },
        "tasks": [{"subject": "Choisir le bois"}],
        "notes": [],
    }


class TestAnEnvelopeCreatedForAProjectIsNeverCapped:
    """PROJ-12 — elle classe, elle ne plafonne pas."""

    def test_a_new_envelope_has_no_monthly_amount(self, household, garden, owner_client):
        response = owner_client.post(
            CREATE_URL, _plan(garden, {"mode": "new", "name": "Terrasse"}), format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Budget.objects.get(household=household, name="Terrasse")
        assert created.monthly_amount is None
        assert created.is_global is False

    def test_the_project_ceiling_stays_its_own_planned_budget(
        self, household, garden, owner_client
    ):
        """Le plafond du chantier ne migre pas dans l'enveloppe."""
        payload = _plan(garden, {"mode": "new", "name": "Terrasse"})
        payload["project"]["planned_budget"] = "3200.00"

        owner_client.post(CREATE_URL, payload, format="json")

        project = Project.objects.get()
        assert str(project.planned_budget) == "3200.00"
        assert project.default_budget.monthly_amount is None

    def test_the_api_reports_the_envelope_as_uncapped(self, household, garden, owner_client):
        """`uncapped` est un état à part, jamais `ok` : une catégorie sans plafond
        ne peut être ni respectée ni dépassée. Le payload doit dire `null`, jamais
        « 0.00 » — un plafond à zéro est perpétuellement dépassé."""
        owner_client.post(
            CREATE_URL, _plan(garden, {"mode": "new", "name": "Terrasse"}), format="json"
        )
        created = Budget.objects.get(name="Terrasse")

        response = owner_client.get(f"/api/budget/budgets/{created.id}/")

        assert response.data["monthly_amount"] is None


class TestAnExistingEnvelopeIsReusedNotDuplicated:
    def test_an_existing_id_is_linked(self, household, garden, works, owner_client):
        response = owner_client.post(
            CREATE_URL,
            _plan(garden, {"mode": "existing", "id": str(works.id), "name": "Travaux"}),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Project.objects.get().default_budget_id == works.id
        assert Budget.objects.filter(household=household).count() == 1

    def test_a_new_name_that_already_exists_reuses_it_rather_than_crashing(
        self, household, garden, works, owner_client
    ):
        """L'utilisateur peut renommer l'enveloppe dans l'écran de relecture.

        `unique_budget_name_per_household` transformerait la collision en
        `IntegrityError`, donc en 500 sur une saisie ordinaire. Ce qu'il a demandé,
        c'est « une enveloppe nommée Travaux » : elle existe, on la prend.
        """
        response = owner_client.post(
            CREATE_URL, _plan(garden, {"mode": "new", "name": "travaux"}), format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Budget.objects.filter(household=household).count() == 1
        assert Project.objects.get().default_budget_id == works.id

    def test_an_envelope_from_another_household_is_not_linked(
        self, household, garden, owner_client
    ):
        """Un id venu du client ne se croit pas."""
        neighbour = Household.objects.create(name="Chez le voisin")
        theirs = Budget.objects.create(household=neighbour, name="Leurs travaux")

        response = owner_client.post(
            CREATE_URL,
            _plan(garden, {"mode": "existing", "id": str(theirs.id), "name": "Leurs travaux"}),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Project.objects.get().default_budget_id is None

    def test_no_envelope_is_a_legitimate_choice(self, household, garden, owner_client):
        """Le détecteur `expense_without_budget` posera la question au premier
        euro — c'est le bon moment, pas maintenant."""
        response = owner_client.post(CREATE_URL, _plan(garden), format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Project.objects.get().default_budget is None
        assert Budget.objects.filter(household=household).count() == 0


class TestTheGlobalBudgetIsNotAnOption:
    """Il ne classe rien, il plafonne tout."""

    def test_it_is_never_resolved_by_name(self, household):
        Budget.objects.create(
            household=household, name="Plafond du foyer", monthly_amount="2000.00", is_global=True
        )

        assert resolve_budget_by_name(household, "Plafond du foyer") is None

    def test_it_cannot_be_linked_by_id(self, household, garden, owner_client):
        overall = Budget.objects.create(
            household=household, name="Plafond", monthly_amount="2000.00", is_global=True
        )

        owner_client.post(
            CREATE_URL,
            _plan(garden, {"mode": "existing", "id": str(overall.id), "name": "Plafond"}),
            format="json",
        )

        assert Project.objects.get().default_budget_id is None


class TestTheModelProposesByNameAndTheServerResolves:
    """Même règle que les zones : un foyer dit « Travaux », pas un UUID."""

    def _resolved(self, household, name):
        plan = Plan(
            project={"title": "Terrasse", "zone_names": [], "budget_name": name},
            tasks=(),
            notes=(),
        )
        return resolve_plan_references(household, plan).project["budget"]

    def test_a_known_name_becomes_an_existing_envelope(self, household, works):
        assert self._resolved(household, "Travaux") == {
            "mode": "existing",
            "id": str(works.id),
            "name": "Travaux",
        }

    def test_case_and_accents_are_not_differences_of_designation(self, household, works):
        assert self._resolved(household, "TRAVAUX")["id"] == str(works.id)

    def test_an_unknown_name_becomes_one_to_create(self, household):
        assert self._resolved(household, "Terrasse") == {"mode": "new", "name": "Terrasse"}

    def test_no_name_means_no_envelope(self, household):
        assert self._resolved(household, None) is None

    def test_the_raw_name_never_survives_the_resolution(self, household, works):
        """Deux façons de désigner la même enveloppe finiraient par diverger."""
        plan = Plan(
            project={"title": "T", "zone_names": [], "budget_name": "Travaux"},
            tasks=(),
            notes=(),
        )
        assert "budget_name" not in resolve_plan_references(household, plan).project

    def test_the_existing_envelopes_travel_to_the_model(self, household, works, owner_client):
        """Sans la liste, le modèle en invente une à chaque chantier."""
        from unittest.mock import patch

        from agent.llm import LLMResponse

        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = LLMResponse(
                text='{"state":"asking","question":"Bois ?","field":"m","input":"text"}',
                input_tokens=1, output_tokens=1, duration_ms=1, model="test",
            )
            owner_client.post(
                "/api/projects/projects/assistant-step/",
                {"goal": "Refaire la terrasse"},
                format="json",
            )

        assert "Travaux" in complete.call_args.kwargs["user"]


class TestDeletingTheEnvelopeLeavesTheProjectStanding:
    def test_set_null_not_cascade(self, household, garden, works, owner_client):
        """Supprimer une enveloppe est supprimer une rubrique — ça ne doit jamais
        emporter le chantier qui la citait."""
        owner_client.post(
            CREATE_URL,
            _plan(garden, {"mode": "existing", "id": str(works.id), "name": "Travaux"}),
            format="json",
        )
        project_id = Project.objects.get().id

        works.delete()

        project = Project.objects.get(pk=project_id)
        assert project.default_budget_id is None


class TestThePurchaseDialogGetsWhatItNeeds:
    def test_the_project_payload_carries_its_envelope(
        self, household, garden, works, owner_client
    ):
        """Le front pré-sélectionne `default_budget` à l'achat : encore faut-il
        que l'API le rende."""
        response = owner_client.post(
            CREATE_URL,
            _plan(garden, {"mode": "existing", "id": str(works.id), "name": "Travaux"}),
            format="json",
        )

        # On lit le **JSON rendu**, pas `response.data` : c'est ce que le front
        # reçoit. `response.data` porte encore un `UUID` Python, et l'assertion
        # aurait prouvé quelque chose que le navigateur ne voit jamais.
        assert response.json()["default_budget"] == str(works.id)
