import { useTranslation } from 'react-i18next';

import PrivateBadge from '@/components/PrivateBadge';
import { Clock, Eye, History, Pencil, Power, Trash2, Users } from 'lucide-react';
import { Card, CardTitle } from '@/design-system/card';
import { Badge } from '@/design-system/badge';
import { Button } from '@/design-system/button';
import CardActions, { type CardAction } from '@/components/CardActions';
import { cn } from '@/lib/utils';
import type { Briefing } from '@/lib/api/briefings';
import { formatNextSend, scheduleSummary } from './schedule';

interface Props {
  briefing: Briefing;
  onEdit: (briefing: Briefing) => void;
  onDelete: (briefing: Briefing) => void;
  onToggleActive: (briefing: Briefing) => void;
  onPreview: (briefing: Briefing) => void;
  onHistory: (briefing: Briefing) => void;
}

export default function BriefingCard({
  briefing,
  onEdit,
  onDelete,
  onToggleActive,
  onPreview,
  onHistory,
}: Props) {
  const { t, i18n } = useTranslation();

  const nextSend = briefing.is_active ? formatNextSend(briefing.next_send_at, i18n.language) : null;
  const lastSend = briefing.last_send;

  const actions: CardAction[] = [
    { label: t('briefings.preview.action'), icon: Eye, onClick: () => onPreview(briefing) },
    { label: t('briefings.history.action'), icon: History, onClick: () => onHistory(briefing) },
    { label: t('common.edit'), icon: Pencil, onClick: () => onEdit(briefing) },
    { label: t('common.delete'), icon: Trash2, onClick: () => onDelete(briefing), variant: 'danger' },
  ];

  return (
    <Card className="p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>{briefing.title}</CardTitle>
            {briefing.is_private ? (
              <PrivateBadge />
            ) : (
              <Badge variant="secondary" className="gap-1">
                <Users className="h-3 w-3" aria-hidden="true" />
                {t('privacy.shared')}
              </Badge>
            )}
          </div>

          <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{briefing.prompt}</p>

          {briefing.condition ? (
            <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
              <span className="font-medium">{t('briefings.fields.condition')}:</span>{' '}
              {briefing.condition}
            </p>
          ) : null}

          <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3 shrink-0" />
            {scheduleSummary(briefing, t)}
          </p>
        </div>

        <CardActions actions={actions} />
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn('gap-1', briefing.is_active ? 'text-primary' : 'text-muted-foreground')}
          onClick={() => onToggleActive(briefing)}
        >
          <Power className="h-4 w-4" />
          {briefing.is_active ? t('briefings.active') : t('briefings.inactive')}
        </Button>
        {nextSend ? (
          <span className="truncate text-xs text-muted-foreground">
            {t('briefings.schedule.nextSend')} : {nextSend}
          </span>
        ) : lastSend ? (
          <button
            type="button"
            onClick={() => onHistory(briefing)}
            className="truncate text-xs text-muted-foreground hover:text-foreground"
          >
            {t(`briefings.history.status.${lastSend.status}`)} ·{' '}
            {formatNextSend(lastSend.created_at, i18n.language)}
          </button>
        ) : null}
      </div>
    </Card>
  );
}
