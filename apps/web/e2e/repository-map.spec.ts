import { expect, test } from '@playwright/test';

async function proveLearningPath(page: any, repositoryUrl: string, readyTimeout = 110_000) {
  await page.goto(process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080');
  await expect(page.getByRole('heading', { name: 'Read the flow before the files.' })).toBeVisible();
  await page.getByLabel('Public repository').fill(repositoryUrl);
  await page.getByRole('button', { name: 'Map repo' }).click();

  const status = page.locator('.status strong');
  await expect(status).not.toHaveText('IDLE');
  await expect(status).toHaveText('READY', { timeout: readyTimeout });

  await expect(page.getByRole('heading', { name: 'Repository map' })).toBeVisible();
  await expect(page.locator('article.feature').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Files' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Concepts' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Cards' })).toBeDisabled();

  await page.getByRole('button', { name: 'Files' }).click();
  await expect(page.getByRole('heading', { name: 'File structure' })).toBeVisible();
  await expect(page.locator('article.file').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Concepts' })).toBeEnabled();

  await page.getByRole('button', { name: 'Concepts' }).click();
  await expect(page.getByRole('heading', { name: 'Concepts' })).toBeVisible();
  const concept = page.locator('article.concept').first();
  await expect(concept).toBeVisible();
  await expect(concept.locator('.basicTeaching[data-verified="true"]')).toBeVisible();
  await expect(concept.locator('.evidenceCitation').first()).toHaveAttribute('data-evidence-id', /.+/);
  await expect(page.locator('.basicTeaching[data-verified="false"]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Cards' })).toBeEnabled();

  await page.getByRole('button', { name: 'Cards' }).click();
  await expect(page.getByRole('heading', { name: 'Code cards' })).toBeVisible();
  const card = page.locator('article.codeCard').first();
  await expect(card).toBeVisible();
  await expect(card.locator('pre code')).not.toBeEmpty();
  await expect(card.locator('.cardTeaching[data-verified="true"]')).toBeVisible();
  await expect(card.locator('.evidenceCitation').first()).toHaveAttribute('data-evidence-id', /.+/);
  await expect(page.locator('.cardTeaching[data-verified="false"]')).toHaveCount(0);

  await expect(card.getByRole('button', { name: 'Explain intermediate' })).toBeVisible();
  await card.getByRole('button', { name: 'Explain intermediate' }).click();
  const intermediate = card.locator('.deeperTeaching[data-verified="true"][data-level="intermediate"]');
  await expect(intermediate).toBeVisible();
  await expect(intermediate.locator('.evidenceCitation').first()).toHaveAttribute('data-evidence-id', /.+/);
}

test('public Python repository reaches READY and follows feature, files, concepts, cards ordering', async ({ page }) => {
  test.setTimeout(120_000);
  await proveLearningPath(page, 'https://github.com/pypa/sampleproject');
});

test('public TypeScript repository reaches READY and produces evidence-backed learning cards', async ({ page }) => {
  // Use a tiny, active public repository with ordinary named TypeScript functions. This
  // exercises the real GitHub network path while also matching the function-sized-card
  // contract that the current fact layer is expected to support.
  test.setTimeout(120_000);
  await proveLearningPath(page, 'https://github.com/TheInvader360/fc64js-typescript-basic-example');

  // proveLearningPath ends in Cards, so explicitly return to Files before asserting that
  // the fetched public snapshot actually contains JavaScript/TypeScript-family source.
  await page.getByRole('button', { name: 'Files' }).click();
  await expect(page.getByRole('heading', { name: 'File structure' })).toBeVisible();
  await expect(page.locator('article.file').filter({ hasText: /\.tsx?|\.jsx?/ }).first()).toBeVisible();
});

test('restored feature route keeps certainty cues readable on a narrow mobile viewport', async ({ page }) => {
  const baseUrl = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080';
  const analysisId = 'call-evidence-regression';
  await page.setViewportSize({ width: 390, height: 844 });

  await page.route(`**/v1/analyses/${analysisId}`, route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ id: analysisId, state: 'READY', repository: 'https://github.com/example/repo' }),
  }));
  await page.route(`**/v1/analyses/${analysisId}/features`, route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      analysis_id: analysisId,
      features: [{
        id: 'feature:run',
        name: 'Run flow',
        entry_symbol_id: 'symbol:start',
        flow_steps: [
          { order: 0, symbol_id: 'symbol:start', symbol_name: 'start', relation: 'entry' },
          {
            order: 1,
            symbol_id: 'symbol:finish',
            symbol_name: 'finish',
            relation: 'calls',
            unresolved_calls: [
              { callee: 'this.finish', callee_kind: 'member', receiver: 'this', member_name: 'finish', dispatch: 'dynamic' },
              { callee: 'client.run', callee_kind: 'member', receiver: 'client', member_name: 'run', dispatch: 'unknown' },
            ],
          },
        ],
      }],
    }),
  }));

  await page.goto(`${baseUrl}/?analysis=${analysisId}&view=features`);
  await expect(page.getByRole('heading', { name: 'Repository map' })).toBeVisible();

  const legend = page.getByLabel('Execution flow certainty');
  await expect(legend).toBeVisible();
  await expect(legend).toContainText('Proven static flow');
  await expect(legend).toContainText('Runtime-dependent call');
  await expect(legend).toHaveCSS('display', 'grid');

  await expect(page.locator('[data-flow-certainty="resolved"]')).toContainText('start');
  await expect(page.locator('[data-flow-certainty="resolved"] .flowMarker--resolved')).toBeVisible();
  await expect(page.locator('[data-flow-certainty="uncertain"]')).toContainText('finish');
  await expect(page.locator('[data-flow-certainty="uncertain"] .flowMarker--uncertain')).toBeVisible();
  await expect(page.locator('[data-flow-certainty="uncertain"]')).toHaveCSS('border-left-style', 'dashed');

  await expect(page.locator('[data-dispatch="dynamic"]')).toContainText('this.finish');
  await expect(page.locator('[data-dispatch="dynamic"]')).toContainText('dynamic dispatch');
  await expect(page.locator('[data-dispatch="unknown"]')).toContainText('client.run');
  await expect(page.locator('[data-dispatch="unknown"]')).toContainText('target unknown');
});
