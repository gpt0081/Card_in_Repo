import { ConceptCandidate } from './api';

export function conceptsForSymbol(concepts: ConceptCandidate[], symbolId?: string) {
  if (!symbolId) return [];
  return concepts.filter(concept => concept.evidence.some(evidence => evidence.symbol_id === symbolId));
}

export default function FlowContext({ concepts, symbolId, onReturnToCode }: { concepts: ConceptCandidate[]; symbolId?: string; onReturnToCode: () => void }) {
  if (!symbolId) return null;
  const related = conceptsForSymbol(concepts, symbolId);
  return <aside className="flowContext" aria-label="Selected execution context" data-symbol-id={symbolId}>
    <strong>Following selected code</strong>
    <p>{related.length ? `${related.length} evidence-backed concept${related.length === 1 ? '' : 's'} ${related.length === 1 ? 'references' : 'reference'} this symbol.` : 'No evidence-backed concept references this symbol yet.'}</p>
    <button type="button" onClick={onReturnToCode}>Return to selected code</button>
  </aside>;
}
