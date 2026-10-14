"""Read PR submission files and upsert the evaluation comment."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any

from .result import RESULT_MARKER, format_comment


def _token() -> str:
    return os.environ.get("SUBMISSION_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _request(method: str, url: str, body: dict[str, Any] | None = None) -> Any:
    token = _token()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "langraph-actions-poc-evaluator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} failed: {exc.code} {detail}") from exc


def parse_repo(submission_repo: str) -> tuple[str, str]:
    parts = submission_repo.strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"submission_repo must be owner/name, got {submission_repo!r}")
    return parts[0], parts[1]


def get_pull_request(submission_repo: str, pr_number: int) -> dict[str, Any]:
    owner, repo = parse_repo(submission_repo)
    return _request("GET", f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}")


def fetch_file_at_ref(submission_repo: str, path: str, ref: str) -> str:
    owner, repo = parse_repo(submission_repo)
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    payload = _request("GET", url)
    if isinstance(payload, list):
        raise RuntimeError(f"Expected file at {path}, got directory")
    encoding = payload.get("encoding")
    content = payload.get("content") or ""
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8")
    return str(content)


def fetch_submission_files(
    submission_repo: str,
    *,
    head_sha: str,
    paths: list[str],
) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in paths:
        files[path] = fetch_file_at_ref(submission_repo, path, head_sha)[:12000]
    return files


def upsert_evaluation_comment(submission_repo: str, pr_number: int, result: dict[str, Any]) -> dict[str, Any]:
    owner, repo = parse_repo(submission_repo)
    body = format_comment(result)
    comments = _request("GET", f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments?per_page=100")
    existing = None
    for comment in comments or []:
        if RESULT_MARKER in (comment.get("body") or ""):
            existing = comment
            break
    if existing:
        return _request(
            "PATCH",
            f"https://api.github.com/repos/{owner}/{repo}/issues/comments/{existing['id']}",
            {"body": body},
        )
    return _request(
        "POST",
        f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
        {"body": body},
    )
