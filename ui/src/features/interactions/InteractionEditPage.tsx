import * as React from 'react';
import { Clock3, ListTodo } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from '@/lib/toast';
import PageHeader from '@/components/PageHeader';
import { Button } from '@/design-system/button';
import { Input } from '@/design-system/input';
import { Textarea } from '@/design-system/textarea';
import { VisibilityField } from '@/design-system/visibility-field';
import { fetchContacts, type Contact } from '@/lib/api/contacts';
import { fetchStructures, type Structure } from '@/lib/api/structures';
import { fetchEquipmentList, type EquipmentListItem } from '@/lib/api/equipment';
import { fetchHouseholdMembers, type HouseholdMember } from '@/lib/api/tasks';
import NewTaskDialog from '@/features/tasks/NewTaskDialog';
import { isOwnedByAllocationEditor } from '@/features/banking/ownership';
import InteractionDeleteAction from './InteractionDeleteAction';
import { useInteraction, useUpdateInteraction } from './hooks';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { useNavigateBack } from '@/lib/backNavigation';
import ExpenseFields from './ExpenseFields';
import ZonePicker from '@/features/zones/ZonePicker';

function isoToDate(value: string): string {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (v: number) => String(v).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function isoToTime(value: string): string {
  if (!value) return '12:00';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '12:00';
  const pad = (v: number) => String(v).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function InteractionEditPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  // `navigate(-1)` sert au reste de la page (annuler, enregistrer), mais après une
  // suppression il peut renvoyer sur la fiche d'un objet qui n'existe plus.
  const navigateBackAfterDelete = useNavigateBack('/app/money/expenses');

  const { data: interaction, isLoading, error } = useInteraction(id ?? '');
  // Le hook, jamais `updateInteraction` en direct : c'est lui qui périme les
  // caches de l'argent. Sans lui, corriger un fournisseur puis revenir en
  // arrière affichait la liste d'avant jusqu'à un rechargement de la page.
  const updateMutation = useUpdateInteraction();

  const [subject, setSubject] = React.useState('');
  const [occurredOn, setOccurredOn] = React.useState('');
  const [includeTime, setIncludeTime] = React.useState(false);
  const [occurredTime, setOccurredTime] = React.useState('12:00');
  const [description, setDescription] = React.useState('');
  const [tagsInput, setTagsInput] = React.useState('');
  const [isPrivate, setIsPrivate] = React.useState(false);
  const [zoneId, setZoneId] = React.useState('');
  const [contactId, setContactId] = React.useState('');
  const [structureId, setStructureId] = React.useState('');
  const [contacts, setContacts] = React.useState<Contact[]>([]);
  const [structures, setStructures] = React.useState<Structure[]>([]);
  const [equipmentId, setEquipmentId] = React.useState('');
  const [equipmentList, setEquipmentList] = React.useState<EquipmentListItem[]>([]);
  const [amount, setAmount] = React.useState('');
  const [supplier, setSupplier] = React.useState('');
  const [budgetId, setBudgetId] = React.useState('');
  const [formError, setFormError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [initialised, setInitialised] = React.useState(false);
  const [taskDialogOpen, setTaskDialogOpen] = React.useState(false);
  const [householdMembers, setHouseholdMembers] = React.useState<HouseholdMember[]>([]);
  const showSkeleton = useDelayedLoading(isLoading);

  React.useEffect(() => {
    fetchHouseholdMembers().then(setHouseholdMembers).catch(() => {});
  }, []);

  const metadata = (interaction?.metadata ?? {}) as Record<string, string | null | undefined>;

  // Pre-fill form once interaction is loaded
  React.useEffect(() => {
    if (!interaction || initialised) return;
    setSubject(interaction.subject ?? '');
    if (interaction.occurred_at) {
      setOccurredOn(isoToDate(interaction.occurred_at));
      setOccurredTime(isoToTime(interaction.occurred_at));
    }
    setDescription(interaction.content ?? '');
    setTagsInput((interaction.tags ?? []).join(', '));
    setAmount(interaction.amount ?? '');
    setSupplier(interaction.supplier ?? '');
    setBudgetId(interaction.budget?.id ?? '');
    setContactId(interaction.contacts?.[0]?.id ?? '');
    setStructureId(interaction.structures?.[0]?.id ?? '');
    setEquipmentId(interaction.equipments?.[0]?.id ?? '');
    setIsPrivate(interaction.is_private ?? false);
    setInitialised(true);
  }, [interaction, initialised]);

  React.useEffect(() => {
    fetchContacts().then(setContacts).catch(() => {});
    fetchStructures().then(setStructures).catch(() => {});
    fetchEquipmentList().then(setEquipmentList).catch(() => {});
  }, []);

  // Le type n'est plus un état du formulaire : il se choisit à la création et
  // jamais plus (il décide si un montant compte comme une dépense — voir
  // `InteractionSerializer.get_fields`). On le lit pour savoir quels champs
  // afficher, on ne l'écrit pas.
  const type = interaction?.type ?? '';
  const isExpense = type === 'expense';

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);

    if (!subject.trim()) {
      setFormError(t('interactions.error_subject_required'));
      return;
    }

    if (!occurredOn) {
      setFormError(t('interactions.error_invalid_date'));
      return;
    }

    const resolvedTime = includeTime ? occurredTime || '12:00' : occurredTime || '12:00';
    const occurredAt = new Date(`${occurredOn}T${resolvedTime}`);
    if (Number.isNaN(occurredAt.getTime())) {
      setFormError(t('interactions.error_invalid_date'));
      return;
    }

    const tags = tagsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    // Expense amount/supplier are now real columns — sent as top-level fields
    // (no metadata round-trip). kind stays as-is; unit_price and other extras
    // remain in metadata and are left untouched by omitting `metadata` here.
    const expenseFields = isExpense
      ? {
          amount: amount.trim() ? amount.trim() : null,
          supplier: supplier.trim(),
          // `null` explicite, jamais l'omission : ne pas envoyer la clé
          // laisserait l'ancienne enveloppe en place, donc « retirer le budget »
          // serait un geste sans effet.
          budget_id: budgetId || null,
        }
      : {};

    try {
      setSubmitting(true);
      await updateMutation.mutateAsync({
        id: id ?? '',
        payload: {
          subject: subject.trim(),
          content: description,
          occurred_at: occurredAt.toISOString(),
          zone_ids: zoneId ? [zoneId] : [],
          tags_input: tags,
          is_private: isPrivate,
          contact_ids: contactId ? [contactId] : [],
          structure_ids: structureId ? [structureId] : [],
          equipment_ids: equipmentId ? [equipmentId] : [],
          ...expenseFields,
        },
      });
      navigate(-1);
    } catch {
      setFormError(t('interactions.update_failed'));
    } finally {
      setSubmitting(false);
    }
  }

  if (showSkeleton) {
    return (
      <div className="mx-auto max-w-2xl space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 animate-pulse rounded-lg bg-slate-100" />
        ))}
      </div>
    );
  }
  if (isLoading) return null;

  if (error || !interaction) {
    return (
      <div className="mx-auto max-w-2xl rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {t('interactions.update_failed')}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title={t('interactions.edit_title')}>
        <Button
          type="button"
          variant="outline"
          onClick={() => setTaskDialogOpen(true)}
          disabled={submitting}
        >
          <ListTodo className="mr-2 h-4 w-4" />
          {t('interactions.createTaskFromHere')}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => navigate(-1)}
        >
          {t('common.cancel')}
        </Button>
        {/* Supprimer depuis le formulaire : on y arrive pour corriger un montant,
            on y découvre parfois que l'entrée n'a rien à faire là. Le geste vivait
            seulement sur la fiche, qu'il fallait donc rouvrir pour l'atteindre. */}
        <InteractionDeleteAction
          id={id ?? ''}
          onDeleted={navigateBackAfterDelete}
          className="h-10 px-4 text-sm"
          description={
            isExpense && isOwnedByAllocationEditor(interaction.kind)
              ? t('money.expense.deleteSplitConfirm')
              : t('interactions.delete_confirm')
          }
        />
      </PageHeader>

      <NewTaskDialog
        open={taskDialogOpen}
        onOpenChange={setTaskDialogOpen}
        onCreated={() => {
          toast({ description: t('interactions.taskCreatedFromInteraction'), variant: 'success' });
          setTaskDialogOpen(false);
        }}
        householdMembers={householdMembers}
        defaultSubject={subject}
        defaultZoneIds={zoneId ? [zoneId] : []}
        sourceInteractionId={id}
      />

      <form className="space-y-5" onSubmit={handleSubmit}>
        {/* Subject */}
        <div className="space-y-2">
          <label htmlFor="interaction-subject" className="text-sm font-medium">
            {t('interactions.subject_label')} <span className="text-rose-500">*</span>
          </label>
          <Input
            id="interaction-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder={t('interactions.subject_placeholder')}
            required
            autoFocus
          />
        </div>

        {/* Type — affiché, jamais modifiable : il dit de quoi on édite la fiche
            (et pourquoi les champs de dépense sont là), sans offrir de le
            basculer. */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <span className="block text-sm font-medium">{t('interactions.type_label')}</span>
            <p className="text-sm text-muted-foreground">
              {t(`equipment.interaction_type.${type}`)}
            </p>
          </div>
        </div>

        {isExpense ? (
          <ExpenseFields
            amount={amount}
            onAmountChange={setAmount}
            supplier={supplier}
            onSupplierChange={setSupplier}
            sourceLabel={interaction.source_label}
            sourceType={interaction.source_type}
            sourceId={interaction.source_id}
            kind={interaction.kind ?? null}
            expenseId={interaction.id}
            bankLine={interaction.bank_line}
            onDeleted={navigateBackAfterDelete}
            budgetId={budgetId}
            onBudgetChange={setBudgetId}
            unitPrice={(metadata.unit_price ?? null) as string | null}
            unit={(metadata.unit ?? null) as string | null}
          />
        ) : null}

        {/* Date / time */}
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <label htmlFor="interaction-date" className="text-sm font-medium">
              {includeTime ? t('interactions.date_time_label') : t('interactions.date_only_label')}
            </label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-pressed={includeTime}
              onClick={() => setIncludeTime((prev) => !prev)}
              className="h-auto gap-1 px-0 py-0 text-xs font-medium text-muted-foreground hover:bg-transparent hover:text-foreground"
            >
              <Clock3 className="h-3.5 w-3.5" />
              {includeTime ? t('interactions.time_label') : t('interactions.add_time_label')}
            </Button>
          </div>
          <div className={`grid gap-3 ${includeTime ? 'md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]' : ''}`}>
            <Input
              id="interaction-date"
              type="date"
              value={occurredOn}
              onChange={(e) => setOccurredOn(e.target.value)}
              required
            />
            {includeTime ? (
              <Input
                id="interaction-time"
                type="time"
                aria-label={t('interactions.time_label')}
                value={occurredTime}
                onChange={(e) => setOccurredTime(e.target.value)}
              />
            ) : null}
          </div>
        </div>

        {/* Zone */}
        <div className="space-y-2">
          <label htmlFor="interaction-zone" className="text-sm font-medium">
            {t('interactions.zone_label')}
          </label>
          <ZonePicker
            id="interaction-zone"
            value={zoneId || null}
            onChange={(id) => setZoneId(id ?? '')}
            placeholder={t('interactions.zone_placeholder')}
          />
        </div>

        {/* Contact + Structure */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label htmlFor="interaction-contact" className="text-sm font-medium">
              {t('interactions.contact_label')}
            </label>
            <select
              id="interaction-contact"
              className="text-base flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 md:text-sm"
              value={contactId}
              onChange={(e) => setContactId(e.target.value)}
            >
              <option value="">{t('interactions.contact_placeholder')}</option>
              {contacts.map((c) => {
                const name = `${c.first_name}${c.last_name ? ' ' + c.last_name : ''}`.trim() || c.id;
                return (
                  <option key={c.id} value={c.id}>
                    {name}
                  </option>
                );
              })}
            </select>
          </div>
          <div className="space-y-2">
            <label htmlFor="interaction-structure" className="text-sm font-medium">
              {t('interactions.structure_label')}
            </label>
            <select
              id="interaction-structure"
              className="text-base flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 md:text-sm"
              value={structureId}
              onChange={(e) => setStructureId(e.target.value)}
            >
              <option value="">{t('interactions.structure_placeholder')}</option>
              {structures.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Equipment */}
        <div className="space-y-2">
          <label htmlFor="interaction-equipment" className="text-sm font-medium">
            {t('interactions.equipment_label')}
          </label>
          <select
            id="interaction-equipment"
            className="text-base flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 md:text-sm"
            value={equipmentId}
            onChange={(e) => setEquipmentId(e.target.value)}
          >
            <option value="">{t('interactions.equipment_placeholder')}</option>
            {equipmentList.map((eq) => (
              <option key={eq.id} value={eq.id}>
                {eq.name}
              </option>
            ))}
          </select>
        </div>

        {/* Description */}
        <div className="space-y-2">
          <label htmlFor="interaction-description" className="text-sm font-medium">
            {t('interactions.description_label')}
          </label>
          <Textarea
            id="interaction-description"
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t('interactions.description_placeholder')}
          />
        </div>

        {/* Tags */}
        <div className="space-y-2">
          <label htmlFor="interaction-tags" className="text-sm font-medium">
            {t('interactions.tags_label')}
          </label>
          <Input
            id="interaction-tags"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder={t('interactions.tags_input_placeholder')}
          />
          <p className="text-xs text-muted-foreground">{t('interactions.tags_input_help')}</p>
        </div>

        <VisibilityField id="interaction-edit-private" value={isPrivate} onChange={setIsPrivate} />

        {/* Error */}
        {formError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {formError}
          </div>
        ) : null}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 border-t border-border/60 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate(-1)}
          >
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? t('common.saving') : t('interactions.update_label')}
          </Button>
        </div>
      </form>
    </div>
  );
}
