import json

import pytest

from card_in_repo_api.teaching import verify_on_demand_card_explanation
from card_in_repo_api.teaching_provider import JsonHttpTeachingProvider, TeachingProviderError


class Response:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        data = json.dumps({"choices": [{"message": {"content": self.content}}]}).encode()
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


def provider_for(content):
    return JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=lambda request, timeout: Response(content),
    )


@pytest.mark.parametrize("opening", ["```json", "```"])
def test_provider_accepts_whole_response_json_fence(opening):
    payload = {
        "level": "intermediate",
        "claims": [{"text": "Entry returns a literal.", "evidence_ids": ["evidence:1"]}],
    }
    result = provider_for(f"{opening}\n{json.dumps(payload)}\n```").explain_card(card(), "intermediate")
    assert verify_on_demand_card_explanation(card(), result, "intermediate")["verified"] is True


@pytest.mark.parametrize("content", [
    "Here is JSON:\n```json\n{}\n```",
    "```python\n{}\n```",
    "```json\n{}\n```\nextra prose",
])
def test_provider_rejects_fences_mixed_with_prose_or_wrong_language(content):
    with pytest.raises(TeachingProviderError):
        provider_for(content).explain_card(card(), "intermediate")
