"""
Tests for parcours-20: project_tab_counts service and its exposure via
ProjectSerializer.tab_counts on the retrieve endpoint.

Coverage:
  1. project_tab_counts() returns all-zero dict on a fresh project.
  2. Each counter increments correctly after creating the relevant item.
  3. documents vs photos split (DocumentLink type discrimination).
  4. timeline = notes + expenses (all linked Interactions).
  5. tab_counts is None on the list endpoint, a dict on the detail endpoint.
  6. Le compteur compte **par lecteur** — parcours 33, lot 1.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from documents.models import Document, DocumentLink
from documents.services import link_document
from households.models import Household, HouseholdMember
from interactions.models import Interaction
from projects.models import Project
from projects.services import project_tab_counts
from tasks.models import Task


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _household(name: str) -> Household:
    return Household.objects.create(name=name)


def _membership(user, household, role=HouseholdMember.Role.OWNER):
    return HouseholdMember.objects.create(user=user, household=household, role=role)


def _client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _project(household, user, title="Tab-count project") -> Project:
    return Project.objects.create(
        household=household,
        created_by=user,
        title=title,
        status=Project.Status.ACTIVE,
        type=Project.Type.OTHER,
        priority=3,
    )


def _document(household, user, doc_type="document", name="Doc", suffix="pdf") -> Document:
    return Document.objects.create(
        household=household,
        created_by=user,
        file_path=f"documents/{name.lower()}.{suffix}",
        name=name,
        mime_type="application/pdf" if suffix == "pdf" else "image/jpeg",
        type=doc_type,
    )


def _interaction(household, user, project, itype="note", subject="Test note") -> Interaction:
    """Create an Interaction linked to *project* via the polymorphic source FK."""
    from django.utils import timezone

    project_ct = ContentType.objects.get_for_model(Project)
    return Interaction.objects.create(
        household=household,
        created_by=user,
        subject=subject,
        type=itype,
        occurred_at=timezone.now(),
        source_content_type=project_ct,
        source_object_id=project.id,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def owner(db):
    return UserFactory(email="tabcount-owner@example.com")


@pytest.fixture
def household(db, owner):
    hh = _household("Tab-count House")
    _membership(owner, hh, role=HouseholdMember.Role.OWNER)
    owner.active_household = hh
    owner.save(update_fields=["active_household"])
    return hh


@pytest.fixture
def owner_client(owner):
    return _client_for(owner)


@pytest.fixture
def project(household, owner):
    return _project(household, owner)


# ---------------------------------------------------------------------------
# TestProjectTabCountsService — unit tests for the service function
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProjectTabCountsService:
    """project_tab_counts() returns correct counts directly (no HTTP)."""

    def test_all_zero_on_fresh_project(self, project):
        counts = project_tab_counts(project)
        assert counts == {
            "tasks": 0,
            "trackers": 0,
            "notes": 0,
            "expenses": 0,
            "documents": 0,
            "photos": 0,
            "timeline": 0,
        }

    def test_task_increments_tasks_count(self, household, owner, project):
        Task.objects.create(
            household=household,
            created_by=owner,
            subject="Paint walls",
            project=project,
        )
        counts = project_tab_counts(project)
        assert counts["tasks"] == 1
        assert counts["notes"] == 0
        assert counts["expenses"] == 0
        assert counts["documents"] == 0
        assert counts["photos"] == 0
        assert counts["timeline"] == 0

    def test_note_interaction_increments_notes_and_timeline(self, household, owner, project):
        _interaction(household, owner, project, itype="note", subject="Noted")
        counts = project_tab_counts(project)
        assert counts["notes"] == 1
        assert counts["timeline"] == 1
        assert counts["expenses"] == 0

    def test_expense_interaction_increments_expenses_and_timeline(self, household, owner, project):
        _interaction(household, owner, project, itype="expense", subject="Bought materials")
        counts = project_tab_counts(project)
        assert counts["expenses"] == 1
        assert counts["timeline"] == 1
        assert counts["notes"] == 0

    def test_timeline_aggregates_all_linked_interactions(self, household, owner, project):
        _interaction(household, owner, project, itype="note", subject="Note 1")
        _interaction(household, owner, project, itype="expense", subject="Expense 1")
        counts = project_tab_counts(project)
        assert counts["timeline"] == 2
        assert counts["notes"] == 1
        assert counts["expenses"] == 1

    def test_document_link_increments_documents_not_photos(self, household, owner, project):
        doc = _document(household, owner, doc_type="document")
        link_document(entity=project, document=doc, user=owner)
        counts = project_tab_counts(project)
        assert counts["documents"] == 1
        assert counts["photos"] == 0

    def test_photo_link_increments_photos_not_documents(self, household, owner, project):
        photo = _document(household, owner, doc_type="photo", name="Photo", suffix="jpg")
        link_document(entity=project, document=photo, user=owner)
        counts = project_tab_counts(project)
        assert counts["photos"] == 1
        assert counts["documents"] == 0

    def test_documents_and_photos_split_correctly(self, household, owner, project):
        doc = _document(household, owner, doc_type="invoice", name="Invoice")
        photo = _document(household, owner, doc_type="photo", name="Photo", suffix="jpg")
        link_document(entity=project, document=doc, user=owner)
        link_document(entity=project, document=photo, user=owner)
        counts = project_tab_counts(project)
        assert counts["documents"] == 1
        assert counts["photos"] == 1

    def test_combined_counts_all_tabs(self, household, owner, project):
        """All six resource types contribute independently."""
        Task.objects.create(
            household=household, created_by=owner,
            subject="Task 1", project=project,
        )
        _interaction(household, owner, project, itype="note", subject="Note 1")
        _interaction(household, owner, project, itype="expense", subject="Expense 1")
        doc = _document(household, owner, doc_type="document")
        photo = _document(household, owner, doc_type="photo", name="Photo", suffix="jpg")
        link_document(entity=project, document=doc, user=owner)
        link_document(entity=project, document=photo, user=owner)
        counts = project_tab_counts(project)
        assert counts["tasks"] == 1
        assert counts["notes"] == 1
        assert counts["expenses"] == 1
        assert counts["timeline"] == 2
        assert counts["documents"] == 1
        assert counts["photos"] == 1

    def test_unlinked_project_items_do_not_bleed_into_another_project(
        self, household, owner, project
    ):
        """Items on project-B must not appear in project-A counts."""
        project_b = _project(household, owner, title="Project B")
        Task.objects.create(
            household=household, created_by=owner,
            subject="B-task", project=project_b,
        )
        _interaction(household, owner, project_b, itype="note", subject="B-note")
        counts_a = project_tab_counts(project)
        assert counts_a["tasks"] == 0
        assert counts_a["timeline"] == 0


# ---------------------------------------------------------------------------
# TestProjectTabCountsAPI — tab_counts exposed by ProjectSerializer
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProjectTabCountsAPI:
    """tab_counts is None on list, a dict on retrieve."""

    def test_tab_counts_is_none_on_list(self, owner_client, project):
        url = reverse("project-list")
        response = owner_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data if isinstance(response.data, list) else response.data.get("results", response.data)
        for item in results:
            assert item["tab_counts"] is None, (
                f"tab_counts should be None on list, got {item['tab_counts']!r}"
            )

    def test_tab_counts_is_dict_on_retrieve(self, owner_client, project):
        url = reverse("project-detail", kwargs={"pk": project.id})
        response = owner_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        tc = response.data["tab_counts"]
        assert isinstance(tc, dict)
        assert set(tc.keys()) >= {"tasks", "notes", "expenses", "documents", "photos", "timeline"}

    def test_tab_counts_zeros_on_fresh_project_via_api(self, owner_client, project):
        url = reverse("project-detail", kwargs={"pk": project.id})
        response = owner_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        tc = response.data["tab_counts"]
        assert tc["tasks"] == 0
        assert tc["notes"] == 0
        assert tc["expenses"] == 0
        assert tc["documents"] == 0
        assert tc["photos"] == 0
        assert tc["timeline"] == 0

    def test_tab_counts_reflect_created_items_via_api(self, owner_client, owner, household, project):
        Task.objects.create(
            household=household, created_by=owner,
            subject="API task", project=project,
        )
        _interaction(household, owner, project, itype="expense", subject="API expense")
        photo = _document(household, owner, doc_type="photo", name="Facade", suffix="jpg")
        link_document(entity=project, document=photo, user=owner)

        url = reverse("project-detail", kwargs={"pk": project.id})
        response = owner_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        tc = response.data["tab_counts"]
        assert tc["tasks"] == 1
        assert tc["expenses"] == 1
        assert tc["photos"] == 1
        assert tc["timeline"] == 1

    def test_anonymous_cannot_retrieve_project(self, project):
        client = APIClient()
        url = reverse("project-detail", kwargs={"pk": project.id})
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cross_household_cannot_retrieve_project(self, project):
        other_user = UserFactory(email="tabcount-other@example.com")
        other_hh = _household("Other House")
        _membership(other_user, other_hh)
        other_user.active_household = other_hh
        other_user.save(update_fields=["active_household"])
        other_client = _client_for(other_user)

        url = reverse("project-detail", kwargs={"pk": project.id})
        response = other_client.get(url)
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# TestTheCountAgreesWithTheTab — parcours 33, lot 1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTheCountAgreesWithTheTab:
    """Un compteur ne peut pas avoir deux définitions — pas même face à lui-même.

    Ces six nombres comptaient **tout le foyer** pendant que les listes derrière
    chaque onglet filtrent la confidentialité : Bob lisait « Tâches (3) » et
    l'onglet lui en servait deux. Le défaut n'est pas cosmétique — hors argent,
    « privé » veut dire absent *sans trace*, et un compteur qui déborde annonce
    l'existence de la tâche privée d'Alice à qui sait soustraire.

    Le test compare le compteur à **la liste que le même lecteur reçoit**, plutôt
    que de vérifier une valeur écrite en dur : c'est la seule forme qui reste vraie
    le jour où la liste change de règle.
    """

    @pytest.fixture
    def duo(self, db):
        household = _household("Foyer à deux")
        alice = UserFactory(email="tabcount-alice@example.com")
        bob = UserFactory(email="tabcount-bob@example.com")
        _membership(alice, household)
        _membership(bob, household, role=HouseholdMember.Role.MEMBER)
        return household, alice, bob

    def test_a_private_task_is_counted_for_its_author_only(self, duo):
        household, alice, bob = duo
        project = _project(household, alice, title="Chantier partagé")
        Task.objects.create(
            household=household, created_by=alice,
            subject="Publique", project=project,
        )
        Task.objects.create(
            household=household, created_by=alice,
            subject="Privée", project=project, is_private=True,
        )

        assert project_tab_counts(project, alice)["tasks"] == 2
        assert project_tab_counts(project, bob)["tasks"] == 1

    def test_a_private_note_is_counted_for_its_author_only(self, duo):
        household, alice, bob = duo
        project = _project(household, alice, title="Chantier partagé")
        _interaction(household, alice, project, itype="note", subject="Publique")
        private = _interaction(household, alice, project, itype="note", subject="Privée")
        private.is_private = True
        private.save(update_fields=["is_private"])

        assert project_tab_counts(project, alice)["notes"] == 2
        assert project_tab_counts(project, bob)["notes"] == 1
        assert project_tab_counts(project, bob)["timeline"] == 1

    def test_a_private_document_is_counted_for_its_author_only(self, duo):
        household, alice, bob = duo
        project = _project(household, alice, title="Chantier partagé")

        shared = _document(household, alice, name="Devis partagé")
        secret = _document(household, alice, name="Devis confidentiel")
        secret.is_private = True
        secret.save(update_fields=["is_private"])
        link_document(entity=project, document=shared, user=alice)
        link_document(entity=project, document=secret, user=alice)

        assert project_tab_counts(project, alice)["documents"] == 2
        assert project_tab_counts(project, bob)["documents"] == 1

    def test_the_count_matches_the_list_the_same_reader_gets(self, duo):
        """Le contrôle qui compte : l'onglet et son nombre, pour le même lecteur."""
        household, alice, bob = duo
        project = _project(household, alice, title="Chantier partagé")
        Task.objects.create(
            household=household, created_by=alice, subject="Publique", project=project,
        )
        Task.objects.create(
            household=household, created_by=alice,
            subject="Privée", project=project, is_private=True,
        )

        for user in (alice, bob):
            client = _client_for(user)
            detail = client.get(reverse("project-detail", args=[project.id]))
            assert detail.status_code == status.HTTP_200_OK
            announced = detail.data["tab_counts"]["tasks"]

            listed = client.get(reverse("task-list"), {"project": str(project.id)})
            assert listed.status_code == status.HTTP_200_OK
            rows = listed.data if isinstance(listed.data, list) else listed.data["results"]

            assert announced == len(rows), (
                f"{user.email} : l'onglet annonce {announced} tâches et la liste en "
                f"sert {len(rows)}"
            )

    def test_a_private_expense_is_counted_for_everyone(self, duo):
        """L'exception de l'argent, ici aussi — et pour la même raison.

        Une dépense ne disparaît d'aucune liste : sept agrégations la lisent. Le
        compteur doit donc l'annoncer aux deux lecteurs, sans quoi l'onglet
        promettrait moins que ce qu'il sert.
        """
        household, alice, bob = duo
        project = _project(household, alice, title="Chantier partagé")
        expense = _interaction(household, alice, project, itype="expense", subject="Achat")
        expense.is_private = True
        expense.save(update_fields=["is_private"])

        assert project_tab_counts(project, alice)["expenses"] == 1
        assert project_tab_counts(project, bob)["expenses"] == 1
