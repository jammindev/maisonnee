import * as React from 'react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '@/lib/auth/useAuth';
import { SheetDialog } from '@/design-system/sheet-dialog';
import { Input } from '@/design-system/input';
import { Textarea } from '@/design-system/textarea';
import { Select } from '@/design-system/select';
import { Button } from '@/design-system/button';
import { FormField } from '@/design-system/form-field';
import { VisibilityField } from '@/design-system/visibility-field';
import { DOCUMENT_TYPES, type DocumentItem } from '@/lib/api/documents';
import { useUpdateDocument } from './hooks';

interface DocumentEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  doc: DocumentItem | null;
  onSaved: () => void;
}

export default function DocumentEditDialog({
  open,
  onOpenChange,
  doc,
  onSaved,
}: DocumentEditDialogProps) {
  const { t } = useTranslation();
  const updateDocument = useUpdateDocument();
  const { user } = useAuth();

  // `AuthUser.id` est une string, `Document.created_by` un number : comparer les
  // deux sans conversion renvoie toujours false, et le contrôle serait grisé
  // pour tout le monde, déposant compris.
  const canChangeVisibility = Boolean(doc && user && String(doc.created_by) === user.id);

  const [name, setName] = React.useState('');
  const [type, setType] = React.useState('document');
  const [notes, setNotes] = React.useState('');
  const [isPrivate, setIsPrivate] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open || !doc) return;
    setName(doc.name || '');
    setType(doc.type || 'document');
    setNotes(doc.notes || '');
    setIsPrivate(doc.is_private ?? false);
    setError(null);
  }, [open, doc?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!doc) return;
    setError(null);
    updateDocument.mutate(
      {
        id: doc.id,
        payload: { name, type, notes, ...(canChangeVisibility ? { is_private: isPrivate } : {}) },
      },
      {
        onSuccess: () => {
          onOpenChange(false);
          onSaved();
        },
        onError: () => {
          setError(t('documents.editFailed'));
        },
      },
    );
  };

  const typeOptions = DOCUMENT_TYPES.map((v) => ({
    value: v,
    label: t(`documents.type.${v}`),
  }));

  return (
    <SheetDialog open={open} onOpenChange={onOpenChange} title={t('documents.editTitle')}>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
          )}

          {/* Name */}
          <FormField label={t('documents.fieldName')} htmlFor="edit-doc-name">
            <Input
              id="edit-doc-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoComplete="off"
            />
          </FormField>

          {/* Type */}
          <FormField label={t('documents.fieldType')} htmlFor="edit-doc-type">
            <Select
              id="edit-doc-type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              options={typeOptions}
            />
          </FormField>

          {/* Notes */}
          <FormField label={t('documents.fieldNotes')} htmlFor="edit-doc-notes">
            <Textarea
              id="edit-doc-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder={t('documents.fieldNotesPlaceholder')}
            />
          </FormField>

          {/* Visibilité — le drapeau vivait dans l'API et dans les sept portes de
              lecture sans qu'aucun écran ne permette de le poser. Seul le déposant
              peut le changer (`documents/views.py::perform_update`) : l'écran le
              dit, au lieu de laisser le serveur refuser après coup. */}
          <VisibilityField
            id="edit-doc-private"
            value={isPrivate}
            onChange={setIsPrivate}
            disabled={!canChangeVisibility}
          />
          {!canChangeVisibility ? (
            <p className="text-xs text-muted-foreground">{t('privacy.documentOwnerOnly')}</p>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={updateDocument.isPending}>
              {updateDocument.isPending ? t('common.saving') : t('common.save')}
            </Button>
          </div>
        </form>
    </SheetDialog>
  );
}
