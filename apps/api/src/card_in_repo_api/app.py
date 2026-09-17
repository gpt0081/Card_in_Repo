from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from card_in_repo_analyzer import analyze_python, build_feature_map

app = FastAPI(title="Card in Repo API", version="0.1.0")

# In-memory store deliberately keeps this slice infrastructure-free. Persistence and
# background jobs replace it without changing the response contracts.
_ANALYSES: dict[str, dict[str, Any]] = {}
_CARDS: dict[str, dict[str, Any]] = {}


class FixtureAnalysisRequest(BaseModel):
    repository: str = "fixture/card-in-repo"
    commit_sha: str
    path: str
    source: str
    language: str = "python"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/fixture-analyses", status_code=201)
def create_fixture_analysis(request: FixtureAnalysisRequest) -> dict[str, Any]:
    """Exercise the deterministic vertical slice without network or an LLM.

    This endpoint is intentionally fixture-only. The production POST /v1/analyses
    will resolve GitHub refs and enqueue workers; it must not accept caller-supplied
    source as repository truth.
    """
    if request.language != "python":
        raise HTTPException(status_code=422, detail="fixture slice supports python only")

    facts = analyze_python(request.path, request.source)
    features = build_feature_map(facts)
    analysis_id = str(uuid4())
    cards: list[dict[str, Any]] = []

    for feature in features:
        for step in feature["flow_steps"]:
            symbol = next(s for s in facts["symbols"] if s["id"] == step["symbol_id"])
            start = symbol["range"]["start"]["line"]
            end = symbol["range"]["end"]["line"]
            excerpt = "\n".join(request.source.splitlines()[start - 1 : end])
            evidence_id = f"evidence:{sha256((request.commit_sha + request.path + str(start) + str(end)).encode()).hexdigest()[:16]}"
            card_id = f"card:{sha256((analysis_id + symbol['id']).encode()).hexdigest()[:16]}"
            card = {
                "id": card_id,
                "analysis_id": analysis_id,
                "repository": request.repository,
                "commit_sha": request.commit_sha,
                "path": request.path,
                "symbol_id": symbol["id"],
                "symbol_name": symbol["name"],
                "range": symbol["range"],
                "source": excerpt,
                "basic_explanation": {
                    "status": "STUB_VERIFIED",
                    "summary": f"This card covers the {symbol['name']} function.",
                    "evidence_ids": [evidence_id],
                },
                "evidence": [{
                    "id": evidence_id,
                    "type": "SOURCE_RANGE",
                    "path": request.path,
                    "range": symbol["range"],
                }],
            }
            _CARDS[card_id] = card
            cards.append(card)

    _ANALYSES[analysis_id] = {
        "id": analysis_id,
        "state": "READY",
        "repository": request.repository,
        "commit_sha": request.commit_sha,
        "facts": facts,
        "features": features,
        "card_ids": [card["id"] for card in cards],
    }
    return {"id": analysis_id, "state": "READY", "card_ids": [card["id"] for card in cards]}


@app.get("/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, Any]:
    analysis = _ANALYSES.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {key: analysis[key] for key in ("id", "state", "repository", "commit_sha")}


@app.get("/v1/analyses/{analysis_id}/features")
def get_features(analysis_id: str) -> dict[str, Any]:
    analysis = _ANALYSES.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {"analysis_id": analysis_id, "features": analysis["features"]}


@app.get("/v1/cards/{card_id}")
def get_card(card_id: str) -> dict[str, Any]:
    card = _CARDS.get(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    return card
