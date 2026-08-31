# Self-hosting Maisonnée

Maisonnée is a household app you run yourself: documents, money, tasks, projects,
zones and equipment, for one family, on one machine you control. No account, no
telemetry, no hosted tier.

These pages are the operator's manual. They assume Docker and nothing else.

| Page | What it answers |
|---|---|
| [install.md](install.md) | Getting it running, and putting it behind a domain if you want one |
| [ai-providers.md](ai-providers.md) | The optional keys — assistant, semantic search, email, push, Telegram — what each costs and what the app does without it |
| [backup-restore.md](backup-restore.md) | Backing up, and — the part that matters — **restoring** |
| [upgrade.md](upgrade.md) | Updating, and the compatibility promise that comes with it |
| [releases.md](releases.md) | What a version number means here, and how to pin one |
| [troubleshooting.md](troubleshooting.md) | It doesn't start / it's slow / I can't log in |

## Start here

```bash
curl -O https://raw.githubusercontent.com/jammindev/maisonnee/main/docker-compose.yml
docker compose up -d
```

Then open <http://localhost:8000>, where the screen asks you to create your
account. Nothing to edit, no key to sign up for, nothing to copy out of a
terminal.

To look around a filled-in household before typing anything of your own:

```bash
docker compose --profile demo up -d
```

## The two things to know before you trust it with your data

**Two volumes, and you need both.** `postgres-data` holds the database;
`maisonnee-state` holds the instance secret key *and* every file anyone
uploaded. Backing up only the first gives you a restore where every document is
referenced and missing, and where everyone is logged out. [backup-restore.md](backup-restore.md)
treats them as one thing on purpose.

**A destructive change ships in two steps.** Once other people run this, we no
longer control when they update — so a column is never dropped and renamed in the
same version. See the compatibility section of [upgrade.md](upgrade.md).

## Where the rest of the documentation is

The project's internal documentation is in French, and it is where the reasoning
lives — every rule tied to a bug that actually happened. [`docs/README.en.md`](../README.en.md)
is an English index of it: what each folder holds and why it might be worth
reading.

`DEPLOYMENT.md` at the repository root is **the author's own deployment** — one
VPS, Traefik, a self-hosted CI runner. It is kept because it documents invariants
this stack inherits, not because you should follow it.
