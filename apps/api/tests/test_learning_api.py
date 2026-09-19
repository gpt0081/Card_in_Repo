from fastapi import FastAPI
from fastapi.testclient import TestClient

from card_in_repo_api.auth import AuthSettings, sign_payload
from card_in_repo_api.learning import create_learning_router
from card_in_repo_api.store import MemoryAnalysisStore


SETTINGS = AuthSettings(
    client_id="client",
    client_secret="secret",
    session_secret="test-session-secret",
    callback_url="http://testserver/v1/auth/github/callback",
    secure_cookie=False,
)


def client_with_store() -> tuple[TestClient, MemoryAnalysisStore]:
    store = MemoryAnalysisStore()
    store.put_analysis({"id": "analysis-1", "state": "READY", "repository": "https://github.com/acme/demo"})
    app = FastAPI()
    app.include_router(create_learning_router(SETTINGS, store))
    return TestClient(app), store


def signed_cookie(github_id: int) -> str:
    return sign_payload({"iat": 2_000_000_000, "github_id": github_id, "login": f"user-{github_id}"}, SETTINGS.session_secret)


def test_learning_state_requires_signed_session(monkeypatch) -> None:
    client, _ = client_with_store()
    response = client.get("/v1/learning/analyses/analysis-1/concepts")
    assert response.status_code == 401


def test_learning_state_is_derived_from_signed_github_user(monkeypatch) -> None:
    monkeypatch.setattr("card_in_repo_api.auth.time.time", lambda: 2_000_000_000)
    client, _ = client_with_store()
    client.cookies.set("card_in_repo_session", signed_cookie(42))

    updated = client.put(
        "/v1/learning/analyses/analysis-1/concepts/concept:loops",
        json={"mastery": "learning", "review_due_at": "2033-05-18T03:33:20+00:00"},
    )
    assert updated.status_code == 200
    assert updated.json()["github_user_id"] == 42
    assert updated.json()["mastery"] == "learning"

    listed = client.get("/v1/learning/analyses/analysis-1/concepts")
    assert listed.status_code == 200
    assert [state["concept_id"] for state in listed.json()["states"]] == ["concept:loops"]


def test_one_user_cannot_read_another_users_learning_state(monkeypatch) -> None:
    monkeypatch.setattr("card_in_repo_api.auth.time.time", lambda: 2_000_000_000)
    client, _ = client_with_store()
    client.cookies.set("card_in_repo_session", signed_cookie(42))
    assert client.put(
        "/v1/learning/analyses/analysis-1/concepts/concept:imports",
        json={"mastery": "understood"},
    ).status_code == 200

    client.cookies.set("card_in_repo_session", signed_cookie(99))
    response = client.get("/v1/learning/analyses/analysis-1/concepts")
    assert response.status_code == 200
    assert response.json()["states"] == []


def test_invalid_mastery_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr("card_in_repo_api.auth.time.time", lambda: 2_000_000_000)
    client, _ = client_with_store()
    client.cookies.set("card_in_repo_session", signed_cookie(42))
    response = client.put(
        "/v1/learning/analyses/analysis-1/concepts/concept:loops",
        json={"mastery": "expert"},
    )
    assert response.status_code == 422
