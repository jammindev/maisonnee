"""Écrire le plan relu — tout, ou rien (parcours 32, lot 2).

Ce que ces tests défendent, dans l'ordre d'importance :

1. **tout ou rien** — un chantier créé avec quatre tâches sur six est un
   demi-succès qui ressemble exactement à un succès, et personne ne saurait dire
   lesquelles manquent. Une ligne fautive doit tout annuler *et* se nommer ;
2. **ce chemin ne fabrique rien de particulier** — une tâche créée par l'entretien
   est indiscernable d'une tâche créée par `POST /api/tasks/tasks/`. C'est le test
   qui verrouille l'absence de chemin d'écriture parallèle ;
3. **les zones sont résolues avant la relecture, pas à l'écriture** — sinon une
   pièce mal nommée retombe sur celles du projet *après* validation, donc sans
   que personne ne puisse le voir ;
4. **une erreur de contenu se dit en 400** — dates incohérentes, plan géant, zone
   d'un autre foyer. Jamais un 500 sur une saisie ordinaire ;
5. **la création ne demande aucune clé** — un plan déjà obtenu reste créable si la
   clé tombe entre-temps.

Couvre `PROJ-06`, `PROJ-09`, `PROJ-10` et `PROJ-11` côté serveur.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from households.models import Household, HouseholdMember
from interactions.models import Interaction
from projects.assistant import MAX_TASKS, Plan, resolve_plan_zones
from projects.models import Project
from tasks.models import Task
from zones.models import Zone

CREATE_URL = "/api/projects/projects/assistant-create/"
TASKS_URL = "/api/tasks/tasks/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(db):
    return UserFactory(email="plan-owner@example.com")


@pytest.fixture
def household(db, owner):
    instance = Household.objects.create(name="Plan House")
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
def basement(household, owner):
    return Zone.objects.create(household=household, name="Sous-sol", created_by=owner)


@pytest.fixture
def owner_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


def _plan(garden, *, tasks=None, notes=None, **project_extra) -> dict:
    project = {
        "title": "Terrasse en bois",
        "description": "Une terrasse de 20 m² côté jardin.",
        "type": "renovation",
        "priority": 2,
        "planned_budget": "3200.00",
        "due_date": "2026-06-21",
        "tags": ["extérieur"],
        "zone_ids": [str(garden.id)],
    }
    project.update(project_extra)
    return {
        "project": project,
        "tasks": tasks if tasks is not None else [
            {"subject": "Choisir l'essence de bois", "content": "Pin traité ou ipé."},
            {"subject": "Demander trois devis", "priority": 1},
        ],
        "notes": notes if notes is not None else [
            {"subject": "Règles d'urbanisme", "content": "Déclaration préalable ?"},
        ],
    }


class TestAllOrNothing:
    """PROJ-11 — la création échoue en entier plutôt qu'à moitié."""

    def test_a_plan_of_six_tasks_and_two_notes_creates_exactly_nine_objects(
        self, household, garden, owner_client
    ):
        payload = _plan(
            garden,
            tasks=[{"subject": f"Tâche {index}"} for index in range(6)],
            notes=[{"subject": "Note A"}, {"subject": "Note B"}],
        )

        response = owner_client.post(CREATE_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Project.objects.count() == 1
        assert Task.objects.count() == 6
        assert Interaction.objects.filter(type="note").count() == 2

    def test_a_bad_zone_on_the_fifth_task_leaves_no_project_behind(
        self, household, garden, owner_client
    ):
        """L'id est syntaxiquement valide mais n'existe pas : le serializer le
        laisse passer, `create_task` le refuse — et tout doit repartir."""
        tasks = [{"subject": f"Tâche {index}"} for index in range(6)]
        tasks[4]["zone_ids"] = ["7c9e6679-7425-40de-944b-e07fc1f90ae7"]
        payload = _plan(garden, tasks=tasks, notes=[{"subject": "Note A"}])

        response = owner_client.post(CREATE_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Project.objects.count() == 0
        assert Task.objects.count() == 0
        assert Interaction.objects.count() == 0

    def test_the_failing_line_says_which_one_it_is(self, household, garden, owner_client):
        """« une ou plusieurs zones n'appartiennent pas au foyer » sur un plan de
        huit tâches n'aide personne."""
        tasks = [{"subject": f"Tâche {index}"} for index in range(6)]
        tasks[4]["zone_ids"] = ["7c9e6679-7425-40de-944b-e07fc1f90ae7"]

        response = owner_client.post(
            CREATE_URL, _plan(garden, tasks=tasks), format="json"
        )

        assert "ligne 5" in str(response.data["tasks"])

    def test_a_failing_note_rolls_the_tasks_back_too(self, household, garden, owner_client):
        """Les notes sont écrites après les tâches : la transaction doit couvrir
        les deux, sinon un plan à moitié écrit reste en base."""
        payload = _plan(
            garden,
            notes=[
                {"subject": "Note A"},
                {"subject": "Note B", "zone_ids": ["7c9e6679-7425-40de-944b-e07fc1f90ae7"]},
            ],
        )

        response = owner_client.post(CREATE_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "ligne 2" in str(response.data["notes"])
        assert Project.objects.count() == 0
        assert Task.objects.count() == 0


class TestTheAssistedPathAgreesWithTheForm:
    """Aucun chemin d'écriture parallèle — c'est ce qui garde les invariants.

    Un service dupliqué ne se voit pas en revue : les deux diffs se ressemblent.
    Ce test compare les deux résultats, pas les deux codes.
    """

    def test_a_task_created_by_the_plan_matches_one_created_by_the_api(
        self, household, garden, owner_client
    ):
        owner_client.post(
            CREATE_URL,
            _plan(garden, tasks=[
                {"subject": "Demander trois devis", "content": "Trois menuisiers."}
            ], notes=[]),
            format="json",
        )
        by_plan = Task.objects.get(subject="Demander trois devis")

        owner_client.post(
            TASKS_URL,
            {
                "subject": "Demander trois devis",
                "content": "Trois menuisiers.",
                "zone_ids": [str(zone_id) for zone_id in by_plan.zones.values_list("id", flat=True)],
                "project": str(by_plan.project_id),
            },
            format="json",
        )
        by_api = Task.objects.filter(subject="Demander trois devis").exclude(pk=by_plan.pk).get()

        comparable = ("status", "priority", "is_private", "needs_dry_weather", "project_id")
        assert {f: getattr(by_plan, f) for f in comparable} == {
            f: getattr(by_api, f) for f in comparable
        }
        assert set(by_plan.zones.values_list("id", flat=True)) == set(
            by_api.zones.values_list("id", flat=True)
        )

    def test_the_project_is_born_a_draft_like_the_form_s(
        self, household, garden, owner_client
    ):
        """Le formulaire crée en `draft` ; l'assistant ne s'octroie pas un statut
        plus avancé sous prétexte que l'utilisateur vient de relire."""
        owner_client.post(CREATE_URL, _plan(garden), format="json")

        assert Project.objects.get().status == Project.Status.DRAFT

    def test_a_note_lands_on_the_project_tab(self, household, garden, owner_client):
        """La note doit porter la FK polymorphe, seule condition pour apparaître
        dans l'onglet du chantier (`services.project_tab_counts`)."""
        from projects.services import project_tab_counts

        owner_client.post(CREATE_URL, _plan(garden), format="json")
        project = Project.objects.get()

        assert project_tab_counts(project)["notes"] == 1

    def test_the_response_carries_the_project_as_any_read_would(
        self, household, garden, owner_client
    ):
        response = owner_client.post(CREATE_URL, _plan(garden), format="json")

        assert response.data["title"] == "Terrasse en bois"
        assert response.data["actual_cost_cached"] == "0.00"
        assert [zone["name"] for zone in response.data["zones"]] == ["Jardin"]


class TestZonesInheritThenRefine:
    """PROJ-09 et PROJ-10 — l'héritage ne doit jamais mentir.

    La résolution vit dans `assistant.resolve_plan_zones`, donc **au tour
    d'entretien** : ce qui est relu est exactement ce qui sera écrit. Si elle
    avait lieu à l'écriture, un nom introuvable retomberait sur les zones du
    projet après validation — sans que personne puisse le voir ni le corriger.
    """

    def _resolved(self, household, *, project_names, item_names):
        plan = Plan(
            project={"title": "Terrasse", "zone_names": list(project_names)},
            tasks=({"subject": "Une tâche", "zone_names": list(item_names)},),
            notes=(),
        )
        return resolve_plan_zones(household, plan)

    def test_an_item_without_a_room_inherits_the_project_s(self, household, garden):
        resolved = self._resolved(household, project_names=["Jardin"], item_names=[])

        assert resolved.project["zone_ids"] == [str(garden.id)]
        assert resolved.tasks[0]["zone_ids"] == [str(garden.id)]

    def test_a_named_room_wins_over_the_inherited_one(self, household, garden, basement):
        """« couper l'eau au sous-sol » va au sous-sol, pas au jardin du chantier."""
        resolved = self._resolved(
            household, project_names=["Jardin"], item_names=["sous-sol"]
        )

        assert resolved.tasks[0]["zone_ids"] == [str(basement.id)]

    def test_a_room_this_home_does_not_have_is_named_not_absorbed(self, household, garden):
        resolved = self._resolved(
            household, project_names=["Jardin"], item_names=["véranda"]
        )

        assert resolved.tasks[0]["zone_ids"] == [str(garden.id)]
        assert resolved.tasks[0]["unresolved_zone_names"] == ["véranda"]

    def test_an_ambiguous_room_is_reported_rather_than_filed_at_random(
        self, household, garden, owner
    ):
        Zone.objects.create(household=household, name="Chambre parentale", created_by=owner)
        Zone.objects.create(household=household, name="Chambre des enfants", created_by=owner)

        resolved = self._resolved(
            household, project_names=["Jardin"], item_names=["chambre"]
        )

        assert resolved.tasks[0]["unresolved_zone_names"] == ["chambre"]
        assert resolved.tasks[0]["zone_ids"] == [str(garden.id)]

    def test_accents_and_case_are_not_differences_of_designation(self, household, basement):
        resolved = self._resolved(
            household, project_names=[], item_names=["SOUS-SOL"]
        )

        assert resolved.tasks[0]["zone_ids"] == [str(basement.id)]

    def test_one_bad_name_does_not_lose_the_seven_good_ones(self, household, garden, basement):
        """`resolve_zone_ids` lève au premier échec : un plan de huit tâches ne
        doit pas être perdu parce qu'une seule désigne une pièce inconnue."""
        resolved = self._resolved(
            household, project_names=["Jardin"], item_names=["véranda", "Sous-sol"]
        )

        assert resolved.tasks[0]["zone_ids"] == [str(basement.id)]
        assert resolved.tasks[0]["unresolved_zone_names"] == ["véranda"]

    def test_the_names_do_not_survive_the_resolution(self, household, garden):
        """Deux façons de désigner la même pièce finiraient par diverger."""
        resolved = self._resolved(household, project_names=["Jardin"], item_names=[])

        assert "zone_names" not in resolved.project
        assert "zone_names" not in resolved.tasks[0]


class TestTheDoorIsNarrow:
    """Une erreur de contenu se dit en 400 — jamais un 500."""

    def test_a_runaway_plan_is_refused(self, household, garden, owner_client):
        tasks = [{"subject": f"Tâche {index}"} for index in range(MAX_TASKS + 1)]

        response = owner_client.post(CREATE_URL, _plan(garden, tasks=tasks), format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Project.objects.count() == 0

    def test_dates_in_the_wrong_order_are_refused_not_crashed(
        self, household, garden, owner_client
    ):
        """`projects_dates_consistent` est un CheckConstraint : sans contrôle en
        amont, une erreur de contenu ordinaire donnerait un 500."""
        response = owner_client.post(
            CREATE_URL,
            _plan(garden, start_date="2026-07-01", due_date="2026-06-21"),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "due_date" in str(response.data)

    def test_a_plan_without_a_title_is_refused(self, household, garden, owner_client):
        response = owner_client.post(CREATE_URL, _plan(garden, title="   "), format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_zone_from_another_household_is_refused(self, household, garden, owner, owner_client):
        neighbour = Household.objects.create(name="Chez le voisin")
        theirs = Zone.objects.create(household=neighbour, name="Leur garage")

        response = owner_client.post(
            CREATE_URL, _plan(garden, zone_ids=[str(theirs.id)]), format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Project.objects.count() == 0

    def test_a_type_the_model_could_not_validate_falls_back_to_the_default(
        self, household, garden, owner_client
    ):
        """Le moteur retire un `type` hors énumération : le plan arrive avec
        `null`, et c'est le défaut du modèle qui s'applique — pas une devinette."""
        response = owner_client.post(
            CREATE_URL, _plan(garden, type=None, priority=None), format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        project = Project.objects.get()
        assert project.type == Project.Type.OTHER
        assert project.priority == 3

    def test_an_unknown_type_is_still_refused(self, household, garden, owner_client):
        """Nullable ne veut pas dire libre : le client ne peut pas inventer un type."""
        response = owner_client.post(
            CREATE_URL, _plan(garden, type="terrassement"), format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_anonymous_caller_gets_nothing(self, household, garden):
        response = APIClient().post(CREATE_URL, _plan(garden), format="json")

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
        assert Project.objects.count() == 0


class TestCreatingNeedsNoKey:
    """Un plan déjà obtenu reste créable si la clé tombe entre-temps.

    Refuser ferait perdre à l'utilisateur une relecture qu'il vient de faire,
    pour une raison qui ne le concerne plus.
    """

    def test_the_creation_works_without_any_provider_key(
        self, settings, household, garden, owner_client
    ):
        settings.ANTHROPIC_API_KEY = ""

        response = owner_client.post(CREATE_URL, _plan(garden), format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_the_creation_endpoint_is_not_throttled_like_the_interview(self, household):
        """Écrire ne coûte pas d'euros : le cap dédié ne concerne que l'entretien."""
        from projects.views import ProjectViewSet

        view = ProjectViewSet()
        view.action = "assistant_create"
        assert not any(
            type(throttle).__name__ == "ProjectAssistantThrottle"
            for throttle in view.get_throttles()
        )
