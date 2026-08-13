import * as React from 'react';
import { AlertCircle, Bell } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/design-system/dropdown-menu';
import { useAcceptInvitation, useDeclineInvitation } from '@/features/settings/hooks';
import { useAlertsSummary } from '@/features/alerts/hooks';
import { EMPTY_ALERTS_SUMMARY, buildAlertSections, flattenAlertRows, type AlertRow } from '@/features/alerts/rows';
import { Button } from '@/design-system/button';
import { appLocale } from '@/lib/format';
import { pushBack } from '@/lib/backNavigation';
import { triggerBellRefresh } from '@/lib/notifications';
import type { NotificationItem } from '@/lib/api/notifications';

import { useMarkAllRead, useMarkRead, useNotifications, useUnreadCount } from './hooks';
import { buildBellPreview } from './preview';

const MAX_PREVIEW = 5;
const MAX_ALERTS_PREVIEW = 3;

function relativeShort(dateStr: string): string {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '';
  const diffMin = Math.round((date.getTime() - Date.now()) / 60_000);
  const diffHours = Math.round(diffMin / 60);
  const diffDays = Math.round(diffHours / 24);
  try {
    const rtf = new Intl.RelativeTimeFormat(appLocale(), { numeric: 'auto', style: 'narrow' });
    if (Math.abs(diffMin) < 60) return rtf.format(diffMin, 'minute');
    if (Math.abs(diffHours) < 24) return rtf.format(diffHours, 'hour');
    return rtf.format(diffDays, 'day');
  } catch {
    return date.toLocaleDateString(appLocale());
  }
}

export default function NotificationsBell() {
  const { t, i18n } = useTranslation();
  const { data: notifications = [] } = useNotifications();
  const { data: unreadCount = 0 } = useUnreadCount();
  const { data: alertsSummary } = useAlertsSummary();
  const markAllRead = useMarkAllRead();

  // L'ordre de l'aperçu est calculé à l'ouverture puis **figé** tant que le menu
  // reste ouvert : marquer une ligne lue la ferait sinon glisser derrière les
  // autres non-lues, sous le curseur de celui qui allait cliquer la suivante.
  const [open, setOpen] = React.useState(false);
  const [pinnedIds, setPinnedIds] = React.useState<readonly string[]>([]);

  const preview = buildBellPreview(notifications, MAX_PREVIEW, pinnedIds);
  const hasUnread = unreadCount > 0;

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen);
    setPinnedIds(
      nextOpen ? buildBellPreview(notifications, MAX_PREVIEW).map((n) => n.id) : [],
    );
  }

  // Une alerte est un état recalculé, pas un événement : elle ne se lit ni ne
  // s'écarte. L'ajouter au badge chiffré fabriquerait un compteur qui ne
  // redescend jamais — d'où un point, sans nombre, à côté des non-lus.
  const alerts = flattenAlertRows(
    buildAlertSections(alertsSummary ?? EMPTY_ALERTS_SUMMARY, t, i18n.language),
  );
  const alertsPreview = alerts.slice(0, MAX_ALERTS_PREVIEW);

  const ariaLabel = hasUnread
    ? t('notifications.bellAriaLabelUnread', { count: unreadCount })
    : t('notifications.bellAriaLabel');

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="relative p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          aria-label={ariaLabel}
          data-testid="notifications-bell"
        >
          <Bell className="h-5 w-5" />
          {hasUnread ? (
            <span
              className="absolute -top-0.5 -right-0.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground"
              data-testid="notifications-bell-badge"
            >
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          ) : null}
          {alerts.length > 0 ? (
            <span
              className="absolute -bottom-0.5 -right-0.5 inline-block h-2 w-2 rounded-full bg-amber-500 ring-2 ring-sidebar"
              data-testid="notifications-bell-alerts-dot"
              aria-label={t('alerts.badgeAriaLabel', { count: alerts.length })}
            />
          ) : null}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-0" data-testid="notifications-dropdown">
        {alertsPreview.length > 0 ? (
          <>
            <div className="flex items-center justify-between px-3 py-2">
              <DropdownMenuLabel className="flex items-center gap-1.5 px-0 py-0 text-sm">
                <AlertCircle className="h-4 w-4 text-amber-500" aria-hidden />
                {t('alerts.title')}
                <span className="text-muted-foreground">({alerts.length})</span>
              </DropdownMenuLabel>
              <Link to="/app/alerts" className="text-xs text-primary hover:underline">
                {t('alerts.viewAll')}
              </Link>
            </div>
            <ul className="py-1">
              {alertsPreview.map((row) => (
                <li key={row.key}>
                  <AlertDropdownItem row={row} onNavigate={() => setOpen(false)} />
                </li>
              ))}
            </ul>
            <DropdownMenuSeparator className="my-0" />
          </>
        ) : null}

        <div className="flex items-center justify-between px-3 py-2">
          <DropdownMenuLabel className="px-0 py-0 text-sm">{t('notifications.title')}</DropdownMenuLabel>
          {hasUnread ? (
            <button
              type="button"
              className="text-xs text-primary hover:underline disabled:opacity-50"
              disabled={markAllRead.isPending}
              onClick={() => markAllRead.mutate()}
            >
              {t('notifications.markAllRead')}
            </button>
          ) : null}
        </div>
        <DropdownMenuSeparator className="my-0" />

        {preview.length === 0 ? (
          <div className="px-3 py-6 text-center text-sm text-muted-foreground">
            {t('notifications.empty')}
          </div>
        ) : (
          <ul className="max-h-96 overflow-y-auto py-1">
            {preview.map((n) => (
              <li key={n.id}>
                <NotificationDropdownItem notification={n} onNavigate={() => setOpen(false)} />
              </li>
            ))}
          </ul>
        )}

        <DropdownMenuSeparator className="my-0" />
        <div className="px-1 py-1">
          <Link
            to="/app/notifications"
            className="block w-full rounded-md px-2 py-1.5 text-center text-xs font-medium text-primary hover:bg-primary/10"
          >
            {t('notifications.viewAll')}
          </Link>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Une alerte de l'aperçu : elle annonce, et elle mène. */
function AlertDropdownItem({ row, onNavigate }: { row: AlertRow; onNavigate: () => void }) {
  return (
    <Link
      to={row.to}
      onClick={onNavigate}
      data-testid="bell-alert-row"
      className="flex items-start gap-2 px-3 py-2 text-sm transition-colors hover:bg-accent"
    >
      <span
        className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
          row.severity === 'critical' ? 'bg-destructive' : 'bg-amber-500'
        }`}
        aria-hidden
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium leading-tight text-foreground">{row.title}</span>
        <span className="block truncate text-xs text-muted-foreground">{row.meta}</span>
      </span>
    </Link>
  );
}

function NotificationDropdownItem({
  notification,
  onNavigate,
}: {
  notification: NotificationItem;
  onNavigate: () => void;
}) {
  const { t } = useTranslation();
  const location = useLocation();
  const markRead = useMarkRead();
  const acceptMutation = useAcceptInvitation();
  const declineMutation = useDeclineInvitation();

  const isInvitation = notification.type === 'household_invitation';
  const invitationId = (notification.payload?.invitation_id as string | undefined) ?? null;

  // Une invitation porte ses propres boutons : l'envelopper dans un lien
  // avalerait « Accepter »/« Refuser ». Partout ailleurs la ligne mène à ce
  // qu'elle annonce — comme la carte de `/app/notifications`, qui lisait déjà
  // `url` alors que la cloche l'ignorait et se contentait de marquer lu.
  const to = !isInvitation && notification.url ? notification.url : null;

  const isAccepting = acceptMutation.isPending && acceptMutation.variables?.invitationId === invitationId;
  const isDeclining = declineMutation.isPending && declineMutation.variables === invitationId;
  const isLoading = isAccepting || isDeclining;

  function handleClick() {
    if (!notification.is_read) markRead.mutate(notification.id);
  }

  function handleNavigate() {
    handleClick();
    onNavigate();
  }

  async function handleAccept() {
    if (!invitationId) return;
    const result = await acceptMutation.mutateAsync({ invitationId, switchToHousehold: false });
    if (!notification.is_read) markRead.mutate(notification.id);
    triggerBellRefresh();
    if (result.switched) window.location.reload();
  }

  async function handleDecline() {
    if (!invitationId) return;
    await declineMutation.mutateAsync(invitationId);
    if (!notification.is_read) markRead.mutate(notification.id);
    triggerBellRefresh();
  }

  const rowClass = `flex flex-col gap-1 px-3 py-2 text-sm transition-colors hover:bg-accent ${
    notification.is_read ? '' : 'bg-primary/5'
  }`;

  const content = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium leading-tight text-foreground">{notification.title}</p>
        {!notification.is_read && (
          <span
            className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full bg-primary"
            aria-label={t('notifications.unread')}
          />
        )}
      </div>
      {notification.body ? (
        <p className="line-clamp-2 text-xs text-muted-foreground">{notification.body}</p>
      ) : null}
      <p className="text-[10px] text-muted-foreground/70">{relativeShort(notification.created_at)}</p>
      {isInvitation && invitationId ? (
        <div
          className="flex flex-wrap gap-1.5 pt-1"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            disabled={isLoading}
            onClick={() => void handleDecline()}
          >
            {isDeclining ? t('common.saving') : t('invitations.decline')}
          </Button>
          <Button
            size="sm"
            className="h-7 text-xs"
            disabled={isLoading}
            onClick={() => void handleAccept()}
          >
            {isAccepting ? t('common.saving') : t('invitations.accept')}
          </Button>
        </div>
      ) : null}
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        state={pushBack(location)}
        onClick={handleNavigate}
        className={rowClass}
        data-testid="bell-notification-row"
      >
        {content}
      </Link>
    );
  }

  return (
    <div className={rowClass} onClick={handleClick} data-testid="bell-notification-row">
      {content}
    </div>
  );
}
