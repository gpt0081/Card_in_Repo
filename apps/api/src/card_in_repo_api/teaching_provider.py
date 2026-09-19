from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen


class TeachingProviderError(RuntimeError):
    """Raised when a configured teaching provider cannot return usable JSON."""


@dataclass(frozen=True)
class JsonHttpTeachingProvider:
    """Small provider adapter for OpenAI-compatible JSON chat endpoints.

    The adapter receives immutable card facts and asks only for teaching prose.
    The API layer still verifies every returned evidence ID before publication.
    """

    endpoint: str
    model: str
    api_key: str
    timeout_seconds: float = 30.0
    opener: Callable[..., Any] = urlopen

    def explain_card(self, card: dict[str, Any], level: str) -> dict[str, Any]:
        evidence = [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "path": item.get("path"),
                "range": item.get("range"),
            }
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
        system = (
            "You teach source code using only the supplied static-analysis facts. "
            "Return JSON only with keys level and claims. claims must be a non-empty list of "
            "objects with text and evidence_ids. Every factual claim must cite one or more supplied "
            "evidence IDs. Never invent repository facts, symbols, files, runtime behavior, or evidence IDs."
        )
        user = json.dumps({"requested_level": level, "card_facts": facts}, ensure_ascii=False)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (OSError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise TeachingProviderError("teaching provider returned an unusable response") from exc
        if not isinstance(result, dict):
            raise TeachingProviderError("teaching provider response must be a JSON object")
        return result
