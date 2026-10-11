from django.apps import AppConfig


class TrackersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trackers'

    def ready(self):
        from core.visibility import PrivacySpec, register as register_privacy
        from .models import Tracker
        from .visibility import visible_trackers

        # Un tracker n'a pas de confidentialité propre — il hérite de celle de son
        # chantier. C'est exactement le cas qui a justifié le registre : sans
        # drapeau à inspecter, aucun ``grep`` de ``is_private`` ne l'aurait vu.
        register_privacy(PrivacySpec(model=Tracker, narrow=visible_trackers))

        from agent.listables import ListableSpec, ListFilter, register as register_listable
        from agent.searchables import SearchableSpec, register
        from agent.writables import WritableSpec, register as register_writable

        register(SearchableSpec(
            entity_type='tracker',
            module='trackers',
            model=Tracker,
            # entries_summary carries the latest values with deltas — the RAG
            # bridge that makes "où en est le compteur d'eau ?" citable.
            search_fields=('name', 'description', 'entries_summary'),
            label_attr='name',
            url_template='/app/trackers/{id}',
            related=_tracker_related,
        ))

        register_writable(WritableSpec(
            entity_type='tracker',
            module='trackers',
            create=_create_tracker_from_agent,
            update=_update_tracker_from_agent,
            updatable_fields=('name', 'unit', 'description', 'emoji'),
            resolve=_resolve_tracker_for_agent,
            label_attr='name',
            url_template='/app/trackers/{id}',
        ))

        register_writable(WritableSpec(
            entity_type='tracker_entry',
            module='trackers',
            create=_create_entry_from_agent,
            update=_update_entry_from_agent,
            updatable_fields=('value', 'occurred_at', 'note'),
            resolve=_resolve_entry_for_agent,
            label_attr=_entry_label,
            # No standalone entry page — the front redirects to the tracker.
            url_template='/app/tracker-entries/{id}',
        ))

        register_listable(ListableSpec(
            entity_type='tracker',
            module='trackers',
            model=Tracker,
            filters=(
                ListFilter('project', 'project id (uuid)', _filter_project),
                ListFilter('general', "'true' = no project", _filter_general),
            ),
            order_by=('-last_entry_at',),
            describe=_describe_tracker,
        ))


def _tracker_related(tracker):
    """The tracker's project anchor — citable via `get_related`."""
    return [tracker.project] if tracker.project is not None else []


# --- create/update handlers (thin adapters over trackers.services) -----------


def _create_tracker_from_agent(household, user, fields, *, anchor=None):
    """Map the agent's raw ``fields`` to ``trackers.services.create_tracker``.

    An anchored project pre-fills the tracker's project.
    """
    from .services import create_tracker

    project = None
    if anchor and anchor[0] == 'project':
        project = anchor[1]

    return create_tracker(
        household,
        user,
        name=(fields.get('name') or '').strip(),
        unit=(fields.get('unit') or '').strip() or None,
        description=fields.get('description'),
        emoji=fields.get('emoji'),
        project=project,
    )


def _update_tracker_from_agent(household, user, instance, fields):
    from .services import update_tracker

    return update_tracker(household, user, instance, fields=dict(fields))


def _resolve_tracker_for_agent(household, raw_id):
    from .models import Tracker

    return Tracker.objects.filter(household_id=household.id, pk=raw_id).first()


def _resolve_tracker(household_id, raw):
    """Find a tracker by id or name — household-scoped, active first.

    When the household has a single active tracker, an empty value resolves to
    it, so "note 148.2" works without naming the tracker.
    """
    import uuid

    from .models import Tracker

    qs = Tracker.objects.filter(household_id=household_id, is_active=True)
    value = (str(raw) if raw is not None else '').strip()
    if not value:
        trackers = list(qs[:2])
        if len(trackers) == 1:
            return trackers[0]
        raise ValueError(
            "tracker is required (several trackers exist)" if trackers else "no tracker exists"
        )
    try:
        match = qs.filter(pk=uuid.UUID(value)).first()
        if match is not None:
            return match
    except ValueError:
        pass
    match = qs.filter(name__iexact=value).first() or qs.filter(name__icontains=value).first()
    if match is None:
        raise ValueError(f"unknown tracker: {value}")
    return match


def _create_entry_from_agent(household, user, fields, *, anchor=None):
    """Map the agent's raw ``fields`` to ``trackers.services.add_entry``.

    The tracker comes from ``fields['tracker']`` (name or id); in a conversation
    anchored on a tracker it falls back to the anchor, so "ajoute 82.4" works
    from the tracker's assistant without naming it.
    """
    from .services import add_entry

    raw_tracker = fields.get('tracker') or fields.get('tracker_id')
    if not raw_tracker and anchor and anchor[0] == 'tracker':
        raw_tracker = anchor[1]
    tracker = _resolve_tracker(household.id, raw_tracker)

    value = fields.get('value')
    if value in (None, ''):
        raise ValueError("value is required")

    occurred_at = _parse_datetime(fields.get('occurred_at'))
    return add_entry(
        household,
        user,
        tracker,
        value=str(value).strip().replace(',', '.'),
        occurred_at=occurred_at,
        note=fields.get('note'),
    )


def _update_entry_from_agent(household, user, instance, fields):
    from .services import update_entry

    payload = dict(fields)
    if 'value' in payload and payload['value'] is not None:
        payload['value'] = str(payload['value']).strip().replace(',', '.')
    if 'occurred_at' in payload:
        payload['occurred_at'] = _parse_datetime(payload['occurred_at'])
    return update_entry(household, user, instance, fields=payload)


def _resolve_entry_for_agent(household, raw_id):
    from .models import TrackerEntry

    return (
        TrackerEntry.objects.filter(household_id=household.id, pk=raw_id)
        .select_related('tracker')
        .first()
    )


def _entry_label(entry) -> str:
    from .services import _fmt

    unit = f" {entry.tracker.unit}" if entry.tracker.unit else ''
    return f"{entry.tracker.name} : {_fmt(entry.value)}{unit}"


def _parse_datetime(value):
    """Parse an ISO datetime (or date) string; None passes through (= now)."""
    if value in (None, ''):
        return None
    from django.utils.dateparse import parse_date, parse_datetime
    from django.utils import timezone

    parsed = parse_datetime(str(value))
    if parsed is None:
        as_date = parse_date(str(value))
        if as_date is None:
            raise ValueError(f"invalid datetime: {value}")
        parsed = timezone.datetime(as_date.year, as_date.month, as_date.day)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


# --- list_entities filters ---------------------------------------------------


def _filter_project(qs, value):
    import uuid

    try:
        return qs.filter(project_id=uuid.UUID(value.strip()))
    except ValueError as exc:
        raise ValueError(f"invalid project id: {value}") from exc


def _filter_general(qs, value):
    if value.strip().lower() not in ('true', '1', 'yes'):
        return qs
    return qs.filter(project__isnull=True)


def _describe_tracker(tracker) -> str:
    from .services import _fmt

    archived = ' | archived' if not tracker.is_active else ''
    unit = f" {tracker.unit}" if tracker.unit else ''

    if tracker.last_value is None:
        return f'(no entries){archived}'
    when = f" on {tracker.last_entry_at:%Y-%m-%d}" if tracker.last_entry_at else ''
    return f"{_fmt(tracker.last_value)}{unit}{when}{archived}"
