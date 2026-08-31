import { Lock } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Badge } from '@/design-system/badge';
import { cn } from '@/lib/utils';

interface PrivateBadgeProps {
  /**
   * `pill` — pastille libellée, pour une carte qui a la place.
   * `icon` — cadenas seul, pour une ligne de titre déjà chargée.
   */
  variant?: 'pill' | 'icon';
  className?: string;
}

/**
 * « Privé » — la marque d'un élément que son déposant est seul à voir.
 *
 * Un seul composant, deux rendus, **un seul libellé**. Il y avait trois copies
 * pour le même état : une pastille libellée sur `BriefingCard` (via
 * `briefings.visibility.private`) et deux cadenas nus sur `TaskCard` et
 * `TaskDetailPage`. Un même état dit avec plusieurs voix finit par se
 * contredire — c'est « un compteur ne peut pas avoir deux définitions »
 * appliqué à un mot.
 *
 * Les deux rendus ne sont pas une coquetterie : une ligne de titre qui porte
 * déjà une pastille de priorité et une icône météo n'a pas la place d'une
 * quatrième pastille. Ce qui ne se négocie pas, c'est le **libellé** : la
 * variante `icon` le porte en `aria-label` et en infobulle, là où les cadenas
 * qu'elle remplace n'annonçaient rien du tout à un lecteur d'écran.
 */
export default function PrivateBadge({ variant = 'pill', className }: PrivateBadgeProps) {
  const { t } = useTranslation();
  const label = t('privacy.private');

  if (variant === 'icon') {
    return (
      <Lock
        className={cn('h-3.5 w-3.5 flex-shrink-0 text-muted-foreground/60', className)}
        aria-label={label}
        role="img"
      />
    );
  }

  return (
    <Badge variant="secondary" className={cn('gap-1', className)}>
      <Lock className="h-3 w-3" aria-hidden="true" />
      {label}
    </Badge>
  );
}
