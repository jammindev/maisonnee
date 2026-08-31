import { toLocalISODate } from '@/lib/format';

import type { WaterChartGranularity } from '@/lib/api/water';

/**
 * Ce qui se calcule avant de dessiner la consommation d'eau (#678, #682).
 *
 * À part du composant parce que c'est ici qu'est le fond — les intervalles
 * réellement mesurés, et surtout **ce qu'une barre a le droit d'affirmer** — et
 * que rien de tout ça n'a besoin d'un rendu pour être vérifié.
 *
 * **Le fait, c'est l'intervalle, jamais le jour.** Un relevé dit quel est
 * l'index du compteur, jamais quand l'eau a coulé. Entre deux relevés on connaît
 * une seule chose : le volume total, donc un débit *moyen*.
 *
 * D'où la granularité que l'écran propose. Les barres quotidiennes de #678
 * affichaient trente fois un seul fait — trente barres identiques à un litre
 * d'arrondi près, pour un relevé mensuel. Mais la barre n'était pas coupable :
 * **la journée l'était.** Un mois agrège un vrai laps de temps, ses hauteurs
 * diffèrent, et c'est l'unité dans laquelle un foyer pense — celle de sa
 * facture. Le module avait déjà supprimé l'heure avec exactement cet argument ;
 * le jour part pour la même raison.
 *
 * Reste la part d'étalement, et c'est ce que `qualifyBuckets` rend visible :
 * une barre qu'aucun relevé ne traverse est une **estimation**, et doit se
 * distinguer d'une mesure. Sans quoi on retomberait sur le défaut d'origine —
 * une division présentée avec la grammaire d'une observation.
 */

/** Un intervalle réellement mesuré : deux relevés consécutifs et ce qu'il y a entre. */
export interface WaterInterval {
  /** Premier relevé, inclus. */
  from: string;
  /** Second relevé, exclu — même convention que `water.services`. */
  to: string;
  days: number;
  litres: number;
  litresPerDay: number;
}

/** Ce qu'il faut d'un relevé ici — le reste du payload ne sert pas. */
interface ReadingLike {
  reading_date: string;
  index_m3: string;
}

/** Une barre, et ce qu'elle a le droit d'affirmer. */
export interface QualifiedBucket {
  ts: string;
  litres: number;
  /**
   * Aucun relevé ne tombe dans la période : sa hauteur vient **entièrement**
   * de l'étalement d'un intervalle plus long. C'est une estimation, pas une
   * mesure, et l'écran doit le montrer.
   */
  estimated: boolean;
  /**
   * Une partie de la période n'est couverte par aucun relevé — début ou fin de
   * série. La barre est alors plus basse que la réalité : sans marqueur, un
   * mois entamé le 5 se lit comme un mois économe.
   */
  partial: boolean;
  /** Les relevés qui encadrent une période estimée, pour le dire dans l'infobulle. */
  from?: string;
  to?: string;
}

function daysBetween(from: string, to: string): number {
  const [fy, fm, fd] = from.split('-').map(Number);
  const [ty, tm, td] = to.split('-').map(Number);
  const start = new Date(fy, fm - 1, fd).getTime();
  const end = new Date(ty, tm - 1, td).getTime();
  return Math.round((end - start) / 86_400_000);
}

function addDays(day: string, offset: number): string {
  const [year, month, date] = day.split('-').map(Number);
  return toLocalISODate(new Date(year, month - 1, date + offset));
}

/**
 * Les intervalles réellement mesurés, du plus ancien au plus récent.
 *
 * L'API sert les relevés du plus récent au plus ancien : on retrie ici plutôt
 * que de dépendre d'un ordre que l'appelant pourrait changer. Une paire qui
 * recule ou qui retombe sur le même jour est ignorée — le serializer l'interdit
 * déjà, et on ne fait jamais confiance en silence (même garde que le service).
 */
export function buildIntervals(readings: ReadingLike[]): WaterInterval[] {
  const sorted = [...readings].sort((a, b) => a.reading_date.localeCompare(b.reading_date));
  const intervals: WaterInterval[] = [];
  for (let i = 0; i < sorted.length - 1; i += 1) {
    const prev = sorted[i];
    const curr = sorted[i + 1];
    const days = daysBetween(prev.reading_date, curr.reading_date);
    const litres = Math.round((Number(curr.index_m3) - Number(prev.index_m3)) * 1000);
    if (days <= 0 || litres < 0) continue;
    intervals.push({
      from: prev.reading_date,
      to: curr.reading_date,
      days,
      litres,
      litresPerDay: litres / days,
    });
  }
  return intervals;
}

/**
 * Combien de jours de la fenêtre sont réellement couverts par un relevé.
 *
 * Sert à moyenner : diviser le total de la période par la largeur de la fenêtre
 * annoncerait un débit trop faible dès qu'un bout de mois n'a pas été relevé.
 * On ne moyenne que sur ce qu'on sait.
 */
export function coveredDays(intervals: WaterInterval[], from: string, to: string): number {
  const endExclusive = addDays(to, 1);
  return intervals.reduce((total, interval) => {
    const start = interval.from > from ? interval.from : from;
    const stop = interval.to < endExclusive ? interval.to : endExclusive;
    const days = daysBetween(start, stop);
    return total + (days > 0 ? days : 0);
  }, 0);
}

/** Bornes calendaires d'un bucket, depuis le `ts` que renvoie le serveur. */
function bucketRange(ts: string, granularity: WaterChartGranularity): { start: string; end: string } {
  const start = ts.slice(0, 10);
  const [year, month] = start.split('-').map(Number);
  const end =
    granularity === 'year'
      ? `${year}-12-31`
      : toLocalISODate(new Date(year, month, 0)); // jour 0 du mois suivant = dernier du mois
  return { start, end };
}

/**
 * Ce que chaque barre a le droit d'affirmer.
 *
 * **Le volume n'est jamais recalculé ici.** Il vient du serveur, seule
 * définition du consommé (`water.services.consumption_summary`) : deux
 * définitions d'un même compteur finissent toujours par diverger, et c'est
 * l'utilisateur qui arbitre. On ne fait que qualifier.
 */
export function qualifyBuckets(
  buckets: { ts: string; total_l: number }[],
  intervals: WaterInterval[],
  readings: ReadingLike[],
  granularity: WaterChartGranularity,
): QualifiedBucket[] {
  return buckets.map(({ ts, total_l }) => {
    const { start, end } = bucketRange(ts, granularity);
    const hasReading = readings.some((r) => r.reading_date >= start && r.reading_date <= end);
    const covered = coveredDays(intervals, start, end);
    const span = daysBetween(start, end) + 1;
    // L'intervalle qui porte la période, quand elle n'en traverse qu'un seul :
    // c'est lui qu'on cite quand la barre est une estimation.
    const source = intervals.find((i) => i.from <= start && end < i.to);
    return {
      ts,
      litres: total_l,
      estimated: !hasReading && covered > 0,
      partial: covered < span,
      from: source?.from,
      to: source?.to,
    };
  });
}
