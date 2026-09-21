import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import RepositoryMap from './RepositoryMap';

const features = [{
  id:'feature:checkout', name:'Checkout flow', entry_symbol_id:'checkout',
  flow_steps:[
    {order:0,symbol_id:'checkout',symbol_name:'checkout',relation:'entry'},
    {order:1,symbol_id:'finish',symbol_name:'finish',relation:'calls',unresolved_calls:[
      {callee:'this.finish',callee_kind:'member',receiver:'this',member_name:'finish',dispatch:'dynamic',range:{start:{line:12},end:{line:12}}},
      {callee:'client.run',callee_kind:'member',receiver:'client',member_name:'run',dispatch:'unknown',range:{start:{line:13},end:{line:13}}}
    ]}
  ]
}];

describe('RepositoryMap',()=>{
  it('distinguishes resolved flow from steps carrying unresolved dispatch evidence',()=>{
    const html=renderToStaticMarkup(<RepositoryMap features={features}/>);
    expect(html).toContain('Checkout flow');
    expect(html).toContain('data-flow-certainty="resolved"');
    expect(html).toContain('flowStep--resolved');
    expect(html).toContain('data-flow-certainty="uncertain"');
    expect(html).toContain('flowStep--uncertain');
    expect(html).toContain('this.finish');
    expect(html).toContain('dynamic dispatch');
    expect(html).toContain('data-dispatch="dynamic"');
    expect(html).toContain('client.run');
    expect(html).toContain('target unknown');
    expect(html).toContain('data-dispatch="unknown"');
  });
});
