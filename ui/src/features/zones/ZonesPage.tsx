import * as React from 'react';
import { ChevronsDownUp, ChevronsUpDown, MapPin, QrCode, Search, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import ListPage from '@/components/ListPage';
import { Button } from '@/design-system/button';
import { Card } from '@/design-system/card';
import { Input } from '@/design-system/input';
import { toast } from '@/lib/toast';
import { useDeleteWithUndo } from '@/lib/useDeleteWithUndo';
import { useSessionState } from '@/lib/useSessionState';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import {
  useZones, useDeleteZone, useMoveZone, useReorderZones, zoneKeys,
  buildZoneRows, expandableZoneIds, compareZones, computeSiblingOrder, parentIdOf,
} from './hooks';
import ZoneRow, { type ZoneDragState } from './ZoneRow';
import ZoneDialog from './ZoneDialog';
import type { Zone } from '@/lib/api/zones';

export default function ZonesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Zone | undefined>(undefined);
  const [query, setQuery] = React.useState('');

  // Le pliage est une préférence de lecture — il survit à un aller-retour vers
  // une page de détail. La recherche, non : on ne veut pas retrouver une liste
  // filtrée sans avoir tapé quoi que ce soit.
  const [collapsedIds, setCollapsedIds] = useSessionState<string[]>('zones.collapsed', []);

  const { data: zones = [], isLoading, error } = useZones();
  const deleteMutation = useDeleteZone();

  const { deleteWithUndo } = useDeleteWithUndo({
    label: t('zones.deleted'),
    onDelete: (id) => deleteMutation.mutateAsync(id),
  });

  const handleDelete = React.useCallback(
    (zone: Zone) => {
      if ((zone.children_count ?? 0) > 0) {
        toast({
          description: t('zones.cannotDeleteWithChildren'),
          variant: 'destructive',
        });
        return;
      }
      deleteWithUndo(zone.id, {
        onRemove: () =>
          qc.setQueryData<Zone[]>(zoneKeys.list(), (old = []) =>
            old.filter((z) => z.id !== zone.id)
          ),
        onRestore: () => qc.invalidateQueries({ queryKey: zoneKeys.all }),
      });
    },
    [deleteWithUndo, qc, t]
  );

  const handleEdit = React.useCallback((zone: Zone) => {
    setEditing(zone);
    setDialogOpen(true);
  }, []);

  const handleCreate = React.useCallback(() => {
    setEditing(undefined);
    setDialogOpen(true);
  }, []);

  const collapsed = React.useMemo(() => new Set(collapsedIds), [collapsedIds]);

  const { rows, matchCount } = React.useMemo(
    () => buildZoneRows(zones, { collapsed, query }),
    [zones, collapsed, query]
  );

  const toggleZone = React.useCallback(
    (zoneId: string) => {
      setCollapsedIds((previous) =>
        previous.includes(zoneId)
          ? previous.filter((id) => id !== zoneId)
          : [...previous, zoneId]
      );
    },
    [setCollapsedIds]
  );

  const allExpandableIds = React.useMemo(() => expandableZoneIds(zones), [zones]);
  const isFullyCollapsed = collapsedIds.length > 0;
  const toggleAll = React.useCallback(() => {
    setCollapsedIds((previous) => (previous.length > 0 ? [] : allExpandableIds));
  }, [setCollapsedIds, allExpandableIds]);

  // ── Réordonnancement ──────────────────────────────────────────────────────
  const moveMutation = useMoveZone();
  const reorderMutation = useReorderZones();
  const [drag, setDrag] = React.useState<ZoneDragState>({ draggingId: null, target: null });

  /**
   * Rang de chaque zone dans sa fratrie, et taille de la fratrie — pour savoir
   * si « Monter »/« Descendre » a un sens. Calculé sur l'arbre **complet** : en
   * butée dans les lignes filtrées ne veut pas dire en butée dans la fratrie.
   */
  const siblingBounds = React.useMemo(() => {
    const groups = new Map<string | null, string[]>();
    for (const zone of [...zones].sort(compareZones)) {
      const parent = parentIdOf(zone);
      const list = groups.get(parent) ?? [];
      list.push(zone.id);
      groups.set(parent, list);
    }
    const bounds = new Map<string, { isFirst: boolean; isLast: boolean }>();
    groups.forEach((ids) =>
      ids.forEach((id, index) =>
        bounds.set(id, { isFirst: index === 0, isLast: index === ids.length - 1 })
      )
    );
    return bounds;
  }, [zones]);

  const handleMove = React.useCallback(
    (zone: Zone, direction: 'up' | 'down') => {
      moveMutation.mutate({ id: zone.id, direction });
    },
    [moveMutation]
  );

  const handleDropRow = React.useCallback(
    (target: Zone) => {
      const edge = drag.target?.zoneId === target.id ? drag.target.edge : 'before';
      const draggingId = drag.draggingId;
      setDrag({ draggingId: null, target: null });
      if (!draggingId) return;

      const order = computeSiblingOrder(zones, draggingId, target.id, edge);
      // `null` = geste sans effet, ou dépôt sur une autre fratrie (le
      // reparentage reste au champ « Zone parente »). On informe plutôt que de
      // ne rien faire en silence.
      if (!order) {
        const dragged = zones.find((z) => z.id === draggingId);
        if (dragged && parentIdOf(dragged) !== parentIdOf(target)) {
          toast({ description: t('zones.dropSameParentOnly') });
        }
        return;
      }
      reorderMutation.mutate(order);
    },
    [drag, zones, reorderMutation, t]
  );

  // Stats de tête : ce que la liste ne peut pas dire d'un coup d'œil.
  const stats = React.useMemo(() => {
    const rootId = zones.find((z) => !(z.parentId ?? z.parent))?.id;
    const mainCount = zones.filter((z) => (z.parentId ?? z.parent) === rootId).length;
    const totalSurface = zones.reduce((sum, z) => sum + (z.surface ?? 0), 0);
    return { total: zones.length, mainCount, totalSurface };
  }, [zones]);

  const isEmpty = !isLoading && !error && zones.length === 0;
  const showSkeleton = useDelayedLoading(isLoading);
  const isSearching = query.trim().length > 0;

  return (
    <>
      <ListPage
        title={t('zones.title')}
        description={
          zones.length > 0 ? (
            <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span>{t('zones.summary.zones', { count: stats.total })}</span>
              <span aria-hidden="true">·</span>
              <span>{t('zones.summary.main', { count: stats.mainCount })}</span>
              {stats.totalSurface > 0 ? (
                <>
                  <span aria-hidden="true">·</span>
                  <span>{t('zones.summary.surface', { value: stats.totalSurface })}</span>
                </>
              ) : null}
            </span>
          ) : undefined
        }
        isEmpty={isEmpty}
        emptyState={{
          icon: MapPin,
          title: t('zones.none'),
          description: t('zones.empty_description'),
          action: { label: t('zones.new'), onClick: handleCreate },
        }}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => navigate('/app/zones/print-qr')}>
              <QrCode className="mr-2 h-4 w-4" aria-hidden />
              {t('zones.qr.openPrintSheet')}
            </Button>
            <Button onClick={handleCreate}>{t('zones.new')}</Button>
          </div>
        }
      >
        {error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            {t('zones.loadFailed')}
            <button
              type="button"
              onClick={() => qc.invalidateQueries({ queryKey: zoneKeys.all })}
              className="ml-2 underline hover:no-underline"
            >
              {t('common.retry')}
            </button>
          </div>
        ) : null}

        {showSkeleton ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : null}

        {!isLoading && !error ? (
          <div className="space-y-3">
            {/* Barre d'outils */}
            <div className="flex items-center gap-2">
              <div className="relative min-w-0 flex-1">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />
                <Input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t('zones.searchPlaceholder')}
                  aria-label={t('zones.searchPlaceholder')}
                  className="h-9 pl-9 pr-9 md:text-sm"
                />
                {isSearching ? (
                  <button
                    type="button"
                    onClick={() => setQuery('')}
                    aria-label={t('common.clear')}
                    className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>

              {allExpandableIds.length > 0 ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={toggleAll}
                  disabled={isSearching}
                  title={isSearching ? t('zones.toggleAllDisabled') : undefined}
                  className="shrink-0"
                >
                  {isFullyCollapsed ? (
                    <ChevronsUpDown className="h-4 w-4 sm:mr-1.5" />
                  ) : (
                    <ChevronsDownUp className="h-4 w-4 sm:mr-1.5" />
                  )}
                  <span className="hidden sm:inline">
                    {isFullyCollapsed ? t('zones.expandAll') : t('zones.collapseAll')}
                  </span>
                </Button>
              ) : null}
            </div>

            {/* Arborescence — un seul conteneur, des lignes séparées par un
                filet. Une Card par zone empilait autant de bordures et d'ombres
                que de zones : c'était le bruit qui rendait la page illisible. */}
            {rows.length === 0 ? (
              <Card className="px-4 py-8 text-center text-sm text-muted-foreground">
                {t('zones.searchEmpty', { query: query.trim() })}
              </Card>
            ) : (
              <Card className="divide-y divide-border/60 overflow-hidden">
                {rows.map((row) => {
                  const bounds = siblingBounds.get(row.zone.id);
                  return (
                    <ZoneRow
                      key={row.zone.id}
                      row={row}
                      collapsed={collapsed.has(row.zone.id)}
                      onToggle={toggleZone}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                      onMove={handleMove}
                      canMoveUp={!isSearching && bounds ? !bounds.isFirst : false}
                      canMoveDown={!isSearching && bounds ? !bounds.isLast : false}
                      drag={drag}
                      onDragStart={(zone) =>
                        setDrag({ draggingId: zone.id, target: null })
                      }
                      onDragEnd={() => setDrag({ draggingId: null, target: null })}
                      onDragOverRow={(zone, edge) =>
                        setDrag((previous) =>
                          previous.target?.zoneId === zone.id && previous.target.edge === edge
                            ? previous
                            : { ...previous, target: { zoneId: zone.id, edge } }
                        )
                      }
                      onDropRow={handleDropRow}
                    />
                  );
                })}
              </Card>
            )}

            {isSearching ? (
              <p className="text-xs text-muted-foreground">
                {t('zones.searchResults', { count: matchCount })}
              </p>
            ) : null}
          </div>
        ) : null}
      </ListPage>

      <ZoneDialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) setEditing(undefined);
        }}
        existing={editing}
      />
    </>
  );
}
