import { useTranslation } from 'react-i18next';

import type { ConsumptionChartOverlay } from '@/components/charts/ConsumptionBarChart';
import type { WeatherHistoryPoint } from '@/lib/api/weather';
import type { Granularity } from '@/lib/period';
import { useActiveHousehold, useDisabledModules } from '@/lib/modules';

import { useWeatherHistory } from './hooks';

// Overlay only makes sense for day/month: daily archive points map 1:1 to days
// and average cleanly per month. Hour is too fine, year too broad (huge fetch).
const OVERLAY_GRANULARITIES: Granularity[] = ['day', 'month'];

/**
 * Align daily mean temperatures to the consumption buckets the page already has.
 * Keys on the ISO date prefix of each bucket's ``ts`` (``YYYY-MM-DD`` for day,
 * ``YYYY-MM`` for month), so it works whatever the module's ts format
 * (water is naive-midnight, electricity is tz-aware). Buckets with no matching
 * temperature are simply omitted from the line.
 */
export function buildTemperatureOverlay(
  buckets: { ts: string }[],
  points: WeatherHistoryPoint[],
  granularity: Granularity,
): { ts: string; value: number }[] {
  if (granularity === 'day') {
    const byDay = new Map(points.map((p) => [p.date, p.temp_mean]));
    return buckets
      .map((b) => ({ ts: b.ts, value: byDay.get(b.ts.slice(0, 10)) }))
      .filter((p): p is { ts: string; value: number } => p.value !== undefined);
  }
  if (granularity === 'month') {
    const sums = new Map<string, { total: number; n: number }>();
    for (const p of points) {
      const key = p.date.slice(0, 7);
      const acc = sums.get(key) ?? { total: 0, n: 0 };
      acc.total += p.temp_mean;
      acc.n += 1;
      sums.set(key, acc);
    }
    return buckets
      .map((b) => {
        const acc = sums.get(b.ts.slice(0, 7));
        return acc ? { ts: b.ts, value: Math.round((acc.total / acc.n) * 10) / 10 } : null;
      })
      .filter((p): p is { ts: string; value: number } => p !== null);
  }
  return [];
}

/**
 * Shared plumbing for the "show weather" overlay on the electricity/water
 * consumption charts (parcours 17 Lot 6). Returns whether the overlay is
 * available for the current household + granularity, and the ready-to-pass
 * ``overlay`` prop (undefined until data is in). The page owns the ``show``
 * toggle state (its session key differs) and renders the toggle button.
 */
export function useTemperatureOverlay(opts: {
  from: string;
  to: string;
  granularity: Granularity;
  buckets: { ts: string }[];
  show: boolean;
}): { available: boolean; overlay: ConsumptionChartOverlay | undefined } {
  const { t } = useTranslation();
  const { household } = useActiveHousehold();
  const { disabled } = useDisabledModules();

  const configured =
    !disabled.has('weather') && household?.latitude != null && household?.longitude != null;
  const supported = OVERLAY_GRANULARITIES.includes(opts.granularity);
  const available = Boolean(configured && supported);

  const enabled = available && opts.show && opts.buckets.length > 0;
  const { data } = useWeatherHistory({ date_from: opts.from, date_to: opts.to }, enabled);

  const points = enabled && data?.points
    ? buildTemperatureOverlay(opts.buckets, data.points, opts.granularity)
    : [];

  const overlay: ConsumptionChartOverlay | undefined =
    enabled && points.length > 0
      ? {
          key: '__temp__',
          label: t('weather.overlay.temperature'),
          color: 'hsl(var(--chart-4))',
          unit: '°C',
          points,
        }
      : undefined;

  return { available, overlay };
}
