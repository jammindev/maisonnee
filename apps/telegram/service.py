"""
Transport layer: route a Telegram update to the right handler and reply.

No business logic lives here — linking is `linking.py`, questions go through
`agent.service.ask`, exactly the entry point the web API uses. This module
only authenticates the sender (`TelegramAccount`), localizes the bot's own
strings and shuttles text back and forth.

Questions run in a daemon thread: Telegram retries any webhook that doesn't
answer within a few seconds, while `ask()` can take 10–30s with tool calls —
so the webhook returns immediately and the answer arrives as a bot message.
"""
from __future__ import annotations

import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import close_old_connections
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .client import get_client
from .linking import consume_link_token, link_account
from .models import TelegramAccount
from .rendering import parse_undo_callback, render_answer, undo_keyboard

logger = logging.getLogger(__name__)

# Telegram retries any non-200 delivery, so updates can arrive twice — remember
# recently-seen ids (best effort, per process) and skip replays.
UPDATE_DEDUP_TTL_SECONDS = 15 * 60

SUPPORTED_LANGUAGES = {"en", "fr", "de", "es"}

# Anchor pair tagging a conversation as belonging to the Telegram channel of
# (household, user). It is a channel discriminator, NOT a household entity, so
# it is never passed to `ask()` as context_entity. Several channel conversations
# can coexist per user — one per session (see `resolve_channel_conversation`).
CHANNEL_ENTITY_TYPE = "channel"
CHANNEL_OBJECT_ID = "telegram"

# A channel conversation is a "session": consecutive turns close in time. Past
# this idle gap — or across a calendar-day boundary — the next turn opens a
# fresh conversation instead of dragging stale context (e.g. yesterday's
# "j'ai noté 2 œufs aujourd'hui") into today's history.
SESSION_MAX_IDLE = timedelta(hours=6)


def _channel_conversations(household, user):
    """Every channel conversation of (household, user), newest-active first."""
    from agent.models import AgentConversation

    return AgentConversation.objects.filter(
        household=household,
        created_by=user,
        context_entity_type=CHANNEL_ENTITY_TYPE,
        context_object_id=CHANNEL_OBJECT_ID,
    )


def _session_expired(conversation, now) -> bool:
    """True when `conversation`'s last activity is a different day or too old."""
    ref = conversation.last_message_at or conversation.created_at
    local_now, local_ref = timezone.localtime(now), timezone.localtime(ref)
    if local_now.date() != local_ref.date():
        return True
    return (now - ref) > SESSION_MAX_IDLE


def resolve_channel_conversation(household, user, *, force_new=False):
    """The channel conversation the next Telegram turn belongs to.

    Reuses the current session's conversation while it stays fresh (same day,
    within `SESSION_MAX_IDLE`); otherwise opens a NEW one so each session keeps
    a clean, self-contained history. Both directions go through here — inbound
    replies and outbound pings — so a session groups the ping and its answer.

    `force_new` (used by `/reset`) forces a fresh conversation WITHOUT deleting
    anything; an already-empty latest one is reused so repeated resets don't pile
    up blank rows.
    """
    from agent.models import AgentConversation

    latest = _channel_conversations(household, user).first()  # recency-ordered
    if latest is None:
        return AgentConversation.objects.create(
            household=household,
            created_by=user,
            context_entity_type=CHANNEL_ENTITY_TYPE,
            context_object_id=CHANNEL_OBJECT_ID,
        )
    has_messages = latest.messages.exists()
    if force_new:
        needs_new = has_messages
    else:
        needs_new = has_messages and _session_expired(latest, timezone.now())
    if needs_new:
        return AgentConversation.objects.create(
            household=household,
            created_by=user,
            context_entity_type=CHANNEL_ENTITY_TYPE,
            context_object_id=CHANNEL_OBJECT_ID,
        )
    return latest

# SOURCE OF TRUTH for the bot's command menu (the `/` autocomplete in Telegram).
# `telegram_set_commands` pushes this list to Telegram (setMyCommands) at every
# deploy, so it is NOT auto-derived from the handlers below — if you add or
# rename a slash command in `_handle_message`, add/rename it HERE too, otherwise
# the menu drifts from what the bot actually accepts. `/start` is intentionally
# absent: Telegram surfaces it as the built-in "Start" button.
# Descriptions use gettext_lazy: they must resolve at push time (under
# translation.override per language), not at import time.
BOT_COMMANDS: tuple[tuple[str, object], ...] = (
    ("help", gettext_lazy("Show what I can do")),
    ("reset", gettext_lazy("Start a fresh conversation")),
    ("stop", gettext_lazy("Turn off proactive messages")),
)


def handle_update(update: dict) -> None:
    """Entry point for the webhook. Must never raise — Telegram would retry."""
    try:
        update_id = update.get("update_id")
        if update_id is not None and not cache.add(
            f"telegram:update:{update_id}", 1, UPDATE_DEDUP_TTL_SECONDS
        ):
            return
        message = update.get("message")
        if isinstance(message, dict):
            _handle_message(message)
            return
        callback_query = update.get("callback_query")
        if isinstance(callback_query, dict):
            _handle_callback_query(callback_query)
    except Exception:  # noqa: BLE001 — a bad update must not 500 the webhook
        logger.exception("telegram.handle_update: unexpected error")


def _handle_message(message: dict) -> None:
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()
    if chat_id is None or not text:
        return

    if text == "/start" or text.startswith("/start "):
        _handle_start(chat_id, message, text)
        return

    account = (
        TelegramAccount.objects.filter(chat_id=chat_id).select_related("user").first()
    )
    if account is None:
        _reply_not_linked(chat_id, message)
        return

    with translation.override(_account_language(account)):
        if text.startswith("/help"):
            get_client().send_message(chat_id, _help_text())
            return
        if text.startswith("/reset"):
            _handle_reset(account, chat_id)
            return
        if text.lower() in ("stop", "/stop"):
            _handle_stop(account, chat_id)
            return
        _handle_question(account, chat_id, text)


def _handle_start(chat_id: int, message: dict, text: str) -> None:
    """`/start <token>` links the account; a bare `/start` explains the bot."""
    # NB: no throwaway `_` here — it would shadow the gettext alias.
    token = text.partition(" ")[2].strip()
    client = get_client()

    if not token:
        account = TelegramAccount.objects.filter(chat_id=chat_id).select_related("user").first()
        if account is None:
            _reply_not_linked(chat_id, message)
        else:
            with translation.override(_account_language(account)):
                client.send_message(chat_id, _help_text())
        return

    user = consume_link_token(token)
    if user is None:
        with translation.override(_sender_language(message)):
            client.send_message(
                chat_id,
                _("This link is invalid or has expired. Generate a new one from the app settings."),
            )
        return

    account = link_account(user, chat_id, username=(message.get("from") or {}).get("username", ""))
    with translation.override(_account_language(account)):
        client.send_message(
            chat_id,
            _("✅ Your Telegram account is linked. Ask me anything about your home!"),
        )


def _handle_question(account: TelegramAccount, chat_id: int, text: str) -> None:
    """A free-text message from a linked user → the agent, off-thread."""
    if not _cooldown_ok(chat_id):
        get_client().send_message(
            chat_id,
            _("One question at a time 🙂 — give me a few seconds and try again."),
        )
        return
    _spawn(_process_question, account, chat_id, text)


def _handle_reset(account: TelegramAccount, chat_id: int) -> None:
    """`/reset` — open a fresh conversation; the next message starts a new thread.

    Non-destructive: the previous conversation is kept (still visible in the web
    history), we merely stop threading into it. A brand-new empty conversation
    becomes the active one, so the next turn lands in a clean session.
    """
    household = _resolve_household(account.user)
    if household is not None:
        resolve_channel_conversation(household, account.user, force_new=True)
    get_client().send_message(
        chat_id, _("Fresh start — your next message opens a new conversation.")
    )


def _handle_stop(account: TelegramAccount, chat_id: int) -> None:
    """A bare "stop" (or `/stop`) — the universal opt-out of proactive pings.

    Disables every ping preference of the user across all their households: a
    "stop" texted to the bot means "leave me alone", not "leave me alone in
    this household". Re-enabling is per ping, from the app settings.
    """
    from pings.models import PingPreference

    prefs = PingPreference.objects.filter(user=account.user, enabled=True)
    count = 0
    for pref in prefs:
        pref.enabled = False
        pref.updated_by = account.user
        pref.save(update_fields=["enabled", "updated_by", "updated_at"])
        count += 1
    if count:
        get_client().send_message(
            chat_id,
            _(
                "🔕 Done — I won't message you first anymore. "
                "You can re-enable proactive messages anytime in the app settings."
            ),
        )
    else:
        get_client().send_message(
            chat_id, _("You have no proactive messages enabled — nothing to stop.")
        )


def _process_question(account: TelegramAccount, chat_id: int, text: str) -> None:
    """Thread body: resolve household/conversation, ask, persist, reply."""
    from agent import service as agent_service
    from agent.conversations import ask_inputs, persist_turns
    from agent.llm import LLMError, LLMTimeoutError

    client = get_client()
    try:
        with translation.override(_account_language(account)):
            household = _resolve_household(account.user)
            if household is None:
                client.send_message(
                    chat_id, _("You are not a member of any household yet.")
                )
                return
            client.send_chat_action(chat_id, "typing")
            conversation = resolve_channel_conversation(household, account.user)
            # The channel anchor is a discriminator, not a household entity —
            # history flows, context_entity deliberately does not.
            history, _anchor = ask_inputs(conversation)
            try:
                result = agent_service.ask(
                    text, household, user=account.user, history=history
                )
            except (LLMTimeoutError, LLMError) as exc:
                logger.warning("telegram.ask failed: %s", exc)
                client.send_message(
                    chat_id,
                    _("The assistant is unavailable right now — please try again in a minute."),
                )
                return
            persist_turns(conversation, text, account.user, result)
            _send_answer(client, chat_id, result)
    except Exception:  # noqa: BLE001 — a thread has nobody to re-raise to
        logger.exception("telegram.process_question: unexpected error")
        with translation.override(_account_language(account)):
            client.send_message(
                chat_id, _("Something went wrong on my side — please try again.")
            )


def _send_answer(client, chat_id: int, result) -> None:
    chunks = render_answer(result, settings.FRONTEND_URL)
    if not chunks:
        return
    # The undo keyboard rides on the LAST chunk so it sits under the whole
    # answer. Buttons are localized here (inside the active translation).
    keyboard = undo_keyboard(
        result.metadata.get("created_entities"),
        lambda entity: _("↩️ Undo: {label}").format(label=entity.get("label") or ""),
    )
    for chunk in chunks[:-1]:
        client.send_message(chat_id, chunk)
    client.send_message(chat_id, chunks[-1], reply_markup=keyboard)


def _handle_callback_query(callback_query: dict) -> None:
    """An inline-button tap — currently only the "Undo" of a created entity."""
    from agent import writables

    query_id = callback_query.get("id")
    message = callback_query.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    from_id = (callback_query.get("from") or {}).get("id")
    client = get_client()

    # Trust the linked account, never the callback payload's own ids: the button
    # is only actionable by the account that owns this chat.
    account = (
        TelegramAccount.objects.filter(chat_id=chat_id).select_related("user").first()
        if chat_id is not None
        else None
    )
    if account is None or account.chat_id != from_id:
        if query_id:
            client.answer_callback_query(query_id)
        return

    parsed = parse_undo_callback(callback_query.get("data", ""))
    with translation.override(_account_language(account)):
        if parsed is None:
            if query_id:
                client.answer_callback_query(query_id)
            return
        entity_type, object_id = parsed
        household = _resolve_household(account.user)
        try:
            if household is None:
                raise LookupError("no household")
            writables.delete_created(entity_type, household, account.user, object_id)
        except LookupError:
            # Already gone (double-tap) or not undoable — nothing to do, but the
            # button has served its purpose so drop it and acknowledge.
            if query_id:
                client.answer_callback_query(query_id, _("Nothing to undo."))
            if chat_id is not None and message_id is not None:
                client.edit_message_reply_markup(chat_id, message_id)
            return
        except Exception:  # noqa: BLE001
            logger.exception("telegram.undo failed")
            if query_id:
                client.answer_callback_query(query_id, _("Couldn't undo — try from the app."))
            return
        if query_id:
            client.answer_callback_query(query_id, _("Undone."))
        if chat_id is not None and message_id is not None:
            client.edit_message_reply_markup(chat_id, message_id)


def _cooldown_ok(chat_id: int) -> bool:
    seconds = settings.TELEGRAM_COOLDOWN_SECONDS
    if seconds <= 0:
        return True
    return bool(cache.add(f"telegram:cooldown:{chat_id}", 1, seconds))


def _spawn(target, *args) -> threading.Thread:
    """Run ``target`` in a daemon thread. Patched to run inline in tests.

    The connection hygiene lives here, not in the targets: each thread gets its
    own DB connections, closed on the way out so they don't leak one per
    question.
    """

    def _runner():
        close_old_connections()
        try:
            target(*args)
        finally:
            close_old_connections()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    return thread


def _reply_not_linked(chat_id: int, message: dict) -> None:
    # Deliberately the same fixed reply for every unlinked chat: no household
    # data, no hint about which accounts exist.
    with translation.override(_sender_language(message)):
        get_client().send_message(
            chat_id,
            _(
                "This Telegram account is not linked to Maisonnée yet. "
                "Open the app settings and tap “Connect Telegram”."
            ),
        )


def _help_text() -> str:
    return _(
        "Ask me anything about your home — expenses, tasks, equipment, notes…\n"
        "/reset starts a fresh conversation.\n"
        "Reply “stop” to turn off proactive messages.\n"
        "/help shows this message."
    )


def _account_language(account: TelegramAccount) -> str:
    user = account.user
    if user.locale:
        return user.locale
    household = _resolve_household(user)
    if household is not None:
        return household.preferred_language
    return "en"


def _sender_language(message: dict) -> str:
    """Best-effort language for chats we don't know: Telegram's own hint."""
    code = ((message.get("from") or {}).get("language_code") or "")[:2].lower()
    return code if code in SUPPORTED_LANGUAGES else "en"


def _resolve_household(user):
    """Active household, falling back to the first membership — same semantics
    as the web `ActiveHouseholdMiddleware`."""
    if user.active_household_id:
        return user.active_household
    from households.models import HouseholdMember

    member = (
        HouseholdMember.objects.filter(user=user).select_related("household").first()
    )
    return member.household if member else None
