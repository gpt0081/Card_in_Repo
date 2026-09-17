from __future__ import annotations

import base64
import json
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


def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Card-in-Repo/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
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


def resolve_github_file(repository_url: str, path: str, ref: str | None = None) -> GitHubSource:
    """Resolve one public GitHub file to immutable source pinned by commit SHA.

    URLs are parsed, never fetched directly. Network requests are generated only for
    api.github.com, which keeps this boundary closed to arbitrary-host SSRF.
    """
    owner, repo = parse_public_repository_url(repository_url)
    repository = f"{owner}/{repo}"
    repo_meta = _get_json(f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}")
    if repo_meta.get("private"):
        raise GitHubSourceError("private repositories are not supported in the public-repo MVP")

    requested_ref = ref or repo_meta.get("default_branch")
    if not requested_ref:
        raise GitHubSourceError("GitHub did not provide a default branch")
    commit = _get_json(
        f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/commits/{quote(str(requested_ref), safe='')}"
    )
    commit_sha = commit.get("sha")
    if not isinstance(commit_sha, str) or len(commit_sha) != 40:
        raise GitHubSourceError("GitHub did not return an immutable commit SHA")

    clean_path = path.strip("/")
    if not clean_path or clean_path != path.strip("/") or ".." in clean_path.split("/"):
        raise GitHubSourceError("path must be a repository-relative file path")
    file_data = _get_json(
        f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/contents/{quote(clean_path, safe='/')}?ref={commit_sha}"
    )
    if file_data.get("type") != "file" or file_data.get("encoding") != "base64":
        raise GitHubSourceError("path did not resolve to a base64-encoded GitHub file")
    try:
        source = base64.b64decode(file_data["content"], validate=False).decode("utf-8")
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise GitHubSourceError("GitHub file is not valid UTF-8 source") from exc
    return GitHubSource(repository=repository, commit_sha=commit_sha, path=clean_path, source=source)
