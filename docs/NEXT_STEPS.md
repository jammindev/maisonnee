# Next steps

> **2026-08-13 — Parcours 28 : il ne reste que le lot 7, et il n'est plus
> technique.** Les lots 0, 1, 1ter, 2, 3, 4, 5, 6 et 8 sont livrés et déployés.
> L'image `v0.1.0` est **publique** : `docker pull ghcr.io/jammindev/maisonnee:latest`
> répond sans compte, en `amd64` et `arm64`, et les trois lignes du README sont
> vraies pour un inconnu — vérifié sans authentification, pas en relisant le
> workflow.
>
> **La prochaine action est donc la recette pilote** (#493) : cinq à dix foyers,
> installation sans assistance en direct, questions à J+1, S+2, S+6, et une issue
> par blocage rencontré. Les canaux publics (r/selfhosted, awesome-selfhosted,
> Show HN) ne s'ouvrent qu'après correction de ces blocages — on n'a qu'un seul
> coup par communauté. Ce qu'on mesure reste la **rétention à S+6**, pas les
> étoiles.
>
> Deux gestes manuels non bloquants restent : déposer
> `docs/assets/brand/social-preview.png` dans *Settings → General → Social preview*
> (aucune API GitHub ne le fait), et le GIF d'import, volontairement non produit —
> un flux multi-étapes qui casse en silence, et un GIF à moitié juste vaut moins
> que pas de GIF.
>
> **Écart connu et assumé** : aucun plafond de dépense sur l'API du fournisseur.
> `AIUsageLog` observe, il ne coupe pas. Sans conséquence tant que l'auteur
> n'héberge pas de foyers tiers — bloquant le jour où il le ferait.
>
> - Journal : [`2026-08-13_parcours-28_ouverture-effective.md`](./journal/2026-08-13_parcours-28_ouverture-effective.md)
> - Fiche neuve : [`DISTRIBUTION_ET_REGISTRE.md`](./fiches/DISTRIBUTION_ET_REGISTRE.md)

---

> **Cadré au 2026-08-03 — Parcours 29 : l'album du foyer.** Chantier cadré ce
> jour (doc produit, fiche concept, backlog en 7 lots, issues #526 → #534).
> **Lot 2 livré le 2026-08-04** (#528) — les six autres restent à faire.
>
> Déclencheur : la livraison du téléversement multiple (#524) le matin même, et la
> friction apparue à la première utilisation réelle — « les photos techniques sont
> mélangées avec les photos souvenirs, les photos observation ». Une photo porte
> trois axes (zone, entité liée, phase avant/après) et aucun ne dit **pourquoi
> elle existe**. Le parcours ajoute cet axe, l'**intention**, et en fait la
> première question de la galerie.
>
> **Arbitrage assumé** : l'ambition retenue est **l'album complet** — House vise à
> devenir le point d'entrée photo, souvenirs inclus — contre l'alternative « le
> classeur du foyer », qui était la recommandation. Les trois coûts sont nommés
> dans la doc produit : changement d'ordre de grandeur du volume, quota qui devient
> une contrainte réelle, comparaison frontale avec la pellicule du téléphone.
>
> Ordre initial : **1** (dettes : pagination curseur + `size_bytes` en colonne) →
> **2** (l'intention et la file « À trier ») → **3** (stockage objet) et **4**
> (tâches de fond), indépendants entre eux mais prérequis du **6** (import
> massif) → **5** (quota, dès que 1 est livré) → **7** (synchro iPhone).
>
> **Réordonné le 2026-08-04 : le lot 2 est passé devant le lot 1, et il est livré.**
> C'est le seul lot qui résout la friction réelle ; les six autres sont de
> l'infrastructure pour un volume qui n'existe pas encore. Le lot 1 n'était pas un
> prérequis *dur* du 2 — sa dette est contournée par une file bornée côté serveur
> (`TRIAGE_WINDOW`), et la galerie à plat ne se charge pas en mode tri. Reste donc :
> **1** (qui lèvera cette borne) → **3** et **4** → **6** → **5** → **7**.
>
> **⚠️ Ce cadrage ne tranche pas la priorité relative avec le parcours 28.** Les
> lots 0 et 4 de celui-ci corrigent des écarts *ouverts aujourd'hui* (runner
> exposé, dépôt public sans licence) et restent hors séquence, avant tout le reste.
>
> - Doc produit : [`PARCOURS_29_ALBUM_DU_FOYER.md`](./parcours/PARCOURS_29_ALBUM_DU_FOYER.md)
> - Backlog : [`PARCOURS_29_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_29_BACKLOG_TECHNIQUE.md)
> - Fiche concept : [`PIPELINE_MEDIA.md`](./fiches/PIPELINE_MEDIA.md)
> - Journal : [`2026-08-03_parcours-29_cadrage_initial.md`](./journal/2026-08-03_parcours-29_cadrage_initial.md)

---

> **Priorité au 2026-07-31 — Parcours 28 : ouvrir Maisonnée (open source,
> auto-hébergeable).** Chantier cadré ce jour (doc produit, fiche concept, backlog
> en 8 lots, issues #485 → #493) ; aucun lot démarré.
>
> Changement de nature par rapport aux parcours 21 → 27, qui ont construit le
> produit : celui-ci ne construit rien pour le foyer de l'auteur. Il transforme un
> déploiement personnel en un **produit qu'un inconnu peut installer, comprendre et
> exploiter** — sous le nom **Maisonnée**, en **AGPL-3.0**.
>
> **Constat qui réordonne tout** : le dépôt est **déjà public depuis le
> 2025-09-21** (0★, aucune licence). Les lots 0 (hygiène + CI) et 4 (licence) ne
> préparent donc rien — ils corrigent des écarts **ouverts aujourd'hui** : un
> runner `self-hosted` exposé, un `@claude` que n'importe qui peut déclencher sur
> le quota de l'auteur, et un code sous « tous droits réservés » par défaut. À
> traiter tout de suite, hors séquence.
>
> Ordre ensuite : **1** (isolation multi-tenant — le plus long, bloquant) → **2**
> (`docker compose up`) → **3** (dégradation sans clé d'API) → **5**
> (sauvegarde/restauration) → **6** (README + captures) → **7** (5-10 foyers
> pilotes, puis annonce). Ne pas faire 6 avant 3 : une capture d'un onglet qui
> promet ce qu'il ne peut pas tenir est une capture à refaire.
>
> Ce qu'on mesure : la **rétention** à S+6, pas les étoiles. Cent installations et
> zéro retour en semaine 3 est un résultat négatif.
>
> - Doc produit : [`PARCOURS_28_OUVRIR_MAISONNEE.md`](./parcours/PARCOURS_28_OUVRIR_MAISONNEE.md)
> - Backlog : [`PARCOURS_28_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_28_BACKLOG_TECHNIQUE.md)
> - Fiche concept : [`AUTO_HEBERGEMENT.md`](./fiches/AUTO_HEBERGEMENT.md)
> - Journal : [`2026-07-31_parcours-28_cadrage_initial.md`](./journal/2026-07-31_parcours-28_cadrage_initial.md)

---

> **Priorité précédente au 2026-07-28 — Parcours 27 : le récap mensuel raconté.** Chantier cadré
> ce jour (doc produit, fiche concept, backlog en 6 lots, issues #435 → #441) ;
> implémentation à démarrer au lot 1.
>
> Changement de nature par rapport aux parcours 21 → 26, qui ont rendu l'argent
> complet puis fiable : celui-ci ne demande **rien de nouveau** à l'utilisateur, il lui
> rend ce qu'il a déjà donné. La limite qu'il lève n'est pas technique mais affective —
> House est entièrement tourné vers le devoir, et **rien n'y récompense jamais d'avoir
> tenu ses données à jour**, alors que c'est l'effort le plus coûteux et le plus fragile
> du produit.
>
> Ordre : **1 → 2 → 3 → 4** en tranche verticale (à la fin du lot 4 la story tourne
> avec un seul chapitre, et c'est là qu'on juge la forme) → **5** (les autres
> chapitres) → **6** (le rendez-vous). Ne pas inverser 4 et 5.
>
> - Doc produit : [`PARCOURS_27_LE_RECAP_MENSUEL_RACONTE.md`](./parcours/PARCOURS_27_LE_RECAP_MENSUEL_RACONTE.md)
> - Backlog : [`PARCOURS_27_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_27_BACKLOG_TECHNIQUE.md)
> - Fiche concept : [`SNAPSHOT_ET_RECIT.md`](./fiches/SNAPSHOT_ET_RECIT.md)
> - Journal : [`2026-07-28_parcours-27_cadrage_initial.md`](./journal/2026-07-28_parcours-27_cadrage_initial.md)
>
> Le chantier voisin, délibérément **non** retenu cette fois : le **fil du foyer avec
> réactions** — le seul levier où la récompense est une autre personne. À rouvrir après
> cette V1, surtout si les foyers réels comptent deux membres actifs ou plus.

---

> **Priorité précédente au 2026-07-25 — Parcours 25 : les relevés bancaires comme source de
> vérité des dépenses.** Chantier cadré ce jour (doc produit, fiche concept,
> backlog en 9 lots, issues GitHub) ; implémentation à démarrer au lot 1.
>
> C'est le chantier qui lève le plafond des parcours 08 et 21 : aujourd'hui une
> dépense n'existe que si elle a été saisie, donc un budget n'est fiable que si la
> discipline de saisie l'est. Ordre : lot 1 (comptes) → lot 2 (import CSV/XLSX) →
> lot 3 (journal) → **lot 4 (soldes, qui valide que l'import est juste)** → lot 5
> (ventilation) → **lot 6 (rapprochement auto, qui décide de l'adoption)** → 7-8.
>
> - Doc produit : [`PARCOURS_25_RELEVES_BANCAIRES.md`](./parcours/PARCOURS_25_RELEVES_BANCAIRES.md)
> - Backlog : [`PARCOURS_25_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_25_BACKLOG_TECHNIQUE.md)
> - Fiche concept : [`IMPORT_ET_RAPPROCHEMENT.md`](./fiches/IMPORT_ET_RAPPROCHEMENT.md)
> - Journal : [`2026-07-25_parcours-25_cadrage_initial.md`](./journal/2026-07-25_parcours-25_cadrage_initial.md)

Le reste de cette page date du **2026-05-02** (fil d'après la V1 du parcours 07) et n'a pas été réactualisé.

## Maintenant — recette manuelle (1-2 semaines)

Utiliser l'agent au quotidien sur le foyer réel ("Les Petits Bonheur", 188 docs) avant d'ouvrir des chantiers d'optimisation.

- [ ] poser des questions au quotidien dans `/app/agent/`
- [ ] noter les questions qui ratent un match évident → déclencheur de #113 (stemming par foyer)
- [ ] noter les réponses où la citation paraît bizarre → déclencheur d'un fix prompt ou retrieval
- [ ] noter les latences inacceptables → déclencheur d'un cache / reformulation prompt
- [ ] fermer #51 (issue parente du parcours 07) une fois la recette terminée

But : ouvrir des issues **ciblées** plutôt que sur-investir à l'aveugle.

## Court terme — issues ouvertes du parcours 07

| Issue | Sujet | Quand | Effort |
|---|---|---|---|
| #109 | Lot 6 — observabilité IA (KPIs + page admin) | Quand le besoin de métriques se fait sentir | ~2 jours |
| #113 | Stemming par foyer (`Household.preferred_language`) | Si l'usage révèle des matches ratés "facture"↔"factures" | ~1 jour |

Lot 6 (#109) : le backend skeleton est déjà livré (modèle `AIUsageLog` + helper + admin). Reste : agrégations, API, UI page admin `/app/admin/ai-usage/`, refacto OCR pour passer par `LLMClient.vision_extract()`.

## Court terme — autres chantiers déjà cadrés

| Issue | Sujet | Pourquoi |
|---|---|---|
| #69 | Page 404 + Error Boundary global | Polish UI avant ouverture multi-user |
| #65 | Page Assurances — frontend manquant | Trou produit visible |
| #67 | Champ montant structuré pour les dépenses | Débloque le scénario B du parcours 07 ("combien j'ai dépensé en plomberie") |
| #75 | Récurrence des tâches | Demande utilisateur récurrente |

## Moyen terme — prochain parcours métier

**Parcours 06 — Alertes et rappels proactifs** est le seul parcours métier V1 pas encore démarré.

- doc produit : [`docs/parcours/PARCOURS_06_ALERTES_ET_RAPPELS_PROACTIFS.md`](./parcours/PARCOURS_06_ALERTES_ET_RAPPELS_PROACTIFS.md)
- backlog : [`docs/parcours/PARCOURS_06_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_06_BACKLOG_TECHNIQUE.md)
- issue parente liée : #40 (assignation de tâche + notifications, V2 du parcours 06)

À démarrer après la recette du parcours 07 si on veut élargir plutôt qu'approfondir.

## Moyen terme — parcours 09 : piloter la maison connectée

Cadré le 2026-07-03. Base domotique générique multi-constructeurs (capabilities normalisées + couche adapter), premier provider Shelly Cloud, intégration agent (lecture d'état via RAG + tool `control_device`). Preuve V1 : piloter le Shelly 2PM réel (volet roulant).

- doc produit : [`docs/parcours/PARCOURS_09_PILOTER_LA_MAISON_CONNECTEE.md`](./parcours/PARCOURS_09_PILOTER_LA_MAISON_CONNECTEE.md)
- backlog : [`docs/parcours/PARCOURS_09_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_09_BACKLOG_TECHNIQUE.md)
- issues : #183 (socle), #185 (provider Shelly), #186 (services + API), #187 (frontend), #188 (agent), #189 (V2 différée : mesures, cron, webhooks, chiffrement)

## Moyen terme — parcours 10 : analyser la consommation électrique

Cadré le 2026-07-04. Onglet Consommation du module Électricité : modèle pivot générique multi-pays (`ConsumptionRecord` en Wh sur intervalle explicite), relevés d'index manuels matérialisés en estimations quotidiennes, imports idempotents via registry d'adaptateurs (`enedis_csv` + `generic_csv` à mapping libre), agrégation serveur heure/jour/mois/année, chart Recharts (première lib de graphiques du projet), agent (somme kWh via `list_entities`, relevé dicté avec undo). Preuve V1 : la courbe de charge Enedis réelle importée donne les mêmes totaux que l'espace client.

- doc produit : [`docs/parcours/PARCOURS_10_ANALYSER_LA_CONSOMMATION_ELECTRIQUE.md`](./parcours/PARCOURS_10_ANALYSER_LA_CONSOMMATION_ELECTRIQUE.md)
- backlog : [`docs/parcours/PARCOURS_10_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_10_BACKLOG_TECHNIQUE.md)
- issues : #198 (socle backend), #199 (importers), #200 (frontend), #201 (agent), #202 (V2 différée : coût €, comparaisons, sync auto, autres fluides)

## Moyen terme — parcours 11 : tracker des valeurs dans le temps

Cadré le 2026-07-04. Séries de valeurs numériques datées (compteurs, niveaux, heures, budgets, poids) ancrées sur l'existant : FK projet (onglet du détail projet) + liaison générique vers toute entité du foyer (via le registry `agent.searchables`). Saisie rapide depuis la carte, sparkline SVG maison, valeurs citables par l'agent via `entries_summary` (même pont RAG que le parcours 09) et relevé dicté via `create_entity` avec undo. Preuve V1 : le relevé mensuel du compteur d'eau en moins de dix secondes.

- doc produit : [`docs/parcours/PARCOURS_11_TRACKER_DES_VALEURS.md`](./parcours/PARCOURS_11_TRACKER_DES_VALEURS.md)
- backlog : [`docs/parcours/PARCOURS_11_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_11_BACKLOG_TECHNIQUE.md)
- issues : #192 (socle), #193 (services + API), #194 (frontend), #195 (embed projet), #196 (agent), #197 (V2 différée : graphes riches, agrégats, rappels, panneaux entités)

## Moyen terme — extensions IA des parcours 01 et 02

S'appuient sur la couche IA déjà posée (`LLMClient`, `AIUsageLog`, citations). À arbitrer après quelques semaines d'usage de l'agent V1.

| Issue | Sujet |
|---|---|
| #50 | Capture d'interaction depuis WhatsApp / email / IA (parcours 01 IA) |
| — | Compréhension assistée de documents à l'upload (parcours 02 IA, suggestion de qualification) |

Décisions transverses tranchées dans [`docs/parcours/PARCOURS_IA_TRANSVERSE.md`](./parcours/PARCOURS_IA_TRANSVERSE.md). Restent à arbitrer : contrat de proposition (schéma JSON unique vs par entité), stockage des suggestions, stratégie zone manquante, résolution utilisateur+household pour canaux externes.

## Moyen terme — ouverture multi-user

Tant qu'on est en solo user, le bar de qualité reste indulgent. Avant d'ouvrir l'app à d'autres utilisateurs :

| Issue | Sujet |
|---|---|
| #58 | Audit global du code et préparation du MVP pour ouverture aux utilisateurs |
| #59 | Page d'inscription (signup) — frontend manquant |
| #64 | Vérifier et activer l'envoi d'email pour les invitations foyer |
| #48 | Audit log pour les actions sensibles |
| #49 | 2FA / TOTP |
| #52 | Compte démo en lecture seule |
| #39 | Séparer Documents et Photos (modèles distincts) |

## Moyen terme — parcours 21 : recherche sémantique hybride (embeddings)

Cadré le 2026-07-21. **Chantier technique transverse** (pas de surface UI nouvelle) : ajouter une jambe sémantique (embeddings `pgvector`) **à côté** du full-text actuel, fusionnée par Reciprocal Rank Fusion — l'agent retrouve par le sens quand le vocabulaire de la question diverge des documents (« le chauffage » → facture « pompe à chaleur »). Abstraction `EmbeddingClient` (miroir de `LLMClient`) ; fournisseur prod tranché : **API Voyage AI** (`voyage-3`, multilingue) — le VPS 4 Go ne peut pas héberger un modèle local sans risquer l'OOM, l'API = 0 Go RAM + coût négligeable ; Ollama local (`bge-m3`) reste la cible RAM ≥ 8 Go, activable en un flag. Table d'index `EmbeddingChunk` + chunking, backfill par management command, flag de rollback, qualité validée par éval `recall@k`/`MRR`. `retrieval.search()` garde sa signature → tout `apps/agent/` est transparent au changement. Prend le relais de l'ancienne idée « embeddings si le full-text plafonne » : le plafond a été touché à l'usage.

- doc produit : [`docs/parcours/PARCOURS_21_RECHERCHE_SEMANTIQUE_HYBRIDE.md`](./parcours/PARCOURS_21_RECHERCHE_SEMANTIQUE_HYBRIDE.md)
- fiche concept (le cours) : [`docs/fiches/EMBEDDINGS.md`](./fiches/EMBEDDINGS.md)
- backlog : [`docs/parcours/PARCOURS_21_BACKLOG_TECHNIQUE.md`](./parcours/PARCOURS_21_BACKLOG_TECHNIQUE.md)
- issues : #327 (lot 0 socle), #328 (lot 1 EmbeddingChunk), #329 (lot 2 backfill), #330 (lot 3 retrieval hybride RRF), #331 (lot 4 éval + observabilité), #332 (lot 5 idées V2)

## Idées long terme

- Lot 4 du parcours 07 — mémoire conversationnelle multi-tour (basculée V2). À arbitrer si l'usage one-shot devient frustrant.
- Streaming de réponse dans le chat agent (UX, pas critique tant que latence reste à 2-4s).
- `OllamaClient` pour faire tourner l'agent en local (l'abstraction `LLMClient` est déjà prête).
- **Chiffrement des documents** (milestone GitHub [#8](https://github.com/jammindev/maisonnee/milestone/8)) — protéger le contenu des documents/photos, aujourd'hui stockés en clair (`MEDIA_ROOT` sur le VPS, `ocr_text` en clair en DB). Deux phases :
  - **Phase 1 — chiffrement au repos** (le serveur garde la clé) : protège contre un vol de disque / backup qui fuite, **sans casser** OCR / full-text / RAG. Meilleur rapport bénéfice/coût, à faire en premier.
  - **Phase 2 — coffre E2EE sélectif** (le client garde la clé) : s'appuie sur `documents.is_private`, l'user marque un doc comme « coffre » → chiffré côté client, **exclu** de l'OCR / full-text / RAG (trade-off assumé et affiché).
  - Hors scope : E2EE total du corpus (casserait le RAG serveur-side).

## Comment garder cette doc à jour

À relire à chaque fin de gros chantier (livraison d'un parcours, ouverture multi-user, pivot produit). Les issues GitHub restent la source de vérité du backlog ; ce document hiérarchise et donne le narratif.
