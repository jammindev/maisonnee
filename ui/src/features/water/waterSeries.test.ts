import { describe, expect, it } from 'vitest';

import { buildIntervals, coveredDays, qualifyBuckets } from './waterSeries';

const reading = (reading_date: string, index_m3: string) => ({ reading_date, index_m3 });
const bucket = (ts: string, total_l: number) => ({ ts: `${ts}T00:00:00`, total_l });

// Cadence réaliste : mensuelle en hiver, un trou de trois mois au printemps.
const READINGS = [
  reading('2026-01-05', '1000.000'),
  reading('2026-02-08', '1007.200'),
  reading('2026-03-07', '1014.100'),
  reading('2026-06-14', '1046.900'),
  reading('2026-07-12', '1069.400'),
];

describe('buildIntervals', () => {
  it('turns consecutive readings into one interval each', () => {
    const intervals = buildIntervals([
      reading('2026-03-01', '1000.000'),
      reading('2026-04-01', '1010.000'),
    ]);
    expect(intervals).toHaveLength(1);
    expect(intervals[0]).toMatchObject({ from: '2026-03-01', to: '2026-04-01', days: 31 });
    expect(intervals[0].litres).toBe(10_000);
    expect(intervals[0].litresPerDay).toBeCloseTo(10_000 / 31, 6);
  });

  it('orders by date whatever the input order (the API serves newest first)', () => {
    const intervals = buildIntervals([...READINGS].reverse());
    expect(intervals.map((i) => i.from)).toEqual([
      '2026-01-05', '2026-02-08', '2026-03-07', '2026-06-14',
    ]);
  });

  it('needs two readings to know anything at all', () => {
    expect(buildIntervals([reading('2026-03-01', '1000.000')])).toEqual([]);
    expect(buildIntervals([])).toEqual([]);
  });

  it('skips a pair that goes backwards or lands on the same day', () => {
    expect(
      buildIntervals([reading('2026-03-01', '1000.000'), reading('2026-04-01', '990.000')]),
    ).toEqual([]);
  });
});

describe('coveredDays', () => {
  it('counts only the days a reading actually covers', () => {
    const intervals = buildIntervals([
      reading('2026-03-10', '1000.000'),
      reading('2026-03-20', '1005.000'),
    ]);
    expect(coveredDays(intervals, '2026-03-01', '2026-03-31')).toBe(10);
  });

  it('is zero when nothing overlaps — never divides the total by the window width', () => {
    const intervals = buildIntervals([
      reading('2026-01-01', '1000.000'),
      reading('2026-02-01', '1005.000'),
    ]);
    expect(coveredDays(intervals, '2026-06-01', '2026-06-30')).toBe(0);
  });
});

describe('qualifyBuckets — ce que la barre a le droit d’affirmer', () => {
  const intervals = buildIntervals(READINGS);
  const qualify = (ts: string, litres: number) =>
    qualifyBuckets([bucket(ts, litres)], intervals, READINGS, 'month')[0];

  it('un mois qui contient un relevé est mesuré', () => {
    const q = qualify('2026-02-01', 6800);
    expect(q.estimated).toBe(false);
    expect(q.partial).toBe(false);
  });

  it('un mois SANS relevé est estimé, et nomme les relevés qui l’encadrent', () => {
    // Avril : aucun relevé, sa valeur vient entièrement de l’étalement 7 mars → 14 juin.
    const q = qualify('2026-04-01', 9930);
    expect(q.estimated).toBe(true);
    expect(q.from).toBe('2026-03-07');
    expect(q.to).toBe('2026-06-14');
  });

  it('le premier mois est partiel — la série commence le 5', () => {
    // Le 1er au 4 janvier n’est couvert par rien : la barre est plus basse
    // que la réalité, et doit le dire au lieu de se lire comme un mois calme.
    const q = qualify('2026-01-01', 5700);
    expect(q.partial).toBe(true);
    expect(q.estimated).toBe(false);
  });

  it('le mois du dernier relevé est partiel lui aussi', () => {
    const q = qualify('2026-07-01', 8800);
    expect(q.partial).toBe(true);
  });

  it('un mois plein encadré par des relevés n’est ni estimé ni partiel', () => {
    const dense = [
      reading('2026-04-30', '1000.000'),
      reading('2026-05-15', '1005.000'),
      reading('2026-06-01', '1010.000'),
    ];
    const q = qualifyBuckets(
      [bucket('2026-05-01', 10_000)], buildIntervals(dense), dense, 'month',
    )[0];
    expect(q.estimated).toBe(false);
    expect(q.partial).toBe(false);
  });

  it('sait aussi qualifier une année', () => {
    const q = qualifyBuckets([bucket('2026-01-01', 104_300)], intervals, READINGS, 'year')[0];
    // 2026 contient des relevés, mais janvier avant le 5 et après le 12 juillet
    // ne sont couverts par rien.
    expect(q.estimated).toBe(false);
    expect(q.partial).toBe(true);
  });

  it('reporte le volume tel quel — la qualification ne recalcule jamais le chiffre', () => {
    // Le total du serveur reste la seule définition du « dépensé » (CLAUDE.md).
    expect(qualify('2026-04-01', 9930).litres).toBe(9930);
  });
});
