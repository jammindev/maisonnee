import * as React from 'react';
import { MessageSquare } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import ListPage from '@/components/ListPage';
import Pager from '@/components/Pager';
import { FilterBar } from '@/design-system/filter-bar';
import { useDeleteWithUndo } from '@/lib/useDeleteWithUndo';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { usePager } from '@/lib/usePager';
import type { InteractionListItem } from '@/lib/api/interactions';
import { fetchContacts, type Contact } from '@/lib/api/contacts';
import { useInteractions, useDeleteInteraction, interactionKeys } from './hooks';
import InteractionCard from './InteractionCard';
import ZonePicker from '@/features/zones/ZonePicker';

/**
 * Les dépenses ne sont plus de l'« activité ».
 *
 * Elles ont leur module — onglet Dépenses, avec leurs filtres de période, leur
 * budget et leur badge de rapprochement. Ici, à cent soixante lignes par mois,
 * elles noyaient les notes, les maintenances et les réparations, c'est-à-dire
 * tout ce que cette page est censée rendre lisible.
 *
 * L'exclusion est **serveur** (`exclude_type`) : la page est paginée par huit,
 * un filtrage après coup afficherait une page vide sous un compteur qui en
 * annonce huit. Leur fiche reste accessible (`/app/interactions/:id`), c'est la
 * liste qui cesse de les mélanger.
 */
const EXCLUDED_TYPES = 'expense';

/**
 * Cinquante événements par page — le journal se **parcourt**, il ne se tronque pas.
 *
 * Cette page était la seule à laisser le serveur choisir : `default_limit = 8` sur
 * `InteractionViewSet`, repris tel quel par le défaut de `fetchInteractions`. Elle
 * lisait `items` et jetait `count` / `next` — un foyer de cent vingt événements en
 * voyait huit, et rien ne le disait. Un plafond qui ne s'annonce pas est pire qu'un
 * plafond : il se lit « je n'ai enregistré que ça ».
 *
 * Cinquante comme les trois autres registres (dépenses, détail de budget,
 * opérations) ; le serveur plafonne à 100, donc agrandir la fenêtre au lieu de
 * pager n'aurait fait que déplacer le mur — c'est l'arbitrage écrit dans
 * `usePager`.
 */
const PAGE_SIZE = 50;

const TYPE_OPTIONS = [
  'note',
  'maintenance',
  'repair',
  'installation',
  'inspection',
  'warranty',
  'issue',
  'upgrade',
  'replacement',
  'disposal',
];


export default function InteractionsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();

  const [search, setSearch] = React.useState('');
  const [type, setType] = React.useState('');
  const [zone, setZone] = React.useState('');
  const [contact, setContact] = React.useState(searchParams.get('contact') ?? '');
  const [structure, setStructure] = React.useState(searchParams.get('structure') ?? '');
  const [tagsFilter, setTagsFilter] = React.useState('');
  const [startDate, setStartDate] = React.useState('');
  const [endDate, setEndDate] = React.useState('');

  const [contacts, setContacts] = React.useState<Contact[]>([]);

  React.useEffect(() => {
    fetchContacts().then(setContacts).catch(() => {});
  }, []);

  const pager = usePager(
    PAGE_SIZE,
    `${search}|${type}|${zone}|${contact}|${structure}|${tagsFilter}|${startDate}|${endDate}`,
  );

  const filters = React.useMemo(
    () => ({
      exclude_type: EXCLUDED_TYPES,
      ...(search ? { search } : {}),
      ...(type ? { type } : {}),
      ...(zone ? { zone } : {}),
      ...(contact ? { contact } : {}),
      ...(structure ? { structure } : {}),
      ...(tagsFilter ? { tags: tagsFilter } : {}),
      ...(startDate ? { start_date: startDate } : {}),
      ...(endDate ? { end_date: endDate } : {}),
      limit: pager.limit,
      offset: pager.offset,
    }),
    [search, type, zone, contact, structure, tagsFilter, startDate, endDate, pager.limit, pager.offset],
  );

  const { data, isLoading, isFetching, error } = useInteractions(filters);
  // Mémoïsé : l'effet de repli plus bas dépend de `items`, et un `?? []` fabrique
  // un tableau neuf à chaque rendu.
  const items: InteractionListItem[] = React.useMemo(() => data?.items ?? [], [data]);

  // Une page vidée sous les doigts (suppressions depuis la liste) ramène à la
  // première. Sans ça `ListPage` passerait en état vide — et cet état **masque la
  // liste**, donc le pager avec elle : un cul-de-sac dont on ne revient pas.
  React.useEffect(() => {
    if (!isFetching && items.length === 0 && pager.offset > 0) pager.reset();
    // `pager` entier en dépendance (comme `ExpensesPanel`) : l'objet change
    // d'identité à chaque rendu, mais la garde rend l'effet inerte.
  }, [isFetching, items.length, pager]);

  const deleteInteractionMutation = useDeleteInteraction();

  const { deleteWithUndo } = useDeleteWithUndo({
    label: t('interactions.deleted'),
    onDelete: (id) => deleteInteractionMutation.mutateAsync(id),
  });

  const handleDelete = React.useCallback(
    (itemId: string) => {
      const item = items.find((i) => i.id === itemId);
      if (!item) return;
      deleteWithUndo(itemId, {
        onRemove: () =>
          qc.setQueryData(
            interactionKeys.list(filters),
            (old: { items: InteractionListItem[]; count: number; next: string | null; previous: string | null } | undefined) =>
              old ? { ...old, items: old.items.filter((i) => i.id !== itemId), count: old.count - 1 } : old,
          ),
        onRestore: () =>
          qc.setQueryData(
            interactionKeys.list(filters),
            (old: { items: InteractionListItem[]; count: number; next: string | null; previous: string | null } | undefined) =>
              old ? { ...old, items: [...old.items, item], count: old.count + 1 } : old,
          ),
      });
    },
    [items, deleteWithUndo, qc, filters],
  );

  function resetFilters() {
    setSearch('');
    setType('');
    setZone('');
    setContact('');
    setStructure('');
    setTagsFilter('');
    setStartDate('');
    setEndDate('');
  }

  const isEmpty = !isLoading && !error && items.length === 0 && pager.offset === 0;
  const showSkeleton = useDelayedLoading(isLoading);

  return (
    <ListPage
      title={t('interactions.title')}
      isEmpty={isEmpty}
      emptyState={{
        icon: MessageSquare,
        title: t('interactions.empty'),
        description: t('interactions.empty_description'),
        action: { label: t('interactions.new'), onClick: () => navigate('/app/interactions/new') },
      }}
      actions={
        <button
          type="button"
          onClick={() => navigate('/app/interactions/new')}
          className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
        >
          {t('interactions.new')}
        </button>
      }
    >
      <div className="space-y-4">
        <FilterBar
          fields={[
            {
              type: 'search',
              id: 'interactions-search',
              label: t('interactions.search_label'),
              value: search,
              onChange: setSearch,
              placeholder: t('interactions.search_placeholder'),
            },
            {
              type: 'select',
              id: 'interactions-type',
              label: t('interactions.filter_type'),
              value: type,
              onChange: setType,
              options: [
                { value: '', label: t('interactions.all_types') },
                ...TYPE_OPTIONS.map((v) => ({
                  value: v,
                  label: t(`equipment.interaction_type.${v}`),
                })),
              ],
            },
            {
              type: 'custom',
              id: 'interactions-zone',
              label: t('interactions.filter_zone'),
              value: zone,
              onChange: setZone,
              render: (field) => (
                <ZonePicker
                  id={field.id}
                  value={field.value || null}
                  onChange={(id) => field.onChange(id ?? '')}
                  allowEmpty
                  emptyLabel={t('interactions.all_zones')}
                  placeholder={t('interactions.all_zones')}
                />
              ),
            },
            {
              type: 'select',
              id: 'interactions-contact',
              label: t('interactions.filter_contact'),
              value: contact,
              onChange: setContact,
              options: [
                { value: '', label: t('interactions.all_contacts') },
                ...contacts.map((c) => ({
                  value: c.id,
                  label: `${c.first_name}${c.last_name ? ' ' + c.last_name : ''}`.trim() || c.id,
                })),
              ],
            },
            {
              type: 'date',
              id: 'interactions-start-date',
              label: t('interactions.filter_start_date'),
              value: startDate,
              onChange: setStartDate,
            },
            {
              type: 'date',
              id: 'interactions-end-date',
              label: t('interactions.filter_end_date'),
              value: endDate,
              onChange: setEndDate,
            },
            {
              type: 'search',
              id: 'interactions-tags',
              label: t('interactions.filter_tags'),
              value: tagsFilter,
              onChange: setTagsFilter,
              placeholder: t('interactions.filter_tags_placeholder'),
            },
          ]}
          onReset={resetFilters}
          hasActiveFilters={!!(search || type || zone || contact || structure || tagsFilter || startDate || endDate)}
          resetLabel={t('interactions.reset_filters')}
          applyLabel={t('interactions.apply_filters')}
        />

        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {t('interactions.error_load_failed')}
            <button
              type="button"
              onClick={() => qc.invalidateQueries({ queryKey: interactionKeys.all })}
              className="ml-2 underline hover:no-underline"
            >
              {t('common.retry')}
            </button>
          </div>
        ) : null}

        {showSkeleton ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded-lg bg-slate-100" />
            ))}
          </div>
        ) : null}

        {!isLoading && !error ? (
          <>
            <ul className="space-y-2">
              {items.map((item) => (
                <InteractionCard key={item.id} item={item} onDelete={handleDelete} />
              ))}
            </ul>
            <Pager
              offset={pager.offset}
              limit={pager.limit}
              shown={items.length}
              total={data?.count ?? items.length}
              onPrevious={pager.previous}
              onNext={pager.next}
              isFetching={isFetching}
            />
          </>
        ) : null}
      </div>
    </ListPage>
  );
}
