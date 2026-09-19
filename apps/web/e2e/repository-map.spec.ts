import { expect, test } from '@playwright/test';

test('public Python repository reaches READY and follows feature, files, concepts, cards ordering', async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto(process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080');

  await expect(page.getByRole('heading', { name: 'Read the flow before the files.' })).toBeVisible();
  await page.getByLabel('Public repository').fill('https://github.com/pypa/sampleproject');
  await page.getByRole('button', { name: 'Map repo' }).click();

  const status = page.locator('.status strong');
  await expect(status).not.toHaveText('IDLE');
  await expect(status).toHaveText('READY', { timeout: 110_000 });

  await expect(page.getByRole('heading', { name: 'Repository map' })).toBeVisible();
  await expect(page.locator('article.feature').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Files' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Concepts' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Cards' })).toBeDisabled();

  await page.getByRole('button', { name: 'Files' }).click();
  await expect(page.getByRole('heading', { name: 'File structure' })).toBeVisible();
  await expect(page.locator('article.file').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Concepts' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Cards' })).toBeDisabled();

  await page.getByRole('button', { name: 'Concepts' }).click();
  await expect(page.getByRole('heading', { name: 'Concepts' })).toBeVisible();
  const concept = page.locator('article.concept').first();
  await expect(concept).toBeVisible();
  await expect(concept.locator('.basicTeaching[data-verified="true"]')).toBeVisible();
  await expect(concept.locator('.teachingClaim').first()).toBeVisible();
  await expect(concept.locator('.evidenceCitation').first()).toHaveAttribute('data-evidence-id', /.+/);
  await expect(page.locator('.basicTeaching[data-verified="false"]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Cards' })).toBeEnabled();

  await page.getByRole('button', { name: 'Cards' }).click();
  await expect(page.getByRole('heading', { name: 'Code cards' })).toBeVisible();
  const card = page.locator('article.codeCard').first();
  await expect(card).toBeVisible();
  await expect(card.locator('pre code')).not.toBeEmpty();
  await expect(card.locator('.cardTeaching[data-verified="true"]')).toBeVisible();
  await expect(card.locator('.teachingClaim').first()).toBeVisible();
  await expect(card.locator('.evidenceCitation').first()).toHaveAttribute('data-evidence-id', /.+/);
  await expect(page.locator('.cardTeaching[data-verified="false"]')).toHaveCount(0);
  await expect(page.getByText('STUB_VERIFIED')).toHaveCount(0);
});
