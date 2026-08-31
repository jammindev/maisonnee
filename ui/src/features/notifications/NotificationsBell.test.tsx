import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { AlertsSummary } from '@/lib/api/alerts';
import { EMPTY_ALERTS_SUMMARY } from '@/features/alerts/rows';
import NotificationsBell from './NotificationsBell';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key, i18n: { language: 'fr' } }) }));

const state = vi.hoisted(() => ({
  notifications: [] as Array<Record<string, unknown>>,
  unread: 0,
  alerts: null as AlertsSummary | null,
}));

const markAllRead = vi.hoisted(() => vi.fn());
const markRead = vi.hoisted(() => vi.fn());

vi.mock('./hooks', () => ({
  useNotifications: () => ({ data: state.notifications }),
  useUnreadCount: () => ({ data: state.unread }),
  useMarkAllRead: () => ({ mutate: markAllRead, isPending: false }),
  useMarkRead: () => ({ mutate: markRead }),
}));

vi.mock('@/features/alerts/hooks', () => ({
  useAlertsSummary: () => ({ data: state.alerts }),
}));

vi.mock('@/features/settings/hooks', () => ({
  useAcceptInvitation: () => ({ mutateAsync: vi.fn(), isPending: false, variables: undefined }),
  useDeclineInvitation: () => ({ mutateAsync: vi.fn(), isPending: false, variables: undefined }),
}));

function alertsWith(partial: Partial<AlertsSummary>): AlertsSummary {
  const summary = { ...EMPTY_ALERTS_SUMMARY, ...partial };
  const total = Object.values(summary).filter(Array.isArray).reduce((n, list) => n + list.length, 0);
  return { ...summary, total };
}

function overdueTask(id: string, title: string) {
  return {
    id,
    title,
    due_date: '2026-07-30',
    days_overdue: 3,
    entity_url: `/app/tasks/${id}`,
    severity: 'critical' as const,
  };
}

function expiringWarranty(id: string, title: string) {
  return {
    id,
    title,
    warranty_expires_on: '2026-09-01',
    days_remaining: 28,
    entity_url: `/app/equipment/${id}`,
    severity: 'warning' as const,
  };
}

beforeAll(() => {
  // Radix pilote son menu à la souris ; jsdom n'implémente pas la capture de pointeur.
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.scrollIntoView = () => {};
});

/** Le serveur sert la liste en `-created_at` : le premier élément est le plus récent. */
function notification(
  id: string,
  title: string,
  { read = false, url = '' }: { read?: boolean; url?: string } = {},
) {
  return {
    id,
    type: 'stock_low',
    title,
    body: '',
    payload: {},
    url,
    is_read: read,
    read_at: read ? '2026-08-13T10:00:00Z' : null,
    created_at: '2026-08-13T09:00:00Z',
  };
}

beforeEach(() => {
  state.notifications = [];
  state.unread = 0;
  state.alerts = null;
  markAllRead.mockClear();
  markRead.mockClear();
});

async function openBell() {
  const user = userEvent.setup({ pointerEventsCheck: 0 });
  render(<MemoryRouter><NotificationsBell /></MemoryRouter>);
  await user.click(screen.getByTestId('notifications-bell'));
  return user;
}

describe('NotificationsBell — les alertes du foyer', () => {
  /**
   * La régression qui fonde tout le reste.
   *
   * Une notification est un événement (lu/non-lu, écartable) ; une alerte est un
   * état recalculé qu'on ne peut pas écarter. Additionner les deux dans le badge
   * fabriquerait un compteur qui ne redescend jamais — et un compteur qui ne
   * redescend jamais devient du décor qu'on cesse de lire.
   */
  it("ne compte pas les alertes dans le badge des non-lus", async () => {
    state.unread = 0;
    state.alerts = alertsWith({
      overdue_tasks: [overdueTask('t1', 'Tondre la pelouse'), overdueTask('t2', 'Relever le compteur')],
    });

    render(<MemoryRouter><NotificationsBell /></MemoryRouter>);

    expect(screen.queryByTestId('notifications-bell-badge')).not.toBeInTheDocument();
    expect(screen.getByTestId('notifications-bell-alerts-dot')).toBeInTheDocument();
  });

  it("n'affiche pas de point quand le foyer n'a aucune alerte", async () => {
    state.unread = 2;
    state.alerts = alertsWith({});

    render(<MemoryRouter><NotificationsBell /></MemoryRouter>);

    expect(screen.getByTestId('notifications-bell-badge')).toHaveTextContent('2');
    expect(screen.queryByTestId('notifications-bell-alerts-dot')).not.toBeInTheDocument();
  });

  it("mène de l'alerte à l'entité concernée", async () => {
    state.alerts = alertsWith({ overdue_tasks: [overdueTask('t1', 'Tondre la pelouse')] });

    await openBell();

    expect(screen.getByRole('link', { name: /Tondre la pelouse/ })).toHaveAttribute(
      'href',
      '/app/tasks/t1',
    );
  });

  // L'aperçu est tronqué : c'est l'urgent qui doit survivre à la troncature.
  it("montre les alertes critiques d'abord, et pas plus de trois", async () => {
    state.alerts = alertsWith({
      expiring_warranties: [
        expiringWarranty('w1', 'Garantie four'),
        expiringWarranty('w2', 'Garantie lave-linge'),
        expiringWarranty('w3', 'Garantie chaudière'),
      ],
      overdue_tasks: [overdueTask('t1', 'Tondre la pelouse')],
    });

    await openBell();

    const shown = screen.getAllByTestId('bell-alert-row').map((row) => row.textContent);
    expect(shown).toHaveLength(3);
    expect(shown[0]).toContain('Tondre la pelouse');
    expect(shown.join(' ')).not.toContain('Garantie chaudière');
  });

  /** Les deux listes ne partagent ni cycle de vie ni compteur. */
  it("garde les alertes visibles quand il n'y a aucune notification", async () => {
    state.notifications = [];
    state.alerts = alertsWith({ overdue_tasks: [overdueTask('t1', 'Tondre la pelouse')] });

    await openBell();

    expect(screen.getByText('notifications.empty')).toBeInTheDocument();
    expect(screen.getByText('Tondre la pelouse')).toBeInTheDocument();
  });

  it("n'offre pas de « tout marquer lu » pour des alertes", async () => {
    state.unread = 0;
    state.alerts = alertsWith({ overdue_tasks: [overdueTask('t1', 'Tondre la pelouse')] });

    await openBell();

    expect(screen.queryByText('notifications.markAllRead')).not.toBeInTheDocument();
  });
});

describe("NotificationsBell — l'aperçu tient la promesse du badge", () => {
  /**
   * La régression : l'aperçu était un `slice` de la liste triée par date, donc
   * l'état lu/non-lu n'entrait pas dans le choix des lignes affichées — alors
   * qu'il fonde le badge. Cinq lues plus récentes suffisaient à rendre un
   * non-lu introuvable dans la cloche pendant que le badge annonçait « 1 ».
   */
  it('montre le non-lu que cinq lues plus récentes chassaient de la troncature', async () => {
    state.unread = 1;
    state.notifications = [
      notification('r1', 'Relevé importé', { read: true }),
      notification('r2', 'Bob a rejoint le foyer', { read: true }),
      notification('r3', 'Stock bas : farine', { read: true }),
      notification('r4', 'Alerte météo', { read: true }),
      notification('r5', 'Corvée du poulailler', { read: true }),
      notification('u1', 'Tondre la pelouse est en retard'),
    ];

    await openBell();

    expect(screen.getByText('Tondre la pelouse est en retard')).toBeInTheDocument();
  });

  /**
   * Lire n'est pas supprimer : le modèle a `deleted_at` pour écarter, et c'est
   * un geste explicite. Vider l'aperçu à la lecture ferait disparaître la ligne
   * sous le curseur au moment même où on la clique.
   */
  it("garde les lues dans l'aperçu, derrière les non-lues", async () => {
    state.unread = 1;
    state.notifications = [
      notification('r1', 'Relevé importé', { read: true }),
      notification('u1', 'Tondre la pelouse est en retard'),
    ];

    await openBell();

    const rows = screen.getAllByTestId('bell-notification-row').map((row) => row.textContent);
    expect(rows[0]).toContain('Tondre la pelouse est en retard');
    expect(rows[1]).toContain('Relevé importé');
  });

  /**
   * Le même objet menait quelque part sur `/app/notifications` (`NotificationCard`
   * ouvre `notification.url`) et nulle part dans la cloche, qui se contentait de
   * marquer lu. Une notification qui annonce sans mener oblige le lecteur à
   * refaire la recherche qu'elle venait de faire pour lui.
   */
  it('mène à ce qu\'elle annonce', async () => {
    state.unread = 1;
    state.notifications = [
      notification('u1', 'Tondre la pelouse est en retard', { url: '/app/tasks/t1' }),
    ];

    await openBell();

    expect(screen.getByRole('link', { name: /Tondre la pelouse/ })).toHaveAttribute(
      'href',
      '/app/tasks/t1',
    );
  });

  it('marque lu en ouvrant, sans attendre un second geste', async () => {
    state.unread = 1;
    state.notifications = [
      notification('u1', 'Tondre la pelouse est en retard', { url: '/app/tasks/t1' }),
    ];

    const user = await openBell();
    await user.click(screen.getByRole('link', { name: /Tondre la pelouse/ }));

    expect(markRead).toHaveBeenCalledWith('u1');
  });

  it("n'invente pas de lien quand la notification ne mène nulle part", async () => {
    state.unread = 1;
    state.notifications = [notification('u1', 'Stock bas : farine')];

    await openBell();

    expect(screen.queryByRole('link', { name: /farine/ })).not.toBeInTheDocument();
    expect(screen.getByText('Stock bas : farine')).toBeInTheDocument();
  });

  /** Une invitation porte ses propres boutons : l'envelopper dans un lien les avalerait. */
  it("ne transforme pas une invitation en lien", async () => {
    state.unread = 1;
    state.notifications = [
      {
        ...notification('i1', 'Invitation au foyer', { url: '/app/settings' }),
        type: 'household_invitation',
        payload: { invitation_id: 'inv-1' },
      },
    ];

    await openBell();

    expect(screen.queryByRole('link', { name: /Invitation au foyer/ })).not.toBeInTheDocument();
    expect(screen.getByText('invitations.accept')).toBeInTheDocument();
  });
});
