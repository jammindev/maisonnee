import * as React from 'react';
import { Separator } from '@/design-system/separator';

interface PageHeaderProps {
  /** Titre — string ou node (permet une pastille/icône devant le nom sur les détails). */
  title: React.ReactNode;
  /** Utilisé pour `document.title` quand `title` n'est pas une string. */
  documentTitle?: string;
  /** Badges/statuts rendus en ligne, à la suite du titre. */
  titleSuffix?: React.ReactNode;
  /** Sous-titre — string ou node (ex: lien vers la zone). */
  description?: React.ReactNode;
  /** Lien retour rendu au-dessus du titre (pages de détail). */
  backLink?: React.ReactNode;
  /** Boutons d'action rendus à droite du header. */
  children?: React.ReactNode;
}

/**
 * Header de page commun : (lien retour) + titre + suffixe/sous-titre + actions,
 * responsive (empilé sur mobile, en ligne à partir de `sm`). Met à jour `document.title`.
 * Utilisé par toutes les pages — listes, pages simples ET pages de détail.
 */
export default function PageHeader({
  title,
  documentTitle,
  titleSuffix,
  description,
  backLink,
  children,
}: PageHeaderProps) {
  const docTitle = documentTitle ?? (typeof title === 'string' ? title : undefined);
  React.useEffect(() => {
    if (docTitle) document.title = `${docTitle} — Maisonnée`;
  }, [docTitle]);

  return (
    <div className="mb-6">
      {backLink ? <div className="mb-3">{backLink}</div> : null}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-foreground">{title}</h1>
            {titleSuffix}
          </div>
          {description ? (
            <div className="mt-1 text-sm text-muted-foreground">{description}</div>
          ) : null}
        </div>
        {children ? (
          <div className="flex flex-wrap items-center gap-2 sm:shrink-0">{children}</div>
        ) : null}
      </div>
      <Separator />
    </div>
  );
}
