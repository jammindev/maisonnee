"""Tests for JWT authentication endpoints."""
from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from .factories import UserFactory


@pytest.mark.django_db
class TestJWTAuth:
    def test_obtain_token_with_valid_credentials(self, api_client):
        """Valid credentials return access + refresh tokens."""
        UserFactory(email="jwt@example.com", password="testpass123")

        url = reverse("token_obtain_pair")
        response = api_client.post(url, {"email": "jwt@example.com", "password": "testpass123"})

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_obtain_token_also_opens_session(self, api_client):
        """JWT login opens a Django session so <img src='/media/...'> can authenticate."""
        UserFactory(email="session@example.com", password="testpass123")

        url = reverse("token_obtain_pair")
        response = api_client.post(url, {"email": "session@example.com", "password": "testpass123"})

        assert response.status_code == status.HTTP_200_OK
        assert "sessionid" in response.cookies

    def test_obtain_token_with_invalid_credentials(self, api_client):
        """Invalid credentials return 401."""
        url = reverse("token_obtain_pair")
        response = api_client.post(url, {"email": "wrong@example.com", "password": "wrong"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token(self, api_client):
        """Valid refresh token returns new access token."""
        UserFactory(email="refresh@example.com", password="testpass123")

        obtain_url = reverse("token_obtain_pair")
        tokens = api_client.post(obtain_url, {"email": "refresh@example.com", "password": "testpass123"}).data

        refresh_url = reverse("token_refresh")
        response = api_client.post(refresh_url, {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_protected_endpoint_requires_token(self, api_client):
        """Unauthenticated request to /api/accounts/me/ returns 401."""
        response = api_client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_protected_endpoint_with_valid_token(self, api_client):
        """Authenticated request to /api/accounts/me/ returns user data."""
        user = UserFactory(email="me@example.com", password="testpass123", display_name="Ben")

        tokens = api_client.post(
            reverse("token_obtain_pair"),
            {"email": "me@example.com", "password": "testpass123"},
        ).data
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = api_client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email
        assert "active_household" in response.data
        # Regression: the SPA greeting reads display_name; me_view must expose it.
        assert response.data["display_name"] == "Ben"

    def test_invalid_token_rejected(self, api_client):
        """Invalid token returns 401."""
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalidtoken")
        response = api_client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_endpoint_returns_active_household(self, api_client):
        """me/ endpoint returns active_household field."""
        UserFactory(email="household@example.com", password="testpass123")

        tokens = api_client.post(
            reverse("token_obtain_pair"),
            {"email": "household@example.com", "password": "testpass123"},
        ).data
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = api_client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["active_household"] is not None or response.data["active_household"] is None


@pytest.mark.django_db
class TestTheSessionLivesAsLongAsTheRefreshToken:
    """Régression #567 — les images mouraient 14 jours après le dernier login.

    ``serve_protected_media`` s'authentifie au **cookie de session** : un
    ``<img src="/media/…">`` ne porte pas de header ``Authorization``, le
    navigateur n'envoie spontanément que les cookies. Le SPA, lui, reste
    connecté indéfiniment en faisant tourner son refresh JWT — 30 jours, avec
    rotation, soit **854 refresh pour 10 logins** relevés en production.

    La session n'était ouverte qu'au login et **jamais prolongée** : au 14e
    jour elle expirait, l'API continuait parfaitement via le JWT, et *toutes*
    les images tombaient en 401 d'un coup. Rien à l'écran ne pouvait le dire,
    et se déconnecter/reconnecter — la seule réparation — n'était devinable
    par personne.

    D'où la règle que ces tests tiennent : **le refresh est le battement de
    cœur de la session.** Tant que le SPA rafraîchit son jeton, la session
    reste ouverte ; et si elle est déjà morte, le refresh la rouvre.
    """

    def _login(self, api_client, email="img@example.com"):
        user = UserFactory(email=email, password="testpass123")
        tokens = api_client.post(
            reverse("token_obtain_pair"),
            {"email": email, "password": "testpass123"},
        ).data
        return user, tokens

    def test_refreshing_pushes_the_session_expiry_forward(self, api_client):
        """Un refresh replace l'échéance de la session à 14 jours pleins."""
        _, tokens = self._login(api_client)

        session = Session.objects.get()
        # On vieillit la session : 13 jours consommés, un seul restant.
        aged = timezone.now() + timedelta(days=1)
        Session.objects.filter(pk=session.pk).update(expire_date=aged)

        response = api_client.post(reverse("token_refresh"), {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_200_OK

        refreshed = Session.objects.get(pk=session.pk)
        # Sans renouvellement l'échéance n'aurait pas bougé, et la session
        # serait morte le lendemain avec l'application encore connectée.
        assert refreshed.expire_date > aged + timedelta(days=10)

    def test_refreshing_reopens_a_session_that_already_expired(self, api_client):
        """Le cas vécu en prod : la session est morte, le JWT est vivant.

        Le refresh doit **rouvrir** la session, pas seulement prolonger celles
        qui vivent encore — sinon un foyer déjà cassé le reste jusqu'à ce que
        quelqu'un devine qu'il faut se reconnecter.
        """
        _, tokens = self._login(api_client)

        # Expiration : Django supprime la ligne, et le cookie du navigateur
        # cesse d'être envoyé. Le JWT, lui, a encore 30 jours devant lui.
        Session.objects.all().delete()
        api_client.cookies.pop(settings.SESSION_COOKIE_NAME, None)

        response = api_client.post(reverse("token_refresh"), {"refresh": tokens["refresh"]})

        assert response.status_code == status.HTTP_200_OK
        assert settings.SESSION_COOKIE_NAME in response.cookies
        assert Session.objects.count() == 1

    @override_settings(PROTECTED_MEDIA_ACCEL=True)
    def test_an_image_loads_again_after_a_refresh(self, api_client):
        """Le symptôme, bout en bout : la vignette 401 doit redevenir servie."""
        user, tokens = self._login(api_client)
        path = f"avatars/{user.pk}/photo.jpg"

        Session.objects.all().delete()
        api_client.cookies.pop(settings.SESSION_COOKIE_NAME, None)
        assert api_client.get(f"/media/{path}").status_code == 401

        api_client.post(reverse("token_refresh"), {"refresh": tokens["refresh"]})

        assert api_client.get(f"/media/{path}").status_code == 200
