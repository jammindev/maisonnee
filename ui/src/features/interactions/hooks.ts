import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  bulkUpdateExpenses,
  fetchInteractions,
  createInteraction,
  deleteInteraction,
  fetchInteraction,
  fetchSuppliers,
  updateInteraction,
  linkDocumentToInteraction,
  type CreateInteractionInput,
} from '@/lib/api/interactions';
import { documentKeys } from '@/features/documents/hooks';
import { INTERACTIONS_ROOT } from '@/features/money/keys';
import { useInvalidateMoney } from '@/features/money/invalidate';

interface InteractionFilters {
  search?: string;
  type?: string;
  status?: string;
  zone?: string;
  contact?: string;
  structure?: string;
  tags?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
  [key: string]: string | number | boolean | undefined;
}

export const interactionKeys = {
  all: INTERACTIONS_ROOT,
  list: (filters?: InteractionFilters) =>
    [...interactionKeys.all, 'list', filters] as const,
  detail: (id: string) => [...interactionKeys.all, 'detail', id] as const,
  suppliers: () => [...interactionKeys.all, 'suppliers'] as const,
};

/**
 * Le journal du foyer, par pages (voir `PAGE_SIZE` dans `InteractionsPage`).
 *
 * `placeholderData` garde la page précédente à l'écran pendant le chargement de
 * la suivante — sans lui, chaque coup de flèche vide la liste puis la remplit, et
 * comme le pager n'est rendu qu'avec la liste il disparaît sous le doigt au
 * moment même où on veut recliquer. Même raison que `useBudgetOverview`.
 */
export function useInteractions(filters: InteractionFilters = {}) {
  return useQuery({
    queryKey: interactionKeys.list(filters),
    queryFn: () => fetchInteractions(filters),
    placeholderData: (previous) => previous,
  });
}

export function useCreateInteraction() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (payload: CreateInteractionInput) => createInteraction(payload),
    onSuccess: invalidate,
  });
}

export function useDeleteInteraction() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (id: string) => deleteInteraction(id),
    onSuccess: invalidate,
  });
}

export function useInteraction(id: string) {
  return useQuery({
    queryKey: interactionKeys.detail(id),
    queryFn: () => fetchInteraction(id),
    enabled: !!id,
  });
}

/**
 * Joindre un document à une entrée du journal — le justificatif d'une dépense.
 *
 * Le lien vit dans `DocumentLink` (table polymorphe), donc la liste se relit par
 * `?linked_to=interaction:{id}` : c'est le cache `documents` qu'il faut invalider,
 * pas celui de l'interaction, qui ne porte pas ses pièces.
 */
export function useAttachDocumentToInteraction(interactionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) =>
      linkDocumentToInteraction({ interactionId, documentId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: documentKeys.all }),
  });
}

export function useUpdateInteraction() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<CreateInteractionInput> }) =>
      updateInteraction(id, payload),
    onSuccess: invalidate,
  });
}

/**
 * Les fournisseurs que le foyer connaît — la liste du `SupplierCombobox`.
 *
 * Clé sous la racine `interactions`, donc rafraîchie par `useInvalidateMoney` :
 * une dépense enregistrée chez un nouveau fournisseur doit le proposer au
 * formulaire suivant, sinon le select promet une mémoire qu'il n'a pas.
 */
export function useSuppliers() {
  return useQuery({
    queryKey: interactionKeys.suppliers(),
    queryFn: fetchSuppliers,
    staleTime: 60_000,
  });
}

/**
 * Corriger le fournisseur ou le budget d'un lot de dépenses.
 *
 * Invalidation par `useInvalidateMoney` : un lot de douze dépenses réaffectées
 * change les compteurs de budget, le résumé des dépenses **et** la conformité
 * (`expense_without_budget`). Lister ici les seules racines « évidentes » est
 * exactement la dérive que ce helper unique a supprimée.
 */
export function useBulkUpdateExpenses() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: bulkUpdateExpenses,
    onSuccess: invalidate,
  });
}
