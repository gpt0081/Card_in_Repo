from __future__ import annotations

import hashlib
import math
import re
from typing import Any

VECTOR_DIMENSIONS = 32
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def structural_concept_vector(concept: dict[str, Any]) -> list[float]:
    """Feature-hash static concept evidence into a stable vector.

    This is deliberately not an LLM embedding. It gives pgvector a factual,
    reproducible retrieval signal until a separately verified embedding
    provider is introduced.
    """
    tokens: list[str] = []
    tokens.extend(_TOKEN.findall(str(concept.get("name") or "").lower()))
    tokens.append(f"kind:{concept.get('kind') or 'unknown'}")
    for item in concept.get("evidence") or []:
        for key in ("symbol_name", "path", "relation"):
            value = item.get(key)
            if value:
                tokens.extend(f"{key}:{token.lower()}" for token in _TOKEN.findall(str(value)))

    vector = [0.0] * VECTOR_DIMENSIONS
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:2], "big") % VECTOR_DIMENSIONS
        sign = 1.0 if digest[2] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


def vectorized_concepts(concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": concept["id"], "concept": concept, "vector": structural_concept_vector(concept)} for concept in concepts]
