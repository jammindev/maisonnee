import { toLocalISODate } from '@/lib/format';

/**
 * Ce qui se calcule avant de dessiner la courbe de débit de l'eau (#678).
 *
 * À part du composant parce que c'est ici qu'est le fond — le découpage en
 * intervalles réels, le débit moyen, le trou là où personne n'a relevé — et que
 * rien de tout ça n'a besoin d'un rendu pour être vérifié.
 *
 * **Le fait, c'est l'intervalle, jamais le jour.** Un relevé dit quel est
 * l'index du compteur, jamais quand l'eau a coulé. Entre deux relevés on connaît
 * une seule chose : le volume total, donc un débit *moyen*. Les barres
 * quotidiennes d'avant affichaient ce débit une fois par jour — trente barres
 * identiques pour une seule mesure, à un litre d'arrondi près. Même défaut que
 * les barres de stock de #575, corrigé de la même façon (`stock/levelCurve.ts`).
 *
 * **Pourquoi un débit et pas un volume.** Les relevés sont manuels, donc
 * irréguliers. Une barre par intervalle rendrait 22 m³ en trois mois et 22 m³ en
 * un mois à la même hauteur, alors que le second est un débit trois fois
 * supérieur. Ramener au jour est la seule normalisation qui compare des
 * intervalles de durées différentes sans mentir.
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

/** Une ligne du graphe : le débit qui tient ce jour-là, ou rien si nul relevé ne le couvre. */
export interface RateRow {
  ts: string;
  rate: number | null;
}

export type TickResolution = 'day' | 'month' | 'year';

/** Ce qu'il faut d'un relevé pour tracer la courbe — le reste du payload ne sert pas. */
interface ReadingLike {
  reading_date: string;
  index_m3: string;
}

/**
 * Clé d'axe stable, insensible au fuseau du navigateur.
 *
 * Midi local ne bascule jamais, quel que soit le décalage ou l'heure d'été —
 * c'est la règle `toISOString()` du projet, prise par l'autre bout, et le même
 * choix que `stock/levelCurve.ts`.
 */
export function dayKey(day: string): string {
  return `${day.slice(0, 10)}T12:00:00`;
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
 * Une ligne par jour de la fenêtre, portant le débit de l'intervalle qui la couvre.
 *
 * La grille est quotidienne pour que l'axe respecte la durée réelle — deux
 * relevés espacés de trois mois doivent occuper trois fois plus de largeur que
 * deux relevés espacés d'un mois. Ce n'est pas une résolution inventée : le
 * tracé est un escalier (`stepAfter`), donc la valeur *tient* visiblement d'un
 * relevé au suivant au lieu de se faire passer pour une mesure du jour.
 *
 * **`null` hors de tout intervalle, jamais zéro.** Avant le premier relevé et
 * après le dernier, l'app ne sait rien ; zéro dirait « aucune consommation »,
 * ce qui est une affirmation. Le trou se voit, et c'est le but — c'est la même
 * règle que le vide qui n'est pas une valeur (`inflow_nature`, `purpose`).
 *
 * **Le dernier relevé ferme le dernier palier.** Les intervalles sont
 * mi-ouverts — un relevé intermédiaire appartient à celui qu'il *ouvre*, ce qui
 * fait tomber la marche pile sur lui. Le tout dernier n'ouvre rien : sans point
 * à sa date, la ligne s'arrêtait la veille et le relevé le plus récent, celui
 * que l'utilisateur vient de saisir, n'avait pas de pastille. Fermer le segment
 * sur sa borne n'invente aucune journée — un intervalle va bien *jusqu'à* son
 * second relevé ; c'est `coveredDays` qui compte les jours, et lui reste
 * mi-ouvert.
 */
export function buildRateRows(intervals: WaterInterval[], from: string, to: string): RateRow[] {
  const rows: RateRow[] = [];
  const span = daysBetween(from, to);
  const last = intervals.length > 0 ? intervals[intervals.length - 1] : undefined;
  for (let offset = 0; offset <= span; offset += 1) {
    const day = addDays(from, offset);
    // Couverture [from, to) — même convention que `water.services.consumption_summary`.
    const covering =
      intervals.find((i) => i.from <= day && day < i.to) ??
      (last && day === last.to ? last : undefined);
    rows.push({ ts: dayKey(day), rate: covering ? covering.litresPerDay : null });
  }
  return rows;
}

/** L'intervalle qui couvre un jour donné — ce que l'infobulle raconte au survol. */
export function intervalCovering(intervals: WaterInterval[], ts: string): WaterInterval | undefined {
  const day = ts.slice(0, 10);
  return intervals.find((i) => i.from <= day && day < i.to);
}

/**
 * Les jours de la fenêtre qui portent un vrai relevé — eux seuls reçoivent un point.
 *
 * C'est ce qui rend la résolution des données lisible : les points sont les
 * faits, le trait entre deux points est une moyenne.
 */
export function readingDayKeys(readings: ReadingLike[], from: string, to: string): Set<string> {
  return new Set(
    readings
      .filter((r) => r.reading_date >= from && r.reading_date <= to)
      .map((r) => dayKey(r.reading_date)),
  );
}

/**
 * Les graduations de l'axe, calculées et non déduites.
 *
 * La grille étant quotidienne, laisser recharts choisir afficherait « avr. »
 * une fois par jour visible sur une fenêtre d'un an. On donne donc les
 * graduations en clair : chaque jour, chaque 1er du mois, ou chaque 1er janvier
 * selon la largeur de la fenêtre.
 */
export function buildTicks(from: string, to: string, resolution: TickResolution): string[] {
  const ticks: string[] = [];
  const span = daysBetween(from, to);
  for (let offset = 0; offset <= span; offset += 1) {
    const day = addDays(from, offset);
    const [, month, date] = day.split('-');
    if (resolution === 'day') ticks.push(dayKey(day));
    else if (resolution === 'month' && date === '01') ticks.push(dayKey(day));
    else if (resolution === 'year' && month === '01' && date === '01') ticks.push(dayKey(day));
  }
  return ticks;
}

/**
 * Combien de jours de la fenêtre sont réellement couverts par un relevé.
 *
 * Sert à moyenner : diviser le total de la période par la largeur de la fenêtre
 * annoncerait un débit trop faible dès qu'un bout de mois n'a pas été relevé.
 * On ne moyenne que sur ce qu'on sait.
 *
 * Se calcule sur les intervalles, jamais en comptant les lignes du graphe : le
 * tracé ferme son dernier palier sur la borne (voir `buildRateRows`), ce qui
 * ajouterait une journée au dénominateur et fausserait la moyenne. Compter et
 * dessiner sont deux questions, elles ont deux fonctions.
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
