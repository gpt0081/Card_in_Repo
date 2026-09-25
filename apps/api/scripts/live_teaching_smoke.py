from __future__ import annotations

import os

from card_in_repo_api.teaching import verify_on_demand_card_explanation
from card_in_repo_api.teaching_provider import JsonHttpTeachingProvider


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def main() -> None:
    card = {
        "id": "live-smoke:card",
        "symbol_name": "normalize_repository",
        "path": "repository.py",
        "range": {"start": {"line": 10}, "end": {"line": 12}},
        "source": "def normalize_repository(name):\n    return name.strip().lower()",
        "segment": {"index": 0, "count": 1},
        "evidence": [
            {
                "id": "live-smoke:evidence:1",
                "type": "SOURCE_RANGE",
                "path": "repository.py",
                "range": {"start": {"line": 10}, "end": {"line": 12}},
            }
        ],
    }
    level = os.environ.get("TEACHING_SMOKE_LEVEL", "intermediate").strip().lower()
    if level not in {"intermediate", "advanced", "deep"}:
        raise SystemExit("TEACHING_SMOKE_LEVEL must be intermediate, advanced, or deep")

    provider = JsonHttpTeachingProvider(
        endpoint=require("TEACHING_LLM_ENDPOINT"),
        model=require("TEACHING_LLM_MODEL"),
        api_key=require("TEACHING_LLM_API_KEY"),
    )
    explanation = provider.explain_card(card, level)
    verified = verify_on_demand_card_explanation(card, explanation, level)
    claims = verified.get("claims", [])
    if not verified.get("verified") or not claims:
        raise SystemExit("provider response did not survive evidence verification")
    print(f"live teaching smoke passed: level={level}, verified_claims={len(claims)}")


if __name__ == "__main__":
    main()
