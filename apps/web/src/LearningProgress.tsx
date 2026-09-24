import { useEffect, useMemo, useState } from 'react';
import { ConceptCandidate, LearningState, Mastery, NextConceptRecommendation, getAuthSession, getLearningStates, getNextConcept, updateLearningState } from './api';

type Props = { analysisId: string; concepts: ConceptCandidate[] };
type StateByConcept = Record<string, LearningState>;

const reasonLabel:Record<NextConceptRecommendation['reason'],string>={
  review_due:'Review due',
  structurally_related_to_learning:'Related to what you are learning',
  execution_flow:'Next in execution flow',
};

export default function LearningProgress({analysisId, concepts}: Props) {
  const [authenticated,setAuthenticated]=useState(false);
  const [states,setStates]=useState<StateByConcept>({});
  const [recommendation,setRecommendation]=useState<NextConceptRecommendation|null>();
  const [busy,setBusy]=useState<string>();
  const [error,setError]=useState<string>();
  const conceptIds=useMemo(()=>new Set(concepts.map(concept=>concept.id)),[concepts]);

  async function refreshRecommendation() {
    const result=await getNextConcept(analysisId);
    setRecommendation(result.recommendation);
  }

  useEffect(()=>{
    let active=true;
    setStates({}); setRecommendation(undefined); setError(undefined);
    getAuthSession().then(async session=>{
      if(!active)return;
      setAuthenticated(session.authenticated);
      if(!session.authenticated)return;
      const [stateResult,nextResult]=await Promise.all([getLearningStates(analysisId),getNextConcept(analysisId)]);
      if(!active)return;
      setStates(Object.fromEntries(stateResult.states.filter(state=>conceptIds.has(state.concept_id)).map(state=>[state.concept_id,state])));
      setRecommendation(nextResult.recommendation);
    }).catch(err=>{if(active)setError(err instanceof Error?err.message:String(err))});
    return()=>{active=false};
  },[analysisId,conceptIds]);

  async function setMastery(conceptId:string, mastery:Mastery) {
    if(!authenticated||busy)return;
    setBusy(conceptId); setError(undefined);
    try {
      const saved=await updateLearningState(analysisId,conceptId,mastery);
      setStates(current=>({...current,[conceptId]:saved}));
      await refreshRecommendation();
    } catch(err) {
      setError(err instanceof Error?err.message:String(err));
    } finally { setBusy(undefined); }
  }

  function focusRecommendation() {
    if(!recommendation)return;
    document.querySelector<HTMLElement>(`[data-concept-id="${CSS.escape(recommendation.concept.id)}"]`)?.scrollIntoView({behavior:'smooth',block:'center'});
  }

  if(!authenticated)return <p className="learningHint">Sign in with GitHub to save learning progress and get a next-concept recommendation.</p>;
  return <section className="learningProgress" aria-label="Concept learning progress">
    <h3>Learning progress</h3>
    {recommendation?<aside className="nextConcept" aria-label="Recommended next concept">
      <strong>Next · {recommendation.concept.name}</strong>
      <small>{reasonLabel[recommendation.reason]}{recommendation.distance!=null?` · distance ${recommendation.distance.toFixed(3)}`:''}</small>
      <button type="button" onClick={focusRecommendation}>Go to concept</button>
    </aside>:recommendation===null?<p className="learningHint">All discovered concepts are understood.</p>:null}
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
