import { expect, test } from '@playwright/test';

test('selected execution symbol scopes code cards on mobile', async ({ page }) => {
  const baseUrl = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080';
  const analysisId = 'card-flow-context';
  await page.setViewportSize({ width: 390, height: 844 });

  await page.route(`**/v1/analyses/${analysisId}`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ id: analysisId, state: 'READY', repository: 'https://github.com/example/repo' }) }));
  await page.route(`**/v1/analyses/${analysisId}/features`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, features: [{ id: 'feature:checkout', name: 'Checkout', flow_steps: [{ order: 0, symbol_id: 'symbol:checkout', symbol_name: 'checkout', relation: 'entry' }] }] }) }));
  await page.route(`**/v1/analyses/${analysisId}/files`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, files: [{ path: 'src/checkout.ts', symbols: [{ id: 'symbol:checkout', name: 'checkout', kind: 'function', range: { start: { line: 12 }, end: { line: 24 } } }, { id: 'symbol:unrelated', name: 'unrelated', kind: 'function', range: { start: { line: 30 }, end: { line: 35 } } }] }] }) }));
  await page.route(`**/v1/analyses/${analysisId}/concepts`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, concepts: [{ id: 'concept:checkout', name: 'Checkout flow', kind: 'execution_flow', feature_id: 'feature:checkout', evidence: [{ id: 'evidence:checkout', symbol_id: 'symbol:checkout', symbol_name: 'checkout', path: 'src/checkout.ts', order: 0 }], explanation: { level: 'basic', verified: true, claims: [{ text: 'Checkout starts here.', evidence_ids: ['evidence:checkout'] }] } }] }) }));
  await page.route(`**/v1/learning/analyses/${analysisId}/concepts`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, states: [] }) }));
  await page.route(`**/v1/analyses/${analysisId}/cards`, route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis_id: analysisId, cards: [
    { id: 'card:checkout', analysis_id: analysisId, path: 'src/checkout.ts', symbol_id: 'symbol:checkout', symbol_name: 'checkout', range: { start: { line: 12 }, end: { line: 24 } }, segment: { index: 0, count: 1 }, source: 'function checkout() { return true; }', basic_explanation: { level: 'basic', verified: true, claims: [{ text: 'Selected checkout card.', evidence_ids: ['range:checkout'] }] }, evidence: [{ id: 'range:checkout', type: 'SOURCE_RANGE', path: 'src/checkout.ts', range: { start: { line: 12 }, end: { line: 24 } } }] },
    { id: 'card:unrelated', analysis_id: analysisId, path: 'src/checkout.ts', symbol_id: 'symbol:unrelated', symbol_name: 'unrelated', range: { start: { line: 30 }, end: { line: 35 } }, segment: { index: 0, count: 1 }, source: 'function unrelated() {}', basic_explanation: { level: 'basic', verified: true, claims: [{ text: 'Unrelated card.', evidence_ids: ['range:unrelated'] }] }, evidence: [{ id: 'range:unrelated', type: 'SOURCE_RANGE', path: 'src/checkout.ts', range: { start: { line: 30 }, end: { line: 35 } } }] }
  ] }) }));

  await page.goto(`${baseUrl}/?analysis=${analysisId}&view=features`);
  await page.getByRole('button', { name: 'Open checkout in file structure' }).click();
  await page.getByRole('button', { name: 'Concepts' }).click();
  await page.getByRole('button', { name: 'Cards' }).click();

  await expect(page.getByRole('heading', { name: 'Code cards' })).toBeVisible();
  await expect(page.locator('.flowCardContext')).toHaveAttribute('data-flow-scoped', 'true');
  await expect(page.locator('.flowCardContext')).toContainText('1 function card follows the selected execution symbol.');
  await expect(page.getByRole('heading', { name: 'checkout' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'unrelated' })).toHaveCount(0);
});
