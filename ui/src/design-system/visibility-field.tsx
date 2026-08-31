import { Lock, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { cn } from '@/lib/utils';

interface VisibilityFieldProps {
  id: string;
  /** `true` = privé, visible du seul déposant. */
  value: boolean;
  onChange: (isPrivate: boolean) => void;
  /**
   * Phrase affichée sous le contrôle quand « privé » est choisi. Sert aux cas
   * où la confidentialité a une conséquence propre à l'écran — sur une tâche,
   * elle retire l'assignation.
   */
  privateHint?: string;
  className?: string;
  disabled?: boolean;
}

/**
 * Partagé / Privé — le contrôle unique de la confidentialité.
 *
 * Il y en avait deux dessins pour la même notion (une case à cocher sur les
 * tâches, un menu déroulant sur les briefings) et **aucun** sur les deux autres
 * modèles qui portent le drapeau : un document et une note ne pouvaient pas être
 * marqués privés depuis l'application, alors que l'API et les sept portes de
 * lecture les respectaient déjà.
 *
 * Deux boutons plutôt qu'une case à cocher, pour une raison qui n'est pas
 * cosmétique : **une case à cocher ne nomme qu'un seul état.** Décochée, elle
 * laisse deviner ce qu'elle veut dire — et sur un réglage dont l'erreur se paie
 * en « tout le foyer a vu mon cadeau », deviner ne suffit pas. Deux boutons
 * nomment les deux états et montrent lequel est actif sans l'ouvrir, là où un
 * menu déroulant demande un geste pour révéler l'alternative.
 *
 * Ce sont de vrais `<input type="radio">` dans un `<fieldset>` : le clavier, le
 * lecteur d'écran et le regroupement viennent du navigateur, on ne les
 * réimplémente pas. Et `radio` ne déclenche pas le zoom d'iOS (cf.
 * `field-font-size.test.ts`), donc la taille du libellé est libre.
 */
export function VisibilityField({
  id,
  value,
  onChange,
  privateHint,
  className,
  disabled = false,
}: VisibilityFieldProps) {
  const { t } = useTranslation();

  const options = [
    { isPrivate: false, icon: Users, label: t('privacy.shared'), hint: t('privacy.sharedHint') },
    { isPrivate: true, icon: Lock, label: t('privacy.private'), hint: t('privacy.privateHint') },
  ];

  return (
    <fieldset className={cn('min-w-0', className)} disabled={disabled}>
      <legend className="mb-1.5 text-sm font-medium text-foreground">
        {t('privacy.legend')}
      </legend>

      <div className="grid grid-cols-2 gap-2">
        {options.map((option) => {
          const Icon = option.icon;
          const checked = value === option.isPrivate;
          const optionId = `${id}-${option.isPrivate ? 'private' : 'shared'}`;

          return (
            <label
              key={optionId}
              htmlFor={optionId}
              className={cn(
                'flex cursor-pointer flex-col gap-0.5 rounded-md border px-3 py-2 transition-colors',
                'focus-within:ring-1 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background',
                checked
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border bg-background text-muted-foreground hover:border-primary/40',
                disabled && 'cursor-not-allowed opacity-50',
              )}
            >
              <span className="flex items-center gap-1.5">
                <input
                  id={optionId}
                  type="radio"
                  name={id}
                  className="sr-only"
                  checked={checked}
                  onChange={() => onChange(option.isPrivate)}
                />
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="text-sm font-medium">{option.label}</span>
              </span>
              <span className="text-xs">{option.hint}</span>
            </label>
          );
        })}
      </div>

      {value && privateHint ? (
        <p className="mt-1.5 text-xs text-muted-foreground">{privateHint}</p>
      ) : null}
    </fieldset>
  );
}
