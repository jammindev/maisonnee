import { describe, expect, it } from 'vitest';

import {
  buildIntervals,
  buildRateRows,
  buildTicks,
  coveredDays,
  readingDayKeys,
} from './rateCurve';

const reading = (reading_date: string, index_m3: string) => ({ reading_date, index_m3 });

describe('buildIntervals', () => {
  it('turns consecutive readings into one interval each, never one per day', () => {
    // Le bug d'origine (#678) : un relevé mensuel produisait 30 barres.
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
    const intervals = buildIntervals([
      reading('2026-04-01', '1010.000'),
      reading('2026-03-01', '1000.000'),
      reading('2026-05-01', '1030.000'),
    ]);
    expect(intervals.map((i) => i.from)).toEqual(['2026-03-01', '2026-04-01']);
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

describe('buildRateRows', () => {
  it('holds one rate across the whole interval — a step, not 30 measurements', () => {
    const intervals = buildIntervals([
      reading('2026-03-01', '1000.000'),
      reading('2026-04-01', '1010.000'),
    ]);
    const rows = buildRateRows(intervals, '2026-03-01', '2026-03-31');
    expect(rows).toHaveLength(31);
    const rates = new Set(rows.map((r) => r.rate));
    expect(rates.size).toBe(1); // une seule valeur : c'est un palier
    expect([...rates][0]).toBeCloseTo(10_000 / 31, 6);
  });

  it('leaves a hole where no reading covers the day, instead of inventing zero', () => {
    // Rien avant le 10, rien après le 20 : l'app ne sait pas, et doit le montrer.
    const intervals = buildIntervals([
      reading('2026-03-10', '1000.000'),
      reading('2026-03-20', '1005.000'),
    ]);
    const rows = buildRateRows(intervals, '2026-03-01', '2026-03-31');
    expect(rows.find((r) => r.ts.startsWith('2026-03-05'))?.rate).toBeNull();
    expect(rows.find((r) => r.ts.startsWith('2026-03-25'))?.rate).toBeNull();
    expect(rows.find((r) => r.ts.startsWith('2026-03-15'))?.rate).toBeCloseTo(500, 6);
  });

  it('compares two intervals of different lengths by rate, not by volume', () => {
    // 22 m³ en 3 mois est un débit PLUS FAIBLE que 10 m³ en 1 mois.
    // C'est exactement ce que des barres de largeur égale lisaient à l'envers.
    const slow = buildIntervals([
      reading('2026-01-01', '0.000'),
      reading('2026-04-01', '22.000'),
    ]);
    const fast = buildIntervals([
      reading('2026-04-01', '22.000'),
      reading('2026-05-01', '32.000'),
    ]);
    expect(slow[0].litres).toBeGreaterThan(fast[0].litres);
    expect(slow[0].litresPerDay).toBeLessThan(fast[0].litresPerDay);
  });

  it('is timezone-proof — a browser west of the household never shifts a day', () => {
    const intervals = buildIntervals([
      reading('2026-03-01', '1000.000'),
      reading('2026-04-01', '1010.000'),
    ]);
    const rows = buildRateRows(intervals, '2026-03-01', '2026-03-03');
    // Midi local : aucun décalage horaire ne fait basculer la date.
    expect(rows.map((r) => r.ts)).toEqual([
      '2026-03-01T12:00:00',
      '2026-03-02T12:00:00',
      '2026-03-03T12:00:00',
    ]);
  });
});

describe('readingDayKeys', () => {
  it('marks only the days that carry a real reading', () => {
    const keys = readingDayKeys(
      [reading('2026-03-01', '1000.000'), reading('2026-04-01', '1010.000')],
      '2026-03-01',
      '2026-03-31',
    );
    expect(keys.has('2026-03-01T12:00:00')).toBe(true);
    expect(keys.has('2026-03-15T12:00:00')).toBe(false);
    expect(keys.has('2026-04-01T12:00:00')).toBe(false); // hors fenêtre
  });
});

describe('buildTicks', () => {
  it('labels days over a month, months over a year, years over a decade', () => {
    expect(buildTicks('2026-03-01', '2026-03-31', 'day').length).toBe(31);
    expect(buildTicks('2026-01-01', '2026-12-31', 'month')).toEqual(
      Array.from({ length: 12 }, (_, m) => `2026-${String(m + 1).padStart(2, '0')}-01T12:00:00`),
    );
    expect(buildTicks('2017-01-01', '2026-12-31', 'year')).toHaveLength(10);
  });

  it('never repeats a label — that is what a daily grid would do on a wide window', () => {
    const ticks = buildTicks('2026-01-01', '2026-12-31', 'month');
    expect(new Set(ticks).size).toBe(ticks.length);
  });
});

describe('coveredDays', () => {
  it('counts only the days a reading actually covers', () => {
    const intervals = buildIntervals([
      reading('2026-03-10', '1000.000'),
      reading('2026-03-20', '1005.000'),
    ]);
    // Couverture [10, 20) = 10 jours, sur une fenêtre de 31.
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

describe('le dernier relevé ferme le dernier palier', () => {
  const readings = [
    reading('2026-08-09', '1091.800'),
    reading('2026-08-26', '1104.300'),
  ];

  it('donne une valeur au jour du dernier relevé — sinon il n’a pas de pastille', () => {
    // Le relevé le plus récent est celui que l'utilisateur vient de saisir :
    // c'est le pire à faire disparaître du graphe.
    const intervals = buildIntervals(readings);
    const rows = buildRateRows(intervals, '2026-08-01', '2026-08-31');
    expect(rows.find((r) => r.ts.startsWith('2026-08-26'))?.rate).toBeCloseTo(12_500 / 17, 6);
    // ...et le lendemain, on ne sait de nouveau plus rien.
    expect(rows.find((r) => r.ts.startsWith('2026-08-27'))?.rate).toBeNull();
  });

  it('ne compte pas ce jour de fermeture dans la moyenne', () => {
    // 17 jours mesurés, pas 18 : fermer un segment n'ajoute pas une journée.
    const intervals = buildIntervals(readings);
    expect(coveredDays(intervals, '2026-08-01', '2026-08-31')).toBe(17);
  });

  it('la marche tombe sur le relevé qui l’ouvre, pas sur celui qui la ferme', () => {
    const intervals = buildIntervals([
      reading('2026-03-01', '1000.000'),
      reading('2026-04-01', '1010.000'),
      reading('2026-05-01', '1040.000'),
    ]);
    const rows = buildRateRows(intervals, '2026-03-01', '2026-05-31');
    const at = (d: string) => rows.find((r) => r.ts.startsWith(d))?.rate;
    expect(at('2026-03-31')).toBeCloseTo(10_000 / 31, 6);
    expect(at('2026-04-01')).toBeCloseTo(30_000 / 30, 6); // la hausse tombe pile sur le relevé
  });
});
