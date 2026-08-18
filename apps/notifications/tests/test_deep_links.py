"""Où mène une notification — une seule définition, servie à tout le monde.

`deep_link_for` résout `notif.url` → `_DEEP_LINKS[type]` → `/app/dashboard`.
Elle n'était appelée que par le miroir Web Push, alors que l'API sérialisait la
**colonne brute** : la même notification menait donc à `/app/weather` depuis une
push et **nulle part** depuis la cloche. Deux voix pour un même fait, et c'est
l'utilisateur qui arbitre.
"""
import pytest
from rest_framework.test import APIClient

from notifications.models import Notification
from notifications.service import _DEEP_LINKS, deep_link_for, send


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email="reader@test.com", password="pass")


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _first(payload):
    rows = payload if isinstance(payload, list) else payload["results"]
    return rows[0]


class TestTheBellLeadsWhereThePushLeads:
    """Le lien servi à l'écran est celui que la push utilise, sans exception."""

    def test_a_notification_without_url_still_leads_somewhere(self, user, auth_client):
        notif = send(
            user,
            Notification.Type.WEATHER_ALERT,
            title="Weather alert",
            body="Frost tonight",
        )
        assert notif.url == "", "le champ brut reste vide : c'est l'appelant qui n'a rien passé"

        row = _first(auth_client.get("/api/notifications/").json())

        assert row["url"] == deep_link_for(notif)
        assert row["url"] != ""

    def test_an_explicit_url_wins_over_its_type_default(self, user, auth_client):
        send(
            user,
            Notification.Type.STOCK_LOW,
            title="Low stock: coffee",
            url="/app/stock/abc",
        )

        row = _first(auth_client.get("/api/notifications/").json())

        assert row["url"] == "/app/stock/abc"

    @pytest.mark.parametrize("notification_type", [t for t, _ in Notification.Type.choices])
    def test_every_type_leads_to_the_same_place_in_both_channels(
        self, user, auth_client, notification_type
    ):
        notif = send(user, notification_type, title="…")
        assert notif is not None

        row = _first(auth_client.get("/api/notifications/").json())

        assert row["url"] == deep_link_for(notif)


class TestTheDeepLinkCatalogueCoversEveryType:
    """Ajouter un type, c'est déclarer où il mène.

    `weather_alert` avait déjà vécu hors de `MUTABLE_TYPES` et hors de
    l'affichage admin ; il manquait **aussi** ici, donc une alerte météo tombait
    sur `/app/dashboard` faute de mieux. Un catalogue incomplet ne se voit pas :
    le repli est toujours une page valide.
    """

    def test_no_type_falls_back_to_the_generic_landing_page(self):
        missing = [t for t, _ in Notification.Type.choices if t not in _DEEP_LINKS]

        assert missing == [], (
            f"types sans destination déclarée dans _DEEP_LINKS : {missing}. "
            "Un repli sur /app/dashboard fait annoncer sans mener."
        )
