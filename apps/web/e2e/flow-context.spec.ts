import { expect, test } from '@playwright/test';

test('selected flow symbol survives concept detour and returns to the same code', async ({ page }) => {
  const baseUrl = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080';
  const analysisId = 'flow-context-round-trip';
  await page.setViewportSize({ width: 390, height: 844 });

  await page.route(`**/v1/analyses/${analysisId}`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ id: analysisId, state: 'READY', repository: 'https://github.com/example/repo' }) }));
  await page.route(`**/v1/analyses/${analysisId}/features`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, features: [{ id: 'feature:checkout', name: 'Checkout', flow_steps: [{ order: 0, symbol_id: 'symbol:checkout', symbol_name: 'checkout', relation: 'entry' }] }] }) }));
  await page.route(`**/v1/analyses/${analysisId}/files`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, files: [{ path: 'src/checkout.ts', symbols: [{ id: 'symbol:checkout', name: 'checkout', kind: 'function', range: { start: { line: 12 }, end: { line: 24 } } }] }] }) }));
  await page.route(`**/v1/analyses/${analysisId}/concepts`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, concepts: [{ id: 'concept:checkout', name: 'Checkout flow', kind: 'execution_flow', feature_id: 'feature:checkout', evidence: [{ id: 'evidence:checkout', symbol_id: 'symbol:checkout', symbol_name: 'checkout', path: 'src/checkout.ts', order: 0 }], explanation: { level: 'basic', verified: true, claims: [{ text: 'Checkout starts here.', evidence_ids: ['evidence:checkout'] }] } }] }) }));
  await page.route(`**/v1/learning/analyses/${analysisId}/concepts`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, states: [] }) }));

  await page.goto(`${baseUrl}/?analysis=${analysisId}&view=features`);
  await page.getByRole('button', { name: 'Open checkout in file structure' }).click();
  const selected = page.locator('[id="symbol-symbol:checkout"]');
  await expect(selected).toBeFocused();

  await page.getByRole('button', { name: 'Concepts' }).click();
  const context = page.getByLabel('Selected execution context');
  await expect(context).toHaveAttribute('data-symbol-id', 'symbol:checkout');
  await expect(context).toContainText('1 evidence-backed concept references this symbol.');
  await context.getByRole('button', { name: 'Return to selected code' }).click();

  await expect(page.getByRole('heading', { name: 'File structure' })).toBeVisible();
  await expect(selected).toHaveAttribute('data-selected', 'true');
  await expect(selected).toHaveAttribute('aria-current', 'location');
  await expect(selected).toBeFocused();
});
