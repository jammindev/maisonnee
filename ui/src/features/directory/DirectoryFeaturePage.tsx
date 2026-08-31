import * as React from 'react';
import { Users, Building2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import ListPage from '@/components/ListPage';
import { FilterPill } from '@/design-system/filter-pill';
import { useDeleteWithUndo } from '@/lib/useDeleteWithUndo';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import type { Contact } from '@/lib/api/contacts';
import type { Structure } from '@/lib/api/structures';
import {
  useContacts, useDeleteContact, contactKeys,
  useStructures, useDeleteStructure, structureKeys,
} from './hooks';
import ContactCard from './ContactCard';
import ContactDialog from './ContactDialog';
import StructureCard from './StructureCard';
import StructureDialog from './StructureDialog';

type Tab = 'contacts' | 'structures';

export default function DirectoryFeaturePage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  // ── Tab state ───────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = React.useState<Tab>('contacts');

  // ── Search ──────────────────────────────────────────────────────────────────
  const [contactSearch, setContactSearch] = React.useState('');
  const [structureSearch, setStructureSearch] = React.useState('');

  // ── Dialog state ────────────────────────────────────────────────────────────
  const [contactDialogOpen, setContactDialogOpen] = React.useState(false);
  const [editingContact, setEditingContact] = React.useState<Contact | null>(null);
  const [structureDialogOpen, setStructureDialogOpen] = React.useState(false);
  const [editingStructure, setEditingStructure] = React.useState<Structure | null>(null);

  // ── Server state — contacts ─────────────────────────────────────────────────
  const contactFilters = React.useMemo(
    () => (contactSearch ? { search: contactSearch } : undefined),
    [contactSearch],
  );
  const { data: contacts = [], isLoading: contactsLoading, error: contactsError } =
    useContacts(contactFilters);
  const deleteContactMutation = useDeleteContact();

  // ── Server state — structures ───────────────────────────────────────────────
  const structureFilters = React.useMemo(
    () => (structureSearch ? { search: structureSearch } : undefined),
    [structureSearch],
  );
  const { data: structures = [], isLoading: structuresLoading, error: structuresError } =
    useStructures(structureFilters);
  const deleteStructureMutation = useDeleteStructure();

  // ── Contact count per structure ─────────────────────────────────────────────
  const { data: allContacts = [] } = useContacts();
  const contactCountByStructure = React.useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of allContacts) {
      if (c.structure?.id) {
        counts[c.structure.id] = (counts[c.structure.id] ?? 0) + 1;
      }
    }
    return counts;
  }, [allContacts]);

  // ── Saved callbacks ─────────────────────────────────────────────────────────
  const handleContactSaved = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: contactKeys.all });
  }, [qc]);

  const handleStructureSaved = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: structureKeys.all });
  }, [qc]);

  // ── Delete with undo — contacts ─────────────────────────────────────────────
  const { deleteWithUndo: deleteContactWithUndo } = useDeleteWithUndo({
    label: t('contacts.deleted'),
    onDelete: (id) => deleteContactMutation.mutateAsync(id),
  });

  const handleDeleteContact = React.useCallback(
    (contactId: string) => {
      const contact = contacts.find((c) => c.id === contactId);
      if (!contact) return;
      deleteContactWithUndo(contactId, {
        onRemove: () =>
          qc.setQueryData<Contact[]>(contactKeys.list(contactFilters), (old) =>
            old?.filter((c) => c.id !== contactId),
          ),
        onRestore: () =>
          qc.setQueryData<Contact[]>(contactKeys.list(contactFilters), (old) =>
            old ? [...old, contact] : [contact],
          ),
      });
    },
    [contacts, deleteContactWithUndo, qc, contactFilters],
  );

  // ── Delete with undo — structures ───────────────────────────────────────────
  const { deleteWithUndo: deleteStructureWithUndo } = useDeleteWithUndo({
    label: t('structures.deleted'),
    onDelete: (id) => deleteStructureMutation.mutateAsync(id),
  });

  const handleDeleteStructure = React.useCallback(
    (structureId: string) => {
      const structure = structures.find((s) => s.id === structureId);
      if (!structure) return;
      deleteStructureWithUndo(structureId, {
        onRemove: () =>
          qc.setQueryData<Structure[]>(structureKeys.list(structureFilters), (old) =>
            old?.filter((s) => s.id !== structureId),
          ),
        onRestore: () =>
          qc.setQueryData<Structure[]>(structureKeys.list(structureFilters), (old) =>
            old ? [...old, structure] : [structure],
          ),
      });
    },
    [structures, deleteStructureWithUndo, qc, structureFilters],
  );

  // ── Render helpers ──────────────────────────────────────────────────────────
  const isContacts = activeTab === 'contacts';
  const isLoading = isContacts ? contactsLoading : structuresLoading;
  const showSkeleton = useDelayedLoading(isLoading);
  const hasError = isContacts ? Boolean(contactsError) : Boolean(structuresError);
  const isEmpty = !isLoading && !hasError && (isContacts ? contacts.length === 0 : structures.length === 0);

  return (
    <>
      <ListPage
        title={t('directory.title')}
        isEmpty={isEmpty}
        emptyState={
          isContacts
            ? {
                icon: Users,
                title: t('contacts.empty'),
                description: t('contacts.empty_description'),
                action: { label: t('contacts.new'), onClick: () => setContactDialogOpen(true) },
              }
            : {
                icon: Building2,
                title: t('structures.empty'),
                description: t('structures.empty_description'),
                action: { label: t('structures.new'), onClick: () => setStructureDialogOpen(true) },
              }
        }
        actions={
          isContacts ? (
            <button
              type="button"
              onClick={() => setContactDialogOpen(true)}
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
            >
              {t('contacts.new')}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setStructureDialogOpen(true)}
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
            >
              {t('structures.new')}
            </button>
          )
        }
      >
        <div className="space-y-4">
          {/* Tab bar */}
          <div className="flex gap-2">
            {(['contacts', 'structures'] as Tab[]).map((tab) => (
              <FilterPill key={tab} active={activeTab === tab} onClick={() => setActiveTab(tab)}>
                {tab === 'contacts' ? t('directory.tabContacts') : t('directory.tabStructures')}
              </FilterPill>
            ))}
          </div>

          {/* Search */}
          {isContacts ? (
            <input
              type="search"
              value={contactSearch}
              onChange={(e) => setContactSearch(e.target.value)}
              placeholder={t('contacts.searchPlaceholder')}
              className="text-base h-9 w-full rounded-md border border-input bg-background px-3 md:text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
          ) : (
            <input
              type="search"
              value={structureSearch}
              onChange={(e) => setStructureSearch(e.target.value)}
              placeholder={t('structures.searchPlaceholder')}
              className="text-base h-9 w-full rounded-md border border-input bg-background px-3 md:text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
          )}

          {/* Error */}
          {hasError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {isContacts ? t('contacts.loadFailed') : t('structures.loadFailed')}
              <button
                type="button"
                onClick={() =>
                  qc.invalidateQueries({
                    queryKey: isContacts ? contactKeys.all : structureKeys.all,
                  })
                }
                className="ml-2 underline hover:no-underline"
              >
                {t('common.retry')}
              </button>
            </div>
          ) : null}

          {/* Skeleton */}
          {showSkeleton ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-lg bg-slate-100" />
              ))}
            </div>
          ) : null}

          {/* Contacts list */}
          {!isLoading && !hasError && isContacts ? (
            <div className="space-y-2">
              {contacts.map((contact) => (
                <ContactCard
                  key={contact.id}
                  contact={contact}
                  onEdit={setEditingContact}
                  onDelete={handleDeleteContact}
                />
              ))}
            </div>
          ) : null}

          {/* Structures list */}
          {!isLoading && !hasError && !isContacts ? (
            <div className="space-y-2">
              {structures.map((structure) => (
                <StructureCard
                  key={structure.id}
                  structure={structure}
                  contactCount={contactCountByStructure[structure.id]}
                  onEdit={setEditingStructure}
                  onDelete={handleDeleteStructure}
                />
              ))}
            </div>
          ) : null}
        </div>
      </ListPage>

      {/* Contact dialogs */}
      <ContactDialog
        open={contactDialogOpen}
        onOpenChange={setContactDialogOpen}
        onSaved={handleContactSaved}
      />
      <ContactDialog
        open={editingContact !== null}
        onOpenChange={(open) => { if (!open) setEditingContact(null); }}
        existingContact={editingContact ?? undefined}
        onSaved={handleContactSaved}
      />

      {/* Structure dialogs */}
      <StructureDialog
        open={structureDialogOpen}
        onOpenChange={setStructureDialogOpen}
        onSaved={handleStructureSaved}
      />
      <StructureDialog
        open={editingStructure !== null}
        onOpenChange={(open) => { if (!open) setEditingStructure(null); }}
        existingStructure={editingStructure ?? undefined}
        onSaved={handleStructureSaved}
      />
    </>
  );
}
