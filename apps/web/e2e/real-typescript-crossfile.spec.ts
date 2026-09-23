import { expect, test } from '@playwright/test';

type FlowStep = { symbol_id: string; relation?: string };
type Feature = { flow_steps: FlowStep[] };
type RepositoryFile = { path: string; symbols: Array<{ id: string }> };

test('real multi-file TypeScript repository preserves a resolved cross-file execution flow', async ({ request }) => {
  test.setTimeout(180_000);
  const baseUrl = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080';

  const submitted = await request.post(`${baseUrl}/v1/analyses`, {
    data: { repository_url: 'https://github.com/jonaskello/tsconfig-paths' },
  });
  expect(submitted.ok()).toBeTruthy();
  const { id } = (await submitted.json()) as { id: string };

  let state = 'QUEUED';
  const deadline = Date.now() + 150_000;
  while (Date.now() < deadline) {
    const response = await request.get(`${baseUrl}/v1/analyses/${id}`);
    expect(response.ok()).toBeTruthy();
    state = ((await response.json()) as { state: string }).state;
    if (state === 'READY' || state.startsWith('FAILED_')) break;
    await new Promise(resolve => setTimeout(resolve, 1_000));
  }
  expect(state).toBe('READY');

  const filesResponse = await request.get(`${baseUrl}/v1/analyses/${id}/files`);
  const featuresResponse = await request.get(`${baseUrl}/v1/analyses/${id}/features`);
  const cardsResponse = await request.get(`${baseUrl}/v1/analyses/${id}/cards`);
  expect(filesResponse.ok()).toBeTruthy();
  expect(featuresResponse.ok()).toBeTruthy();
  expect(cardsResponse.ok()).toBeTruthy();

  const files = ((await filesResponse.json()) as { files: RepositoryFile[] }).files;
  const features = ((await featuresResponse.json()) as { features: Feature[] }).features;
  const cards = ((await cardsResponse.json()) as { cards: Array<{ path: string; source: string; basic_explanation: { verified: boolean } }> }).cards;

  // This upstream repository is intentionally multi-file and exposes a barrel at src/index.ts.
  // Keeping that file in the analyzed fact set prevents the TypeScript acceptance path from
  // silently regressing to the previous single-file smoke test.
  expect(files.some(file => file.path === 'src/index.ts')).toBeTruthy();
  expect(files.filter(file => file.path.endsWith('.ts')).length).toBeGreaterThan(5);

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

  expect(crossFileCalls.length).toBeGreaterThan(0);
  expect(cards.length).toBeGreaterThan(0);
  expect(cards.some(card => card.path.endsWith('.ts') && card.source.length > 0 && card.basic_explanation.verified)).toBeTruthy();
});
