import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/design-system/input';
import { Textarea } from '@/design-system/textarea';
import { DecimalInput } from '@/design-system/decimal-input';
import ZonePicker from '@/features/zones/ZonePicker';
import { useZones } from '@/features/zones/hooks';
import { cn } from '@/lib/utils';
import type { AssistantQuestion } from '@/lib/api/projects';

/**
 * Le champ de réponse — choisi par le **serveur**, pas par le modèle.
 *
 * Le modèle décide *quelle* question poser ; `question.input` décide *comment* on
 * y répond. Ce n'est pas de la cosmétique : une question d'argent doit atterrir
 * dans un `DecimalInput`, sinon le montant repasse par du texte libre que
 * quelqu'un devra relire comme un nombre — et « 12,5 » tapé sur un clavier
 * français a déjà enregistré 512 € en production.
 *
 * Aucune taille de police n'est posée ici, et c'est volontaire : `tailwind-merge`
 * fait gagner le dernier de la même famille, donc un `text-sm` ajouté pour tasser
 * un champ effacerait le `text-base` du design-system et ferait zoomer iOS à
 * l'ouverture du dialogue. Les composants du design-system portent cette
 * décision, à un seul endroit.
 */

interface Props {
  question: AssistantQuestion;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  inputId: string;
}

export default function AnswerField({ question, value, onChange, disabled, inputId }: Props) {
  const { t } = useTranslation();

  if (question.input === 'amount') {
    return (
      <DecimalInput
        id={inputId}
        value={value}
        onChange={onChange}
        disabled={disabled}
        placeholder={t('projects.assistant.answer.amountPlaceholder')}
      />
    );
  }

  if (question.input === 'date') {
    return (
      <Input
        id={inputId}
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      />
    );
  }

  if (question.input === 'zones') {
    return <ZoneAnswer inputId={inputId} onChange={onChange} disabled={disabled} />;
  }

  if (question.input === 'choice' && question.choices.length > 0) {
    return (
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          {question.choices.map((choice) => (
            <button
              key={choice}
              type="button"
              disabled={disabled}
              onClick={() => onChange(choice)}
              aria-pressed={value === choice}
              className={cn(
                'rounded-full border px-3 py-1.5 text-sm transition-colors disabled:opacity-50',
                value === choice
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border text-muted-foreground hover:text-foreground',
              )}
            >
              {choice}
            </button>
          ))}
        </div>
        {/* Les propositions ne sont pas une liste fermée : un foyer a le droit de
            répondre « en pierre reconstituée » quand on lui propose trois bois. */}
        <Input
          id={inputId}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          placeholder={t('projects.assistant.answer.otherPlaceholder')}
          autoComplete="off"
        />
      </div>
    );
  }

  return (
    <Textarea
      id={inputId}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      rows={2}
      placeholder={t('projects.assistant.answer.textPlaceholder')}
    />
  );
}

/**
 * Une question de lieu se répond dans le sélecteur habituel — mais ce qui repart
 * au modèle, ce sont les **noms**.
 *
 * Le modèle raisonne en noms de pièces (c'est ce que le contexte lui donne, et ce
 * qu'il rend dans le plan) ; lui envoyer des UUID le ferait répondre à côté. Le
 * sélecteur, lui, travaille en ids — d'où la traduction ici, au seul endroit qui
 * connaît les deux.
 */
function ZoneAnswer({
  inputId,
  onChange,
  disabled,
}: {
  inputId: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const [ids, setIds] = React.useState<string[]>([]);
  const { data: zones = [] } = useZones();

  const handleChange = (next: string[]) => {
    setIds(next);
    const names = next
      .map((id) => zones.find((zone) => zone.id === id)?.name)
      .filter((name): name is string => Boolean(name));
    onChange(names.join(', '));
  };

  return (
    <ZonePicker id={inputId} mode="multiple" value={ids} onChange={handleChange} disabled={disabled} />
  );
}
