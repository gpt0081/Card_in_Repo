import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import CallEvidence from './CallEvidence';

describe('CallEvidence',()=>{
  it('distinguishes dynamic dispatch from an unknown target without claiming an edge',()=>{
    const html=renderToStaticMarkup(<CallEvidence calls={[
      {callee:'this.finish',receiver:'this',member_name:'finish',dispatch:'dynamic',range:{start:{line:12}}},
      {callee:'client.run',receiver:'client',member_name:'run',dispatch:'unknown',range:{start:{line:14}}},
    ]}/>);
    expect(html).toContain('<code>this.finish</code>');
    expect(html).toContain('dynamic dispatch · L12');
    expect(html).toContain('data-dispatch="dynamic"');
    expect(html).toContain('<code>client.run</code>');
    expect(html).toContain('target unknown · L14');
    expect(html).toContain('data-dispatch="unknown"');
  });

  it('renders nothing when no unresolved evidence exists',()=>{
    expect(renderToStaticMarkup(<CallEvidence/>)).toBe('');
  });
});
