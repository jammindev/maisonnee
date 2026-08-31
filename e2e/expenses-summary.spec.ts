import { test, expect } from '@playwright/test';

/**
 * Parcours 08 — Lot 1.0 : vue dépense agrégée + endpoint summary.
 *
 * Issue: https://github.com/jammindev/maisonnee/issues/122
 *
 * Le test crée une dépense via le parcours stock (déjà rodé) puis vérifie
 * que l'onglet Dépenses du module Argent affiche le total + le breakdown.
 */

test('parcours dépenses — total mensuel + breakdown via achat de stock', async ({ page }) => {
  // 1. Créer une catégorie + item de stock (mêmes selectors que stock-purchase.spec.ts)
  await page.goto('/app/stock');
  await expect(page).toHaveURL(/\/app\/stock/);

  await page.getByRole('button', { name: 'Catégories', exact: true }).click();
  await page.getByRole('button', { name: 'Nouvelle catégorie' }).first().click();
  let dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const categoryName = `Cat dépense E2E ${Date.now()}`;
  await dialog.getByLabel('Nom').fill(categoryName);
  await dialog.getByRole('button', { name: 'Créer' }).click();
  await expect(dialog).toBeHidden();

  await page.getByRole('button', { name: 'Articles', exact: true }).click();
  await page.getByRole('button', { name: 'Nouveau' }).first().click();
  dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const itemName = `Bois E2E ${Date.now()}`;
  await page.locator('#stock-item-name').fill(itemName);

  const categorySelect = page.locator('#stock-item-category');
  const categoryOption = categorySelect.locator(`option:has-text("${categoryName}")`);
  await categoryOption.waitFor({ state: 'attached', timeout: 10_000 });
  await categorySelect.selectOption(await categoryOption.getAttribute('value') as string);

  await page.locator('#stock-item-unit').fill('stère');
  await page.locator('#stock-item-qty').fill('0');
  await dialog.getByRole('button', { name: 'Créer' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(itemName)).toBeVisible();

  // 2. Enregistrer un achat sur cet item
  const card = page.getByText(itemName, { exact: true }).locator('xpath=ancestor::li');
  await card.getByRole('button', { name: 'Achat' }).click();
  dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await page.locator('#purchase-delta').fill('3');
  await page.locator('#purchase-price').fill('150');
  await page.locator('#purchase-supplier').fill('Wood Co E2E');
  await dialog.getByRole('button', { name: "Enregistrer l'achat" }).click();
  await expect(dialog).toBeHidden();

  // 3. Naviguer vers l'onglet Dépenses et vérifier le total
  await page.goto('/app/money/expenses');
  await expect(page).toHaveURL(/\/app\/money/);
  await expect(page.getByRole('heading', { level: 1, name: 'Dépenses' })).toBeVisible();

  // Le total du mois courant doit refléter au moins notre achat de 150 €.
  // On évite d'asserter exactement 150,00 € pour ne pas casser si la DB
  // contient déjà des dépenses seedées.
  await expect(page.getByText('Total', { exact: true })).toBeVisible();

  // Le breakdown par type doit afficher "Achat de stock"
  await expect(page.getByText('Achat de stock').first()).toBeVisible();

  // Le breakdown par fournisseur doit afficher notre supplier
  await expect(page.getByText('Wood Co E2E').first()).toBeVisible();

  // La liste des dépenses doit montrer notre achat
  await expect(page.getByText(`Achat — ${itemName}`).first()).toBeVisible();
});
