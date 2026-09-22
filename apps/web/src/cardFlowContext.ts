import { LearningCard } from './api';

export type FlowScopedCards = {
  cards: LearningCard[];
  scoped: boolean;
};

/**
 * Preserve execution-flow context without guessing. Cards are scoped only when
 * their analyzer-provided symbol_id exactly matches the selected flow symbol.
 * If no card matches, keep the complete card set rather than hiding learning
 * material behind a fuzzy or LLM-derived association.
 */
export function cardsForFlow(cards: LearningCard[], selectedSymbolId?: string): FlowScopedCards {
  if (!selectedSymbolId) return { cards, scoped: false };
  const matches = cards.filter(card => card.symbol_id === selectedSymbolId);
  return matches.length > 0 ? { cards: matches, scoped: true } : { cards, scoped: false };
}
