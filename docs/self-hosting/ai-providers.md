# Optional services

Maisonnée runs without a single API key. Nothing crashes, nothing hangs, and no
screen is left blank — but six capabilities stay switched off until you give the
instance what they need.

This page is the reference behind every "not available on this instance" message
in the app. Each section below is one capability: what it does, what it costs,
what the app does **without** it, and the exact variables to set.

## How keys are configured

**Keys are per instance, never per household.** They live in the `.env` file
next to your `docker-compose.yml` — that file *is* the bring-your-own-key
surface. There is no key field anywhere in the interface, and that is
deliberate: which provider answers a question is a deployment decision, not a
per-user one.

After editing `.env`:

```bash
docker compose up -d
```

The app reads the new values at startup. You can confirm what the instance
believes it can do at `GET /api/capabilities/`, which is also what the interface
reads before promising anything.

**Every capability below is optional.** Skipping all of them leaves a complete
household app — documents, money, tasks, budgets, the monthly recap. What you
lose is the assistant, semantic search, warmer recap wording, outgoing email,
push notifications, and Telegram.

---

## Assistant (Anthropic)

The conversational assistant: ask a question in plain language, get an answer
grounded in your household's own documents, expenses and tasks, with citations
back to the source. It also powers OCR on uploaded documents, and the optional
riddle-writing help when you compose a treasure hunt.

**Without it.** The Assistant tab says it needs a key and links here. Every other
screen is untouched — and, importantly, the search box at the top still works
(see the next section: keyword search needs no key at all). Treasure hunts work
exactly the same; you write the riddles yourself, and the "Suggest riddles"
button is simply not there.

**Get a key.** Create one at [console.anthropic.com](https://console.anthropic.com/)
→ *API keys*. It starts with `sk-ant-`.

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Optional, with sensible defaults already set:

```bash
LLM_PROVIDER=anthropic                       # the only provider implemented today
LLM_TEXT_MODEL=claude-haiku-4-5-20251001     # chat and recap wording
LLM_VISION_MODEL=claude-haiku-4-5-20251001   # OCR on document uploads
```

**Cost.** Claude Haiku 4.5 is billed per million tokens — $1.00 in, $5.00 out at
the time of writing ([current pricing](https://claude.com/pricing)). A household
asking a few questions a day and uploading a handful of documents a week lands in
the low single digits of dollars per month. The app records every call in its
own usage log (`/app/admin/ai-usage`), so you can watch the real number rather
than trust this estimate.

---

## Semantic search (embeddings)

The search box has two stages. The first is **keyword search** — a few indexed
SQL queries, answered in milliseconds, and it needs no key whatsoever. The second
stage finds what the words missed: "the paper about the boiler" matching a PDF
titled *Chaudière — contrat d'entretien*.

**Without it.** The first stage still answers. You simply never see the extra
group of results the second stage would have added. Nothing is slower, nothing
errors — the second stage returns an empty list and the interface says so rather
than pretending it searched everything.

**Two settings, and you need both.** The key alone is not enough:

```bash
VOYAGE_API_KEY=pa-...
AGENT_HYBRID_RETRIEVAL_ENABLED=True
```

Get a key at [dash.voyageai.com](https://dash.voyageai.com/). Embeddings are
billed per million tokens; the one-off cost of indexing an existing household is
larger than the ongoing cost of queries, which is a few cents a month. Check
[Voyage's pricing page](https://www.voyageai.com/pricing) for current rates.

**Turn the flag on only after the index is built.** Sequence:

```bash
docker compose exec web python manage.py backfill_embeddings
# then set AGENT_HYBRID_RETRIEVAL_ENABLED=True and restart
```

A half-filled index is worse than no index: the search runs, finds nothing, and
never tells you it only looked at part of your household.

**Other providers.** `EMBEDDING_PROVIDER` accepts `voyage` (default), `openai`
(`OPENAI_API_KEY`), or `ollama` (no key, `EMBEDDING_BASE_URL` pointing at your
local instance — it needs about 8 GB of RAM).

> ⚠️ **Changing `EMBEDDING_PROVIDER` or `EMBEDDING_MODEL` after you have indexed
> means re-running `backfill_embeddings` on everything.** The vector column is
> fixed at `EMBEDDING_DIMENSIONS`, and an index holding vectors from two
> different models returns silently wrong results. The startup check catches a
> change of *width*; it cannot catch a change of *model* at the same width.

---

## Recap wording (Anthropic)

Each month Maisonnée assembles a recap of the household — what was spent, what
was fixed, what was photographed. With a key, an LLM rewrites the captions into
warmer prose in the reader's own language.

**Without it.** The recap still exists, still shows every figure, and is still
translated into all four interface languages. The sentences are simply the
built-in templates: accurate, a little drier.

Two settings, both required:

```bash
ANTHROPIC_API_KEY=sk-ant-...     # the same key as the assistant
RECAP_AI_POLISH_ENABLED=True
```

**Cost.** One call per household per month, a few hundred tokens. Negligible
next to the assistant.

---

## Email (SMTP)

Outgoing transactional email: password reset, and the notification sent to
someone you invite who already has an account.

**Without it — and this is the important part — you can still add people to your
household.** Every invitation produces a `/join/<token>` link you copy and send
yourself, by whatever means you already use. Email is a convenience here, never
the only route in. Password reset is the one thing that genuinely needs a
mailbox; without SMTP you reset a password from the admin instead.

By default emails are written to the container log (`docker compose logs web`),
which is useful for testing and honest about delivering nothing.

To send for real, point the instance at any SMTP server — your own, or a
transactional provider:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=maisonnee@example.com
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=maisonnee@example.com
```

**Cost.** Free on most providers at household volume — a handful of messages a
month.

---

## Push notifications (VAPID)

Browser push, so a phone with Maisonnée installed as a web app is notified when
a task is completed or a threshold is crossed, without the app being open.

**Without it.** In-app notifications still work, and so does the bell in the
header. The push toggle in Settings says what it needs. Nothing is sent into a
void.

VAPID keys are self-generated — there is no account to create, nothing to pay:

```bash
docker compose exec web python manage.py generate_vapid_keys
```

Copy the two values it prints into `.env`:

```bash
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_ADMIN_EMAIL=you@example.com    # push services use this to reach you
```

**Both halves matter.** With the public key alone, the browser accepts the
subscription and no message ever arrives — the quietest failure in the set,
which is why the app refuses to create the subscription at all until it has the
pair.

> Push requires HTTPS (except on `localhost`). Set `MAISONNEE_PUBLIC_URL` so the
> instance serves secure cookies to match.

---

## Telegram bot

A second door into the household: ask the assistant a question from Telegram,
receive the daily digest and proactive reminders there.

**Without it.** The Telegram card in Settings is hidden. Notifications still
reach the app itself.

Create a bot by messaging [@BotFather](https://t.me/BotFather) on Telegram
(`/newbot`). You get a token; the username is the one you chose:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-...
TELEGRAM_BOT_USERNAME=my_household_bot     # without the @
TELEGRAM_WEBHOOK_SECRET=<a long random string you invent>
```

Then register the webhook so Telegram knows where to reach your instance:

```bash
docker compose exec web python manage.py telegram_set_webhook
```

**Both the token and the username are required.** The token talks to Telegram;
the username builds the `t.me` link a member opens to link their account. With
only the token, the linking screen shows a button that leads nowhere.

**Cost.** Free. Note that the assistant answering over Telegram uses your
Anthropic key like any other question.

---

## Checking what is on

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/capabilities/
```

```json
{
  "capabilities": [
    {"key": "assistant", "available": false,
     "env_vars": ["ANTHROPIC_API_KEY"],
     "docs_url": "https://github.com/jammindev/maisonnee/blob/main/docs/self-hosting/ai-providers.md#assistant-anthropic"}
  ]
}
```

`available: false` is never an error state. It means the instance knows exactly
what it cannot do and says so — to you here, and to every screen that would
otherwise have promised it.
