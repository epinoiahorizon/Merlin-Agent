"""The self-hosted CI runner has no ``gh``; every GitHub call is plain REST.

The queue janitor, the skills-index watchdog, the install-E2E red tracker and
the docs deploy all used to shell out to ``gh`` and died with
``gh: command not found`` on the self-hosted runner. ``scripts/ci/gh_rest.py``
replaces it. The two contracts worth pinning are the ones every caller relies
on: pagination follows the ``Link`` header and flattens the API's list wrapper,
and an error carries the server's own message instead of a bare status code.
"""

from __future__ import annotations

import io
import urllib.error

import pytest

from scripts.ci.gh_rest import GitHubError, _rows, api, api_all


def test_api_all_follows_link_header_and_flattens_list_wrappers(monkeypatch):
    calls: list[str] = []
    pages = [
        (b'{"total_count": 3, "workflow_runs": [{"id": 1}, {"id": 2}]}',
         {"Link": '<https://api.github.com/next?page=2>; rel="next"'}),
        (b'{"total_count": 3, "workflow_runs": [{"id": 3}]}', {}),
    ]

    def fake_open(method, url, payload=None):
        calls.append(url)
        return pages[len(calls) - 1]

    monkeypatch.setattr("scripts.ci.gh_rest._open", fake_open)
    assert api_all("/repos/o/r/actions/runs") == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert len(calls) == 2


def test_api_raises_the_server_message_on_http_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 404, "Not Found", {},
            io.BytesIO(b'{"message": "Not Found", "status": "404"}'),
        )

    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(GitHubError, match="HTTP 404"):
        api("GET", "/repos/o/r/pages")


def test_rows_keeps_a_bare_object_even_when_it_holds_a_list():
    # A repo payload has a top-level "topics" array; it is still one object,
    # not a page of rows (queue-janitor reads [0]["default_branch"] from it).
    assert _rows({"default_branch": "main", "topics": ["agent"]}) == [
        {"default_branch": "main", "topics": ["agent"]}
    ]
    assert _rows({"total_count": 1, "workflow_runs": [{"id": 1}]}) == [{"id": 1}]
    assert _rows(None) == []
