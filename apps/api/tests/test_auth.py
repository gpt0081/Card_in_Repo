from __future__ import annotations

import pytest

from card_in_repo_api.auth import auth_settings_from_env, sign_payload, verify_payload


OAUTH_ENV = (
    "CARD_IN_REPO_GITHUB_CLIENT_ID",
    "CARD_IN_REPO_GITHUB_CLIENT_SECRET",
    "CARD_IN_REPO_SESSION_SECRET",
    "CARD_IN_REPO_GITHUB_CALLBACK_URL",
    "CARD_IN_REPO_INSECURE_COOKIE",
)


def _clear_oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in OAUTH_ENV:
        monkeypatch.delenv(name, raising=False)


def _set_oauth_env(monkeypatch: pytest.MonkeyPatch, callback_url: str) -> None:
    monkeypatch.setenv("CARD_IN_REPO_GITHUB_CLIENT_ID", "client")
    monkeypatch.setenv("CARD_IN_REPO_GITHUB_CLIENT_SECRET", "secret")
    monkeypatch.setenv("CARD_IN_REPO_SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("CARD_IN_REPO_GITHUB_CALLBACK_URL", callback_url)


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


def test_auth_settings_allow_fully_disabled_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_oauth_env(monkeypatch)
    assert auth_settings_from_env() is None


def test_auth_settings_reject_partial_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_oauth_env(monkeypatch)
    monkeypatch.setenv("CARD_IN_REPO_GITHUB_CLIENT_ID", "client")
    with pytest.raises(ValueError, match="incomplete GitHub OAuth configuration"):
        auth_settings_from_env()


def test_auth_settings_reject_weak_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_oauth_env(monkeypatch)
    _set_oauth_env(monkeypatch, "https://card-in-repo.example/v1/auth/github/callback")
    monkeypatch.setenv("CARD_IN_REPO_SESSION_SECRET", "too-short")
    with pytest.raises(ValueError, match="at least 32 bytes"):
        auth_settings_from_env()


def test_auth_settings_accept_32_byte_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_oauth_env(monkeypatch)
    _set_oauth_env(monkeypatch, "https://card-in-repo.example/v1/auth/github/callback")
    settings = auth_settings_from_env()
    assert settings is not None
    assert len(settings.session_secret.encode()) == 32


def test_auth_settings_require_https_for_remote_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_oauth_env(monkeypatch)
    _set_oauth_env(monkeypatch, "http://card-in-repo.example/v1/auth/github/callback")
    with pytest.raises(ValueError, match="must use HTTPS"):
        auth_settings_from_env()


def test_auth_settings_allow_http_loopback_for_local_development(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_oauth_env(monkeypatch)
    _set_oauth_env(monkeypatch, "http://localhost:8000/v1/auth/github/callback")
    monkeypatch.setenv("CARD_IN_REPO_INSECURE_COOKIE", "1")
    settings = auth_settings_from_env()
    assert settings is not None
    assert settings.secure_cookie is False


def test_auth_settings_reject_insecure_cookie_for_remote_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_oauth_env(monkeypatch)
    _set_oauth_env(monkeypatch, "https://card-in-repo.example/v1/auth/github/callback")
    monkeypatch.setenv("CARD_IN_REPO_INSECURE_COOKIE", "1")
    with pytest.raises(ValueError, match="only for loopback"):
        auth_settings_from_env()
