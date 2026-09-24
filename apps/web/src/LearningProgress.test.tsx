// @vitest-environment jsdom
import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import LearningProgress from './LearningProgress';
import * as api from './api';

vi.mock('./api', async importOriginal => {
  const actual=await importOriginal<typeof import('./api')>();
  return {...actual,getAuthSession:vi.fn(),getLearningStates:vi.fn(),getNextConcept:vi.fn(),updateLearningState:vi.fn()};
});

const concept={id:'concept-1',name:'Request flow',kind:'execution_flow' as const,feature_id:'feature-1',evidence:[],explanation:{level:'basic' as const,claims:[{text:'verified',evidence_ids:['e1']}],verified:true as const}};
const next={concept,reason:'execution_flow' as const,anchor_concept_id:null,distance:null};

function saved(mastery:'unknown'|'learning'|'understood') { return {github_user_id:7,repository:'owner/repo',concept_id:'concept-1',mastery,updated_at:'2026-09-20T00:00:00Z'}; }
function signedIn(){vi.mocked(api.getAuthSession).mockResolvedValue({authenticated:true,login_available:true,user:{id:7,login:'learner'}});}

afterEach(()=>{document.body.innerHTML='';vi.clearAllMocks()});

describe('LearningProgress',()=>{
  it('keeps anonymous learning read-only',async()=>{
    vi.mocked(api.getAuthSession).mockResolvedValue({authenticated:false,login_available:true});
    const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>{root.render(<LearningProgress analysisId="analysis-1" concepts={[concept]}/>)});
    expect(host.textContent).toContain('Sign in with GitHub');
    expect(api.getLearningStates).not.toHaveBeenCalled();
    expect(api.getNextConcept).not.toHaveBeenCalled();
  });

  it('loads saved mastery and the next recommendation for the signed-in user',async()=>{
    signedIn();
    vi.mocked(api.getLearningStates).mockResolvedValue({analysis_id:'analysis-1',states:[saved('understood')]});
    vi.mocked(api.getNextConcept).mockResolvedValue({analysis_id:'analysis-1',recommendation:next});
    const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>{root.render(<LearningProgress analysisId="analysis-1" concepts={[concept]}/>)});
    expect(host.textContent).toContain('understood');
    expect(host.textContent).toContain('Next · Request flow');
    expect(host.textContent).toContain('Next in execution flow');
    expect(host.querySelector('button[aria-pressed="true"]')?.textContent).toBe('Understood');
  });

  it('refreshes recommendation after a mastery choice',async()=>{
    signedIn();
    vi.mocked(api.getLearningStates).mockResolvedValue({analysis_id:'analysis-1',states:[saved('unknown')]});
    vi.mocked(api.getNextConcept).mockResolvedValueOnce({analysis_id:'analysis-1',recommendation:next}).mockResolvedValueOnce({analysis_id:'analysis-1',recommendation:null});
    vi.mocked(api.updateLearningState).mockResolvedValue(saved('learning'));
    const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>{root.render(<LearningProgress analysisId="analysis-1" concepts={[concept]}/>)});
    const learning=[...host.querySelectorAll('button')].find(button=>button.textContent==='Learning');
    await act(async()=>{learning!.click()});
    expect(api.updateLearningState).toHaveBeenCalledWith('analysis-1','concept-1','learning');
    expect(api.getNextConcept).toHaveBeenCalledTimes(2);
    expect(host.textContent).toContain('All discovered concepts are understood.');
  });
});
