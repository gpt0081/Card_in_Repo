from __future__ import annotations

import base64

import pytest

from card_in_repo_api import github_source
from card_in_repo_api.github_source import GitHubSourceError, parse_public_repository_url, resolve_github_file


def test_repository_url_parser_rejects_non_github_and_nested_urls():
    assert parse_public_repository_url("https://github.com/octo/demo") == ("octo", "demo")
    assert parse_public_repository_url("https://github.com/octo/demo.git") == ("octo", "demo")
    with pytest.raises(GitHubSourceError):
        parse_public_repository_url("https://example.com/octo/demo")
    with pytest.raises(GitHubSourceError):
        parse_public_repository_url("https://github.com/octo/demo/issues/1")


def test_resolve_github_file_pins_content_request_to_commit_sha(monkeypatch):
    sha = "a" * 40
    calls: list[str] = []

    def fake_get_json(url: str) -> dict:
        calls.append(url)
        if url.endswith("/repos/octo/demo"):
            return {"private": False, "default_branch": "main"}
        if "/commits/main" in url:
            return {"sha": sha}
        if "/contents/src/app.py?ref=" in url:
            return {
                "type": "file",
                "encoding": "base64",
                "content": base64.b64encode(b"def run():\n    return 1\n").decode(),
            }
        raise AssertionError(url)

    monkeypatch.setattr(github_source, "_get_json", fake_get_json)
    result = resolve_github_file("https://github.com/octo/demo", "src/app.py")

    assert result.repository == "octo/demo"
    assert result.commit_sha == sha
    assert result.source.startswith("def run")
    assert calls[-1].endswith(f"/contents/src/app.py?ref={sha}")


def test_resolver_rejects_private_repository(monkeypatch):
    monkeypatch.setattr(github_source, "_get_json", lambda _: {"private": True, "default_branch": "main"})
    with pytest.raises(GitHubSourceError, match="private repositories"):
        resolve_github_file("https://github.com/octo/private", "app.py")
