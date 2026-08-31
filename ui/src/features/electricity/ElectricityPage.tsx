import * as React from 'react';
import {
  Zap, Plus, Pencil, Trash2, Link2, Link2Off, Plug, Lightbulb, ShieldCheck,
  TriangleAlert, Info,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/design-system/button';
import { Badge } from '@/design-system/badge';
import { Card } from '@/design-system/card';
import { FilterPill } from '@/design-system/filter-pill';
import CardActions, { type CardAction } from '@/components/CardActions';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { useDeleteWithUndo } from '@/lib/useDeleteWithUndo';
import { useSessionState } from '@/lib/useSessionState';
import type { ElectricityBoard, ProtectiveDevice, ElectricCircuit, UsagePoint, CircuitUsagePointLink } from '@/lib/api/electricity';
import {
  electricityKeys,
  useElectricityBoards,
  useProtectiveDevices,
  useCircuits,
  useUsagePoints,
  useLinks,
  useDeleteBoard,
  useDeleteDevice,
  useDeleteCircuit,
  useDeleteUsagePoint,
  useDeactivateLink,
} from './hooks';
import BoardDialog from './BoardDialog';
import { BoardPanel } from './BoardPanel';
import DeviceDialog from './DeviceDialog';
import CircuitDialog from './CircuitDialog';
import UsagePointDialog from './UsagePointDialog';
import LinkDialog from './LinkDialog';
import ConsumptionTab from './ConsumptionTab';
import { useQueryClient } from '@tanstack/react-query';

// ── Tab types ─────────────────────────────────────────────────────────────────

type Tab = 'board' | 'circuits' | 'usagePoints' | 'links' | 'consumption';

// ── Device type helpers ───────────────────────────────────────────────────────

function deviceTypeBadge(type: string, t: (key: string) => string) {
  const variants: Record<string, { label: string; className: string }> = {
    breaker: { label: t('electricity.device.typeBreaker'), className: 'bg-blue-100 text-blue-800 border-blue-200' },
    rcd: { label: t('electricity.device.typeRcd'), className: 'bg-purple-100 text-purple-800 border-purple-200' },
    combined: { label: t('electricity.device.typeCombined'), className: 'bg-indigo-100 text-indigo-800 border-indigo-200' },
    main: { label: t('electricity.device.typeMain'), className: 'bg-amber-100 text-amber-800 border-amber-200' },
  };
  const v = variants[type] ?? { label: type, className: '' };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${v.className}`}>
      {v.label}
    </span>
  );
}

function complianceBadge(value: string | null | undefined, t: (key: string) => string) {
  if (!value) return null;
  const map: Record<string, { label: string; icon: React.ReactNode }> = {
    yes: { label: t('electricity.board.complianceYes'), icon: <ShieldCheck className="h-3.5 w-3.5 text-green-600" /> },
    no: { label: t('electricity.board.complianceNo'), icon: <TriangleAlert className="h-3.5 w-3.5 text-red-500" /> },
    partial: { label: t('electricity.board.compliancePartial'), icon: <Info className="h-3.5 w-3.5 text-amber-500" /> },
  };
  const entry = map[value];
  if (!entry) return null;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      {entry.icon}
      {entry.label}
    </span>
  );
}

// ── Board info card ───────────────────────────────────────────────────────────

interface BoardInfoCardProps {
  board: ElectricityBoard;
  onEdit: () => void;
  onDelete: () => void;
  t: (key: string) => string;
}

function BoardInfoCard({ board, onEdit, onDelete, t }: BoardInfoCardProps) {
  const actions: CardAction[] = [
    { label: t('common.edit'), icon: Pencil, onClick: onEdit },
    { label: t('common.delete'), icon: Trash2, onClick: onDelete, variant: 'danger' },
  ];
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold">{board.name}</h2>
            <Badge variant="outline" className="text-xs">
              {board.supply_type === 'three_phase' ? t('electricity.board.supplyThree') : t('electricity.board.supplySingle')}
            </Badge>
            {complianceBadge(board.nf_c_15100_compliant, t)}
          </div>
          {board.location ? (
            <p className="text-sm text-muted-foreground">{board.location}</p>
          ) : null}
          {board.last_inspection_date ? (
            <p className="text-xs text-muted-foreground">
              {t('electricity.board.inspectionDate')}: {board.last_inspection_date}
            </p>
          ) : null}
          {board.main_notes ? (
            <p className="text-sm text-muted-foreground">{board.main_notes}</p>
          ) : null}
        </div>
        <CardActions actions={actions} />
      </div>
    </Card>
  );
}

// ── Device card ───────────────────────────────────────────────────────────────

interface DeviceCardProps {
  device: ProtectiveDevice;
  onEdit: () => void;
  onDelete: () => void;
  t: (key: string) => string;
}

function DeviceCard({ device, onEdit, onDelete, t }: DeviceCardProps) {
  const actions: CardAction[] = [
    { label: t('common.edit'), icon: Pencil, onClick: onEdit },
    { label: t('common.delete'), icon: Trash2, onClick: onDelete, variant: 'danger' },
  ];

  const specs: string[] = [];
  if (device.row != null && device.position != null) {
    const posStr = device.position_end != null && device.position_end !== device.position
      ? `R${device.row} P${device.position}–${device.position_end}`
      : `R${device.row} P${device.position}`;
    specs.push(posStr);
  }
  if (device.rating_amps) specs.push(`${device.rating_amps}A`);
  if (device.pole_count) specs.push(`${device.pole_count}P`);
  if (device.curve_type) specs.push(`Courbe ${device.curve_type.toUpperCase()}`);
  if (device.sensitivity_ma) specs.push(`${device.sensitivity_ma} mA`);
  if (device.type_code) specs.push(device.type_code.toUpperCase());

  return (
    <Card className="p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {device.label ? (
              <span className="font-mono text-sm font-medium">{device.label}</span>
            ) : null}
            {deviceTypeBadge(device.device_type, t)}
            {device.role ? (
              <Badge variant="outline" className="text-xs">
                {t(`electricity.device.role${device.role.charAt(0).toUpperCase() + device.role.slice(1)}`)}
              </Badge>
            ) : null}
            {device.phase ? (
              <Badge variant="secondary" className="text-xs">{device.phase}</Badge>
            ) : null}
            {device.is_spare ? (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                {t('electricity.device.isSpare')}
              </Badge>
            ) : null}
          </div>
          {specs.length > 0 ? (
            <p className="text-xs text-muted-foreground">{specs.join(' · ')}</p>
          ) : null}
          {(device.brand || device.model_ref) ? (
            <p className="text-xs text-muted-foreground">
              {[device.brand, device.model_ref].filter(Boolean).join(' ')}
            </p>
          ) : null}
          {device.notes ? (
            <p className="text-xs text-muted-foreground">{device.notes}</p>
          ) : null}
        </div>
        <CardActions actions={actions} />
      </div>
    </Card>
  );
}

// ── Circuit card ──────────────────────────────────────────────────────────────

interface CircuitCardProps {
  circuit: ElectricCircuit;
  device: ProtectiveDevice | undefined;
  linkedCount: number;
  onEdit: () => void;
  onDelete: () => void;
  t: (key: string) => string;
}

function CircuitCard({ circuit, device, linkedCount, onEdit, onDelete, t }: CircuitCardProps) {
  const actions: CardAction[] = [
    { label: t('common.edit'), icon: Pencil, onClick: onEdit },
    { label: t('common.delete'), icon: Trash2, onClick: onDelete, variant: 'danger' },
  ];
  return (
    <Card className="p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-sm font-medium">{circuit.label}</span>
            <span className="text-sm text-muted-foreground">—</span>
            <span className="text-sm">{circuit.name}</span>
            {circuit.is_active === false ? (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                {t('electricity.inactive')}
              </Badge>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {device ? (
              <span className="flex items-center gap-1">
                <Zap className="h-3 w-3" />
                {device.label ?? '—'} {device.rating_amps ? `${device.rating_amps}A` : ''}
              </span>
            ) : null}
            {linkedCount > 0 ? (
              <span className="flex items-center gap-1">
                <Link2 className="h-3 w-3" />
                {linkedCount} {t('electricity.link.active')}
              </span>
            ) : null}
          </div>
          {circuit.notes ? (
            <p className="text-xs text-muted-foreground">{circuit.notes}</p>
          ) : null}
        </div>
        <CardActions actions={actions} />
      </div>
    </Card>
  );
}

// ── Usage point card ──────────────────────────────────────────────────────────

interface UsagePointCardProps {
  usagePoint: UsagePoint;
  linkedCircuit: ElectricCircuit | undefined;
  onEdit: () => void;
  onDelete: () => void;
  t: (key: string) => string;
}

function UsagePointCard({ usagePoint, linkedCircuit, onEdit, onDelete, t }: UsagePointCardProps) {
  const actions: CardAction[] = [
    { label: t('common.edit'), icon: Pencil, onClick: onEdit },
    { label: t('common.delete'), icon: Trash2, onClick: onDelete, variant: 'danger' },
  ];
  const KindIcon = usagePoint.kind === 'light' ? Lightbulb : Plug;
  return (
    <Card className="p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <KindIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="font-mono text-sm font-medium">{usagePoint.label}</span>
            <span className="text-sm text-muted-foreground">—</span>
            <span className="text-sm">{usagePoint.name}</span>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {linkedCircuit ? (
              <span className="flex items-center gap-1">
                <Link2 className="h-3 w-3" />
                {linkedCircuit.label} — {linkedCircuit.name}
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <Link2Off className="h-3 w-3" />
                {t('electricity.link.notLinked')}
              </span>
            )}
          </div>
          {usagePoint.notes ? (
            <p className="text-xs text-muted-foreground">{usagePoint.notes}</p>
          ) : null}
        </div>
        <CardActions actions={actions} />
      </div>
    </Card>
  );
}

// ── Link card ─────────────────────────────────────────────────────────────────

interface LinkCardProps {
  link: CircuitUsagePointLink;
  circuit: ElectricCircuit | undefined;
  usagePoint: UsagePoint | undefined;
  onDeactivate: () => void;
  t: (key: string) => string;
}

function LinkCard({ link: _link, circuit, usagePoint, onDeactivate, t }: LinkCardProps) {
  return (
    <Card className="p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2 text-sm">
          <span className="font-mono font-medium text-muted-foreground">
            {circuit?.label ?? '?'}
          </span>
          <span className="text-muted-foreground">—</span>
          <span className="font-medium">{circuit?.name ?? '?'}</span>
          <Link2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="font-mono font-medium text-muted-foreground">
            {usagePoint?.label ?? '?'}
          </span>
          <span className="text-muted-foreground">—</span>
          <span className="truncate font-medium">{usagePoint?.name ?? '?'}</span>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onDeactivate}
          className="shrink-0 gap-1 text-xs"
        >
          <Link2Off className="h-3 w-3" />
          {t('electricity.link.deactivate')}
        </Button>
      </div>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ElectricityPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data: boards = [], isLoading: boardsLoading } = useElectricityBoards();
  const [selectedBoardId, setSelectedBoardId] = useSessionState<string>('electricity.boardId', '');
  const [activeTab, setActiveTab] = useSessionState<Tab>('electricity.tab', 'board');

  // Resolve selected board
  const selectedBoard = React.useMemo(() => {
    if (selectedBoardId && boards.find((b) => b.id === selectedBoardId)) {
      return boards.find((b) => b.id === selectedBoardId)!;
    }
    return boards[0] ?? null;
  }, [boards, selectedBoardId]);

  React.useEffect(() => {
    if (selectedBoard && selectedBoard.id !== selectedBoardId) {
      setSelectedBoardId(selectedBoard.id);
    }
  }, [selectedBoard, selectedBoardId, setSelectedBoardId]);

  const boardId = selectedBoard?.id;

  const { data: devices = [], isLoading: devicesLoading } = useProtectiveDevices(boardId);
  const { data: circuits = [], isLoading: circuitsLoading } = useCircuits(boardId);
  const { data: usagePoints = [], isLoading: upLoading } = useUsagePoints();
  const { data: links = [], isLoading: linksLoading } = useLinks(boardId);

  const isLoading = boardsLoading || (Boolean(boardId) && (devicesLoading || circuitsLoading || upLoading || linksLoading));
  const showSkeleton = useDelayedLoading(isLoading);

  // Dialog states
  const [boardDialogOpen, setBoardDialogOpen] = React.useState(false);
  const [editingBoard, setEditingBoard] = React.useState<ElectricityBoard | undefined>(undefined);
  const [deviceDialogOpen, setDeviceDialogOpen] = React.useState(false);
  const [editingDevice, setEditingDevice] = React.useState<ProtectiveDevice | undefined>(undefined);
  const [circuitDialogOpen, setCircuitDialogOpen] = React.useState(false);
  const [editingCircuit, setEditingCircuit] = React.useState<ElectricCircuit | undefined>(undefined);
  const [upDialogOpen, setUpDialogOpen] = React.useState(false);
  const [editingUp, setEditingUp] = React.useState<UsagePoint | undefined>(undefined);
  const [linkDialogOpen, setLinkDialogOpen] = React.useState(false);

  // Filter for usage points tab
  const [upKindFilter, setUpKindFilter] = useSessionState<'all' | 'socket' | 'light'>('electricity.upFilter', 'all');

  // Mutations
  const deleteBoardMutation = useDeleteBoard();
  const deleteDeviceMutation = useDeleteDevice();
  const deleteCircuitMutation = useDeleteCircuit();
  const deleteUsagePointMutation = useDeleteUsagePoint();
  const deactivateLink = useDeactivateLink();

  // Delete with undo
  const { deleteWithUndo: deleteBoardWithUndo } = useDeleteWithUndo({
    label: t('electricity.board.deleted'),
    onDelete: (id) => deleteBoardMutation.mutateAsync(id),
  });
  const { deleteWithUndo: deleteDeviceWithUndo } = useDeleteWithUndo({
    label: t('electricity.device.deleted'),
    onDelete: (id) => deleteDeviceMutation.mutateAsync(id),
  });
  const { deleteWithUndo: deleteCircuitWithUndo } = useDeleteWithUndo({
    label: t('electricity.circuit.deleted'),
    onDelete: (id) => deleteCircuitMutation.mutateAsync(id),
  });
  const { deleteWithUndo: deleteUsagePointWithUndo } = useDeleteWithUndo({
    label: t('electricity.usagePoint.deleted'),
    onDelete: (id) => deleteUsagePointMutation.mutateAsync(id),
  });

  // On initial load: if board exists but no devices, redirect to 'board' tab so the user creates one first.
  // We only redirect once (on first non-loading render) to avoid kicking the user back if they delete devices later.
  const hasRedirectedRef = React.useRef(false);
  React.useEffect(() => {
    if (!isLoading && boards.length > 0 && devices.length === 0 && activeTab !== 'board' && activeTab !== 'consumption' && !hasRedirectedRef.current) {
      hasRedirectedRef.current = true;
      setActiveTab('board');
    }
    if (!isLoading && devices.length > 0) {
      hasRedirectedRef.current = true;
    }
  }, [isLoading, boards.length, devices.length, activeTab, setActiveTab]);

  // Computed data
  const activeLinks = React.useMemo(() => links.filter((l) => l.is_active !== false), [links]);

  const deviceMap = React.useMemo(
    () => new Map(devices.map((d) => [d.id, d])),
    [devices],
  );

  const circuitMap = React.useMemo(
    () => new Map(circuits.map((c) => [c.id, c])),
    [circuits],
  );

  const usagePointMap = React.useMemo(
    () => new Map(usagePoints.map((u) => [u.id, u])),
    [usagePoints],
  );

  // Count active links per circuit
  const linkCountByCircuit = React.useMemo(() => {
    const map = new Map<string, number>();
    for (const link of activeLinks) {
      map.set(link.circuit, (map.get(link.circuit) ?? 0) + 1);
    }
    return map;
  }, [activeLinks]);

  // Linked circuit for each usage point (from active links)
  const linkedCircuitByUsagePoint = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const link of activeLinks) {
      map.set(link.usage_point, link.circuit);
    }
    return map;
  }, [activeLinks]);

  // Filtered usage points
  const filteredUsagePoints = React.useMemo(() => {
    if (upKindFilter === 'all') return usagePoints;
    return usagePoints.filter((u) => u.kind === upKindFilter);
  }, [usagePoints, upKindFilter]);

  function openCreateBoard() { setEditingBoard(undefined); setBoardDialogOpen(true); }
  function openEditBoard(board: ElectricityBoard) { setEditingBoard(board); setBoardDialogOpen(true); }
  function openCreateDevice() { setEditingDevice(undefined); setDeviceDialogOpen(true); }
  function openEditDevice(device: ProtectiveDevice) { setEditingDevice(device); setDeviceDialogOpen(true); }
  function openCreateCircuit() { setEditingCircuit(undefined); setCircuitDialogOpen(true); }
  function openEditCircuit(circuit: ElectricCircuit) { setEditingCircuit(circuit); setCircuitDialogOpen(true); }
  function openCreateUp() { setEditingUp(undefined); setUpDialogOpen(true); }
  function openEditUp(up: UsagePoint) { setEditingUp(up); setUpDialogOpen(true); }

  const TABS: { key: Tab; label: string }[] = [
    { key: 'board', label: t('electricity.tabs.board') },
    { key: 'circuits', label: t('electricity.tabs.circuits') },
    { key: 'usagePoints', label: t('electricity.tabs.usagePoints') },
    { key: 'links', label: t('electricity.tabs.links') },
    { key: 'consumption', label: t('electricity.tabs.consumption') },
  ];

  // Skeleton
  if (showSkeleton) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-slate-100" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-100" />
          ))}
        </div>
      </div>
    );
  }

  // No board: show empty state — no button in PageHeader (only in EmptyState)
  if (!isLoading && boards.length === 0) {
    return (
      <>
        <PageHeader title={t('electricity.title')} description={t('electricity.description')} />
        <EmptyState
          icon={Zap}
          title={t('electricity.board.empty')}
          description={t('electricity.board.emptyDescription')}
          action={{ label: t('electricity.board.new'), onClick: openCreateBoard }}
        />
        <BoardDialog
          open={boardDialogOpen}
          onOpenChange={setBoardDialogOpen}
          existing={editingBoard}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader title={t('electricity.title')} description={t('electricity.description')}>
        {/* Board selector when multiple boards */}
        {boards.length > 1 && (
          <select
            value={selectedBoardId}
            onChange={(e) => setSelectedBoardId(e.target.value)}
            className="text-base rounded-md border border-border bg-background px-3 py-2 md:text-sm"
          >
            {boards.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        )}
        <Button variant="outline" onClick={openCreateBoard} className="gap-1.5">
          <Plus className="h-4 w-4" />
          {t('electricity.board.new')}
        </Button>
      </PageHeader>

      {/* Tab navigation */}
      <div className="flex flex-wrap gap-1.5 pb-4">
        {TABS.map(({ key, label }) => (
          <FilterPill key={key} active={activeTab === key} onClick={() => setActiveTab(key)}>
            {label}
          </FilterPill>
        ))}
      </div>

      {/* ── Board tab ──────────────────────────────────────────────────────── */}
      {activeTab === 'board' && selectedBoard && (
        <div className="space-y-4">
          <BoardInfoCard
            board={selectedBoard}
            onEdit={() => openEditBoard(selectedBoard)}
            onDelete={() => {
              deleteBoardWithUndo(selectedBoard.id, {
                onRemove: () => qc.setQueryData<ElectricityBoard[]>(
                  electricityKeys.boards(),
                  (old) => old?.filter((b) => b.id !== selectedBoard.id),
                ),
                onRestore: () => qc.setQueryData<ElectricityBoard[]>(
                  electricityKeys.boards(),
                  (old) => old ? [...old, selectedBoard] : [selectedBoard],
                ),
              });
            }}
            t={t}
          />

          {/* Représentation graphique du tableau */}
          <BoardPanel
            board={selectedBoard}
            devices={devices}
            onDeviceClick={(d) => openEditDevice(d)}
          />

          {/* Devices section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-muted-foreground">
                {t('electricity.device.title')} ({devices.length})
              </h3>
              {devices.length > 0 && (
                <Button size="sm" onClick={openCreateDevice} className="gap-1">
                  <Plus className="h-3.5 w-3.5" />
                  {t('electricity.device.new')}
                </Button>
              )}
            </div>
            {devices.length === 0 ? (
              <EmptyState
                icon={Zap}
                title={t('electricity.device.empty')}
                description={t('electricity.device.emptyDescription')}
                action={{ label: t('electricity.device.new'), onClick: openCreateDevice }}
              />
            ) : (
              <div className="space-y-2">
                {devices.map((device) => (
                  <DeviceCard
                    key={device.id}
                    device={device}
                    onEdit={() => openEditDevice(device)}
                    onDelete={() => {
                      deleteDeviceWithUndo(device.id, {
                        onRemove: () => qc.setQueryData<ProtectiveDevice[]>(
                          electricityKeys.devices(boardId),
                          (old) => old?.filter((d) => d.id !== device.id),
                        ),
                        onRestore: () => qc.setQueryData<ProtectiveDevice[]>(
                          electricityKeys.devices(boardId),
                          (old) => old ? [...old, device] : [device],
                        ),
                      });
                    }}
                    t={t}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Circuits tab ──────────────────────────────────────────────────── */}
      {activeTab === 'circuits' && (
        <div className="space-y-3">
          {devices.length === 0 ? (
            <EmptyState
              icon={Zap}
              title={t('electricity.device.empty')}
              description={t('electricity.device.emptyDescription')}
              action={{ label: t('electricity.device.new'), onClick: openCreateDevice }}
            />
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {circuits.length} {t('electricity.circuit.title').toLowerCase()}
                </p>
                {circuits.length > 0 && (
                  <Button size="sm" onClick={openCreateCircuit} className="gap-1">
                    <Plus className="h-3.5 w-3.5" />
                    {t('electricity.circuit.new')}
                  </Button>
                )}
              </div>
              {circuits.length === 0 ? (
                <EmptyState
                  icon={Link2}
                  title={t('electricity.circuit.empty')}
                  description={t('electricity.circuit.emptyDescription')}
                  action={{ label: t('electricity.circuit.new'), onClick: openCreateCircuit }}
                />
              ) : (
                <div className="space-y-2">
                  {circuits.map((circuit) => (
                    <CircuitCard
                      key={circuit.id}
                      circuit={circuit}
                      device={deviceMap.get(circuit.protective_device)}
                      linkedCount={linkCountByCircuit.get(circuit.id) ?? 0}
                      onEdit={() => openEditCircuit(circuit)}
                      onDelete={() => {
                        deleteCircuitWithUndo(circuit.id, {
                          onRemove: () => qc.setQueryData<ElectricCircuit[]>(
                            electricityKeys.circuits(boardId),
                            (old) => old?.filter((c) => c.id !== circuit.id),
                          ),
                          onRestore: () => qc.setQueryData<ElectricCircuit[]>(
                            electricityKeys.circuits(boardId),
                            (old) => old ? [...old, circuit] : [circuit],
                          ),
                        });
                      }}
                      t={t}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Usage points tab ──────────────────────────────────────────────── */}
      {activeTab === 'usagePoints' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {(['all', 'socket', 'light'] as const).map((k) => (
                <FilterPill
                  key={k}
                  active={upKindFilter === k}
                  onClick={() => setUpKindFilter(k)}
                >
                  {k === 'all' ? t('electricity.usagePoint.filterAll') :
                   k === 'socket' ? t('electricity.usagePoint.filterSocket') :
                   t('electricity.usagePoint.filterLight')}
                </FilterPill>
              ))}
            </div>
            {usagePoints.length > 0 && (
              <Button size="sm" onClick={openCreateUp} className="gap-1">
                <Plus className="h-3.5 w-3.5" />
                {t('electricity.usagePoint.new')}
              </Button>
            )}
          </div>
          {usagePoints.length === 0 ? (
            <EmptyState
              icon={Plug}
              title={t('electricity.usagePoint.empty')}
              description={t('electricity.usagePoint.emptyDescription')}
              action={{ label: t('electricity.usagePoint.new'), onClick: openCreateUp }}
            />
          ) : filteredUsagePoints.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t('electricity.usagePoint.filterEmpty')}
            </p>
          ) : (
            <div className="space-y-2">
              {filteredUsagePoints.map((up) => {
                const linkedCirId = linkedCircuitByUsagePoint.get(up.id);
                const linkedCir = linkedCirId ? circuitMap.get(linkedCirId) : undefined;
                return (
                  <UsagePointCard
                    key={up.id}
                    usagePoint={up}
                    linkedCircuit={linkedCir}
                    onEdit={() => openEditUp(up)}
                    onDelete={() => {
                      deleteUsagePointWithUndo(up.id, {
                        onRemove: () => qc.setQueryData<UsagePoint[]>(
                          electricityKeys.usagePoints(),
                          (old) => old?.filter((u) => u.id !== up.id),
                        ),
                        onRestore: () => qc.setQueryData<UsagePoint[]>(
                          electricityKeys.usagePoints(),
                          (old) => old ? [...old, up] : [up],
                        ),
                      });
                    }}
                    t={t}
                  />
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Links tab ─────────────────────────────────────────────────────── */}
      {activeTab === 'links' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {activeLinks.length} {t('electricity.link.active').toLowerCase()}
            </p>
            {activeLinks.length > 0 && (
              <Button size="sm" onClick={() => setLinkDialogOpen(true)} className="gap-1" disabled={circuits.length === 0 || usagePoints.length === 0}>
                <Plus className="h-3.5 w-3.5" />
                {t('electricity.link.new')}
              </Button>
            )}
          </div>
          {activeLinks.length === 0 ? (
            <EmptyState
              icon={Link2}
              title={t('electricity.link.empty')}
              description={t('electricity.link.emptyDescription')}
              action={
                circuits.length > 0 && usagePoints.length > 0
                  ? { label: t('electricity.link.new'), onClick: () => setLinkDialogOpen(true) }
                  : undefined
              }
            />
          ) : (
            <div className="space-y-2">
              {activeLinks.map((link) => (
                <LinkCard
                  key={link.id}
                  link={link as CircuitUsagePointLink}
                  circuit={circuitMap.get(link.circuit)}
                  usagePoint={usagePointMap.get(link.usage_point)}
                  onDeactivate={() => {
                    void deactivateLink.mutateAsync(link.id);
                  }}
                  t={t}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Consumption tab ───────────────────────────────────────── */}
      {activeTab === 'consumption' && <ConsumptionTab />}

      {/* ── Dialogs ───────────────────────────────────────────────────────── */}
      <BoardDialog
        open={boardDialogOpen}
        onOpenChange={setBoardDialogOpen}
        existing={editingBoard}
      />

      {selectedBoard && (
        <>
          <DeviceDialog
            open={deviceDialogOpen}
            onOpenChange={setDeviceDialogOpen}
            boardId={selectedBoard.id}
            supplyType={selectedBoard.supply_type as 'single_phase' | 'three_phase'}
            slotsPerRow={selectedBoard.slots_per_row}
            existing={editingDevice}
          />
          <CircuitDialog
            open={circuitDialogOpen}
            onOpenChange={setCircuitDialogOpen}
            boardId={selectedBoard.id}
            devices={devices}
            existing={editingCircuit}
          />
          <LinkDialog
            open={linkDialogOpen}
            onOpenChange={setLinkDialogOpen}
            circuits={circuits}
            usagePoints={usagePoints}
          />
        </>
      )}

      <UsagePointDialog
        open={upDialogOpen}
        onOpenChange={setUpDialogOpen}
        existing={editingUp}
      />
    </>
  );
}
