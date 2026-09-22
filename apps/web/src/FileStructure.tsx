import { RepositoryFile } from './api';

export default function FileStructure({files,selectedSymbolId}:{files:RepositoryFile[];selectedSymbolId?:string}) {
  if(files.length===0)return <p>No analyzed source files were discovered.</p>;
  return <>
    {files.map(file=><article className="feature file" key={file.path}><div className="featureHead"><b>PY</b><h3>{file.path}</h3></div><ol>{file.symbols.map(symbol=>{
      const selected=symbol.id===selectedSymbolId;
      return <li key={symbol.id} id={`symbol-${symbol.id}`} data-selected={selected||undefined} aria-current={selected?'location':undefined}><span>{symbol.name}</span><small>{symbol.kind??'symbol'}{symbol.range?.start?.line?` · L${symbol.range.start.line}${symbol.range.end?.line?`–${symbol.range.end.line}`:''}`:''}</small></li>;
    })}</ol></article>)}
  </>;
}
