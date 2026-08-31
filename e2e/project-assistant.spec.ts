import path from 'path';
import { fileURLToPath } from 'url';
import { test, expect, type Page } from '@playwright/test';

/**
 * La création de projet par entretien — parcours 32, lots 3 à 5
 * (issues #655, #656, #657).
 *
 * **L'entretien est stubé, la création ne l'est pas.** C'est le partage qui rend
 * ce fichier utile : la question « le fournisseur répond-il ? » n'a rien à faire
 * dans un test (elle serait verte chez l'auteur, rouge en CI, et ne dirait rien
 * de l'application), alors que la question « le plan relu arrive-t-il vraiment en
 * base, et seulement ce qui était coché ? » ne se prouve qu'en traversant le vrai
 * backend. Le chemin d'écriture est celui qui porte le risque, donc c'est celui
 * qu'on ne simule pas.
 *
 * Ce que seul un vrai navigateur atteste ici :
 *
 * - **ce que l'écran promet** — sans clé, le bouton est *absent*, pas grisé. Ce
 *   défaut ne se voit dans aucune réponse HTTP ;
 * - **le champ vide d'une question d'argent** — la fourchette de prix est à côté
 *   du champ, jamais dedans. C'est une propriété du rendu, pas du payload ;
 * - **la case décochée** — que le corps envoyé perde bien la ligne retirée, de
 *   bout en bout ;
 * - **« 12,5 » qui part en `12.5`** — le bug que `DecimalInput` ferme n'existe que
 *   dans un vrai moteur, jamais en jsdom ;
 * - **le montant cité qui ne se recopie pas tout seul** — un champ vide contre un
 *   champ pré-rempli est une propriété de l'écran, et la citation est la seule
 *   exception à « le modèle ne remplit jamais un montant ».
 *
 * Couvre `PROJ-01`, `PROJ-04`, `PROJ-05`, `PROJ-06`, `PROJ-07`, `PROJ-08`,
 * `PROJ-11`, `PROJ-12`, `PROJ-13` et `PROJ-14`.
 */

const STEP_URL = '**/api/projects/projects/assistant-step/';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** La pièce jointe de l'entretien. On réutilise la photo des specs documents
 *  plutôt que d'ajouter un PDF au dépôt (aucun binaire commité) : ce qui est
 *  testé ici est la **liaison** au chantier, pas l'extraction de texte — le devis
 *  s'obtient en nommant le document à l'envoi. */
const FIXTURE_QUOTE = path.resolve(__dirname, 'fixtures/test-photo.jpg');

/** Le nom donné au document joint. Il est aussi la `source` de la citation : une
 *  suggestion n'est gardée par le serveur que si elle nomme une pièce
 *  **réellement jointe**. */
const QUOTE_NAME = 'Devis terrasse assistant';

async function token(page: Page): Promise<string> {
  return page.evaluate(() => localStorage.getItem('access_token') ?? '');
}

async function auth(page: Page): Promise<{ Authorization: string }> {
  return { Authorization: `Bearer ${await token(page)}` };
}

function unwrap<T>(body: unknown): T[] {
  return (Array.isArray(body) ? body : ((body as { results?: unknown[] }).results ?? [])) as T[];
}

/** La première zone du foyer — le plan stubé doit porter des ids **réels**, la
 *  création n'étant pas simulée. */
async function firstZoneId(page: Page): Promise<string> {
  const response = await page.request.get('/api/zones/', { headers: await auth(page) });
  const zones = unwrap<{ id: string }>(await response.json());
  return zones[0].id;
}

async function projectsNamed(page: Page, title: string) {
  const response = await page.request.get('/api/projects/projects/', {
    headers: await auth(page),
    params: { search: title },
  });
  return unwrap<{
    id: string;
    title: string;
    planned_budget: string;
    default_budget: string | null;
  }>(await response.json());
}

/** Supprime l'enveloppe créée par l'entretien — la base n'est pas réinitialisée
 *  entre les fichiers, et un nom d'enveloppe est unique par foyer. */
async function removeEnvelope(page: Page, name: string): Promise<void> {
  const headers = await auth(page);
  const response = await page.request.get('/api/budget/budgets/', { headers });
  for (const budget of unwrap<{ id: string; name: string }>(await response.json())) {
    if (budget.name === name) {
      await page.request.delete(`/api/budget/budgets/${budget.id}/`, { headers });
    }
  }
}

/** Supprime le document joint pendant l'entretien. Il **survit** volontairement à
 *  la suppression du chantier — un entretien ne possède pas le fichier qu'on y
 *  joint — donc c'est au test de le retirer, comme pour l'enveloppe. */
async function removeDocuments(page: Page, name: string): Promise<void> {
  const headers = await auth(page);
  const response = await page.request.get('/api/documents/documents/', {
    headers,
    params: { search: name },
  });
  for (const document of unwrap<{ id: number; name: string }>(await response.json())) {
    if (document.name === name) {
      await page.request.delete(`/api/documents/documents/${document.id}/`, { headers });
    }
  }
}

/** Repart d'un foyer sans ce chantier : les specs partagent une base qui n'est
 *  pas réinitialisée entre les fichiers. */
async function removeProjects(page: Page, title: string): Promise<void> {
  const headers = await auth(page);
  for (const project of await projectsNamed(page, title)) {
    await page.request.delete(`/api/projects/projects/${project.id}/`, { headers });
  }
}

/**
 * Fait dire au serveur que la capacité est là — ou qu'elle manque.
 *
 * On réécrit la **réponse réelle** plutôt que d'en inventer une : le reste de
 * l'application lit la même liste (l'assistant, le push, l'e-mail), et une
 * réponse fabriquée de toutes pièces éteindrait des écrans sans rapport.
 */
async function setAssistantCapability(page: Page, available: boolean): Promise<void> {
  await page.route('**/api/capabilities/', async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as { capabilities: { key: string; available: boolean }[] };
    body.capabilities = body.capabilities.map((row) =>
      row.key === 'project_assistant' ? { ...row, available } : row,
    );
    await route.fulfill({ response, json: body });
  });
}

const TITLE = 'Terrasse écrite par l’assistant';

/** Ce que l'écran a **réellement envoyé**, tour par tour. Le stub le collecte au
 *  lieu de le jeter : c'est la seule façon d'attester qu'une frappe « 12,5 »
 *  arrive en `12.5` côté serveur, et que les pièces jointes voyagent avec chaque
 *  tour et pas seulement à la création. */
interface Interview {
  sent: {
    history: { question: string; field: string; answer: string }[];
    force_ready: boolean;
    document_ids: number[];
  }[];
}

/**
 * Un entretien scripté : une question de matière, une d'argent, puis le plan.
 *
 * `suggestion` fait citer un montant par la question d'argent. Le contrôle qui
 * exige une pièce réellement jointe est **serveur** (`_parse_suggestion`) et il a
 * ses tests à lui ; ici on stube la citation pour éprouver ce que seul un
 * navigateur dit : qu'elle ne remplit rien toute seule.
 */
async function stubInterview(
  page: Page,
  zoneId: string,
  options: { suggestion?: { amount: string; source: string } } = {},
): Promise<Interview> {
  const interview: Interview = { sent: [] };

  await page.route(STEP_URL, async (route) => {
    const sent = route.request().postDataJSON() as Interview['sent'][number];
    interview.sent.push(sent);
    const asked = sent.history.length;

    if (!sent.force_ready && asked === 0) {
      await route.fulfill({
        json: {
          state: 'asking',
          asked: 0,
          remaining: 6,
          question: {
            text: 'Bois, composite ou carrelage ?',
            field: 'material',
            input: 'choice',
            hint: '',
            choices: ['bois', 'composite'],
          },
        },
      });
      return;
    }

    if (!sent.force_ready && asked === 1) {
      await route.fulfill({
        json: {
          state: 'asking',
          asked: 1,
          remaining: 5,
          question: {
            text: 'As-tu un budget en tête ?',
            field: 'budget',
            input: 'amount',
            hint: 'Une terrasse bois de 20 m² se situe souvent entre 2 500 et 4 500 €.',
            choices: [],
            suggestion: options.suggestion ?? null,
          },
        },
      });
      return;
    }

    await route.fulfill({
      json: {
        state: 'ready',
        asked,
        remaining: 0,
        plan: {
          project: {
            title: TITLE,
            description: 'Une terrasse de 20 m² côté jardin.',
            type: 'renovation',
            priority: 2,
            planned_budget: '3200.00',
            start_date: null,
            due_date: null,
            tags: [],
            zone_ids: [zoneId],
            unresolved_zone_names: [],
            budget: { mode: 'new', name: 'Terrasse assistant' },
          },
          tasks: [
            {
              subject: 'Choisir l’essence de bois',
              content: 'Pin traité ou ipé.',
              priority: 3,
              due_date: null,
              zone_ids: [zoneId],
              unresolved_zone_names: [],
            },
            {
              subject: 'Louer une bétonnière',
              content: '',
              priority: null,
              due_date: null,
              zone_ids: [zoneId],
              unresolved_zone_names: [],
            },
          ],
          notes: [
            {
              subject: 'Règles d’urbanisme',
              content: 'Déclaration préalable ?',
              zone_ids: [zoneId],
              unresolved_zone_names: [],
            },
          ],
        },
      },
    });
  });

  return interview;
}

test.describe('Création de projet par entretien', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app/projects');
    await removeProjects(page, TITLE);
  });

  /**
   * `unrouteAll` d'abord : sans lui, une requête encore en vol au moment où la
   * page se ferme fait échouer le *callback de route*, donc le test — un rouge
   * qui ne dit rien de l'application. Le ménage passe par `page.request`, qui ne
   * traverse pas les routes.
   */
  test.afterEach(async ({ page }) => {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await removeProjects(page, TITLE);
    await removeEnvelope(page, 'Terrasse assistant');
    await removeDocuments(page, QUOTE_NAME);
  });

  test('PROJ-01/05/06/07/11/12 — raconter, relire, corriger, décocher, créer', async ({ page }) => {
    await setAssistantCapability(page, true);
    const zoneId = await firstZoneId(page);
    await stubInterview(page, zoneId);

    await page.goto('/app/projects');
    await page.getByRole('button', { name: 'Créer avec l’assistant' }).click();

    const dialog = page.getByRole('dialog').first();
    await dialog.getByLabel('Qu’est-ce que tu veux faire ?').fill('Je veux refaire la terrasse');
    await dialog.getByRole('button', { name: 'Commencer' }).click();

    // Tour 1 — une question à choix, répondue par une pastille.
    await expect(dialog.getByText('Bois, composite ou carrelage ?')).toBeVisible();
    await dialog.getByRole('button', { name: 'bois', exact: true }).click();
    await dialog.getByRole('button', { name: 'Répondre' }).click();

    // Tour 2 — PROJ-05 : la fourchette est **à côté** du champ, et le champ est
    // vide. Un montant pré-rempli par le modèle est indistinguable d'un montant
    // décidé par le foyer, et il sert ensuite de référence pendant des mois.
    await expect(dialog.getByText(/entre 2 500 et 4 500/)).toBeVisible();
    const amount = dialog.locator('#assistant-answer-1');
    await expect(amount).toHaveValue('');
    await amount.fill('3200');

    // La sortie est là depuis le premier tour — ce n'est pas un raccourci pour
    // les pressés, c'est ce qui empêche l'entretien de retenir quelqu'un.
    await dialog.getByRole('button', { name: 'J’ai assez dit, génère' }).click();

    // PROJ-06 — la relecture, où rien n'existe encore.
    await expect(dialog.getByText('Relire avant de créer')).toBeVisible();
    await expect(dialog.getByLabel('Titre *')).toHaveValue(TITLE);
    expect(await projectsNamed(page, TITLE)).toHaveLength(0);

    // On retire la tâche qui ne sert à rien, on corrige l'autre — PROJ-07 : le
    // titre se corrige **avant** la création, pas en rouvrant la tâche ensuite.
    await dialog.locator('#tasks-keep-1').uncheck();
    await dialog.getByRole('textbox', { name: 'Choisir l’essence de bois' }).fill('Choisir le bois');

    // PROJ-12 — l'enveloppe proposée est **choisie**, pas imposée : elle apparaît
    // dans un sélecteur, avec « aucune » disponible juste à côté.
    await expect(dialog.locator('#review-envelope')).toHaveValue('__new__');

    await dialog.getByRole('button', { name: 'Créer le projet' }).click();

    // On mène au chantier : « c'est fait » sans pouvoir aller voir est
    // invérifiable, et la page qu'on ouvre n'est justement pas vide.
    await expect(page).toHaveURL(/\/app\/projects\/[0-9a-f-]{36}$/);

    // PROJ-11 — ce qui est en base est ce qui était coché, et rien d'autre.
    const [created] = await projectsNamed(page, TITLE);
    expect(created).toBeTruthy();
    const tasks = await page.request.get('/api/tasks/tasks/', {
      headers: await auth(page),
      params: { project: created.id },
    });
    const subjects = unwrap<{ subject: string }>(await tasks.json()).map((task) => task.subject);
    expect(subjects).toContain('Choisir le bois');
    expect(subjects).not.toContain('Louer une bétonnière');

    // PROJ-12 — et l'enveloppe existe, sans plafond : elle classe les dépenses du
    // chantier, elle ne les borne pas.
    expect(created.default_budget).not.toBeNull();
    const envelopes = await page.request.get('/api/budget/budgets/', {
      headers: await auth(page),
    });
    const envelope = unwrap<{ id: string; name: string; monthly_amount: string | null }>(
      await envelopes.json(),
    ).find((row) => row.id === created.default_budget);
    expect(envelope?.name).toBe('Terrasse assistant');
    expect(envelope?.monthly_amount).toBeNull();
  });

  test('PROJ-08 — fermer l’entretien n’écrit rien', async ({ page }) => {
    await setAssistantCapability(page, true);
    const zoneId = await firstZoneId(page);
    await stubInterview(page, zoneId);

    await page.goto('/app/projects');
    await page.getByRole('button', { name: 'Créer avec l’assistant' }).click();

    const dialog = page.getByRole('dialog').first();
    await dialog.getByLabel('Qu’est-ce que tu veux faire ?').fill('Je veux refaire la terrasse');
    await dialog.getByRole('button', { name: 'Commencer' }).click();
    await dialog.getByRole('button', { name: 'J’ai assez dit, génère' }).click();
    await expect(dialog.getByText('Relire avant de créer')).toBeVisible();

    await page.keyboard.press('Escape');

    expect(await projectsNamed(page, TITLE)).toHaveLength(0);
  });

  /**
   * PROJ-13 — la pièce jointe, de l'envoi au chantier créé.
   *
   * Trois choses que seul un vrai navigateur atteste, et qui sont **le** critère
   * du lot :
   *
   * - le champ de montant reste **vide** alors qu'une citation est affichée. Un
   *   montant recopié d'office serait indistinguable d'un montant décidé par le
   *   foyer, et il servirait de référence à la barre du chantier pendant des mois ;
   * - la pièce voyage avec **chaque tour**, pas seulement à la création — c'est ce
   *   qui permet au serveur de n'accepter une citation que si elle nomme un
   *   fichier réellement joint ;
   * - le chantier créé porte son `DocumentLink`, donc le devis n'est pas à ranger
   *   deux fois.
   *
   * Le téléversement n'est pas stubé : c'est un chemin d'écriture, et c'est là
   * qu'était le piège (les clés de `Document` sont des entiers, pas des UUID).
   */
  test('PROJ-13 — joindre un devis, citer son montant, le retrouver sur le chantier', async ({
    page,
  }) => {
    await setAssistantCapability(page, true);
    const zoneId = await firstZoneId(page);
    const interview = await stubInterview(page, zoneId, {
      suggestion: { amount: '3180.00', source: QUOTE_NAME },
    });

    await page.goto('/app/projects');
    await page.getByRole('button', { name: 'Créer avec l’assistant' }).click();

    const dialog = page.getByRole('dialog').first();
    await dialog.getByLabel('Qu’est-ce que tu veux faire ?').fill('Je veux refaire la terrasse');
    await dialog.getByRole('button', { name: 'Commencer' }).click();
    await expect(dialog.getByText('Bois, composite ou carrelage ?')).toBeVisible();

    // Joindre passe par le `DocumentUploadDialog` **existant** : le fichier entre
    // dans la bibliothèque du foyer comme n'importe quel autre, et l'entretien ne
    // le possède pas.
    await dialog.getByRole('button', { name: 'Joindre un devis ou une photo' }).click();
    // Deux dialogues sont ouverts : celui de l'entretien reste `.first()` (portail
    // monté avant), et celui du téléversement se désigne par son titre. On ne
    // scope pas l'entretien par son nom — il devient « Relire avant de créer »
    // dès qu'un brouillon existe.
    const upload = page.getByRole('dialog', { name: /Téléverser des documents/ });
    await upload.locator('#upload-file').setInputFiles(FIXTURE_QUOTE);
    await upload.locator('#upload-name').fill(QUOTE_NAME);
    await upload.getByRole('button', { name: 'Téléverser' }).click();
    await expect(upload).toBeHidden();

    // La pièce est listée dans l'entretien — sans ça on ne sait pas ce que le
    // modèle a sous les yeux.
    await expect(dialog.getByText(QUOTE_NAME)).toBeVisible();

    await dialog.getByRole('button', { name: 'bois', exact: true }).click();
    await dialog.getByRole('button', { name: 'Répondre' }).click();

    // Elle voyage avec le tour, et son id est un **nombre** : le type TS
    // `DocumentItem.id: string` ment, l'API rend un entier.
    const attached = interview.sent[interview.sent.length - 1].document_ids;
    expect(attached).toHaveLength(1);
    expect(typeof attached[0]).toBe('number');

    // Le cœur du lot : la citation est **à côté** du champ, et le champ est vide.
    const amount = dialog.locator('#assistant-answer-1');
    await expect(amount).toHaveValue('');
    const useAmount = dialog.getByRole('button', { name: new RegExp(QUOTE_NAME) });
    await expect(useAmount).toContainText(/3\s?180/);

    // Un clic, un geste délibéré — et alors seulement le montant est là.
    await useAmount.click();
    await expect(amount).toHaveValue('3180,00');

    await dialog.getByRole('button', { name: 'J’ai assez dit, génère' }).click();
    await expect(dialog.getByText('Relire avant de créer')).toBeVisible();
    await dialog.getByRole('button', { name: 'Créer le projet' }).click();
    await expect(page).toHaveURL(/\/app\/projects\/[0-9a-f-]{36}$/);

    // Le devis est sur le chantier : un `DocumentLink`, pas une pièce oubliée
    // dans la bibliothèque.
    const [created] = await projectsNamed(page, TITLE);
    const linked = await page.request.get('/api/documents/documents/', {
      headers: await auth(page),
      params: { linked_to: `project:${created.id}` },
    });
    const names = unwrap<{ name: string }>(await linked.json()).map((row) => row.name);
    expect(names).toContain(QUOTE_NAME);
  });

  /**
   * PROJ-04 — la question d'argent est un `DecimalInput`, et rien d'autre.
   *
   * Que « 12,5 » ne devienne pas 512 est une propriété du composant, déjà
   * attestée dans un vrai moteur par `e2e/decimal-input.spec.ts` — on ne la
   * redémontre pas. Ce qui se joue **ici** est l'autre moitié : que cet écran-là
   * passe bien par ce composant-là. Un `<input type="number">` posé un jour sur
   * cette question rendrait ce test rouge, et rien d'autre ne le verrait.
   *
   * D'où la frappe touche à touche : un `fill()` écrit la valeur d'un coup et
   * n'emprunte pas le chemin qui produisait le faux montant.
   */
  test('PROJ-04 — « 12,5 » part en 12.5, jamais en 512', async ({ page }) => {
    await setAssistantCapability(page, true);
    const zoneId = await firstZoneId(page);
    const interview = await stubInterview(page, zoneId);

    await page.goto('/app/projects');
    await page.getByRole('button', { name: 'Créer avec l’assistant' }).click();

    const dialog = page.getByRole('dialog').first();
    await dialog.getByLabel('Qu’est-ce que tu veux faire ?').fill('Je veux refaire la terrasse');
    await dialog.getByRole('button', { name: 'Commencer' }).click();
    await dialog.getByRole('button', { name: 'bois', exact: true }).click();
    await dialog.getByRole('button', { name: 'Répondre' }).click();

    const amount = dialog.locator('#assistant-answer-1');
    await amount.pressSequentially('12,5');

    // Ce que l'utilisateur lit est dans sa locale…
    await expect(amount).toHaveValue('12,5');

    await dialog.getByRole('button', { name: 'Répondre' }).click();

    // …et ce que le serveur reçoit est canonique. Les deux doivent être le même
    // nombre : c'est « un compteur ne peut pas avoir deux définitions » à
    // l'entrée.
    const sent = interview.sent[interview.sent.length - 1];
    expect(sent.history[sent.history.length - 1]).toMatchObject({
      field: 'budget',
      answer: '12.5',
    });
  });

  test('PROJ-14 — sans clé, le bouton est absent et le formulaire reste', async ({ page }) => {
    await setAssistantCapability(page, false);

    await page.goto('/app/projects');

    // Absent, pas désactivé : un bouton grisé promet et dément dans le même
    // geste. Et rien ne manque — le formulaire de création *est* le repli.
    await expect(page.getByRole('button', { name: 'Créer avec l’assistant' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Nouveau projet' }).first()).toBeVisible();
  });
});
