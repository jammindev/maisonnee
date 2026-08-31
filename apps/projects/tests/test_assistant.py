"""L'entretien de création d'un chantier — et les cinq façons de se tromper.

Ce que ces tests défendent, dans l'ordre d'importance :

1. **le plafond de questions est une garantie, pas une consigne** — c'est le seul
   point du lot qu'un prompt ne peut pas tenir. Un modèle qui insiste pour
   questionner au septième tour ne doit pas pouvoir le faire ; ici on le fait
   insister exprès ;
2. **rien n'est écrit en base** — ni par le tour qui réussit, ni par celui qui
   échoue. C'est ce qui permet à l'utilisateur d'abandonner sans conséquence, et
   c'est structurel : l'endpoint ne connaît aucune écriture ;
3. **une instance sans clé le dit** (503 nommé) et **n'appelle pas le
   fournisseur** — le formulaire de création reste le repli, rien ne manque ;
4. **une réponse mal formée ne rend rien** — un demi-plan se lit plus mal
   qu'aucun plan : l'écran afficherait des lignes vides sans dire lesquelles
   viennent du modèle ;
5. **le chemin littéral est celui que le front appelle** — `reverse()` ne le
   prouve pas, DRF ne dérivant pas `url_path` et `url_name` de la même façon.

Couvre `PROJ-02`, `PROJ-03`, `PROJ-08` et `PROJ-14` côté serveur ; le parcours
navigateur arrive au lot 3 (`e2e/project-assistant.spec.ts`).
"""
import json
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from agent.llm import LLMError, LLMResponse
from households.models import Household, HouseholdMember
from interactions.models import Interaction
from projects.assistant import MAX_QUESTIONS, MAX_TASKS, Step, next_step
from projects.models import Project
from tasks.models import Task
from zones.models import Zone

STEP_URL = "/api/projects/projects/assistant-step/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(db):
    return UserFactory(email="assistant-owner@example.com")


@pytest.fixture
def household(db, owner):
    instance = Household.objects.create(name="Assistant House")
    HouseholdMember.objects.create(
        user=owner, household=instance, role=HouseholdMember.Role.OWNER
    )
    owner.active_household = instance
    owner.save(update_fields=["active_household"])
    return instance


@pytest.fixture
def rooms(household, owner):
    return [
        Zone.objects.create(household=household, name=name, created_by=owner)
        for name in ("Jardin", "Garage", "Salle de bain")
    ]


@pytest.fixture
def owner_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture
def with_key(settings):
    """Une instance qui a sa clé. `override_settings` ne décore pas une classe
    pytest (il exige une `SimpleTestCase`) : c'est la fixture `settings` de
    pytest-django qui joue ce rôle, et elle restaure toute seule."""
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    settings.LLM_PROVIDER = "anthropic"


@pytest.fixture
def without_key(settings):
    """Une instance d'auto-hébergeur qui n'a posé aucune clé."""
    settings.ANTHROPIC_API_KEY = ""
    settings.LLM_PROVIDER = "anthropic"


def _reply(payload) -> LLMResponse:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return LLMResponse(
        text=text, input_tokens=10, output_tokens=20, duration_ms=5, model="test-model"
    )


def _question(text="Bois, composite ou carrelage ?", **extra) -> LLMResponse:
    return _reply({
        "state": "asking",
        "question": text,
        "field": "material",
        "input": "choice",
        "choices": ["bois", "composite", "carrelage"],
        **extra,
    })


def _plan(**overrides) -> LLMResponse:
    project = {
        "title": "Terrasse en bois",
        "description": "Une terrasse de 20 m² côté jardin.",
        "type": "renovation",
        "priority": 3,
        "planned_budget": "3200.00",
        "due_date": "2026-06-21",
        "tags": ["extérieur"],
        "zone_names": ["Jardin"],
    }
    project.update(overrides.pop("project", {}))
    return _reply({
        "state": "ready",
        "plan": {
            "project": project,
            "tasks": overrides.pop("tasks", [
                {"subject": "Choisir l'essence de bois", "content": "Pin traité ou ipé."},
                {"subject": "Demander trois devis", "content": "", "zone_names": ["Garage"]},
            ]),
            "notes": overrides.pop("notes", [
                {"subject": "Règles d'urbanisme", "content": "Vérifier la déclaration préalable."},
            ]),
        },
    })


def _history(count: int) -> list[dict]:
    return [
        {"question": f"Question {index}", "field": f"f{index}", "answer": f"Réponse {index}"}
        for index in range(count)
    ]


def _body(**extra) -> dict:
    return {"goal": "Je veux refaire la terrasse", **extra}


@pytest.mark.usefixtures("with_key")
class TestTheCapIsAGuaranteeNotAnInstruction:
    """PROJ-02 — l'entretien s'arrête, même contre l'avis du modèle.

    C'est le seul point du lot qu'un prompt ne peut pas tenir : « pose au plus
    six questions » est une intention, et le jour où elle n'est pas respectée,
    c'est l'utilisateur qui découvre la boucle.
    """

    def test_a_full_history_concludes_even_when_the_model_insists(self, household, rooms, owner_client):
        """Le modèle renvoie une question au septième tour : elle est refusée.

        Pas rattrapée, pas convertie — refusée. Le prompt de conclusion et
        `_parse` disent la même chose, et c'est `_parse` qui a le dernier mot.
        """
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question()

            response = owner_client.post(
                STEP_URL, _body(history=_history(MAX_QUESTIONS)), format="json"
            )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "question" in response.data["detail"].lower()

    def test_a_full_history_gets_the_concluding_prompt(self, household, rooms, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _plan()

            response = owner_client.post(
                STEP_URL, _body(history=_history(MAX_QUESTIONS)), format="json"
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["state"] == "ready"
        assert "Do not ask another question" in complete.call_args.kwargs["system"]

    def test_the_remaining_count_walks_down_to_the_last_question(self, household, rooms, owner_client):
        """`remaining` compte la question en cours : à cinq réponses, il vaut 1."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question()

            response = owner_client.post(
                STEP_URL, _body(history=_history(MAX_QUESTIONS - 1)), format="json"
            )

        assert response.data["asked"] == MAX_QUESTIONS - 1
        assert response.data["remaining"] == 1

    def test_a_history_longer_than_the_cap_is_refused_not_truncated(self, household, rooms, owner_client):
        """Le corps est le seul état de l'entretien : c'est le seul endroit où le borner."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan()

            response = owner_client.post(
                STEP_URL, _body(history=_history(MAX_QUESTIONS + 1)), format="json"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        get_client.assert_not_called()


@pytest.mark.usefixtures("with_key")
class TestTheUserCanCutTheInterviewShort:
    """PROJ-03 — « J'ai assez dit » n'est pas un raccourci, c'est une sortie."""

    def test_force_ready_at_the_very_first_turn_produces_a_plan(self, household, rooms, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _plan()

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["state"] == "ready"
        assert response.data["plan"]["project"]["title"] == "Terrasse en bois"
        assert "Do not ask another question" in complete.call_args.kwargs["system"]

    def test_a_question_is_refused_once_the_user_has_cut_short(self, household, rooms, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question()

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert response.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.usefixtures("with_key")
class TestNothingIsWrittenBeforeTheUserHasRead:
    """PROJ-08 — le critère central du lot : proposer n'est pas enregistrer.

    La séparation n'est pas une politesse. Un modèle qui écrirait directement
    créerait douze objets qu'il faudrait annuler un par un — et l'utilisateur
    qui voulait retirer *une* tâche sur six devrait tout défaire.
    """

    def test_a_successful_plan_writes_nothing(self, household, rooms, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan()

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert response.status_code == status.HTTP_200_OK
        assert Project.objects.count() == 0
        assert Task.objects.count() == 0
        assert Interaction.objects.count() == 0

    def test_a_failed_turn_writes_nothing_either(self, household, rooms, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _reply("pas du json")

            owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert Project.objects.count() == 0
        assert Task.objects.count() == 0
        assert Interaction.objects.count() == 0

    def test_the_plan_carries_no_identifier_of_anything_created(self, household, rooms, owner_client):
        """Un `id` dans le plan laisserait croire que quelque chose existe déjà."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan()

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert "id" not in response.data["plan"]["project"]
        assert all("id" not in task for task in response.data["plan"]["tasks"])


@pytest.mark.usefixtures("with_key")
class TestAMalformedAnswerFillsNothing:
    """Un demi-plan se lit plus mal qu'aucun plan.

    Même arbitrage que `games.riddles._parse` et `recap.polish._parse` : on ne
    complète pas les trous, on refuse — sinon l'écran de relecture affiche des
    lignes vides sans dire lesquelles viennent du modèle.
    """

    @pytest.mark.parametrize("payload", [
        "pas du json du tout",
        json.dumps(["une", "liste"]),
        json.dumps({"state": "confused"}),
        json.dumps({"state": "ready"}),
        json.dumps({"state": "ready", "plan": {"project": {"title": "   "}}}),
        json.dumps({"state": "ready", "plan": {"project": {"title": "Ok"}, "tasks": "trois"}}),
        json.dumps({"state": "ready", "plan": {
            "project": {"title": "Ok"}, "tasks": [{"content": "sans sujet"}]
        }}),
    ])
    def test_a_broken_shape_is_refused(self, household, rooms, owner_client, payload):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _reply(payload)

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "plan" not in response.data

    def test_an_unknown_input_kind_is_refused_rather_than_downgraded(self, household, rooms, owner_client):
        """Pas de repli sur « texte libre » pour une question d'argent.

        Un montant qui repasse par du texte est un nombre qu'il faut relire, et
        c'est le chemin qui a déjà produit un faux montant en production.
        """
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question(input="slider")

            response = owner_client.post(STEP_URL, _body(), format="json")

        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    def test_a_runaway_plan_is_refused_rather_than_truncated(self, household, rooms, owner_client):
        """Tronquer laisserait croire que le plan est complet."""
        tasks = [{"subject": f"Tâche {index}"} for index in range(MAX_TASKS + 1)]
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan(tasks=tasks)

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    def test_a_fenced_code_block_is_still_read(self, household, rooms, owner_client):
        """Le seul écart de forme qu'un modèle produit encore, et il est inoffensif."""
        fenced = "```json\n" + _plan().text + "\n```"
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _reply(fenced)

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"]["project"]["title"] == "Terrasse en bois"

    def test_a_provider_outage_is_not_an_exception_leaking_out(self, household, rooms, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.side_effect = LLMError("boom")

            response = owner_client.post(STEP_URL, _body(), format="json")

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "boom" not in response.data["detail"]


@pytest.mark.usefixtures("with_key")
class TestWhatTheModelIsGivenAndWhatItMayGiveBack:
    """Le contexte est pauvre à dessein, et les valeurs douteuses sont retirées."""

    def test_the_household_rooms_travel_with_the_question(self, household, rooms, owner_client):
        """Le plan désigne les zones **par nom** — encore faut-il les connaître."""
        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question()

            owner_client.post(STEP_URL, _body(), format="json")

        sent = complete.call_args.kwargs["user"]
        for room in rooms:
            assert room.name in sent

    def test_the_answers_already_given_travel_too(self, household, rooms, owner_client):
        """L'entretien n'a pas d'autre mémoire que celle-là."""
        history = [{"question": "Bois ou composite ?", "field": "material", "answer": "bois"}]
        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question("Quelle surface ?")

            owner_client.post(STEP_URL, _body(history=history), format="json")

        sent = complete.call_args.kwargs["user"]
        assert "Bois ou composite ?" in sent
        assert "bois" in sent

    def test_an_unknown_project_type_is_dropped_not_guessed(self, household, rooms, owner_client):
        """Écrire « autre » à la place de « rénovation » serait indistinguable
        d'un choix. Le champ est retiré, et l'utilisateur tranche à la relecture."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan(project={"type": "terrassement"})

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert response.data["plan"]["project"]["type"] is None

    def test_a_priority_out_of_range_is_dropped_not_clamped(self, household, rooms, owner_client):
        """Un `CheckConstraint` la refuserait à l'écriture ; la ramener dans
        l'intervalle inventerait une valeur que personne n'a choisie."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan(project={"priority": 9})

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        assert response.data["plan"]["project"]["priority"] is None

    def test_the_interview_is_not_a_rag(self, household, rooms, owner_client):
        """Aucun projet existant n'entre dans le contexte : on compose une page
        blanche, et la matière vient de qui répond."""
        Project.objects.create(
            household=household, title="Chantier déjà là", type=Project.Type.REPAIR
        )
        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question()

            owner_client.post(STEP_URL, _body(), format="json")

        assert "Chantier déjà là" not in complete.call_args.kwargs["user"]


@pytest.mark.usefixtures("with_key")
class TestThePlanCarriesRealRoomsNotNames:
    """Ce qui est relu doit être exactement ce qui sera écrit.

    La résolution nom → id a lieu **ici**, au tour d'entretien, et pas à
    l'écriture : sinon une pièce mal nommée par le modèle retomberait sur celles
    du projet *après* que l'utilisateur a validé, donc sans qu'il puisse le voir
    ni le corriger. Le détail du comportement est testé dans
    `test_assistant_create.py::TestZonesInheritThenRefine` ; ici on vérifie que le
    contrat de l'endpoint le reflète.
    """

    def test_the_step_answers_with_ids_and_never_with_names(
        self, household, rooms, owner_client
    ):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan()

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        project = response.data["plan"]["project"]
        assert project["zone_ids"] == [str(rooms[0].id)]  # « Jardin »
        assert "zone_names" not in project
        assert all("zone_names" not in task for task in response.data["plan"]["tasks"])

    def test_an_item_without_a_room_inherits_the_project_s(
        self, household, rooms, owner_client
    ):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan()

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        tasks = response.data["plan"]["tasks"]
        assert tasks[0]["zone_ids"] == [str(rooms[0].id)]   # hérite du Jardin
        assert tasks[1]["zone_ids"] == [str(rooms[1].id)]   # a nommé le Garage

    def test_a_room_this_home_does_not_have_is_reported(
        self, household, rooms, owner_client
    ):
        """L'écran doit pouvoir dire « je n'ai pas trouvé « véranda » » plutôt
        que de ranger dans le jardin sans un mot."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _plan(
                tasks=[{"subject": "Poser les lames", "zone_names": ["véranda"]}]
            )

            response = owner_client.post(STEP_URL, _body(force_ready=True), format="json")

        task = response.data["plan"]["tasks"][0]
        assert task["unresolved_zone_names"] == ["véranda"]
        assert task["zone_ids"] == [str(rooms[0].id)]


class TestAnUnconfiguredInstanceSaysSo:
    """PROJ-14 — sans clé, le formulaire reste, et rien ne ment.

    Le repli n'est pas une version dégradée de l'entretien : c'est le formulaire
    de création, qui existe déjà. Sans clé il ne manque donc **rien** — seul le
    bouton disparaît (lot 3).
    """

    @pytest.mark.usefixtures("without_key")
    def test_the_refusal_is_a_named_503(self, household, rooms, owner_client):
        response = owner_client.post(STEP_URL, _body(), format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["capability"] == "project_assistant"
        assert "ANTHROPIC_API_KEY" in response.data["env_vars"]

    @pytest.mark.usefixtures("without_key")
    def test_the_provider_is_never_called(self, household, rooms, owner_client):
        """La garde est **avant** l'effet de bord, pas après."""
        with patch("projects.assistant.get_llm_client") as get_client:
            owner_client.post(STEP_URL, _body(), format="json")

        get_client.assert_not_called()

    @pytest.mark.usefixtures("with_key")
    def test_an_anonymous_caller_gets_nothing(self, household, rooms):
        assert APIClient().post(STEP_URL, _body(), format="json").status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


@pytest.mark.usefixtures("with_key")
class TestTheLiteralPathIsTheOneTheFrontCalls:
    """DRF ne dérive pas `url_path` et `url_name` de la même façon : un test qui
    passerait par `reverse()` resterait vert sur `/assistant_step/`."""

    def test_the_dashed_path_answers(self, household, rooms, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question()

            assert owner_client.post(
                STEP_URL, _body(), format="json"
            ).status_code == status.HTTP_200_OK

    def test_the_underscored_path_never_reaches_the_assistant(self, owner_client):
        """Et il ne répond même pas 404 — c'est ce qui rend l'erreur coûteuse.

        `/projects/assistant_step/` tombe dans la route de **détail**, avec
        `assistant_step` pris pour un identifiant de projet : le serveur répond
        405, pas « cette adresse n'existe pas ». Un front qui appellerait cette
        forme n'aurait donc aucun indice pointant vers `url_path`.
        """
        with patch("projects.assistant.get_llm_client") as get_client:
            response = owner_client.post(
                "/api/projects/projects/assistant_step/", _body(), format="json"
            )

        assert response.status_code != status.HTTP_200_OK
        get_client.assert_not_called()


@pytest.mark.usefixtures("with_key")
class TestTheEngineOnItsOwn:
    """`next_step` sans HTTP — ce que la vue n'a pas à savoir."""

    def test_an_empty_goal_is_refused(self, household):
        with pytest.raises(ValueError):
            next_step(household, goal="   ")

    def test_one_call_per_turn_and_not_one_more(self, household, rooms):
        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question()

            step = next_step(household, goal="Refaire la terrasse")

        assert complete.call_count == 1
        assert isinstance(step, Step)
        assert step.state == "asking"
        assert step.question.choices == ("bois", "composite", "carrelage")

    def test_the_writing_language_is_the_readers(self, household, rooms):
        """Un foyer francophone qui reçoit un plan en anglais n'a rien gagné sur
        le formulaire — même défaut que les notifications rendues une seule fois
        dans la langue de l'acteur."""
        from django.utils import translation

        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question()
            with translation.override("de"):
                next_step(household, goal="Terrasse")

        assert "Language for every text you write: de" in complete.call_args.kwargs["user"]


def test_the_throttle_scope_has_a_rate(settings):
    """Une portée sans tarif lève `ImproperlyConfigured` à la **première**
    requête, donc en production. Le test de `core` balaye les classes du projet ;
    celui-ci nomme la portée, pour que l'oubli se lise ici aussi."""
    from projects.throttles import ProjectAssistantThrottle

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert ProjectAssistantThrottle.scope in rates
