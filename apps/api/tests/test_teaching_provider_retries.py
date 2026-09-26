import json
from urllib.error import HTTPError

import pytest

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
        "symbol_name": "entry",
        "path": "app.py",
        "range": {"start": {"line": 1}, "end": {"line": 2}},
        "source": "def entry():\n    return 1",
        "segment": {"index": 0, "count": 1},
        "evidence": [{"id": "evidence:1", "type": "SOURCE_RANGE", "path": "app.py"}],
    }


def success_body():
    return {"choices": [{"message": {"content": json.dumps({
        "level": "intermediate",
        "claims": [{"text": "Entry returns a literal.", "evidence_ids": ["evidence:1"]}],
    })}}]}


def http_error(code, headers=None):
    return HTTPError("https://llm.invalid/chat", code, "upstream", headers or {}, None)


def test_provider_retries_one_transient_http_failure_then_succeeds():
    calls = []
    sleeps = []

    def opener(request, timeout):
        calls.append(request)
        if len(calls) == 1:
            raise http_error(429, {"Retry-After": "0.25"})
        return Response(success_body())

    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=opener,
        sleeper=sleeps.append,
    )

    assert provider.explain_card(card(), "intermediate")["level"] == "intermediate"
    assert len(calls) == 2
    assert sleeps == [0.25]


def test_provider_caps_retry_after_delay():
    calls = 0
    sleeps = []

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise http_error(503, {"Retry-After": "120"})
        return Response(success_body())

    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=opener,
        sleeper=sleeps.append,
    )

    provider.explain_card(card(), "intermediate")
    assert sleeps == [2.0]


def test_provider_supports_http_date_retry_after_and_caps_delay():
    calls = 0
    sleeps = []

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise http_error(429, {"Retry-After": "Wed, 31 Dec 2099 23:59:59 GMT"})
        return Response(success_body())

    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=opener,
        sleeper=sleeps.append,
    )

    provider.explain_card(card(), "intermediate")
    assert calls == 2
    assert sleeps == [2.0]


def test_provider_does_not_retry_non_transient_http_failure():
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        raise http_error(400)

    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=opener,
        sleeper=lambda delay: pytest.fail("non-transient failure must not sleep"),
    )

    with pytest.raises(TeachingProviderError):
        provider.explain_card(card(), "intermediate")
    assert calls == 1


def test_provider_stops_after_bounded_attempts():
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        raise http_error(502)

    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=opener,
        max_attempts=2,
        sleeper=lambda delay: None,
    )

    with pytest.raises(TeachingProviderError):
        provider.explain_card(card(), "intermediate")
    assert calls == 2


def test_provider_retries_one_transport_failure_then_succeeds_without_extra_sleep():
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("upstream timed out")
        return Response(success_body())

    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=opener,
        sleeper=lambda delay: pytest.fail("transport retry must not add a second delay after timeout"),
    )

    assert provider.explain_card(card(), "intermediate")["level"] == "intermediate"
    assert calls == 2


def test_provider_bounds_repeated_transport_failures():
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        raise ConnectionError("connection reset")

    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=opener,
        max_attempts=2,
    )

    with pytest.raises(TeachingProviderError, match="transport failed"):
        provider.explain_card(card(), "intermediate")
    assert calls == 2
