import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ProjectInteractionItem } from '@/lib/api/projects';
import ProjectDetailPage from './ProjectDetailPage';

/**
 * Ce que ce test tient : **l'onglet Dépenses dit combien**.
 *
 * L'en-tête de la fiche affiche le coût réel du chantier (`actual / planned`),
 * qui n'est rien d'autre que la somme des dépenses listées juste en dessous.
 * Sans le montant sur chaque ligne, le total est invérifiable : on lit « 350 € »
 * sans pouvoir dire d'où ils viennent, ni repérer la saisie à 1 000 € au lieu de
 * 100 €. Un total dont on ne peut pas voir la décomposition n'est pas un chiffre,
 * c'est une affirmation.
 */

const project = {
  id: 'p-1',
  title: 'Salle de bain',
  status: 'in_progress',
  type: 'renovation',
  priority: 2,
  is_pinned: false,
  planned_budget: '1000.00',
  actual_cost_cached: '350.00',
  project_group_name: null,
  tab_counts: {
    tasks: 0,
    trackers: 0,
    notes: 0,
    expenses: 2,
    documents: 0,
    photos: 0,
    timeline: 2,
  },
};

const expenses: Partial<ProjectInteractionItem>[] = [
  {
    id: 'exp-1',
    subject: 'Carrelage',
    content: '',
    type: 'expense',
    occurred_at: '2026-07-10T12:00:00Z',
    amount: '250.00',
  },
  {
    id: 'exp-2',
    subject: 'Joint silicone',
    content: '',
    type: 'expense',
    occurred_at: '2026-07-11T12:00:00Z',
    amount: '100.00',
  },
];

let items: Partial<ProjectInteractionItem>[] = expenses;

vi.mock('./hooks', async () => {
  const actual = await vi.importActual<typeof import('./hooks')>('./hooks');
  return {
    ...actual,
    useProject: () => ({ data: project, isLoading: false, error: null }),
    useProjectInteractions: () => ({ data: items, isLoading: false, error: null }),
    useDeleteProject: () => ({ mutate: vi.fn(), isPending: false }),
    usePinProject: () => ({ mutate: vi.fn(), isPending: false }),
  };
});

vi.mock('@/features/tasks/hooks', async () => {
  const actual = await vi.importActual<typeof import('@/features/tasks/hooks')>(
    '@/features/tasks/hooks',
  );
  return { ...actual, useHouseholdMembersWithMe: () => ({ data: [] }) };
});

// Deux dialogues fermés, hors sujet ici — et qui tirent tout le contexte
// d'authentification (foyer actif, modules) juste pour se monter.
vi.mock('@/features/tasks/NewTaskDialog', () => ({ default: () => null }));
vi.mock('./ProjectPurchaseDialog', () => ({ default: () => null }));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

function renderExpensesTab() {
  // L'onglet actif vit dans sessionStorage (useSessionState + TabShell).
  sessionStorage.setItem('project-detail.p-1.tab', JSON.stringify('expenses'));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/app/projects/p-1']}>
        <Routes>
          <Route path="/app/projects/:id" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("l'onglet Dépenses d'un chantier", () => {
  beforeAll(() => {
    // jsdom n'implémente pas matchMedia, utilisé par useIsMobile (SheetDialog).
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  beforeEach(() => {
    sessionStorage.clear();
    items = expenses;
  });

  it('affiche le montant de chaque dépense', () => {
    renderExpensesTab();

    // `formatAmount` suit la locale de l'app : on n'y compare ni le séparateur
    // décimal ni la place du symbole.
    const carrelage = screen.getByText('Carrelage').closest('a') as HTMLElement;
    expect(within(carrelage).getByText(/250[.,]00/)).toBeTruthy();

    const joint = screen.getByText('Joint silicone').closest('a') as HTMLElement;
    expect(within(joint).getByText(/100[.,]00/)).toBeTruthy();
  });

  it("n'affiche pas de montant sur ce qui n'en a pas", () => {
    // Le même composant sert les onglets Notes et Fil : une note sans montant ne
    // doit pas hériter d'un « — » qui la ferait passer pour une dépense à zéro.
    // (Vide n'est pas une valeur — même règle que `inflow_nature` ou le tri des
    // photos : un blanc dit « rien à dire », pas « zéro ».)
    items = [
      {
        id: 'note-1',
        subject: 'Prendre les mesures',
        content: '',
        type: 'note',
        occurred_at: '2026-07-12T12:00:00Z',
      },
    ];
    renderExpensesTab();

    const note = screen.getByText('Prendre les mesures').closest('a') as HTMLElement;
    expect(within(note).queryByText('—')).toBeNull();
  });
});
