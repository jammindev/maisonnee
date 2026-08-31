# Parcours 24 — L'agent retient les faits durables du foyer

> Cadrage : 2026-07-23. Prolonge le parcours 07 lot 10 (mémoire utilisateur).
> Là où la mémoire actuelle (`AgentMemory`) ne retient que des faits **privés
> à une personne** (« Ben préfère les réponses courtes »), ce parcours ajoute
> une mémoire **partagée par le foyer** : les faits stables sur la maison
> elle-même (« la maison est chauffée par une pompe à chaleur », « la façade
> est en pierre », « le plombier habituel est Dupont »). L'agent les capture
> pendant une conversation, puis — en V2 — les extrait automatiquement des
> interactions et projets que le foyer saisit, pour répondre mieux partout sans
> qu'on ait à tout redire.
>
> Numéro **24** : le 22 est réservé aux modules courses/repas
> (`app:shopping`/`app:meals`), le 23 à la feature briefings.
>
> Réutilise intégralement le socle mémoire du parcours 07 :
> `apps/agent/memory.py`, tool `manage_memory`, `MEMORY_BLOCK` du system prompt.

## Décisions d'architecture (actées)

1. **Deux mémoires DISTINCTES, pas un champ `scope` unifié.** `AgentMemory`
   existant reste tel quel : scope `(household, user)`, privé, préférences et
   habitudes de la personne. Un nouveau modèle `HouseholdFact` porte la mémoire
   **foyer** : scope `household`, partagé par tous les membres, faits stables sur
   la maison. Deux buckets séparés → l'agent sait toujours exactement où il écrit,
   et un fait privé ne peut pas se retrouver dans le partagé par simple bascule de
   flag.

2. **Le garde-fou de confidentialité est à l'ÉCRITURE, jamais à la lecture.**
   Un `HouseholdFact` est par construction visible de tout le foyer ; la seule
   protection fiable est donc de **ne jamais en créer un** à partir d'une source
   privée. Règle de routage : source **privée**
   (`Interaction.is_private=True`) → fait écrit dans le bucket **user du
   créateur** (`AgentMemory`) ; source **partagée** → `HouseholdFact`. Réutilise
   le pattern de requête déjà éprouvé au digest :
   `apps/agent/digest/collectors.py:74` →
   `.filter(Q(is_private=False) | Q(created_by=user))`.

3. **Deux surfaces de capture, un seul extracteur de règles.** (a) En **chat**,
   le mode auto existant (`service.py`, `MEMORY_AUTO_ADDENDUM`) est étendu pour
   que `manage_memory` cible l'un OU l'autre bucket ; le prompt décide selon la
   nature du fait (sur la personne → user ; sur la maison → foyer). (b) En **job
   de fond** (V2), un scan périodique reprend les interactions/projets récents et
   passe par un extracteur LLM dédié. Les deux surfaces partagent les mêmes
   règles éditoriales (ci-dessous).

4. **`HouseholdFact` = miroir foyer de `AgentMemory`.** Même forme de service
   (`save`/`update`/`forget`/`list`), même cap dur
   (`HOUSEHOLD_FACT_LIMIT = 50`, trim du plus ancien au-delà), même injection
   « notes, pas instructions » via un bloc jumeau du `MEMORY_BLOCK` protégé par
   `neutralize()`. On ajoute une liaison `source` (`chat`|`interaction`|`project`)
   + `source_ref` polymorphe optionnelle pour tracer l'origine.

5. **Trois règles éditoriales pour l'extracteur** (chat ET job) :
   - **Dédup explicite** : l'extracteur reçoit les faits déjà connus et répond
     `add` / `merge` (avec l'`id` remplacé) / `skip`. Sans ça, « la maison a une
     PAC » / « pompe à chaleur installée » / « PAC air-eau » deviennent 3 entrées.
   - **Biais conservateur** : dans le doute, ne rien mémoriser. On préfère un
     fait manquant à du bruit.
   - **Ne pas redonder la donnée structurée** : on mémorise le fait *implicite*
     (« la maison est chauffée par une PAC »), jamais la donnée déjà en base (le
     montant d'une facture, une date, une tâche — elles vivent dans leur table).

6. **Décisions produit actées.** Les `HouseholdFact` sont **éditables et
   supprimables par tout membre** du foyer (cohérent avec les autres modules ;
   pas d'asymétrie owner/member). Les **projets sont traités comme toujours
   partagés** en V2 : `Project` n'a pas de flag `is_private` aujourd'hui, on
   n'en ajoute pas — leurs faits peuvent devenir des `HouseholdFact`. Ajouter la
   confidentialité projet serait une story ultérieure si le besoin émerge.

7. **Job de fond idempotent, branché sur le scheduler existant.** Pas de nouveau
   scheduler : le scan s'accroche au tick déjà en place (pings/digest). Un
   curseur « dernier objet traité » garantit qu'un objet n'est extrait qu'une
   fois ; relancer le job ne recrée pas de doublons (curseur + dédup). Volume
   borné par passage pour éviter un batch LLM démesuré ; entités d'un module
   désactivé ignorées.

## Backlog

### Lot 1 — Socle `HouseholdFact` (V1)

| # | Story | Issue | État |
|---|---|---|---|
| 1.1 | Modèle `HouseholdFact` scopé foyer (`content`, `source`, `source_ref`, `confidence`) + service miroir de `memory.py` (cap 50) + API DRF list/create/update/destroy | [#346](https://github.com/jammindev/maisonnee/issues/346) | ⏳ |

### Lot 2 — Capture & injection en chat (V1)

| # | Story | Issue | État |
|---|---|---|---|
| 2.1 | Bloc « faits du foyer » injecté dans le system prompt (jumeau `MEMORY_BLOCK`, `neutralize()`) + `manage_memory` étendu pour cibler le bon bucket + routage par le prompt (perso → user, maison → foyer) | [#347](https://github.com/jammindev/maisonnee/issues/347) | ⏳ |

### Lot 3 — UI de gestion (V1)

| # | Story | Issue | État |
|---|---|---|---|
| 3.1 | Vue liste des faits du foyer, édition + suppression annulable (toast/undo), état vide pédagogique, distinction visible mémoire perso vs foyer | [#348](https://github.com/jammindev/maisonnee/issues/348) | ⏳ |

### Lot 4 — Extracteur de faits (V2)

| # | Story | Issue | État |
|---|---|---|---|
| 4.1 | Fonction d'extraction `(contenu, faits_connus)` → JSON strict `{"facts":[{action:add\|merge\|skip, content, replaces_id, confidence}]}`, best-effort, feature name dédié dans `AIUsageLog` | [#349](https://github.com/jammindev/maisonnee/issues/349) | ⏳ |

### Lot 5 — Job de fond & routage confidentialité (V2)

| # | Story | Issue | État |
|---|---|---|---|
| 5.1 | Job périodique idempotent (curseur) scannant `Interaction`/`Project`, extraction via lot 4, **routage confidentialité à l'écriture** (privé → bucket user du créateur, jamais `HouseholdFact`), test de non-régression explicite | [#350](https://github.com/jammindev/maisonnee/issues/350) | ⏳ |

## Limites V1 assumées

- **Capture chat uniquement en V1** : la capture automatique hors chat (job de
  fond) est en V2 (lots 4-5). En V1, un fait foyer n'est retenu que si l'agent le
  croise dans une conversation.
- **Projets toujours partagés** : pas de confidentialité projet — un fait extrait
  d'un projet ira en `HouseholdFact`. Acceptable tant que les projets restent des
  objets collectifs du foyer.
- **Extracteur LLM best-effort** : toute erreur (pas de clé, SDK absent, réseau,
  JSON invalide) → aucun fait écrit, pas de crash. On perd une extraction, jamais
  la donnée.
- **`source_ref` non requêtée** : la liaison d'origine sert la traçabilité et
  l'affichage, pas de filtre métier dessus (même limite que le carnet de
  rénovation).

## Fichiers clés (prévus)

- Backend : `apps/agent/models.py` (`HouseholdFact`) + migration, service
  `apps/agent/household_memory.py` (miroir de `memory.py`), extension
  `apps/agent/tools.py` (`manage_memory` + scope), `apps/agent/prompts.py`
  (bloc jumeau + addendum de routage), API + route dans `apps/agent/urls.py`,
  job de fond `apps/agent/facts/` (extracteur + scan + curseur) branché au tick
  existant, réglages `HOUSEHOLD_FACT_*` (`config/settings/base.py`).
- Frontend : `ui/src/lib/api/householdFacts.ts`, `ui/src/features/agent/`
  (vue de gestion des faits, distincte de la mémoire perso), route + entrée
  sidebar.
- i18n : clés de la vue de gestion dans en/fr/de/es ; faits stockés dans la
  langue du foyer.
- Tutoriels : mise à jour du guide agent (`/tutorials`) quand l'UI (lot 3) est
  livrée.
- Tests : socle `HouseholdFact` (django-drf), routage confidentialité
  (non-régression : source privée ne devient jamais un `HouseholdFact`),
  extracteur (dédup add/merge/skip, best-effort).
