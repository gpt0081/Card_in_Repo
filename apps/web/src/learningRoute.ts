export type LearningView = 'features'|'files'|'concepts'|'cards';

const views = new Set<LearningView>(['features','files','concepts','cards']);

export type LearningRoute = { analysisId?: string; view: LearningView };

export function readLearningRoute(search: string): LearningRoute {
  const params = new URLSearchParams(search);
  const analysisId = params.get('analysis')?.trim() || undefined;
  const candidate = params.get('view') as LearningView | null;
  return { analysisId, view: candidate && views.has(candidate) ? candidate : 'features' };
}

export function writeLearningRoute(analysisId: string | undefined, view: LearningView): string {
  if (!analysisId) return window.location.pathname;
  const params = new URLSearchParams({ analysis: analysisId, view });
  return `${window.location.pathname}?${params.toString()}`;
}
