import { describe, expect, it } from 'vitest';

import { buildTemperatureOverlay } from './overlay';

const point = (date: string, temp_mean: number) => ({ date, temp_mean }) as never;

describe('buildTemperatureOverlay', () => {
  it('aligns a daily point on each daily bucket', () => {
    const buckets = [{ ts: '2026-03-01T12:00:00' }, { ts: '2026-03-02T12:00:00' }];
    const points = [point('2026-03-01', 8.4), point('2026-03-02', 9.1)];
    expect(buildTemperatureOverlay(buckets, points, 'day')).toEqual([
      { ts: '2026-03-01T12:00:00', value: 8.4 },
      { ts: '2026-03-02T12:00:00', value: 9.1 },
    ]);
  });

  it('drops a bucket the archive has no temperature for, instead of plotting a hole as zero', () => {
    const buckets = [{ ts: '2026-03-01T12:00:00' }, { ts: '2026-03-02T12:00:00' }];
    expect(buildTemperatureOverlay(buckets, [point('2026-03-01', 8.4)], 'day')).toEqual([
      { ts: '2026-03-01T12:00:00', value: 8.4 },
    ]);
  });

  it('averages per month when the buckets are months (électricité)', () => {
    const buckets = [{ ts: '2026-03-01T00:00:00' }];
    const points = [point('2026-03-01', 8), point('2026-03-02', 10), point('2026-03-03', 12)];
    expect(buildTemperatureOverlay(buckets, points, 'month')).toEqual([
      { ts: '2026-03-01T00:00:00', value: 10 },
    ]);
  });

  it('plots nothing for a decade — the window that is never fetched', () => {
    const buckets = [{ ts: '2026-01-01T12:00:00' }];
    expect(buildTemperatureOverlay(buckets, [point('2026-01-01', 5)], 'year')).toEqual([]);
  });
});
