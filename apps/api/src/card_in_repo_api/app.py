from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from card_in_repo_analyzer import analyze_python, analyze_python_repository, build_feature_map, split_python_symbol
from .github_source import GitHubSourceError, resolve_github_repository
from .runtime import build_analysis_store
from .store import AnalysisStore

app = FastAPI(title="Card in Repo API", version="0.1.0")
_STORE: AnalysisStore = build_analysis_store()


def set_store(store: AnalysisStore) -> None:
    """Override the store at the application composition boundary, primarily for tests."""
    global _STORE
    _STORE = store


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


def _store_analysis(repository: str, commit_sha: str, files: dict[str, str], facts: dict[str, Any]) -> dict[str, Any]:
    features = build_feature_map(facts)
    analysis_id = str(uuid4())
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
                start = segment["start_line"]
                end = segment["end_line"]
                excerpt = "\n".join(source.splitlines()[start - 1 : end])
                evidence_id = f"evidence:{sha256((commit_sha + path + str(start) + str(end)).encode()).hexdigest()[:16]}"
                card_id = f"card:{sha256((analysis_id + symbol['id'] + str(segment_index)).encode()).hexdigest()[:16]}"
                card_range = {"start": {"line": start}, "end": {"line": end}}
                card = {
                    "id": card_id,
                    "analysis_id": analysis_id,
                    "repository": repository,
                    "commit_sha": commit_sha,
                    "path": path,
                    "symbol_id": symbol["id"],
                    "symbol_name": symbol["name"],
                    "range": card_range,
                    "parent_symbol_range": symbol["range"],
                    "segment": {"index": segment_index, "count": len(segments), "previous_card_id": None, "next_card_id": None},
                    "source": excerpt,
                    "basic_explanation": {
                        "status": "STUB_VERIFIED",
                        "summary": f"This card covers {symbol['name']} segment {segment_index + 1} of {len(segments)}.",
                        "evidence_ids": [evidence_id],
                    },
                    "evidence": [{"id": evidence_id, "type": "SOURCE_RANGE", "path": path, "range": card_range}],
                }
                if symbol_cards:
                    previous = symbol_cards[-1]
                    card["segment"]["previous_card_id"] = previous["id"]
                    previous["segment"]["next_card_id"] = card_id
                symbol_cards.append(card)
            cards.extend(symbol_cards)

    analysis = {
        "id": analysis_id,
        "state": "READY",
        "repository": repository,
        "commit_sha": commit_sha,
        "facts": facts,
        "features": features,
        "card_ids": [card["id"] for card in cards],
    }
    _STORE.put_analysis(analysis)
    for card in cards:
        _STORE.put_card(card)
    return {"id": analysis_id, "state": "READY", "card_ids": analysis["card_ids"]}


def _analyze_source(repository: str, commit_sha: str, path: str, source: str) -> dict[str, Any]:
    if not path.endswith(".py"):
        raise HTTPException(status_code=422, detail="fixture slice supports Python files only")
    return _store_analysis(repository, commit_sha, {path: source}, analyze_python(path, source))


@app.post("/v1/fixture-analyses", status_code=201)
def create_fixture_analysis(request: FixtureAnalysisRequest) -> dict[str, Any]:
    if request.language != "python":
        raise HTTPException(status_code=422, detail="fixture slice supports python only")
    return _analyze_source(request.repository, request.commit_sha, request.path, request.source)


@app.post("/v1/analyses", status_code=201)
def create_github_analysis(request: GitHubAnalysisRequest) -> dict[str, Any]:
    try:
        snapshot = resolve_github_repository(request.repository_url, request.ref)
    except GitHubSourceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    facts = analyze_python_repository(snapshot.files)
    result = _store_analysis(snapshot.repository, snapshot.commit_sha, snapshot.files, facts)
    return {**result, "repository": snapshot.repository, "commit_sha": snapshot.commit_sha, "file_count": len(snapshot.files)}


@app.get("/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {key: analysis[key] for key in ("id", "state", "repository", "commit_sha")}


@app.get("/v1/analyses/{analysis_id}/features")
def get_features(analysis_id: str) -> dict[str, Any]:
    analysis = _STORE.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {"analysis_id": analysis_id, "features": analysis["features"]}


@app.get("/v1/cards/{card_id}")
def get_card(card_id: str) -> dict[str, Any]:
    card = _STORE.get_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    return card
