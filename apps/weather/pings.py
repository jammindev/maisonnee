"""
Proactive weather-alert ping (parcours 17, Lot 4).

Registered as ``PingSpec('weather_alert')`` from ``apps.py::ready()``. Reuses the
existing ping scheduler (``send_scheduled_pings`` tick, ``PingLog`` idempotence,
per-user opt-in via ``PingPreference``) — no new cron.

``build_message`` evaluates the shared alert evaluator (``weather.alerts``); when
an alert fires it also drops an in-app notification (the "bell" channel) before
returning the Telegram text. Both are deduped to once per day: the ping by
``PingLog``, the notification by a same-day existence check (so a Telegram send
retry doesn't create a second bell entry).
"""
from __future__ import annotations

from datetime import date

from .alerts import evaluate_weather_alerts, render_alert_message

# Notification.type discriminator for the in-app bell. Declared in the enum like
# every other type: `choices` is not enforced by the database and `.create()`
# skips `full_clean`, so a literal persisted just fine — and left one type
# invisible to the admin display, to `MUTABLE_TYPES`, and to anyone reading the
# catalogue in one place.
NOTIFICATION_TYPE = "weather_alert"


def build_weather_alert_ping(household, user, *, today: date) -> str | None:
    """Return the localized alert message, or ``None`` when nothing is at risk.

    Side effect on a firing alert: create an in-app notification for ``user``
    (idempotent per day). Called inside the user's language context, so the
    evaluator's rendered text is localized.
    """
    alerts = evaluate_weather_alerts(household)
    message = render_alert_message(alerts)
    if message is None:
        return None

    _notify_bell(household, user, today, alerts, message)
    return message


def _notify_bell(household, user, today: date, alerts: list[dict], message: str) -> None:
    from django.utils.translation import gettext as _

    from notifications.service import send

    # Idempotence keyed on the household-local day (not created_at, whose server
    # timezone could disagree with `today` around midnight). The check itself is
    # the service's — this used to be a hand-rolled `payload__day` existence
    # query, one of three different ways the codebase avoided saying a thing
    # twice.
    day = today.isoformat()
    send(
        user,
        NOTIFICATION_TYPE,
        title=_("Weather alert"),
        body=message,
        # La seule notification du catalogue qui ne disait pas où elle mène : le
        # repli par type la rattrape désormais, mais un émetteur déclare sa
        # destination — c'est lui qui sait de quoi il parle.
        url="/app/weather",
        dedup_key=f"weather:{day}",
        payload={
            "household_id": str(household.id),
            "day": day,
            "kinds": sorted({a["kind"] for a in alerts}),
        },
    )
