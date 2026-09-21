export type AnalysisState = { id: string; state: string; repository?: string; commit_sha?: string; error?: string };
export type SourceRange = {start?: {line?: number}; end?: {line?: number}};
export type UnresolvedCallEvidence = { callee?:string; callee_kind?:string; receiver?:string; member_name?:string; dispatch?:'dynamic'|'unknown'|string; range?:SourceRange };
export type FlowStep = { order: number; symbol_id: string; symbol_name?: string; relation?: string; unresolved_calls?:UnresolvedCallEvidence[] };
export type Feature = { id: string; name: string; entry_symbol_id?: string; flow_steps: FlowStep[] };
export type FileSymbol = { id: string; name: string; kind?: string; range?: SourceRange };
export type RepositoryFile = { path: string; symbols: FileSymbol[] };
export type ConceptEvidence = { id:string; symbol_id:string; symbol_name:string; path?:string; range?: SourceRange; relation?:string; order:number };
export type TeachingClaim = { text:string; evidence_ids:string[] };
export type BasicExplanation = { level:'basic'; claims:TeachingClaim[]; verified:true };
export type TeachingLevel = 'intermediate'|'advanced'|'deep';
export type VerifiedTeaching = { level:TeachingLevel; claims:TeachingClaim[]; verified:true };
export type ConceptCandidate = { id:string; name:string; kind:'execution_flow'; feature_id:string; evidence:ConceptEvidence[]; explanation:BasicExplanation };
export type CardEvidence = {id:string;type:'SOURCE_RANGE';path:string;range:{start:{line:number};end:{line:number}}};
export type LearningCard = { id:string; analysis_id:string; path:string; symbol_id:string; symbol_name:string; range:{start:{line:number};end:{line:number}}; segment:{index:number;count:number;previous_card_id?:string|null;next_card_id?:string|null}; source:string; basic_explanation:BasicExplanation; evidence:CardEvidence[] };
export type AuthUser = { id:number; login:string; avatar_url?:string|null };
export type AuthSession = { authenticated:boolean; login_available:boolean; user?:AuthUser };
export type Mastery = 'unknown'|'learning'|'understood';
export type LearningState = { github_user_id:number; repository:string; concept_id:string; mastery:Mastery; review_due_at?:string|null; updated_at:string };

const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, {...init, credentials:'include'});
  if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`);
  return response.json() as Promise<T>;
}
export function submitRepository(repository_url: string) {
  return json<{id:string;state:string}>('/v1/analyses', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({repository_url})});
}
export function getAnalysis(id: string) { return json<AnalysisState>(`/v1/analyses/${id}`); }
export function getFeatures(id: string) { return json<{analysis_id:string;features:Feature[]}>(`/v1/analyses/${id}/features`); }
export function getFiles(id: string) { return json<{analysis_id:string;files:RepositoryFile[]}>(`/v1/analyses/${id}/files`); }
export function getConcepts(id: string) { return json<{analysis_id:string;concepts:ConceptCandidate[]}>(`/v1/analyses/${id}/concepts`); }
export function getCards(id: string) { return json<{analysis_id:string;cards:LearningCard[]}>(`/v1/analyses/${id}/cards`); }
export function getCardTeaching(cardId:string, level:TeachingLevel) { return json<VerifiedTeaching>(`/v1/cards/${encodeURIComponent(cardId)}/teaching?level=${level}`); }
export function getAuthSession() { return json<AuthSession>('/v1/auth/session'); }
export function getLearningStates(analysisId:string) { return json<{analysis_id:string;states:LearningState[]}>(`/v1/learning/analyses/${encodeURIComponent(analysisId)}/concepts`); }
export function updateLearningState(analysisId:string, conceptId:string, mastery:Mastery, review_due_at?:string|null) {
  return json<LearningState>(`/v1/learning/analyses/${encodeURIComponent(analysisId)}/concepts/${encodeURIComponent(conceptId)}`, {method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({mastery,review_due_at:review_due_at??null})});
}
export function githubLoginUrl() { return `${base}/v1/auth/github/login`; }
export async function logout() {
  const response=await fetch(`${base}/v1/auth/logout`,{method:'POST',credentials:'include',redirect:'follow'});
  if(!response.ok)throw new Error((await response.text())||`HTTP ${response.status}`);
}