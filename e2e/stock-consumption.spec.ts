import { test, expect } from '@playwright/test';

/**
 * Parcours 18 — Lot 2 : achat enrichi (marque + quantité restante) et inventaire.
 *
 * Issue: https://github.com/jammindev/maisonnee/issues/289
 * Vérifie qu'un achat avec « quantité restante avant achat » recale le stock
 * (restant + delta) et que la marque remonte dans l'historique, puis qu'un
 * inventaire en valeur absolue met à jour la quantité.
 */

test("parcours achat avec restant + inventaire — nourriture", async ({ page }) => {
  const stamp = Date.now();

  // 1. Créer une catégorie (onglet Catégories).
  await page.goto('/app/stock');
  await page.getByRole('button', { name: 'Catégories' }).click();
  await page.getByRole('button', { name: 'Nouvelle catégorie' }).first().click();
  let dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const catName = `Animaux E2E ${stamp}`;
  await page.locator('#cat-name').fill(catName);
  await dialog.getByRole('button', { name: /enregistrer|créer/i }).click();
  await expect(dialog).toBeHidden();

  // 2. Créer un article avec quantité initiale 2.
  await page.getByRole('button', { name: 'Articles' }).click();
  await page.getByRole('button', { name: 'Nouveau' }).first().click();
  dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const itemName = `Nourriture E2E ${stamp}`;
  await page.locator('#stock-item-name').fill(itemName);
  await page.locator('#stock-item-category').selectOption({ label: `📦 ${catName}` });
  await page.locator('#stock-item-qty').fill('2');
  await page.locator('#stock-item-unit').fill('kg');
  await dialog.getByRole('button', { name: /enregistrer|créer/i }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(itemName)).toBeVisible();

  // 3. Achat : +20 kg, restant réel 0,5 kg (≠ 2 théorique → recalage), marque Gasco.
  const card = page.getByText(itemName, { exact: true }).locator('xpath=ancestor::li');
  await card.getByRole('button', { name: 'Achat' }).click();
  dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await page.locator('#purchase-delta').fill('20');
  await page.locator('#purchase-remaining').fill('0.5');
  await page.locator('#purchase-price').fill('30');
  await page.locator('#purchase-brand').fill('Gasco');
  await expect(dialog).toContainText('0.5'); // hint de recalage
  await dialog.getByRole('button', { name: "Enregistrer l'achat" }).click();
  await expect(dialog).toBeHidden();

  // 4. Fiche détail : quantité recalée à 20,5 kg + marque dans l'historique.
  await page.getByText(itemName, { exact: true }).click();
  await expect(page).toHaveURL(/\/app\/stock\/[0-9a-f-]+/);
  await expect(page.getByText('20.5 kg')).toBeVisible();
  await page.getByRole('button', { name: 'Historique' }).click();
  await expect(page.getByText('Gasco')).toBeVisible();

  // 5. Inventaire : je compte 8 kg restants.
  await page.getByRole('button', { name: 'Inventaire' }).first().click();
  dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await page.locator('#inventory-quantity').fill('8');
  await dialog.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(dialog).toBeHidden();
  await page.getByRole('button', { name: 'Infos' }).click();
  await expect(page.getByText('8 kg')).toBeVisible();
});
