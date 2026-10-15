import { describe, expect, it } from 'vitest';
import { apiErrorMessage } from './apiError';

const err = (data: unknown) => ({ response: { data } });

describe('apiErrorMessage', () => {
  it('rend le `detail` de DRF', () => {
    expect(apiErrorMessage(err({ detail: 'Trop de tentatives.' }))).toBe('Trop de tentatives.');
  });

  it('rend une erreur de champ, forme liste', () => {
    expect(apiErrorMessage(err({ file: ['Fichier trop volumineux (34 Mo).'] }))).toBe(
      'Fichier trop volumineux (34 Mo).',
    );
  });

  it('concatène plusieurs erreurs de champ', () => {
    expect(apiErrorMessage(err({ file: ['Type non supporté.'], name: ['Trop long.'] }))).toBe(
      'Type non supporté. Trop long.',
    );
  });

  it('préfère `detail` aux erreurs de champ', () => {
    expect(apiErrorMessage(err({ detail: 'Refusé.', file: ['Ignoré.'] }))).toBe('Refusé.');
  });

  // Une page nginx n'est pas un message : l'afficher noierait l'utilisateur
  // sous du HTML au lieu de lui laisser le repli de l'appelant.
  it('rejette une page HTML', () => {
    expect(apiErrorMessage(err('<html><body>413</body></html>'))).toBeNull();
  });

  it('rend null quand il n’y a rien à dire', () => {
    expect(apiErrorMessage(err({}))).toBeNull();
    expect(apiErrorMessage(err(undefined))).toBeNull();
    expect(apiErrorMessage(new Error('network'))).toBeNull();
    expect(apiErrorMessage(undefined)).toBeNull();
  });
});
