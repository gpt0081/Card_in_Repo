from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol
from urllib.request import Request, urlopen


class TeachingProviderError(RuntimeError):
    pass


class TeachingProvider(Protocol):
    def explain_card(self, card: dict[str, Any], level: str) -> dict[str, Any]: ...


def _decode_message_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        result = content
    elif isinstance(content, str):
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise TeachingProviderError("teaching provider content must be JSON") from exc
    elif isinstance(content, list):
        text = "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
        if not text:
            raise TeachingProviderError("teaching provider content blocks contained no text")
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TeachingProviderError("teaching provider content blocks must contain JSON") from exc
    else:
        raise TeachingProviderError("teaching provider content has unsupported shape")
    if not isinstance(result, dict):
        raise TeachingProviderError("teaching provider content must decode to an object")
    return result


@dataclass(frozen=True)
class DeterministicTestTeachingProvider:
    """Test-only provider that produces evidence-linked teaching text."""

    def explain_card(self, card: dict[str, Any], level: str) -> dict[str, Any]:
        evidence = card.get("evidence") or []
        if not evidence:
            raise TeachingProviderError("card has no evidence")
        evidence_id = evidence[0]["id"]
        symbol = card.get("symbol_name") or card.get("path") or "This code"
        return {
            "level": level,
            "claims": [
                {
                    "text": f"{symbol} is explained from its linked static-analysis evidence.",
                    "evidence_ids": [evidence_id],
                }
            ],
        }


@dataclass(frozen=True)
class JsonHttpTeachingProvider:
    """OpenAI-compatible JSON chat adapter limited to teaching prose."""

    endpoint: str
    model: str
    api_key: str
    timeout_seconds: float = 30.0
    # Keep opener before new optional fields so existing positional test/integration
    # adapters do not silently bind their opener as a byte limit.
    opener: Callable[..., Any] = urlopen
    max_response_bytes: int = 1_048_576

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
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise TeachingProviderError("teaching provider response exceeds size limit")
                body = json.loads(raw.decode())
            content = body["choices"][0]["message"]["content"]
            return _decode_message_content(content)
        except TeachingProviderError:
            raise
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise TeachingProviderError("teaching provider returned an unusable response") from exc
