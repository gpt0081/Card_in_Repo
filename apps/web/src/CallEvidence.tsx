import { UnresolvedCallEvidence } from './api';

export default function CallEvidence({calls}:{calls?:UnresolvedCallEvidence[]}) {
  if (!calls?.length) return null;
  return <ul className="callEvidence" aria-label="Observed unresolved calls">{calls.map((call,index)=>{
    const label=call.callee??[call.receiver,call.member_name].filter(Boolean).join('.')??'unknown call';
    const certainty=call.dispatch==='dynamic'?'dynamic dispatch':'target unknown';
    const line=call.range?.start?.line;
    return <li key={`${label}-${line??'line'}-${index}`} data-dispatch={call.dispatch??'unknown'}>
      <code>{label}</code><small>{certainty}{line?` · L${line}`:''}</small>
    </li>;
  })}</ul>;
}
