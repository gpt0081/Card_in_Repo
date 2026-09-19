from __future__ import annotations

import pytest

from card_in_repo_api.auth import sign_payload, verify_payload


def test_signed_payload_round_trip() -> None:
    token = sign_payload({"iat": 100, "login": "learner"}, "test-secret")
    assert verify_payload(token, "test-secret", max_age=60, now=120)["login"] == "learner"


def test_signed_payload_rejects_tampering() -> None:
    token = sign_payload({"iat": 100, "login": "learner"}, "test-secret")
    with pytest.raises(ValueError):
        verify_payload(token + "x", "test-secret", max_age=60, now=120)


def test_signed_payload_rejects_expiry() -> None:
    token = sign_payload({"iat": 100, "login": "learner"}, "test-secret")
    with pytest.raises(ValueError):
        verify_payload(token, "test-secret", max_age=10, now=120)
