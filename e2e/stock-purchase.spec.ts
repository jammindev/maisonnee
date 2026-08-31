import { test, expect } from '@playwright/test';

/**
 * Parcours friction utilisateur : "j'ai acheté 3,8 stères de bois,
 * je veux les rentrer dans mon stock et tracer la dépense en un seul geste".
 *
 * Issue: https://github.com/jammindev/maisonnee/issues/116
 */

test('parcours achat de stock — bois de chauffage 3,8 stères', async ({ page }) => {
  // 1. Créer la catégorie "Chauffage E2E"
  await page.goto('/app/stock');
  await expect(page).toHaveURL(/\/app\/stock/);

  await page.getByRole('button', { name: 'Catégories', exact: true }).click();
  await page.getByRole('button', { name: 'Nouvelle catégorie' }).first().click();

  let dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const categoryName = `Chauffage E2E ${Date.now()}`;
  await dialog.getByLabel('Nom').fill(categoryName);
  await dialog.getByRole('button', { name: 'Créer' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(categoryName)).toBeVisible();

  // 2. Créer l'article "Bois de chauffage" avec unit=stère
  await page.getByRole('button', { name: 'Articles', exact: true }).click();
  await page.getByRole('button', { name: 'Nouveau' }).first().click();

  dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const itemName = `Bois de chauffage E2E ${Date.now()}`;
  await page.locator('#stock-item-name').fill(itemName);

  const categorySelect = page.locator('#stock-item-category');
  const categoryOption = categorySelect.locator(`option:has-text("${categoryName}")`);
  await categoryOption.waitFor({ state: 'attached', timeout: 10_000 });
  await categorySelect.selectOption(await categoryOption.getAttribute('value') as string);

  // unit personnalisée
  await page.locator('#stock-item-unit').fill('stère');
  // commencer à 0 pour vérifier l'incrément
  await page.locator('#stock-item-qty').fill('0');

  await dialog.getByRole('button', { name: 'Créer' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(itemName)).toBeVisible();

  // 3. Ouvrir le dialog d'achat depuis la card
  const card = page.getByText(itemName, { exact: true }).locator('xpath=ancestor::li');
  await card.getByRole('button', { name: 'Achat' }).click();

  dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('Approvisionner');
  await expect(dialog).toContainText(itemName);
  await expect(dialog).toContainText('Quantité actuelle');

  // 4. Remplir : 3,8 stères / 342 € / Wood Co.
  await page.locator('#purchase-delta').fill('3.8');
  await page.locator('#purchase-price').fill('342');
  await page.locator('#purchase-supplier').fill('Wood Co.');
  await dialog.getByRole('button', { name: "Enregistrer l'achat" }).click();

  await expect(dialog).toBeHidden();

  // 5. Vérifier que la quantité a été incrémentée sur la card
  await expect(card).toContainText('3.8');
  await expect(card).toContainText('stère');

  // 6. Vérifier que l'interaction expense est listée dans /app/interactions
  await page.goto('/app/interactions');
  await expect(page.getByText(itemName).first()).toBeVisible();
});
