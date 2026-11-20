"""GitHub REST calls for CI that runs without the ``gh`` CLI.

Every scheduled workflow that talks to GitHub used to shell out to ``gh``.
GitHub-hosted runners ship it; the self-hosted Linux runner this repository
targets does not, so the queue janitor, the skills-index probe, the install
E2E red tracker and the docs deploy all died with ``gh: command not found``
before they could do their job. This module speaks the same REST API over
``urllib`` with the token the caller already exports as ``GH_TOKEN``.

``api`` returns the decoded body of one call. ``api_all`` walks every page of
a list endpoint and flattens the ``{"total_count": n, "<kind>": [...]}``
wrapper the API uses for list responses. The CLI at the bottom covers the
three shell call sites that only need one line of glue:

    python3 scripts/ci/gh_rest.py api GET /repos/owner/repo
    python3 scripts/ci/gh_rest.py dispatch deploy-site.yml -f run_id=123
    python3 scripts/ci/gh_rest.py artifact-url 123 skills-index
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

API_BASE = "https://api.github.com"
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


class GitHubError(RuntimeError):
    """A non-2xx answer from the REST API, carrying the server's own message."""


def _token() -> str:
    value = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not value:
        raise GitHubError("GH_TOKEN or GITHUB_TOKEN is required")
    return value


def _open(method: str, url: str, payload: Any | None = None) -> tuple[bytes, Any]:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {_token()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read(), response.headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").strip()
        raise GitHubError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc


def api(method: str, path: str, payload: Any | None = None) -> Any:
    """Call one REST endpoint and return its decoded JSON body (``None`` for 204)."""
    url = path if path.startswith("http") else API_BASE + path
    body, _headers = _open(method, url, payload)
    return json.loads(body) if body else None


def _rows(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # List endpoints carry "total_count"; single objects do not — a repo
        # payload has its own "topics" array, so only treat a dict as a page
        # when the count field marks it as one.
        if "total_count" in payload:
            for value in payload.values():
                if isinstance(value, list):
                    return value
            return []
        return [payload]
    return [payload]


def api_all(path: str) -> list[Any]:
    """GET every page of a list endpoint, following the ``Link`` header."""
    items: list[Any] = []
    url = path if path.startswith("http") else API_BASE + path
    while url:
        body, headers = _open("GET", url)
        items.extend(_rows(json.loads(body) if body else None))
        match = _NEXT_LINK.search(headers.get("Link", ""))
        url = match.group(1) if match else ""
    return items


def _repo(explicit: str | None) -> str:
    repo = explicit or os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        raise GitHubError("GITHUB_REPOSITORY is required")
    return repo


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True) if value is not None else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    call = commands.add_parser("api")
    call.add_argument("method", choices=["GET", "POST", "PATCH", "PUT", "DELETE"])
    call.add_argument("path")
    call.add_argument("--json", default=None, help="Request body as JSON.")

    dispatch = commands.add_parser("dispatch")
    dispatch.add_argument("workflow")
    dispatch.add_argument("--repo", default=None)
    dispatch.add_argument("--ref", default="main")
    dispatch.add_argument("-f", "--field", action="append", default=[], help="key=value input.")

    artifact = commands.add_parser("artifact-url")
    artifact.add_argument("run_id")
    artifact.add_argument("name")
    artifact.add_argument("--repo", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "api":
            _print(api(args.method, args.path, json.loads(args.json) if args.json else None))
        elif args.command == "dispatch":
            inputs = dict(field.split("=", 1) for field in args.field)
            api("POST", f"/repos/{_repo(args.repo)}/actions/workflows/{args.workflow}/dispatches",
                {"ref": args.ref, "inputs": inputs})
            print(f"dispatched {args.workflow}")
        elif args.command == "artifact-url":
            artifacts = api_all(f"/repos/{_repo(args.repo)}/actions/runs/{args.run_id}/artifacts?per_page=100")
            for item in artifacts:
                if item.get("name") == args.name and not item.get("expired"):
                    print(item["archive_download_url"])
                    return 0
            raise GitHubError(f"run {args.run_id} has no unexpired artifact named {args.name!r}")
    except GitHubError as exc:
        print(f"gh_rest: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
