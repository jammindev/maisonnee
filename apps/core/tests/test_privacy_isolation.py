"""Isolation en confidentialité — un item privé ne sort pas de sa liste.

Troisième volet de la famille ``test_tenant_isolation`` (lectures entre foyers)
et ``test_write_isolation`` (FK de serializer). Celui-ci porte sur la frontière
*à l'intérieur* d'un foyer : ``moi`` vs ``les autres membres``.

Pourquoi un test transverse et pas trois tests locaux
-----------------------------------------------------

``is_private`` existait sur quatre modèles, avec son badge dans l'UI, sa
contrainte DB et son exclusion du récap — et n'était filtré en liste que sur
deux d'entre eux. Le drapeau était décoratif là où il comptait le plus, et
personne ne l'a vu, parce que le défaut est invisible deux fois :

- **en revue**, un ``get_queryset()`` qui oublie la clause ressemble trait pour
  trait à celui qui la porte ;
- **à l'usage**, il faut deux comptes dans le même foyer pour s'en apercevoir —
  c'est-à-dire précisément ce qu'un développeur seul n'a jamais sous la main.

D'où la forme : le test ne vérifie pas trois vues, il vérifie **la règle**, et
refuse qu'un cinquième modèle privatisable arrive sans se déclarer.

Les quatre parties sont nécessaires
-----------------------------------

1. **Structurelle** — aucune vue n'expose ``is_private`` en filtre. Sans ce
   contrôle, la partie n°2 se laisse contourner : le queryset a beau borner, un
   ``?is_private=true`` ré-ouvre exactement ce qu'il bornait. C'est le même
   rapport que la clé i18n et son ``defaultValue``.
2. **Comportementale** — un second membre ne voit pas l'item privé du premier.
   C'est le seul contrôle qui compare le *code* à ce que l'API sert vraiment.
3. **Complétude** — un modèle portant le drapeau doit être couvert ou exempté.
   Sans elle, les deux premières restent vertes en ignorant le nouveau venu.
4. **La déclaration** — un modèle privatisable est enregistré dans
   ``core.visibility.REGISTRY``. Les trois premières parties ne regardent que les
   listes REST, et **une liste bornée ne borne pas ⌘K** : la palette du haut,
   ``search_household``, ``get_entity``, ``get_related``, ``list_entities`` et le
   contexte ancré ne passent jamais par le viewset. Une seule déclaration les
   ferme toutes, parce que toutes appellent ``narrow_for``. La restriction a
   d'abord vécu sur le ``SearchableSpec`` de l'agent, et un seul spec sur quatre
   la déclarait — la tâche privée d'un membre était donc absente de sa liste et
   citable par l'assistant. Elle a été déplacée vers le registre parce que lier
   la confidentialité au fait d'être *cherchable* laissait deux trous : un modèle
   privatisable non searchable (``Briefing``) n'avait nulle part où se déclarer,
   et une confidentialité **héritée** ne porte aucun champ à inspecter.

Limite connue : la partie n°1 lit ``filterset_fields``, pas un éventuel
``filterset_class`` (le dépôt n'en utilise aucun). Le jour où l'un apparaît, il
faudra l'inspecter ici aussi — un filtre déclaré autrement reste un filtre.
"""
import importlib
import inspect
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.viewsets import GenericViewSet

from accounts.tests.factories import UserFactory
from households.models import Household, HouseholdMember

#: Racine des apps du projet. Sert à ne parcourir que **notre** code : sans ce
#: bornage on inspecterait aussi Django et DRF, dont les modèles et les vues ne
#: nous regardent pas et feraient échouer la partie n°3 sur un faux positif.
_PROJECT_APPS_DIR = Path(settings.BASE_DIR) / "apps"


def _is_project_app(app_config) -> bool:
    return Path(app_config.path).is_relative_to(_PROJECT_APPS_DIR)


# ── Ce qui n'est pas encore filtré, et pourquoi ──────────────────────────────
#
# Même convention que ``EXEMPT_FIELDS`` dans ``test_write_isolation`` : une
# exemption est une dette **nommée**, avec sa raison et ce qui protège à la
# place. Le silence, lui, ne se relit pas.
#
# Le dictionnaire est vide, et c'est un acquis récent : les quatre modèles
# portant le drapeau sont couverts. ``interactions.Interaction`` y a longtemps
# figuré, parce que filtrer une dépense supposait d'avoir décidé ce que
# « dépense privée » veut dire. C'est tranché : l'argent ne **disparaît** jamais
# d'une liste — sept agrégations le lisent — il se **masque**. La liste borne
# donc tout sauf les dépenses (``interactions.visibility``), et le masquage de
# leur contenu est le lot 4 du parcours 33. Voir
# ``TestAPrivateExpenseIsNeverHidden`` plus bas : le report est un choix écrit,
# pas un oubli.

EXEMPT_MODELS: dict[str, str] = {}


def _models_with_is_private():
    """Tous les modèles du projet portant un champ ``is_private``."""
    found = []
    for model in django_apps.get_models():
        if not _is_project_app(model._meta.app_config):
            continue
        if any(f.name == "is_private" for f in model._meta.get_fields()):
            found.append(model)
    return found


def _label(model) -> str:
    return f"{model._meta.app_label}.{model.__name__}"


def _all_viewsets():
    """Toutes les classes de viewset déclarées dans les modules ``views`` du projet.

    ``startswith`` et non ``==`` sur ``__module__`` : ``accounts.views`` est un
    **package**, et ses viewsets vivent dans ``accounts.views.api``. Une égalité
    stricte les écartait — c'est-à-dire qu'elle ouvrait un angle mort exactement là
    où le dépôt s'écarte déjà de la convention, et un garde-fou aveugle sur
    l'exception est un garde-fou qui rassure à tort.
    """
    found = {}
    for config in django_apps.get_app_configs():
        if not _is_project_app(config):
            continue
        for suffix in ("views", "views_media"):
            module_name = f"{config.name}.{suffix}"
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError:
                continue
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, GenericViewSet) and obj.__module__.startswith(module_name):
                    found[f"{obj.__module__}.{name}"] = obj
    return found


# ── 1. Structurel : aucun filtre ne ré-ouvre ce que le queryset borne ────────


class TestNoViewExposesThePrivacyFlagAsAFilter:
    def test_no_filterset_field_named_is_private(self):
        offenders = [
            name
            for name, viewset in _all_viewsets().items()
            if "is_private" in (getattr(viewset, "filterset_fields", None) or ())
        ]
        assert not offenders, (
            "Ces vues exposent ?is_private= en filtre, c'est-à-dire l'endroit exact "
            "où lire les items privés des autres membres : "
            f"{offenders}. Un filtre ne doit jamais pouvoir élargir ce que borne le "
            "queryset — pour retrouver ses propres items privés, filtrer côté client "
            "ou ajouter un ?mine=true qui ne peut porter que sur soi."
        )


# ── 2. Comportemental : le second membre ne voit rien ────────────────────────


@pytest.fixture
def duo(db):
    """Un foyer, deux membres : Alice écrit, Bob lit."""
    household = Household.objects.create(name="Foyer privé")
    alice = UserFactory(email="privacy-alice@example.com")
    bob = UserFactory(email="privacy-bob@example.com")
    HouseholdMember.objects.create(household=household, user=alice, role="owner")
    HouseholdMember.objects.create(household=household, user=bob, role="member")
    return household, alice, bob


def _as(user, household):
    client = APIClient()
    client.force_authenticate(user=user)
    return client, {"household_id": str(household.id)}


def _labels(response, key):
    payload = response.data
    rows = payload if isinstance(payload, list) else (payload.get("results") or [])
    return [row.get(key) for row in rows]


@pytest.mark.django_db
class TestAPrivateItemStaysWithItsAuthor:
    """Pour chaque modèle couvert : Alice le voit, Bob ne le voit pas."""

    def test_task(self, duo):
        from tasks.models import Task

        household, alice, bob = duo
        Task.objects.create(
            household=household, created_by=alice,
            subject="Cadeau d'anniversaire de Bob", is_private=True,
        )

        client, params = _as(bob, household)
        assert "Cadeau d'anniversaire de Bob" not in _labels(
            client.get(reverse("task-list"), params), "subject"
        )

        client, params = _as(alice, household)
        assert "Cadeau d'anniversaire de Bob" in _labels(
            client.get(reverse("task-list"), params), "subject"
        )

    def test_document(self, duo):
        from documents.models import Document

        household, alice, bob = duo
        Document.objects.create(
            household=household, created_by=alice,
            name="Bilan médical", file_path=f"{household.id}/documents/bilan.pdf",
            is_private=True,
        )

        client, params = _as(bob, household)
        assert "Bilan médical" not in _labels(
            client.get(reverse("document-list"), params), "name"
        )

        client, params = _as(alice, household)
        assert "Bilan médical" in _labels(
            client.get(reverse("document-list"), params), "name"
        )

    def test_note(self, duo):
        from django.utils import timezone

        from interactions.models import Interaction

        household, alice, bob = duo
        Interaction.objects.create(
            household=household, created_by=alice,
            subject="Idée de cadeau pour Bob", type="note", is_private=True,
            # Contrainte ``interactions_occurred_at_required`` : une entrée de
            # journal sans date n'est pas une entrée de journal.
            occurred_at=timezone.now(),
        )

        client, params = _as(bob, household)
        assert "Idée de cadeau pour Bob" not in _labels(
            client.get(reverse("interaction-list"), params), "subject"
        )

        client, params = _as(alice, household)
        assert "Idée de cadeau pour Bob" in _labels(
            client.get(reverse("interaction-list"), params), "subject"
        )

    def test_briefing(self, duo):
        from briefings.models import Briefing

        household, alice, bob = duo
        Briefing.objects.create(
            household=household, created_by=alice,
            title="Mes rendez-vous", prompt="Résume mon agenda", is_private=True,
        )

        client, params = _as(bob, household)
        assert "Mes rendez-vous" not in _labels(
            client.get(reverse("briefing-list"), params), "title"
        )

        client, params = _as(alice, household)
        assert "Mes rendez-vous" in _labels(
            client.get(reverse("briefing-list"), params), "title"
        )


@pytest.mark.django_db
class TestAPrivateExpenseIsNeverHidden:
    """L'exception, et la seule — écrite ici pour qu'on ait à la changer sciemment.

    Une dépense privée reste servie à tout le foyer. Ce n'est pas un trou dans la
    règle du dessus, c'est l'arbitrage du parcours 33 : ``Interaction(type=
    "expense")`` alimente ``interactions.queries.expenses()``, point de vérité
    unique de sept agrégations. La retirer d'une liste sans la retirer des totaux
    donnerait au budget « Bricolage » deux valeurs selon le lecteur — « un compteur
    ne peut pas avoir deux définitions ».

    Le secret d'une dépense porte donc sur son **contenu**, pas sur son existence :
    le lot 4 remplacera sujet, fournisseur et projet source par « Dépense privée »
    pour les autres membres. Tant que ce masquage n'est pas là, ce test échouera si
    quelqu'un « corrige » l'exception en la cachant — ce qui est précisément le but.
    """

    def test_the_other_member_still_sees_the_row(self, duo):
        from decimal import Decimal

        from django.utils import timezone

        from interactions.models import Interaction

        household, alice, bob = duo
        Interaction.objects.create(
            household=household, created_by=alice,
            subject="Achat — Terrasse", type="expense", is_private=True,
            amount=Decimal("250.00"), occurred_at=timezone.now(),
        )

        client, params = _as(bob, household)
        subjects = _labels(client.get(reverse("interaction-list"), params), "subject")
        assert "Achat — Terrasse" in subjects, (
            "Une dépense privée doit rester servie : sept agrégations la lisent, et "
            "la cacher en liste sans la retirer des totaux donne deux définitions au "
            "même compteur. Ce qui doit disparaître pour Bob, c'est le *contenu* — "
            "voir le lot 4 du parcours 33."
        )


# ── 3. Le catalogue ne peut pas prendre de retard sur le code ────────────────


class TestEveryPrivatisableModelIsAccountedFor:
    """Un cinquième modèle portant ``is_private`` doit se déclarer ici.

    Sans ce contrôle, les deux moitiés ci-dessus resteraient vertes en ignorant
    le nouveau venu — c'est la même règle que ``banking.compliance.REGISTRY`` :
    ajouter un mécanisme, c'est ajouter son détecteur.
    """

    COVERED = {
        "tasks.Task",
        "documents.Document",
        "briefings.Briefing",
        "interactions.Interaction",
    }

    def test_no_model_carries_the_flag_without_a_test_or_a_named_exemption(self):
        accounted = self.COVERED | set(EXEMPT_MODELS)
        actual = {_label(model) for model in _models_with_is_private()}

        unaccounted = actual - accounted
        assert not unaccounted, (
            f"Ces modèles portent is_private sans être couverts ni exemptés : "
            f"{sorted(unaccounted)}. Ajouter un cas dans "
            "TestAPrivateItemStaysWithItsAuthor, ou une entrée motivée dans "
            "EXEMPT_MODELS."
        )

        stale = accounted - actual
        assert not stale, (
            f"Ces entrées ne correspondent plus à aucun modèle : {sorted(stale)}. "
            "Une exemption périmée a l'air de faire autorité en étant fausse."
        )


# ── 4. La porte de l'agent : une liste bornée ne borne pas ⌘K ────────────────


class TestEveryPrivatisableModelDeclaresItsRestriction:
    """Un modèle privatisable est déclaré dans ``core.visibility.REGISTRY``.

    Les trois parties du dessus ne regardent que les listes REST. Or six autres
    portes ne passent **jamais** par le viewset : la palette ⌘K, le tool
    ``search_household``, ``get_entity``, ``get_related``, ``list_entities`` et le
    contexte d'une conversation ancrée. Une seule déclaration les ferme toutes,
    parce que toutes appellent ``core.visibility.narrow_for``.

    Le contrôle est structurel et pas comportemental, exprès : énumérer les sept
    portes dans un test finirait par en oublier une huitième, alors que la
    déclaration, elle, les ferme d'un coup. Même choix que pour
    ``banking.compliance.REGISTRY`` — on vérifie que le mécanisme est *déclaré*,
    pas qu'il a été recopié partout.

    ⚠️ Ce contrôle lit le **registre**, et surtout pas le champ ``is_private``.
    C'est ce qui lui permettra de voir arriver une confidentialité **héritée** —
    un tracker dont le projet est privé n'a aucun drapeau à inspecter, donc un
    catalogue adossé au ``grep`` du champ ne pourrait structurellement pas le
    couvrir.
    """

    def test_no_model_carries_the_flag_without_being_registered(self):
        from core import visibility

        registered = {spec.model for spec in visibility.REGISTRY}
        offenders = [
            _label(model)
            for model in _models_with_is_private()
            if model not in registered
        ]
        assert not offenders, (
            f"Ces modèles portent is_private sans être déclarés au registre de "
            f"visibilité : {sorted(offenders)}. Le queryset de leur vue a beau "
            "borner, les six portes de l'agent lisent core.visibility.REGISTRY — "
            "pas la vue. Enregistrer un PrivacySpec depuis l'apps.py de l'app "
            "propriétaire (narrow=visible_to_creator pour le couple is_private / "
            "created_by)."
        )

    def test_the_registry_has_no_stale_entry(self):
        """Une déclaration qui ne restreint plus rien a l'air de faire autorité."""
        from core import visibility

        privatisable = set(_models_with_is_private())
        inherited = set()  # confidentialité héritée : lot 4 (Tracker, Project…)
        stale = [
            _label(spec.model)
            for spec in visibility.REGISTRY
            if spec.model not in privatisable | inherited
        ]
        assert not stale, (
            f"Ces specs ne correspondent plus à un modèle privatisable : {sorted(stale)}. "
            "Une déclaration périmée a l'air de faire autorité en étant fausse."
        )

    def test_narrow_for_leaves_an_unregistered_model_alone(self, db):
        """« Pas de spec » veut dire « le scope foyer est toute la règle ».

        Le défaut ouvert est ici volontaire et borné par le test du dessus : sans
        lui, ``narrow_for`` planterait sur les dizaines d'entités qui n'ont aucune
        confidentialité, et on serait revenu à une liste de cas dans l'appelant.
        """
        from core import visibility
        from zones.models import Zone

        base = Zone.objects.all()
        assert visibility.narrow_for(base, None).query.__str__() == base.query.__str__()
