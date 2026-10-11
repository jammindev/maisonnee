import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { SheetDialog } from '@/design-system/sheet-dialog';
import { Input } from '@/design-system/input';
import { DecimalInput } from '@/design-system/decimal-input';
import { Textarea } from '@/design-system/textarea';
import { Button } from '@/design-system/button';
import { Select } from '@/design-system/select';
import { FormField } from '@/design-system/form-field';
import { VisibilityField } from '@/design-system/visibility-field';
import ZonePicker from '@/features/zones/ZonePicker';
import {
  type ProjectListItem,
  type ProjectStatus,
  type ProjectType,
} from '@/lib/api/projects';
import { useCreateProject, useProjectGroups, useUpdateProject } from './hooks';

const STATUS_OPTIONS: ProjectStatus[] = ['draft', 'active', 'on_hold', 'completed', 'cancelled'];
const TYPE_OPTIONS: ProjectType[] = [
  'renovation', 'maintenance', 'repair', 'purchase',
  'relocation', 'vacation', 'leisure', 'other',
];

interface ProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  existingProject?: ProjectListItem;
}

export default function ProjectDialog({
  open,
  onOpenChange,
  onSaved,
  existingProject,
}: ProjectDialogProps) {
  const { t } = useTranslation();
  const isEditing = Boolean(existingProject);

  const { data: groups = [] } = useProjectGroups();
  const createMutation = useCreateProject();
  const updateMutation = useUpdateProject();

  const [title, setTitle] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [status, setStatus] = React.useState<ProjectStatus>('draft');
  const [type, setType] = React.useState<ProjectType>('other');
  const [groupId, setGroupId] = React.useState('');
  const [startDate, setStartDate] = React.useState('');
  const [dueDate, setDueDate] = React.useState('');
  const [plannedBudget, setPlannedBudget] = React.useState('');
  const [zoneIds, setZoneIds] = React.useState<string[]>([]);
  const [isPrivate, setIsPrivate] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    setTitle(existingProject?.title ?? '');
    setDescription(existingProject?.description ?? '');
    setStatus((existingProject?.status ?? 'draft') as ProjectStatus);
    setType((existingProject?.type ?? 'other') as ProjectType);
    setGroupId(existingProject?.project_group ?? '');
    setStartDate(existingProject?.start_date ?? '');
    setDueDate(existingProject?.due_date ?? '');
    setPlannedBudget(
      existingProject?.planned_budget ? String(Number(existingProject.planned_budget)) : '',
    );
    setZoneIds(existingProject?.zones?.map((z) => z.id) ?? []);
    setIsPrivate(existingProject?.is_private ?? false);
    setError(null);
  }, [open, existingProject?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError(t('projects.form.errors.title_required'));
      return;
    }
    setLoading(true);
    setError(null);

    const payload = {
      title: title.trim(),
      description,
      status,
      type,
      project_group: groupId || null,
      start_date: startDate || null,
      due_date: dueDate || null,
      planned_budget: plannedBudget ? Number(plannedBudget) : 0,
      zone_ids: zoneIds,
      is_private: isPrivate,
    };

    const action =
      isEditing && existingProject
        ? updateMutation.mutateAsync({ id: existingProject.id, payload })
        : createMutation.mutateAsync(payload);

    action
      .then(() => {
        setLoading(false);
        onOpenChange(false);
        onSaved();
      })
      .catch((err) => {
        setLoading(false);
        // Le refus de privatiser est un 400 **nommé** : il dit combien d'éléments
        // appartiennent à d'autres membres. L'afficher tel quel, plutôt qu'un
        // « échec de l'enregistrement » générique — le refus n'a de sens que s'il
        // se corrige, et un message opaque ne se corrige pas.
        const named = err?.response?.data?.is_private;
        if (named) {
          setError(Array.isArray(named) ? named.join(' ') : String(named));
          return;
        }
        setError(
          isEditing
            ? t('projects.form.errors.update_failed')
            : t('projects.form.errors.create_failed'),
        );
      });
  };

  return (
    <SheetDialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? t('projects.form.title_edit') : t('projects.form.title_create')}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
          {error ? (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
          ) : null}

          {/* Title */}
          <FormField label={`${t('projects.form.fields.title')} *`} htmlFor="proj-title">
            <Input
              id="proj-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              autoComplete="off"
            />
          </FormField>

          {/* Description */}
          <FormField label={t('projects.form.fields.description')} htmlFor="proj-description">
            <Textarea
              id="proj-description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </FormField>

          {/* Status + Type */}
          <div className="grid grid-cols-2 gap-3">
            <FormField label={t('projects.form.fields.status')} htmlFor="proj-status">
              <Select
                id="proj-status"
                value={status}
                onChange={(e) => setStatus(e.target.value as ProjectStatus)}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {t(`projects.status.${s}`)}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label={t('projects.form.fields.type')} htmlFor="proj-type">
              <Select
                id="proj-type"
                value={type}
                onChange={(e) => setType(e.target.value as ProjectType)}
              >
                {TYPE_OPTIONS.map((tp) => (
                  <option key={tp} value={tp}>
                    {t(`projects.type.${tp}`)}
                  </option>
                ))}
              </Select>
            </FormField>
          </div>

          {/* Zone select (first zone of existing project) — simplified: group only */}
          {groups.length > 0 ? (
            <FormField label={t('projects.form.fields.project_group')} htmlFor="proj-group">
              <Select
                id="proj-group"
                value={groupId}
                onChange={(e) => setGroupId(e.target.value)}
              >
                <option value="">{t('projects.form.no_group')}</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            </FormField>
          ) : null}

          {/* Zones — multi-select */}
          <FormField label={t('projects.form.fields.zones')} htmlFor="proj-zones">
            <ZonePicker mode="multiple" id="proj-zones" value={zoneIds} onChange={setZoneIds} />
          </FormField>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <FormField label={t('projects.form.fields.start_date')} htmlFor="proj-start">
              <Input
                id="proj-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </FormField>
            <FormField label={t('projects.form.fields.due_date')} htmlFor="proj-due">
              <Input
                id="proj-due"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </FormField>
          </div>

          {/* Budget */}
          <FormField label={t('projects.form.fields.planned_budget')} htmlFor="proj-budget">
            <DecimalInput
              id="proj-budget"
              value={plannedBudget}
              onChange={setPlannedBudget}
            />
          </FormField>

          {/* Visibilité — un chantier privé rend privé tout ce qu'il contient :
              tâches, notes, dépenses, documents, trackers. Jamais ses zones : une
              pièce de la maison est structurelle, partagée par vingt features. */}
          <VisibilityField
            id="proj-private"
            value={isPrivate}
            onChange={setIsPrivate}
            privateHint={t('projects.form.privateHint')}
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? t('common.saving') : t('common.save')}
            </Button>
          </div>
      </form>
    </SheetDialog>
  );
}
