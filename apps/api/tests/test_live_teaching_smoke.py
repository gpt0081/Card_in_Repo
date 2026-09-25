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


def test_live_smoke_defaults_to_eager_basic_path(monkeypatch):
    monkeypatch.delenv("TEACHING_SMOKE_LEVEL", raising=False)
    source = SCRIPT_PATH.read_text()

    assert 'os.environ.get("TEACHING_SMOKE_LEVEL", "basic")' in source
    assert "generate_card_basic_explanation(card, provider)" in source
    assert 'level == "basic"' in source


def test_live_smoke_workflow_defaults_to_basic():
    workflow = WORKFLOW_PATH.read_text()

    assert "default: basic" in workflow
    assert "          - basic" in workflow
    assert "TEACHING_SMOKE_LEVEL: ${{ inputs.level }}" in workflow


def test_live_smoke_keeps_deeper_levels_available():
    source = SCRIPT_PATH.read_text()

    for level in ("intermediate", "advanced", "deep"):
        assert f'"{level}"' in source
    assert "verify_on_demand_card_explanation(card, explanation, level)" in source
