import pytest

from card_in_repo_api.teaching import UnverifiedExplanation, verify_explanation


def test_verifier_accepts_only_claims_citing_known_evidence():
    explanation = {
        "level": "basic",
        "claims": [{"text": "entry calls load", "evidence_ids": ["e1", "e2"]}],
    }

    verified = verify_explanation(explanation, {"e1", "e2"})

    assert verified["verified"] is True


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
