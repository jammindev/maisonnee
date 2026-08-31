import { test, expect, type Page } from '@playwright/test';

/**
 * La création de projet par entretien — parcours 32, lot 3 (issue #655).
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
 *   bout en bout.
 *
 * Couvre `PROJ-01`, `PROJ-05`, `PROJ-06`, `PROJ-08`, `PROJ-11` et `PROJ-14`.
 */

const STEP_URL = '**/api/projects/projects/assistant-step/';

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

/** Un entretien scripté : une question de matière, une d'argent, puis le plan. */
async function stubInterview(page: Page, zoneId: string): Promise<void> {
  await page.route(STEP_URL, async (route) => {
    const sent = route.request().postDataJSON() as {
      history: { answer: string }[];
      force_ready: boolean;
    };
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
  });

  test('PROJ-01/05/06/11 — raconter, relire, décocher, créer', async ({ page }) => {
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

    // On retire la tâche qui ne sert à rien, on corrige l'autre.
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

  test('PROJ-14 — sans clé, le bouton est absent et le formulaire reste', async ({ page }) => {
    await setAssistantCapability(page, false);

    await page.goto('/app/projects');

    // Absent, pas désactivé : un bouton grisé promet et dément dans le même
    // geste. Et rien ne manque — le formulaire de création *est* le repli.
    await expect(page.getByRole('button', { name: 'Créer avec l’assistant' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Nouveau projet' }).first()).toBeVisible();
  });
});
