import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import FileStructure from './FileStructure';
import type { RepositoryFile } from './api';

const files:RepositoryFile[]=[{path:'src/checkout.py',symbols:[
  {id:'sym-open',name:'open_checkout',kind:'function',range:{start:{line:4},end:{line:9}}},
  {id:'sym-finish',name:'finish_checkout',kind:'function',range:{start:{line:12},end:{line:20}}},
]}];

describe('FileStructure',()=>{
  it('marks the execution-flow symbol as the current code location',()=>{
    render(<FileStructure files={files} selectedSymbolId="sym-finish"/>);
    const selected=screen.getByText('finish_checkout').closest('li');
    const other=screen.getByText('open_checkout').closest('li');
    expect(selected).not.toBeNull();
    expect(selected?.getAttribute('id')).toBe('symbol-sym-finish');
    expect(selected?.getAttribute('data-selected')).toBe('true');
    expect(selected?.getAttribute('aria-current')).toBe('location');
    expect(other?.hasAttribute('data-selected')).toBe(false);
    expect(screen.getByText('function · L12–20')).toBeTruthy();
  });

  it('keeps the complete static file structure when no flow symbol is selected',()=>{
    render(<FileStructure files={files}/>);
    expect(screen.getByText('open_checkout')).toBeTruthy();
    expect(screen.getByText('finish_checkout')).toBeTruthy();
    expect(document.querySelector('[data-selected="true"]')).toBeNull();
  });
});
