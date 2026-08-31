import { api } from '@/lib/axios';

/** Renovation phase of a photo relative to a linked entity. Empty = unclassified. */
export type PhotoPhase = 'before' | 'during' | 'after';

/**
 * L'intention d'une photo : **pourquoi elle existe**.
 *
 * ⚠️ `''` n'est pas `'memory'` : le vide dit que personne n'a trié, `'memory'` dit
 * qu'on a choisi. Ne jamais traiter l'absence comme un souvenir, ni ici ni dans un
 * compteur — c'est ce qui rendrait la file « À trier » aveugle.
 */
export type PhotoPurpose = 'technical' | 'observation' | 'memory';

/** Le marqueur qui demande « ce que personne n'a trié ». Jamais un paramètre vide. */
export const UNTRIAGED = 'untriaged';

export interface PurposeCounts {
  technical: number;
  observation: number;
  memory: number;
  untriaged: number;
}

export interface TriageCluster {
  /** Clé stable d'un rechargement à l'autre, servie par le serveur. */
  key: string;
  start: string;
  end: string;
  count: number;
  photos: DocumentItem[];
}

export interface TriageQueue {
  /** Tout ce qui reste à trier — pas seulement ce que les grappes montrent. */
  total: number;
  clusters: TriageCluster[];
}

export interface LinkedInteractionSummary {
  id: string;
  subject: string;
  type: string;
  occurred_at: string;
}

export interface DocumentQualification {
  has_activity_context: boolean;
  qualification_state: 'without_activity' | 'activity_linked';
  linked_interactions_count: number;
  has_secondary_context: boolean;
}

export interface ZoneLinkSummary {
  zone_id: string;
  zone_name: string;
}

export interface ProjectLinkSummary {
  project_id: string;
  project_name: string;
}

/** Generic backlink: any household entity a document is attached to. */
export interface EntityLinkSummary {
  entity_type: string;
  id: string;
  label: string;
  url_path: string;
}

export interface DocumentItem {
  id: string;
  name: string;
  file_path: string;
  file_url: string | null;
  thumbnail_url?: string | null;
  medium_url?: string | null;
  mime_type: string;
  type: string;
  notes?: string | null;
  ocr_text?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  created_by?: number | null;
  created_by_name?: string | null;
  /** Privé = seul le déposant le voit. Seul lui peut aussi le changer. */
  is_private?: boolean;
  interaction?: string | null;
  interaction_subject?: string | null;
  qualification: DocumentQualification;
  linked_interactions: LinkedInteractionSummary[];
  legacy_interaction?: string | null;
  legacy_interaction_subject?: string | null;
  /** Phase of this photo for the entity being filtered on (null when unscoped). */
  phase?: PhotoPhase | '' | null;
  /**
   * Date de prise de vue, lue dans l'EXIF à l'upload. `null` = inconnue (capture
   * d'écran, scan, EXIF strippé) — **jamais** un repli sur `created_at` : le
   * backend refuse de fabriquer cette donnée, et l'affichage doit donc pouvoir
   * dire « prise le » plutôt que « ajoutée le ».
   */
  taken_at?: string | null;
  /**
   * Pourquoi cette photo existe — preuve, observation ou souvenir. `''` = personne
   * ne l'a encore triée, et c'est un état à part entière (voir `PhotoPurpose`).
   */
  purpose?: PhotoPurpose | '' | null;
  /**
   * Zones où la photo est rangée — servi **dès la liste**, pas seulement sur le
   * détail : c'est ce qui permet à la galerie de dire où est une photo et de
   * signaler celle qui n'est rangée nulle part. Un tableau vide est une
   * information (aucune zone), et le backend l'envoie toujours.
   */
  zone_links: ZoneLinkSummary[];
  /**
   * Tout ce à quoi le document est rattaché (projet, équipement, zone, tâche…) —
   * servi **dès la liste**, comme `zone_links`. C'est ce qui permet à la page
   * Documents de dire *où vit* un fichier : une liste de deux cents noms de
   * fichiers ne se lit pas. Tableau vide = rattaché à rien, une information.
   */
  entity_links: EntityLinkSummary[];
}

export interface DocumentDetail extends DocumentItem {
  project_links: ProjectLinkSummary[];
  recent_interaction_candidates: LinkedInteractionSummary[];
}

export interface UploadDocumentInput {
  file: File;
  name?: string;
  type?: DocumentType | 'photo' | '';
  notes?: string;
  zone?: string;
}

export interface DocumentUploadResponse {
  document: DocumentDetail;
  detail_url: string;
}

export interface DocumentFilters {
  search?: string;
  type?: string;
  zone?: string;
  project?: string;
  equipment?: string;
  /** `'1'` = seulement les documents rangés dans aucune zone. */
  without_zone?: string;
  [key: string]: string | undefined;
}

function normalizeId(d: DocumentItem & { id: string | number }): DocumentItem {
  return { ...d, id: String(d.id) };
}

export async function fetchDocuments(filters: DocumentFilters = {}): Promise<DocumentItem[]> {
  // Forward every filter as a query param: `search`/`type` are reserved, any
  // other key is an entity link filter (?zone= / ?project= / ?task= / ?chicken=…)
  // resolved polymorphically by the backend via the searchables registry.
  const params: Record<string, string> = { ordering: '-created_at' };
  for (const [key, value] of Object.entries(filters)) {
    if (value) params[key] = value;
  }

  const { data } = await api.get('/documents/documents/', { params });
  const list: Array<DocumentItem & { id: string | number }> = Array.isArray(data)
    ? data
    : ((data as { results?: Array<DocumentItem & { id: string | number }> }).results ?? []);

  return list.filter((d) => d.type !== 'photo').map(normalizeId);
}

export async function fetchPhotoDocuments(filters: Omit<DocumentFilters, 'type'> = {}): Promise<DocumentItem[]> {
  // `effective_date` = COALESCE(taken_at, created_at) côté serveur : une galerie se
  // range par date de prise de vue, pas par date d'import — une série prise en juin
  // et importée en juillet apparaissait sous « juillet ». Le repli garde les photos
  // sans EXIF à une place plausible plutôt que de les reléguer en fin de liste.
  const params: Record<string, string> = { ordering: '-effective_date', type: 'photo' };
  for (const [key, value] of Object.entries(filters)) {
    if (key === 'type') continue; // forced to 'photo'
    if (value) params[key] = value;
  }

  const { data } = await api.get('/documents/documents/', { params });
  const list: Array<DocumentItem & { id: string | number }> = Array.isArray(data)
    ? data
    : ((data as { results?: Array<DocumentItem & { id: string | number }> }).results ?? []);

  return list.map(normalizeId);
}

export async function fetchDocumentDetail(id: string): Promise<DocumentDetail> {
  const { data } = await api.get(`/documents/documents/${id}/`);
  return { ...(data as DocumentDetail & { id: string | number }), id: String((data as { id: string | number }).id) };
}

export async function uploadDocument(input: UploadDocumentInput): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.set('file', input.file);
  if (input.name) formData.set('name', input.name);
  if (input.type) formData.set('type', input.type);
  if (input.notes) formData.set('notes', input.notes);
  if (input.zone) formData.set('zone', input.zone);

  const { data } = await api.post('/documents/documents/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  const payload = data as DocumentUploadResponse;
  return {
    ...payload,
    document: {
      ...payload.document,
      id: String(payload.document.id),
    },
  };
}

export async function updateDocument(
  id: string,
  // `purpose: ''` est admis **ici seulement** : détrier une photo qu'on a regardée
  // est un geste unitaire légitime. Le lot, lui, le refuse.
  payload: { name?: string; notes?: string; type?: string; purpose?: PhotoPurpose | '' },
): Promise<DocumentItem> {
  const { data } = await api.patch(`/documents/documents/${id}/`, payload);
  return normalizeId(data as DocumentItem & { id: string | number });
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/documents/${id}/`);
}

/**
 * Remplace les zones d'un document — un seul appel, pas un `detach` suivi d'un
 * `attach` : ranger une photo passerait par un état intermédiaire sans zone, et le
 * client devrait connaître les anciens liens pour les défaire. Une liste vide
 * efface les zones.
 */
export async function setDocumentZones(id: string, zoneIds: string[]): Promise<DocumentItem> {
  const { data } = await api.post(`/documents/documents/${id}/set_zones/`, { zone_ids: zoneIds });
  return normalizeId(data as DocumentItem & { id: string | number });
}

/**
 * Ajoute des zones à un lot de documents — **sans rien retirer**, contrairement à
 * `setDocumentZones`. Un lot qui remplacerait effacerait le rangement de documents
 * qu'on n'a pas regardés un par un. Contrepartie : le lot ne sait pas retirer une
 * zone. Un seul appel : trente photos ne valent pas trente allers-retours, et un
 * échec au milieu laisserait un lot à moitié rangé.
 */
export async function bulkAddDocumentZones(
  documentIds: string[],
  zoneIds: string[],
): Promise<{ updated: number }> {
  const { data } = await api.post('/documents/documents/bulk_add_zones/', {
    document_ids: documentIds,
    zone_ids: zoneIds,
  });
  return data as { updated: number };
}

/** Ce qui reste à trier, par grappes de session — le serveur groupe, pas le client. */
export async function fetchTriageQueue(): Promise<TriageQueue> {
  const { data } = await api.get('/documents/documents/triage/');
  const payload = data as TriageQueue;
  return {
    ...payload,
    clusters: payload.clusters.map((cluster) => ({
      ...cluster,
      photos: cluster.photos.map(normalizeId),
    })),
  };
}

/** Les compteurs des pastilles — un `COUNT(*)`, jamais une liste qu'on mesure. */
export async function fetchPurposeCounts(): Promise<PurposeCounts> {
  const { data } = await api.get('/documents/documents/purpose_counts/');
  return data as PurposeCounts;
}

/**
 * Pose une intention sur un lot de photos.
 *
 * `overwrite` est un geste explicite : sans lui, le serveur laisse intactes les
 * photos qui portent déjà une autre intention et les compte dans `skipped`.
 */
export async function setPhotosPurpose(
  documentIds: string[],
  purpose: PhotoPurpose,
  options: { overwrite?: boolean } = {},
): Promise<{ updated: number; skipped: number }> {
  const { data } = await api.post('/documents/documents/set_purpose/', {
    document_ids: documentIds,
    purpose,
    ...(options.overwrite ? { overwrite: true } : {}),
  });
  return data as { updated: number; skipped: number };
}

/**
 * Entity types that expose document attach/detach endpoints, mapped to their
 * URL base. Reads go through the polymorphic DocumentLink (`?<entityType>=id`);
 * writes still go through each entity's wrapper endpoint (kept for compat).
 */
const DOCUMENT_LINK_ENDPOINTS: Record<string, (id: string) => string> = {
  project: (id) => `/projects/projects/${id}`,
  equipment: (id) => `/equipment/${id}`,
  zone: (id) => `/zones/${id}`,
  task: (id) => `/tasks/tasks/${id}`,
  chicken: (id) => `/chickens/${id}`,
};

export function supportsDocumentLinking(entityType: string): boolean {
  return entityType in DOCUMENT_LINK_ENDPOINTS;
}

/**
 * Root React Query key of an entity's detail cache, so attaching/detaching a
 * document or photo can refresh its `tab_counts`. Pluralization is irregular
 * (equipment stays singular) — keep this map explicit rather than guessing.
 */
const ENTITY_DETAIL_QUERY_KEYS: Record<string, readonly unknown[]> = {
  project: ['projects'],
  equipment: ['equipment'],
  zone: ['zones'],
  task: ['tasks'],
  chicken: ['chickens'],
};

export function entityDetailQueryKey(entityType: string): readonly unknown[] | null {
  return ENTITY_DETAIL_QUERY_KEYS[entityType] ?? null;
}

export async function attachEntityDocument(
  entityType: string,
  objectId: string,
  documentId: string,
  phase?: PhotoPhase | '',
): Promise<void> {
  const base = DOCUMENT_LINK_ENDPOINTS[entityType];
  if (!base) throw new Error(`Unsupported entity type for document linking: ${entityType}`);
  await api.post(`${base(objectId)}/attach_document/`, {
    document_id: documentId,
    ...(phase ? { phase } : {}),
  });
}

/** Set the renovation phase of a photo relative to a linked entity ('' clears it). */
export async function setDocumentPhase(
  entityType: string,
  objectId: string,
  documentId: string,
  phase: PhotoPhase | '',
): Promise<void> {
  const base = DOCUMENT_LINK_ENDPOINTS[entityType];
  if (!base) throw new Error(`Unsupported entity type for document linking: ${entityType}`);
  await api.post(`${base(objectId)}/set_document_phase/`, {
    document_id: documentId,
    phase,
  });
}

export async function detachEntityDocument(
  entityType: string,
  objectId: string,
  documentId: string,
): Promise<void> {
  const base = DOCUMENT_LINK_ENDPOINTS[entityType];
  if (!base) throw new Error(`Unsupported entity type for document linking: ${entityType}`);
  await api.post(`${base(objectId)}/detach_document/`, { document_id: documentId });
}

export async function reprocessDocumentOcr(id: string): Promise<DocumentDetail> {
  const { data } = await api.post(`/documents/documents/${id}/reprocess_ocr/`);
  return { ...(data as DocumentDetail & { id: string | number }), id: String((data as { id: string | number }).id) };
}

export function formatFileSize(bytes?: number | null): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const DOCUMENT_TYPES = [
  'document',
  'invoice',
  'manual',
  'warranty',
  'receipt',
  'plan',
  'certificate',
  'other',
] as const;

export type DocumentType = (typeof DOCUMENT_TYPES)[number];
