from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from card_in_repo_analyzer import analyze_python, build_feature_map, split_python_symbol
from .concepts import build_concept_candidates
from .jobs import AnalysisJob, AnalysisJobQueue
from .runtime import build_analysis_queue, build_analysis_store, build_teaching_provider
from .store import AnalysisStore
from .teaching import TeachingProvider, UnverifiedExplanation, build_card_basic_explanation, verify_on_demand_card_explanation
from .teaching_provider import TeachingProviderError

app = FastAPI(title="Card in Repo API", version="0.1.0")
_STORE: AnalysisStore = build_analysis_store()
_QUEUE: AnalysisJobQueue = build_analysis_queue()
_TEACHING_PROVIDER: TeachingProvider | None = build_teaching_provider()


def set_store(store: AnalysisStore) -> None:
    global _STORE
    _STORE = store


def set_queue(queue: AnalysisJobQueue) -> None:
    global _QUEUE
    _QUEUE = queue


def set_teaching_provider(provider: TeachingProvider | None) -> None:
    global _TEACHING_PROVIDER
    _TEACHING_PROVIDER = provider


class FixtureAnalysisRequest(BaseModel):
    repository: str = "fixture/card-in-repo"
    commit_sha: str
    path: str
    source: str
    language: str = "python"


class GitHubAnalysisRequest(BaseModel):
    repository: str
    ref: str = "HEAD"


class FixtureMultiFileAnalysisRequest(BaseModel):
    repository: str = "fixture/card-in-repo"
    commit_sha: str
    files: dict[str, str]


def _analysis_id(repository: str, commit_sha: str) -> str:
    digest = sha256(f"{repository}@{commit_sha}".encode()).hexdigest()[:16]
    return f"analysis:{digest}"


def _persist_analysis(
    *,
    analysis_id: str,
    repository: str,
    commit_sha: str,
    files: dict[str, str],
) -> dict[str, Any]:
    from card_in_repo_analyzer import analyze_python_files

    result = analyze_python_files(files)
    feature_map = build_feature_map(result)
    cards: list[dict[str, Any]] = []
    for symbol in result["symbols"]:
        if symbol["kind"] not in {"function", "method"}:
            continue
        source = files[symbol["path"]]
        for card in split_python_symbol(source, symbol):
            card_id = f"card:{uuid4().hex}"
            evidence = [{
                "id": f"{card_id}:source-range",
                "type": "SOURCE_RANGE",
                "path": card["path"],
                "range": card["range"],
            }]
            card_record = {"id": card_id, **card, "evidence": evidence}
            card_record["explanation"] = build_card_basic_explanation(card_record)
            cards.append(card_record)
    payload = {
        "id": analysis_id,
        "repository": repository,
        "commit_sha": commit_sha,
        "status": "READY",
        "analysis": result,
        "feature_map": feature_map,
        "files": files,
        "cards": cards,
    }
    _STORE.save_analysis(payload)
    return payload


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/fixture-analyses", status_code=201)
def create_fixture_analysis(request: FixtureAnalysisRequest) -> dict[str, Any]:
    analysis_id = _analysis_id(request.repository, request.commit_sha)
    payload = _persist_analysis(
        analysis_id=analysis_id,
        repository=request.repository,
        commit_sha=request.commit_sha,
        files={request.path: request.source},
    )
    return {"analysis_id": analysis_id, "status": payload["status"], "card_ids": [c["id"] for c in payload["cards"]]}


@app.post("/v1/fixture-multi-file-analyses", status_code=201)
def create_fixture_multi_file_analysis(request: FixtureMultiFileAnalysisRequest) -> dict[str, Any]:
    analysis_id = _analysis_id(request.repository, request.commit_sha)
    payload = _persist_analysis(
        analysis_id=analysis_id,
        repository=request.repository,
        commit_sha=request.commit_sha,
        files=request.files,
    )
    return {"analysis_id": analysis_id, "status": payload["status"], "card_ids": [c["id"] for c in payload["cards"]]}


@app.post("/v1/analyses", status_code=202)
def create_analysis(request: GitHubAnalysisRequest) -> dict[str, Any]:
    analysis_id = f"analysis:{uuid4().hex}"
    payload = {
        "id": analysis_id,
        "repository": request.repository,
        "requested_ref": request.ref,
        "status": "QUEUED",
        "cards": [],
    }
    _STORE.save_analysis(payload)
    _QUEUE.enqueue(AnalysisJob(analysis_id=analysis_id, repository=request.repository, requested_ref=request.ref))
    return {"analysis_id": analysis_id, "status": "QUEUED"}


@app.get("/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return analysis


@app.get("/v1/analyses/{analysis_id}/features")
def get_analysis_features(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    if analysis.get("status") != "READY":
        raise HTTPException(status_code=409, detail="analysis is not ready")
    return {"analysis_id": analysis_id, "features": analysis.get("feature_map", {}).get("features", [])}


@app.get("/v1/analyses/{analysis_id}/files")
def get_analysis_files(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    if analysis.get("status") != "READY":
        raise HTTPException(status_code=409, detail="analysis is not ready")
    facts = analysis.get("analysis", {})
    symbols = facts.get("symbols", [])
    paths = sorted({item.get("path") for item in symbols if item.get("path")})
    return {
        "analysis_id": analysis_id,
        "files": [
            {
                "path": path,
                "symbols": [
                    {
                        "id": symbol.get("id"),
                        "name": symbol.get("name"),
                        "kind": symbol.get("kind"),
                        "range": symbol.get("range"),
                    }
                    for symbol in symbols
                    if symbol.get("path") == path
                ],
            }
            for path in paths
        ],
    }


@app.get("/v1/analyses/{analysis_id}/concepts")
def get_analysis_concepts(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    if analysis.get("status") != "READY":
        raise HTTPException(status_code=409, detail="analysis is not ready")
    concepts = build_concept_candidates(analysis.get("analysis", {}), analysis.get("feature_map", {}))
    return {"analysis_id": analysis_id, "concepts": concepts}


@app.get("/v1/analyses/{analysis_id}/cards")
def get_analysis_cards(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    if analysis.get("status") != "READY":
        raise HTTPException(status_code=409, detail="analysis is not ready")
    cards = analysis.get("cards", [])
    return {"analysis_id": analysis_id, "cards": cards}


@app.get("/v1/cards/{card_id}/teaching")
def get_card_teaching(card_id: str, level: str = Query(...)) -> dict[str, Any]:
    if level not in {"intermediate", "advanced", "deep"}:
        raise HTTPException(status_code=422, detail="level must be intermediate, advanced, or deep")
    card = _STORE.get_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    if _TEACHING_PROVIDER is None:
        raise HTTPException(status_code=503, detail="on-demand teaching provider is not configured")
    try:
        proposed = _TEACHING_PROVIDER.explain_card(card, level)
        return verify_on_demand_card_explanation(card, proposed, level)
    except UnverifiedExplanation as exc:
        raise HTTPException(status_code=422, detail="teaching output failed evidence verification") from exc
    except TeachingProviderError as exc:
        raise HTTPException(status_code=502, detail="teaching provider failed") from exc


@app.get("/v1/cards/{card_id}")
def get_card(card_id: str) -> dict[str, Any]:
    card = _STORE.get_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    return card
