"""Guard: the bot's own strings are actually translated, not just marked _().

These messages shipped untranslated (empty msgstr in fr/de/es) — the bot
answered in English for every locale but the egg ping. This test fails the day
a bot string regresses to its English source, per locale.
"""
from __future__ import annotations

import pytest
from django.utils import translation
from django.utils.translation import gettext as _

# A representative sample of the bot's own messages (telegram/service.py).
BOT_STRINGS = [
    "Undone.",
    "Nothing to undo.",
    "Fresh start — your next message opens a new conversation.",
    "The assistant is unavailable right now — please try again in a minute.",
    "This Telegram account is not linked to Maisonnée yet. "
    "Open the app settings and tap “Connect Telegram”.",
]


@pytest.mark.parametrize("locale", ["fr", "de", "es"])
@pytest.mark.parametrize("source", BOT_STRINGS)
def test_bot_strings_are_translated(locale, source):
    with translation.override(locale):
        assert _(source) != source, f"{source!r} is untranslated in {locale}"


def test_undo_button_keeps_the_label_placeholder():
    # A broken translation could drop {label} and crash .format() at send time.
    for locale in ("fr", "de", "es"):
        with translation.override(locale):
            rendered = _("↩️ Undo: {label}").format(label="Purger la VMC")
        assert "Purger la VMC" in rendered
