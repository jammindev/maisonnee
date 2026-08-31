import * as React from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import PrivateBadge from '@/components/PrivateBadge';
import { useQueryClient } from '@tanstack/react-query';
import { ExternalLink, FileText, Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/design-system/button';
import { Card, CardContent } from '@/design-system/card';
import ConfirmDialog from '@/components/ConfirmDialog';
import BackLink from '@/components/BackLink';
import PageHeader from '@/components/PageHeader';
import InfoField from '@/components/InfoField';
import LoadError from '@/components/LoadError';
import ListSkeleton from '@/components/ListSkeleton';
import { TabShell } from '@/components/TabShell';
import { pushBack, useNavigateBack } from '@/lib/backNavigation';
import { formatDate } from '@/lib/format';
import { useAuth } from '@/lib/auth/useAuth';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { isTaskOverdue, formatRelativeDate, type Task, type TaskStatus } from '@/lib/api/tasks';
import {
  useTask,
  useHouseholdMembersWithMe,
  useUpdateTaskStatus,
  useUpdateTaskAssignee,
  useDeleteTask,
  taskKeys,
} from './hooks';
import TaskStatusBadge from './TaskStatusBadge';
import TaskAssigneeBadge from './TaskAssigneeBadge';
import NewTaskDialog from './NewTaskDialog';
import TaskWeatherHint from './TaskWeatherHint';
import EntityDocumentsTab from '@/features/documents/EntityDocumentsTab';

function priorityLabelKey(priority: Task['priority']): string {
  if (priority === 1) return 'tasks.priorityHigh_label';
  if (priority === 3) return 'tasks.priorityLow_label';
  return 'tasks.priorityNormal_label';
}

// ── Tabs ───────────────────────────────────────────────────

type Tab = 'info' | 'documents' | 'activity';
const TABS: Tab[] = ['info', 'documents', 'activity'];

// ── Main page ──────────────────────────────────────────────

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const location = useLocation();
  const navigateBack = useNavigateBack('/app/tasks');
  const { user } = useAuth();
  const qc = useQueryClient();

  const [editOpen, setEditOpen] = React.useState(false);
  const [deleteOpen, setDeleteOpen] = React.useState(false);

  const { data: task, isLoading, error } = useTask(id ?? '');
  const { data: householdMembers = [] } = useHouseholdMembersWithMe();
  const updateStatus = useUpdateTaskStatus();
  const updateAssignee = useUpdateTaskAssignee();
  const deleteMutation = useDeleteTask();

  const showSkeleton = useDelayedLoading(isLoading);

  const handleStatusChange = React.useCallback(
    async (newStatus: TaskStatus) => {
      if (!id) return;
      await updateStatus.mutateAsync({ id, status: newStatus });
    },
    [id, updateStatus],
  );

  const handleAssigneeChange = React.useCallback(
    async (assignedToId: string | null) => {
      if (!id) return;
      await updateAssignee.mutateAsync({ id, assignedToId });
    },
    [id, updateAssignee],
  );

  function handleDelete() {
    if (!id) return;
    deleteMutation.mutate(id, {
      onSuccess: () => navigateBack(),
    });
  }

  // NewTaskDialog performs the update via the raw API and delegates cache
  // refresh to its caller — invalidate so this detail page reflects the edit.
  const handleEdited = React.useCallback(() => {
    setEditOpen(false);
    void qc.invalidateQueries({ queryKey: taskKeys.all });
  }, [qc]);

  if (!id) return null;

  if (showSkeleton) {
    return <ListSkeleton className="space-y-2 p-4" />;
  }
  if (isLoading) return null;

  if (error || !task) {
    return (
      <LoadError
        message={t('tasks.notFound')}
        link={{ to: '/app/tasks', label: t('tasks.title') }}
      />
    );
  }

  const isCreator = user != null && String(task.created_by) === String(user.id);
  const isAssignee =
    user != null && task.assigned_to != null && String(task.assigned_to) === String(user.id);
  const canChangeStatus = isCreator || isAssignee;
  const showAssignee = householdMembers.length > 1 && !task.is_private;
  const overdue = isTaskOverdue(task);
  const relativeDate = formatRelativeDate(task.due_date);
  const zoneName = task.zone_names?.[0];

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          backLink={<BackLink fallback="/app/tasks" fallbackLabel={t('tasks.title')} />}
          title={
            <>
              {task.priority === 1 && (
                <span
                  className="h-2.5 w-2.5 flex-shrink-0 rounded-full bg-destructive"
                  title={t('tasks.priorityHigh')}
                />
              )}
              {task.is_private && <PrivateBadge variant="icon" className="h-4 w-4" />}
              <span>{task.subject || t('tasks.untitledTask')}</span>
            </>
          }
          description={
            (zoneName || relativeDate) ? (
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                {zoneName && <span className="font-medium text-foreground/80">{zoneName}</span>}
                {relativeDate && (
                  <>
                    {zoneName && <span className="text-border">·</span>}
                    <span className={overdue ? 'font-medium text-destructive' : ''}>
                      {relativeDate}
                    </span>
                  </>
                )}
              </span>
            ) : undefined
          }
        >
          {isCreator && (
            <>
              <Button
                type="button"
                variant="outline"
                className="h-8 px-3 text-sm"
                onClick={() => setEditOpen(true)}
              >
                <Pencil className="mr-1.5 h-3.5 w-3.5" />
                {t('common.edit')}
              </Button>
              <Button
                type="button"
                variant="destructive"
                className="h-8 px-3 text-sm"
                onClick={() => setDeleteOpen(true)}
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                {t('common.delete')}
              </Button>
            </>
          )}
        </PageHeader>

        {/* Tabs */}
        <TabShell<Tab>
          tabs={TABS.map((tab) => ({ key: tab, label: t(`tasks.tabs.${tab}`) }))}
          sessionKey={`task-detail.${task.id}.tab`}
          defaultTab="info"
        >
          {(tab) => (
            <>
              {tab === 'info' ? (
                <div className="space-y-6">
                  <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <InfoField label={t('tasks.fieldStatus')}>
                      <TaskStatusBadge
                        status={task.status}
                        onChange={handleStatusChange}
                        disabled={!canChangeStatus}
                      />
                    </InfoField>

                    {showAssignee && (
                      <InfoField label={t('tasks.fieldAssignedTo')}>
                        <TaskAssigneeBadge
                          task={task}
                          members={householdMembers}
                          onChange={handleAssigneeChange}
                          disabled={!isCreator}
                        />
                      </InfoField>
                    )}

                    <InfoField label={t('tasks.fieldDate')}>
                      <span className={overdue ? 'font-medium text-destructive' : undefined}>
                        {formatDate(task.due_date)}
                      </span>
                    </InfoField>

                    <InfoField label={t('tasks.fieldZone')}>
                      {zoneName || t('tasks.noZone')}
                    </InfoField>

                    <InfoField label={t('tasks.fieldPriority')}>
                      {t(priorityLabelKey(task.priority))}
                    </InfoField>

                    {task.project && task.project_title && (
                      <InfoField label={t('tasks.fieldProject')}>
                        <Link
                          to={`/app/projects/${task.project}`}
                          state={pushBack(location)}
                          className="text-primary hover:underline"
                        >
                          {task.project_title}
                        </Link>
                      </InfoField>
                    )}
                  </dl>

                  <Card>
                    <CardContent className="pt-4">
                      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-foreground">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        {t('tasks.fieldContent')}
                      </h2>
                      {task.content ? (
                        <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
                          {task.content}
                        </p>
                      ) : (
                        <p className="text-sm italic text-muted-foreground">
                          {t('tasks.noNotes')}
                        </p>
                      )}
                    </CardContent>
                  </Card>

                  {/* Weather suggestion (parcours 17, Lot 3) — outdoor dry-weather tasks */}
                  <TaskWeatherHint task={task} />
                </div>
              ) : null}

              {tab === 'documents' ? (
                <EntityDocumentsTab entityType="task" objectId={task.id} />
              ) : null}

              {tab === 'activity' ? (
                <div className="space-y-2">
                  {task.linked_interactions.length === 0 ? (
                    <p className="text-sm italic text-muted-foreground">
                      {t('tasks.noLinkedInteractions')}
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {task.linked_interactions.map((item) => (
                        <li key={item.id} className="rounded-md border border-border p-3 text-sm">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              <span className="font-medium text-foreground">
                                {item.subject || '—'}
                              </span>
                              {item.occurred_at && (
                                <p className="mt-0.5 text-xs text-muted-foreground">
                                  {formatDate(item.occurred_at)}
                                </p>
                              )}
                            </div>
                            <Link
                              to={`/app/interactions/${item.interaction_id}`}
                              state={pushBack(location)}
                              className="ml-1 inline-flex shrink-0 items-center text-muted-foreground hover:text-foreground"
                              aria-label={t('common.view')}
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </Link>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : null}
            </>
          )}
        </TabShell>
      </div>

      <NewTaskDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        onCreated={handleEdited}
        existingTask={task}
        onUpdated={handleEdited}
        householdMembers={householdMembers}
      />

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={t('common.confirmDelete')}
        description={t('tasks.deleted')}
        onConfirm={handleDelete}
        loading={deleteMutation.isPending}
      />
    </>
  );
}
