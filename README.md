<div align="center">

<img src="docs/assets/brand/logo-mark.svg" alt="" width="72" />

# Maisonnée

**Everything a household keeps alive — and a memory that can answer for it.**
Indoors and out: the works, the money, the meters, the garden, the animals.

[**Try the live demo →**](https://demo.maisonnee.jammin-dev.com) ·
[Install](#install-it-in-three-lines) · [What it does](#what-it-does) ·
[Without an API key](#without-an-api-key) ·
[What it does not do](#what-it-does-not-do) ·
[Self-hosting docs](docs/self-hosting/README.md) · [Français](README.fr.md)

</div>

![The assistant answering a question about the household, citing the renovation log and the project it belongs to](docs/assets/screenshots/01-assistant.png)

> *"We want to redo the toilet floor in the same tile as the bathroom. What was
> the reference, and is there any left?"* — and the answer comes back with the
> brand, the reference, **where the two spare boxes are stored**, and a link to
> the two records it read. Nobody remembers that three years later. The house
> does.

---

## The idea

Household software makes you choose a corner. A budgeting app for the money. A
todo app for the chores. A spreadsheet for the meter readings. A note somewhere
for when the boiler was serviced. Each is fine on its own, and none of them
knows about the others — so nothing ever adds up, and nothing can be *asked*.

Maisonnée keeps **one register for the whole household**, and then puts an
assistant on top of it. That order matters: the assistant is not a chatbot
bolted onto a database. It is the reason the single register is worth keeping.

Everything you record is retrievable and citable — around two dozen kinds of
thing: projects, journal entries, the renovation log, documents and the text
inside them, equipment, contracts, tasks, zones, meter readings, stock,
chickens, contacts. Ask a question in plain language and the answer comes back
**with its sources attached**, each one a link to the record it came from.

- *"Which equipment is still under warranty?"*
- *"What did the bathroom cost, all in?"*
- *"When was the boiler last serviced, and by whom?"*
- *"What paint is on the teenager's bedroom wall?"*

The assistant can also **write**: create a task or a note from the conversation,
with a one-click undo. It keeps a **memory** of what you tell it to remember,
and a conversation can be **anchored** to one project or one piece of equipment
so it already knows the context before you start typing.

## Install it in three lines

```bash
curl -O https://raw.githubusercontent.com/jammindev/maisonnee/main/docker-compose.yml
docker compose up -d
open http://localhost:8000
```

No Python, no Node, no `git clone`, no key to subscribe to. The first start
pulls the image, creates the database and applies the schema. Then the browser
asks you for the rest — your email, your password, a name for your household.
Nothing to copy out of a terminal.

Runs on `amd64` and `arm64`: a Raspberry Pi 4/5, an N100 box or a Synology are
all enough. About 2 GB of RAM and 5 GB of disk to start.

Full guide: [docs/self-hosting/install.md](docs/self-hosting/install.md) —
reverse proxy, backups, upgrades.

## What it does

### The memory it reads from

![The household journal: notes, maintenance records and the renovation log in one timeline](docs/assets/screenshots/02-journal.png)

A single journal holds what a household actually needs to remember: notes,
maintenance done on a piece of equipment, and a **renovation log** that keeps the
brand and reference of what was installed, room by room. Documents are indexed
by their contents, not just their filename — a scanned invoice is searchable by
what is printed on it.

This is what the assistant reads. It is also perfectly usable on its own: search,
filter, follow a link from a project to the receipts that paid for it.

### The day, in one screen

![The dashboard: what needs attention today, with the money and the outdoors side by side](docs/assets/screenshots/03-dashboard.png)

What needs attention, what is due this week, and the household's vital signs —
spending, water, eggs — in the same glance.

### The money, down to the line

![The bank journal: every operation exactly as the bank recorded it, each one allocated or flagged](docs/assets/screenshots/04-bank-journal.png)

Import a CSV statement and reconcile it. One bank line can split across several
budgets *and* attach to a project — 150 € at the hardware store can be 90 € of
"the bathroom" and 60 € of general upkeep, which is what makes "what did the
bathroom cost" answerable at all. Refunds credit the envelope back. Internal
transfers stop counting as spending. A **Control** tab lists, with a reason,
everything the app cannot account for.

The rule the money side is built on: **every euro is either filed or flagged** —
nothing sits in a silent in-between.

![Budgets: nested categories, ceilings, and what is over](docs/assets/screenshots/05-budgets.png)

Ceilings are **optional** — "Gifts" can be a tracked category with no limit,
because inventing a number to get a category makes every other bar meaningless.

### The outdoors is not an afterthought

![The chicken coop: laying, feed, cost per egg, chores and the flock](docs/assets/screenshots/06-chicken-coop.png)

Chickens, water, electricity, stock, the garden — same register as everything
else, which is why the coop can tell you what an egg costs. Laying, feed
reserves, recurring chores, and each hen with her own history.

![The electrical board: rows, breakers and RCDs, as they are in the cellar](docs/assets/screenshots/07-electricity.png)

The consumer unit, drawn as it actually is — the thing you want when a breaker
trips and you are in the cellar with a torch.

And the ordinary things: tasks and recurring chores, zones and equipment,
insurance policies, a shopping list, photos.

## Without an API key

**Almost everything still works, and nothing is crippled.** Every record the
assistant reads, you can create, edit, search and link **from the interface** —
the app was a complete household register before it had an assistant, and it
still is one.

What a key adds, and nothing else:

| Needs a key | What you have without one |
|---|---|
| Conversational assistant | Full-text search across the same records, with highlighting |
| Semantic search | Keyword search, which covers most of what you look for |
| Monthly recap written in prose | The monthly report, with the same figures |
| Reading text out of a scanned document | The document itself, and everything you type about it |

Push notifications, e-mail and the Telegram bot are the same idea: supply the
service and they light up, skip it and the rest is untouched.

**And the app says so out loud.** An unavailable capability is announced where
you would have used it, with the variable to set and a link to the guide — never
a button that fails. Keys are per instance, in your `.env`; nothing is ever sent
anywhere you did not configure. See
[docs/self-hosting/ai-providers.md](docs/self-hosting/ai-providers.md).

## What it does not do

Written down so you find out here rather than after installing:

- **No bank aggregation.** You export a CSV from your bank and import it.
- **No hosted version.** You run it, or you don't. There is no account to create
  on someone else's server.
- **No native mobile app.** It is a PWA: installable, works offline for reading,
  takes shared photos from Android and iOS.
- **No telemetry.** Nothing calls home. Ever.
- **No multi-currency.** Amounts are euros.
- **Not a team product.** It models a household: a few people who trust each
  other and share a roof.

## Status

**v0.1.0.** Built for one real household and used daily by it since 2025. It has
had one user for most of its life, which shows in both directions: the parts that
household uses are worn smooth, and the parts it doesn't are younger than they
look.

- The interface speaks **English, French, German and Spanish**.
- The internal documentation and some code comments are **in French** — a
  deliberate, documented choice, see [CONTRIBUTING.md](CONTRIBUTING.md). Issues
  and pull requests in English are welcome, and
  [docs/README.en.md](docs/README.en.md) is an English guide to the French docs.
- Backup **and restore** are scripted and exercised in CI on every release,
  because a backup nobody has restored is not a backup.
- Destructive migrations ship in two steps, so an upgrade never needs you to be
  watching.

If you install it, the most useful thing you can do is tell the author what
broke. That is worth more right now than a pull request.

## Documentation

| | |
|---|---|
| [Self-hosting](docs/self-hosting/README.md) | Install, backup and restore, upgrades, troubleshooting |
| [AI providers](docs/self-hosting/ai-providers.md) | Which keys unlock what, and what happens without them |
| [Contributing](CONTRIBUTING.md) | How to help, and the language the project is written in |
| [Security](SECURITY.md) | Reporting a vulnerability, privately |
| [English guide to the docs](docs/README.en.md) | What the French documentation holds |

## Licence

[AGPL-3.0-only](LICENSE). Run it, change it, share it. If you host a modified
version *for other people*, publish your changes — hosting it for your own family
is not "for other people", it is the normal use of this software.

The **name and the mark are not covered by the licence**; a redistributed fork
carries its own name. Details, without lawyer-speak:
[docs/assets/brand/README.md](docs/assets/brand/README.md).
