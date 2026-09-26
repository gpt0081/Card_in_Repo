from __future__ import annotations

import os

from card_in_repo_analyzer import analyze_python
from card_in_repo_api.app import set_store, set_teaching_provider, store_completed_analysis
from card_in_repo_api.runtime import build_teaching_provider
from card_in_repo_api.store import MemoryAnalysisStore
from card_in_repo_api.teaching import verify_on_demand_card_explanation
from card_in_repo_api.teaching_provider import JsonHttpTeachingProvider


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def provider_environment() -> dict[str, str]:
    """Build the same provider configuration surface used by deployed runtime."""
    values = {
        "CARD_IN_REPO_TEACHING_PROVIDER": "json_http",
        "TEACHING_LLM_ENDPOINT": require("TEACHING_LLM_ENDPOINT"),
        "TEACHING_LLM_MODEL": require("TEACHING_LLM_MODEL"),
        "TEACHING_LLM_API_KEY": require("TEACHING_LLM_API_KEY"),
    }
    for name in ("TEACHING_LLM_TIMEOUT_SECONDS", "TEACHING_LLM_MAX_RESPONSE_BYTES"):
        value = os.environ.get(name, "").strip()
        if value:
            values[name] = value
    return values


def main() -> None:
    source = "def normalize_repository(name):\n    return name.strip().lower()"
    path = "repository.py"
    level = os.environ.get("TEACHING_SMOKE_LEVEL", "basic").strip().lower()
    if level not in {"basic", "intermediate", "advanced", "deep"}:
        raise SystemExit(
            "TEACHING_SMOKE_LEVEL must be basic, intermediate, advanced, or deep"
        )

    provider = build_teaching_provider(provider_environment())
    if not isinstance(provider, JsonHttpTeachingProvider):
        raise SystemExit("live smoke did not construct the json_http teaching provider")

    # Exercise the same eager Basic boundary that production analysis uses:
    # static facts -> feature/card construction -> provider-backed Basic ->
    # evidence verification -> READY persistence. This catches integration
    # failures that a direct provider helper call cannot see.
    store = MemoryAnalysisStore()
    set_store(store)
    set_teaching_provider(provider)
    result = store_completed_analysis(
        "live-smoke/card-in-repo",
        "0123456789abcdef0123456789abcdef01234567",
        {path: source},
        analyze_python(path, source),
        analysis_id="live-smoke-analysis",
    )
    if result.get("state") != "READY" or not result.get("card_ids"):
        raise SystemExit("live smoke did not reach READY with a generated card")

    card = store.get_card(result["card_ids"][0])
    if card is None:
        raise SystemExit("live smoke READY card was not persisted")

    if level == "basic":
        verified = card.get("basic_explanation") or {}
    else:
        explanation = provider.explain_card(card, level)
        verified = verify_on_demand_card_explanation(card, explanation, level)

    claims = verified.get("claims", [])
    if not verified.get("verified") or not claims:
        raise SystemExit("provider response did not survive evidence verification")
    print(
        "live teaching smoke passed: "
        f"state={result['state']}, cards={len(result['card_ids'])}, "
        f"level={level}, verified_claims={len(claims)}"
    )


if __name__ == "__main__":
    main()
