import { describe, expect, it } from 'vitest';

import { fieldBase } from './field-styles';

/**
 * Un champ de saisie ne descend jamais sous 16px sur mobile.
 *
 * Le symptôme : on ouvre un SheetDialog, un champ prend le focus, « l'écran se
 * rapproche » et on ne voit plus le formulaire. Ce n'est pas une mise en page
 * cassée — c'est **Mobile Safari qui zoome le viewport**, ce qu'il fait dès
 * qu'un contrôle de formulaire prend le focus avec une `font-size` calculée
 * sous 16px. En PWA installée, il n'y a pas de geste pour revenir en arrière :
 * le formulaire reste hors cadre jusqu'à la fermeture.
 *
 * Le design-system tenait déjà la règle (`fieldBase` : `text-base md:text-sm`,
 * donc 16px sur mobile et 14px à partir de `md`). Ce qui la cassait, ce sont
 * les **sites d'appel** : un `className="h-8 text-sm"` posé pour tasser un
 * champ, et `tailwind-merge` fait gagner le dernier de la même famille — le
 * `text-base` du composant saute, sans rien changer d'autre à l'apparence sur
 * desktop, là où on relit le diff. Quinze champs étaient dans ce cas.
 *
 * D'où un contrôle statique plutôt qu'une relecture, pour les deux raisons
 * habituelles :
 *
 * 1. **en revue, `text-sm` sur un champ ressemble exactement à `md:text-sm`** ;
 * 2. **le zoom n'existe que dans WebKit** — ni jsdom, ni Chromium, ni Firefox
 *    ne le reproduisent, donc aucun test de rendu ne l'attesterait. La
 *    propriété *est* déterministe, elle : c'est une taille de police, elle se
 *    lit dans la source.
 *
 * Le garde-fou précédent (#272) neutralisait le focus **à l'ouverture d'un
 * SheetDialog**, pour empêcher le clavier de sortir. Il ne pouvait pas couvrir
 * celui-ci : le zoom ne dépend pas de *qui* donne le focus — un composant
 * enfant qui se focus dans son propre effet (le sélecteur de zones), ou
 * simplement le doigt de l'utilisateur — mais uniquement de la taille du texte.
 */

/** Tout le front — pas une liste de dossiers choisis. */
const sources = import.meta.glob<string>(
  '../{features,components,pages,design-system}/**/*.tsx',
  { eager: true, query: '?raw', import: 'default' },
);

/**
 * Ce qui prend le focus et fait zoomer : les composants de champ du
 * design-system, et les éléments de formulaire bruts.
 */
const FIELD = /<(Input|Textarea|DecimalInput|Select|input|textarea|select)\b/g;

/**
 * Les `type` qui n'ouvrent pas de saisie clavier — iOS ne zoome pas dessus.
 * Une case à cocher a le droit d'être petite.
 */
const NO_KEYBOARD = new Set([
  'checkbox', 'radio', 'file', 'color', 'range',
  'hidden', 'submit', 'button', 'image', 'reset',
]);

/**
 * `text-sm` / `text-xs` **sans préfixe de variante**. `md:text-sm` est la forme
 * juste (petit à partir du desktop) ; `file:text-sm` ne vise pas le champ mais
 * son bouton de sélection.
 */
const SMALL_ON_MOBILE = /(?<![\w:-])text-(xs|sm)(?![\w-])/;

/**
 * La prose de ce dépôt cite volontiers `<select>` ou `<input>` pour expliquer ce
 * qu'un composant remplace — six commentaires le font. On lit le code, pas ce
 * qu'il raconte : les blocs `/* … *\/` (JSDoc et commentaires JSX) sautent.
 */
function withoutComments(source: string): string {
  // Les retours à la ligne du bloc sont conservés : sinon le numéro rapporté
  // n'est plus celui du fichier, et un garde-fou qui désigne la mauvaise ligne
  // fait chercher le défaut là où il n'est pas.
  return source.replace(/\/\*[\s\S]*?\*\//g, (block) =>
    '\n'.repeat((block.match(/\n/g) ?? []).length),
  );
}

/** La balise ouvrante d'un élément, accolades équilibrées comprises. */
function openingTag(source: string, start: number): string {
  let depth = 0;
  for (let i = source.indexOf('<', start) + 1; i < source.length; i += 1) {
    const char = source[i];
    if (char === '{') depth += 1;
    else if (char === '}') depth -= 1;
    else if (char === '>' && depth === 0) return source.slice(start, i);
  }
  return source.slice(start);
}

function typeOf(tag: string): string | null {
  const match = /\btype=(?:"([^"]+)"|'([^']+)'|\{['"]([^'"]+)['"]\})/.exec(tag);
  return match ? (match[1] ?? match[2] ?? match[3]) : null;
}

/**
 * Un champ **brut** ne passe pas par `fieldBase` : sans taille explicite il
 * hérite de son conteneur (Tailwind pose `font-size: 100%` sur les contrôles de
 * formulaire), donc 14px dès qu'il est posé dans un bloc `text-sm`. Il doit
 * déclarer son socle lui-même — ou passer par le composant du design-system.
 */
const IS_RAW = /^[a-z]/;
const HAS_BASE = /(?<![\w:-])text-base(?![\w-])/;

function fieldsUnder16px(): string[] {
  const offenders: string[] = [];

  for (const [path, raw] of Object.entries(sources)) {
    // Le design-system lui-même est voisin de ce fichier — Vite le résout en
    // `./…`. Ses champs portent `fieldBase`, c'est le premier test qui les tient.
    if (path.startsWith('./')) continue;
    if (path.endsWith('.test.tsx')) continue;       // un harnais ne s'affiche chez personne

    const source = withoutComments(raw);
    for (const match of source.matchAll(FIELD)) {
      const tag = openingTag(source, match.index);
      const type = typeOf(tag);
      if (type && NO_KEYBOARD.has(type)) continue;

      const tooSmall = SMALL_ON_MOBILE.test(tag);
      const inherits = IS_RAW.test(match[1]) && !HAS_BASE.test(tag);
      if (!tooSmall && !inherits) continue;

      const line = source.slice(0, match.index).split('\n').length;
      const why = tooSmall ? 'taille sous 16px' : 'aucune taille : hérite du conteneur';
      offenders.push(`${path.replace('../', 'ui/src/')}:${line} — <${match[1]}> ${why}`);
    }
  }

  return offenders.sort();
}

describe('Un champ de saisie fait 16px sur mobile', () => {
  it('le design-system pose la taille une seule fois, pour tous ses champs', () => {
    // `Select` n'avait pas le `text-base` que portaient `Input` et `Textarea` :
    // il héritait de la taille ambiante, donc 14px dès qu'il était posé dans un
    // conteneur `text-sm`. La taille appartient au socle commun, pas à chaque
    // composant — sinon le prochain champ ajouté l'oubliera à son tour.
    expect(fieldBase).toContain('text-base');
    expect(fieldBase).toContain('md:text-sm');
  });

  it('aucun site d\'appel ne repasse un champ sous 16px', () => {
    expect(fieldsUnder16px()).toEqual([]);
  });
});
