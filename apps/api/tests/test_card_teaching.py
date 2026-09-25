import pytest

from card_in_repo_api.teaching import (
    UnverifiedExplanation,
    build_card_basic_explanation,
    generate_card_basic_explanation,
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


class BasicProvider:
    def __init__(self, evidence_id="source:e1"):
        self.evidence_id = evidence_id
        self.levels = []

    def explain_card(self, card, level):
        self.levels.append(level)
        return {
            "level": level,
            "claims": [{"text": "Provider-generated Basic teaching.", "evidence_ids": [self.evidence_id]}],
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


def test_configured_provider_generates_basic_teaching_up_front():
    provider = BasicProvider()

    explanation = generate_card_basic_explanation(_card(), provider)

    assert provider.levels == ["basic"]
    assert explanation["verified"] is True
    assert explanation["claims"][0]["text"] == "Provider-generated Basic teaching."


def test_provider_basic_teaching_cannot_escape_static_evidence():
    provider = BasicProvider(evidence_id="invented:evidence")

    with pytest.raises(UnverifiedExplanation, match="outside the static fact layer"):
        generate_card_basic_explanation(_card(), provider)


def test_basic_teaching_keeps_verified_fallback_without_provider():
    explanation = generate_card_basic_explanation(_card(), None)

    assert explanation["verified"] is True
    assert "normalize segment 2 of 3" in explanation["claims"][0]["text"]
