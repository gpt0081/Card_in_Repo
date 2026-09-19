from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .auth import AuthSettings, verify_payload
from .store import AnalysisStore


class LearningStateUpdate(BaseModel):
    mastery: str
    review_due_at: str | None = None


def _github_user_id(request: Request, settings: AuthSettings | None) -> int:
    if settings is None:
        raise HTTPException(status_code=401, detail="GitHub authentication required")
    token = request.cookies.get("card_in_repo_session")
    if not token:
        raise HTTPException(status_code=401, detail="GitHub authentication required")
    try:
        payload = verify_payload(token, settings.session_secret, max_age=60 * 60 * 24 * 30)
        return int(payload["github_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="GitHub authentication required") from exc


def create_learning_router(settings: AuthSettings | None, store: AnalysisStore) -> APIRouter:
    router = APIRouter(prefix="/v1/learning", tags=["learning"])

    @router.get("/analyses/{analysis_id}/concepts")
    def list_concept_state(analysis_id: str, request: Request) -> dict[str, Any]:
        github_user_id = _github_user_id(request, settings)
        analysis = store.get_analysis(analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="analysis not found")
        repository = str(analysis.get("repository") or "")
        return {"analysis_id": analysis_id, "states": store.get_learning_state(github_user_id, repository)}

    @router.put("/analyses/{analysis_id}/concepts/{concept_id}")
    def update_concept_state(analysis_id: str, concept_id: str, update: LearningStateUpdate, request: Request) -> dict[str, Any]:
        github_user_id = _github_user_id(request, settings)
        analysis = store.get_analysis(analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="analysis not found")
        repository = str(analysis.get("repository") or "")
        try:
            return store.put_learning_state(github_user_id, repository, concept_id, update.mastery, update.review_due_at)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="mastery must be unknown, learning, or understood") from exc

    return router
