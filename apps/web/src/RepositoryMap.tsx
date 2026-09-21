import { Feature } from './api';
import CallEvidence from './CallEvidence';

export default function RepositoryMap({features}:{features:Feature[]}) {
  if(features.length===0)return <p>No execution features were discovered.</p>;
  return <>
    <aside className="flowLegend" aria-label="Execution flow certainty">
      <span><i className="flowMarker flowMarker--resolved" aria-hidden="true"/>Proven static flow</span>
      <span><i className="flowMarker flowMarker--uncertain" aria-hidden="true"/>Runtime-dependent call</span>
    </aside>
    {features.map((f,i)=><article className="feature" key={f.id}><div className="featureHead"><b>{String(i+1).padStart(2,'0')}</b><h3>{f.name}</h3></div><ol>{f.flow_steps.map((s,j)=>{
      const certainty=s.unresolved_calls?.length?'uncertain':'resolved';
      return <li key={`${s.symbol_id}-${j}`} className={`flowStep flowStep--${certainty}`} data-flow-certainty={certainty}>
        <span className="flowStepLabel"><i className={`flowMarker flowMarker--${certainty}`} aria-hidden="true"}/>{s.symbol_name??s.symbol_id}</span>{s.relation&&<small>{s.relation}</small>}
        <CallEvidence calls={s.unresolved_calls}/>
      </li>;
    })}</ol></article>)}
  </>;
}
