import { test, expect } from '@playwright/test';

/**
 * Parcours 08 — Lot 1.1 : enregistrer une dépense liée à un projet.
 *
 * Issues: https://github.com/jammindev/maisonnee/issues/123
 *         https://github.com/jammindev/maisonnee/issues/131 (onglet Dépenses)
 *
 * Le test déclenche le quick-add depuis la card d'un projet, vérifie que
 * l'`Interaction(type=expense, kind='project_purchase')` est créée et listée
 * dans /app/interactions ET dans l'onglet Dépenses du projet (liaison via la
 * source polymorphe — c'était le bug de désync de #131), et qu'elle apparaît
 * dans la vue dépenses.
 */

test('parcours achat projet — Rénovation salle de bain 450€ Leroy Merlin', async ({ page }) => {
  // Utilise un projet seedé par seed_demo_data ("Rénovation salle de bain") —
  // le test se concentre sur le parcours d'achat, pas sur la création de projet
  // (couverte par pytest test_create_project_accepts_blank_description_from_ui).
  await page.goto('/app/projects');
  await expect(page).toHaveURL(/\/app\/projects/);

  const projectTitle = 'Rénovation salle de bain';
  await expect(page.getByText(projectTitle).first()).toBeVisible();

  // Cliquer sur l'action « + Dépense » sur la card du projet
  const card = page.getByText(projectTitle, { exact: true })
    .locator('xpath=ancestor::*[contains(@class, "rounded")][1]');
  await card.getByRole('button', { name: 'Dépense' }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('Enregistrer une dépense');
  await expect(dialog).toContainText(projectTitle);

  const supplier = `Leroy Merlin E2E ${Date.now()}`;
  await page.locator('#purchase-price').fill('450');
  await page.locator('#purchase-supplier').fill(supplier);
  await dialog.getByRole('button', { name: "Enregistrer l'achat" }).click();
  await expect(dialog).toBeHidden();

  // Vérifier que la dépense apparaît dans l'onglet Dépenses du projet
  // (régression #131 : les achats du dialog n'y étaient pas visibles)
  await page.getByText(projectTitle, { exact: true }).first().click();
  await expect(page).toHaveURL(/\/app\/projects\/[0-9a-f-]+/);
  await page.getByRole('button', { name: 'Dépenses', exact: true }).click();
  await expect(page.getByText(`Achat — ${projectTitle}`).first()).toBeVisible();

  // Point d'entrée unique (#235) : le bouton « Dépense » de l'onglet ouvre le
  // dialog d'achat (pas le form complet)
  await page.getByRole('button', { name: 'Dépense', exact: true }).last().click();
  const tabDialog = page.getByRole('dialog');
  await expect(tabDialog).toBeVisible();
  await expect(tabDialog).toContainText('Enregistrer une dépense');
  await tabDialog.getByRole('button', { name: 'Annuler' }).click();
  await expect(tabDialog).toBeHidden();

  // Vérifier que l'interaction expense est listée dans /app/interactions
  await page.goto('/app/interactions');
  await expect(page.getByText(`Achat — ${projectTitle}`).first()).toBeVisible();

  // Vérifier qu'elle apparaît aussi dans la vue dépense (filtrée par supplier
  // pour distinguer cette execution des autres)
  await page.goto('/app/money/expenses');
  await expect(page.getByText(supplier).first()).toBeVisible();
});
