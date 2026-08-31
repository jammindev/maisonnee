from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tasks'

    def ready(self):
        from agent.listables import ListableSpec, ListFilter, register as register_listable
        from agent.searchables import SearchableSpec, register
        from agent.writables import WritableSpec, register as register_writable
        from core.visibility import (
            PrivacySpec,
            register as register_privacy,
            visible_to_creator,
        )
        from .models import Task

        # Confidentialité — la déclaration vit ici, une seule fois, et vaut pour
        # toutes les portes de lecture (liste REST, palette ⌘K, agent, contexte
        # ancré). Voir ``core.visibility``.
        register_privacy(PrivacySpec(model=Task, narrow=visible_to_creator))

        register(SearchableSpec(
            entity_type='task',
            model=Task,
            search_fields=('subject', 'content'),
            label_attr='subject',
            url_template='/app/tasks/{id}',
        ))

        register_writable(WritableSpec(
            entity_type='task',
            create=_create_task_from_agent,
            update=_update_task_from_agent,
            updatable_fields=('subject', 'content', 'status', 'due_date', 'priority', 'needs_dry_weather'),
            resolve=_resolve_task_for_agent,
            delete=_delete_task_from_agent,
            label_attr='subject',
            url_template='/app/tasks/{id}',
        ))

        register_listable(ListableSpec(
            entity_type='task',
            model=Task,
            filters=(
                ListFilter('status', 'comma-separated statuses', _filter_status),
                ListFilter('due_before', 'due date <= YYYY-MM-DD', _filter_due_before),
                ListFilter('due_after', 'due date >= YYYY-MM-DD', _filter_due_after),
                ListFilter('overdue', "'true' = past due and not done/archived", _filter_overdue),
            ),
            order_by=('due_date', '-created_at'),
            describe=_describe_task,
        ))


def _create_task_from_agent(household, user, fields, *, anchor=None):
    """Map the agent's raw ``fields`` to ``tasks.services.create_task``.

    La pièce vient d'abord de ``fields`` (``zone`` = nom ou id, ``zone_ids`` =
    liste d'ids) ; l'``anchor`` n'est qu'un **défaut** — un projet ancré
    pré-remplit le projet (dont le serializer hérite les zones), une zone ancrée
    pré-remplit la zone.

    Même trou que la note (#579), en plus discret : sans lecture de ``fields``, une
    tâche demandée « dans la salle de bain » tombait sur le repli **zone racine**
    du service, donc dans une pièce que personne n'avait nommée.
    """
    from zones.services import resolve_zone_ids

    from .services import create_task

    zone_ids = resolve_zone_ids(household, fields.get('zone'), fields.get('zone_ids'))

    project = None
    if anchor:
        anchor_type, anchor_id = anchor
        if anchor_type == 'project':
            project = anchor_id
        elif anchor_type == 'zone' and not zone_ids:
            zone_ids = [str(anchor_id)]

    priority = fields.get('priority')
    task = create_task(
        household,
        user,
        subject=(fields.get('subject') or '').strip(),
        content=fields.get('content'),
        due_date=fields.get('due_date'),
        priority=int(priority) if priority not in (None, '') else None,
        project=project,
        zone_ids=zone_ids,
        needs_dry_weather=bool(fields.get('needs_dry_weather')),
    )
    # L'agent ne crée que sur demande explicite : c'est le geste d'un membre, pas
    # de l'app. Le laisser muet ferait dépendre la notification du bouton
    # utilisé, ce qu'aucun membre du foyer ne peut deviner.
    from .notifications import notify_task_created

    notify_task_created(task, user)
    return task


def _update_task_from_agent(household, user, instance, fields):
    """Map the agent's raw ``fields`` to ``tasks.services.update_task``."""
    from .services import update_task

    return update_task(household, user, instance, fields=fields)


def _resolve_task_for_agent(household, raw_id):
    """Household-scoped task lookup for ``update_entity``."""
    from .models import Task

    return Task.objects.filter(household_id=household.id, pk=raw_id).first()


def _delete_task_from_agent(household, user, object_id):
    """Undo a created task — archive it, reusing ``tasks.services.archive_task``.

    Raises ``LookupError`` when the task is already gone so a double undo is a
    no-op rather than an error.
    """
    from .services import archive_task

    task = _resolve_task_for_agent(household, object_id)
    if task is None:
        raise LookupError(f"no task {object_id} in this household")
    archive_task(user, task)


# --- list_entities filters ---------------------------------------------------

_TASK_STATUSES = {'backlog', 'pending', 'in_progress', 'done', 'archived'}


def _filter_status(qs, value):
    statuses = [v.strip() for v in value.split(',') if v.strip()]
    unknown = [v for v in statuses if v not in _TASK_STATUSES]
    if not statuses or unknown:
        raise ValueError(f"unknown status: {', '.join(unknown) or '(empty)'}")
    return qs.filter(status__in=statuses)


def _filter_due_before(qs, value):
    return qs.filter(due_date__lte=_parse_date(value))


def _filter_due_after(qs, value):
    return qs.filter(due_date__gte=_parse_date(value))


def _filter_overdue(qs, value):
    from django.utils import timezone

    if value.strip().lower() not in ('true', '1', 'yes'):
        return qs
    return qs.filter(due_date__lt=timezone.localdate()).exclude(
        status__in=('done', 'archived')
    )


def _parse_date(value):
    from datetime import date

    return date.fromisoformat(value.strip())


def _describe_task(task) -> str:
    parts = [task.status]
    if task.due_date:
        parts.append(f"due {task.due_date.isoformat()}")
    if task.priority:
        parts.append(f"priority {task.priority}")
    return ' | '.join(parts)
