---
name: water_module_patterns
description: Patterns for writing E2E tests for the Water module (/app/water)
type: ui-patterns
---

# Water Module Patterns

## Route and feature location

- Page: `/app/water`
- Feature files: `ui/src/features/water/` (WaterPage.tsx, WaterReadingDialog.tsx, hooks.ts)
- API prefix: `/api/water/readings/`, `/api/water/consumption/summary/`

## French UI strings

| Key | French string |
|-----|--------------|
| `water.title` | "Eau" |
| `water.emptyTitle` | "Aucun relevé" |
| `water.reading.new` | "Nouveau relevé" |
| `water.reading.edit` | "Modifier le relevé" |
| `water.reading.recentTitle` | "Derniers relevés" |
| `water.reading.created` | "Relevé créé." |
| `water.reading.updated` | "Relevé modifié." |
| `water.reading.deleted` | "Relevé supprimé" |
| `common.save` | "Enregistrer" |
| `common.cancel` | "Annuler" |
| `common.edit` | "Modifier" |
| `common.delete` | "Supprimer" |
| `consumption.previousPeriod` | "Période précédente" |
| `consumption.nextPeriod` | "Période suivante" |
| `consumption.noData` | "Aucune donnée de consommation sur cette période." |

## Reading dialog field IDs

- `#water-reading-date` — `<input type="date">`
- `#water-reading-index` — `<input type="number" step="0.001">`

## Granularities (water only has 3, no "hour")

Filters: "Jour" / "Mois" / "Année" (no "Heure" tab unlike electricity).

## Index display pattern

`WaterReading.index_m3` is a string. It displays as `{Number(index_m3).toLocaleString(locale)} m³`.
With French locale: `1250.5` → `"1 250,5 m³"`. Use a regex: `/1\s*250[,.]?5?\s*m³/`.

## API helper pattern (no meter concept)

Water has no meter entity — readings belong directly to the household. Use these helpers:

```ts
async function apiCreateReading(page, readingDate, indexM3) {
  const token = await getAccessToken(page);
  const resp = await page.request.post('/api/water/readings/', {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: { reading_date: readingDate, index_m3: indexM3 },
  });
  return resp.json();
}

async function deleteAllReadingsViaApi(page) {
  const token = await getAccessToken(page);
  const resp = await page.request.get('/api/water/readings/', { headers: { Authorization: `Bearer ${token}` } });
  const body = await resp.json();
  const items = Array.isArray(body) ? body : (body.results ?? []);
  for (const item of items) {
    await page.request.delete(`/api/water/readings/${item.id}/`, { headers: { Authorization: `Bearer ${token}` } });
  }
}
```

Important: always call `await page.goto('/app/water')` BEFORE `deleteAllReadingsViaApi` so the JWT is loaded into localStorage first.

## Chart card locator

The total m³ is `page.locator('p.text-lg')` — same pattern as electricity consumption. Its text content includes `m³`.
The chart wrapper is `.recharts-wrapper` (same as electricity).

## Reading card structure (for CardActions)

Each reading row renders as a `<Card className="p-3">` with:
- date span + index span
- `<CardActions />` (last button in the card)

To click the CardActions menu from an index locator:
```ts
const indexLoc = page.getByText(/1\s*000\s*m³/).first();
const ancestor = indexLoc.locator('xpath=ancestor::*[4]');
await ancestor.locator('button').last().click();
await page.getByRole('menuitem', { name: 'Modifier' }).click();
```

## Monotonicity validation

The API returns a 400 with `{ index_m3: ["Index is lower than the previous reading."] }`.
The dialog catches it and displays `<p class="text-sm text-destructive">`.
Check: `await expect(page.locator('p.text-destructive')).toBeVisible()`.

## Test isolation strategy

Because the household has one global set of readings (no meter-scoping), tests must:
1. Navigate to `/app/water` first (loads JWT)
2. Call `deleteAllReadingsViaApi` to clear all existing readings
3. Create only the readings needed for this test via `apiCreateReading`
4. Reload the page to get fresh React state

This avoids monotonicity conflicts between tests.

## Worktree note

The worktree `feat-water-readings` does not ship a Python venv. A symlink is needed:
`ln -sf <main checkout>/venv <worktree>/venv`
