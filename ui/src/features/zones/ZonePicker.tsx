import * as React from 'react';
import { Check, ChevronDown, ChevronRight, Search, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/design-system/input';
import { fieldBase } from '@/design-system/field-styles';
import { cn } from '@/lib/utils';
import { useTransientLayer } from '@/lib/transientLayers';
import { useZones, buildZoneRows, expandableZoneIds } from './hooks';
import type { Zone } from '@/lib/api/zones';

/**
 * Le sélecteur de zones de toute l'application — simple ou multiple.
 *
 * Il remplace quatre patterns qui coexistaient (liste de cases à cocher plate,
 * `<select>` brut, `Select` + options, et une liste de cases maison dupliquée) et
 * trois chemins d'accès aux données. Tous partageaient le même défaut : une liste
 * **à plat**, sans recherche ni hiérarchie. Passé une vingtaine de zones, choisir
 * « Chambre » parmi trois « Chambre … » de trois étages différents relevait de la
 * divination.
 *
 * Le panneau réutilise `buildZoneRows` — donc la même arborescence, le même ordre
 * du foyer et la même recherche que la page Zones. Deux façons de présenter la
 * même arborescence, c'est deux modèles mentaux pour l'utilisateur.
 */

interface CommonProps {
  /** id du déclencheur — à apparier avec le `htmlFor` du FormField. */
  id: string;
  disabled?: boolean;
  /** Texte du déclencheur quand rien n'est sélectionné. */
  placeholder?: string;
  /**
   * Zones non sélectionnables (grisées, toujours visibles pour garder la
   * hiérarchie lisible). Sert à exclure une zone et ses descendants d'un
   * sélecteur de parent : s'en faire son propre enfant créerait un cycle.
   */
  disabledIds?: ReadonlySet<string>;
  className?: string;
}

interface SingleProps extends CommonProps {
  mode?: 'single';
  value: string | null;
  onChange: (zoneId: string | null) => void;
  /** Autorise « aucune zone » et affiche l'entrée correspondante. */
  allowEmpty?: boolean;
  /** Libellé de l'entrée « aucune zone » (défaut : `zones.noZone`). */
  emptyLabel?: string;
}

interface MultipleProps extends CommonProps {
  mode: 'multiple';
  value: string[];
  onChange: (zoneIds: string[]) => void;
}

export type ZonePickerProps = SingleProps | MultipleProps;

/** Ferme au clic extérieur et à Échap — un panneau flottant qu'on ne peut pas
 *  fermer au clavier est un piège pour la navigation au clavier. */
function useDismiss(
  open: boolean,
  close: () => void,
  containerRef: React.RefObject<HTMLDivElement | null>
) {
  React.useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) close();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      // Échap ne doit fermer QUE le panneau. Le picker vit presque toujours dans
      // un SheetDialog dont Radix écoute aussi Échap sur `document` :
      // `stopPropagation` n'arrête pas un autre écouteur du même nœud, il faut
      // `stopImmediatePropagation` **et** la phase de capture pour passer avant.
      // Sans ça, refermer le panneau fermait le formulaire et perdait la saisie.
      event.stopImmediatePropagation();
      event.preventDefault();
      close();
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
      document.removeEventListener('keydown', onKeyDown, true);
    };
  }, [open, close, containerRef]);
}

/**
 * Hauteur maximale du panneau, en px : la recherche (~52) plus la liste
 * (`max-h-64` = 256). Sert à décider s'il tient sous le déclencheur.
 */
const PANEL_MAX_HEIGHT = 320;

/**
 * De quel côté déployer le panneau.
 *
 * Il se posait toujours vers le bas. Dans la card de la visionneuse photo —
 * collée au bas de la fenêtre — la recherche et la liste tombaient hors de
 * l'écran : ranger une photo depuis la visionneuse était impossible, sans qu'un
 * seul pixel ne le dise. Le champ n'a pas à savoir où il est dans la page ; c'est
 * au panneau de regarder la place qui lui reste.
 *
 * On ne bascule que si le haut fait **mieux** : coupé en haut ne vaut pas mieux
 * que coupé en bas, et un panneau qui saute d'un côté à l'autre sans y gagner est
 * plus déroutant que celui qui reste où on l'attend.
 */
function placementFor(trigger: DOMRect, viewportHeight: number): 'top' | 'bottom' {
  const below = viewportHeight - trigger.bottom;
  if (below >= PANEL_MAX_HEIGHT) return 'bottom';
  return trigger.top > below ? 'top' : 'bottom';
}

export default function ZonePicker(props: ZonePickerProps) {
  const { id, disabled, placeholder, disabledIds, className } = props;
  // Le narrowing se fait sur `props.mode` (union discriminée), pas sur une
  // variable locale : TypeScript ne propage pas la copie.
  const { t } = useTranslation();

  const { data: zones = [], isLoading } = useZones();

  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [collapsedIds, setCollapsedIds] = React.useState<string[]>([]);

  const containerRef = React.useRef<HTMLDivElement>(null);
  const searchRef = React.useRef<HTMLInputElement>(null);

  const close = React.useCallback(() => {
    setOpen(false);
    setQuery('');
  }, []);
  useDismiss(open, close, containerRef);
  // Tant que le panneau est ouvert, il revendique Échap face au dialog parent.
  useTransientLayer(open);

  // À l'ouverture, le curseur va dans la recherche : c'est le geste attendu
  // quand on cherche une zone parmi beaucoup.
  React.useEffect(() => {
    if (open) searchRef.current?.focus();
  }, [open]);

  // Le côté se décide **avant la peinture** (`useLayoutEffect`) : mesuré dans un
  // `useEffect`, le panneau apparaîtrait un instant vers le bas avant de sauter.
  const [placement, setPlacement] = React.useState<'top' | 'bottom'>('bottom');
  React.useLayoutEffect(() => {
    if (!open) return;
    const trigger = containerRef.current?.getBoundingClientRect();
    if (!trigger) return;
    setPlacement(placementFor(trigger, window.innerHeight));
  }, [open]);

  const selectedIds = React.useMemo(
    () =>
      new Set(
        props.mode === 'multiple' ? props.value : props.value ? [props.value] : []
      ),
    [props.mode, props.value]
  );

  const collapsed = React.useMemo(() => new Set(collapsedIds), [collapsedIds]);
  const { rows } = React.useMemo(
    () => buildZoneRows(zones, { collapsed, query }),
    [zones, collapsed, query]
  );

  const byId = React.useMemo(
    () => new Map<string, Zone>(zones.map((zone) => [zone.id, zone])),
    [zones]
  );

  const toggleBranch = (zoneId: string) =>
    setCollapsedIds((previous) =>
      previous.includes(zoneId)
        ? previous.filter((item) => item !== zoneId)
        : [...previous, zoneId]
    );

  const pick = (zone: Zone) => {
    if (disabledIds?.has(zone.id)) return;
    if (props.mode === 'multiple') {
      const next = selectedIds.has(zone.id)
        ? props.value.filter((item) => item !== zone.id)
        : [...props.value, zone.id];
      props.onChange(next);
      return;
    }
    props.onChange(zone.id);
    close();
  };

  const clearAll = () => {
    if (props.mode === 'multiple') props.onChange([]);
    else props.onChange(null);
  };

  // ── Contenu du déclencheur ────────────────────────────────────────────────
  /**
   * Quand rien n'est choisi, un champ qui autorise le vide affiche son libellé
   * « aucune zone » — c'est un **choix**, pas une absence de choix, et c'est ce
   * que montrait le `<option value="">` du `<select>` d'origine. Un champ requis
   * affiche au contraire une invitation.
   */
  const emptyText =
    placeholder ??
    (props.mode !== 'multiple' && props.allowEmpty ? props.emptyLabel ?? t('zones.noZone') : null) ??
    t('zones.pickerPlaceholder');

  let triggerContent: React.ReactNode;
  if (props.mode === 'multiple') {
    const chosen = props.value.map((zoneId) => byId.get(zoneId)).filter(Boolean) as Zone[];
    triggerContent =
      chosen.length === 0 ? (
        <span className="truncate text-muted-foreground">{emptyText}</span>
      ) : (
        <span className="flex min-w-0 flex-wrap items-center gap-1">
          {chosen.slice(0, 3).map((zone) => (
            <span
              key={zone.id}
              className="inline-flex max-w-[12rem] items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-xs"
            >
              <span
                aria-hidden="true"
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: zone.color || '#94a3b8' }}
              />
              <span className="truncate">{zone.name}</span>
            </span>
          ))}
          {chosen.length > 3 ? (
            <span className="text-xs text-muted-foreground">
              {t('zones.pickerMore', { count: chosen.length - 3 })}
            </span>
          ) : null}
        </span>
      );
  } else {
    const chosen = props.value ? byId.get(props.value) : undefined;
    triggerContent = chosen ? (
      <span className="flex min-w-0 items-center gap-1.5">
        <span
          aria-hidden="true"
          className="h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: chosen.color || '#94a3b8' }}
        />
        {/* Le chemin complet lève l'ambiguïté entre trois « Chambre » — c'est
            précisément ce qu'un <select> à plat ne donnait pas. */}
        <span className="truncate">{chosen.full_path ?? chosen.name}</span>
      </span>
    ) : (
      <span className="truncate text-muted-foreground">{emptyText}</span>
    );
  }

  const selectionCount = props.mode === 'multiple' ? props.value.length : props.value ? 1 : 0;
  const canCollapseAll = expandableZoneIds(zones).length > 0;

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <button
        id={id}
        type="button"
        disabled={disabled}
        onClick={() => setOpen((previous) => !previous)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={cn(fieldBase, 'flex h-10 items-center justify-between gap-2 text-left')}
      >
        <span className="flex min-w-0 flex-1 items-center">{triggerContent}</span>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-180'
          )}
          aria-hidden="true"
        />
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={t('zones.pickerLabel')}
          data-placement={placement}
          className={cn(
            'absolute z-50 w-full min-w-[16rem] overflow-hidden rounded-md border border-border bg-card shadow-lg',
            placement === 'top' ? 'bottom-full mb-1' : 'top-full mt-1',
          )}
        >
          <div className="relative border-b border-border p-2">
            <Search
              className="pointer-events-none absolute left-4 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              ref={searchRef}
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('zones.searchPlaceholder')}
              aria-label={t('zones.searchPlaceholder')}
              className="h-8 pl-8 md:text-sm"
            />
          </div>

          <div className="max-h-64 overflow-y-auto py-1">
            {isLoading && zones.length === 0 ? (
              <p className="px-3 py-2 text-sm text-muted-foreground">{t('common.loading')}</p>
            ) : zones.length === 0 ? (
              <p className="px-3 py-2 text-sm text-muted-foreground">{t('zones.no_zones')}</p>
            ) : rows.length === 0 ? (
              <p className="px-3 py-2 text-sm text-muted-foreground">
                {t('zones.searchEmpty', { query: query.trim() })}
              </p>
            ) : (
              <>
                {props.mode !== 'multiple' && props.allowEmpty ? (
                  <button
                    type="button"
                    onClick={() => {
                      props.onChange(null);
                      close();
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-muted-foreground hover:bg-muted"
                  >
                    <span className="w-4 shrink-0">
                      {props.value === null ? <Check className="h-3.5 w-3.5" /> : null}
                    </span>
                    {props.emptyLabel ?? t('zones.noZone')}
                  </button>
                ) : null}

                {rows.map(({ zone, depth, hasChildren }) => {
                  const isSelected = selectedIds.has(zone.id);
                  const isDisabled = disabledIds?.has(zone.id) ?? false;
                  return (
                    <div
                      key={zone.id}
                      className="flex items-center"
                      style={{ paddingLeft: depth * 12 }}
                    >
                      {/* Chevron séparé du choix : replier une branche ne doit
                          pas sélectionner la zone qui la porte. */}
                      <span className="flex h-7 w-5 shrink-0 items-center justify-center">
                        {hasChildren ? (
                          <button
                            type="button"
                            onClick={() => toggleBranch(zone.id)}
                            aria-label={
                              collapsed.has(zone.id)
                                ? t('zones.expandZone')
                                : t('zones.collapseZone')
                            }
                            className="flex h-4 w-4 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                          >
                            <ChevronRight
                              className={cn(
                                'h-3 w-3 transition-transform',
                                !collapsed.has(zone.id) && 'rotate-90'
                              )}
                            />
                          </button>
                        ) : null}
                      </span>

                      <button
                        type="button"
                        onClick={() => pick(zone)}
                        disabled={isDisabled}
                        aria-pressed={props.mode === 'multiple' ? isSelected : undefined}
                        className={cn(
                          'flex min-w-0 flex-1 items-center gap-2 rounded px-1.5 py-1 text-left text-sm hover:bg-muted',
                          isDisabled && 'cursor-not-allowed opacity-40 hover:bg-transparent',
                          isSelected && 'font-medium text-primary'
                        )}
                      >
                        <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                          {isSelected ? <Check className="h-3.5 w-3.5" /> : null}
                        </span>
                        <span
                          aria-hidden="true"
                          className="h-2.5 w-2.5 shrink-0 rounded-full"
                          style={{ backgroundColor: zone.color || '#94a3b8' }}
                        />
                        <span className="truncate">{zone.name}</span>
                      </button>
                    </div>
                  );
                })}
              </>
            )}
          </div>

          {canCollapseAll || selectionCount > 0 ? (
            <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-1.5 text-xs text-muted-foreground">
              <span>
                {props.mode === 'multiple'
                  ? t('zones.pickerSelected', { count: selectionCount })
                  : null}
              </span>
              {selectionCount > 0 ? (
                <button
                  type="button"
                  onClick={clearAll}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                  {t('common.clear')}
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
