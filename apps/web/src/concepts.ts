import type { Feature, RepositoryFile } from './api';

export type ConceptEvidence = { symbol_id:string; symbol_name:string; path?:string; relation?:string; order:number };
export type ConceptCandidate = { id:string; name:string; kind:'execution_flow'; feature_id:string; evidence:ConceptEvidence[] };

export function buildConceptCandidates(features: Feature[], files: RepositoryFile[]): ConceptCandidate[] {
  const paths = new Map(files.flatMap(file => file.symbols.map(symbol => [symbol.id, file.path] as const)));
  return features.flatMap(feature => {
    const evidence = feature.flow_steps.map((step,index) => ({
      symbol_id: step.symbol_id,
      symbol_name: step.symbol_name ?? step.symbol_id,
      path: paths.get(step.symbol_id),
      relation: step.relation,
      order: step.order ?? index + 1,
    }));
    if (!evidence.length) return [];
    return [{id:`concept:flow:${feature.id}`,name:feature.name,kind:'execution_flow' as const,feature_id:feature.id,evidence}];
  });
}
