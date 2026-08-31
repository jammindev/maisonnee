import * as React from 'react';
import { Pencil, Trash2, ListTodo } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Badge } from '@/design-system/badge';
import { Button } from '@/design-system/button';
import PrivateBadge from '@/components/PrivateBadge';
import { Card, CardTitle } from '@/design-system/card';
import { pushBack } from '@/lib/backNavigation';
import { appLocale } from '@/lib/format';
import type { InteractionListItem } from '@/lib/api/interactions';
import NewTaskDialog from '@/features/tasks/NewTaskDialog';

interface InteractionCardProps {
  item: InteractionListItem;
  onDelete: (id: string) => void;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(appLocale(), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default function InteractionCard({ item, onDelete }: InteractionCardProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [taskDialogOpen, setTaskDialogOpen] = React.useState(false);

  const typeLabelKey = `equipment.interaction_type.${item.type}`;

  return (
    <Card className="p-3 transition-shadow hover:shadow-md">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {item.is_redacted ? (
              // Masqué, pas caché. La ligne et son montant restent — sept
              // agrégations les lisent, et un total qu'on ne peut pas recomposer ne
              // se lit pas — mais rien ici ne la nomme. Le lien de détail saute
              // avec : il n'y aurait rien à y lire, et une promesse d'adresse qui
              // mène à un écran vide se retourne contre l'app.
              <CardTitle className="text-muted-foreground">
                {t('privacy.redactedExpense')}
              </CardTitle>
            ) : (
              <Link
                to={`/app/interactions/${item.id}`}
                state={pushBack(location)}
                className="group text-foreground hover:text-primary"
              >
                <CardTitle className="text-inherit [&>span:last-child]:group-hover:underline">
                  {item.subject}
                </CardTitle>
              </Link>
            )}
            <Badge variant="outline">{t(typeLabelKey)}</Badge>
            {item.is_redacted ? <PrivateBadge variant="icon" /> : null}
          </div>

          {item.content ? (
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.content}</p>
          ) : null}

          {(item.zone_names.length > 0 || item.document_count > 0 || item.tags.length > 0) ? (
            <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {item.zone_names.length > 0 ? (
                <span>
                  {t('interactions.meta_zones')}: {item.zone_names.join(', ')}
                </span>
              ) : null}
              {item.document_count > 0 ? (
                <span>
                  {t('interactions.meta_documents', { count: item.document_count })}
                </span>
              ) : null}
              {item.tags.length > 0 ? (
                <span className="flex flex-wrap gap-1">
                  {item.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full bg-muted px-1.5 py-0.5 text-xs"
                    >
                      {tag}
                    </span>
                  ))}
                </span>
              ) : null}
            </div>
          ) : null}

          {item.source_type === 'projects.project' && item.source_id && item.source_label ? (
            <div className="mt-1 text-xs text-muted-foreground">
              <span>{t('interactions.project_label')}: </span>
              <Link
                to={`/app/projects/${item.source_id}`}
                state={pushBack(location)}
                className="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                {item.source_label}
              </Link>
            </div>
          ) : null}

          <p className="mt-1 text-xs text-muted-foreground">{formatDate(item.occurred_at)}</p>
        </div>

        <div className="flex flex-shrink-0 items-center gap-0.5">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={() => setTaskDialogOpen(true)}
            aria-label={t('interactions.createTask')}
            title={t('interactions.createTask')}
            type="button"
          >
            <ListTodo className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={() => navigate(`/app/interactions/${item.id}/edit`)}
            aria-label={t('common.edit')}
            type="button"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(item.id)}
            aria-label={t('common.delete')}
            type="button"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <NewTaskDialog
        open={taskDialogOpen}
        onOpenChange={setTaskDialogOpen}
        onCreated={() => setTaskDialogOpen(false)}
        defaultSubject={item.subject}
        defaultZoneIds={item.zone_id_list ?? []}
        sourceInteractionId={item.id}
      />
    </Card>
  );
}
