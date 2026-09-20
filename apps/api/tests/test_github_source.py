from __future__ import annotations

import base64
import pytest
from card_in_repo_api import github_source
from card_in_repo_api.github_source import GitHubSourceError, parse_public_repository_url, resolve_github_file, resolve_github_repository


def test_repository_url_parser_rejects_non_github_and_nested_urls():
    assert parse_public_repository_url("https://github.com/octo/demo") == ("octo", "demo")
    assert parse_public_repository_url("https://github.com/octo/demo.git") == ("octo", "demo")
    with pytest.raises(GitHubSourceError):
        parse_public_repository_url("https://example.com/octo/demo")
    with pytest.raises(GitHubSourceError):
        parse_public_repository_url("https://github.com/octo/demo/issues/1")


def test_request_headers_add_optional_github_token(monkeypatch):
    monkeypatch.delenv("CARD_IN_REPO_GITHUB_TOKEN", raising=False)
    assert "Authorization" not in github_source._request_headers()
    monkeypatch.setenv("CARD_IN_REPO_GITHUB_TOKEN", "fixture-token")
    assert github_source._request_headers()["Authorization"] == "Bearer fixture-token"


def test_resolve_github_file_pins_content_request_to_commit_sha(monkeypatch):
    sha = "a" * 40
    calls: list[str] = []
    def fake_get_json(url: str) -> dict:
        calls.append(url)
        if url.endswith("/repos/octo/demo"): return {"private": False, "default_branch": "main"}
        if "/commits/main" in url: return {"sha": sha}
        if "/contents/src/app.py?ref=" in url: return {"type": "file", "encoding": "base64", "content": base64.b64encode(b"def run():\n    return 1\n").decode()}
        raise AssertionError(url)
    monkeypatch.setattr(github_source, "_get_json", fake_get_json)
    result = resolve_github_file("https://github.com/octo/demo", "src/app.py")
    assert result.commit_sha == sha
    assert calls[-1].endswith(f"/contents/src/app.py?ref={sha}")


def test_repository_snapshot_uses_commit_tree_and_sorted_supported_blobs(monkeypatch):
    sha = "b" * 40
    def encoded(text: str) -> dict: return {"encoding": "base64", "content": base64.b64encode(text.encode()).decode()}
    def fake_get_json(url: str) -> dict:
        if url.endswith("/repos/octo/demo"): return {"private": False, "default_branch": "main"}
        if "/commits/main" in url: return {"sha": sha}
        if f"/git/trees/{sha}?recursive=1" in url: return {"truncated": False, "tree": [
            {"type": "blob", "path": "z.tsx", "sha": "z", "size": 8},
            {"type": "blob", "path": "README.md", "sha": "r", "size": 5},
            {"type": "blob", "path": "web/main.js", "sha": "j", "size": 8},
            {"type": "blob", "path": "a.py", "sha": "a", "size": 8},
        ]}
        if url.endswith("/git/blobs/a"): return encoded("def a(): pass\n")
        if url.endswith("/git/blobs/j"): return encoded("function boot() {}\n")
        if url.endswith("/git/blobs/z"): return encoded("export const App = () => null;\n")
        raise AssertionError(url)
    monkeypatch.setattr(github_source, "_get_json", fake_get_json)
    snapshot = resolve_github_repository("https://github.com/octo/demo")
    assert snapshot.commit_sha == sha
    assert list(snapshot.files) == ["a.py", "web/main.js", "z.tsx"]


def test_repository_snapshot_rejects_truncated_tree(monkeypatch):
    sha = "c" * 40
    def fake_get_json(url: str) -> dict:
        if url.endswith("/repos/octo/demo"): return {"private": False, "default_branch": "main"}
        if "/commits/main" in url: return {"sha": sha}
        return {"truncated": True, "tree": []}
    monkeypatch.setattr(github_source, "_get_json", fake_get_json)
    with pytest.raises(GitHubSourceError, match="truncated"):
        resolve_github_repository("https://github.com/octo/demo")


def test_resolver_rejects_private_repository(monkeypatch):
    monkeypatch.setattr(github_source, "_get_json", lambda _: {"private": True, "default_branch": "main"})
    with pytest.raises(GitHubSourceError, match="private repositories"):
        resolve_github_file("https://github.com/octo/private", "app.py")
