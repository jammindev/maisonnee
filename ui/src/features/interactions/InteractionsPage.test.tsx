import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { FetchInteractionsResult, InteractionListItem } from '@/lib/api/interactions';
import InteractionsPage from './InteractionsPage';

/**
 * Ce que ces tests tiennent, et pourquoi :
 *
 * 1. **Le journal se parcourt, il ne se tronque pas.** Le serveur pagine cette
 *    liste par **huit** (`InteractionViewSet.Pagination.default_limit`), et cette
 *    page était la seule à s'en contenter sans jamais lire `count` : un foyer de
 *    cent vingt événements en voyait huit, et rien — pas un compteur, pas un
 *    bouton — ne disait qu'il y avait une suite. Le défaut est le même que celui
 *    corrigé sur `BudgetDetailPage` et `ExpensesPanel` ; les helpers existaient
 *    déjà (`usePager` + `Pager`), c'est leur absence ici qui était le bug.
 * 2. **⚠️ Changer un filtre ramène à la première page.** Rester page 3 d'une
 *    liste qui n'en a plus qu'une affiche un vide inexplicable — et sur une page
 *    de liste, ce vide se lit « je n'ai rien enregistré », pas « j'ai filtré
 *    trop loin ».
 * 3. **⚠️ Une page vidée sous les doigts ne se dit pas « aucun événement ».** Les
 *    suppressions se font depuis la liste (avec undo) : vider la dernière page
 *    ferait passer `ListPage` en état vide, **qui masque la liste et donc le
 *    pager avec elle** — un cul-de-sac dont on ne revient pas.
 */

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, vars?: Record<string, unknown>) =>
      vars ? `${key}:${Object.values(vars).join(',')}` : key,
    i18n: { language: 'fr' },
  }),
}));

// Le picker de zones interroge l'arborescence du foyer : il ne dit rien du
// parcours de la liste.
vi.mock('@/features/zones/ZonePicker', () => ({ default: () => null }));

vi.mock('@/lib/api/contacts', () => ({ fetchContacts: () => Promise.resolve([]) }));

// Chaque carte porte le dialogue « créer une tâche », qui lit le foyer actif via
// `useAuth` : hors `AuthProvider` il lève, et ce n'est pas le sujet ici.
vi.mock('@/features/tasks/NewTaskDialog', () => ({ default: () => null }));

function event(id: string, subject: string): InteractionListItem {
  return {
    id,
    subject,
    content: '',
    type: 'note',
    occurred_at: '2026-07-10T12:00:00Z',
    tags: [],
    zone_names: [],
    document_count: 0,
  };
}

/** Cent vingt événements : deux pages et demie, quinze fois l'ancien plafond. */
const TOTAL = 120;

/** Les offsets que le test veut voir répondre « page vide » (suppressions). */
const emptiedOffsets = new Set<number>();

const fetchInteractions = vi.fn(
  async (
    options: { limit?: number; offset?: number; type?: string } = {},
  ): Promise<FetchInteractionsResult> => {
    const limit = options.limit ?? 8;
    const offset = options.offset ?? 0;
    if (emptiedOffsets.has(offset)) return { items: [], count: TOTAL, next: null, previous: null };
    const prefix = options.type ? `${options.type}-` : '';
    const items = Array.from({ length: Math.max(0, Math.min(limit, TOTAL - offset)) }, (_, i) =>
      event(`${prefix}${offset + i}`, `Événement ${prefix}${offset + i}`),
    );
    return { items, count: TOTAL, next: null, previous: null };
  },
);

vi.mock('@/lib/api/interactions', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/interactions')>(
    '@/lib/api/interactions',
  );
  return {
    ...actual,
    fetchInteractions: ((options) =>
      fetchInteractions(options)) as typeof actual.fetchInteractions,
  };
});

function renderPage() {
  const router = createMemoryRouter(
    [
      { path: '/app/interactions', element: <InteractionsPage /> },
      { path: '*', element: null },
    ],
    { initialEntries: ['/app/interactions'] },
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

beforeEach(() => {
  fetchInteractions.mockClear();
  emptiedOffsets.clear();
});

describe('InteractionsPage — la liste des activités', () => {
  it('se parcourt par pages au lieu de s’arrêter aux derniers événements', async () => {
    renderPage();

    await screen.findByText('Événement 0');
    // Surtout pas le `default_limit` du serveur, qui est de huit.
    expect(fetchInteractions).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 50, offset: 0 }),
    );
    expect(screen.getByText('Événement 49')).toBeInTheDocument();
    // « 1–50 sur 120 » : le total est dit, donc la suite est visible avant le clic.
    expect(screen.getByText('common.rangeOfTotal:1,50,120')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /common.next/ }));

    await screen.findByText('Événement 50');
    expect(fetchInteractions).toHaveBeenCalledWith(expect.objectContaining({ offset: 50 }));
    expect(screen.getByText('common.rangeOfTotal:51,100,120')).toBeInTheDocument();
  });

  it('revient à la première page quand un filtre change', async () => {
    renderPage();
    await screen.findByText('Événement 0');

    await userEvent.click(screen.getByRole('button', { name: /common.next/ }));
    await screen.findByText('Événement 50');

    await userEvent.selectOptions(
      screen.getByLabelText('interactions.filter_type'),
      'maintenance',
    );

    await screen.findByText('Événement maintenance-0');
    expect(fetchInteractions).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'maintenance', offset: 0 }),
    );
  });

  it('ne dit pas « aucun événement » à un foyer qui en a cent vingt', async () => {
    // La deuxième page a été vidée pendant la lecture (suppressions avec undo).
    emptiedOffsets.add(50);
    renderPage();
    await screen.findByText('Événement 0');

    await userEvent.click(screen.getByRole('button', { name: /common.next/ }));

    // Retour à la première page, jamais l'état vide — qui masquerait le pager.
    await waitFor(() => expect(screen.getByText('Événement 0')).toBeInTheDocument());
    expect(screen.queryByText('interactions.empty')).not.toBeInTheDocument();
  });
});
