import { test, expect } from '@playwright/test';

/**
 * Parcours générique : enregistrer un achat sur un équipement.
 *
 * Issue: https://github.com/jammindev/maisonnee/issues/119 — généralisation du
 * pattern "auto-création d'Interaction(expense) depuis n'importe quel module"
 * via la FK polymorphe Interaction.source + le service create_expense_interaction.
 */

test('parcours achat d\'équipement — perceuse 199€', async ({ page }) => {
  // 1. Créer un équipement « Perceuse E2E »
  await page.goto('/app/equipment');
  await expect(page).toHaveURL(/\/app\/equipment/);

  await page.getByRole('button', { name: 'Nouveau' }).first().click();

  let dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const itemName = `Perceuse E2E ${Date.now()}`;
  await page.locator('#eq-name').fill(itemName);

  await dialog.getByRole('button', { name: /enregistrer|créer/i }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(itemName)).toBeVisible();

  // 2. Cliquer sur l'action « Achat » de la card
  const card = page.getByText(itemName, { exact: true }).locator('xpath=ancestor::li');
  await card.getByRole('button', { name: 'Achat' }).click();

  dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('Enregistrer un achat');
  await expect(dialog).toContainText(itemName);

  // 3. Remplir : pas de delta (equipment), juste prix + fournisseur
  await page.locator('#purchase-price').fill('199');
  await page.locator('#purchase-supplier').fill('ToolStore');
  await dialog.getByRole('button', { name: "Enregistrer l'achat" }).click();
  await expect(dialog).toBeHidden();

  // 4. Vérifier que l'interaction expense est listée dans /app/interactions
  await page.goto('/app/interactions');
  await expect(page.getByText(`Achat — ${itemName}`).first()).toBeVisible();
});
