import { Link } from 'react-router-dom';
import { Pencil, Plus, Star, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/design-system/badge';
import { Button } from '@/design-system/button';
import PrivateBadge from '@/components/PrivateBadge';
import { Card, CardTitle } from '@/design-system/card';
import CardActions, { type CardAction } from '@/components/CardActions';
import { formatAmount } from '@/lib/format';
import type { ProjectListItem, ProjectType } from '@/lib/api/projects';
import { statusVariant, formatDate, isOverdue, isDueSoon } from './format';

function typeColor(type: ProjectType): string {
  const map: Record<ProjectType, string> = {
    renovation: 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800',
    maintenance: 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800',
    repair: 'bg-red-50 text-red-800 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800',
    purchase: 'bg-green-50 text-green-800 border-green-200 dark:bg-green-950/40 dark:text-green-300 dark:border-green-800',
    relocation: 'bg-purple-50 text-purple-800 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800',
    vacation: 'bg-cyan-50 text-cyan-800 border-cyan-200 dark:bg-cyan-950/40 dark:text-cyan-300 dark:border-cyan-800',
    leisure: 'bg-pink-50 text-pink-800 border-pink-200 dark:bg-pink-950/40 dark:text-pink-300 dark:border-pink-800',
    other: 'bg-muted text-muted-foreground border-border',
  };
  return map[type] ?? map.other;
}

function BudgetBar({ planned, actual }: { planned: number; actual: number }) {
  if (!planned) return null;
  const pct = Math.min((actual / planned) * 100, 100);
  const overBudget = actual > planned;
  return (
    <div className="mt-1">
      <div className="mb-0.5 flex justify-between text-[10px] text-muted-foreground">
        <span>{formatAmount(actual, { fractionDigits: 0 })}</span>
        <span>{formatAmount(planned, { fractionDigits: 0 })}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all ${overBudget ? 'bg-destructive' : 'bg-primary'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

interface ProjectCardProps {
  project: ProjectListItem;
  onEdit: (project: ProjectListItem) => void;
  onDelete: (projectId: string) => void;
  onTogglePin?: (project: ProjectListItem) => void;
  onPurchase?: (project: ProjectListItem) => void;
  pinLoading?: boolean;
}

export default function ProjectCard({
  project,
  onEdit,
  onDelete,
  onTogglePin,
  onPurchase,
  pinLoading = false,
}: ProjectCardProps) {
  const { t } = useTranslation();
  const overdue = isOverdue(project);
  const dueSoon = isDueSoon(project);

  const menuActions: CardAction[] = [
    { label: t('projects.edit'), icon: Pencil, onClick: () => onEdit(project) },
    { label: t('projects.delete'), icon: Trash2, onClick: () => onDelete(project.id), variant: 'danger' },
  ];

  return (
    <Card className="p-4 transition-shadow hover:shadow-md">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <Link
            to={`/app/projects/${project.id}`}
            className="group text-foreground hover:text-primary"
          >
            <CardTitle className="font-semibold leading-tight text-inherit [&>span:last-child]:group-hover:underline">{project.title}</CardTitle>
          </Link>
          {project.is_private ? <PrivateBadge className="mt-1" /> : null}
          {project.description ? (
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{project.description}</p>
          ) : null}
        </div>

        <div className="flex flex-shrink-0 items-center gap-0.5">
          {onTogglePin ? (
            <Button
              variant="ghost"
              size="icon"
              className={`h-7 w-7 ${project.is_pinned ? 'text-primary' : 'text-muted-foreground hover:text-foreground'}`}
              onClick={() => onTogglePin(project)}
              disabled={pinLoading}
              aria-label={project.is_pinned ? t('projects.unpin') : t('projects.pin')}
              type="button"
            >
              <Star
                className="h-3.5 w-3.5"
                fill={project.is_pinned ? 'currentColor' : 'none'}
              />
            </Button>
          ) : null}
          <CardActions actions={menuActions} />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <span
          className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-medium ${typeColor(project.type)}`}
        >
          {t(`projects.type.${project.type}`)}
        </span>
        <Badge variant={statusVariant(project.status)} className="h-5 text-[10px]">
          {t(`projects.status.${project.status}`)}
        </Badge>
        {overdue ? (
          <Badge variant="destructive" className="h-5 text-[10px]">
            {t('projects.overdue')}
          </Badge>
        ) : dueSoon ? (
          <Badge variant="secondary" className="h-5 text-[10px]">
            {t('projects.due_soon')}
          </Badge>
        ) : null}
        {project.project_group_name ? (
          <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {project.project_group_name}
          </span>
        ) : null}
        {project.zones.length > 0 ? (
          <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {project.zones.map((z) => z.name).join(', ')}
          </span>
        ) : null}
      </div>

      {project.due_date || project.start_date ? (
        <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
          {project.start_date ? (
            <span>
              <span className="font-medium">{t('projects.start_date')}: </span>
              {formatDate(project.start_date)}
            </span>
          ) : null}
          {project.due_date ? (
            <span>
              <span className="font-medium">{t('projects.due_date')}: </span>
              {formatDate(project.due_date)}
            </span>
          ) : null}
        </div>
      ) : null}

      {Number(project.planned_budget) > 0 || Number(project.actual_cost_cached) > 0 ? (
        <div className="mt-3">
          <div className="mb-1 text-xs text-muted-foreground">
            <span className="font-medium">{t('projects.budget')}</span>
          </div>
          <BudgetBar
            planned={Number(project.planned_budget)}
            actual={Number(project.actual_cost_cached)}
          />
        </div>
      ) : null}

      {onPurchase ? (
        <div className="mt-3 flex justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onPurchase(project)}
            className="h-7 gap-1 px-2 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            {t('projects.purchase.actions.add')}
          </Button>
        </div>
      ) : null}
    </Card>
  );
}
