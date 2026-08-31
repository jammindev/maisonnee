import { api } from '@/lib/axios';

export type ChangeType = 'feat' | 'fix' | 'perf';

export interface ChangelogEntry {
  id: number;
  commit_sha: string;
  pr_number: number | null;
  module: string;
  change_type: ChangeType;
  summary: string;
  raw_subject: string;
  committed_at: string; // ISO
}

export interface ChangelogState {
  head_sha: string;
  head_committed_at: string; // ISO
  generated_at: string; // ISO
}

/** Base publique du repo — sert à construire les liens vers les PR. */
export const REPO_URL = 'https://github.com/jammindev/maisonnee';

export function prUrl(prNumber: number): string {
  return `${REPO_URL}/pull/${prNumber}`;
}

export async function fetchChangelog(): Promise<ChangelogEntry[]> {
  const { data } = await api.get('/releases/changelog/', {
    params: { limit: 1000, ordering: '-committed_at' },
  });
  return Array.isArray(data)
    ? (data as ChangelogEntry[])
    : ((data as { results?: ChangelogEntry[] }).results ?? []);
}

export async function fetchChangelogState(): Promise<ChangelogState | null> {
  const { data } = await api.get('/releases/changelog/state/');
  return (data as ChangelogState | null) ?? null;
}
