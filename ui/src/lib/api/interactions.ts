import { api } from '@/lib/axios';

export interface InteractionContactSummary {
  id: string;
  name: string;
}

export interface InteractionStructureSummary {
  id: string;
  name: string;
}

export interface InteractionEquipmentSummary {
  id: string;
  name: string;
}

/**
 * Est-ce qu'une ligne de relevé justifie cette dépense — **verdict du serveur**.
 *
 * Ne jamais le redériver de `bank_transaction === null` : le verdict dépend de
 * la fenêtre de conformité du foyer, exactement comme le détecteur
 * `expense_unreconciled` qu'il doit refléter. Une dépense antérieure au premier
 * relevé n'a aucune ligne à laquelle se rattacher et n'en aura jamais — la
 * badger en rouge fabriquerait une tâche insoluble que le Contrôle, lui, ne
 * réclame pas. Miroir exact de `AllocationProgress` côté banque.
 *
 * - `''` — pas une dépense, aucun marqueur.
 * - `attested` — une ligne de relevé la justifie.
 * - `cash` — une ligne d'un compte espèces : rattachée, mais personne n'a rapproché.
 * - `pending` — rien ne la justifie, et la banque aurait dû la voir. C'est l'écart.
 * - `out_of_scope` — rien ne la justifie, hors de la fenêtre. Pas un écart.
 */
export type ReconciliationState = '' | 'attested' | 'cash' | 'pending' | 'out_of_scope';

/** De quoi nommer l'opération qui justifie une dépense, et lier vers elle. */
export interface BankLineRef {
  id: string;
  label: string;
  booked_on: string;
  account_name: string;
}

export interface InteractionListItem {
  id: string;
  subject: string;
  content: string;
  type: string;
  occurred_at: string;
  tags: string[];
  zone_names: string[];
  zone_id_list?: string[];
  document_count: number;
  created_by_name?: string;
  /** Privé = seul l'auteur la voit. Sans effet sur une dépense, qui alimente
   * sept agrégations et ne disparaît donc d'aucune liste. */
  is_private?: boolean;
  metadata?: Record<string, unknown>;
  // Expense columns (promoted out of metadata). Only meaningful for type='expense'.
  amount?: string | null;
  kind?: string;
  supplier?: string;
  source_type?: string | null;
  source_id?: string | null;
  source_label?: string | null;
  /** Enveloppe qui classe cette dépense — le seul axe qui dit *de quelle nature*. */
  budget?: { id: string; name: string } | null;
  /** Ligne de relevé dont cette dépense est une ventilation (parcours 25). */
  bank_transaction?: string | null;
  /** `auto` | `manual` | `''` — comment le rapprochement s'est fait. */
  reconciled_by?: string;
  /** Voir {@link ReconciliationState} — calculé par le serveur, jamais ici. */
  reconciliation_state?: ReconciliationState;
  /** De quoi nommer l'opération et y aller. `null` quand rien ne la justifie. */
  bank_line?: BankLineRef | null;
  contacts?: InteractionContactSummary[];
  structures?: InteractionStructureSummary[];
  equipments?: InteractionEquipmentSummary[];
}

export interface CreateInteractionInput {
  subject: string;
  content?: string;
  type: string;
  occurred_at: string;
  zone_ids: string[];
  tags_input?: string[];
  /** Privé = seul l'auteur la voit (sans effet sur une dépense). */
  is_private?: boolean;
  metadata?: Record<string, unknown>;
  amount?: string | null;
  kind?: string;
  supplier?: string;
  /** Enveloppe de la dépense ; `null` la retire. Omettre la clé ne change rien. */
  budget_id?: string | null;
  document_ids?: string[];
  source_type?: string | null;
  source_id?: string | null;
  contact_ids?: string[];
  structure_ids?: string[];
  equipment_ids?: string[];
}

export interface LinkDocumentToInteractionInput {
  interactionId: string;
  documentId: string;
  role?: string;
  note?: string;
}

interface FetchInteractionsOptions {
  search?: string;
  type?: string;
  /**
   * Types à retirer, séparés par des virgules. **Filtre serveur**, jamais un
   * `.filter()` sur le résultat : la liste est paginée par huit, donc écarter
   * des lignes après coup afficherait une page vide sous un compteur qui en
   * annonce huit.
   */
  exclude_type?: string;
  /**
   * `true` = les dépenses qu'aucune ligne ne justifie encore — le vivier du
   * rattachement manuel. **Hors fenêtre de conformité**, contrairement au
   * détecteur : ici la question est « qu'est-ce qui existe déjà ? », pas
   * « qu'est-ce que je dois réclamer ? ».
   */
  unreconciled?: boolean;
  /** Plafond de montant : ce qui tient dans le reste à ventiler d'une ligne. */
  max_amount?: string;
  zone?: string;
  contact?: string;
  structure?: string;
  tags?: string;
  start_date?: string;
  end_date?: string;
  kind?: string;
  supplier?: string;
  /**
   * `'1'` ne garde que les dépenses auxquelles il manque un fournisseur — un
   * paramètre à part et non une valeur de `supplier`, un fournisseur pouvant
   * légitimement s'appeler « none ». Exclusif de `supplier` côté appelant.
   */
  without_supplier?: string;
  /** Id d'un budget, ou `'none'` pour le seau « hors budget ». */
  budget?: string;
  limit?: number;
  offset?: number;
}

interface PaginatedResponse<T> {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results?: T[];
}

export interface FetchInteractionsResult {
  items: InteractionListItem[];
  count: number;
  next: string | null;
  previous: string | null;
}

function normalize(payload: unknown): FetchInteractionsResult {
  if (Array.isArray(payload)) {
    const items = payload as InteractionListItem[];
    return {
      items,
      count: items.length,
      next: null,
      previous: null,
    };
  }

  if (payload && typeof payload === 'object') {
    const paginated = payload as PaginatedResponse<InteractionListItem>;
    if (Array.isArray(paginated.results)) {
      return {
        items: paginated.results,
        count: typeof paginated.count === 'number' ? paginated.count : paginated.results.length,
        next: paginated.next ?? null,
        previous: paginated.previous ?? null,
      };
    }
  }

  return {
    items: [],
    count: 0,
    next: null,
    previous: null,
  };
}

export async function fetchInteractions(
  options: FetchInteractionsOptions = {}
): Promise<FetchInteractionsResult> {
  const {
    search,
    type,
    exclude_type,
    unreconciled,
    max_amount,
    zone,
    contact,
    structure,
    tags,
    start_date,
    end_date,
    kind,
    supplier,
    without_supplier,
    budget,
    limit = 8,
    offset = 0,
  } = options;

  const params: Record<string, string | number> = { ordering: '-occurred_at' };
  if (search) params.search = search;
  if (type) params.type = type;
  if (exclude_type) params.exclude_type = exclude_type;
  if (unreconciled) params.unreconciled = 'true';
  if (max_amount) params.max_amount = max_amount;
  if (zone) params.zone = zone;
  if (contact) params.contact = contact;
  if (structure) params.structure = structure;
  if (tags) params.tags = tags;
  if (start_date) params.start_date = start_date;
  if (end_date) params.end_date = end_date;
  if (kind) params.kind = kind;
  if (supplier !== undefined) params.supplier = supplier;
  if (without_supplier) params.without_supplier = without_supplier;
  // `'none'` est une valeur (« hors budget »), pas l'absence de filtre.
  if (budget) params.budget = budget;
  if (limit > 0) params.limit = limit;
  if (offset > 0) params.offset = offset;

  const { data } = await api.get('/interactions/interactions/', { params });
  return normalize(data);
}

export async function searchInteractions(
  search: string,
  options: Omit<FetchInteractionsOptions, 'search'> = {}
): Promise<FetchInteractionsResult> {
  return fetchInteractions({
    ...options,
    search,
  });
}

export async function createInteraction(
  input: CreateInteractionInput,
): Promise<InteractionListItem & { linked_document_ids?: string[] }> {
  const { data } = await api.post('/interactions/interactions/', {
    ...input,
    content: input.content ?? '',
    metadata: input.metadata ?? {},
    document_ids: input.document_ids ?? [],
    enriched_text: '',
  });
  return data as InteractionListItem;
}

export async function deleteInteraction(id: string): Promise<void> {
  await api.delete(`/interactions/interactions/${id}/`);
}

export async function fetchInteraction(id: string): Promise<InteractionListItem> {
  const { data } = await api.get(`/interactions/interactions/${id}/`);
  return data as InteractionListItem;
}

export async function updateInteraction(
  id: string,
  input: Partial<CreateInteractionInput>,
): Promise<InteractionListItem> {
  const { data } = await api.patch(`/interactions/interactions/${id}/`, {
    ...input,
    content: input.content ?? '',
  });
  return data as InteractionListItem;
}

export async function linkDocumentToInteraction(
  input: LinkDocumentToInteractionInput,
): Promise<void> {
  await api.post('/interactions/interaction-documents/', {
    interaction: input.interactionId,
    document: input.documentId,
    role: input.role ?? 'attachment',
    note: input.note ?? '',
  });
}

/**
 * Un fournisseur du catalogue du foyer (table `interactions.Supplier`).
 *
 * `count` est le nombre de dépenses qui le portent — calculé à la lecture, jamais
 * dénormalisé sur la table : un compteur stocké aurait deux définitions dès la
 * première suppression de dépense. Il sert à l'ordre (le plus employé d'abord) et
 * à un discret repère à l'écran. `0` veut dire « au catalogue, pas encore
 * employé », ce qui reste une raison de le proposer.
 */
export interface SupplierSuggestion {
  name: string;
  count: number;
}

/**
 * La liste entière, sans pagination ni recherche serveur : le filtrage se fait à
 * la frappe côté client, et un foyer compte ses fournisseurs en dizaines. Un
 * aller-retour par caractère coûterait plus cher que la liste complète.
 */
export async function fetchSuppliers(): Promise<SupplierSuggestion[]> {
  const { data } = await api.get<{ results: SupplierSuggestion[] }>(
    '/interactions/interactions/suppliers/',
  );
  return data.results ?? [];
}

/**
 * Corriger un lot de dépenses en un appel.
 *
 * `supplier` et `budgetId` sont optionnels **mais pas simultanément**. Et pour le
 * budget, `null` est un choix (« retirer l'enveloppe ») là où l'absence de clé veut
 * dire « ne touche pas au budget » — d'où le `undefined` distinct du `null`, que le
 * sérialiseur JSON traduit en clé absente.
 *
 * Le serveur refuse le lot **en entier** si un id n'est pas une dépense du foyer :
 * une écriture partielle ne se rattrape par aucun écran.
 */
export async function bulkUpdateExpenses(input: {
  ids: string[];
  supplier?: string;
  budgetId?: string | null;
}): Promise<{ updated: number; supplier: string | null }> {
  const { data } = await api.post('/interactions/interactions/bulk-update/', {
    ids: input.ids,
    ...(input.supplier !== undefined ? { supplier: input.supplier } : {}),
    ...(input.budgetId !== undefined ? { budget_id: input.budgetId } : {}),
  });
  return data as { updated: number; supplier: string | null };
}
