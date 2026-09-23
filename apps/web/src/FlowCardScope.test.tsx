import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import FlowCardScope from './FlowCardScope';
import type { LearningCard } from './api';

function card(id: string, symbolId: string): LearningCard {
  return {
    id,
    analysis_id: 'analysis:test',
    symbol_id: symbolId,
    symbol_name: id,
    path: 'src/app.ts',
    range: { start: { line: 1 }, end: { line: 2 } },
    source: 'function x() {}',
    segment: { index: 0, count: 1 },
    evidence: [],
    basic_explanation: { level: 'basic', verified: true, claims: [] },
  };
}

function renderScope(cards: LearningCard[], selectedSymbolId: string) {
  return renderToStaticMarkup(
    <FlowCardScope cards={cards} selectedSymbolId={selectedSymbolId}>
      {visible => <>{visible.map(item => <span key={item.id}>{item.id}</span>)}</>}
    </FlowCardScope>,
  );
}

describe('FlowCardScope', () => {
  it('renders only cards with the exact analyzer symbol id', () => {
    const html = renderScope(
      [card('checkout-card', 'symbol:checkout'), card('search-card', 'symbol:search')],
      'symbol:checkout',
    );
    expect(html).toContain('checkout-card');
    expect(html).not.toContain('search-card');
    expect(html).toContain('data-flow-scoped="true"');
    expect(html).toContain('1 function card follow');
  });

  it('fails open to verified cards when there is no exact symbol match', () => {
    const html = renderScope(
      [card('checkout-card', 'symbol:checkout'), card('search-card', 'symbol:search')],
      'symbol:missing',
    );
    expect(html).toContain('checkout-card');
    expect(html).toContain('search-card');
    expect(html).toContain('data-flow-scoped="false"');
    expect(html).toContain('No exact function card matches');
  });
});
