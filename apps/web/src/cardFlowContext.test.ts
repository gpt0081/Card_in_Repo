import { describe, expect, it } from 'vitest';
import { LearningCard } from './api';
import { cardsForFlow } from './cardFlowContext';

function card(id: string, symbol_id: string): LearningCard {
  return {
    id,
    analysis_id: 'analysis-1',
    path: 'src/app.ts',
    symbol_id,
    symbol_name: symbol_id,
    range: { start: { line: 1 }, end: { line: 2 } },
    segment: { index: 0, count: 1 },
    source: 'function x() {}',
    basic_explanation: { level: 'basic', verified: true, claims: [{ text: 'fact', evidence_ids: ['source-1'] }] },
    evidence: [{ id: 'source-1', type: 'SOURCE_RANGE', path: 'src/app.ts', range: { start: { line: 1 }, end: { line: 2 } } }]
  };
}

describe('cardsForFlow', () => {
  it('keeps only cards with the exact analyzer symbol id', () => {
    const result = cardsForFlow([card('a', 'symbol:checkout'), card('b', 'symbol:checkout-helper')], 'symbol:checkout');
    expect(result.scoped).toBe(true);
    expect(result.cards.map(item => item.id)).toEqual(['a']);
  });

  it('fails open to the complete verified card set when no exact card exists', () => {
    const cards = [card('a', 'symbol:other')];
    const result = cardsForFlow(cards, 'symbol:checkout');
    expect(result.scoped).toBe(false);
    expect(result.cards).toEqual(cards);
  });

  it('does not scope cards without a selected execution symbol', () => {
    const cards = [card('a', 'symbol:checkout')];
    expect(cardsForFlow(cards)).toEqual({ cards, scoped: false });
  });
});
