import pytest

from card_in_repo_api.teaching import (
    UnverifiedExplanation,
    build_basic_explanation,
    verify_explanation,
)


def test_verifier_accepts_only_claims_citing_known_evidence():
    explanation = {
        "level": "basic",
        "claims": [{"text": "entry calls load", "evidence_ids": ["e1", "e2"]}],
    }

    verified = verify_explanation(explanation, {"e1", "e2"})

    assert verified["verified"] is True


def test_basic_explanation_tolerates_nullable_execution_order_from_real_analysis():
    concept = {
        "evidence": [
            {"id": "e-null", "symbol_id": "helper", "symbol_name": "helper", "order": None},
            {"id": "e-2", "symbol_id": "second", "symbol_name": "second", "order": 2},
            {"id": "e-1", "symbol_id": "first", "symbol_name": "first", "order": 1},
        ]
    }

    explanation = build_basic_explanation(concept)

    assert explanation["verified"] is True
    assert explanation["claims"][0]["evidence_ids"] == ["e-1", "e-2", "e-null"]
    assert "first → second → helper" in explanation["claims"][0]["text"]


@pytest.mark.parametrize(
    "explanation",
    [
        {"level": "basic", "claims": [{"text": "unsupported", "evidence_ids": []}]},
        {"level": "basic", "claims": [{"text": "invented", "evidence_ids": ["ghost"]}]},
        {"level": "intermediate", "claims": [{"text": "too early", "evidence_ids": ["e1"]}]},
    ],
)
def test_verifier_fails_closed_for_unbacked_or_non_basic_teaching(explanation):
    with pytest.raises(UnverifiedExplanation):
        verify_explanation(explanation, {"e1"})
