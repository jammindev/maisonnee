"""
Project cost computation.

The actual cost is no longer a maintained counter: it is the SUM of the
`amount` of the expense Interactions linked to the project via the polymorphic
source FK (#131 / #234). The DB column `actual_cost_cached` is kept for now but
never written anymore — every creation/edit/deletion path (purchase dialog,
agent, undo) is reflected without sync logic.

Expense amount/kind/supplier are real columns on Interaction; the shared
`interactions.queries` helpers own the expense-select convention.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from interactions.models import Interaction
from interactions.queries import AMOUNT_FIELD, ZERO, expenses


def _expense_amounts(project_ref):
    from .models import Project

    return expenses(
        base=Interaction.objects.filter(
            source_content_type=ContentType.objects.get_for_model(Project),
            source_object_id=project_ref,
        )
    )


def annotate_actual_cost(queryset):
    """Annotate each project with ``actual_cost_computed`` (one subquery, no N+1)."""
    totals = (
        _expense_amounts(OuterRef("pk"))
        .values("source_object_id")
        .annotate(total=Sum("amount"))
        .values("total")[:1]
    )
    return queryset.annotate(
        actual_cost_computed=Coalesce(Subquery(totals, output_field=AMOUNT_FIELD), ZERO)
    )


def project_actual_cost(project) -> Decimal:
    """Single-project fallback when the annotation is absent (e.g. fresh instance)."""
    return _expense_amounts(project.pk).aggregate(
        total=Coalesce(Sum("amount"), ZERO)
    )["total"]


def project_tab_counts(project, viewer=None) -> dict[str, int]:
    """Number of items behind each tab of the project detail page.

    Consumed by ``ProjectSerializer`` (detail only) so the frontend can hide
    empty tabs. Handful of aggregate queries — acceptable for a single object,
    NOT to be used on a list (would N+1). Mirrors exactly what each tab shows:
    active trackers only, documents excluding photos, interactions split by type.

    ⚠️ ``viewer`` n'est pas un raffinement, c'est la condition pour que le nombre
    veuille dire quelque chose. Ces compteurs comptaient **tout le foyer** pendant
    que les listes derrière chaque onglet filtrent la confidentialité : Bob lisait
    « Tâches (3) » et l'onglet lui en servait deux. Un compteur ne peut pas avoir
    deux définitions — et celui-ci trahissait en prime l'existence de la tâche
    privée d'Alice, alors que hors argent « privé » veut dire absent, sans trace.

    ``viewer=None`` reste fail-closed (voir ``core.visibility``) : un appelant qui
    oublie le lecteur sous-compte, il ne fuit pas.
    """
    from django.contrib.contenttypes.models import ContentType

    from core.visibility import narrow_for
    from documents.models import Document, DocumentLink
    from interactions.models import Interaction
    from tasks.models import Task
    from trackers.models import Tracker

    from .models import Project

    project_ct = ContentType.objects.get_for_model(Project)
    interactions = narrow_for(
        Interaction.objects.filter(
            source_content_type=project_ct, source_object_id=project.id
        ),
        viewer,
    )
    # Le lien n'a pas de drapeau : c'est le **document** qu'il pointe qui en porte
    # un. On borne donc par les documents lisibles, plutôt que de réécrire ici la
    # règle avec un préfixe de relation — deux écritures de la même règle, et c'est
    # toujours la plus permissive qui gagne en silence.
    links = DocumentLink.objects.filter(
        content_type=project_ct,
        object_id=project.id,
        document__in=narrow_for(Document.objects.all(), viewer),
    )

    return {
        "tasks": narrow_for(Task.objects.filter(project=project), viewer).count(),
        "trackers": Tracker.objects.filter(project=project, is_active=True).count(),
        "notes": interactions.filter(type="note").count(),
        "expenses": interactions.filter(type="expense").count(),
        "documents": links.exclude(document__type="photo").count(),
        "photos": links.filter(document__type="photo").count(),
        "timeline": interactions.count(),
    }


# --- Création assistée (parcours 32, lot 2) ----------------------------------
#
# Le pendant en écriture de `assistant.py`. La séparation est le sujet : le
# module qui parle au modèle ne connaît aucune écriture, celui-ci ne parle à
# aucun modèle. « Rien n'est écrit avant relecture » ne dépend donc pas d'un
# `if`, mais du fait qu'un des deux ne sait physiquement pas écrire.
#
# Rien ici ne crée d'objet à la main : le projet passe par `ProjectSerializer`,
# chaque tâche par `tasks.services.create_task`, chaque note par
# `interactions.services.create_note_interaction`. Un chemin d'écriture parallèle
# rouvrirait tous les invariants que ces services tiennent — le repli sur la zone
# racine d'une tâche, le scope foyer, les bornes de priorité.

#: Les champs du plan qui vont droit dans `ProjectSerializer`. Tout le reste de
#: la ligne `project` (notamment `unresolved_zone_names`, qui n'existe que pour
#: l'écran) est **ignoré** : un plan porte de l'affichage en plus de la donnée.
_PROJECT_FIELDS = (
    "title",
    "description",
    "type",
    "priority",
    "planned_budget",
    "start_date",
    "due_date",
    "tags",
    "zone_ids",
)


def create_project_from_plan(household, user, *, plan: dict):
    """Écrit le plan relu : un projet, ses tâches, ses notes — ou rien.

    ``plan`` est la sortie **validée** de `ProjectPlanSerializer`, donc du contenu
    utilisateur : entre la génération et cet appel, l'humain a corrigé des titres
    et décoché des lignes.

    Tout est dans **une** transaction, et c'est un critère et pas un réflexe : un
    chantier créé avec quatre tâches sur six est un demi-succès qui ressemble
    exactement à un succès, et personne ne saurait dire lesquelles manquent. Une
    ligne fautive lève une `ValidationError` **préfixée de son numéro** — un
    mauvais id de zone doit se lire, pas donner un 500.

    Le projet n'est pas marqué comme venant de l'assistant, et c'est délibéré :
    il naît en `draft` comme celui du formulaire, avec les mêmes défauts. Ce que
    l'utilisateur a validé est de lui.
    """
    from django.db import transaction

    from interactions.services import create_note_interaction
    from tasks.services import create_task

    from .serializers import ProjectSerializer

    raw_project = dict(plan.get("project") or {})
    # Une valeur absente ou nulle laisse parler le défaut du modèle. Le moteur
    # **retire** ce qu'il n'a pas su valider (un `type` hors énumération, une
    # priorité hors bornes) plutôt que de le deviner : ce `None` est donc une
    # information, pas un oubli.
    payload = {
        key: raw_project[key]
        for key in _PROJECT_FIELDS
        if raw_project.get(key) is not None
    }

    with transaction.atomic():
        serializer = ProjectSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        project = serializer.save(household=household, created_by=user)

        for index, task in enumerate(plan.get("tasks") or []):
            with _numbered("tasks", index):
                create_task(
                    household,
                    user,
                    subject=task["subject"],
                    content=task.get("content") or "",
                    due_date=task.get("due_date"),
                    priority=task.get("priority"),
                    project=project,
                    zone_ids=task.get("zone_ids") or None,
                )

        for index, note in enumerate(plan.get("notes") or []):
            with _numbered("notes", index):
                create_note_interaction(
                    household=household,
                    user=user,
                    subject=note["subject"],
                    content=note.get("content") or "",
                    # La note est rattachée au chantier par la FK polymorphe —
                    # c'est ce que compte `project_tab_counts`, donc la condition
                    # pour qu'elle apparaisse dans l'onglet du projet.
                    project=project,
                    zone_ids=note.get("zone_ids") or None,
                )

    return project


@contextmanager
def _numbered(label: str, index: int):
    """Transforme l'échec d'une ligne en 400 qui dit **laquelle**.

    Les trois créateurs ne lèvent pas la même chose, et l'appelant n'a pas à
    connaître cette différence :

    - `create_task` valide par un serializer DRF → `ValidationError` ;
    - `create_note_interaction` valide à la main → `ValueError` ;
    - `TaskSerializer.create` fait un `Zone.objects.get(...)` sur chaque zone →
      **`ObjectDoesNotExist`** quand l'id n'existe pas dans le foyer.

    Le troisième cas n'est pas théorique : l'écran de relecture envoie des ids, et
    une zone supprimée entre l'entretien et la création donne exactement ça. Il
    faut le rattraper, sinon un plan par ailleurs correct rend un 500 sur une
    donnée périmée.

    ⚠️ Le même trou existe sur `POST /api/tasks/tasks/`, où un `zone_ids` inconnu
    rend un 500 au lieu d'un 400 — défaut préexistant, hors périmètre de ce lot,
    suivi par une issue. On le borne ici sans le corriger là-bas : le vrai
    correctif est une validation dans `TaskSerializer`, qui profiterait aux deux.

    Sans le préfixe de ligne, « une ou plusieurs zones n'appartiennent pas au
    foyer » sur un plan de huit tâches n'aide personne. Patron de
    `banking.views.set_allocations`.
    """
    from django.core.exceptions import ObjectDoesNotExist
    from rest_framework.exceptions import ValidationError

    try:
        yield
    except ValidationError as exc:
        raise ValidationError({label: [f"ligne {index + 1} : {exc.detail}"]}) from exc
    except (ValueError, ObjectDoesNotExist) as exc:
        raise ValidationError({label: [f"ligne {index + 1} : {exc}"]}) from exc
# ── Privatiser un chantier ────────────────────────────────────────────────────


def foreign_content_counts(project, user) -> dict[str, int]:
    """Ce que le chantier contient et qui n'appartient pas à ``user``.

    Compté par famille pour que le refus puisse **dire** ce qui bloque : « 2 tâches
    et 1 note d'un autre membre » se corrige, « impossible » ne se corrige pas.
    """
    from django.contrib.contenttypes.models import ContentType

    from documents.models import DocumentLink
    from interactions.models import Interaction
    from tasks.models import Task
    from trackers.models import Tracker

    from .models import Project

    project_ct = ContentType.objects.get_for_model(Project)
    return {
        "tasks": Task.objects.filter(project=project).exclude(created_by=user).count(),
        "interactions": Interaction.objects.filter(
            source_content_type=project_ct, source_object_id=project.id
        ).exclude(created_by=user).count(),
        "trackers": Tracker.objects.filter(project=project).exclude(created_by=user).count(),
        "documents": DocumentLink.objects.filter(
            content_type=project_ct, object_id=project.id
        ).exclude(document__created_by=user).count(),
    }


def assert_can_privatise(project, user) -> None:
    """Refuser de privatiser un chantier qui contient le travail d'un autre.

    Le troisième chemin possible, et le seul honnête. Les deux autres étaient
    mauvais symétriquement : « le chantier gagne » **confisque** à l'autre membre ce
    qu'il a écrit — sa tâche disparaît sans un mot et il ne peut pas la retrouver ;
    « le créateur garde » ne confisque rien mais fait **mentir la case**, puisque le
    chantier cesse d'être privé dès qu'un autre membre y a touché.

    Un refus, lui, se voit. Et il ne coûte rien au cas réel : le chantier surprise
    est créé par une seule personne, donc il passe. Seul l'ambigu est refusé.

    Corollaire qui simplifie tout le reste du parcours : **la cascade ne porte
    jamais que sur ce que le demandeur a créé lui-même**, ce qui supprime la
    question « privé pour qui ? » au niveau des enfants.
    """
    from rest_framework import serializers as drf_serializers

    counts = {family: n for family, n in foreign_content_counts(project, user).items() if n}
    if not counts:
        return

    detail = ", ".join(f"{n} {family}" for family, n in sorted(counts.items()))
    raise drf_serializers.ValidationError({
        "is_private": (
            "Ce chantier contient le travail d'autres membres du foyer "
            f"({detail}). Le rendre privé le leur retirerait sans un mot : "
            "détachez ces éléments ou demandez à leurs auteurs de les rendre "
            "privés eux-mêmes."
        ),
        "foreign_content": counts,
    })


def retract_notifications_for(project) -> int:
    """Retirer des cloches ce que la privatisation vient de rendre inaccessible.

    Une annonce ne survit pas à son sujet — même règle qu'à la suppression d'une
    note. Ici le sujet n'est pas supprimé, il devient invisible à tous sauf un :
    une notification « Bob a terminé Poser le bardage » qui mène à un écran vide
    ferait chercher au lecteur ce que l'app vient de lui cacher, sans qu'il puisse
    savoir si c'est l'app ou lui qui se trompe.
    """
    from django.contrib.contenttypes.models import ContentType

    from interactions.models import Interaction
    from notifications.models import Notification
    from notifications.service import retract_by_payload
    from tasks.models import Task

    from .models import Project

    retracted = 0
    for task_id in Task.objects.filter(project=project).values_list("id", flat=True):
        retracted += retract_by_payload(
            Notification.Type.TASK_CREATED, task_id=str(task_id)
        )

    note_ids = Interaction.objects.filter(
        source_content_type=ContentType.objects.get_for_model(Project),
        source_object_id=project.id,
        type="note",
    ).values_list("id", flat=True)
    for note_id in note_ids:
        # La clé de payload est ``note_id`` — voir ``interactions.notifications``.
        # Se tromper de nom ne lève rien : le filtre JSON ne matche simplement
        # aucune ligne, et la rétractation devient un no-op silencieux.
        retracted += retract_by_payload(
            Notification.Type.NOTE_CREATED, note_id=str(note_id)
        )
    return retracted

