from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from card_in_repo_api.teaching_provider import JsonHttpTeachingProvider


def test_json_http_provider_round_trips_over_real_http_transport() -> None:
    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
            length = int(self.headers["Content-Length"])
            received["path"] = self.path
            received["authorization"] = self.headers.get("Authorization")
            received["content_type"] = self.headers.get("Content-Type")
            received["body"] = json.loads(self.rfile.read(length))

            response = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "level": "advanced",
                                    "claims": [
                                        {
                                            "text": "The function is grounded in the supplied source range.",
                                            "evidence_ids": ["evidence:source"],
                                        }
                                    ],
                                }
                            )
                        }
                    }
                ]
            }
            payload = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = JsonHttpTeachingProvider(
            endpoint=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            model="fixture-model",
            api_key="fixture-secret",
            timeout_seconds=2,
        )
        card = {
            "symbol_name": "load_repository",
            "path": "src/repository.py",
            "range": {"start": {"line": 4}, "end": {"line": 8}},
            "source": "def load_repository():\n    return True",
            "segment": {"index": 0, "count": 1},
            "evidence": [
                {
                    "id": "evidence:source",
                    "type": "SOURCE_RANGE",
                    "path": "src/repository.py",
                    "range": {"start": {"line": 4}, "end": {"line": 8}},
                }
            ],
        }

        result = provider.explain_card(card, "advanced")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result["level"] == "advanced"
    assert result["claims"][0]["evidence_ids"] == ["evidence:source"]
    assert received["path"] == "/v1/chat/completions"
    assert received["authorization"] == "Bearer fixture-secret"
    assert received["content_type"] == "application/json"

    body = received["body"]
    assert isinstance(body, dict)
    assert body["model"] == "fixture-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system"
    user_payload = json.loads(body["messages"][1]["content"])
    assert user_payload["requested_level"] == "advanced"
    assert user_payload["card_facts"]["evidence"] == [card["evidence"][0]]
