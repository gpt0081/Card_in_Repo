import { describe, expect, it } from 'vitest';
import { readLearningRoute } from './learningRoute';

describe('learning route', () => {
  it('restores an analysis and learning view from the query string', () => {
    expect(readLearningRoute('?analysis=analysis-123&view=concepts')).toEqual({analysisId:'analysis-123',view:'concepts'});
  });

  it('fails closed to the feature map for unknown views', () => {
    expect(readLearningRoute('?analysis=analysis-123&view=admin')).toEqual({analysisId:'analysis-123',view:'features'});
  });

  it('does not invent an analysis id', () => {
    expect(readLearningRoute('?view=cards')).toEqual({analysisId:undefined,view:'cards'});
  });
});
