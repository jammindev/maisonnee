import * as React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { ConsumptionChartOverlay } from '@/components/charts/ConsumptionBarChart';
import { formatLabel, formatTick } from '@/components/charts/ticks';
import { appLocale } from '@/lib/format';
import type { WaterChartGranularity } from '@/lib/api/water';

import type { QualifiedBucket } from './waterSeries';

/**
 * La consommation d'eau du foyer, en m³ par mois (#682).
 *
 * Des barres, comme avant #678 — mais sur le **mois** et plus sur le jour. Le
 * défaut d'origine n'était pas la barre, c'était la journée : trente barres
 * identiques pour un relevé mensuel. Un mois agrège un vrai laps de temps, ses
 * hauteurs diffèrent, et c'est l'unité dans laquelle un foyer pense.
 *
 * La courbe de débit qui avait remplacé ces barres était *plus juste et moins
 * lisible* : un trait de 2px sur un axe 0–1000 n'a aucune matière visuelle, et
 * « 331 L/jour » n'est pas la question qu'on se pose devant sa facture. Une
 * lecture correcte que personne ne fait ne vaut pas mieux qu'une lecture fausse.
 *
 * **Ce qui rend les barres honnêtes sans les rendre illisibles :** une période
 * qu'aucun relevé ne traverse est dessinée en aplat clair, et l'infobulle nomme
 * les deux relevés dont elle est étalée. Une barre mesurée et une barre estimée
 * ne se ressemblent pas — c'est tout ce que le défaut d'origine réclamait.
 *
 * Local à l'eau : `ConsumptionBarChart` reste juste pour l'électricité (vraies
 * données infra-journalières) et pour l'argent (dépenses discrètes), et n'a pas
 * à porter la notion d'estimation.
 */

const WATER_COLOR = 'hsl(var(--chart-2))';

interface WaterVolumeChartProps {
  buckets: QualifiedBucket[];
  granularity: WaterChartGranularity;
  /** Température sur l'axe de droite, quand le foyer l'a activée. */
  overlay?: ConsumptionChartOverlay;
}

function toM3(litres: number): number {
  return Math.round(litres) / 1000;
}

export default function WaterVolumeChart({
  buckets,
  granularity,
  overlay,
}: WaterVolumeChartProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const data = React.useMemo(() => {
    const overlayByTs = new Map((overlay?.points ?? []).map((p) => [p.ts, p.value]));
    return buckets.map((b) => ({
      ts: b.ts,
      volume: toM3(b.litres),
      ...(overlay ? { [overlay.key]: overlayByTs.get(b.ts) ?? null } : {}),
    }));
  }, [buckets, overlay]);

  const byTs = React.useMemo(() => new Map(buckets.map((b) => [b.ts, b])), [buckets]);
  const hasApproximate = buckets.some((b) => b.estimated || b.partial);

  const formatDate = React.useCallback(
    (iso: string) =>
      new Date(`${iso}T12:00:00`).toLocaleDateString(locale, { day: 'numeric', month: 'long' }),
    [locale],
  );

  const renderTooltip = React.useCallback(
    ({ active, label }: { active?: boolean; label?: string | number }) => {
      if (!active || label == null) return null;
      const ts = String(label);
      const b = byTs.get(ts);
      if (!b) return null;
      const temp = overlay
        ? (overlay.points.find((p) => p.ts === ts)?.value ?? null)
        : null;
      return (
        <div className="max-w-64 rounded-lg border border-border bg-card p-2 text-xs shadow-sm">
          <p className="pb-1 font-medium capitalize text-foreground">
            {formatLabel(ts, granularity, locale)}
          </p>
          <p className="text-foreground">
            {t('water.chart.volume')} :{' '}
            <span className="font-medium">
              {toM3(b.litres).toLocaleString(appLocale(), { maximumFractionDigits: 1 })} m³
            </span>
          </p>
          {b.estimated && b.from && b.to && (
            <p className="pt-1 text-muted-foreground">
              {t('water.chart.estimatedFrom', {
                from: formatDate(b.from),
                to: formatDate(b.to),
              })}
            </p>
          )}
          {!b.estimated && b.partial && (
            <p className="pt-1 text-muted-foreground">{t('water.chart.partialPeriod')}</p>
          )}
          {temp !== null && (
            <p className="pt-0.5 text-muted-foreground">
              {overlay?.label} : {temp} {overlay?.unit}
            </p>
          )}
        </div>
      );
    },
    [byTs, overlay, granularity, locale, t, formatDate],
  );

  return (
    <div className="w-full">
      <div className="h-64 w-full sm:h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis
              dataKey="ts"
              tickFormatter={(ts: string) => formatTick(ts, granularity, locale)}
              tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
              tickLine={false}
              axisLine={{ stroke: 'hsl(var(--border))' }}
              interval="preserveStartEnd"
              minTickGap={8}
            />
            <YAxis
              yAxisId="main"
              tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
              tickLine={false}
              axisLine={false}
              width={48}
              unit=" m³"
            />
            {overlay && (
              <YAxis
                yAxisId="overlay"
                orientation="right"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                tickLine={false}
                axisLine={false}
                width={40}
                unit={` ${overlay.unit}`}
              />
            )}
            {/*
              Pas de `cursor` : dans un ComposedChart recharts le rend en trait
              vertical, l'affordance d'une courbe et non d'un histogramme. C'est
              la barre survolée qui se souligne (`activeBar`), ce qui préserve
              en plus son opacité — donc la distinction mesuré / estimé.
            */}
            <Tooltip cursor={false} content={renderTooltip} />
            {overlay && (
              <Legend
                formatter={(value: string) =>
                  value === overlay.key ? overlay.label : t('water.chart.volume')
                }
                wrapperStyle={{ fontSize: 12 }}
              />
            )}
            <Bar
              yAxisId="main"
              dataKey="volume"
              radius={[3, 3, 0, 0]}
              isAnimationActive={false}
              // Sans borne, une année seule s'étire sur toute la largeur de la
              // carte : une barre unique de 640px ne se lit plus comme une barre.
              maxBarSize={72}
              activeBar={{ stroke: WATER_COLOR, strokeWidth: 2 }}
            >
              {buckets.map((b) => (
                // Une estimation ne se dessine pas comme une mesure.
                <Cell
                  key={b.ts}
                  fill={WATER_COLOR}
                  fillOpacity={b.estimated ? 0.32 : b.partial ? 0.6 : 1}
                />
              ))}
            </Bar>
            {overlay && (
              <Line
                yAxisId="overlay"
                type="monotone"
                dataKey={overlay.key}
                stroke={overlay.color}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {/* L'aplat clair porte du sens : il se légende, il ne se devine pas. */}
      {hasApproximate && (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: WATER_COLOR, opacity: 0.32 }}
            />
            {t('water.chart.legendEstimated')}
          </span>
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: WATER_COLOR, opacity: 0.6 }}
            />
            {t('water.chart.legendPartial')}
          </span>
        </p>
      )}
    </div>
  );
}
