import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, X } from 'lucide-react';
import { SheetDialog } from '@/design-system/sheet-dialog';
import { Input } from '@/design-system/input';
import { Textarea } from '@/design-system/textarea';
import { Button } from '@/design-system/button';
import { VisibilityField } from '@/design-system/visibility-field';
import { FilterPill } from '@/design-system/filter-pill';
import { FormField } from '@/design-system/form-field';
import type { Briefing } from '@/lib/api/briefings';
import { useCreateBriefing, useUpdateBriefing } from './hooks';
import { WEEKDAY_KEYS, toHHMM } from './schedule';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existing?: Briefing;
}

export default function BriefingDialog({ open, onOpenChange, existing }: Props) {
  const { t } = useTranslation();
  const isEditing = Boolean(existing);
  const createMutation = useCreateBriefing();
  const updateMutation = useUpdateBriefing();

  const [title, setTitle] = React.useState('');
  const [prompt, setPrompt] = React.useState('');
  const [condition, setCondition] = React.useState('');
  const [visibility, setVisibility] = React.useState<'shared' | 'private'>('shared');
  const [sendTimes, setSendTimes] = React.useState<string[]>([]);
  const [weekdays, setWeekdays] = React.useState<number[]>([]);

  React.useEffect(() => {
    if (!open) return;
    if (existing) {
      setTitle(existing.title);
      setPrompt(existing.prompt);
      setCondition(existing.condition || '');
      setVisibility(existing.is_private ? 'private' : 'shared');
      setSendTimes(existing.send_times.map(toHHMM));
      setWeekdays([...existing.weekdays]);
    } else {
      setTitle('');
      setPrompt('');
      setCondition('');
      setVisibility('shared');
      setSendTimes([]);
      setWeekdays([]);
    }
  }, [open, existing]);

  function updateTime(index: number, value: string) {
    setSendTimes((prev) => prev.map((t, i) => (i === index ? value : t)));
  }
  function addTime() {
    setSendTimes((prev) => [...prev, '']);
  }
  function removeTime(index: number) {
    setSendTimes((prev) => prev.filter((_, i) => i !== index));
  }
  function toggleWeekday(day: number) {
    setWeekdays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]));
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !prompt.trim()) return;
    const cleanedTimes = sendTimes.map((t) => t.trim()).filter(Boolean);
    const payload = {
      title: title.trim(),
      prompt: prompt.trim(),
      condition: condition.trim(),
      is_private: visibility === 'private',
      send_times: cleanedTimes,
      weekdays: [...weekdays].sort((a, b) => a - b),
    };
    if (existing) {
      await updateMutation.mutateAsync({ id: existing.id, payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
    onOpenChange(false);
  }

  return (
    <SheetDialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? t('briefings.edit.title') : t('briefings.new.title')}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label={`${t('briefings.fields.title')} *`} htmlFor="briefing-title">
          <Input
            id="briefing-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t('briefings.fields.titlePlaceholder')}
            required
            autoComplete="off"
          />
        </FormField>

        <FormField label={`${t('briefings.fields.prompt')} *`} htmlFor="briefing-prompt">
          <Textarea
            id="briefing-prompt"
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={t('briefings.fields.promptPlaceholder')}
            required
          />
          <p className="text-xs text-muted-foreground">{t('briefings.fields.promptHint')}</p>
        </FormField>

        <FormField label={t('briefings.fields.condition')} htmlFor="briefing-condition">
          <Textarea
            id="briefing-condition"
            rows={2}
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
            placeholder={t('briefings.fields.conditionPlaceholder')}
          />
          <p className="text-xs text-muted-foreground">{t('briefings.fields.conditionHint')}</p>
        </FormField>

        <FormField label={t('briefings.schedule.times')} htmlFor="briefing-times">
          <div className="space-y-2">
            {sendTimes.length === 0 ? (
              <p className="text-xs text-muted-foreground">{t('briefings.schedule.noTimeYet')}</p>
            ) : null}
            {sendTimes.map((time, index) => (
              <div key={index} className="flex items-center gap-2">
                <Input
                  id={index === 0 ? 'briefing-times' : undefined}
                  type="time"
                  value={time}
                  onChange={(e) => updateTime(index, e.target.value)}
                  className="max-w-[10rem]"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t('briefings.schedule.removeTime')}
                  onClick={() => removeTime(index)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" className="gap-1" onClick={addTime}>
              <Plus className="h-4 w-4" />
              {t('briefings.schedule.addTime')}
            </Button>
          </div>
        </FormField>

        <FormField label={t('briefings.schedule.weekdays')} htmlFor="briefing-weekdays">
          <div className="flex flex-wrap gap-1.5" id="briefing-weekdays">
            {WEEKDAY_KEYS.map((key, day) => (
              <FilterPill
                key={key}
                active={weekdays.includes(day)}
                onClick={() => toggleWeekday(day)}
              >
                {t(`briefings.schedule.weekdaysShort.${key}`)}
              </FilterPill>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{t('briefings.schedule.everyDayHint')}</p>
        </FormField>

        <VisibilityField
          id="briefing-visibility"
          value={visibility === 'private'}
          onChange={(isPrivate) => setVisibility(isPrivate ? 'private' : 'shared')}
        />

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={isPending}>
            {t('common.save')}
          </Button>
        </div>
      </form>
    </SheetDialog>
  );
}
