export type AnalysisState = { id: string; state: string; repository?: string; commit_sha?: string; error?: string };
export type FlowStep = { order: number; symbol_id: string; symbol_name?: string; relation?: string };
export type Feature = { id: string; name: string; entry_symbol_id?: string; flow_steps: FlowStep[] };

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
