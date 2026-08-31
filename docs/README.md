# Documentation Hub

> La porte d'entrée publique du projet est [`../README.md`](../README.md)
> (et [`../README.fr.md`](../README.fr.md)) : la promesse, les captures et
> l'installation en trois lignes. Ce hub-ci s'adresse à qui travaille dessus.


Documentation active du projet **House**. Mise à jour : avril 2026.

Architecture courante : **SPA pure** — backend Django/DRF (API REST + JWT) + frontend React unique (`ui/src`) routé par `react-router`.

Parcours 01→06 livrés. Voir `JOURNAL_PRODUIT.md` pour le détail.

## Scope et source de vérité

- Runtime source of truth : `config/`, `apps/`, `ui/src/`
- **Backlog** : [GitHub issues](https://github.com/jammindev/maisonnee/issues), filtrable par label `app:<name>`
- En cas de conflit doc ↔ code, le code gagne.

## Lire en priorité

- `../CLAUDE.md` — comment travailler + règles projet (workflow git, commandes,
  i18n, composants UI). `../AGENTS.md` est un lien symbolique vers ce fichier :
  une seule source, pour tous les agents.
- `./MODULES/README.md` — référence architecturale par module
- `./FEATURE_PATTERN.md` — pattern à suivre pour toute nouvelle feature React
- `./JOURNAL_PRODUIT.md` — journal des parcours métier livrés et en cours
- `./NEXT_STEPS.md` — petite doc des chantiers à venir (recette, lots ouverts, prochain parcours)

## Product and domain

- `./PRODUCT_OVERVIEW.md` — intent, capabilities and boundaries
- `./DOMAIN_MODEL_INTERACTIONS.md` — interaction-centric domain model
- `./ARCHITECTURE.md` — backend/frontend stack et organisation

## Parcours métier

- `./parcours/PARCOURS_01_*.md` — capturer / retrouver un événement
- `./parcours/PARCOURS_02_*.md` — traiter un document entrant
- `./parcours/PARCOURS_03_*.md` — transformer un besoin en action
- `./parcours/PARCOURS_04_*.md` — suivre un projet de bout en bout
- `./parcours/PARCOURS_05_*.md` — naviguer par zone ou équipement
- `./parcours/PARCOURS_06_*.md` — alertes proactives
- `./parcours/PARCOURS_07_*.md` — agent conversationnel sur le foyer (V1 livrée 2026-05-02, lots 0a→3)

> Les parcours 08 et suivants ne sont pas listés ici un par un — voir
> `./NEXT_STEPS.md` pour le chantier courant et `./parcours/` pour l'ensemble.

## Auto-hébergement

- `./parcours/PARCOURS_28_OUVRIR_MAISONNEE.md` — publier le projet en open source
  auto-hébergeable (AGPL-3.0, `docker compose up`, foyers pilotes)
- `./fiches/AUTO_HEBERGEMENT.md` — le cours : d'un déploiement à un produit
  installable (modèle de menace, capacités optionnelles, licence, sauvegarde),
  suivi de ce que l'implémentation des lots 0 à 5 a appris
- `./self-hosting/` — **en anglais**, le manuel de l'exploitant : installation,
  clés optionnelles, sauvegarde **et restauration**, mises à jour, releases,
  dépannage. `../DEPLOYMENT.md` reste le déploiement de l'auteur et le dit
  désormais dès sa première ligne.

## RFC et notes thématiques

- `./SYNC_CONTACTS_STRUCTURES.md` — RFC vCard pour le directory
- `./parcours/PARCOURS_IA_TRANSVERSE.md` — note chapeau de la couche IA (principes communs aux parcours 01 et 02)

## App-level docs

- `../apps/electricity/react/README.md`

Additional app docs should be added under each app when behavior is specific to one domain and not cross-cutting.
