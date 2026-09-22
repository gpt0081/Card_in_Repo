import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import FileStructure from './FileStructure';
import type { RepositoryFile } from './api';

const files:RepositoryFile[]=[{path:'src/checkout.py',symbols:[
  {id:'sym-open',name:'open_checkout',kind:'function',range:{start:{line:4},end:{line:9}}},
  {id:'sym-finish',name:'finish_checkout',kind:'function',range:{start:{line:12},end:{line:20}}},
]}];

describe('FileStructure',()=>{
  it('marks the execution-flow symbol as the current code location',()=>{
    const html=renderToStaticMarkup(<FileStructure files={files} selectedSymbolId="sym-finish"/>);
    expect(html).toContain('id="symbol-sym-finish"');
    expect(html).toContain('data-selected="true"');
    expect(html).toContain('aria-current="location"');
    expect(html).toContain('finish_checkout');
    expect(html).toContain('function · L12–20');
    expect(html).not.toContain('id="symbol-sym-open" data-selected="true"');
  });

  it('keeps the complete static file structure when no flow symbol is selected',()=>{
    const html=renderToStaticMarkup(<FileStructure files={files}/>);
    expect(html).toContain('open_checkout');
    expect(html).toContain('finish_checkout');
    expect(html).not.toContain('data-selected="true"');
    expect(html).not.toContain('aria-current="location"');
  });
});
