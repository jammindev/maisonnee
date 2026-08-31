"""Les pièces jointes de l'entretien — lues, citables, et jamais possédées.

Ce que ces tests défendent, dans l'ordre d'importance :

1. **un document privé d'un autre membre n'entre pas dans le prompt.** Ce serait
   la fuite de #667 par une autre porte, avec un intermédiaire de plus — et un
   texte parti chez un fournisseur ne se rattrape pas ;
2. **une citation ne vaut que si elle nomme une pièce réellement jointe.** C'est
   la seule exception à « le modèle ne remplit jamais un montant », et elle tient
   à la source consultable : sans ce contrôle, « le devis indique 3 180 € » est
   une phrase qu'un modèle peut écrire sans avoir rien lu ;
3. **le document survit à un entretien abandonné.** Téléverser est un geste
   délibéré et indépendant : la bibliothèque du foyer le garde, l'entretien ne le
   possède pas ;
4. **un id inconnu ne fait pas échouer la création.** Les pièces sont un
   complément, pas la matière du plan ;
5. **aucun appel de vision n'est fait ici** — l'extraction a eu lieu au
   téléversement, donc ce chemin n'a pas de coût à borner.

Couvre `PROJ-13`.
"""
import json
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from agent.llm import LLMResponse
from documents.models import Document, DocumentLink
from households.models import Household, HouseholdMember
from projects.models import Project
from zones.models import Zone

STEP_URL = "/api/projects/projects/assistant-step/"
CREATE_URL = "/api/projects/projects/assistant-create/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(db):
    return UserFactory(email="docs-owner@example.com")


@pytest.fixture
def roommate(db):
    return UserFactory(email="docs-roommate@example.com")


@pytest.fixture
def household(db, owner, roommate):
    instance = Household.objects.create(name="Docs House")
    for user in (owner, roommate):
        HouseholdMember.objects.create(
            user=user, household=instance, role=HouseholdMember.Role.MEMBER
        )
        user.active_household = instance
        user.save(update_fields=["active_household"])
    return instance


@pytest.fixture
def garden(household, owner):
    return Zone.objects.create(household=household, name="Jardin", created_by=owner)


@pytest.fixture
def owner_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture
def quote(household, owner):
    return Document.objects.create(
        household=household,
        created_by=owner,
        name="devis-menuisier.pdf",
        file_path="docs/devis.pdf",
        ocr_text="Menuiserie Dupont — terrasse ipé 20 m² — TOTAL 3180,00 EUR",
    )


@pytest.fixture
def private_note(household, roommate):
    """Un document privé **d'un autre membre** que celui qui mène l'entretien."""
    return Document.objects.create(
        household=household,
        created_by=roommate,
        name="secret.pdf",
        file_path="docs/secret.pdf",
        ocr_text="MOT DE PASSE DU COFFRE 1234",
        is_private=True,
    )


@pytest.fixture
def with_key(settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    settings.LLM_PROVIDER = "anthropic"


def _reply(payload) -> LLMResponse:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return LLMResponse(text=text, input_tokens=1, output_tokens=1, duration_ms=1, model="test")


def _question(**extra) -> LLMResponse:
    return _reply({
        "state": "asking",
        "question": "As-tu un budget en tête ?",
        "field": "budget",
        "input": "amount",
        **extra,
    })


def _body(documents=(), **extra) -> dict:
    return {
        "goal": "Je veux refaire la terrasse",
        "document_ids": [document.id for document in documents],
        **extra,
    }


@pytest.mark.usefixtures("with_key")
class TestAPrivateDocumentNeverEntersThePrompt:
    """PROJ-13 — la fuite de #667 ne doit pas se rouvrir par cette porte."""

    def test_the_text_of_another_members_private_file_is_not_sent(
        self, household, private_note, owner_client
    ):
        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question()

            owner_client.post(STEP_URL, _body([private_note]), format="json")

        sent = complete.call_args.kwargs["user"]
        assert "MOT DE PASSE DU COFFRE" not in sent
        assert "secret.pdf" not in sent

    def test_my_own_private_file_is_mine_to_use(self, household, owner, owner_client):
        """La restriction porte sur l'auteur, pas sur le fait d'être privé."""
        mine = Document.objects.create(
            household=household,
            created_by=owner,
            name="mon-devis.pdf",
            file_path="docs/mine.pdf",
            ocr_text="TOTAL 900 EUR",
            is_private=True,
        )

        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question()

            owner_client.post(STEP_URL, _body([mine]), format="json")

        assert "TOTAL 900 EUR" in complete.call_args.kwargs["user"]

    def test_a_document_from_another_household_is_not_read(self, household, owner_client):
        neighbour = Household.objects.create(name="Chez le voisin")
        theirs = Document.objects.create(
            household=neighbour, name="leur-devis.pdf", file_path="d.pdf", ocr_text="CHEZ EUX"
        )

        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question()

            owner_client.post(STEP_URL, _body([theirs]), format="json")

        assert "CHEZ EUX" not in complete.call_args.kwargs["user"]


@pytest.mark.usefixtures("with_key")
class TestACitationNeedsAConsultableSource:
    """La seule exception à « le modèle ne remplit jamais un montant »."""

    def test_a_suggestion_naming_an_attached_file_is_kept(
        self, household, quote, owner_client
    ):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question(
                suggestion={"amount": "3180.00", "source": "devis-menuisier.pdf"}
            )

            response = owner_client.post(STEP_URL, _body([quote]), format="json")

        assert response.data["question"]["suggestion"] == {
            "amount": "3180.00",
            "source": "devis-menuisier.pdf",
        }

    def test_a_suggestion_naming_nothing_attached_is_dropped(
        self, household, quote, owner_client
    ):
        """Sinon le seul chiffre que le modèle a le droit de proposer redevient une
        devinette — avec, en prime, l'autorité d'une source inventée."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question(
                suggestion={"amount": "9999.00", "source": "un-autre-devis.pdf"}
            )

            response = owner_client.post(STEP_URL, _body([quote]), format="json")

        assert response.data["question"]["suggestion"] is None

    def test_a_suggestion_without_any_attachment_is_dropped(self, household, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question(
                suggestion={"amount": "9999.00", "source": "devis-menuisier.pdf"}
            )

            response = owner_client.post(STEP_URL, _body(), format="json")

        assert response.data["question"]["suggestion"] is None

    def test_a_non_numeric_suggestion_is_dropped(self, household, quote, owner_client):
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question(
                suggestion={"amount": "environ trois mille", "source": "devis-menuisier.pdf"}
            )

            response = owner_client.post(STEP_URL, _body([quote]), format="json")

        assert response.data["question"]["suggestion"] is None

    def test_a_bad_suggestion_does_not_lose_the_question(
        self, household, quote, owner_client
    ):
        """Perdre le tour entier pour un champ facultatif serait disproportionné."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question(
                suggestion={"amount": "1", "source": "inventé.pdf"}
            )

            response = owner_client.post(STEP_URL, _body([quote]), format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["question"]["text"] == "As-tu un budget en tête ?"


@pytest.mark.usefixtures("with_key")
class TestReadingCostsNothingExtra:
    def test_no_vision_call_is_made(self, household, quote, owner_client):
        """L'extraction a eu lieu au téléversement : ce chemin ne fait que relire
        un texte déjà payé, donc il n'a pas de cap à lui."""
        with patch("projects.assistant.get_llm_client") as get_client:
            get_client.return_value.complete.return_value = _question()

            owner_client.post(STEP_URL, _body([quote]), format="json")

        assert get_client.return_value.vision_extract.call_count == 0

    def test_the_excerpt_is_truncated(self, household, owner, owner_client):
        from projects.assistant import MAX_DOCUMENT_CHARS

        long_one = Document.objects.create(
            household=household,
            created_by=owner,
            name="pave.pdf",
            file_path="d.pdf",
            ocr_text="A" * (MAX_DOCUMENT_CHARS + 500) + "FIN-DU-PAVE",
        )

        with patch("projects.assistant.get_llm_client") as get_client:
            complete = get_client.return_value.complete
            complete.return_value = _question()

            owner_client.post(STEP_URL, _body([long_one]), format="json")

        assert "FIN-DU-PAVE" not in complete.call_args.kwargs["user"]


@pytest.mark.usefixtures("with_key")
class TestADocumentKeyIsAnInteger:
    """Ce que `document_ids` attend, et ce que le front doit envoyer.

    Les clés de `Document` sont des **entiers** là où presque tout le reste du
    dépôt est en UUID — le type TS `DocumentItem.id: string` ne le dit pas, d'où
    la coercition dans l'écran d'entretien. Ce test fige la vérité côté serveur
    pour que la coercition ne devienne pas un mystère dans six mois, et pour que
    le jour où `Document` passerait en UUID, c'est ici que ça rougirait.
    """

    def test_the_api_renders_it_as_a_number(self, household, quote, owner_client):
        response = owner_client.get(f"/api/documents/documents/{quote.id}/")

        assert isinstance(response.json()["id"], int)


class TestTheInterviewDoesNotOwnTheFile:
    """PROJ-13 — téléverser est un geste délibéré et indépendant."""

    def _plan(self, garden, documents) -> dict:
        return {
            "project": {"title": "Terrasse", "zone_ids": [str(garden.id)]},
            "tasks": [],
            "notes": [],
            "document_ids": [document.id for document in documents],
        }

    def test_the_created_project_carries_one_link_per_attachment(
        self, household, garden, quote, owner_client
    ):
        response = owner_client.post(CREATE_URL, self._plan(garden, [quote]), format="json")

        assert response.status_code == status.HTTP_201_CREATED
        project = Project.objects.get()
        assert DocumentLink.objects.filter(object_id=project.id, document=quote).count() == 1

    def test_an_abandoned_interview_leaves_the_file_in_the_library(
        self, household, quote, owner_client
    ):
        """Comportement **attendu**, figé ici pour qu'on ne le « corrige » pas :
        faire l'inverse demanderait une transaction qui embrasse un envoi de
        fichier."""
        assert Document.objects.filter(pk=quote.pk).exists()
        assert DocumentLink.objects.filter(document=quote).count() == 0

    def test_an_unknown_id_does_not_lose_the_project(self, household, garden, owner_client):
        """Le document a pu être supprimé entre l'entretien et la validation."""
        payload = self._plan(garden, [])
        payload["document_ids"] = [999_999]

        response = owner_client.post(CREATE_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Project.objects.count() == 1

    def test_a_private_file_of_another_member_is_never_linked(
        self, household, garden, private_note, owner_client
    ):
        """Accrocher le privé d'un autre à un chantier que tout le foyer voit
        serait la même fuite, par la porte de la liaison."""
        response = owner_client.post(
            CREATE_URL, self._plan(garden, [private_note]), format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert DocumentLink.objects.filter(document=private_note).count() == 0
