import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import CallEvidence from './CallEvidence';

describe('CallEvidence',()=>{
  it('distinguishes dynamic dispatch from an unknown target without claiming an edge',()=>{
    render(<CallEvidence calls={[
      {callee:'this.finish',receiver:'this',member_name:'finish',dispatch:'dynamic',range:{start:{line:12}}},
      {callee:'client.run',receiver:'client',member_name:'run',dispatch:'unknown',range:{start:{line:14}}},
    ]}/>);
    expect(screen.getByText('this.finish')).toBeInTheDocument();
    expect(screen.getByText('dynamic dispatch · L12')).toBeInTheDocument();
    expect(screen.getByText('client.run')).toBeInTheDocument();
    expect(screen.getByText('target unknown · L14')).toBeInTheDocument();
  });

  it('renders nothing when no unresolved evidence exists',()=>{
    const {container}=render(<CallEvidence/>);
    expect(container).toBeEmptyDOMElement();
  });
});
