"""The shared way to tell a household that one of its members did something.

Before this helper there were two hand-rolled fan-outs — `stock` and
`households` — and they had already drifted: stock rendered its text **once**,
outside the loop, so a bilingual household got the language of whoever moved the
stock. That is not a cosmetic bug. The text is stored in plain form (write-time
rule, `CLAUDE.md`), so there is no second chance at display time.

The family this serves — "somebody completed a task", "somebody logged an
expense" — is entity-scoped and high-frequency, which is what the three other
guarantees here are about: a per-notification link, a dedup key, and a mute the
user controls.
"""
import pytest
from django.contrib.auth import get_user_model

from accounts.tests.factories import UserFactory
from households.models import Household, HouseholdMember
from notifications.models import MUTABLE_TYPES, Notification
from notifications.service import notify_household, send

User = get_user_model()

# A real, mutable type — the helper is exercised on something that ships.
# `task_completed` / `expense_added` are deliberately NOT declared yet: an
# enum value without an emitter is dead code.
FANOUT = Notification.Type.STOCK_LOW
# Deliberately NOT a real type: `test_deep_links.py` now requires every member of
# `Notification.Type` to declare where it leads, so any real type used here would
# have to be one that ought to be mapped — and this test would then be asking for
# the catalogue to stay incomplete. `weather_alert` played that role until it got
# its `/app/weather` entry, and pinning the fallback to it turned a legitimate fix
# into a red test. What is under test is the *fallback branch* of
# `deep_link_for`, which only an unknown string can reach.
UNMAPPED = "a_type_with_no_landing_page"


@pytest.fixture
def actor(db):
    return UserFactory(display_name="Alice")


@pytest.fixture
def household(db, actor):
    h = Household.objects.create(name="Maison Test")
    HouseholdMember.objects.create(household=h, user=actor, role=HouseholdMember.Role.OWNER)
    return h


@pytest.fixture
def bob(db, household):
    u = UserFactory(display_name="Bob")
    HouseholdMember.objects.create(household=household, user=u)
    return u


def texts(n=1):
    """A text builder that records nothing — the common case."""
    return lambda: (f"title {n}", f"body {n}")


# ---------------------------------------------------------------------------
# Who hears it
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestWhoIsTold:

    def test_every_member_but_the_actor(self, household, actor, bob):
        notify_household(household, FANOUT, actor=actor, text=texts())

        assert list(Notification.objects.values_list("user_id", flat=True)) == [bob.id]

    def test_without_an_actor_everybody_is_told(self, household, actor, bob):
        """A household-wide fact with no author — a stock threshold, a weather alert."""
        notify_household(household, FANOUT, text=texts())

        assert Notification.objects.count() == 2

    def test_another_household_hears_nothing(self, household, actor, bob):
        elsewhere = Household.objects.create(name="Ailleurs")
        HouseholdMember.objects.create(household=elsewhere, user=UserFactory())

        notify_household(household, FANOUT, actor=actor, text=texts())

        assert Notification.objects.count() == 1

    def test_a_household_of_one_tells_nobody(self, household, actor):
        assert notify_household(household, FANOUT, actor=actor, text=texts()) == []

    def test_the_actor_is_recorded_in_the_payload(self, household, actor, bob):
        notify_household(household, FANOUT, actor=actor, text=texts())

        notif = Notification.objects.get()
        assert notif.payload["actor_id"] == str(actor.id)
        assert notif.payload["actor_name"] == "Alice"


# ---------------------------------------------------------------------------
# In which language
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEachRecipientReadsTheirOwnLanguage:
    """`text` is a callable on purpose: a plain string would be rendered once by
    the caller, under whatever locale happens to be active, and that is exactly
    the bug this helper replaces."""

    def test_the_builder_runs_once_per_recipient_under_their_locale(self, household, actor, bob):
        from django.utils import translation

        actor.locale = "fr"
        actor.save(update_fields=["locale"])
        bob.locale = "de"
        bob.save(update_fields=["locale"])
        seen = []

        def build():
            seen.append(translation.get_language())
            return ("t", "b")

        notify_household(household, FANOUT, text=build)

        assert sorted(seen) == ["de", "fr"]

    def test_a_user_without_a_locale_falls_back_to_english(self, household, actor, bob):
        from django.utils import translation

        assert actor.locale is None
        seen = []
        notify_household(
            household, FANOUT, actor=bob,
            text=lambda: (seen.append(translation.get_language()) or "t", "b"),
        )

        assert seen == ["en"]


# ---------------------------------------------------------------------------
# Where it leads
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTheNotificationLeadsSomewhere:
    """A static map keyed by *type* cannot express "the task Bob just finished".
    The whole family is entity-scoped, so the link belongs on the row."""

    def test_the_url_is_stored_on_the_row(self, household, actor, bob):
        notify_household(household, FANOUT, actor=actor, text=texts(), url="/app/stock/42")

        assert Notification.objects.get().url == "/app/stock/42"

    def test_the_push_prefers_the_row_over_the_type_map(self, household, actor, bob, monkeypatch):
        sent = {}
        monkeypatch.setattr(
            "webpush.service.send_web_push",
            lambda user, title, body, **kw: sent.update(kw) or 1,
        )

        notify_household(household, FANOUT, actor=actor, text=texts(), url="/app/stock/42")

        assert sent["url"] == "/app/stock/42"

    def test_without_a_url_the_type_map_still_answers(self, actor, monkeypatch):
        sent = {}
        monkeypatch.setattr(
            "webpush.service.send_web_push",
            lambda user, title, body, **kw: sent.update(kw) or 1,
        )

        send(actor, Notification.Type.HOUSEHOLD_MEMBER_JOINED, title="t")

        assert sent["url"] == "/app/settings"

    def test_an_unmapped_type_lands_on_the_dashboard(self, actor, monkeypatch):
        sent = {}
        monkeypatch.setattr(
            "webpush.service.send_web_push",
            lambda user, title, body, **kw: sent.update(kw) or 1,
        )

        send(actor, UNMAPPED, title="t")

        assert sent["url"] == "/app/dashboard"


# ---------------------------------------------------------------------------
# Saying it once
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestItIsNotSaidTwice:
    """Weather hand-rolled a per-day existence check; stock has none at all and
    re-notifies on every crossing of the threshold."""

    def test_the_same_key_is_only_announced_once(self, household, actor, bob):
        notify_household(household, FANOUT, actor=actor, text=texts(), dedup_key="stock:42:low")
        notify_household(household, FANOUT, actor=actor, text=texts(), dedup_key="stock:42:low")

        assert Notification.objects.count() == 1

    def test_a_different_key_is_a_different_announcement(self, household, actor, bob):
        notify_household(household, FANOUT, actor=actor, text=texts(), dedup_key="stock:42:low")
        notify_household(household, FANOUT, actor=actor, text=texts(), dedup_key="stock:43:low")

        assert Notification.objects.count() == 2

    def test_a_deleted_notification_frees_its_key(self, household, actor, bob):
        """Soft-deleting is the user saying they are done with it — the next
        occurrence of the same fact is news again."""
        notify_household(household, FANOUT, actor=actor, text=texts(), dedup_key="k")
        Notification.objects.update(deleted_at="2026-01-01T00:00:00Z")

        notify_household(household, FANOUT, actor=actor, text=texts(), dedup_key="k")

        assert Notification.objects.filter(deleted_at__isnull=True).count() == 1

    def test_the_key_is_per_recipient(self, household, actor, bob):
        """Bob having already been told must not silence Chloé."""
        chloe = UserFactory(display_name="Chloé")
        HouseholdMember.objects.create(household=household, user=chloe)
        send(bob, FANOUT, title="t", dedup_key="k")

        notify_household(household, FANOUT, actor=actor, text=texts(), dedup_key="k")

        assert Notification.objects.filter(user=chloe).count() == 1
        assert Notification.objects.filter(user=bob).count() == 1


# ---------------------------------------------------------------------------
# What the user can silence — and what they cannot
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTheUserCanSilenceTheChatter:
    """« Untel a coché une tâche » is ~60 a week in a family of four. Without a
    mute the bell becomes noise, and a bell that is noise loses the invitation
    that mattered along with the rest."""

    def test_a_muted_type_does_not_reach_that_user(self, household, actor, bob):
        bob.muted_notification_types = [FANOUT]
        bob.save(update_fields=["muted_notification_types"])

        notify_household(household, FANOUT, actor=actor, text=texts())

        assert not Notification.objects.exists()

    def test_muting_is_personal(self, household, actor, bob):
        chloe = UserFactory(display_name="Chloé")
        HouseholdMember.objects.create(household=household, user=chloe)
        bob.muted_notification_types = [FANOUT]
        bob.save(update_fields=["muted_notification_types"])

        notify_household(household, FANOUT, actor=actor, text=texts())

        assert list(Notification.objects.values_list("user_id", flat=True)) == [chloe.id]

    def test_an_invitation_cannot_be_muted(self, actor):
        """Some notifications are the only way to learn something actionable.
        Letting a checkbox hide them turns a preference into a trap."""
        assert Notification.Type.HOUSEHOLD_INVITATION not in MUTABLE_TYPES

        actor.muted_notification_types = [Notification.Type.HOUSEHOLD_INVITATION]
        actor.save(update_fields=["muted_notification_types"])

        assert send(actor, Notification.Type.HOUSEHOLD_INVITATION, title="t") is not None

    def test_a_muted_send_returns_none_rather_than_raising(self, actor):
        actor.muted_notification_types = [FANOUT]
        actor.save(update_fields=["muted_notification_types"])

        assert send(actor, FANOUT, title="t") is None


# ---------------------------------------------------------------------------
# The settings screen cannot lag behind the catalogue
# ---------------------------------------------------------------------------

class TestTheMuteScreenCoversWhatCanBeMuted:
    """`MUTABLE_TYPES` is what the write path enforces; the screen only renders
    it. Checked from Python because that is the only side holding the full list —
    same reason `test_global_search.py` checks the search palette from here.
    """

    def test_every_mutable_type_has_a_label_in_the_four_catalogues(self):
        import json
        from pathlib import Path

        ui = Path(__file__).resolve().parents[3] / "ui/src/locales"
        for lang in ("en", "fr", "de", "es"):
            catalogue = json.loads((ui / lang / "translation.json").read_text(encoding="utf-8"))
            labels = catalogue.get("notifications", {}).get("type", {})
            missing = set(MUTABLE_TYPES) - set(labels)
            assert not missing, (
                f"{lang}: notifications.type.* is missing {sorted(missing)} — the "
                "settings screen would offer a checkbox labelled with a raw i18n key"
            )


@pytest.mark.django_db
class TestTheMuteEndpointAndTheWritePathAgree:

    def test_the_endpoint_lists_exactly_what_can_be_muted(self, client, actor):
        client.force_login(actor)

        listed = client.get("/api/notifications/mutable-types/").json()["types"]

        assert set(listed) == set(MUTABLE_TYPES)

    def test_muting_something_unmutable_is_refused_not_ignored(self, client, actor):
        client.force_login(actor)

        response = client.patch(
            "/api/accounts/users/me/",
            data={"muted_notification_types": [Notification.Type.HOUSEHOLD_INVITATION]},
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_the_preference_survives_the_round_trip(self, client, actor):
        """The endpoint drops unlisted keys in silence, so a preference the
        screen offers and the API ignores looks exactly like one that resets on
        its own. `recap_disabled_chapters` had been in that state.
        """
        client.force_login(actor)

        client.patch(
            "/api/accounts/users/me/",
            data={"muted_notification_types": [Notification.Type.STOCK_LOW]},
            content_type="application/json",
        )

        actor.refresh_from_db()
        assert actor.muted_notification_types == [Notification.Type.STOCK_LOW]

    def test_every_preference_the_serializer_validates_can_be_written(self):
        """The allow-list and the validators must name the same fields: a
        `validate_x` with no `x` in the list guards something unreachable, and
        that is how a screen ends up saving nothing."""
        from accounts.serializers import UserSerializer

        validated = {
            name[len("validate_"):]
            for name in dir(UserSerializer)
            if name.startswith("validate_") and name != "validate_empty_values"
        }
        unreachable = validated - UserSerializer.SELF_EDITABLE_FIELDS
        assert not unreachable, (
            f"validated but not self-editable: {sorted(unreachable)} — /users/me/ "
            "drops them without a word"
        )
