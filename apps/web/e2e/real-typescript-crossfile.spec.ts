import { expect, test } from '@playwright/test';

type FlowStep = { symbol_id: string; relation?: string };
type Feature = { flow_steps: FlowStep[] };
type RepositoryFile = { path: string; symbols: Array<{ id: string }> };

const stage = (name: string, details: Record<string, unknown> = {}) => {
  console.log(`[real-ts-crossfile] ${name} ${JSON.stringify(details)}`);
};

test('real multi-file TypeScript repository preserves a resolved cross-file execution flow', async ({ request }) => {
  test.setTimeout(180_000);
  const baseUrl = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080';

  stage('submit:start');
  const submitted = await request.post(`${baseUrl}/v1/analyses`, {
    data: { repository_url: 'https://github.com/jonaskello/tsconfig-paths' },
  });
  expect(submitted.ok(), `analysis submission failed: HTTP ${submitted.status()}`).toBeTruthy();
  const { id } = (await submitted.json()) as { id: string };
  stage('submit:accepted', { id });

  let state = 'QUEUED';
  const deadline = Date.now() + 150_000;
  while (Date.now() < deadline) {
    const response = await request.get(`${baseUrl}/v1/analyses/${id}`);
    expect(response.ok(), `analysis status failed: HTTP ${response.status()}`).toBeTruthy();
    state = ((await response.json()) as { state: string }).state;
    if (state === 'READY' || state.startsWith('FAILED_')) break;
    await new Promise(resolve => setTimeout(resolve, 1_000));
  }
  stage('analysis:terminal', { id, state });
  expect(state, `analysis ${id} did not reach READY; terminal/last state=${state}`).toBe('READY');

  const filesResponse = await request.get(`${baseUrl}/v1/analyses/${id}/files`);
  const featuresResponse = await request.get(`${baseUrl}/v1/analyses/${id}/features`);
  const cardsResponse = await request.get(`${baseUrl}/v1/analyses/${id}/cards`);
  expect(filesResponse.ok(), `files endpoint failed: HTTP ${filesResponse.status()}`).toBeTruthy();
  expect(featuresResponse.ok(), `features endpoint failed: HTTP ${featuresResponse.status()}`).toBeTruthy();
  expect(cardsResponse.ok(), `cards endpoint failed: HTTP ${cardsResponse.status()}`).toBeTruthy();

  const files = ((await filesResponse.json()) as { files: RepositoryFile[] }).files;
  const features = ((await featuresResponse.json()) as { features: Feature[] }).features;
  const cards = ((await cardsResponse.json()) as { cards: Array<{ path: string; source: string; basic_explanation: { verified: boolean } }> }).cards;

  const tsPaths = files.filter(file => file.path.endsWith('.ts')).map(file => file.path);
  stage('facts:persisted', {
    files: files.length,
    typescript_files: tsPaths.length,
    has_barrel: tsPaths.includes('src/index.ts'),
    features: features.length,
    cards: cards.length,
  });

  // This upstream repository is intentionally multi-file and exposes a barrel at src/index.ts.
  // Keeping that file in the analyzed fact set prevents the TypeScript acceptance path from
  // silently regressing to the previous single-file smoke test.
  expect(tsPaths, `src/index.ts missing; persisted TypeScript paths=${JSON.stringify(tsPaths)}`).toContain('src/index.ts');
  expect(tsPaths.length, `expected >5 TypeScript files; paths=${JSON.stringify(tsPaths)}`).toBeGreaterThan(5);

  const symbolPath = new Map<string, string>();
  for (const file of files) {
    for (const symbol of file.symbols) symbolPath.set(symbol.id, file.path);
  }

  const crossFileCalls = features.flatMap(feature => {
    const steps = feature.flow_steps;
    return steps.slice(1).filter((step, index) => {
      if (step.relation !== 'calls') return false;
      const previousPath = symbolPath.get(steps[index].symbol_id);
      const currentPath = symbolPath.get(step.symbol_id);
      return Boolean(previousPath && currentPath && previousPath !== currentPath);
    });
  });
  stage('flow:checked', { cross_file_calls: crossFileCalls.length });

  expect(crossFileCalls.length, 'no resolved calls edge crossed a file boundary').toBeGreaterThan(0);
  expect(cards.length, 'analysis produced no learning cards').toBeGreaterThan(0);
  const verifiedTypeScriptCards = cards.filter(
    card => card.path.endsWith('.ts') && card.source.length > 0 && card.basic_explanation.verified,
  );
  stage('cards:checked', { verified_typescript_cards: verifiedTypeScriptCards.length });
  expect(verifiedTypeScriptCards.length, 'no verified TypeScript Basic card with source evidence was produced').toBeGreaterThan(0);
});
