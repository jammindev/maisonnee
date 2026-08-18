import { describe, expect, it } from 'vitest';

import type { NotificationItem } from '@/lib/api/notifications';

import { buildBellPreview } from './preview';

/** Le serveur sert la liste en `-created_at` : le premier élément est le plus récent. */
function notif(id: string, isRead: boolean): NotificationItem {
  return {
    id,
    type: 'stock_low',
    title: id,
    body: '',
    payload: {},
    url: '',
    is_read: isRead,
    read_at: isRead ? '2026-08-13T10:00:00Z' : null,
    created_at: '2026-08-13T09:00:00Z',
  };
}

const ids = (list: NotificationItem[]) => list.map((n) => n.id);

describe("buildBellPreview — l'aperçu montre ce que le badge annonce", () => {
  /**
   * La régression qui fonde le reste.
   *
   * Le badge compte tous les non-lus ; l'aperçu ne montrait que les plus
   * récents *par date*. Cinq lues arrivées après un non-lu le rendaient
   * introuvable dans la cloche pendant que le badge affichait « 1 » — un
   * compteur et son aperçu avec deux définitions.
   */
  it('remonte un non-lu que cinq lues plus récentes chassaient de la troncature', () => {
    const list = [
      notif('lue-1', true),
      notif('lue-2', true),
      notif('lue-3', true),
      notif('lue-4', true),
      notif('lue-5', true),
      notif('non-lue', false),
    ];

    expect(ids(buildBellPreview(list, 5))).toContain('non-lue');
    expect(ids(buildBellPreview(list, 5))[0]).toBe('non-lue');
  });

  /**
   * Lire n'est pas supprimer. Le modèle a déjà `deleted_at` pour écarter, et
   * c'est un geste explicite : vider l'aperçu à la lecture ferait disparaître
   * la ligne sous le curseur au moment même où on la clique.
   */
  it('garde les lues dans l\'aperçu, derrière les non-lues', () => {
    const list = [notif('lue-1', true), notif('non-lue', false), notif('lue-2', true)];

    expect(ids(buildBellPreview(list, 5))).toEqual(['non-lue', 'lue-1', 'lue-2']);
  });

  it('conserve l\'ordre chronologique à l\'intérieur de chaque groupe', () => {
    const list = [
      notif('lue-recente', true),
      notif('non-lue-recente', false),
      notif('lue-ancienne', true),
      notif('non-lue-ancienne', false),
    ];

    expect(ids(buildBellPreview(list, 4))).toEqual([
      'non-lue-recente',
      'non-lue-ancienne',
      'lue-recente',
      'lue-ancienne',
    ]);
  });

  it('ne rend jamais plus de lignes que la borne', () => {
    const list = Array.from({ length: 12 }, (_, i) => notif(`n${i}`, i % 2 === 0));

    expect(buildBellPreview(list, 5)).toHaveLength(5);
  });

  it('ne tombe pas sur une liste vide', () => {
    expect(buildBellPreview([], 5)).toEqual([]);
  });

  describe("l'ordre est figé tant que le menu est ouvert", () => {
    /**
     * Sans ce gel, cliquer un non-lu le fait passer derrière les autres
     * non-lus : la ligne suivante monte sous le curseur et le second clic
     * tombe à côté. C'est la même règle que la jambe sémantique de la
     * recherche — on ajoute, on ne réordonne pas ce que l'utilisateur lit.
     */
    it('garde une ligne en place quand elle vient de passer en lue', () => {
      const before = [notif('a', false), notif('b', false), notif('c', true)];
      const pinned = ids(buildBellPreview(before, 5));

      const after = [notif('a', true), notif('b', false), notif('c', true)];

      expect(ids(buildBellPreview(after, 5, pinned))).toEqual(['a', 'b', 'c']);
    });

    it('relit toujours l\'état frais de la ligne épinglée', () => {
      const pinned = ['a', 'b'];
      const after = [notif('a', true), notif('b', false)];

      expect(buildBellPreview(after, 5, pinned)[0].is_read).toBe(true);
    });

    it('laisse tomber une ligne épinglée qui a disparu, et comble le trou', () => {
      const pinned = ['disparue', 'a'];
      const list = [notif('a', false), notif('b', true)];

      expect(ids(buildBellPreview(list, 5, pinned))).toEqual(['a', 'b']);
    });

    it('ajoute une arrivée après ce qui est déjà affiché', () => {
      const pinned = ['a', 'b'];
      const list = [notif('arrivee', false), notif('a', true), notif('b', true)];

      expect(ids(buildBellPreview(list, 5, pinned))).toEqual(['a', 'b', 'arrivee']);
    });

    it('ne duplique jamais une ligne épinglée deux fois', () => {
      const list = [notif('a', false)];

      expect(ids(buildBellPreview(list, 5, ['a', 'a']))).toEqual(['a']);
    });
  });
});
