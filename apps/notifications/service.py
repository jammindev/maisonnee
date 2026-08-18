"""
Notification service — single entry point for creating and managing notifications.
Transport-agnostic: swap polling for WebSocket later by editing only this file.

Two entry points, and the second is the one to reach for:

- ``send(user, ...)`` — one recipient, one notification.
- ``notify_household(household, ..., actor=…, text=…)`` — the whole household
  minus whoever caused it. **Every "a member did something" notification goes
  through this one.** Hand-rolling the loop is how the two pre-existing fan-outs
  drifted apart, one of them shipping the wrong language to half a household.
"""
import logging

from django.utils import timezone, translation

from .models import MUTABLE_TYPES, Notification

logger = logging.getLogger(__name__)

# HTMX event name broadcast on the body to refresh the bell widget.
# Used in both Django views (HX-Trigger header) and React (dispatchEvent).
BELL_REFRESH_EVENT = "bellRefresh"

# Fallback landing page per notification type, for the notifications that lead
# to a *place* rather than to a *thing*. Anything entity-scoped passes its own
# ``url`` instead — see ``Notification.url``. The service worker falls back to
# /app/dashboard for whatever neither provides.
#
# **Every type in ``Notification.Type`` has an entry here**, and a test enforces
# it (``test_deep_links.py``). An incomplete catalogue is invisible: the fallback
# is always a valid page, so a missing type simply lands on the dashboard and
# nobody can tell it was never declared. ``weather_alert`` had already lived
# outside ``MUTABLE_TYPES`` and outside the admin display for the same reason.
_DEEP_LINKS = {
    Notification.Type.STOCK_LOW: "/app/stock",
    Notification.Type.STOCK_OUT: "/app/stock",
    Notification.Type.HOUSEHOLD_INVITATION: "/app/dashboard",
    Notification.Type.HOUSEHOLD_MEMBER_JOINED: "/app/settings",
    Notification.Type.WEATHER_ALERT: "/app/weather",
    Notification.Type.CHICKEN_CHORE_DUE: "/app/chickens",
    Notification.Type.TASK_CREATED: "/app/tasks",
    Notification.Type.NOTE_CREATED: "/app/interactions",
    Notification.Type.HUNT_SUGGESTION: "/app/games",
}

DEFAULT_DEEP_LINK = "/app/dashboard"


def send(
    user,
    notification_type: str,
    title: str,
    body: str = "",
    payload: dict | None = None,
    url: str = "",
    dedup_key: str = "",
) -> Notification | None:
    """
    Create and persist a notification for a user.
    All callers (households, projects, etc.) go through here.

    Returns ``None`` — not an error — when the user has silenced this type, or
    when ``dedup_key`` names something they have already been told and not yet
    dismissed. Callers that count notifications must tolerate both.

    Also mirrors the notification to Web Push (best-effort): a user with a push
    subscription gets it on their device even when the SPA is closed. The push
    carries the current unread count so the PWA can set its app-icon badge.
    """
    if is_muted(user, notification_type):
        return None
    if dedup_key and _already_told(user, notification_type, dedup_key):
        return None

    notif = Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        body=body,
        payload=payload or {},
        url=url,
        dedup_key=dedup_key,
    )
    _mirror_to_web_push(notif)
    # Future: channel_layer.group_send(f"user_{user.id}", {...}) here for WS
    return notif


def notify_household(
    household,
    notification_type: str,
    *,
    text,
    actor=None,
    url: str = "",
    payload: dict | None = None,
    dedup_key: str = "",
) -> list[Notification]:
    """Tell a household's members about something. Returns what was created.

    ``actor`` is the member who caused it: they are **excluded** from the
    recipients — nobody needs telling about their own action — and recorded in
    the payload so the text can name them. Pass ``None`` for a fact with no
    author (a stock threshold, a weather alert): then everybody is told.

    ``text`` is a **callable** returning ``(title, body)``, not a pair of
    strings, and that is the whole point of this helper. It is invoked once per
    recipient inside ``translation.override(their locale)``. A household mixes
    languages, and the text is stored in plain form (write-time rule,
    ``CLAUDE.md``) — so a caller that renders it once, up front, silently posts
    everyone the language of whoever happened to act. That bug shipped in
    ``stock`` and lived there unnoticed.
    """
    from households.models import HouseholdMember

    recipients = HouseholdMember.objects.filter(household=household).select_related("user")
    if actor is not None:
        recipients = recipients.exclude(user=actor)

    full_payload = dict(payload or {})
    if actor is not None:
        full_payload.setdefault("actor_id", str(actor.id))
        # `full_name` porte déjà le repli sur l'email. Ce champ nomme l'auteur
        # de *toutes* les notifications du foyer : une règle recomposée ici se
        # voit partout à la fois (#546).
        full_payload.setdefault("actor_name", actor.full_name)

    created = []
    for member in recipients:
        with translation.override(getattr(member.user, "locale", None) or "en"):
            title, body = text()
        notif = send(
            member.user,
            notification_type,
            title=str(title),
            body=str(body),
            payload=full_payload,
            url=url,
            dedup_key=dedup_key,
        )
        if notif is not None:
            created.append(notif)
    return created


def is_muted(user, notification_type: str) -> bool:
    """Whether this user silenced this type — only ever true for a mutable one.

    The guard is here rather than at the settings screen on purpose: a type can
    leave ``MUTABLE_TYPES`` (it turned out to matter), and a preference row left
    over from when it was mutable must stop applying immediately, not wait for
    the user to reopen a screen they may never reopen.
    """
    if notification_type not in MUTABLE_TYPES:
        return False
    return notification_type in (getattr(user, "muted_notification_types", None) or [])


def _already_told(user, notification_type: str, dedup_key: str) -> bool:
    """A live notification for the same fact already sits in their bell.

    Scoped to ``deleted_at__isnull=True``: dismissing is the user saying they
    are done with it, so the next occurrence of the same fact is news again.
    """
    return Notification.objects.filter(
        user=user,
        type=notification_type,
        dedup_key=dedup_key,
        deleted_at__isnull=True,
    ).exists()


def deep_link_for(notif: Notification) -> str:
    """Where this notification leads: its own url, else its type's, else home."""
    return notif.url or _DEEP_LINKS.get(notif.type, DEFAULT_DEEP_LINK)


def _mirror_to_web_push(notif: Notification) -> None:
    """Fire the notification to the user's push subscriptions. Never raises."""
    try:
        from webpush.service import send_web_push

        unread = Notification.objects.filter(
            user=notif.user, is_read=False, deleted_at__isnull=True
        ).count()
        send_web_push(
            notif.user,
            notif.title,
            notif.body,
            url=deep_link_for(notif),
            tag=notif.type,
            data={"unreadCount": unread},
        )
    except Exception:  # noqa: BLE001 — push must never break notification creation
        logger.exception("web push mirror failed for notification %s", notif.id)


# Keep legacy alias so existing callers don't break
create_notification = send


def mark_read_by_payload(user, notification_type: str, **payload_filters) -> int:
    """
    Mark notifications as read by payload field values.
    Returns the number of notifications updated.

    Example:
        mark_read_by_payload(
            user, "household_invitation", invitation_id=str(invitation.id)
        )
    """
    filters = {f"payload__{k}": v for k, v in payload_filters.items()}
    return Notification.objects.filter(
        user=user,
        type=notification_type,
        is_read=False,
        deleted_at__isnull=True,
        **filters,
    ).update(is_read=True, read_at=timezone.now())


def retract_by_payload(notification_type: str, **payload_filters) -> int:
    """Retirer de toutes les cloches ce qui annonçait une chose disparue.

    Le pendant de ``notify_household`` à la suppression, et **non scopé à un
    utilisateur** pour cette raison précise : l'annonce a été fan-outée à tout le
    foyer, la retirer chez son seul auteur — qui ne l'a justement jamais reçue —
    ne retirerait rien.

    Existe parce que ``url`` est une promesse d'adresse : une notification qui
    survit à son sujet mène à un écran mort, et le lecteur ne peut pas savoir si
    c'est l'app ou lui qui se trompe. À appeler depuis **tous** les chemins de
    suppression d'un objet notifié, pas seulement celui qu'on a sous la main.

    Soft-delete (``deleted_at``), comme quand l'utilisateur écarte une
    notification : rien ne s'efface, et le compteur de non-lues suit.
    """
    filters = {f"payload__{k}": v for k, v in payload_filters.items()}
    return Notification.objects.filter(
        type=notification_type,
        deleted_at__isnull=True,
        **filters,
    ).update(deleted_at=timezone.now())
