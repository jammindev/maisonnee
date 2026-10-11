import * as React from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { Star, Plus } from 'lucide-react';
import { Badge } from '@/design-system/badge';
import { Button } from '@/design-system/button';
import { Card, CardContent } from '@/design-system/card';
import { TabShell, type TabConfig } from '@/components/TabShell';
import ConfirmDialog from '@/components/ConfirmDialog';
import BackLink from '@/components/BackLink';
import PageHeader from '@/components/PageHeader';
import LoadError from '@/components/LoadError';
import ListSkeleton from '@/components/ListSkeleton';
import { pushBack, useNavigateBack } from '@/lib/backNavigation';
import { formatAmount } from '@/lib/format';
import { statusVariant, formatDateTime } from './format';
import TasksPanel from '@/features/tasks/TasksPanel';
import TrackersPanel from '@/features/trackers/TrackersPanel';
import NewTaskDialog from '@/features/tasks/NewTaskDialog';
import { taskKeys, useHouseholdMembersWithMe } from '@/features/tasks/hooks';
import {
  useProject,
  useProjectInteractions,
  useDeleteProject,
  usePinProject,
  projectKeys,
} from './hooks';
import ProjectDialog from './ProjectDialog';
import ReconciliationBadge from '@/features/money/ReconciliationBadge';
import EntityDocumentsTab from '@/features/documents/EntityDocumentsTab';
import EntityPhotosTab from '@/features/photos/EntityPhotosTab';
import ProjectPurchaseDialog from './ProjectPurchaseDialog';
import ProjectDashboard from './ProjectDashboard';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { useSessionState } from '@/lib/useSessionState';

type Tab =
  | 'overview'
  | 'tasks'
  | 'trackers'
  | 'notes'
  | 'expenses'
  | 'documents'
  | 'photos'
  | 'timeline';

/**
 * `overview` is always shown (pivot + entry points to create content). The other
 * tabs are hidden when empty and revealed as soon as they hold something — the
 * per-tab counts come from the project detail (`tab_counts`). Order preserved.
 */
const COUNTED_TABS: Exclude<Tab, 'overview'>[] = [
  'tasks',
  'trackers',
  'notes',
  'expenses',
  'documents',
  'photos',
  'timeline',
];

// ── Tab: interactions list ─────────────────────────────────

function TabInteractions({
  projectId,
  type,
  emptyKey,
  addUrl,
  addLabel,
  onAdd,
}: {
  projectId: string;
  type?: string;
  emptyKey: string;
  addUrl?: string;
  addLabel?: string;
  onAdd?: () => void;
}) {
  const { t } = useTranslation();
  const location = useLocation();
  const { data: items = [], isLoading, error } = useProjectInteractions(projectId, type);

  if (isLoading) {
    return <ListSkeleton rows={3} rowClassName="h-12" />;
  }

  if (error) {
    return (
      <p className="text-sm text-destructive">{t('common.error_loading')}</p>
    );
  }

  return (
    <div className="space-y-3">
      {onAdd ? (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onAdd}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-3.5 w-3.5" />
            {addLabel}
          </button>
        </div>
      ) : addUrl ? (
        <div className="flex justify-end">
          <Link
            to={addUrl}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-3.5 w-3.5" />
            {addLabel}
          </Link>
        </div>
      ) : null}

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">{t(emptyKey)}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                to={`/app/interactions/${item.id}`}
                state={pushBack(location)}
                className="block rounded-md border p-3 text-sm transition-colors hover:border-primary/40 hover:bg-muted"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium">{item.subject || '—'}</span>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {/* Le coût réel affiché en tête de fiche est la somme de ces
                        lignes : sans le montant sur chacune, le total ne se
                        vérifie pas et une saisie à 1 000 € au lieu de 100 € ne
                        se repère nulle part. Même rendu que l'historique d'un
                        équipement, qui le disait déjà. */}
                    {item.amount ? (
                      <span className="text-xs font-medium text-foreground">
                        {formatAmount(item.amount)}
                      </span>
                    ) : null}
                    {/* Une dépense de chantier saisie à la main est aussi une
                        dépense que la banque n'a peut-être jamais vue passer. */}
                    <ReconciliationBadge
                      state={item.reconciliation_state}
                      line={item.bank_line}
                      linked={false}
                    />
                    {item.type ? (
                      <Badge variant="outline" className="h-5 text-[10px]">
                        {t(`interactions.type.${item.type}`)}
                      </Badge>
                    ) : null}
                  </div>
                </div>
                {item.content ? (
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.content}</p>
                ) : null}
                {item.occurred_at ? (
                  <p className="mt-1 text-[10px] text-muted-foreground">{formatDateTime(item.occurred_at)}</p>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const navigateBack = useNavigateBack('/app/projects');
  const qc = useQueryClient();

  const [editOpen, setEditOpen] = React.useState(false);
  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [purchaseOpen, setPurchaseOpen] = React.useState(false);
  const [newTaskOpen, setNewTaskOpen] = React.useState(false);
  // Mirrors TabShell's active tab (same sessionKey) so an active-but-empty tab
  // stays visible until the user leaves it.
  const [activeTab, setActiveTab] = useSessionState<Tab>(
    `project-detail.${id ?? ''}.tab`,
    'overview',
  );

  const { data: project, isLoading, error } = useProject(id ?? '');
  const { data: householdMembers = [] } = useHouseholdMembersWithMe();
  const deleteProjectMutation = useDeleteProject();
  const pinProjectMutation = usePinProject();

  const handleSaved = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: projectKeys.all });
  }, [qc]);

  const handleTaskCreated = React.useCallback(() => {
    if (!id) return;
    void qc.invalidateQueries({ queryKey: taskKeys.project(id) });
    void qc.invalidateQueries({ queryKey: taskKeys.all });
    // Refresh tab_counts so the Tasks tab appears after the first task.
    void qc.invalidateQueries({ queryKey: projectKeys.detail(id) });
  }, [qc, id]);

  const showSkeleton = useDelayedLoading(isLoading);

  function handleDelete() {
    if (!id) return;
    deleteProjectMutation.mutate(id, {
      onSuccess: () => navigateBack(),
    });
  }

  if (showSkeleton) {
    return <ListSkeleton className="space-y-2 p-4" />;
  }
  if (isLoading) return null;

  if (error || !project) {
    return <LoadError message={t('projects.detail.error_loading')} />;
  }

  const planned = Number(project.planned_budget);
  const actual = Number(project.actual_cost_cached);
  const overBudget = actual > planned && planned > 0;

  const counts = project.tab_counts ?? null;
  // Visible tabs: overview always, others when they have content OR are currently
  // active (so the active tab doesn't vanish under the cursor when it empties).
  const isVisible = (tab: Exclude<Tab, 'overview'>) =>
    (counts ? counts[tab] > 0 : true) || tab === activeTab;
  const visibleTabs: TabConfig<Tab>[] = [
    { key: 'overview', label: t('projects.tabs.overview') },
    ...COUNTED_TABS.filter(isVisible).map((tab) => ({
      key: tab,
      label: t(`projects.tabs.${tab}`),
      badge: counts?.[tab],
    })),
  ];
  // Empty tabs, reachable via the « + » menu so the first item can still be added.
  const moreTabs: TabConfig<Tab>[] = COUNTED_TABS.filter((tab) => !isVisible(tab)).map(
    (tab) => ({ key: tab, label: t(`projects.tabs.${tab}`) }),
  );

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          backLink={<BackLink fallback="/app/projects" fallbackLabel={t('projects.title')} />}
          title={project.title}
          titleSuffix={
            <>
              <Badge variant={statusVariant(project.status)} className="text-xs">
                {t(`projects.status.${project.status}`)}
              </Badge>
              <Badge variant="outline" className="text-xs">
                {t(`projects.type.${project.type}`)}
              </Badge>
              <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                P{project.priority}
              </span>
              {project.project_group_name ? (
                <span className="text-xs text-muted-foreground">
                  {project.project_group_name}
                </span>
              ) : null}
            </>
          }
        >
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={() =>
              pinProjectMutation.mutate({ id: project.id, pinned: project.is_pinned })
            }
            disabled={pinProjectMutation.isPending}
            aria-label={project.is_pinned ? t('projects.unpin') : t('projects.pin')}
          >
            <Star
              className="h-4 w-4"
              fill={project.is_pinned ? 'currentColor' : 'none'}
            />
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-8 gap-1 px-3 text-sm"
            onClick={() => setPurchaseOpen(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            {t('projects.purchase.actions.add')}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-8 px-3 text-sm"
            onClick={() => setEditOpen(true)}
          >
            {t('projects.edit')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            className="h-8 px-3 text-sm"
            onClick={() => setDeleteOpen(true)}
          >
            {t('projects.delete')}
          </Button>
        </PageHeader>

        {/* Summary bar */}
        {(planned > 0 || actual > 0) ? (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm">
            {planned > 0 ? (
              <span>
                {t('projects.summary.budget')}{' '}
                <span className={`font-medium ${overBudget ? 'text-destructive' : ''}`}>
                  {formatAmount(actual, { fractionDigits: 0 })}
                </span>
                {' / '}{formatAmount(planned, { fractionDigits: 0 })}{' '}
                <span className="text-xs text-muted-foreground">
                  ({((actual / planned) * 100).toFixed(0)} %)
                </span>
              </span>
            ) : null}
          </div>
        ) : null}

        {/* Tabs */}
        <TabShell
          tabs={visibleTabs}
          moreTabs={moreTabs}
          sessionKey={`project-detail.${project.id}.tab`}
          defaultTab="overview"
          onTabChange={setActiveTab}
        >
          {(tab) => (
            <Card>
              <CardContent className="pt-4">
                {tab === 'overview' ? (
                  <ProjectDashboard
                    project={project}
                    onAddTask={() => setNewTaskOpen(true)}
                  />
                ) : null}

                {tab === 'tasks' ? (
                  <TasksPanel
                    projectId={project.id}
                    stateKeyPrefix={`project.${project.id}`}
                  />
                ) : null}

                {tab === 'trackers' ? (
                  <TrackersPanel
                    projectId={project.id}
                    stateKeyPrefix={`project.${project.id}.trackers`}
                  />
                ) : null}

                {tab === 'notes' ? (
                  <TabInteractions
                    projectId={project.id}
                    type="note"
                    emptyKey="projects.empty_notes"
                    addUrl={`/app/interactions/new?type=note&project_id=${project.id}`}
                    addLabel={t('projects.add_note')}
                  />
                ) : null}

                {tab === 'expenses' ? (
                  <TabInteractions
                    projectId={project.id}
                    type="expense"
                    emptyKey="projects.empty_expenses"
                    onAdd={() => setPurchaseOpen(true)}
                    addLabel={t('projects.purchase.actions.add')}
                  />
                ) : null}

                {tab === 'documents' ? (
                  <EntityDocumentsTab entityType="project" objectId={project.id} />
                ) : null}

                {tab === 'photos' ? (
                  <EntityPhotosTab entityType="project" objectId={project.id} />
                ) : null}

                {tab === 'timeline' ? (
                  <TabInteractions
                    projectId={project.id}
                    emptyKey="projects.empty_timeline"
                    addUrl={`/app/interactions/new?project_id=${project.id}`}
                    addLabel={t('projects.add_activity')}
                  />
                ) : null}
              </CardContent>
            </Card>
          )}
        </TabShell>
      </div>

      <ProjectDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        existingProject={project}
        onSaved={handleSaved}
      />

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={t('common.confirmDelete')}
        description={t('projects.delete_confirm', { title: project.title })}
        onConfirm={handleDelete}
        loading={deleteProjectMutation.isPending}
      />

      <ProjectPurchaseDialog
        open={purchaseOpen}
        onOpenChange={setPurchaseOpen}
        project={project}
      />

      <NewTaskDialog
        open={newTaskOpen}
        onOpenChange={setNewTaskOpen}
        onCreated={handleTaskCreated}
        householdMembers={householdMembers}
        defaultProjectId={project.id}
      />
    </>
  );
}
