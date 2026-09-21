import { Feature } from './api';
import CallEvidence from './CallEvidence';

export default function RepositoryMap({features}:{features:Feature[]}) {
  if(features.length===0)return <p>No execution features were discovered.</p>;
  return <>{features.map((f,i)=><article className="feature" key={f.id}><div className="featureHead"><b>{String(i+1).padStart(2,'0')}</b><h3>{f.name}</h3></div><ol>{f.flow_steps.map((s,j)=><li key={`${s.symbol_id}-${j}`}><span>{s.symbol_name??s.symbol_id}</span>{s.relation&&<small>{s.relation}</small>}<CallEvidence calls={s.unresolved_calls}/></li>)}</ol></article>)}</>;
}
