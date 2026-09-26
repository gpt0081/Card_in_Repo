import json
from http.client import IncompleteRead

from card_in_repo_api.teaching_provider import JsonHttpTeachingProvider


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


def test_provider_retries_incomplete_chunked_response_body():
    attempts = 0

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise IncompleteRead(b'{"choices":', 128)
        return Response({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "level": "intermediate",
                        "claims": [{
                            "text": "Entry returns a literal.",
                            "evidence_ids": ["evidence:1"],
                        }],
                    })
                }
            }]
        })

    provider = JsonHttpTeachingProvider(
        "https://llm.invalid/chat",
        "model",
        "secret",
        opener=opener,
        max_attempts=2,
    )
    result = provider.explain_card({
        "symbol_name": "entry",
        "path": "app.py",
        "range": {"start": {"line": 1}, "end": {"line": 2}},
        "source": "def entry():\n    return 1",
        "segment": {"index": 0, "count": 1},
        "evidence": [{"id": "evidence:1", "type": "SOURCE_RANGE", "path": "app.py"}],
    }, "intermediate")

    assert attempts == 2
    assert result["level"] == "intermediate"
    assert result["claims"][0]["evidence_ids"] == ["evidence:1"]
