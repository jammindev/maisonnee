import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { SheetDialog } from '@/design-system/sheet-dialog';
import type { ProjectListItem } from '@/lib/api/projects';
import PurchaseForm, { type PurchaseFormPayload } from '@/features/interactions/PurchaseForm';
import { useRegisterProjectPurchase } from './hooks';

interface ProjectPurchaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project: ProjectListItem | null;
}

export default function ProjectPurchaseDialog({
  open,
  onOpenChange,
  project,
}: ProjectPurchaseDialogProps) {
  const { t } = useTranslation();
  const purchaseMutation = useRegisterProjectPurchase();
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) setError(null);
  }, [open]);

  if (!project) return null;

  async function handleSubmit(payload: PurchaseFormPayload) {
    setError(null);
    if (!project) return;
    try {
      await purchaseMutation.mutateAsync({
        id: project.id,
        payload: {
          amount: payload.amount,
          supplier: payload.supplier,
          occurred_at: payload.occurred_at,
          notes: payload.notes,
          budget_id: payload.budget_id,
        },
      });
      onOpenChange(false);
    } catch {
      setError(t('purchase.errors.save_failed'));
    }
  }

  return (
    <SheetDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t('projects.purchase.title', { name: project.title })}
    >
      <PurchaseForm
        isPending={purchaseMutation.isPending}
        onSubmit={handleSubmit}
        onCancel={() => onOpenChange(false)}
        externalError={error}
        // L'enveloppe du chantier arrive pré-sélectionnée — modifiable : c'est un
        // défaut, pas une contrainte. Sans elle, chaque achat repartait sur
        // « aucun budget », donc sur l'écart `expense_without_budget` que l'app
        // aurait ensuite réclamé de réparer.
        initialBudgetId={project.default_budget ?? ''}
      />
    </SheetDialog>
  );
}
