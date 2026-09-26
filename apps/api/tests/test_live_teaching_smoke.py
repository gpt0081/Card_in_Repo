from pathlib import Path

import pytest


API_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = API_ROOT / "scripts" / "live_teaching_smoke.py"
WORKFLOW_PATH = API_ROOT.parents[1] / ".github" / "workflows" / "live-teaching-smoke.yml"


def load_script_namespace() -> dict[str, object]:
    # Keep the operational scripts directory outside the API package/import
    # surface while still regression-testing the smoke contract itself.
    namespace = {"__name__": "live_teaching_smoke_test"}
    exec(compile(SCRIPT_PATH.read_text(), str(SCRIPT_PATH), "exec"), namespace)
    return namespace


def test_live_smoke_requires_explicit_provider_configuration(monkeypatch):
    monkeypatch.delenv("TEACHING_LLM_API_KEY", raising=False)
    namespace = load_script_namespace()

    with pytest.raises(SystemExit, match="TEACHING_LLM_API_KEY"):
        namespace["require"]("TEACHING_LLM_API_KEY")


def test_live_smoke_reads_explicit_provider_configuration(monkeypatch):
    monkeypatch.setenv("TEACHING_LLM_MODEL", "provider-model")
    namespace = load_script_namespace()
    assert namespace["require"]("TEACHING_LLM_MODEL") == "provider-model"


def test_live_smoke_forwards_optional_runtime_resource_bounds(monkeypatch):
    monkeypatch.setenv("TEACHING_LLM_ENDPOINT", "https://provider.example/v1/chat/completions")
    monkeypatch.setenv("TEACHING_LLM_MODEL", "provider-model")
    monkeypatch.setenv("TEACHING_LLM_API_KEY", "secret")
    monkeypatch.setenv("TEACHING_LLM_TIMEOUT_SECONDS", "47.5")
    monkeypatch.setenv("TEACHING_LLM_MAX_RESPONSE_BYTES", "262144")
    namespace = load_script_namespace()

    values = namespace["provider_environment"]()

    assert values["TEACHING_LLM_TIMEOUT_SECONDS"] == "47.5"
    assert values["TEACHING_LLM_MAX_RESPONSE_BYTES"] == "262144"


def test_live_smoke_omits_empty_runtime_resource_bounds(monkeypatch):
    monkeypatch.setenv("TEACHING_LLM_ENDPOINT", "https://provider.example/v1/chat/completions")
    monkeypatch.setenv("TEACHING_LLM_MODEL", "provider-model")
    monkeypatch.setenv("TEACHING_LLM_API_KEY", "secret")
    monkeypatch.setenv("TEACHING_LLM_TIMEOUT_SECONDS", "")
    monkeypatch.delenv("TEACHING_LLM_MAX_RESPONSE_BYTES", raising=False)
    namespace = load_script_namespace()

    values = namespace["provider_environment"]()

    assert "TEACHING_LLM_TIMEOUT_SECONDS" not in values
    assert "TEACHING_LLM_MAX_RESPONSE_BYTES" not in values


def test_live_smoke_defaults_to_eager_basic_ready_path(monkeypatch):
    monkeypatch.delenv("TEACHING_SMOKE_LEVEL", raising=False)
    source = SCRIPT_PATH.read_text()

    assert 'os.environ.get("TEACHING_SMOKE_LEVEL", "basic")' in source
    assert "store_completed_analysis(" in source
    assert "analyze_python(path, source)" in source
    assert 'result.get("state") != "READY"' in source
    assert 'verified = card.get("basic_explanation") or {}' in source
    assert "generate_card_basic_explanation(card, provider)" not in source


def test_live_smoke_reloads_ready_card_from_postgres():
    source = SCRIPT_PATH.read_text()

    assert 'PostgresAnalysisStore(require("DATABASE_URL"))' in source
    assert "store.initialize()" in source
    assert "MemoryAnalysisStore" not in source
    assert "persisted_store = PostgresAnalysisStore" in source
    assert "persisted_store.get_card" in source


def test_live_smoke_workflow_defaults_to_basic():
    workflow = WORKFLOW_PATH.read_text()

    assert "default: basic" in workflow
    assert "          - basic" in workflow
    assert "TEACHING_SMOKE_LEVEL: ${{ inputs.level }}" in workflow


def test_live_smoke_workflow_pins_credential_destination_to_repository_config():
    workflow = WORKFLOW_PATH.read_text()

    assert "TEACHING_LLM_ENDPOINT: ${{ vars.TEACHING_LLM_ENDPOINT }}" in workflow
    assert "TEACHING_LLM_MODEL: ${{ vars.TEACHING_LLM_MODEL }}" in workflow
    assert "TEACHING_LLM_API_KEY: ${{ secrets.TEACHING_LLM_API_KEY }}" in workflow
    assert "inputs.endpoint" not in workflow
    assert "inputs.model" not in workflow
    assert 'test -n "$TEACHING_LLM_ENDPOINT"' in workflow
    assert 'test -n "$TEACHING_LLM_MODEL"' in workflow


def test_live_smoke_workflow_uses_repository_resource_bounds():
    workflow = WORKFLOW_PATH.read_text()

    assert "TEACHING_LLM_TIMEOUT_SECONDS: ${{ vars.TEACHING_LLM_TIMEOUT_SECONDS }}" in workflow
    assert "TEACHING_LLM_MAX_RESPONSE_BYTES: ${{ vars.TEACHING_LLM_MAX_RESPONSE_BYTES }}" in workflow
    assert "inputs.timeout" not in workflow
    assert "inputs.max_response" not in workflow


def test_live_smoke_workflow_provides_postgres_persistence():
    workflow = WORKFLOW_PATH.read_text()

    assert "image: pgvector/pgvector:pg16" in workflow
    assert "POSTGRES_DB: card_in_repo_live_smoke" in workflow
    assert "DATABASE_URL: postgresql://card_in_repo:card_in_repo@localhost:5432/card_in_repo_live_smoke" in workflow


def test_live_smoke_deeper_levels_use_runtime_handler_and_verify_durable_cache():
    source = SCRIPT_PATH.read_text()

    for level in ("intermediate", "advanced", "deep"):
        assert f'"{level}"' in source
    assert "verified = get_card_teaching(card_id, level)" in source
    assert "cached_store = PostgresAnalysisStore" in source
    assert 'get("on_demand_teaching")' in source
    assert "cached != verified" in source
    assert "provider.explain_card(card, level)" not in source
    assert "verify_on_demand_card_explanation(card, explanation, level)" not in source
