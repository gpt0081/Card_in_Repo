import json

import pytest

from card_in_repo_api.runtime import RuntimeConfigurationError, build_teaching_provider
from card_in_repo_api.teaching import verify_on_demand_card_explanation, UnverifiedExplanation
from card_in_repo_api.teaching_provider import JsonHttpTeachingProvider, TeachingProviderError


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        data = json.dumps(self.body).encode()
        return data if size < 0 else data[:size]


def card():
    return {
        "id": "card:1",
        "symbol_name": "entry",
        "path": "app.py",
        "range": {"start": {"line": 1}, "end": {"line": 2}},
        "source": "def entry():\n    return 1",
        "segment": {"index": 0, "count": 1},
        "evidence": [{"id": "evidence:1", "type": "SOURCE_RANGE", "path": "app.py"}],
    }


def test_json_http_provider_sends_only_card_facts_and_returns_structured_prose():
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response({"choices": [{"message": {"content": json.dumps({
            "level": "intermediate",
            "claims": [{"text": "Entry returns a literal.", "evidence_ids": ["evidence:1"]}],
        })}}]})

    provider = JsonHttpTeachingProvider("https://llm.invalid/chat", "teaching-model", "secret", opener=opener)
    result = provider.explain_card(card(), "intermediate")
    verified = verify_on_demand_card_explanation(card(), result, "intermediate")

    assert verified["verified"] is True
    payload = json.loads(captured["request"].data)
    prompt = json.loads(payload["messages"][1]["content"])
    assert prompt["requested_level"] == "intermediate"
    assert prompt["card_facts"]["evidence"][0]["id"] == "evidence:1"
    assert "repository" not in prompt["card_facts"]


@pytest.mark.parametrize("content", [
    {"level": "advanced", "claims": [{"text": "Direct JSON object.", "evidence_ids": ["evidence:1"]}]},
    [{"type": "text", "text": json.dumps({
        "level": "advanced",
        "claims": [{"text": "Typed content block.", "evidence_ids": ["evidence:1"]}],
    })}],
])
def test_provider_accepts_common_openai_compatible_json_content_shapes(content):
    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=lambda request, timeout: Response({"choices": [{"message": {"content": content}}]}),
    )
    result = provider.explain_card(card(), "advanced")
    assert verify_on_demand_card_explanation(card(), result, "advanced")["verified"] is True


def test_provider_output_still_fails_closed_on_invented_evidence():
    def opener(request, timeout):
        return Response({"choices": [{"message": {"content": json.dumps({
            "level": "deep",
            "claims": [{"text": "Invented claim.", "evidence_ids": ["evidence:fake"]}],
        })}}]})

    result = JsonHttpTeachingProvider("https://llm.invalid/chat", "model", "secret", opener=opener).explain_card(card(), "deep")
    with pytest.raises(UnverifiedExplanation):
        verify_on_demand_card_explanation(card(), result, "deep")


def test_malformed_provider_response_is_explicit_failure():
    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat", "model", "secret", opener=lambda request, timeout: Response({"choices": []})
    )
    with pytest.raises(TeachingProviderError):
        provider.explain_card(card(), "advanced")


def test_non_json_content_never_falls_back_to_unverified_prose():
    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=lambda request, timeout: Response({"choices": [{"message": {"content": "plain prose"}}]}),
    )
    with pytest.raises(TeachingProviderError):
        provider.explain_card(card(), "advanced")


def test_provider_rejects_response_larger_than_configured_limit():
    oversized = {"choices": [{"message": {"content": "x" * 512}}]}
    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        max_response_bytes=128,
        opener=lambda request, timeout: Response(oversized),
    )
    with pytest.raises(TeachingProviderError, match="exceeds size limit"):
        provider.explain_card(card(), "advanced")


def test_runtime_requires_complete_configuration_and_defaults_off():
    assert build_teaching_provider({}) is None
    with pytest.raises(RuntimeConfigurationError):
        build_teaching_provider({"CARD_IN_REPO_TEACHING_PROVIDER": "json_http"})

    provider = build_teaching_provider({
        "CARD_IN_REPO_TEACHING_PROVIDER": "json_http",
        "TEACHING_LLM_ENDPOINT": "https://llm.invalid/chat",
        "TEACHING_LLM_MODEL": "model",
        "TEACHING_LLM_API_KEY": "secret",
    })
    assert isinstance(provider, JsonHttpTeachingProvider)


def test_runtime_applies_configured_provider_resource_bounds():
    provider = build_teaching_provider({
        "CARD_IN_REPO_TEACHING_PROVIDER": "json_http",
        "TEACHING_LLM_ENDPOINT": "https://llm.invalid/chat",
        "TEACHING_LLM_MODEL": "model",
        "TEACHING_LLM_API_KEY": "secret",
        "TEACHING_LLM_TIMEOUT_SECONDS": "12.5",
        "TEACHING_LLM_MAX_RESPONSE_BYTES": "262144",
    })
    assert isinstance(provider, JsonHttpTeachingProvider)
    assert provider.timeout_seconds == 12.5
    assert provider.max_response_bytes == 262144


@pytest.mark.parametrize(("name", "value"), [
    ("TEACHING_LLM_TIMEOUT_SECONDS", "0"),
    ("TEACHING_LLM_TIMEOUT_SECONDS", "not-a-number"),
    ("TEACHING_LLM_MAX_RESPONSE_BYTES", "-1"),
    ("TEACHING_LLM_MAX_RESPONSE_BYTES", "1.5"),
])
def test_runtime_rejects_invalid_provider_resource_bounds(name, value):
    env = {
        "CARD_IN_REPO_TEACHING_PROVIDER": "json_http",
        "TEACHING_LLM_ENDPOINT": "https://llm.invalid/chat",
        "TEACHING_LLM_MODEL": "model",
        "TEACHING_LLM_API_KEY": "secret",
        name: value,
    }
    with pytest.raises(RuntimeConfigurationError):
        build_teaching_provider(env)


@pytest.mark.parametrize("endpoint", [
    "http://localhost:1234/v1/chat/completions",
    "http://127.0.0.1:1234/v1/chat/completions",
    "http://[::1]:1234/v1/chat/completions",
    "http://host.docker.internal:1234/v1/chat/completions",
])
def test_runtime_allows_cleartext_only_for_local_model_servers(endpoint):
    provider = build_teaching_provider({
        "CARD_IN_REPO_TEACHING_PROVIDER": "json_http",
        "TEACHING_LLM_ENDPOINT": endpoint,
        "TEACHING_LLM_MODEL": "local-model",
        "TEACHING_LLM_API_KEY": "local-secret",
    })
    assert isinstance(provider, JsonHttpTeachingProvider)


@pytest.mark.parametrize("endpoint", [
    "http://llm.example.com/v1/chat/completions",
    "ftp://llm.example.com/chat",
    "llm.example.com/chat",
])
def test_runtime_rejects_remote_or_invalid_non_https_teaching_endpoint(endpoint):
    with pytest.raises(RuntimeConfigurationError, match="must use HTTPS"):
        build_teaching_provider({
            "CARD_IN_REPO_TEACHING_PROVIDER": "json_http",
            "TEACHING_LLM_ENDPOINT": endpoint,
            "TEACHING_LLM_MODEL": "model",
            "TEACHING_LLM_API_KEY": "secret",
        })
