from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from card_in_repo_analyzer import analyze_python, build_feature_map, split_python_symbol
from .jobs import AnalysisJob, AnalysisJobQueue
from .runtime import build_analysis_queue, build_analysis_store
from .store import AnalysisStore

app = FastAPI(title="Card in Repo API", version="0.1.0")
_STORE: AnalysisStore = build_analysis_store()
_QUEUE: AnalysisJobQueue = build_analysis_queue()


def set_store(store: AnalysisStore) -> None:
    global _STORE
    _STORE = store


def set_queue(queue: AnalysisJobQueue) -> None:
    global _QUEUE
    _QUEUE = queue


class FixtureAnalysisRequest(BaseModel):
    repository: str = "fixture/card-in-repo"
    commit_sha: str
    path: str
    source: str
    language: str = "python"


class GitHubAnalysisRequest(BaseModel):
    repository_url: str
    ref: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def store_completed_analysis(repository: str, commit_sha: str, files: dict[str, str], facts: dict[str, Any], analysis_id: str | None = None) -> dict[str, Any]:
    features = build_feature_map(facts)
    analysis_id = analysis_id or str(uuid4())
    cards: list[dict[str, Any]] = []
    symbols = {symbol["id"]: symbol for symbol in facts["symbols"]}
    symbol_paths = facts.get("symbol_paths", {symbol_id: next(iter(files)) for symbol_id in symbols})
    for feature in features:
        for step in feature["flow_steps"]:
            symbol = symbols[step["symbol_id"]]
            path = symbol_paths[symbol["id"]]
            source = files[path]
            segments = split_python_symbol(source, symbol)
            symbol_cards: list[dict[str, Any]] = []
            for segment_index, segment in enumerate(segments):
                start, end = segment["start_line"], segment["end_line"]
                excerpt = "\n".join(source.splitlines()[start - 1:end])
                evidence_id = f"evidence:{sha256((commit_sha + path + str(start) + str(end)).encode()).hexdigest()[:16]}"
                card_id = f"card:{sha256((analysis_id + symbol['id'] + str(segment_index)).encode()).hexdigest()[:16]}"
                card_range = {"start": {"line": start}, "end": {"line": end}}
                card = {"id": card_id, "analysis_id": analysis_id, "repository": repository, "commit_sha": commit_sha, "path": path, "symbol_id": symbol["id"], "symbol_name": symbol["name"], "range": card_range, "parent_symbol_range": symbol["range"], "segment": {"index": segment_index, "count": len(segments), "previous_card_id": None, "next_card_id": None}, "source": excerpt, "basic_explanation": {"status": "STUB_VERIFIED", "summary": f"This card covers {symbol['name']} segment {segment_index + 1} of {len(segments)}.", "evidence_ids": [evidence_id]}, "evidence": [{"id": evidence_id, "type": "SOURCE_RANGE", "path": path, "range": card_range}]}
                if symbol_cards:
                    previous = symbol_cards[-1]
                    card["segment"]["previous_card_id"] = previous["id"]
                    previous["segment"]["next_card_id"] = card_id
                symbol_cards.append(card)
            cards.extend(symbol_cards)
    previous = _STORE.get_analysis(analysis_id) or {}
    previous.pop("error", None)
    analysis = {**previous, "id": analysis_id, "state": "READY", "repository": repository, "commit_sha": commit_sha, "facts": facts, "features": features, "card_ids": [card["id"] for card in cards]}
    _STORE.put_completed_analysis(analysis, cards)
    return {"id": analysis_id, "state": "READY", "card_ids": analysis["card_ids"]}


def _persist_job(analysis: dict[str, Any], job: AnalysisJob, expected_state: str | None = None) -> bool:
    durable = getattr(_STORE, "put_analysis_with_job", None)
    if durable is not None:
        return durable(analysis, {"analysis_id": job.analysis_id, "repository_url": job.repository_url, "ref": job.ref}, expected_state=expected_state)
    if expected_state is None:
        _STORE.put_analysis(analysis)
    elif not _STORE.transition_analysis(analysis["id"], expected_state, analysis):
        return False
    try:
        _QUEUE.enqueue(job)
    except Exception:
        if expected_state is not None:
            return False
        raise
    return True


def _analyze_source(repository: str, commit_sha: str, path: str, source: str) -> dict[str, Any]:
    if not path.endswith(".py"):
        raise HTTPException(status_code=422, detail="fixture slice supports Python files only")
    return store_completed_analysis(repository, commit_sha, {path: source}, analyze_python(path, source))


@app.post("/v1/fixture-analyses", status_code=201)
def create_fixture_analysis(request: FixtureAnalysisRequest) -> dict[str, Any]:
    if request.language != "python":
        raise HTTPException(status_code=422, detail="fixture slice supports python only")
    return _analyze_source(request.repository, request.commit_sha, request.path, request.source)


@app.post("/v1/analyses", status_code=202)
def create_github_analysis(request: GitHubAnalysisRequest) -> dict[str, Any]:
    analysis_id = str(uuid4())
    queued = {"id": analysis_id, "state": "QUEUED", "repository": request.repository_url, "source_repository_url": request.repository_url, "source_ref": request.ref, "commit_sha": None, "facts": {}, "features": [], "card_ids": [], "retry_count": 0}
    job = AnalysisJob(analysis_id, request.repository_url, request.ref)
    try:
        if not _persist_job(queued, job):
            raise RuntimeError("analysis id collision")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="analysis submission unavailable") from exc
    return {"id": analysis_id, "state": "QUEUED"}


@app.post("/v1/analyses/{analysis_id}/requeue", status_code=202)
def requeue_exhausted_analysis(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    if analysis.get("state") == "QUEUED" and analysis.get("requeued"):
        return {"id": analysis_id, "state": "QUEUED"}
    if analysis.get("state") != "FAILED_EXHAUSTED":
        raise HTTPException(status_code=409, detail="only exhausted analyses can be requeued")
    repository_url = analysis.get("source_repository_url")
    if not repository_url:
        raise HTTPException(status_code=409, detail="analysis predates requeue source metadata")
    queued = {**analysis, "state": "QUEUED", "retry_count": 0, "requeued": True}
    queued.pop("error", None)
    job = AnalysisJob(analysis_id, repository_url, analysis.get("source_ref"))
    if not _persist_job(queued, job, expected_state="FAILED_EXHAUSTED"):
        current = _STORE.get_analysis(analysis_id)
        if current and current.get("state") == "QUEUED" and current.get("requeued"):
            return {"id": analysis_id, "state": "QUEUED"}
        raise HTTPException(status_code=409, detail="analysis state changed during requeue")
    return {"id": analysis_id, "state": "QUEUED"}


@app.get("/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {key: analysis.get(key) for key in ("id", "state", "repository", "commit_sha", "retry_count", "error") if key in analysis}


@app.get("/v1/analyses/{analysis_id}/features")
def get_features(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {"analysis_id": analysis_id, "features": analysis.get("features", [])}


@app.get("/v1/cards/{card_id}")
def get_card(card_id: str) -> dict[str, Any]:
    card = _STORE.get_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    return card
