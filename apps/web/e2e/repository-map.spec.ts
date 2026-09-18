import { expect, test } from '@playwright/test';

test('public repository reaches READY and renders the feature-first map', async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto(process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080');

  await expect(page.getByRole('heading', { name: 'Read the flow before the files.' })).toBeVisible();
  await page.getByLabel('Public repository').fill('https://github.com/gpt0081/Card_in_Repo');
  await page.getByRole('button', { name: 'Map repo' }).click();

  const status = page.locator('.status strong');
  await expect(status).not.toHaveText('IDLE');
  await expect(status).toHaveText('READY', { timeout: 110_000 });

  await expect(page.getByRole('heading', { name: 'Repository map' })).toBeVisible();
  await expect(page.locator('article.feature').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Feature map' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Files' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Concepts' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Cards' })).toBeDisabled();
});
