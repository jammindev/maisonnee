import * as React from 'react';
import { useTranslation } from 'react-i18next';
import {
  CartesianGrid,
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
import type { WaterReading } from '@/lib/api/water';

import {
  buildIntervals,
  buildRateRows,
  buildTicks,
  intervalCovering,
  readingDayKeys,
  type TickResolution,
  type WaterInterval,
} from './rateCurve';

/**
 * Le débit d'eau du foyer dans le temps — la courbe en marches (#678).
 *
 * Remplace les barres quotidiennes, qui affichaient N fois un seul fait : entre
 * deux relevés, la « consommation du mardi » n'était pas une mesure mais une
 * division. Trente barres identiques à un litre d'arrondi près, pour un seul
 * relevé mensuel. Même défaut que les barres de stock de #575, même correction.
 *
 * Trois partis pris, tous du métier :
 *
 * 1. **Un escalier, pas une droite.** Contrairement à `StockLevelChart` — un
 *    stock se vide en continu, donc interpoler y est honnête — on ne trace pas
 *    ici un niveau mais un *débit moyen*, et cette moyenne est la seule chose
 *    connue sur tout l'intervalle. Une pente laisserait croire à une tendance
 *    qu'aucun relevé n'atteste. C'est le raisonnement de `BalanceLineChart`,
 *    appliqué à un débit.
 * 2. **Les relevés sont marqués, le reste ne l'est pas.** Un point sur chaque
 *    relevé : ce sont les seuls faits. Le palier entre deux points est une
 *    moyenne, et se lit comme telle.
 * 3. **Un trou reste un trou.** Hors de tout intervalle, la ligne s'interrompt
 *    au lieu de retomber à zéro — « on ne sait pas » et « rien consommé » ne
 *    sont pas la même phrase.
 *
 * Le composant est local à l'eau : `ConsumptionBarChart` reste juste pour
 * l'électricité (vraies données infra-journalières) et pour l'argent (dépenses
 * discrètes), et n'est pas touché.
 */

const RATE_COLOR = 'hsl(var(--chart-2))';

interface WaterRateChartProps {
  readings: WaterReading[];
  /** Bornes de la fenêtre affichée, incluses (`YYYY-MM-DD`). */
  from: string;
  to: string;
  /** Résolution des graduations — dérivée de la largeur de la fenêtre. */
  tickResolution: TickResolution;
  /** Température sur l'axe de droite, quand le foyer l'a activée. */
  overlay?: ConsumptionChartOverlay;
}

export default function WaterRateChart({
  readings,
  from,
  to,
  tickResolution,
  overlay,
}: WaterRateChartProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const intervals = React.useMemo(() => buildIntervals(readings), [readings]);
  const rows = React.useMemo(() => buildRateRows(intervals, from, to), [intervals, from, to]);
  const ticks = React.useMemo(() => buildTicks(from, to, tickResolution), [from, to, tickResolution]);
  const readingDays = React.useMemo(() => readingDayKeys(readings, from, to), [readings, from, to]);

  const data = React.useMemo(() => {
    const overlayByTs = new Map((overlay?.points ?? []).map((p) => [p.ts.slice(0, 10), p.value]));
    return rows.map((row) => ({
      ...row,
      ...(overlay ? { [overlay.key]: overlayByTs.get(row.ts.slice(0, 10)) ?? null } : {}),
    }));
  }, [rows, overlay]);

  const renderReadingDot = React.useCallback(
    (props: { cx?: number; cy?: number; payload?: { ts?: string } }) => {
      const { cx, cy, payload } = props;
      const key = `${payload?.ts ?? ''}-${cx}`;
      if (cx == null || cy == null || !payload?.ts || !readingDays.has(payload.ts)) {
        return <g key={key} />;
      }
      return (
        <circle
          key={key}
          cx={cx}
          cy={cy}
          r={4}
          fill={RATE_COLOR}
          stroke="hsl(var(--card))"
          strokeWidth={2}
        />
      );
    },
    [readingDays],
  );

  // L'infobulle raconte l'intervalle, pas le jour survolé : c'est l'intervalle
  // qui a été mesuré, et sa durée est ce qui rend le débit interprétable.
  const renderTooltip = React.useCallback(
    ({ active, label }: { active?: boolean; label?: string | number }) => {
      if (!active || label == null) return null;
      const ts = String(label);
      const interval: WaterInterval | undefined = intervalCovering(intervals, ts);
      const temp = overlay
        ? (overlay.points.find((p) => p.ts.slice(0, 10) === ts.slice(0, 10))?.value ?? null)
        : null;
      return (
        <div className="rounded-lg border border-border bg-card p-2 text-xs shadow-sm">
          <p className="pb-1 font-medium text-foreground">
            {formatLabel(ts, tickResolution === 'day' ? 'day' : 'month', locale)}
          </p>
          {interval ? (
            <>
              <p className="text-foreground">
                {t('water.chart.rate')} :{' '}
                <span className="font-medium">
                  {Math.round(interval.litresPerDay).toLocaleString(appLocale())}{' '}
                  {t('water.chart.rateUnit')}
                </span>
              </p>
              <p className="pt-0.5 text-muted-foreground">
                {t('water.chart.intervalDetail', {
                  volume: (interval.litres / 1000).toLocaleString(appLocale(), {
                    maximumFractionDigits: 3,
                  }),
                  days: interval.days,
                })}
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">{t('water.chart.noReadingHere')}</p>
          )}
          {temp !== null && (
            <p className="pt-0.5 text-muted-foreground">
              {overlay?.label} : {temp} {overlay?.unit}
            </p>
          )}
        </div>
      );
    },
    [intervals, overlay, locale, tickResolution, t],
  );

  return (
    <div className="h-64 w-full sm:h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis
            dataKey="ts"
            ticks={ticks}
            tickFormatter={(ts: string) => formatTick(ts, tickResolution, locale)}
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false}
            axisLine={{ stroke: 'hsl(var(--border))' }}
            interval="preserveStartEnd"
            minTickGap={16}
          />
          {/* Ancré à zéro : un débit se lit contre l'absence de consommation. */}
          <YAxis
            yAxisId="main"
            domain={[0, 'auto']}
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false}
            axisLine={false}
            width={56}
            unit={` ${t('water.chart.rateUnitShort')}`}
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
          <Tooltip
            cursor={{ stroke: 'hsl(var(--muted-foreground))', strokeWidth: 1 }}
            content={renderTooltip}
          />
          {overlay && (
            <Legend
              formatter={(value: string) =>
                value === overlay.key ? overlay.label : t('water.chart.rate')
              }
              wrapperStyle={{ fontSize: 12 }}
            />
          )}
          <Line
            yAxisId="main"
            type="stepAfter"
            dataKey="rate"
            stroke={RATE_COLOR}
            strokeWidth={2}
            dot={renderReadingDot}
            activeDot={{ r: 5 }}
            connectNulls={false}
            isAnimationActive={false}
          />
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
  );
}
