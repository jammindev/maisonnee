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
- **Granularités** : l'API accepte `day|month|year` ; la **page** n'offre que `month|year` (#682, voir plus bas).

## Réutilisation frontend (extraite à l'occasion de ce module)

- `ui/src/components/charts/ConsumptionBarChart.tsx` : **chart générique partagé** (barres empilées Recharts, séries paramétrées `{key,label,color}`, unité paramétrée) — consommé par `electricity/ConsumptionChart.tsx` (wrapper cadrans/kWh) et par les trois écrans de la famille argent. **L'eau ne l'utilise plus** depuis #678 : elle a besoin d'une notion d'estimation que les quatre autres écrans n'ont pas à porter. Voir juste en dessous.
- `ui/src/lib/period.ts` : helpers de fenêtre de période (`isoDate`, `periodRange`, `shiftAnchor`, `periodLabel`) extraits de `ConsumptionTab` — partagés eau/électricité.
- Clés i18n partagées `consumption.*` (granularity, previousPeriod, nextPeriod, overPeriod, noData) — déplacées depuis `electricity.consumption.*`.
- Page : pattern standard Feature page (PageHeader, FilterPill + `useSessionState`, skeleton `useDelayedLoading`, EmptyState, `useDeleteWithUndo`).

## Le graphe — des barres mensuelles, et l'estimé se voit (#678 puis #682)

`WaterVolumeChart` + `waterSeries.ts` (fonctions pures, testées sans rendu).

**Le défaut d'origine (#678).** La page affichait des barres **quotidiennes**
issues de la proratisation de `consumption_summary`. Un foyer qui relève son
compteur une fois par mois voyait **30 barres strictement identiques** — 333 ou
334 litres, le litre d'écart étant du bruit d'arrondi cumulatif. Trente
observations dessinées pour **une** mesure.

**La correction qui a raté (#679), et pourquoi elle a raté.** Le premier
correctif a remplacé les barres par une courbe de débit en marches (L/jour) :
plus juste sur la résolution, et **nettement moins lisible**. Un trait de 2px sur
un axe 0–1000 n'a aucune matière visuelle, et « 331 L/jour » n'est pas la
question qu'on se pose devant sa facture — un foyer pense en m³ par mois. La
leçon vaut au-delà de cet écran : **une lecture correcte que personne ne fait ne
vaut pas mieux qu'une lecture fausse.** L'analyse avait cadré les trois formes
proposées sur l'honnêteté de la résolution, et aucune sur la lisibilité.

**Ce qui était vraiment coupable : la journée, pas la barre.** Un mois agrège un
vrai laps de temps, ses hauteurs diffèrent, personne ne lit « avril = 10 m³ »
comme une mesure indépendante d'avril, et c'est l'unité de la facture. Le module
avait déjà écarté l'heure à sa création avec exactement cet argument ; le jour
part pour la même raison. `WaterChartGranularity` = `month | year`.

**Ce que le tracé garantit, et pourquoi :**

- **Une barre qu'aucun relevé ne traverse est une estimation**, dessinée en aplat
  clair, et l'infobulle nomme les deux relevés dont elle est étalée. C'est ce qui
  garde les barres honnêtes sans les rendre illisibles — sans ce marqueur on
  retomberait sur le défaut de #678, une division présentée avec la grammaire
  d'une observation.
- **Une période partiellement couverte se signale aussi** (début ou fin de série).
  Sans ça un mois entamé le 5 se lit comme un mois économe, alors que la barre est
  simplement plus basse que la réalité.
- **`qualifyBuckets` ne recalcule jamais le volume** : il vient du serveur, seule
  définition du consommé. Deux définitions d'un même compteur divergent toujours,
  et c'est l'utilisateur qui arbitre. On ne fait que **qualifier**.
- **`coveredDays` borne la moyenne** : diviser le total par la largeur de la
  fenêtre annoncerait un débit trop faible dès qu'un bout de mois n'est pas relevé.
- **Pas de `cursor` d'infobulle.** Dans un `ComposedChart`, recharts le rend en
  trait vertical — l'affordance d'une courbe, pas d'un histogramme. C'est la barre
  survolée qui se souligne (`activeBar`), ce qui préserve en plus son opacité, donc
  la distinction mesuré / estimé.
- **`maxBarSize`** : sans borne, une année seule s'étire sur toute la largeur de la
  carte, et une barre unique de 640px ne se lit plus comme une barre.

**La liste des relevés dit l'intervalle, pas l'index.** Elle affichait
« 1104,3 m³ », l'index brut : ce nombre ne se compare qu'au relevé précédent, et
c'est justement cette soustraction qu'on demandait au lecteur de faire de tête.
Chaque ligne porte donc le volume et le débit de l'intervalle qui s'y achève ;
l'index reste en retrait, parce que c'est lui qu'on relit sur le compteur. La
ligne reste **le relevé** et non l'intervalle — éditer et supprimer agissent sur
un objet, et un intervalle n'en est pas un.

**`WaterGranularity` reste plus large que `WaterChartGranularity`** : l'API
accepte toujours `day`, dont `dashboard/WaterCard` se sert pour sa sparkline sur
30 jours. Cette sparkline porte le même défaut en miniature (elle est plate quand
les relevés sont mensuels) — hors périmètre de #682 — suivi en #683.

Régressions : `ui/src/features/water/waterSeries.test.ts` (13 cas, dont la
qualification mesuré / estimé / partiel) et `ui/src/features/weather/overlay.test.ts`.

## Agent (`apps/water/apps.py::ready()`)

- `WritableSpec('water_reading')` : create (« j'ai relevé 1250 sur le compteur d'eau », `reading_date` défaut = aujourd'hui, virgule décimale acceptée) + update (`index_m3`, `reading_date`) — les deux via les services. Undo front : `UNDO_HANDLERS` / `UPDATE_UNDO_HANDLERS` dans `ui/src/features/agent/hooks.ts`.
- `ListableSpec('water_reading')` : filtres `date_from` / `date_to` — la consommation se lit comme delta entre deux relevés (pas d'`amount_of` : un index n'est pas un montant).
- Pas de `SearchableSpec` : rien de textuel à indexer sur un relevé.
- Descriptions des tools étendues dans `apps/agent/tools.py` (create/update/list) — seule retouche dans `apps/agent/`.

## Limitations connues / V2 possibles

- Un seul compteur d'eau par foyer (pas d'entité compteur). Si un second compteur devient nécessaire, introduire un modèle `WaterMeter` sur le modèle électricité.
- Pas de coût € (pas de tarif eau) ; pas d'import de données fournisseur.
- Si l'utilisateur veut une vue « depuis toujours », la navigation décennale du mode année la couvre.
