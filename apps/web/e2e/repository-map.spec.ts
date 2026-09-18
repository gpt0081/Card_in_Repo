import { expect, test } from '@playwright/test';

test('public Python repository reaches READY, renders the feature map, then opens fact-backed files', async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto(process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080');

  await expect(page.getByRole('heading', { name: 'Read the flow before the files.' })).toBeVisible();
  // Use a stable public Python fixture whose default branch contains analyzable
  // source. Card_in_Repo's main branch is intentionally still the bootstrap
  // contract while the implementation is progressing through stacked PRs.
  await page.getByLabel('Public repository').fill('https://github.com/pypa/sampleproject');
  await page.getByRole('button', { name: 'Map repo' }).click();

  const status = page.locator('.status strong');
  await expect(status).not.toHaveText('IDLE');
  await expect(status).toHaveText('READY', { timeout: 110_000 });

  await expect(page.getByRole('heading', { name: 'Repository map' })).toBeVisible();
  await expect(page.locator('article.feature').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Feature map' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Files' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Concepts' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Cards' })).toBeDisabled();

  await page.getByRole('button', { name: 'Files' }).click();
  await expect(page.getByRole('heading', { name: 'File structure' })).toBeVisible();
  await expect(page.locator('article.file').first()).toBeVisible();
});
