from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .concept_index import ConceptIndex
from .concepts import build_concept_candidates
from .store import AnalysisStore


def create_retrieval_router(store: AnalysisStore, index: ConceptIndex | None) -> APIRouter:
    router = APIRouter(prefix="/v1/retrieval", tags=["retrieval"])

    @router.get("/analyses/{analysis_id}/concepts/{concept_id}/similar")
    def similar_concepts(analysis_id: str, concept_id: str, limit: int = Query(5, ge=1, le=20)) -> dict:
        if index is None:
            raise HTTPException(status_code=503, detail="pgvector concept retrieval requires PostgreSQL runtime")
        analysis = store.get_analysis(analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="analysis not found")
        if analysis.get("state") != "READY":
            raise HTTPException(status_code=409, detail="concept retrieval is available only after repository map is ready")
        concepts = build_concept_candidates(analysis.get("facts") or {}, analysis.get("features") or [])
        if not any(concept["id"] == concept_id for concept in concepts):
            raise HTTPException(status_code=404, detail="concept not found in analysis fact layer")
        index.index(analysis_id, concepts)
        return {
            "analysis_id": analysis_id,
            "concept_id": concept_id,
            "signal": "static-structural-v1",
            "results": index.similar(analysis_id, concept_id, limit),
        }

    return router
