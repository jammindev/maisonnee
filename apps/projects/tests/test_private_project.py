"""Un chantier privé rend privé ce qu'il contient — et rien de plus.

Parcours 33, lot 4. Quatre propriétés, et chacune protège une décision distincte :

1. **La cascade porte** sur les tâches, les notes, les trackers et les documents.
2. **Elle s'arrête aux zones.** Une pièce de la maison est structurelle et partagée
   par vingt features ; la privatiser privatiserait la maison.
3. **Elle se calcule.** Rien n'est écrit sur les enfants, donc dé-privatiser rend
   exactement l'état d'avant — y compris ce qui était privé à titre propre.
4. **Elle refuse plutôt que de confisquer** le travail d'un autre membre.

Le piège que ce fichier existe surtout pour attraper
----------------------------------------------------

``TestAnItemWithoutAProjectStaysVisible``. Le filtre d'héritage s'écrit
``exclude(project__in=…)`` sur un champ **nullable**, et en SQL
``NOT (project_id IN (…))`` vaut NULL — donc « faux » — pour une ligne sans projet.
Écrit à la main avec un ``~Q(...)``, ce filtre ferait disparaître **toutes les
tâches sans chantier**, c'est-à-dire la grande majorité d'entre elles. Django ajoute
la clause ``OR project_id IS NULL`` qu'il faut ; le jour où quelqu'un « simplifie »
en réécrivant le ``Q``, seul ce test le dira — et le symptôme, une liste de tâches
vide, ne ressemblera pas du tout à un problème de confidentialité.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from documents.models import Document
from documents.services import link_document
from households.models import Household, HouseholdMember
from interactions.models import Interaction
from projects.models import Project
from tasks.models import Task
from trackers.models import Tracker
from zones.models import Zone


@pytest.fixture
def duo(db):
    household = Household.objects.create(name="Foyer à deux")
    alice = UserFactory(email="cascade-alice@example.com")
    bob = UserFactory(email="cascade-bob@example.com")
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


def _rows(response):
    payload = response.data
    return payload["results"] if isinstance(payload, dict) and "results" in payload else payload


def _project_ct():
    return ContentType.objects.get_for_model(Project)


@pytest.fixture
def furnished_project(duo):
    """Un chantier d'Alice, garni d'un exemplaire de chaque enfant."""
    household, alice, _bob = duo
    project = Project.objects.create(
        household=household, created_by=alice, title="Cabane surprise",
    )
    zone = Zone.objects.create(household=household, created_by=alice, name="Jardin")
    project.project_zones.create(zone=zone, created_by=alice)

    task = Task.objects.create(
        household=household, created_by=alice, subject="Poser le bardage", project=project,
    )
    note = Interaction.objects.create(
        household=household, created_by=alice, subject="Idée de couleur",
        type="note", occurred_at=timezone.now(),
        source_content_type=_project_ct(), source_object_id=project.id,
    )
    tracker = Tracker.objects.create(
        household=household, created_by=alice, name="Heures passées", project=project,
    )
    document = Document.objects.create(
        household=household, created_by=alice, name="Devis charpente",
        file_path=f"{household.id}/documents/devis.pdf", mime_type="application/pdf",
        type="document",
    )
    link_document(entity=project, document=document, user=alice)

    return {
        "project": project, "zone": zone, "task": task,
        "note": note, "tracker": tracker, "document": document,
    }


def _privatise(project):
    project.is_private = True
    project.save(update_fields=["is_private"])


@pytest.mark.django_db
class TestTheCascadeReaches:
    """Ce qu'un chantier privé emporte avec lui."""

    def test_its_task(self, duo, furnished_project):
        _household, _alice, bob = duo
        _privatise(furnished_project["project"])
        rows = _rows(_as(bob).get(reverse("task-list")))
        assert "Poser le bardage" not in [row["subject"] for row in rows]

    def test_its_note(self, duo, furnished_project):
        _household, _alice, bob = duo
        _privatise(furnished_project["project"])
        rows = _rows(_as(bob).get(reverse("interaction-list")))
        assert "Idée de couleur" not in [row["subject"] for row in rows]

    def test_its_document(self, duo, furnished_project):
        _household, _alice, bob = duo
        _privatise(furnished_project["project"])
        rows = _rows(_as(bob).get(reverse("document-list")))
        assert "Devis charpente" not in [row["name"] for row in rows]

    def test_its_tracker_even_though_it_has_no_flag_of_its_own(self, duo, furnished_project):
        """Le cas qui a justifié le registre du lot 2.

        ``Tracker`` ne porte pas ``is_private`` : aucun ``grep`` du champ n'aurait
        pu voir qu'il se restreint. Il fallait un endroit où le déclarer.
        """
        _household, _alice, bob = duo
        _privatise(furnished_project["project"])
        rows = _rows(_as(bob).get(reverse("tracker-list")))
        assert "Heures passées" not in [row["name"] for row in rows]

    def test_and_its_author_still_sees_everything(self, duo, furnished_project):
        _household, alice, _bob = duo
        _privatise(furnished_project["project"])

        assert "Poser le bardage" in [
            row["subject"] for row in _rows(_as(alice).get(reverse("task-list")))
        ]
        assert "Devis charpente" in [
            row["name"] for row in _rows(_as(alice).get(reverse("document-list")))
        ]


@pytest.mark.django_db
class TestTheCascadeStops:
    def test_a_zone_never_inherits(self, duo, furnished_project):
        """Une zone est une pièce de la maison, pas un secret.

        Elle est partagée par vingt features — tâches, photos, dépenses, relevés.
        La privatiser au passage privatiserait la maison, et la faire disparaître
        de la liste des zones casserait tous les écrans qui la nomment.
        """
        _household, _alice, bob = duo
        _privatise(furnished_project["project"])
        rows = _rows(_as(bob).get(reverse("zone-list")))
        assert "Jardin" in [row["name"] for row in rows]


@pytest.mark.django_db
class TestAnItemWithoutAProjectStaysVisible:
    """Le piège du NULL — voir l'entête du fichier.

    ``NOT (project_id IN (…))`` vaut NULL en SQL pour une ligne sans projet, donc
    un filtre écrit à la main ferait disparaître toutes les tâches libres. Le
    symptôme — une liste vide — ne ressemble pas à un problème de confidentialité,
    et c'est ce qui rend ce test indispensable.
    """

    def test_a_task_with_no_project(self, duo, furnished_project):
        household, alice, bob = duo
        Task.objects.create(household=household, created_by=alice, subject="Sortir les poubelles")
        _privatise(furnished_project["project"])

        rows = _rows(_as(bob).get(reverse("task-list")))
        assert "Sortir les poubelles" in [row["subject"] for row in rows]

    def test_a_tracker_with_no_project(self, duo, furnished_project):
        household, alice, bob = duo
        Tracker.objects.create(household=household, created_by=alice, name="Niveau de cuve")
        _privatise(furnished_project["project"])

        rows = _rows(_as(bob).get(reverse("tracker-list")))
        assert "Niveau de cuve" in [row["name"] for row in rows]

    def test_a_note_attached_to_nothing(self, duo, furnished_project):
        household, alice, bob = duo
        Interaction.objects.create(
            household=household, created_by=alice, subject="Le facteur est passé",
            type="note", occurred_at=timezone.now(),
        )
        _privatise(furnished_project["project"])

        rows = _rows(_as(bob).get(reverse("interaction-list")))
        assert "Le facteur est passé" in [row["subject"] for row in rows]


@pytest.mark.django_db
class TestItCalculatesAndNeverWrites:
    def test_de_privatising_gives_back_exactly_what_was_there(self, duo, furnished_project):
        """La raison d'être du choix « dérivé » plutôt que « propagé ».

        Une tâche privée **à titre propre** dans un chantier qu'on privatise puis
        dé-privatise doit rester privée. Un drapeau recopié sur les enfants aurait
        perdu cette distinction au premier aller-retour.
        """
        household, alice, bob = duo
        project = furnished_project["project"]
        secret = Task.objects.create(
            household=household, created_by=alice, subject="Cadeau de Bob",
            project=project, is_private=True,
        )

        _privatise(project)
        project.is_private = False
        project.save(update_fields=["is_private"])

        subjects = [row["subject"] for row in _rows(_as(bob).get(reverse("task-list")))]
        assert "Poser le bardage" in subjects, "la tâche publique revient"
        assert "Cadeau de Bob" not in subjects, "celle qui était privée le reste"
        secret.refresh_from_db()
        assert secret.is_private is True

    def test_an_assigned_task_keeps_its_assignee(self, duo, furnished_project):
        """La contrainte ``tasks_private_not_assigned`` n'est jamais heurtée.

        Un drapeau propagé aurait dû désassigner la tâche pour respecter la
        contrainte — c'est-à-dire détruire de l'information pour cocher une case.
        Rien n'étant écrit, la question ne se pose pas.
        """
        _household, _alice, bob = duo
        task = furnished_project["task"]
        task.assigned_to = bob
        task.save(update_fields=["assigned_to"])

        _privatise(furnished_project["project"])

        task.refresh_from_db()
        assert task.assigned_to_id == bob.id
        assert task.is_private is False


@pytest.mark.django_db
class TestItRefusesRatherThanConfiscates:
    def test_privatising_a_project_holding_another_members_work_is_a_named_400(
        self, duo, furnished_project
    ):
        household, alice, bob = duo
        project = furnished_project["project"]
        Task.objects.create(
            household=household, created_by=bob, subject="Commander le bois", project=project,
        )

        response = _as(alice).patch(
            reverse("project-detail", args=[project.id]), {"is_private": True}, format="json"
        )
        assert response.status_code == 400
        assert "is_private" in response.data
        # DRF convertit les valeurs d'un ValidationError en ErrorDetail (des
        # strings) : le compte se lit tel que le front le recevra.
        assert str(response.data["foreign_content"]["tasks"]) == "1"

        project.refresh_from_db()
        assert project.is_private is False, "un refus n'écrit rien"

    def test_the_real_case_goes_through(self, duo, furnished_project):
        """Le chantier surprise — créé par une seule personne — n'est jamais bloqué."""
        _household, alice, _bob = duo
        project = furnished_project["project"]

        response = _as(alice).patch(
            reverse("project-detail", args=[project.id]), {"is_private": True}, format="json"
        )
        assert response.status_code == 200, response.data
        project.refresh_from_db()
        assert project.is_private is True


@pytest.mark.django_db
class TestTheCountersFollowTheReader:
    def test_the_group_count_does_not_announce_a_hidden_project(self, duo, furnished_project):
        """Un groupe qui annonce « 2 » et en montre 1 trahit l'existence du second."""
        from projects.models import ProjectGroup

        household, alice, bob = duo
        group = ProjectGroup.objects.create(
            household=household, created_by=alice, name="Extérieur",
        )
        project = furnished_project["project"]
        project.project_group = group
        project.save(update_fields=["project_group"])
        Project.objects.create(
            household=household, created_by=alice, title="Terrasse", project_group=group,
        )

        _privatise(project)

        def count_for(user):
            rows = _rows(_as(user).get(reverse("project-group-list")))
            return next(row["projects_count"] for row in rows if row["name"] == "Extérieur")

        assert count_for(alice) == 2
        assert count_for(bob) == 1
