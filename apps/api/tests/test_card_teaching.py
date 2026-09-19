import pytest

from card_in_repo_api.teaching import (
    UnverifiedExplanation,
    build_card_basic_explanation,
)


def _card():
    return {
        "symbol_name": "normalize",
        "path": "service.py",
        "range": {"start": {"line": 10}, "end": {"line": 18}},
        "segment": {"index": 1, "count": 3},
        "evidence": [{
            "id": "source:e1",
            "type": "SOURCE_RANGE",
            "path": "service.py",
            "range": {"start": {"line": 10}, "end": {"line": 18}},
        }],
    }


def test_card_basic_teaching_is_structured_and_evidence_verified():
    explanation = build_card_basic_explanation(_card())

    assert explanation["level"] == "basic"
    assert explanation["verified"] is True
    assert explanation["claims"][0]["evidence_ids"] == ["source:e1"]
    assert "normalize segment 2 of 3" in explanation["claims"][0]["text"]
    assert "service.py lines 10–18" in explanation["claims"][0]["text"]


def test_card_basic_teaching_fails_closed_without_source_evidence():
    card = _card()
    card["evidence"] = []

    with pytest.raises(UnverifiedExplanation):
        build_card_basic_explanation(card)
