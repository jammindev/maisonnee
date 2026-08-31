import { describe, expect, it } from 'vitest';

import { last30Days, lastCompleteMonths } from './waterWindows';

describe('last30Days', () => {
  it('borne les 30 derniers jours, bornes incluses', () => {
    expect(last30Days(new Date(2026, 7, 31))).toEqual({
      from: '2026-08-01',
      to: '2026-08-31',
    });
  });

  it('traverse un changement de mois sans se tromper', () => {
    expect(last30Days(new Date(2026, 2, 5))).toEqual({ from: '2026-02-03', to: '2026-03-05' });
  });
});

describe('lastCompleteMonths', () => {
  it('s’arrête au dernier mois RÉVOLU — jamais au mois en cours', () => {
    // Le 31 août, août n'est pas fini : l'inclure ferait plonger la sparkline
    // à droite tous les mois, ce qui se lit « on consomme de moins en moins ».
    expect(lastCompleteMonths(new Date(2026, 7, 31), 12)).toEqual({
      from: '2025-08-01',
      to: '2026-07-31',
    });
  });

  it('le 1er du mois ne compte pas le mois qui vient de commencer', () => {
    expect(lastCompleteMonths(new Date(2026, 0, 1), 3)).toEqual({
      from: '2025-10-01',
      to: '2025-12-31',
    });
  });

  it('gère une fenêtre qui remonte sur février', () => {
    expect(lastCompleteMonths(new Date(2026, 2, 15), 1)).toEqual({
      from: '2026-02-01',
      to: '2026-02-28',
    });
  });
});

describe('les bornes ne basculent jamais avec le fuseau', () => {
  it('minuit local reste le même jour (règle toISOString du projet)', () => {
    // `new Date(2026, 7, 1)` est minuit à Paris = 2026-07-31T22:00Z. Un
    // `toISOString().slice(0,10)` renverrait « 2026-07-31 » et déclencherait la
    // requête sur un jour de trop, à chaque bout de la fenêtre.
    const midnightLocal = new Date(2026, 7, 1);
    expect(midnightLocal.getDate()).toBe(1);
    expect(lastCompleteMonths(new Date(2026, 8, 15), 1)).toEqual({
      from: '2026-08-01',
      to: '2026-08-31',
    });
  });
});
