# Security policy

Maisonnée holds a household's bank statements, invoices, insurance contracts and
address. A scoping bug here is not "my partner saw my shopping list" — it is "a
stranger read my bank statements". Reports are taken seriously and answered.

## Reporting a vulnerability

**Please do not open a public issue.**

Use GitHub's private reporting form:
**[Security → Report a vulnerability](https://github.com/jammindev/maisonnee/security/advisories/new)**

It is enabled on this repository. The report stays private between you and the
maintainer until a fix is published.

Useful in a report, roughly in order of value:

1. what an attacker can reach that they should not (a household's data, a file, an
   endpoint);
2. the steps to reproduce it, ideally against a local `docker compose` instance;
3. the version or commit you tested;
4. whether the issue is already public somewhere.

A proof of concept is welcome but never required — a clear description of the flaw
is enough.

## What to expect

This is a **one-person project**, maintained alongside a full-time job. The
commitments below are deliberately modest, because a promise that cannot be kept
is worse than no promise:

| Step | Target |
|---|---|
| Acknowledgement of your report | within **7 days** |
| First assessment (confirmed / not a vulnerability / need more info) | within **14 days** |
| Fix released for a confirmed, exploitable issue | as fast as possible; you will be told what "as fast as possible" means in practice |

If you have not heard back after 14 days, assume the message was missed rather
than ignored, and ping [@jammindev](https://github.com/jammindev) on GitHub.

## Disclosure

Coordinated disclosure, without a fixed deadline imposed on you: publish whenever
you judge it right. Being told beforehand is appreciated, so that a fix and the
report can land together.

Credit is given in the release notes unless you prefer to stay anonymous — just
say so.

## Supported versions

Only the **latest release** is supported. There is no long-term support branch:
one person cannot maintain several. Self-hosted instances should track the latest
tag.

Users who self-host are the ones who apply updates, so a security fix is only
useful once it reaches them: security releases are announced in the repository's
releases feed, which is worth subscribing to.

## Scope

**In scope** — anything that lets someone reach data belonging to a household
they are not a member of; authentication and session handling; the file-serving
paths; the conversational agent's read and write tools; the default configuration
shipped by `docker-compose.yml`.

**Out of scope** — findings that require an already-compromised server or
database; missing hardening headers with no demonstrated impact; automated
scanner output without an exploitable scenario; and vulnerabilities in a
self-hoster's own reverse proxy, network or operating system.

A note on the default configuration: it is designed for a home network. Exposing
an instance directly to the internet is a deliberate choice made by its operator,
and hardening beyond what ships by default is theirs to do.
