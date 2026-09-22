import { Feature, FlowStep } from './api';
import CallEvidence from './CallEvidence';

type FlowSelection = { feature: Feature; step: FlowStep };

export default function RepositoryMap({features,onSelectStep}:{features:Feature[];onSelectStep?:(selection:FlowSelection)=>void}) {
  if(features.length===0)return <p>No execution features were discovered.</p>;
  return <>
    <aside className="flowLegend" aria-label="Execution flow certainty">
      <span><i className="flowMarker flowMarker--resolved" aria-hidden="true"/>Proven static flow</span>
      <span><i className="flowMarker flowMarker--uncertain" aria-hidden="true"/>Runtime-dependent call</span>
    </aside>
    {features.map((f,i)=><article className="feature" key={f.id}><div className="featureHead"><b>{String(i+1).padStart(2,'0')}</b><h3>{f.name}</h3></div><ol>{f.flow_steps.map((s,j)=>{
      const certainty=s.unresolved_calls?.length?'uncertain':'resolved';
      return <li key={`${s.symbol_id}-${j}`} className={`flowStep flowStep--${certainty}`} data-flow-certainty={certainty}>
        <span className="flowStepLabel"><i className={`flowMarker flowMarker--${certainty}`} aria-hidden="true"/>{onSelectStep?<button type="button" className="flowStepSelect" aria-label={`Open ${s.symbol_name??s.symbol_id} in file structure`} onClick={()=>onSelectStep({feature:f,step:s})}>{s.symbol_name??s.symbol_id}</button>:s.symbol_name??s.symbol_id}</span>{s.relation&&<small>{s.relation}</small>}
        <CallEvidence calls={s.unresolved_calls}/>
      </li>;
    })}</ol></article>)}
  </>;
}
