import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import FlowContext, { conceptsForSymbol } from './FlowContext';
import { ConceptCandidate } from './api';

const concepts: ConceptCandidate[] = [
  { id:'concept:checkout', name:'Checkout flow', kind:'execution_flow', feature_id:'feature:checkout', evidence:[{ id:'evidence:checkout', symbol_id:'symbol:checkout', symbol_name:'checkout', path:'src/checkout.ts', order:0 }], explanation:{ level:'basic', verified:true, claims:[{ text:'Checkout starts here.', evidence_ids:['evidence:checkout'] }] } },
  { id:'concept:receipt', name:'Receipt flow', kind:'execution_flow', feature_id:'feature:receipt', evidence:[{ id:'evidence:receipt', symbol_id:'symbol:receipt', symbol_name:'receipt', path:'src/receipt.ts', order:0 }], explanation:{ level:'basic', verified:true, claims:[{ text:'Receipt starts here.', evidence_ids:['evidence:receipt'] }] } },
];

describe('FlowContext', () => {
  it('matches concepts only through static-analysis symbol evidence', () => {
    expect(conceptsForSymbol(concepts, 'symbol:checkout').map(concept => concept.id)).toEqual(['concept:checkout']);
    expect(conceptsForSymbol(concepts, 'symbol:missing')).toEqual([]);
  });

  it('renders selected symbol context without inventing a concept match', () => {
    const html = renderToStaticMarkup(<FlowContext concepts={concepts} symbolId="symbol:missing" onReturnToCode={() => undefined}/>);
    expect(html).toContain('data-symbol-id="symbol:missing"');
    expect(html).toContain('No evidence-backed concept references this symbol yet.');
    expect(html).toContain('Return to selected code');
  });
});
