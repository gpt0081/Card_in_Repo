from __future__ import annotations

import os

from card_in_repo_analyzer import analyze_python
from card_in_repo_api.app import (
    get_card_teaching,
    set_store,
    set_teaching_provider,
    store_completed_analysis,
)
from card_in_repo_api.postgres_store import PostgresAnalysisStore
from card_in_repo_api.runtime import build_teaching_provider
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

    # Exercise the same durable store and eager Basic boundary used by the
    # deployed runtime: static facts -> feature/card construction ->
    # provider-backed Basic -> evidence verification -> PostgreSQL persistence.
    store = PostgresAnalysisStore(require("DATABASE_URL"))
    store.initialize()
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

    card_id = result["card_ids"][0]
    # Re-open the store before reading back the card so this probe proves the
    # result crossed the database boundary instead of surviving in process state.
    persisted_store = PostgresAnalysisStore(require("DATABASE_URL"))
    card = persisted_store.get_card(card_id)
    if card is None:
        raise SystemExit("live smoke READY card was not persisted to PostgreSQL")

    if level == "basic":
        verified = card.get("basic_explanation") or {}
    else:
        # Use the deployed endpoint handler rather than duplicating its provider,
        # verifier, and cache-write sequence inside the smoke script.
        verified = get_card_teaching(card_id, level)
        # Re-open once more and require the verified on-demand result to have
        # crossed PostgreSQL. This catches provider success with a broken cache
        # write, which would otherwise regenerate the same teaching every read.
        cached_store = PostgresAnalysisStore(require("DATABASE_URL"))
        cached_card = cached_store.get_card(card_id)
        cached = ((cached_card or {}).get("on_demand_teaching") or {}).get(level)
        if cached != verified:
            raise SystemExit("verified on-demand teaching was not persisted to PostgreSQL")

        # Remove the provider and read through the deployed handler again. A
        # successful second read now proves the durable cache is actually used,
        # rather than merely written while every request still calls the LLM.
        set_teaching_provider(None)
        cached_response = get_card_teaching(card_id, level)
        if cached_response != verified:
            raise SystemExit("durable on-demand teaching cache was not served consistently")

    claims = verified.get("claims", [])
    if not verified.get("verified") or not claims:
        raise SystemExit("provider response did not survive evidence verification")
    print(
        "live teaching smoke passed: "
        f"state={result['state']}, cards={len(result['card_ids'])}, "
        f"level={level}, verified_claims={len(claims)}, store=postgres"
    )


if __name__ == "__main__":
    main()
