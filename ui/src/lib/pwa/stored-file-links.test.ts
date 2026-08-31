import { describe, expect, it } from 'vitest';

/**
 * Un fichier stocké se télécharge, il ne se *navigue* pas.
 *
 * Le symptôme : on installe l'app (iPhone, ou « Ajouter au Dock » sur Mac), on
 * ouvre un PDF depuis un document — et on est **coincé**. La fenêtre affiche le
 * PDF et il n'y a plus rien pour revenir.
 *
 * Ce n'est pas une page cassée, c'est le **mode standalone** : une PWA installée
 * n'a pas de barre de navigation. Toute navigation qui sort du SPA est donc une
 * porte à sens unique — et `/media/<fichier>.pdf` est same-origin, dans le
 * `scope` du manifeste (`/`), donc la fenêtre l'honore *sur place* au lieu
 * d'ouvrir un onglet. Le bouton disait « Télécharger » et faisait une
 * navigation : l'interface promettait, le clic démentait.
 *
 * L'attribut `download` supprime la navigation — le fichier part au
 * gestionnaire de téléchargements et l'app ne bouge pas. `PhotoLightbox` le
 * faisait déjà ; `DocumentDetailPage` ne le faisait pas.
 *
 * D'où un contrôle statique plutôt qu'une relecture, pour les deux raisons
 * habituelles de cette famille (cf. `field-font-size.test.ts`) :
 *
 * 1. **en revue, `target="_blank"` sur un fichier ressemble exactement à
 *    `download`** — même ligne, même longueur, intention opposée ;
 * 2. **le piège n'existe qu'en mode standalone**, que ni jsdom ni un navigateur
 *    piloté ne reproduisent : il n'y a pas de chrome à retirer dans un onglet.
 *    La propriété, elle, est déterministe — c'est un attribut, il se lit dans la
 *    source.
 *
 * Limite connue, même forme que les clés i18n construites : un `href` qui passe
 * par un alias (`const url = doc.file_url`) échappe au contrôle. Ce que la règle
 * couvre, c'est la forme que le dépôt écrit.
 */

/** Tout le front — pas une liste de dossiers choisis. */
const sources = import.meta.glob<string>(
  '../../{features,components,pages,design-system}/**/*.tsx',
  { eager: true, query: '?raw', import: 'default' },
);

/**
 * Les URLs de fichiers servis par `/media/` (vue `core.views_media`) : le
 * fichier lui-même et ses vignettes.
 */
const STORED_FILE_URL = /\b(?:file|medium|thumbnail)_url\b/;

const HAS_DOWNLOAD = /(?:^|\s)download(?=[\s/>=])/;
const HAS_BLANK_TARGET = /target=\{?['"]_blank/;

/**
 * Découpe les balises d'ouverture `<a …>` d'une source JSX. Les accolades sont
 * comptées : un `className={cn(…)}` ne doit pas couper la balise en deux.
 */
function anchorTags(source: string): string[] {
  const tags: string[] = [];
  const opening = /<a(?=[\s/>])/g;
  let match: RegExpExecArray | null;
  while ((match = opening.exec(source)) !== null) {
    let depth = 0;
    let i = match.index + 2;
    for (; i < source.length; i += 1) {
      const char = source[i];
      if (char === '{') depth += 1;
      else if (char === '}') depth -= 1;
      else if (char === '>' && depth === 0) break;
    }
    tags.push(source.slice(match.index, i + 1));
  }
  return tags;
}

/** Balises `<a>` dont le `href` porte l'URL d'un fichier stocké. */
function storedFileAnchors(): { file: string; tag: string }[] {
  const found: { file: string; tag: string }[] = [];
  for (const [file, source] of Object.entries(sources)) {
    for (const tag of anchorTags(source)) {
      const href = /href=\{([\s\S]*?)\}/.exec(tag);
      if (href && STORED_FILE_URL.test(href[1])) found.push({ file, tag });
    }
  }
  return found;
}

describe('un fichier stocké ne se navigue pas', () => {
  it('trouve les liens de fichiers du front (sinon le contrôle ne contrôle rien)', () => {
    expect(storedFileAnchors().length).toBeGreaterThan(0);
  });

  it('porte toujours `download`', () => {
    const offenders = storedFileAnchors()
      .filter(({ tag }) => !HAS_DOWNLOAD.test(tag))
      .map(({ file, tag }) => `${file}\n    ${tag.replace(/\s+/g, ' ')}`);

    expect(
      offenders,
      'Un lien vers /media/ sans `download` est une navigation : en PWA ' +
        'installée, elle sort du SPA et rien ne ramène en arrière.\n\n' +
        offenders.join('\n\n'),
    ).toEqual([]);
  });

  it('ne porte jamais `target="_blank"`', () => {
    const offenders = storedFileAnchors()
      .filter(({ tag }) => HAS_BLANK_TARGET.test(tag))
      .map(({ file, tag }) => `${file}\n    ${tag.replace(/\s+/g, ' ')}`);

    expect(
      offenders,
      '`target="_blank"` ne crée pas d\'onglet en mode standalone : la fenêtre ' +
        'de l\'app navigue sur place.\n\n' +
        offenders.join('\n\n'),
    ).toEqual([]);
  });

  it("ne passe jamais par window.open", () => {
    const offenders = Object.entries(sources)
      .filter(([, source]) =>
        [...source.matchAll(/window\.open\(([\s\S]{0,80}?)[,)]/g)].some((m) =>
          STORED_FILE_URL.test(m[1]),
        ),
      )
      .map(([file]) => file);

    expect(offenders, offenders.join('\n')).toEqual([]);
  });
});
