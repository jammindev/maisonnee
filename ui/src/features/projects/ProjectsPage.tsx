import * as React from 'react';
import { FolderOpen, FolderKanban, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import ListPage from '@/components/ListPage';
import { TabShell } from '@/components/TabShell';
import { FilterBar } from '@/design-system/filter-bar';
import ConfirmDialog from '@/components/ConfirmDialog';
import { useDeleteWithUndo } from '@/lib/useDeleteWithUndo';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { useCapability } from '@/lib/capabilities';
import type { ProjectListItem, ProjectGroupItem } from '@/lib/api/projects';
import {
  useProjects,
  useProjectGroups,
  useDeleteProject,
  useDeleteGroup,
  projectKeys,
} from './hooks';
import ProjectCard from './ProjectCard';
import ProjectDialog from './ProjectDialog';
import ProjectPurchaseDialog from './ProjectPurchaseDialog';
import ProjectAssistantDialog from './assistant/ProjectAssistantDialog';
import GroupCard from './GroupCard';
import GroupDialog from './GroupDialog';

type TabKey = 'projects' | 'groups';

const STATUS_OPTIONS = ['', 'draft', 'active', 'on_hold', 'completed', 'cancelled'];
const TYPE_OPTIONS = [
  '', 'renovation', 'maintenance', 'repair', 'purchase',
  'relocation', 'vacation', 'leisure', 'other',
];

export default function ProjectsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  // Project filters
  const [search, setSearch] = React.useState('');
  const [status, setStatus] = React.useState('active');
  const [type, setType] = React.useState('');

  // Project dialog
  const [projectDialogOpen, setProjectDialogOpen] = React.useState(false);

  // Création assistée (parcours 32). La capacité décide de la **présence** du
  // bouton, jamais de son état désactivé : un bouton grisé promet et dément dans
  // le même geste, et le repli n'est pas une version dégradée de l'entretien —
  // c'est le formulaire, qui est juste à côté.
  const [assistantOpen, setAssistantOpen] = React.useState(false);
  const { available: canUseAssistant } = useCapability('project_assistant');
  const [editingProject, setEditingProject] = React.useState<ProjectListItem | null>(null);

  // Group dialog
  const [groupDialogOpen, setGroupDialogOpen] = React.useState(false);
  const [editingGroup, setEditingGroup] = React.useState<ProjectGroupItem | null>(null);
  const [deletingGroupId, setDeletingGroupId] = React.useState<string | null>(null);

  // Purchase dialog
  const [purchaseDialogOpen, setPurchaseDialogOpen] = React.useState(false);
  const [purchasingProject, setPurchasingProject] = React.useState<ProjectListItem | null>(null);

  const handleOpenPurchase = React.useCallback((project: ProjectListItem) => {
    setPurchasingProject(project);
    setPurchaseDialogOpen(true);
  }, []);

  const filters = React.useMemo(
    () => ({
      ...(search ? { search } : {}),
      ...(status ? { status } : {}),
      ...(type ? { type } : {}),
    }),
    [search, status, type],
  );

  const { data: projects = [], isLoading: projectsLoading, error: projectsError } = useProjects(filters);
  const { data: groups = [], isLoading: groupsLoading, error: groupsError } = useProjectGroups();
  const deleteProjectMutation = useDeleteProject();
  const deleteGroupMutation = useDeleteGroup();

  // Sort projects: pinned first
  const sortedProjects = React.useMemo(
    () =>
      [...projects].sort((a, b) => {
        if (a.is_pinned === b.is_pinned) return 0;
        return a.is_pinned ? -1 : 1;
      }),
    [projects],
  );

  const handleProjectSaved = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: projectKeys.all });
  }, [qc]);

  const handleGroupSaved = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: projectKeys.groups() });
  }, [qc]);

  // Delete project with undo
  const { deleteWithUndo } = useDeleteWithUndo({
    label: t('projects.deleted'),
    onDelete: (id) => deleteProjectMutation.mutateAsync(id),
  });

  const handleDeleteProject = React.useCallback(
    (projectId: string) => {
      const project = sortedProjects.find((p) => p.id === projectId);
      if (!project) return;
      deleteWithUndo(projectId, {
        onRemove: () =>
          qc.setQueryData<ProjectListItem[]>(projectKeys.list(filters), (old) =>
            old?.filter((p) => p.id !== projectId),
          ),
        onRestore: () =>
          qc.setQueryData<ProjectListItem[]>(projectKeys.list(filters), (old) =>
            old ? [...old, project] : [project],
          ),
      });
    },
    [sortedProjects, deleteWithUndo, qc, filters],
  );

  // Delete group with confirm dialog
  const handleConfirmDeleteGroup = React.useCallback(() => {
    if (!deletingGroupId) return;
    deleteGroupMutation.mutate(deletingGroupId, {
      onSuccess: () => setDeletingGroupId(null),
      onError: () => setDeletingGroupId(null),
    });
  }, [deletingGroupId, deleteGroupMutation]);

  function resetFilters() {
    setSearch('');
    setStatus('active');
    setType('');
  }

  const hasActiveFilters = !!(search || status !== 'active' || type);
  const isProjectsEmpty = !projectsLoading && !projectsError && sortedProjects.length === 0;
  const isGroupsEmpty = !groupsLoading && !groupsError && groups.length === 0;
  const showProjectsSkeleton = useDelayedLoading(projectsLoading);
  const showGroupsSkeleton = useDelayedLoading(groupsLoading);

  const TABS: { key: TabKey; label: string }[] = [
    { key: 'projects', label: t('projects.title') },
    { key: 'groups', label: t('projects.groups.title') },
  ];

  return (
    <>
      <TabShell
        tabs={TABS}
        sessionKey="projects.tab"
        defaultTab="projects"
        actions={(tab) => {
          if (tab === 'projects') {
            return (
              <div className="flex items-center gap-2">
                {canUseAssistant ? (
                  <button
                    type="button"
                    onClick={() => setAssistantOpen(true)}
                    className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-sm font-medium text-foreground"
                  >
                    <Sparkles className="h-4 w-4 text-primary" aria-hidden />
                    {t('projects.assistant.new')}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => setProjectDialogOpen(true)}
                  className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
                >
                  {t('projects.new')}
                </button>
              </div>
            );
          }
          if (tab === 'groups') {
            return (
              <button
                type="button"
                onClick={() => setGroupDialogOpen(true)}
                className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
              >
                {t('projects.groups.new')}
              </button>
            );
          }
          return null;
        }}
      >
        {(tab) => (
          <>
            {/* Projects tab */}
            {tab === 'projects' ? (
              <ListPage
                title={t('projects.title')}
                isEmpty={isProjectsEmpty}
                emptyState={
                  hasActiveFilters
                    ? {
                        icon: FolderOpen,
                        title: t('projects.no_filter_results'),
                      }
                    : {
                        icon: FolderOpen,
                        title: t('projects.empty_list'),
                        description: t('projects.empty_description'),
                        action: { label: t('projects.new'), onClick: () => setProjectDialogOpen(true) },
                      }
                }
              >
                <div className="space-y-4">
                  <FilterBar
                    fields={[
                      {
                        type: 'search',
                        id: 'proj-search',
                        label: t('projects.search'),
                        value: search,
                        onChange: setSearch,
                        placeholder: t('projects.search_placeholder'),
                      },
                      {
                        type: 'select',
                        id: 'proj-status',
                        label: t('projects.status_label'),
                        value: status,
                        onChange: setStatus,
                        options: STATUS_OPTIONS.map((s) => ({
                          value: s,
                          label: s ? t(`projects.status.${s}`) : t('projects.all_statuses'),
                        })),
                      },
                      {
                        type: 'select',
                        id: 'proj-type',
                        label: t('projects.type_label'),
                        value: type,
                        onChange: setType,
                        options: TYPE_OPTIONS.map((tp) => ({
                          value: tp,
                          label: tp ? t(`projects.type.${tp}`) : t('projects.all_types'),
                        })),
                      },
                    ]}
                    onReset={resetFilters}
                    hasActiveFilters={hasActiveFilters}
                    resetLabel={t('projects.reset')}
                    applyLabel={t('projects.apply')}
                  />

                  {projectsError ? (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                      {t('projects.error_loading_list')}
                      <button
                        type="button"
                        onClick={() => qc.invalidateQueries({ queryKey: projectKeys.all })}
                        className="ml-2 underline hover:no-underline"
                      >
                        {t('common.retry')}
                      </button>
                    </div>
                  ) : null}

                  {showProjectsSkeleton ? (
                    <div className="space-y-2">
                      {[1, 2, 3].map((i) => (
                        <div key={i} className="h-14 animate-pulse rounded-lg bg-muted" />
                      ))}
                    </div>
                  ) : null}

                  {!projectsLoading && !projectsError ? (
                    <div className="space-y-3">
                      {sortedProjects.map((project) => (
                        <ProjectCard
                          key={project.id}
                          project={project}
                          onEdit={setEditingProject}
                          onDelete={handleDeleteProject}
                          onPurchase={handleOpenPurchase}
                        />
                      ))}
                    </div>
                  ) : null}
                </div>
              </ListPage>
            ) : null}

            {/* Groups tab */}
            {tab === 'groups' ? (
              <ListPage
                title={t('projects.groups.title')}
                isEmpty={isGroupsEmpty}
                emptyState={{
                  icon: FolderKanban,
                  title: t('projects.groups.empty'),
                  description: t('projects.groups.empty_description'),
                  action: { label: t('projects.groups.new'), onClick: () => setGroupDialogOpen(true) },
                }}
              >
                <div className="space-y-2">
                  {groupsError ? (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                      {t('projects.groups.error_loading')}
                      <button
                        type="button"
                        onClick={() => qc.invalidateQueries({ queryKey: projectKeys.groups() })}
                        className="ml-2 underline hover:no-underline"
                      >
                        {t('common.retry')}
                      </button>
                    </div>
                  ) : null}

                  {showGroupsSkeleton ? (
                    <div className="space-y-2">
                      {[1, 2, 3].map((i) => (
                        <div key={i} className="h-14 animate-pulse rounded-lg bg-muted" />
                      ))}
                    </div>
                  ) : null}

                  {!groupsLoading && !groupsError ? (
                    <div className="space-y-2">
                      {groups.map((group) => (
                        <GroupCard
                          key={group.id}
                          group={group}
                          onEdit={setEditingGroup}
                          onDelete={setDeletingGroupId}
                        />
                      ))}
                    </div>
                  ) : null}
                </div>
              </ListPage>
            ) : null}
          </>
        )}
      </TabShell>

      {/* Dialogs — outside TabShell to avoid remount on tab switch */}
      <ProjectAssistantDialog open={assistantOpen} onOpenChange={setAssistantOpen} />
      <ProjectDialog
        open={projectDialogOpen}
        onOpenChange={setProjectDialogOpen}
        onSaved={handleProjectSaved}
      />

      <ProjectDialog
        open={editingProject !== null}
        onOpenChange={(open) => {
          if (!open) setEditingProject(null);
        }}
        existingProject={editingProject ?? undefined}
        onSaved={handleProjectSaved}
      />

      <GroupDialog
        open={groupDialogOpen}
        onOpenChange={setGroupDialogOpen}
        onSaved={handleGroupSaved}
      />

      <GroupDialog
        open={editingGroup !== null}
        onOpenChange={(open) => {
          if (!open) setEditingGroup(null);
        }}
        existingGroup={editingGroup ?? undefined}
        onSaved={handleGroupSaved}
      />

      <ConfirmDialog
        open={deletingGroupId !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingGroupId(null);
        }}
        title={t('common.confirmDelete')}
        description={t('projects.groups.delete_confirm', {
          name: groups.find((g) => g.id === deletingGroupId)?.name ?? '',
        })}
        onConfirm={handleConfirmDeleteGroup}
        loading={deleteGroupMutation.isPending}
      />

      <ProjectPurchaseDialog
        open={purchaseDialogOpen}
        onOpenChange={(open) => {
          setPurchaseDialogOpen(open);
          if (!open) setPurchasingProject(null);
        }}
        project={purchasingProject}
      />
    </>
  );
}
