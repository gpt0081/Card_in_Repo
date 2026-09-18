import { FormEvent, useEffect, useState } from 'react';
import { Feature, getAnalysis, getFeatures, submitRepository } from './api';
import './app.css';

const terminal = new Set(['READY','FAILED_TERMINAL','FAILED_EXHAUSTED']);
export default function App() {
  const [url,setUrl]=useState('https://github.com/octocat/Hello-World');
  const [id,setId]=useState<string>(); const [state,setState]=useState('IDLE');
  const [features,setFeatures]=useState<Feature[]>([]); const [error,setError]=useState<string>();
  async function submit(e:FormEvent){e.preventDefault();setError(undefined);setFeatures([]);try{const r=await submitRepository(url.trim());setId(r.id);setState(r.state)}catch(e){setError(e instanceof Error?e.message:String(e))}}
  useEffect(()=>{if(!id||terminal.has(state))return;const timer=setInterval(async()=>{try{const a=await getAnalysis(id);setState(a.state);if(a.state==='READY'){const map=await getFeatures(id);setFeatures(map.features)}if(a.error)setError(a.error)}catch(e){setError(e instanceof Error?e.message:String(e))}},1000);return()=>clearInterval(timer)},[id,state]);
  return <main><header><span className="eyebrow">CARD IN REPO</span><h1>Read the flow before the files.</h1><p>Paste a public GitHub repository. The first result is its feature and execution map, not a wall of code cards.</p></header>
    <form onSubmit={submit}><label htmlFor="repo">Public repository</label><div className="submitRow"><input id="repo" type="url" required value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://github.com/owner/repo"/><button disabled={state!=='IDLE'&&!terminal.has(state)}>Map repo</button></div></form>
    {state!=='IDLE'&&<section className="status" aria-live="polite"><strong>{state}</strong><span>{id}</span></section>}{error&&<p className="error">{error}</p>}
    {state==='READY'&&<section><div className="sectionTitle"><span>01</span><h2>Repository map</h2></div>{features.length===0?<p>No execution features were discovered.</p>:features.map((f,i)=><article className="feature" key={f.id}><div className="featureHead"><b>{String(i+1).padStart(2,'0')}</b><h3>{f.name}</h3></div><ol>{f.flow_steps.map((s,j)=><li key={`${s.symbol_id}-${j}`}><span>{s.symbol_name??s.symbol_id}</span>{s.relation&&<small>{s.relation}</small>}</li>)}</ol></article>)}</section>}
    <nav aria-label="Learning views"><button className="active">Feature map</button><button disabled>Files</button><button disabled>Concepts</button><button disabled>Cards</button></nav>
  </main>
}
