import { ReactNode } from 'react';
import { LearningCard } from './api';
import { cardsForFlow } from './cardFlowContext';

type Props = {
  cards: LearningCard[];
  selectedSymbolId?: string;
  children: (cards: LearningCard[]) => ReactNode;
};

/**
 * Keep the execution-flow symbol authoritative when entering code cards.
 * Exact analyzer symbol ids scope the list; no-match falls back to all
 * verified cards rather than inventing a fuzzy association.
 */
export default function FlowCardScope({ cards, selectedSymbolId, children }: Props) {
  const result = cardsForFlow(cards, selectedSymbolId);
  return <>
    {selectedSymbolId && <p className="flowCardContext" data-flow-scoped={result.scoped}>
      {result.scoped
        ? `${result.cards.length} function card${result.cards.length === 1 ? '' : 's'} follow the selected execution symbol.`
        : 'No exact function card matches the selected execution symbol. Showing all verified cards.'}
    </p>}
    {children(result.cards)}
  </>;
}
