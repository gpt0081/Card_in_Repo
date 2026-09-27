from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "live_teaching_smoke.py"


def load_script_namespace() -> dict[str, object]:
    namespace = {"__name__": "live_teaching_smoke_test"}
    exec(compile(SCRIPT_PATH.read_text(), str(SCRIPT_PATH), "exec"), namespace)
    return namespace


def test_live_smoke_forwards_private_http_teaching_opt_in(monkeypatch):
    monkeypatch.setenv(
        "TEACHING_LLM_ENDPOINT",
        "http://100.101.102.103:1234/v1/chat/completions",
    )
    monkeypatch.setenv("TEACHING_LLM_MODEL", "local-model")
    monkeypatch.setenv("TEACHING_LLM_API_KEY", "local-secret")
    monkeypatch.setenv("CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING", "1")

    namespace = load_script_namespace()
    values = namespace["provider_environment"]()

    assert values["CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING"] == "1"
    provider = namespace["build_teaching_provider"](values)
    assert provider.__class__.__name__ == "JsonHttpTeachingProvider"


def test_live_smoke_does_not_enable_private_http_implicitly(monkeypatch):
    monkeypatch.setenv("TEACHING_LLM_ENDPOINT", "https://provider.example/v1/chat/completions")
    monkeypatch.setenv("TEACHING_LLM_MODEL", "provider-model")
    monkeypatch.setenv("TEACHING_LLM_API_KEY", "secret")
    monkeypatch.delenv("CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING", raising=False)

    namespace = load_script_namespace()
    values = namespace["provider_environment"]()

    assert "CARD_IN_REPO_ALLOW_PRIVATE_HTTP_TEACHING" not in values
