from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen


class TeachingProviderError(RuntimeError):
    """Raised when a configured teaching provider cannot return usable JSON."""


@dataclass(frozen=True)
class JsonHttpTeachingProvider:
    """OpenAI-compatible JSON chat adapter limited to teaching prose."""

    endpoint: str
    model: str
    api_key: str
    timeout_seconds: float = 30.0
    opener: Callable[..., Any] = urlopen

    def explain_card(self, card: dict[str, Any], level: str) -> dict[str, Any]:
        evidence = [
            {key: item.get(key) for key in ("id", "type", "path", "range")}
            for item in card.get("evidence", [])
            if item.get("id")
        ]
        facts = {
            "symbol_name": card.get("symbol_name"),
            "path": card.get("path"),
            "range": card.get("range"),
            "source": card.get("source"),
            "segment": card.get("segment"),
            "evidence": evidence,
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Teach only from supplied static-analysis facts. Return JSON only with keys level and claims. "
                        "Each claim needs text and one or more supplied evidence_ids. Never invent repository facts, "
                        "runtime behavior, files, symbols, or evidence IDs."
                    ),
                },
                {"role": "user", "content": json.dumps({"requested_level": level, "card_facts": facts})},
            ],
            "response_format": {"type": "json_object"},
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode())
            result = json.loads(body["choices"][0]["message"]["content"])
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise TeachingProviderError("teaching provider returned an unusable response") from exc
        if not isinstance(result, dict):
            raise TeachingProviderError("teaching provider response must be a JSON object")
        return result
