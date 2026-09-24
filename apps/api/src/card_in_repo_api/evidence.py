from __future__ import annotations

from typing import Any

from .source_artifacts import SourceArtifactStore
from .store import AnalysisStore


class DurableEvidenceError(RuntimeError):
    """Raised when persisted card evidence cannot be proven from its source artifact."""


def reconstruct_card_evidence(
    store: AnalysisStore,
    source_artifacts: SourceArtifactStore,
    card: dict[str, Any],
) -> list[dict[str, Any]]:
    """Reconstruct every SOURCE_RANGE evidence item from the analyzed commit snapshot.

    The database card is treated as an index only. Source text is always recovered from
    the immutable object-storage artifact and verified against the digest recorded by
    the worker before it is returned as evidence.
    """
    analysis_id = card.get("analysis_id")
    analysis = store.get_analysis(analysis_id) if analysis_id else None
    if analysis is None or analysis.get("state") != "READY":
        raise DurableEvidenceError("card analysis is not ready")

    repository = analysis.get("repository")
    commit_sha = analysis.get("commit_sha")
    artifact = (analysis.get("facts") or {}).get("source_artifact") or {}
    expected_sha256 = artifact.get("sha256")
    if not repository or not commit_sha or not expected_sha256:
        raise DurableEvidenceError("analysis has no verified source artifact")
    if card.get("repository") != repository or card.get("commit_sha") != commit_sha:
        raise DurableEvidenceError("card identity does not match analysis artifact")

    reconstructed: list[dict[str, Any]] = []
    for evidence in card.get("evidence") or []:
        if evidence.get("type") != "SOURCE_RANGE":
            continue
        path = evidence.get("path")
        range_ = evidence.get("range") or {}
        try:
            start_line = int(range_["start"]["line"])
            end_line = int(range_["end"]["line"])
            source = source_artifacts.get_source_range(
                repository,
                commit_sha,
                path,
                start_line,
                end_line,
                expected_sha256=expected_sha256,
            )
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            raise DurableEvidenceError("source evidence verification failed") from exc
        reconstructed.append({**evidence, "source": source, "verified": True})

    if not reconstructed:
        raise DurableEvidenceError("card has no source-range evidence")
    return reconstructed
