import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { Check, FolderKanban, Pencil, Plus, Trash2 } from 'lucide-react';

import CardActions, { type CardAction } from '@/components/CardActions';
import Sparkline from '@/components/Sparkline';
import { Card, CardTitle } from '@/design-system/card';
import { DecimalInput } from '@/design-system/decimal-input';
import { formatTrackerValue, type Tracker } from '@/lib/api/trackers';
import { pushBack } from '@/lib/backNavigation';

interface TrackerCardProps {
  tracker: Tracker;
  onEdit: (tracker: Tracker) => void;
  onDelete: (trackerId: string) => void;
  onQuickAdd: (tracker: Tracker, value: string) => Promise<void>;
}

function formatRelativeFrom(iso: string | null, locale?: string): string | null {
  if (!iso) return null;
  const diffMs = new Date(iso).getTime() - Date.now();
  const days = Math.round(diffMs / 86_400_000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
  if (Math.abs(days) >= 30) return rtf.format(Math.round(days / 30), 'month');
  if (Math.abs(days) >= 1) return rtf.format(days, 'day');
  const hours = Math.round(diffMs / 3_600_000);
  if (Math.abs(hours) >= 1) return rtf.format(hours, 'hour');
  return rtf.format(Math.round(diffMs / 60_000), 'minute');
}

export default function TrackerCard({
  tracker,
  onEdit,
  onDelete,
  onQuickAdd,
}: TrackerCardProps) {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const [quickAddOpen, setQuickAddOpen] = React.useState(false);
  const [quickValue, setQuickValue] = React.useState('');
  const [saving, setSaving] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const relative = formatRelativeFrom(tracker.last_entry_at, i18n.language);
  const sparkPoints = tracker.sparkline.map((p) => ({
    t: p.occurred_at,
    v: Number(p.value),
  }));

  const actions: CardAction[] = [
    { label: t('common.edit'), icon: Pencil, onClick: () => onEdit(tracker) },
    {
      label: t('common.delete'),
      icon: Trash2,
      onClick: () => onDelete(tracker.id),
      variant: 'danger',
    },
  ];

  const openQuickAdd = () => {
    setQuickValue(tracker.last_value ? formatTrackerValue(tracker.last_value) : '');
    setQuickAddOpen(true);
    requestAnimationFrame(() => inputRef.current?.select());
  };

  const submitQuickAdd = async () => {
    const value = quickValue.trim();
    if (!value || Number.isNaN(Number(value))) return;
    setSaving(true);
    try {
      await onQuickAdd(tracker, value);
      setQuickAddOpen(false);
      setQuickValue('');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <Link
            to={`/app/trackers/${tracker.id}`}
            state={pushBack(location)}
            className="group text-foreground hover:text-primary"
          >
            <CardTitle className="text-inherit [&>span:last-child]:group-hover:underline">
              {`${tracker.emoji ? `${tracker.emoji} ` : ''}${tracker.name}`}
            </CardTitle>
          </Link>

          <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            {tracker.last_value != null ? (
              <>
                <span className="text-lg font-semibold text-foreground">
                  {formatTrackerValue(tracker.last_value)}
                  {tracker.unit ? (
                    <span className="ml-1 text-xs font-normal text-muted-foreground">
                      {tracker.unit}
                    </span>
                  ) : null}
                </span>
                {relative ? (
                  <span className="text-xs text-muted-foreground">{relative}</span>
                ) : null}
              </>
            ) : (
              <span className="text-xs text-muted-foreground">{t('trackers.noEntries')}</span>
            )}
          </div>

          {tracker.project && tracker.project_title ? (
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
              <Link
                to={`/app/projects/${tracker.project}`}
                state={pushBack(location)}
                className="inline-flex items-center gap-1 hover:text-foreground hover:underline"
              >
                <FolderKanban className="h-3 w-3" />
                {tracker.project_title}
              </Link>
            </div>
          ) : null}
        </div>

        <div className="flex flex-shrink-0 flex-col items-end gap-1">
          <CardActions actions={actions} />
          {sparkPoints.length > 0 ? (
            <span className="text-primary/70">
              <Sparkline points={sparkPoints} width={96} height={28} />
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-2">
        {quickAddOpen ? (
          <form
            className="flex items-center gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              void submitQuickAdd();
            }}
          >
            <DecimalInput
              ref={inputRef}
              decimals={3}
              allowNegative
              value={quickValue}
              onChange={setQuickValue}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setQuickAddOpen(false);
              }}
              placeholder={t('trackers.quickAddPlaceholder')}
              className="h-8 flex-1 md:text-sm"
              disabled={saving}
              autoFocus
            />
            {tracker.unit ? (
              <span className="text-xs text-muted-foreground">{tracker.unit}</span>
            ) : null}
            <button
              type="submit"
              disabled={saving}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground disabled:opacity-50"
              aria-label={t('trackers.addValue')}
            >
              <Check className="h-4 w-4" />
            </button>
          </form>
        ) : (
          <button
            type="button"
            onClick={openQuickAdd}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-primary"
          >
            <Plus className="h-3 w-3" />
            {t('trackers.addValue')}
          </button>
        )}
      </div>
    </Card>
  );
}
