import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { Card, CardTitle } from '@/design-system/card';
import Sparkline from '@/components/Sparkline';
import { pushBack } from '@/lib/backNavigation';
import { appLocale } from '@/lib/format';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { useWaterConsumptionSummary, useWaterReadings } from '@/features/water/hooks';
import { last30Days, lastCompleteMonths } from './waterWindows';

const WINDOW_DAYS = 30;
const SPARKLINE_MONTHS = 12;

/**
 * La carte Eau du tableau de bord — un débit moyen, et douze mois de tendance.
 *
 * **La sparkline était plate** (#683). Elle demandait `granularity=day` sur
 * trente jours : avec des relevés manuels mensuels — la cadence normale — la
 * proratisation renvoyait trente valeurs identiques, donc une ligne rigoureusement
 * horizontale qui affirmait « ta consommation ne bouge pas ». C'est le défaut de
 * #678 en miniature, resté hors périmètre de #682 pour garder ce correctif-là
 * relisable.
 *
 * Deux fenêtres, parce que les deux chiffres ne répondent pas à la même question
 * (voir `waterWindows.ts`) : un débit sur 30 jours glissants pour le chiffre de
 * tête, des mois **révolus** pour la tendance — un mois entamé est mécaniquement
 * plus bas, et l'inclure ferait plonger la courbe à droite tous les mois.
 *
 * Le total vient du serveur dans les deux cas : `total_l` ne dépend pas du
 * découpage, donc demander le mois plutôt que le jour ne change pas le chiffre
 * de tête — ça évite juste de redemander une résolution qui n'existe pas.
 */

export default function WaterCard() {
  const { t } = useTranslation();
  const location = useLocation();
  const today = new Date();
  const recent = last30Days(today);
  const trend = lastCompleteMonths(today, SPARKLINE_MONTHS);

  const { data: readings = [], isLoading: readingsLoading } = useWaterReadings();
  const hasHistory = readings.length >= 2;
  const { data: summary, isLoading: summaryLoading } = useWaterConsumptionSummary({
    granularity: 'month',
    date_from: recent.from,
    date_to: recent.to,
    enabled: hasHistory,
  });
  const { data: history } = useWaterConsumptionSummary({
    granularity: 'month',
    date_from: trend.from,
    date_to: trend.to,
    enabled: hasHistory,
  });
  const showSkeleton = useDelayedLoading(readingsLoading || (hasHistory && summaryLoading));

  if (showSkeleton) return <Card className="h-36 animate-pulse bg-muted p-4" />;
  if (!hasHistory || !summary || summary.total_l === 0) return null;

  const avgPerDay = Math.round(summary.total_l / WINDOW_DAYS);
  // Deux mois suffisent à faire une tendance ; un seul point n'est qu'un trait.
  const points = (history?.buckets ?? []).map((b) => ({ t: b.ts, v: b.total_l }));

  return (
    <Link to="/app/water" state={pushBack(location)} className="group block h-full">
      <Card className="flex h-full flex-col p-4 transition-colors hover:border-border hover:bg-muted/20">
        <CardTitle className="text-sm text-muted-foreground">
          💧 {t('dashboard.metrics.water.title')}
        </CardTitle>
        <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          {t('dashboard.metrics.water.avg', { liters: avgPerDay })}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {t('dashboard.metrics.water.total', {
            m3: (summary.total_l / 1000).toLocaleString(appLocale(), { maximumFractionDigits: 1 }),
          })}
        </p>
        {points.length >= 2 && (
          <div className="mt-auto pt-3 text-primary">
            <Sparkline points={points} width={220} height={40} className="w-full" />
          </div>
        )}
      </Card>
    </Link>
  );
}
