# Documentation par module

Référence architecturale de chaque app Django / feature React. Mise à jour : avril 2026.

> Ces fiches sont une **référence**, pas un backlog. Le backlog vit dans [GitHub issues](https://github.com/jammindev/maisonnee/issues) (filtrable par label `app:<name>`). Si une fiche mentionne un comportement, le code en est l'autorité.

Chaque fiche suit le même format :

1. **État synthétique** — backend, frontend, locales, tests, migrations, couverture parcours
2. **Modèles & API** — entités, endpoints, permissions
3. **Notes / décisions produit** — design figé, contraintes DB, références RFC

Lecture recommandée pour reprendre un module après pause — pour les bugs et features à venir, voir GitHub.

## Apps métier (modèle + API + UI)

- [accounts](./accounts.md) — auth, users, impersonation
- [households](./households.md) — tenancy, invitations
- [zones](./zones.md) — hiérarchie spatiale
- [interactions](./interactions.md) — journal d'événements (cœur métier)
- [documents](./documents.md) — fichiers, OCR, privacy
- [directory](./directory.md) — contacts + structures
- [tags](./tags.md) — tags polymorphes
- [equipment](./equipment.md) — équipements + warranty
- [stock](./stock.md) — inventaire consommables
- [electricity](./electricity.md) — tableau électrique
- [projects](./projects.md) — projets + IA threads
- [tasks](./tasks.md) — tâches + assignation
- [insurance](./insurance.md) — contrats d'assurance
- [notifications](./notifications.md) — notifications user

## Argent

- [money](./money.md) — la coque « Argent » : Contrôle / À ranger / Comptes / Dépenses / Budgets
- [banking](./banking.md) — comptes, relevés, rapprochement, **conformité**
- [budget](./budget.md) — enveloppes mensuelles, récurrences, bilan

## Agent & messagerie proactive

- [agent](./agent.md) — assistant conversationnel (RAG + function calling)
- [pings](./pings.md) — questions proactives templatées (Telegram)
- [digest](./digest.md) — résumé quotidien proactif (agrège les signaux du foyer)
- [recap](./recap.md) — le récap mensuel raconté : le mois du foyer en une story de cartes
- [telegram](./telegram.md) — canal Telegram entrant/sortant
- [webpush](./webpush.md) — canal notifications push PWA (Web Push / VAPID)

## Apps frontend / utilitaires

- [photos](./photos.md) — namespace UI
- [app_settings](./app_settings.md) — namespace UI
- [core](./core.md) — modèles abstraits, permissions, middleware

## Apps transverses (frontend / infra)

- [shell-and-design-system](./shell-and-design-system.md) — AppShell, Sidebar, design system, i18n
- [auth-frontend](./auth-frontend.md) — login, JWT, refresh, ProtectedLayout
- [build-and-deploy](./build-and-deploy.md) — Vite, Docker, prod sur Mac Mini

## Voir aussi

- [`docs/JOURNAL_PRODUIT.md`](../JOURNAL_PRODUIT.md) — état des parcours métier
- [`docs/FEATURE_PATTERN.md`](../FEATURE_PATTERN.md) — pattern à suivre pour toute nouvelle feature
- [`CLAUDE.md`](../../CLAUDE.md) — comment travailler + règles projet
  (`AGENTS.md` est un lien symbolique vers ce même fichier)
- **GitHub issues** ([`jammindev/maisonnee`](https://github.com/jammindev/maisonnee/issues)) — source unique de vérité du backlog
