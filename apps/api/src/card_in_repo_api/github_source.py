from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


class GitHubSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubSource:
    repository: str
    commit_sha: str
    path: str
    source: str


@dataclass(frozen=True)
class GitHubRepositorySnapshot:
    repository: str
    commit_sha: str
    files: dict[str, str]


SUPPORTED_SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")


def _request_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Card-in-Repo/0.1", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.getenv("CARD_IN_REPO_GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str) -> dict:
    request = Request(url, headers=_request_headers())
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubSourceError(f"GitHub source request failed: {exc}") from exc


def parse_public_repository_url(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitHubSourceError("repository_url must be an https://github.com public repository URL")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise GitHubSourceError("repository_url must identify exactly one repository")
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        raise GitHubSourceError("repository_url must identify exactly one repository")
    return owner, repo


def _resolve_repository(repository_url: str, ref: str | None) -> tuple[str, str, str, str]:
    owner, repo = parse_public_repository_url(repository_url)
    repository = f"{owner}/{repo}"
    base = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
    repo_meta = _get_json(base)
    if repo_meta.get("private"):
        raise GitHubSourceError("private repositories are not supported in the public-repo MVP")
    requested_ref = ref or repo_meta.get("default_branch")
    if not requested_ref:
        raise GitHubSourceError("GitHub did not provide a default branch")
    commit = _get_json(f"{base}/commits/{quote(str(requested_ref), safe='')}")
    commit_sha = commit.get("sha")
    if not isinstance(commit_sha, str) or len(commit_sha) != 40:
        raise GitHubSourceError("GitHub did not return an immutable commit SHA")
    return repository, base, commit_sha, owner


def _decode_blob(data: dict, path: str) -> str:
    if data.get("encoding") != "base64":
        raise GitHubSourceError(f"GitHub blob is not base64 encoded: {path}")
    try:
        return base64.b64decode(data["content"], validate=False).decode("utf-8")
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise GitHubSourceError(f"GitHub file is not valid UTF-8 source: {path}") from exc


def resolve_github_repository(repository_url: str, ref: str | None = None, *, max_files: int = 200, max_total_bytes: int = 2_000_000) -> GitHubRepositorySnapshot:
    """Fetch a bounded immutable snapshot of supported MVP source files from a public repo."""
    repository, base, commit_sha, _ = _resolve_repository(repository_url, ref)
    tree = _get_json(f"{base}/git/trees/{commit_sha}?recursive=1")
    if tree.get("truncated"):
        raise GitHubSourceError("GitHub repository tree was truncated; refusing an incomplete analysis")
    entries = [
        item
        for item in tree.get("tree", [])
        if item.get("type") == "blob" and str(item.get("path", "")).lower().endswith(SUPPORTED_SOURCE_SUFFIXES)
    ]
    entries.sort(key=lambda item: item["path"])
    if not entries:
        raise GitHubSourceError("repository contains no supported Python/JavaScript/TypeScript files")
    if len(entries) > max_files:
        raise GitHubSourceError(f"repository exceeds supported source file limit ({max_files})")
    declared_size = sum(int(item.get("size") or 0) for item in entries)
    if declared_size > max_total_bytes:
        raise GitHubSourceError(f"repository exceeds supported source size ({max_total_bytes} bytes)")
    files: dict[str, str] = {}
    actual_size = 0
    for item in entries:
        path = item["path"]
        source = _decode_blob(_get_json(f"{base}/git/blobs/{item['sha']}"), path)
        actual_size += len(source.encode("utf-8"))
        if actual_size > max_total_bytes:
            raise GitHubSourceError(f"repository exceeds supported source size ({max_total_bytes} bytes)")
        files[path] = source
    return GitHubRepositorySnapshot(repository=repository, commit_sha=commit_sha, files=files)


def resolve_github_file(repository_url: str, path: str, ref: str | None = None) -> GitHubSource:
    """Resolve one public GitHub file to immutable source pinned by commit SHA."""
    repository, base, commit_sha, _ = _resolve_repository(repository_url, ref)
    clean_path = path.strip("/")
    if not clean_path or clean_path != path.strip("/") or ".." in clean_path.split("/"):
        raise GitHubSourceError("path must be a repository-relative file path")
    file_data = _get_json(f"{base}/contents/{quote(clean_path, safe='/')}?ref={commit_sha}")
    if file_data.get("type") != "file":
        raise GitHubSourceError("path did not resolve to a GitHub file")
    source = _decode_blob(file_data, clean_path)
    return GitHubSource(repository=repository, commit_sha=commit_sha, path=clean_path, source=source)
