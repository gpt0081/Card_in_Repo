import { useEffect, useMemo, useState } from 'react';
import { ConceptCandidate, LearningState, Mastery, getAuthSession, getLearningStates, updateLearningState } from './api';

type Props = { analysisId: string; concepts: ConceptCandidate[] };
type StateByConcept = Record<string, LearningState>;

export default function LearningProgress({analysisId, concepts}: Props) {
  const [authenticated,setAuthenticated]=useState(false);
  const [states,setStates]=useState<StateByConcept>({});
  const [busy,setBusy]=useState<string>();
  const [error,setError]=useState<string>();
  const conceptIds=useMemo(()=>new Set(concepts.map(concept=>concept.id)),[concepts]);

  useEffect(()=>{
    let active=true;
    setStates({}); setError(undefined);
    getAuthSession().then(async session=>{
      if(!active)return;
      setAuthenticated(session.authenticated);
      if(!session.authenticated)return;
      const result=await getLearningStates(analysisId);
      if(!active)return;
      setStates(Object.fromEntries(result.states.filter(state=>conceptIds.has(state.concept_id)).map(state=>[state.concept_id,state])));
    }).catch(err=>{if(active)setError(err instanceof Error?err.message:String(err))});
    return()=>{active=false};
  },[analysisId,conceptIds]);

  async function setMastery(conceptId:string, mastery:Mastery) {
    if(!authenticated||busy)return;
    setBusy(conceptId); setError(undefined);
    try {
      const saved=await updateLearningState(analysisId,conceptId,mastery);
      setStates(current=>({...current,[conceptId]:saved}));
    } catch(err) {
      setError(err instanceof Error?err.message:String(err));
    } finally { setBusy(undefined); }
  }

  if(!authenticated)return <p className="learningHint">Sign in with GitHub to save learning progress.</p>;
  return <section className="learningProgress" aria-label="Concept learning progress">
    <h3>Learning progress</h3>
    {concepts.map(concept=>{const mastery=states[concept.id]?.mastery??'unknown';return <div className="learningRow" key={concept.id} data-concept-id={concept.id}>
      <span>{concept.name}</span><small>{mastery}</small>
      <div className="learningActions">
        <button type="button" aria-pressed={mastery==='learning'} disabled={busy===concept.id} onClick={()=>setMastery(concept.id,'learning')}>Learning</button>
        <button type="button" aria-pressed={mastery==='understood'} disabled={busy===concept.id} onClick={()=>setMastery(concept.id,'understood')}>Understood</button>
      </div>
    </div>})}
    {error&&<p className="learningError" role="status">Learning progress unavailable: {error}</p>}
  </section>;
}
