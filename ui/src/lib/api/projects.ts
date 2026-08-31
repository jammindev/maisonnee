import { api } from '@/lib/axios';
import type { BankLineRef, ReconciliationState } from '@/lib/api/interactions';

export type ProjectStatus = 'draft' | 'active' | 'on_hold' | 'completed' | 'cancelled';
export type ProjectType =
  | 'renovation'
  | 'maintenance'
  | 'repair'
  | 'purchase'
  | 'relocation'
  | 'vacation'
  | 'leisure'
  | 'other';

export interface ProjectZoneItem {
  id: string;
  name: string;
  color?: string | null;
}

/** Item count behind each detail tab. Populated on retrieve only (null in list). */
export interface ProjectTabCounts {
  tasks: number;
  trackers: number;
  notes: number;
  expenses: number;
  documents: number;
  photos: number;
  timeline: number;
}

export interface ProjectListItem {
  id: string;
  household: string;
  title: string;
  description: string;
  status: ProjectStatus;
  priority: number;
  type: ProjectType;
  start_date: string | null;
  due_date: string | null;
  closed_at: string | null;
  tags: string[];
  planned_budget: string;
  actual_cost_cached: string;
  tab_counts?: ProjectTabCounts | null;
  cover_interaction: string | null;
  project_group: string | null;
  project_group_name: string | null;
  is_pinned: boolean;
  zones: ProjectZoneItem[];
  created_at: string;
  updated_at: string;
}

export interface ProjectGroupItem {
  id: string;
  household: string;
  name: string;
  description: string;
  tags: string[];
  projects_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectPayload {
  title: string;
  description?: string;
  status?: ProjectStatus;
  priority?: number;
  type?: ProjectType;
  start_date?: string | null;
  due_date?: string | null;
  planned_budget?: number;
  tags?: string[];
  project_group?: string | null;
  zone_ids?: string[];
}

export interface ProjectGroupPayload {
  name: string;
  description?: string;
  tags?: string[];
}

export interface ProjectPurchasePayload {
  amount: number | null;
  supplier?: string;
  occurred_at?: string | null;
  notes?: string;
  /** Enveloppe à laquelle imputer la dépense créée. `null` = non classée. */
  budget_id?: string | null;
}

interface PaginatedResponse<T> {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results?: T[];
}

function normalizeList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && typeof payload === 'object') {
    const paginated = payload as PaginatedResponse<T>;
    if (Array.isArray(paginated.results)) return paginated.results;
  }
  return [];
}

// ── Projects ───────────────────────────────────────────────

interface FetchProjectsOptions {
  search?: string;
  status?: string;
  type?: string;
  zone?: string;
  groupId?: string;
  ordering?: string;
  limit?: number;
  offset?: number;
}

export async function fetchProjects(options: FetchProjectsOptions = {}): Promise<ProjectListItem[]> {
  const params: Record<string, string | number> = {
    ordering: options.ordering ?? '-updated_at',
    limit: options.limit ?? 200,
  };
  if (options.search) params.search = options.search;
  if (options.status) params.status = options.status;
  if (options.type) params.type = options.type;
  if (options.zone) params.zone = options.zone;
  if (options.groupId) params.project_group = options.groupId;
  if (options.offset) params.offset = options.offset;

  const { data } = await api.get('/projects/projects/', { params });
  return normalizeList<ProjectListItem>(data);
}

export async function fetchProject(id: string): Promise<ProjectListItem> {
  const { data } = await api.get(`/projects/projects/${id}/`);
  return data as ProjectListItem;
}

export async function createProject(input: ProjectPayload): Promise<ProjectListItem> {
  const { data } = await api.post('/projects/projects/', {
    ...input,
    description: input.description ?? '',
    tags: input.tags ?? [],
    start_date: input.start_date || null,
    due_date: input.due_date || null,
    project_group: input.project_group || null,
    zone_ids: input.zone_ids ?? [],
  });
  return data as ProjectListItem;
}

export async function updateProject(id: string, input: Partial<ProjectPayload>): Promise<ProjectListItem> {
  const { data } = await api.patch(`/projects/projects/${id}/`, {
    ...input,
    ...(input.tags !== undefined ? { tags: input.tags } : {}),
    ...(typeof input.start_date !== 'undefined' ? { start_date: input.start_date || null } : {}),
    ...(typeof input.due_date !== 'undefined' ? { due_date: input.due_date || null } : {}),
    ...(typeof input.project_group !== 'undefined' ? { project_group: input.project_group || null } : {}),
    ...(input.zone_ids !== undefined ? { zone_ids: input.zone_ids } : {}),
  });
  return data as ProjectListItem;
}

export async function deleteProject(id: string): Promise<void> {
  await api.delete(`/projects/projects/${id}/`);
}

export async function pinProject(id: string): Promise<ProjectListItem> {
  const { data } = await api.post(`/projects/projects/${id}/pin/`);
  return data as ProjectListItem;
}

export async function unpinProject(id: string): Promise<ProjectListItem> {
  const { data } = await api.post(`/projects/projects/${id}/unpin/`);
  return data as ProjectListItem;
}

export async function registerProjectPurchase(
  projectId: string,
  payload: ProjectPurchasePayload,
): Promise<ProjectListItem & { interaction_id?: string }> {
  const body: Record<string, unknown> = {};
  if (payload.amount !== undefined && payload.amount !== null) body.amount = payload.amount;
  if (payload.supplier) body.supplier = payload.supplier;
  if (payload.occurred_at) body.occurred_at = payload.occurred_at;
  if (payload.notes) body.notes = payload.notes;
  const { data } = await api.post(
    `/projects/projects/${projectId}/register-purchase/`,
    body,
  );
  return data as ProjectListItem & { interaction_id?: string };
}

export interface ProjectInteractionItem {
  id: string;
  subject: string;
  content: string;
  type: string;
  occurred_at: string;
  /** Sur une dépense : est-ce qu'une ligne de relevé la justifie (verdict serveur). */
  reconciliation_state?: ReconciliationState;
  bank_line?: BankLineRef | null;
}

export async function fetchProjectInteractions(
  projectId: string,
  type?: string,
): Promise<ProjectInteractionItem[]> {
  const params: Record<string, string | number> = {
    source_type: 'projects.project',
    source_id: projectId,
    ordering: '-occurred_at',
    limit: 100,
  };
  if (type) params.type = type;
  const { data } = await api.get('/interactions/interactions/', { params });
  return normalizeList<ProjectInteractionItem>(data);
}

// ── Project Groups ─────────────────────────────────────────

export async function fetchProjectGroups(): Promise<ProjectGroupItem[]> {
  const { data } = await api.get('/projects/project-groups/');
  return normalizeList<ProjectGroupItem>(data);
}

export async function fetchProjectGroup(id: string): Promise<ProjectGroupItem> {
  const { data } = await api.get(`/projects/project-groups/${id}/`);
  return data as ProjectGroupItem;
}

export async function createProjectGroup(input: ProjectGroupPayload): Promise<ProjectGroupItem> {
  const { data } = await api.post('/projects/project-groups/', {
    ...input,
    description: input.description ?? '',
    tags: input.tags ?? [],
  });
  return data as ProjectGroupItem;
}

export async function updateProjectGroup(id: string, input: Partial<ProjectGroupPayload>): Promise<ProjectGroupItem> {
  const { data } = await api.patch(`/projects/project-groups/${id}/`, input);
  return data as ProjectGroupItem;
}

export async function deleteProjectGroup(id: string): Promise<void> {
  await api.delete(`/projects/project-groups/${id}/`);
}

// --- Création assistée (parcours 32) ----------------------------------------
//
// Deux endpoints, et la séparation est structurelle : `assistantStep` parle au
// modèle et n'écrit rien, `assistantCreate` écrit et ne parle à aucun modèle.
// « Rien n'est écrit avant relecture » ne dépend donc pas d'une branche de code.

/**
 * Comment rendre le champ de réponse. Le modèle choisit *quelle* question poser ;
 * le serveur choisit *comment* on y répond — un montant atterrit dans un
 * `DecimalInput`, jamais dans du texte libre qu'il faudrait relire comme un
 * nombre.
 */
export type AssistantInput = 'text' | 'amount' | 'date' | 'zones' | 'choice';

export interface AssistantQuestion {
  text: string;
  field: string;
  input: AssistantInput;
  hint: string;
  choices: string[];
}

/**
 * Un item du plan. `zone_ids` porte des ids **résolus par le serveur** au tour
 * d'entretien ; `unresolved_zone_names` dit ce qu'il n'a pas trouvé, pour que
 * l'écran le montre au lieu de l'absorber.
 */
export interface PlanItem {
  subject: string;
  content: string;
  priority?: number | null;
  due_date?: string | null;
  zone_ids: string[];
  unresolved_zone_names: string[];
}

export interface PlanProject {
  title: string;
  description: string;
  type: ProjectType | null;
  priority: number | null;
  planned_budget: string | null;
  start_date: string | null;
  due_date: string | null;
  tags: string[];
  zone_ids: string[];
  unresolved_zone_names: string[];
}

export interface AssistantPlan {
  project: PlanProject;
  tasks: PlanItem[];
  notes: PlanItem[];
}

export interface AssistantTurn {
  question: string;
  field: string;
  answer: string;
}

export interface AssistantStep {
  state: 'asking' | 'ready';
  asked: number;
  /** Combien de questions peuvent encore être posées, celle-ci comprise. */
  remaining: number;
  question?: AssistantQuestion;
  plan?: AssistantPlan;
}

export interface AssistantStepInput {
  goal: string;
  history: AssistantTurn[];
  force_ready?: boolean;
}

export async function assistantStep(input: AssistantStepInput): Promise<AssistantStep> {
  const { data } = await api.post('/projects/projects/assistant-step/', {
    ...input,
    force_ready: input.force_ready ?? false,
  });
  return data as AssistantStep;
}

export async function assistantCreate(plan: AssistantPlan): Promise<ProjectListItem> {
  const { data } = await api.post('/projects/projects/assistant-create/', plan);
  return data as ProjectListItem;
}
