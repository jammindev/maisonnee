import * as React from 'react';
import { ChevronLeft, ChevronRight, Droplets, Pencil, Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/design-system/button';
import { Card } from '@/design-system/card';
import { FilterPill } from '@/design-system/filter-pill';
import CardActions, { type CardAction } from '@/components/CardActions';
import EmptyState from '@/components/EmptyState';
import PageHeader from '@/components/PageHeader';
import WaterVolumeChart from './WaterVolumeChart';
import WeatherOverlayToggle from '@/features/weather/WeatherOverlayToggle';
import { useTemperatureOverlay } from '@/features/weather/overlay';
import { appLocale } from '@/lib/format';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { useDeleteWithUndo } from '@/lib/useDeleteWithUndo';
import { useSessionState } from '@/lib/useSessionState';
import { isoDate, periodLabel, periodRange, shiftAnchor } from '@/lib/period';
import type { WaterChartGranularity, WaterReading } from '@/lib/api/water';
import { useQueryClient } from '@tanstack/react-query';
import {
  useDeleteWaterReading,
  useWaterConsumptionSummary,
  useWaterReadings,
  waterKeys,
} from './hooks';
import WaterReadingDialog from './WaterReadingDialog';
import { buildIntervals, coveredDays, qualifyBuckets, type WaterInterval } from './waterSeries';

// Le jour est parti avec #682 : les relevés sont manuels et espacés, cette
// résolution n'existe pas dans les données (l'heure était partie pour la même
// raison dès la création du module).
const GRANULARITIES: WaterChartGranularity[] = ['month', 'year'];

function formatM3(litres: number): string {
  return (litres / 1000).toLocaleString(appLocale(), { maximumFractionDigits: 3 });
}

// ── Readings list ─────────────────────────────────────────────────────────────

/**
 * Un relevé, et surtout **ce qui s'est passé depuis le précédent**.
 *
 * La liste affichait l'index brut du compteur — « 1104,3 m³ ». Ce nombre ne dit
 * rien à un humain : il ne se compare qu'au relevé d'avant, et c'est justement
 * cette soustraction qu'on demandait au lecteur de faire de tête. La ligne
 * porte donc le volume et le débit de l'intervalle qui s'achève ici ; l'index
 * reste, en retrait, parce que c'est lui qu'on relit sur le compteur.
 *
 * La ligne reste **le relevé** et non l'intervalle : éditer et supprimer
 * agissent sur un objet, et un intervalle n'en est pas un.
 */
interface ReadingRowProps {
  reading: WaterReading;
  /** L'intervalle qui se termine à ce relevé — absent pour le tout premier. */
  interval?: WaterInterval;
  locale: string;
  onEdit: () => void;
  onDelete: () => void;
  t: (key: string, opts?: Record<string, unknown>) => string;
}

function ReadingRow({ reading, interval, locale, onEdit, onDelete, t }: ReadingRowProps) {
  const actions: CardAction[] = [
    { label: t('common.edit'), icon: Pencil, onClick: onEdit },
    { label: t('common.delete'), icon: Trash2, onClick: onDelete, variant: 'danger' },
  ];
  const shortDate = (iso: string) =>
    new Date(`${iso}T12:00:00`).toLocaleDateString(locale, { day: 'numeric', month: 'short' });

  return (
    <Card className="p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className="text-sm font-medium">
              {new Date(`${reading.reading_date}T12:00:00`).toLocaleDateString(locale, {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
              })}
            </span>
            {interval ? (
              <span className="text-sm text-muted-foreground">
                {t('water.reading.since', { date: shortDate(interval.from) })}
              </span>
            ) : (
              <span className="text-sm text-muted-foreground">{t('water.reading.first')}</span>
            )}
          </div>
          <p className="pt-0.5 text-xs text-muted-foreground">
            {t('water.reading.index', {
              value: Number(reading.index_m3).toLocaleString(locale),
            })}
          </p>
        </div>
        {interval && (
          <div className="shrink-0 text-right">
            <p className="text-sm font-medium">
              {(interval.litres / 1000).toLocaleString(locale, { maximumFractionDigits: 1 })} m³
            </p>
            <p className="text-xs text-muted-foreground">
              {Math.round(interval.litresPerDay).toLocaleString(locale)} {t('water.chart.rateUnit')}
            </p>
          </div>
        )}
        <CardActions actions={actions} />
      </div>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function WaterPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const qc = useQueryClient();

  const { data: readings = [], isLoading: readingsLoading } = useWaterReadings();
  const [storedGranularity, setGranularity] = useSessionState<WaterChartGranularity>(
    'water.granularity',
    'month',
  );
  // Une session ouverte avant #682 peut encore porter 'day' : on la ramène au
  // mois plutôt que de demander au serveur un découpage que l'écran n'offre plus.
  const granularity: WaterChartGranularity = GRANULARITIES.includes(storedGranularity)
    ? storedGranularity
    : 'month';
  const [anchorIso, setAnchorIso] = useSessionState<string>('water.anchor', isoDate(new Date()));

  const anchor = React.useMemo(() => new Date(`${anchorIso}T00:00:00`), [anchorIso]);
  const { from, to } = periodRange(anchor, granularity);

  const { data: summary, isLoading: summaryLoading } = useWaterConsumptionSummary({
    granularity,
    date_from: from,
    date_to: to,
  });

  const [readingDialogOpen, setReadingDialogOpen] = React.useState(false);
  const [editingReading, setEditingReading] = React.useState<WaterReading | undefined>(undefined);

  const deleteReading = useDeleteWaterReading();
  const { deleteWithUndo } = useDeleteWithUndo({
    label: t('water.reading.deleted'),
    onDelete: (id: string) => deleteReading.mutateAsync(id),
  });

  // Une seule dérivation des intervalles pour la page ; le graphe rappelle la
  // même fonction pure sur les mêmes relevés (cf. `rateCurve.ts`).
  const intervals = React.useMemo(() => buildIntervals(readings), [readings]);

  // Ce que chaque barre a le droit d'affirmer — mesurée, estimée, ou partielle.
  const chartBuckets = React.useMemo(
    () => qualifyBuckets(summary?.buckets ?? [], intervals, readings, granularity),
    [summary, intervals, readings, granularity],
  );

  const [showWeather, setShowWeather] = useSessionState<boolean>('water.showWeather', false);
  const { available: weatherAvailable, overlay: weatherOverlay } = useTemperatureOverlay({
    from,
    to,
    granularity,
    buckets: chartBuckets,
    show: showWeather,
  });

  const showSkeleton = useDelayedLoading(readingsLoading);
  if (showSkeleton) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    );
  }

  if (!readingsLoading && readings.length === 0) {
    return (
      <>
        <PageHeader title={t('water.title')} description={t('water.description')} />
        <EmptyState
          icon={Droplets}
          title={t('water.emptyTitle')}
          description={t('water.emptyDescription')}
          action={{
            label: t('water.reading.new'),
            onClick: () => { setEditingReading(undefined); setReadingDialogOpen(true); },
          }}
        />
        <WaterReadingDialog
          open={readingDialogOpen}
          onOpenChange={setReadingDialogOpen}
          existing={editingReading}
        />
      </>
    );
  }

  // Le résumé serveur reste le prédicat : un bucket existe exactement quand un
  // intervalle recoupe la fenêtre. Deux relevés sont le minimum pour consommer.
  const hasData = (summary?.buckets.length ?? 0) > 0;
  const needsSecondReading = readings.length < 2;
  // L'intervalle qui s'achève à chaque relevé — indexé pour la liste du bas.
  const intervalEndingAt = new Map(intervals.map((i) => [i.to, i]));
  const daysCovered = coveredDays(intervals, from, to);
  const averageRate = daysCovered > 0 ? (summary?.total_l ?? 0) / daysCovered : null;

  return (
    <div className="space-y-4">
      <PageHeader title={t('water.title')} description={t('water.description')}>
        <Button
          size="sm"
          onClick={() => { setEditingReading(undefined); setReadingDialogOpen(true); }}
        >
          <Plus className="mr-1.5 h-4 w-4" />
          {t('water.reading.new')}
        </Button>
      </PageHeader>

      {/* Granularity + period navigation */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {GRANULARITIES.map((g) => (
            <FilterPill key={g} active={granularity === g} onClick={() => setGranularity(g)}>
              {t(`consumption.granularity.${g}`)}
            </FilterPill>
          ))}
          {weatherAvailable && (
            <WeatherOverlayToggle active={showWeather} onToggle={setShowWeather} />
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            aria-label={t('consumption.previousPeriod')}
            onClick={() => setAnchorIso(isoDate(shiftAnchor(anchor, granularity, -1)))}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-32 text-center text-sm capitalize">{periodLabel(anchor, granularity, locale)}</span>
          <Button
            variant="ghost"
            size="sm"
            aria-label={t('consumption.nextPeriod')}
            onClick={() => setAnchorIso(isoDate(shiftAnchor(anchor, granularity, 1)))}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Chart card */}
      <Card className="p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2 pb-2">
          <p className="text-lg font-semibold">
            {formatM3(summary?.total_l ?? 0)} m³
            <span className="pl-1.5 text-sm font-normal text-muted-foreground">
              {t('consumption.overPeriod')}
            </span>
          </p>
          {averageRate !== null && (
            <p className="text-sm text-muted-foreground">
              {t('water.chart.averageRate', {
                rate: Math.round(averageRate).toLocaleString(locale),
                unit: t('water.chart.rateUnit'),
              })}
            </p>
          )}
        </div>
        {summaryLoading && !summary ? (
          <div className="h-64 animate-pulse rounded-lg bg-muted sm:h-80" />
        ) : hasData && summary ? (
          <WaterVolumeChart
            buckets={chartBuckets}
            granularity={granularity}
            overlay={weatherOverlay}
          />
        ) : (
          <div className="flex h-64 items-center justify-center px-4 text-center text-sm text-muted-foreground sm:h-80">
            {needsSecondReading ? t('water.chart.needsTwoReadings') : t('consumption.noData')}
          </div>
        )}
      </Card>

      {/* Recent readings */}
      {readings.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">
            {t('water.reading.recentTitle')}
          </h3>
          {readings.slice(0, 8).map((reading) => (
            <ReadingRow
              key={reading.id}
              reading={reading}
              interval={intervalEndingAt.get(reading.reading_date)}
              locale={locale}
              onEdit={() => { setEditingReading(reading); setReadingDialogOpen(true); }}
              onDelete={() => {
                deleteWithUndo(reading.id, {
                  onRemove: () => qc.setQueryData<WaterReading[]>(
                    waterKeys.readings(),
                    (old) => old?.filter((r) => r.id !== reading.id),
                  ),
                  onRestore: () => qc.setQueryData<WaterReading[]>(
                    waterKeys.readings(),
                    (old) => (old ? [...old, reading] : [reading]),
                  ),
                });
              }}
              t={t}
            />
          ))}
        </div>
      ) : null}

      <WaterReadingDialog
        open={readingDialogOpen}
        onOpenChange={setReadingDialogOpen}
        existing={editingReading}
      />
    </div>
  );
}
