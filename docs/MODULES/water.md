# Module — water

> Créé : 2026-07-07. Rôle : suivre la **consommation d'eau** du foyer par relevés manuels du compteur (une date + un index m³), avec les mêmes graphs et la même navigation de période que le module électricité — sans en dupliquer le code.

## État synthétique

- **Backend** : Présent (`apps/water/` — 1 modèle, volontairement minimal)
- **Frontend** : Complet dans `ui/src/features/water/` (page unique, chart partagé)
- **Locales (en/fr/de/es)** : ok (namespace `water.*` + namespace partagé `consumption.*`)
- **Tests** : `apps/water/tests/` (serializers, views, services, agent) + E2E `e2e/water.spec.ts`
- **Migrations** : 1

## Modèles & API

- `WaterReading` (`HouseholdScopedModel`) : `reading_date` (DateField), `index_m3` (Decimal 12,3), unique `(household, reading_date)`. **Pas d'entité compteur, pas de cadran, pas de tarif, pas d'import** — simplification volontaire vs électricité : un foyer = un compteur d'eau implicite.
- Endpoints : `/api/water/readings/` (CRUD), `GET /api/water/consumption/summary/?granularity=day|month|year&date_from=&date_to=`
- Permissions : `IsHouseholdMember` (pattern trackers, pas le permission custom électricité)
- Validation (serializer) : index ≥ 0, monotonie (jamais inférieur au relevé précédent ni supérieur au suivant), un relevé max par date.

## Architecture — décisions

- **Pas de table dérivée** : contrairement à l'électricité (`ConsumptionRecord` régénéré à chaque écriture), la consommation eau est **calculée à la volée** dans `services.consumption_summary` — les relevés sont date-only et peu nombreux, un recalcul par requête est trivial. Même contrat de proratisation : le delta entre deux relevés consécutifs est réparti sur `[date_prev, date_curr)` en litres entiers avec arrondi cumulatif (la somme des parts vaut exactement le delta).
- **Litres entiers dans l'API** (`total_l`), conversion m³ côté UI — miroir exact du contrat Wh/kWh de l'électricité.
- **Source de vérité des écritures** : `apps/water/services.py` — `create_water_reading` / `update_water_reading` passent par `WaterReadingSerializer` ; le viewset (`perform_create`/`perform_update`) **et** les handlers agent appellent ces services. Le delete n'a pas de service (aucun état dérivé à rafraîchir).
- **Granularités** : `day|month|year` seulement — pas de vue horaire (relevés date-only).

## Réutilisation frontend (extraite à l'occasion de ce module)

- `ui/src/components/charts/ConsumptionBarChart.tsx` : **chart générique partagé** (barres empilées Recharts, séries paramétrées `{key,label,color}`, unité paramétrée) — consommé par `electricity/ConsumptionChart.tsx` (wrapper cadrans/kWh) et par les trois écrans de la famille argent. **L'eau ne l'utilise plus** depuis #678, voir juste en dessous.
- `ui/src/lib/period.ts` : helpers de fenêtre de période (`isoDate`, `periodRange`, `shiftAnchor`, `periodLabel`) extraits de `ConsumptionTab` — partagés eau/électricité.
- Clés i18n partagées `consumption.*` (granularity, previousPeriod, nextPeriod, overPeriod, noData) — déplacées depuis `electricity.consumption.*`.
- Page : pattern standard Feature page (PageHeader, FilterPill + `useSessionState`, skeleton `useDelayedLoading`, EmptyState, `useDeleteWithUndo`).

## Le graphe — un débit en marches, jamais des barres (#678)

`WaterRateChart` + `rateCurve.ts` (fonctions pures, testées sans rendu — même
découpage que `stock/levelCurve.ts`).

**Le défaut corrigé.** La page affichait des barres quotidiennes issues de la
proratisation de `consumption_summary`. En granularité `jour` (celle par défaut,
fenêtre = un mois), un foyer qui relève son compteur une fois par mois voyait
**30 barres strictement identiques** — 333 ou 334 litres, le litre d'écart étant
du bruit d'arrondi cumulatif. Trente observations dessinées pour **une** mesure.
La proratisation reste juste pour un **total** ; c'est la grammaire des barres
qui ment, puisqu'une barre annonce une quantité mesurée discrète. L'électricité a
de vraies données infra-journalières (import Enedis), l'eau n'a que des relevés
manuels espacés et irréguliers : **le même graphe ne pouvait pas servir les deux.**

C'est le défaut déjà corrigé sur le stock (`StockLevelChart`, #622, qui
remplaçait les barres de #575) — et le raisonnement s'énonce pareil : *un relevé
dit quel est l'index, jamais quand l'eau a coulé.*

**Ce que le tracé garantit, et pourquoi :**

- **Un escalier (`stepAfter`), pas une droite.** Entre deux relevés on ne connaît
  qu'un débit *moyen*, constant par construction. Une pente laisserait lire une
  tendance qu'aucun relevé n'atteste. C'est le raisonnement de `BalanceLineChart`
  (« un solde tient jusqu'à ce que quelque chose le bouge ») et non celui de
  `StockLevelChart`, où interpoler est honnête parce qu'un stock se vide en continu.
- **Un débit (L/jour), pas un volume.** Les relevés sont irréguliers : une barre
  par intervalle rendrait 22 m³ en trois mois et 22 m³ en un mois à la même
  hauteur, alors que le second est un débit trois fois supérieur. Ramener au jour
  est la seule normalisation qui compare des intervalles de durées différentes
  sans mentir. Le volume reste dans le titre de la carte et dans l'infobulle.
- **Les relevés portent une pastille, le reste non.** Les points sont les faits ;
  le palier entre deux points est une moyenne, et doit se lire comme telle.
- **Le dernier relevé ferme son palier.** Les intervalles sont mi-ouverts, donc un
  relevé intermédiaire appartient à celui qu'il *ouvre* (la marche tombe pile sur
  lui). Le tout dernier n'ouvre rien : sans point à sa date, la ligne s'arrêtait la
  veille et **le relevé le plus récent — celui qu'on vient de saisir — n'avait pas
  de pastille.** `coveredDays` reste mi-ouvert de son côté : compter des jours et
  fermer un segment sont deux questions, elles ont deux fonctions.
- **Un trou reste un trou.** Hors de tout intervalle la ligne s'interrompt
  (`connectNulls={false}`) au lieu de retomber à zéro : « on ne sait pas » et
  « rien consommé » ne sont pas la même phrase. Quatrième occurrence de la règle du
  vide qui n'est pas une valeur (`inflow_nature`, `Document.purpose`, parcours 26).
- **Les graduations sont calculées, pas déduites.** La grille est quotidienne (pour
  que l'axe respecte la durée réelle des intervalles) ; laisser recharts choisir
  afficherait « avr. » une fois par jour visible sur une fenêtre d'un an.
- **L'overlay météo s'aligne au jour** (`pointGranularity: 'day'`), tout en restant
  *borné* par la fenêtre : c'est elle qui décide de la taille du fetch, pas la
  résolution des points. Sans ce découplage, chaque jour d'un mois recevait la
  moyenne du mois — une ligne de température en escalier, que l'archive ne dit pas.

Régressions : `ui/src/features/water/rateCurve.test.ts` (16 cas) et
`ui/src/features/weather/overlay.test.ts`. Les trois pastilles `jour|mois|année`
restent des **sélecteurs de fenêtre** (un mois / un an / une décennie) — c'est déjà
ce que faisait `periodRange`, le bucketing n'en était qu'un effet de bord.

## Agent (`apps/water/apps.py::ready()`)

- `WritableSpec('water_reading')` : create (« j'ai relevé 1250 sur le compteur d'eau », `reading_date` défaut = aujourd'hui, virgule décimale acceptée) + update (`index_m3`, `reading_date`) — les deux via les services. Undo front : `UNDO_HANDLERS` / `UPDATE_UNDO_HANDLERS` dans `ui/src/features/agent/hooks.ts`.
- `ListableSpec('water_reading')` : filtres `date_from` / `date_to` — la consommation se lit comme delta entre deux relevés (pas d'`amount_of` : un index n'est pas un montant).
- Pas de `SearchableSpec` : rien de textuel à indexer sur un relevé.
- Descriptions des tools étendues dans `apps/agent/tools.py` (create/update/list) — seule retouche dans `apps/agent/`.

## Limitations connues / V2 possibles

- Un seul compteur d'eau par foyer (pas d'entité compteur). Si un second compteur devient nécessaire, introduire un modèle `WaterMeter` sur le modèle électricité.
- Pas de coût € (pas de tarif eau) ; pas d'import de données fournisseur.
- Si l'utilisateur veut une vue « depuis toujours », la navigation décennale du mode année la couvre.
