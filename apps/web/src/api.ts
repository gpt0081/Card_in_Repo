export type AnalysisState = { id: string; state: string; repository?: string; commit_sha?: string; error?: string };
export type FlowStep = { order: number; symbol_id: string; symbol_name?: string; relation?: string };
export type Feature = { id: string; name: string; entry_symbol_id?: string; flow_steps: FlowStep[] };
export type FileSymbol = { id: string; name: string; kind?: string; range?: {start?: {line?: number}; end?: {line?: number}} };
export type RepositoryFile = { path: string; symbols: FileSymbol[] };
export type ConceptEvidence = { id:string; symbol_id:string; symbol_name:string; path?:string; range?: {start?: {line?: number}; end?: {line?: number}}; relation?:string; order:number };
export type TeachingClaim = { text:string; evidence_ids:string[] };
export type BasicExplanation = { level:'basic'; claims:TeachingClaim[]; verified:true };
export type ConceptCandidate = { id:string; name:string; kind:'execution_flow'; feature_id:string; evidence:ConceptEvidence[]; explanation:BasicExplanation };

const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, init);
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
