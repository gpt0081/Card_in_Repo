import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import FlowCardScope from './FlowCardScope';
import { LearningCard } from './api';

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

describe('FlowCardScope', () => {
  it('renders only cards with the exact analyzer symbol id', () => {
    const cards = [card('checkout-card', 'symbol:checkout'), card('search-card', 'symbol:search')];
    render(<FlowCardScope cards={cards} selectedSymbolId="symbol:checkout">{visible => <>{visible.map(item => <span key={item.id}>{item.id}</span>)}</>}</FlowCardScope>);
    expect(screen.getByText('checkout-card')).toBeInTheDocument();
    expect(screen.queryByText('search-card')).not.toBeInTheDocument();
    expect(screen.getByText(/1 function card follow/)).toHaveAttribute('data-flow-scoped', 'true');
  });

  it('fails open to verified cards when there is no exact symbol match', () => {
    const cards = [card('checkout-card', 'symbol:checkout'), card('search-card', 'symbol:search')];
    render(<FlowCardScope cards={cards} selectedSymbolId="symbol:missing">{visible => <>{visible.map(item => <span key={item.id}>{item.id}</span>)}</>}</FlowCardScope>);
    expect(screen.getByText('checkout-card')).toBeInTheDocument();
    expect(screen.getByText('search-card')).toBeInTheDocument();
    expect(screen.getByText(/No exact function card matches/)).toHaveAttribute('data-flow-scoped', 'false');
  });
});
