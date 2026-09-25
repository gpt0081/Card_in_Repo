import pytest

from scripts.live_teaching_smoke import require


def test_live_smoke_requires_explicit_provider_configuration(monkeypatch):
    monkeypatch.delenv("TEACHING_LLM_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="TEACHING_LLM_API_KEY"):
        require("TEACHING_LLM_API_KEY")


def test_live_smoke_reads_explicit_provider_configuration(monkeypatch):
    monkeypatch.setenv("TEACHING_LLM_MODEL", "provider-model")
    assert require("TEACHING_LLM_MODEL") == "provider-model"
