from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest
from fastapi.responses import RedirectResponse


@dataclass(frozen=True)
class AuthSettings:
    client_id: str
    client_secret: str
    session_secret: str
    callback_url: str
    app_url: str = "/"
    secure_cookie: bool = True


class GitHubOAuthClient(Protocol):
    def exchange_code(self, code: str) -> str: ...
    def fetch_user(self, access_token: str) -> dict[str, Any]: ...


class GitHubHTTPClient:
    def __init__(self, settings: AuthSettings) -> None:
        self.settings = settings

    def exchange_code(self, code: str) -> str:
        body = urlencode({
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "code": code,
            "redirect_uri": self.settings.callback_url,
        }).encode()
        request = Request(
            "https://github.com/login/oauth/access_token",
            data=body,
            headers={"Accept": "application/json", "User-Agent": "Card-in-Repo"},
        )
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
        token = payload.get("access_token")
        if not token:
            raise ValueError("GitHub did not return an access token")
        return str(token)

    def fetch_user(self, access_token: str) -> dict[str, Any]:
        request = Request(
            "https://api.github.com/user",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Card-in-Repo",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
        if not payload.get("id") or not payload.get("login"):
            raise ValueError("GitHub user response is incomplete")
        return payload


def _is_loopback_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _validate_callback_url(callback_url: str, *, secure_cookie: bool) -> None:
    parsed = urlparse(callback_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("CARD_IN_REPO_GITHUB_CALLBACK_URL must be an absolute HTTP(S) URL")
    if parsed.scheme != "https" and not _is_loopback_host(parsed.hostname):
        raise ValueError("remote GitHub OAuth callback URLs must use HTTPS")
    if not secure_cookie and not _is_loopback_host(parsed.hostname):
        raise ValueError("insecure OAuth cookies are allowed only for loopback development callbacks")


def auth_settings_from_env() -> AuthSettings | None:
    values = {
        "CARD_IN_REPO_GITHUB_CLIENT_ID": os.getenv("CARD_IN_REPO_GITHUB_CLIENT_ID", "").strip(),
        "CARD_IN_REPO_GITHUB_CLIENT_SECRET": os.getenv("CARD_IN_REPO_GITHUB_CLIENT_SECRET", "").strip(),
        "CARD_IN_REPO_SESSION_SECRET": os.getenv("CARD_IN_REPO_SESSION_SECRET", "").strip(),
        "CARD_IN_REPO_GITHUB_CALLBACK_URL": os.getenv("CARD_IN_REPO_GITHUB_CALLBACK_URL", "").strip(),
    }
    configured = [name for name, value in values.items() if value]
    if not configured:
        return None
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError("incomplete GitHub OAuth configuration; missing: " + ", ".join(missing))

    secure_cookie = os.getenv("CARD_IN_REPO_INSECURE_COOKIE") != "1"
    callback_url = values["CARD_IN_REPO_GITHUB_CALLBACK_URL"]
    _validate_callback_url(callback_url, secure_cookie=secure_cookie)
    return AuthSettings(
        client_id=values["CARD_IN_REPO_GITHUB_CLIENT_ID"],
        client_secret=values["CARD_IN_REPO_GITHUB_CLIENT_SECRET"],
        session_secret=values["CARD_IN_REPO_SESSION_SECRET"],
        callback_url=callback_url,
        app_url=os.getenv("CARD_IN_REPO_APP_URL", "/"),
        secure_cookie=secure_cookie,
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    encoded = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64(hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_payload(token: str, secret: str, *, max_age: int, now: int | None = None) -> dict[str, Any]:
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64(hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        payload = json.loads(_unb64(encoded))
        issued_at = int(payload["iat"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid signed payload") from exc
    current = int(time.time()) if now is None else now
    if issued_at > current + 30 or current - issued_at > max_age:
        raise ValueError("expired signed payload")
    return payload


def create_auth_router(settings: AuthSettings | None, client: GitHubOAuthClient | None = None) -> APIRouter:
    router = APIRouter(prefix="/v1/auth", tags=["auth"])
    oauth = client or (GitHubHTTPClient(settings) if settings else None)

    @router.get("/session")
    def session(request: FastAPIRequest) -> dict[str, Any]:
        if settings is None:
            return {"authenticated": False, "login_available": False}
        token = request.cookies.get("card_in_repo_session")
        if not token:
            return {"authenticated": False, "login_available": True}
        try:
            payload = verify_payload(token, settings.session_secret, max_age=60 * 60 * 24 * 30)
        except ValueError:
            return {"authenticated": False, "login_available": True}
        return {
            "authenticated": True,
            "login_available": True,
            "user": {"id": payload["github_id"], "login": payload["login"], "avatar_url": payload.get("avatar_url")},
        }

    @router.get("/github/login")
    def login() -> RedirectResponse:
        if settings is None:
            raise HTTPException(status_code=503, detail="GitHub login is not configured")
        state = sign_payload({"iat": int(time.time()), "purpose": "github_oauth"}, settings.session_secret)
        target = "https://github.com/login/oauth/authorize?" + urlencode({
            "client_id": settings.client_id,
            "redirect_uri": settings.callback_url,
            "scope": "read:user",
            "state": state,
        })
        return RedirectResponse(target, status_code=302)

    @router.get("/github/callback")
    def callback(code: str, state: str) -> RedirectResponse:
        if settings is None or oauth is None:
            raise HTTPException(status_code=503, detail="GitHub login is not configured")
        try:
            state_payload = verify_payload(state, settings.session_secret, max_age=600)
            if state_payload.get("purpose") != "github_oauth":
                raise ValueError("wrong state purpose")
            access_token = oauth.exchange_code(code)
            user = oauth.fetch_user(access_token)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail="GitHub login failed") from exc
        session_token = sign_payload({
            "iat": int(time.time()),
            "github_id": int(user["id"]),
            "login": str(user["login"]),
            "avatar_url": user.get("avatar_url"),
        }, settings.session_secret)
        response = RedirectResponse(settings.app_url, status_code=302)
        response.set_cookie(
            "card_in_repo_session",
            session_token,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            secure=settings.secure_cookie,
            samesite="lax",
            path="/",
        )
        return response

    @router.post("/logout", status_code=204)
    def logout() -> RedirectResponse:
        response = RedirectResponse(settings.app_url if settings else "/", status_code=303)
        response.delete_cookie("card_in_repo_session", path="/")
        return response

    return router
