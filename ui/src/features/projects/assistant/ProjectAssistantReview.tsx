import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/design-system/button';
import { Input } from '@/design-system/input';
import { Textarea } from '@/design-system/textarea';
import { Select } from '@/design-system/select';
import { DecimalInput } from '@/design-system/decimal-input';
import { FormField } from '@/design-system/form-field';
import { CheckboxField } from '@/design-system/checkbox-field';
import ZonePicker from '@/features/zones/ZonePicker';
import { useBudgets } from '@/features/budget/hooks';
import { selectableBudgets } from '@/features/budget/tree';
import type { PlanBudget, ProjectType } from '@/lib/api/projects';
import { type Draft, type DraftItem, keptCount, unresolvedRooms } from './plan';

/**
 * La relecture — le moment où rien n'est encore écrit.
 *
 * C'est ce qui remplace le « créer + Annuler » de l'écriture conversationnelle,
 * et la bascule tient à la **cardinalité** : une bulle « Annuler » suffit pour un
 * objet, douze n'en sont pas un contrôle, et l'utilisateur qui veut retirer *une*
 * tâche sur six devrait tout défaire pour tout refaire.
 *
 * Tout arrive coché : l'écran propose un résultat, il ne demande pas de le
 * reconstruire. Décocher est un geste ; cocher n'en serait pas un.
 */

const TYPE_OPTIONS: ProjectType[] = [
  'renovation', 'maintenance', 'repair', 'purchase',
  'relocation', 'vacation', 'leisure', 'other',
];

interface Props {
  draft: Draft;
  onDraftChange: (draft: Draft) => void;
  onBack: () => void;
  onCreate: () => void;
  isPending: boolean;
  error: string | null;
}

export default function ProjectAssistantReview({
  draft,
  onDraftChange,
  onBack,
  onCreate,
  isPending,
  error,
}: Props) {
  const { t } = useTranslation();
  const kept = keptCount(draft);
  const missingRooms = unresolvedRooms(draft);

  const patchProject = (patch: Partial<Draft['project']>) =>
    onDraftChange({ ...draft, project: { ...draft.project, ...patch } });

  const patchItem = (kind: 'tasks' | 'notes', index: number, patch: Partial<DraftItem>) =>
    onDraftChange({
      ...draft,
      [kind]: draft[kind].map((item, position) =>
        position === index ? { ...item, ...patch } : item,
      ),
    });

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onCreate();
      }}
      className="space-y-4"
    >
      <p className="text-sm text-muted-foreground">{t('projects.assistant.reviewIntro')}</p>

      {/* Ce que le serveur n'a pas su rattacher se **dit**, une fois. Absorber en
          silence une pièce que ce foyer n'a pas, c'est exactement le défaut que la
          résolution au tour d'entretien existe pour supprimer. */}
      {missingRooms.length > 0 ? (
        <p
          className="flex items-start gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive"
          role="status"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {t('projects.assistant.unresolvedRooms', { rooms: missingRooms.join(', ') })}
        </p>
      ) : null}

      {error ? (
        <p className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <FormField label={`${t('projects.form.fields.title')} *`} htmlFor="review-title">
        <Input
          id="review-title"
          value={draft.project.title}
          onChange={(event) => patchProject({ title: event.target.value })}
          required
          autoComplete="off"
        />
      </FormField>

      <FormField label={t('projects.form.fields.description')} htmlFor="review-description">
        <Textarea
          id="review-description"
          value={draft.project.description}
          onChange={(event) => patchProject({ description: event.target.value })}
          rows={3}
        />
      </FormField>

      <div className="grid grid-cols-2 gap-3">
        <FormField label={t('projects.form.fields.type')} htmlFor="review-type">
          <Select
            id="review-type"
            value={draft.project.type ?? ''}
            onChange={(event) =>
              patchProject({ type: (event.target.value || null) as ProjectType | null })
            }
            placeholder={t('projects.assistant.chooseType')}
            options={TYPE_OPTIONS.map((option) => ({
              value: option,
              label: t(`projects.type.${option}`),
            }))}
          />
        </FormField>
        <FormField label={t('projects.form.fields.planned_budget')} htmlFor="review-budget">
          <DecimalInput
            id="review-budget"
            value={draft.project.planned_budget ?? ''}
            onChange={(value) => patchProject({ planned_budget: value })}
          />
        </FormField>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <FormField label={t('projects.form.fields.start_date')} htmlFor="review-start">
          <Input
            id="review-start"
            type="date"
            value={draft.project.start_date ?? ''}
            onChange={(event) => patchProject({ start_date: event.target.value })}
          />
        </FormField>
        <FormField label={t('projects.form.fields.due_date')} htmlFor="review-due">
          <Input
            id="review-due"
            type="date"
            value={draft.project.due_date ?? ''}
            onChange={(event) => patchProject({ due_date: event.target.value })}
          />
        </FormField>
      </div>

      <BudgetRow
        value={draft.project.budget}
        onChange={(budget) => patchProject({ budget })}
      />

      <FormField label={t('projects.form.fields.zones')} htmlFor="review-zones">
        <ZonePicker
          id="review-zones"
          mode="multiple"
          value={draft.project.zone_ids}
          onChange={(zoneIds) => patchProject({ zone_ids: zoneIds })}
        />
      </FormField>

      <ItemList
        kind="tasks"
        heading={t('projects.assistant.tasksHeading', { count: kept.tasks })}
        empty={t('projects.assistant.noTasks')}
        items={draft.tasks}
        onPatch={patchItem}
      />
      <ItemList
        kind="notes"
        heading={t('projects.assistant.notesHeading', { count: kept.notes })}
        empty={t('projects.assistant.noNotes')}
        items={draft.notes}
        onPatch={patchItem}
      />

      <div className="flex flex-wrap justify-end gap-2 pt-2">
        {/* « Retour » et « Annuler » ne se désactivent jamais pendant l'écriture :
            si la mutation traîne, l'utilisateur doit toujours pouvoir sortir. */}
        <Button type="button" variant="outline" onClick={onBack}>
          {t('projects.assistant.back')}
        </Button>
        {/* Le submit, lui, se désactive — c'est le seul garde-fou contre une
            double création, qui n'est pas idempotente. */}
        <Button type="submit" disabled={isPending}>
          {isPending ? t('common.saving') : t('projects.assistant.create')}
        </Button>
      </div>
    </form>
  );
}

/**
 * L'enveloppe du chantier — proposée, jamais imposée.
 *
 * Trois choix dans un seul contrôle : une enveloppe existante, la nouvelle que
 * l'assistant a proposée, ou aucune. « Aucune » est un choix légitime et pas un
 * oubli : le détecteur `expense_without_budget` posera la question au premier
 * euro, ce qui est le bon moment.
 *
 * Le nom proposé pour une enveloppe neuve est mémorisé à l'initialisation : sans
 * ça, passer sur « aucune » puis revenir perdrait la proposition, et il faudrait
 * relancer l'entretien pour la retrouver.
 */
const NEW_BUDGET = '__new__';

function BudgetRow({
  value,
  onChange,
}: {
  value: PlanBudget | null;
  onChange: (budget: PlanBudget | null) => void;
}) {
  const { t } = useTranslation();
  const { data: budgets } = useBudgets();
  const options = React.useMemo(() => selectableBudgets(budgets), [budgets]);
  const [proposedName] = React.useState(() =>
    value?.mode === 'new' ? value.name : '',
  );

  const selected =
    value === null ? '' : value.mode === 'new' ? NEW_BUDGET : value.id;

  const handleChange = (next: string) => {
    if (next === '') {
      onChange(null);
      return;
    }
    if (next === NEW_BUDGET) {
      onChange({ mode: 'new', name: proposedName });
      return;
    }
    const label = options.find((option) => option.value === next)?.label ?? '';
    onChange({ mode: 'existing', id: next, name: label });
  };

  return (
    <FormField label={t('projects.assistant.budgetLabel')} htmlFor="review-envelope">
      <Select
        id="review-envelope"
        value={selected}
        onChange={(event) => handleChange(event.target.value)}
        options={[
          { value: '', label: t('projects.assistant.budgetNone') },
          ...(proposedName
            ? [{ value: NEW_BUDGET, label: t('projects.assistant.budgetNew', { name: proposedName }) }]
            : []),
          ...options,
        ]}
      />
      <p className="mt-1 text-xs text-muted-foreground">
        {t('projects.assistant.budgetHint')}
      </p>
    </FormField>
  );
}

function ItemList({
  kind,
  heading,
  empty,
  items,
  onPatch,
}: {
  kind: 'tasks' | 'notes';
  heading: string;
  empty: string;
  items: DraftItem[];
  onPatch: (kind: 'tasks' | 'notes', index: number, patch: Partial<DraftItem>) => void;
}) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium text-foreground">{heading}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, index) => (
            <li key={`${kind}-${index}`} className="flex items-start gap-2">
              <CheckboxField
                id={`${kind}-keep-${index}`}
                label=""
                checked={item.keep}
                onChange={(keep) => onPatch(kind, index, { keep })}
                className="mt-2"
              />
              <div className="min-w-0 flex-1 space-y-1">
                <Input
                  aria-label={item.subject}
                  value={item.subject}
                  onChange={(event) => onPatch(kind, index, { subject: event.target.value })}
                  disabled={!item.keep}
                  autoComplete="off"
                />
                {item.content ? (
                  <p className="px-1 text-xs text-muted-foreground">{item.content}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
