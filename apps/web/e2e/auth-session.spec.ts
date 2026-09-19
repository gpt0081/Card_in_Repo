import { createHmac } from 'node:crypto';
import { expect, test } from '@playwright/test';

function base64url(value: Buffer | string) {
  return Buffer.from(value).toString('base64url');
}

function signedSession(secret: string) {
  // Keep keys in lexical order to match Python json.dumps(sort_keys=True).
  const payload = JSON.stringify({
    avatar_url: null,
    github_id: 424242,
    iat: Math.floor(Date.now() / 1000),
    login: 'ci-learner',
  });
  const encoded = base64url(payload);
  const signature = createHmac('sha256', secret).update(encoded).digest('base64url');
  return `${encoded}.${signature}`;
}

test('authenticated GitHub session survives navigation and can sign out', async ({ page, context }) => {
  const baseUrl = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080';
  const secret = process.env.E2E_SESSION_SECRET;
  if (!secret) throw new Error('E2E_SESSION_SECRET is required for authenticated session coverage');

  await context.addCookies([{
    name: 'card_in_repo_session',
    value: signedSession(secret),
    url: baseUrl,
    httpOnly: true,
    sameSite: 'Lax',
  }]);

  await page.goto(baseUrl);
  const account = page.getByLabel('GitHub account');
  await expect(account.getByText('@ci-learner')).toBeVisible();
  await expect(account.getByRole('button', { name: 'Sign out' })).toBeVisible();

  await page.reload();
  await expect(page.getByLabel('GitHub account').getByText('@ci-learner')).toBeVisible();

  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByLabel('GitHub account').getByRole('link', { name: 'Sign in with GitHub' })).toBeVisible();
  await expect(page.getByText('@ci-learner')).toHaveCount(0);
});
