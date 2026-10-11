import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/axios';
import { toLocalISODate } from '@/lib/format';
import { useInvalidate } from '@/lib/invalidate';
import type { Task, TaskStatus } from '@/lib/api/tasks';
import { updateTaskStatus } from '@/lib/api/tasks';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DashboardProject {
  id: string;
  title: string;
  status: string;
  due_date?: string | null;
}

export interface DashboardInteraction {
  id: string;
  subject: string;
  type: string;
  occurred_at: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function normalizeList<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[];
  const p = data as { results?: T[] };
  return Array.isArray(p.results) ? p.results : [];
}

export function isoDate(d: Date): string {
  // Délègue au helper du projet : `toISOString()` convertit en UTC, donc à Paris
  // minuit local recule d'un jour et toutes les bornes de ces cartes partaient
  // décalées entre minuit et 2 h. C'est la règle « jamais toISOString() » de
  // CLAUDE.md, dont cette fonction était la dernière entorse du tableau de bord.
  return toLocalISODate(d);
}

// ── Query keys ────────────────────────────────────────────────────────────────

export const dashboardKeys = {
  all: ['dashboard'] as const,
  myWeek: () => [...dashboardKeys.all, 'my-week'] as const,
  activity: () => [...dashboardKeys.all, 'activity'] as const,
  projects: () => [...dashboardKeys.all, 'projects'] as const,
};

// ── Queries ───────────────────────────────────────────────────────────────────

/** Pending tasks due within the next 7 days (overdue ones live in the triage block). */
export function useMyWeekTasks() {
  return useQuery({
    queryKey: dashboardKeys.myWeek(),
    queryFn: async () => {
      const horizon = new Date();
      horizon.setDate(horizon.getDate() + 7);
      const { data } = await api.get('/tasks/tasks/', {
        params: { status: 'pending', due_before: isoDate(horizon), limit: 20 },
      });
      const today = isoDate(new Date());
      return normalizeList<Task>(data).filter(
        (task) => task.due_date !== null && task.due_date >= today,
      );
    },
  });
}

export function useRecentActivity() {
  return useQuery({
    queryKey: dashboardKeys.activity(),
    queryFn: async () => {
      // Même exclusion que la page Activité, à laquelle « Toute l'activité »
      // renvoie : sans elle, on cliquerait ici une dépense pour atterrir sur une
      // liste où elle ne figure pas.
      const { data } = await api.get('/interactions/interactions/', {
        params: { limit: 6, exclude_type: 'expense' },
      });
      return normalizeList<DashboardInteraction>(data);
    },
  });
}

export function useActiveProjects() {
  return useQuery({
    queryKey: dashboardKeys.projects(),
    queryFn: async () => {
      const { data } = await api.get('/projects/projects/', {
        params: { status: 'active', limit: 5 },
      });
      return normalizeList<DashboardProject>(data);
    },
  });
}

// ── Mutations ─────────────────────────────────────────────────────────────────

/** Status toggle for "My week" checkboxes — invalidates both dashboard and tasks caches. */
export function useSetTaskStatus() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) =>
      updateTaskStatus(id, status),
    // Ce qu'on écrit, c'est une tâche : le dashboard et les alertes en dérivent
    // (`lib/invalidate`). Cette liste-ci était la seule de l'app à connaître le
    // lien tâche → alertes, et elle ne servait qu'à cet écran.
    onSettled: () => invalidate('tasks'),
  });
}
