from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "live_teaching_smoke.py"


def test_live_smoke_requires_explicit_provider_configuration(monkeypatch):
    monkeypatch.delenv("TEACHING_LLM_API_KEY", raising=False)

    # Keep the configuration guard independently testable without making the
    # operational scripts directory part of the API package/import surface.
    namespace = {"__name__": "live_teaching_smoke_test"}
    exec(compile(SCRIPT_PATH.read_text(), str(SCRIPT_PATH), "exec"), namespace)

    with pytest.raises(SystemExit, match="TEACHING_LLM_API_KEY"):
        namespace["require"]("TEACHING_LLM_API_KEY")


def test_live_smoke_reads_explicit_provider_configuration(monkeypatch):
    monkeypatch.setenv("TEACHING_LLM_MODEL", "provider-model")
    namespace = {"__name__": "live_teaching_smoke_test"}
    exec(compile(SCRIPT_PATH.read_text(), str(SCRIPT_PATH), "exec"), namespace)
    assert namespace["require"]("TEACHING_LLM_MODEL") == "provider-model"
