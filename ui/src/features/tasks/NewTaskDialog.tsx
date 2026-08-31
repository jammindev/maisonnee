import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, Paperclip } from 'lucide-react';
import { SheetDialog } from '@/design-system/sheet-dialog';
import { Input } from '@/design-system/input';
import { Textarea } from '@/design-system/textarea';
import { Select } from '@/design-system/select';
import { Button } from '@/design-system/button';
import { FormField } from '@/design-system/form-field';
import { CheckboxField } from '@/design-system/checkbox-field';
import { VisibilityField } from '@/design-system/visibility-field';
import ZonePicker from '@/features/zones/ZonePicker';
import { useDisabledModules } from '@/lib/modules';
import { fetchProjects } from '@/lib/api/projects';
import type { ProjectListItem } from '@/lib/api/projects';
import { fetchDocuments, fetchPhotoDocuments, type DocumentItem } from '@/lib/api/documents';
import { fetchInteractions, type InteractionListItem } from '@/lib/api/interactions';
import { fetchZones } from '@/lib/api/zones';
import {
  type CreateTaskInput,
  type Zone, type Task, type HouseholdMember, type TaskPriority, type TaskStatus,
} from '@/lib/api/tasks';
import { useCreateTask, useUpdateTask } from './hooks';

interface NewTaskDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
  existingTask?: Task;
  onUpdated?: (task: Task) => void;
  householdMembers?: HouseholdMember[];
  /** Pre-fill project when opening from a project page */
  defaultProjectId?: string;
  /** Pre-fill subject (e.g. when opening from an interaction) */
  defaultSubject?: string;
  /** Pre-fill zones (e.g. when opening from an interaction) */
  defaultZoneIds?: string[];
  /** Link the new task to the source interaction it was created from */
  sourceInteractionId?: string;
}

export default function NewTaskDialog({
  open,
  onOpenChange,
  onCreated,
  existingTask,
  onUpdated,
  householdMembers = [],
  defaultProjectId,
  defaultSubject,
  defaultZoneIds,
  sourceInteractionId,
}: NewTaskDialogProps) {
  const { t } = useTranslation();
  const isEditing = Boolean(existingTask);
  const { disabled } = useDisabledModules();
  const weatherEnabled = !disabled.has('weather');
  const createMutation = useCreateTask();
  const updateMutation = useUpdateTask();

  const priorityOptions = [
    { value: '1', label: t('tasks.priorityHigh_label') },
    { value: '2', label: t('tasks.priorityNormal_label') },
    { value: '3', label: t('tasks.priorityLow_label') },
  ];

  const statusOptions = [
    { value: 'pending', label: t('tasks.sections.pending') },
    { value: 'backlog', label: t('tasks.sections.backlog') },
  ];

  const [subject, setSubject] = React.useState('');
  const [content, setContent] = React.useState('');
  const [dueDate, setDueDate] = React.useState('');
  const [priority, setPriority] = React.useState<string>('2');
  const [status, setStatus] = React.useState<string>('pending');
  const [assignedToId, setAssignedToId] = React.useState('');
  const [zoneIds, setZoneIds] = React.useState<string[]>([]);
  const [projectId, setProjectId] = React.useState('');
  const [isPrivate, setIsPrivate] = React.useState(false);
  const [needsDryWeather, setNeedsDryWeather] = React.useState(false);
  const [zones, setZones] = React.useState<Zone[]>([]);
  const [projects, setProjects] = React.useState<ProjectListItem[]>([]);
  const [zonesLoading, setZonesLoading] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Attachment selection state (create only)
  const [selectedDocumentIds, setSelectedDocumentIds] = React.useState<string[]>([]);
  const [selectedInteractionIds, setSelectedInteractionIds] = React.useState<string[]>([]);
  const [allDocuments, setAllDocuments] = React.useState<DocumentItem[]>([]);
  const [allInteractions, setAllInteractions] = React.useState<InteractionListItem[]>([]);
  const [attachmentsLoaded, setAttachmentsLoaded] = React.useState(false);

  const loadZones = React.useCallback(() => {
    setZonesLoading(true);
    Promise.all([fetchZones(), fetchProjects()])
      .then(([zoneList, projectList]) => {
        setZones(zoneList);
        setProjects(projectList);
        setZonesLoading(false);
      })
      .catch(() => setZonesLoading(false));
  }, []);

  const loadAttachmentItems = React.useCallback(() => {
    if (attachmentsLoaded) return;
    setAttachmentsLoaded(true);
    Promise.all([
      fetchDocuments(),
      fetchPhotoDocuments(),
      fetchInteractions({ limit: 200 }),
    ]).then(([docs, photos, interResult]) => {
      setAllDocuments([...docs, ...photos]);
      setAllInteractions(interResult.items);
    }).catch(() => {});
  }, [attachmentsLoaded]);

  React.useEffect(() => {
    if (!open) return;
    if (existingTask) {
      setSubject(existingTask.subject || '');
      setContent(existingTask.content || '');
      setDueDate(existingTask.due_date ?? '');
      setPriority(String(existingTask.priority ?? 2));
      setAssignedToId(existingTask.assigned_to ?? '');
      setProjectId(existingTask.project ?? defaultProjectId ?? '');
      setIsPrivate(existingTask.is_private ?? false);
      setNeedsDryWeather(existingTask.needs_dry_weather ?? false);
    } else {
      setSubject(defaultSubject ?? '');
      setContent('');
      setDueDate('');
      setPriority('2');
      setStatus('pending');
      setAssignedToId('');
      setZoneIds(defaultZoneIds ?? []);
      setProjectId(defaultProjectId ?? '');
      setIsPrivate(false);
      setNeedsDryWeather(false);
      setSelectedDocumentIds([]);
      setSelectedInteractionIds([]);
      setAttachmentsLoaded(false);
    }
    setError(null);
    loadZones();
  }, [open, existingTask?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    if (zones.length === 0) return;
    if (existingTask?.zone_names?.length) {
      const matched = zones.filter((z) => existingTask.zone_names.includes(z.name));
      if (matched.length) setZoneIds(matched.map((z) => z.id));
      return;
    }
    if (existingTask) return;
    // Création : si l'appelant a déjà fourni des zones (ex: depuis une interaction), on ne touche pas.
    if (defaultZoneIds && defaultZoneIds.length > 0) return;
    // Si on vient d'un projet avec des zones, on les hérite ; sinon on retombe sur la racine du household.
    if (defaultProjectId && projects.length > 0) {
      const project = projects.find((p) => p.id === defaultProjectId);
      if (project?.zones?.length) {
        setZoneIds(project.zones.map((z) => z.id));
        return;
      }
    }
    const root = zones.find((z) => !z.parent);
    if (root) setZoneIds([root.id]);
  }, [zones, projects]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (zoneIds.length === 0) {
      setError(t('tasks.zoneRequired'));
      return;
    }
    setLoading(true);
    setError(null);

    const payload = {
      subject,
      content: content || undefined,
      zone_ids: zoneIds,
      due_date: dueDate || null,
      priority: (Number(priority) || null) as TaskPriority,
      assigned_to_id: assignedToId || null,
      project: projectId || null,
      is_private: isPrivate,
      needs_dry_weather: needsDryWeather,
    };

    if (isEditing && existingTask) {
      updateMutation
        .mutateAsync({ id: existingTask.id, payload })
        .then((updated) => {
          setLoading(false);
          onOpenChange(false);
          if (onUpdated) onUpdated(updated);
        })
        .catch(() => {
          setLoading(false);
          setError(t('tasks.updateFailed'));
        });
    } else {
      createMutation.mutateAsync({
        ...payload,
        status: status as TaskStatus,
        document_ids: selectedDocumentIds.length > 0 ? selectedDocumentIds : undefined,
        interaction_ids: selectedInteractionIds.length > 0 ? selectedInteractionIds : undefined,
        source_interaction: sourceInteractionId ?? undefined,
      } as CreateTaskInput)
        .then(() => {
          setLoading(false);
          onOpenChange(false);
          onCreated();
        })
        .catch(() => {
          setLoading(false);
          setError(t('tasks.createFailed'));
        });
    }
  };

  const toggleDocumentId = (id: string) => {
    setSelectedDocumentIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const toggleInteractionId = (id: string) => {
    setSelectedInteractionIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const memberOptions = householdMembers.map((m) => ({ value: m.userId, label: m.name }));
  const projectOptions = projects.map((p) => ({ value: p.id, label: p.title }));

  return (
    <SheetDialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? t('tasks.editTitle') : t('tasks.newTask')}
    >
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
          )}

          <FormField label={t('tasks.fieldSubject')} htmlFor="task-subject">
            <Input
              id="task-subject"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              required
              autoComplete="off"
              placeholder={t('tasks.fieldSubjectPlaceholder')}
            />
          </FormField>

          <FormField label={t('tasks.fieldZone')} htmlFor="task-zones">
            <ZonePicker mode="multiple" id="task-zones" value={zoneIds} onChange={setZoneIds} />
          </FormField>

          <FormField label={t('tasks.fieldPriority')} htmlFor="task-priority">
            <Select
              id="task-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              options={priorityOptions}
            />
          </FormField>

          <div className={isEditing ? undefined : 'grid grid-cols-2 gap-3'}>
            <FormField label={t('tasks.fieldDate')} htmlFor="task-date">
              <Input
                id="task-date"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </FormField>

            {!isEditing && (
              <FormField label={t('tasks.fieldStatus')} htmlFor="task-status">
                <Select
                  id="task-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  options={statusOptions}
                />
              </FormField>
            )}
          </div>

          {memberOptions.length > 1 && !isPrivate && (
            <FormField label={t('tasks.fieldAssignedTo')} htmlFor="task-assigned">
              <Select
                id="task-assigned"
                value={assignedToId}
                onChange={(e) => setAssignedToId(e.target.value)}
                options={memberOptions}
                placeholder={t('tasks.noAssignee')}
              />
            </FormField>
          )}

          {projectOptions.length > 0 && (
            <FormField label={t('tasks.fieldProject')} htmlFor="task-project">
              <Select
                id="task-project"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                options={projectOptions}
                placeholder={t('tasks.noProject')}
              />
            </FormField>
          )}

          <FormField label={t('tasks.fieldContent')} htmlFor="task-content">
            <Textarea
              id="task-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={3}
              placeholder={t('tasks.fieldContentPlaceholder')}
            />
          </FormField>

          {householdMembers.length > 1 && (
            <VisibilityField
              id="task-private"
              value={isPrivate}
              // Le retrait de l'assignation est fait **ici et maintenant**, pas
              // laissé au serveur : la contrainte DB `tasks_private_not_assigned`
              // existe, et un 500 sur un choix de visibilité est un mauvais
              // professeur. L'écran dit ce qu'il va faire, puis le fait.
              onChange={(val) => { setIsPrivate(val); if (val) setAssignedToId(''); }}
              privateHint={t('privacy.taskUnassigns')}
            />
          )}

          {weatherEnabled && (
            <div className="space-y-1">
              <CheckboxField
                id="task-needs-dry-weather"
                label={t('tasks.weather.fieldNeedsDryWeather')}
                checked={needsDryWeather}
                onChange={setNeedsDryWeather}
              />
              <p className="pl-6 text-xs text-muted-foreground">
                {t('tasks.weather.fieldNeedsDryWeatherHint')}
              </p>
            </div>
          )}

          {!isEditing && (
            <details className="group" onToggle={(e) => {
              if ((e.currentTarget as HTMLDetailsElement).open) loadAttachmentItems();
            }}>
              <summary className="flex cursor-pointer list-none items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
                <Paperclip className="h-3.5 w-3.5" />
                {t('tasks.addAttachments')}
                {selectedDocumentIds.length + selectedInteractionIds.length > 0 && (
                  <span className="ml-1 rounded-full bg-slate-200 px-1.5 py-0.5 text-xs text-slate-700">
                    {selectedDocumentIds.length + selectedInteractionIds.length}
                  </span>
                )}
                <ChevronDown className="ml-auto h-3.5 w-3.5 transition-transform group-open:rotate-180" />
              </summary>

              <div className="mt-3 space-y-3">
                {allDocuments.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                      {t('tasks.linkedDocuments')} / {t('tasks.linkedPhotos')}
                    </p>
                    <div className="max-h-32 space-y-0.5 overflow-y-auto rounded-md border p-1">
                      {allDocuments.map((d) => (
                        <label key={d.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-slate-50">
                          <input
                            type="checkbox"
                            checked={selectedDocumentIds.includes(String(d.id))}
                            onChange={() => toggleDocumentId(String(d.id))}
                            className="h-3.5 w-3.5"
                          />
                          <span className="min-w-0 flex-1 truncate text-sm">{d.name}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">{d.type}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {allInteractions.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                      {t('tasks.linkedInteractions')}
                    </p>
                    <div className="max-h-32 space-y-0.5 overflow-y-auto rounded-md border p-1">
                      {allInteractions.map((i) => (
                        <label key={i.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-slate-50">
                          <input
                            type="checkbox"
                            checked={selectedInteractionIds.includes(i.id)}
                            onChange={() => toggleInteractionId(i.id)}
                            className="h-3.5 w-3.5"
                          />
                          <span className="min-w-0 flex-1 truncate text-sm">{i.subject}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">{i.type}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </details>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={loading || zonesLoading}>
              {loading ? t('common.saving') : t('common.save')}
            </Button>
          </div>
        </form>
    </SheetDialog>
  );
}
