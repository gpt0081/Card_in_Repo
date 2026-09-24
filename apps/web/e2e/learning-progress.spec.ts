import { createHmac } from 'node:crypto';
import { expect, test } from '@playwright/test';

function signedSession(secret: string) {
  const payload = JSON.stringify({
    avatar_url: null,
    github_id: 424242,
    iat: Math.floor(Date.now() / 1000),
    login: 'ci-learner',
  });
  const encoded = Buffer.from(payload).toString('base64url');
  const signature = createHmac('sha256', secret).update(encoded).digest('base64url');
  return `${encoded}.${signature}`;
}

test('authenticated mastery persists and drives the next-concept recommendation', async ({ page, context }) => {
  test.setTimeout(120_000);
  const baseUrl = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080';
  const secret = process.env.E2E_SESSION_SECRET;
  if (!secret) throw new Error('E2E_SESSION_SECRET is required for mastery coverage');

  await context.addCookies([{
    name: 'card_in_repo_session',
    value: signedSession(secret),
    url: baseUrl,
    httpOnly: true,
    sameSite: 'Lax',
  }]);

  await page.goto(baseUrl);
  await expect(page.getByLabel('GitHub account').getByText('@ci-learner')).toBeVisible();
  await page.getByLabel('Public repository').fill('https://github.com/pypa/sampleproject');
  await page.getByRole('button', { name: 'Map repo' }).click();
  await expect(page.locator('.status strong')).toHaveText('READY', { timeout: 110_000 });

  const analysisId = (await page.locator('.status span').textContent())?.trim();
  expect(analysisId).toBeTruthy();

  await page.getByRole('button', { name: 'Files' }).click();
  await page.getByRole('button', { name: 'Concepts' }).click();
  await expect(page).toHaveURL(new RegExp(`analysis=${analysisId}.*view=concepts`));

  const progress = page.getByRole('region', { name: 'Concept learning progress' });
  await expect(progress).toBeVisible();
  const recommendation = progress.getByRole('complementary', { name: 'Recommended next concept' });
  await expect(recommendation).toBeVisible();
  await expect(recommendation.getByRole('button', { name: 'Go to concept' })).toBeVisible();

  const initialNext = await page.evaluate(async analysisId => {
    const response = await fetch(`/v1/learning/analyses/${encodeURIComponent(analysisId)}/next`, { credentials: 'include' });
    if (!response.ok) throw new Error(`next concept HTTP ${response.status}`);
    return (await response.json()).recommendation;
  }, analysisId!);
  expect(initialNext?.concept?.id).toBeTruthy();
  expect(initialNext?.reason).toBe('execution_flow');

  const row = progress.locator(`[data-concept-id="${initialNext.concept.id}"]`);
  await expect(row).toBeVisible();
  await row.getByRole('button', { name: 'Understood' }).click();
  await expect(row.getByRole('button', { name: 'Understood' })).toHaveAttribute('aria-pressed', 'true');
  await expect(row.locator('small')).toHaveText('understood');

  const nextAfterMastery = await page.evaluate(async analysisId => {
    const response = await fetch(`/v1/learning/analyses/${encodeURIComponent(analysisId)}/next`, { credentials: 'include' });
    if (!response.ok) throw new Error(`next concept HTTP ${response.status}`);
    return (await response.json()).recommendation;
  }, analysisId!);
  if (nextAfterMastery) {
    expect(nextAfterMastery.concept.id).not.toBe(initialNext.concept.id);
    await expect(recommendation.getByText(`Next · ${nextAfterMastery.concept.name}`)).toBeVisible();
  } else {
    await expect(progress.getByText('All discovered concepts are understood.')).toBeVisible();
  }

  await page.reload();
  await expect(page.getByLabel('GitHub account').getByText('@ci-learner')).toBeVisible();
  await expect(page.locator('.status strong')).toHaveText('READY', { timeout: 110_000 });
  await expect(page).toHaveURL(new RegExp(`analysis=${analysisId}.*view=concepts`));

  const restoredProgress = page.getByRole('region', { name: 'Concept learning progress' });
  await expect(restoredProgress).toBeVisible();
  const restoredRow = restoredProgress.locator(`[data-concept-id="${initialNext.concept.id}"]`);
  await expect(restoredRow.getByRole('button', { name: 'Understood' })).toHaveAttribute('aria-pressed', 'true');
  await expect(restoredRow.locator('small')).toHaveText('understood');

  const persisted = await page.evaluate(async ({ analysisId, conceptId }) => {
    const response = await fetch(`/v1/learning/analyses/${encodeURIComponent(analysisId)}/concepts`, { credentials: 'include' });
    if (!response.ok) throw new Error(`learning state HTTP ${response.status}`);
    const body = await response.json();
    return body.states.find((state: { concept_id: string }) => state.concept_id === conceptId);
  }, { analysisId: analysisId!, conceptId: initialNext.concept.id });

  expect(persisted?.mastery).toBe('understood');
  expect(persisted?.github_user_id).toBe(424242);
});
