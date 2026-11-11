from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from src.candidate.screening import screen_job
from src.common.connectors import FetchResult
from src.common.models import CanonicalJob, IdKind, RemoteMode
from src.discovery.handler import _live_fetcher, run_discovery


class EmptyResponse:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"results": []}'


def emit(name, data):
    print(json.dumps({"probe": name, **data}))


def main():
    now = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
    requested = []

    def capture_request(request, **kwargs):
        requested.append(parse_qs(urlparse(request.full_url).query, keep_blank_values=True))
        return EmptyResponse()

    with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen", capture_request):
        run_discovery(
            run_id="review", now=now, fetcher=_live_fetcher, providers=["adzuna"],
            env={"ADZUNA_APP_ID": "FAKE_ID", "ADZUNA_APP_KEY": "FAKE_KEY"},
            max_pages_per_source=1,
        )
    emit("actual_http_boundary", {
        "request_count": len(requested), "app_id": requested[0].get("app_id"),
        "app_key": requested[0].get("app_key"), "network": "mocked at urlopen",
    })

    cases = [
        "Interview process: A recorded video introduction is optional. "
        "You may instead have a live video call with the team.",
        "Interview process: We do not require a recorded video introduction. "
        "You must complete a one-way video interview in the final round.",
        "Requirements: No security clearance is required. "
        "You must pass a drug screening before starting.",
        "Responsibilities: You will build tools for the sales team and carry a sales quota.",
    ]
    for index, description in enumerate(cases):
        job = CanonicalJob(
            source_id="review:test", job_id=f"review:test#{index}", id_kind=IdKind.NATIVE_ID,
            title="Senior Software Engineer", description_text=description,
            raw_location="Remote, US", canonical_location="remote, us",
            remote_hybrid_language=RemoteMode.REMOTE,
        )
        result = screen_job(job)
        emit("screening", {
            "text": description, "outcome": str(result.outcome),
            "excluded": [hit.rule_id for hit in result.exclusions],
            "suppressed": [hit.rule_id for hit in result.suppressed],
        })

    previous = types.ModuleType("review_deployed_models")
    sys.modules[previous.__name__] = previous
    exec(subprocess.check_output(
        ["git", "show", "e549a73:src/common/models.py"], text=True,
    ), previous.__dict__)
    current = CanonicalJob(
        source_id="greenhouse:test", job_id="greenhouse:test#1", id_kind=IdKind.NATIVE_ID,
        title="Software Engineer",
    )
    try:
        previous.CanonicalJob.model_validate(current.model_dump(mode="json"))
        emit("rollback_reader", {"accepts_current_record": True})
    except Exception as error:
        emit("rollback_reader", {
            "accepts_current_record": False,
            "rejected_fields": [item["loc"][0] for item in error.errors()],
        })

    pages_requested = []

    def feed_fetcher(provider, token, url):
        pages_requested.append(token)
        payload = {
            "jobs": [],
            "nextCursor": {"all": "OLDER_PAGE_2", "OLDER_PAGE_2": "OLDER_PAGE_3"}.get(token),
        }
        return FetchResult(
            raw_bytes=json.dumps(payload).encode(), http_status=200, error_class=None,
            endpoint_url=url, request_at=now, response_at=now,
        )

    first = run_discovery(
        run_id="day1", now=now, fetcher=feed_fetcher, providers=["himalayas"],
        env={}, max_pages_per_source=1,
    )
    pages_requested.clear()
    run_discovery(
        run_id="day2", now=now + timedelta(days=1), fetcher=feed_fetcher,
        providers=["himalayas"], env={}, max_pages_per_source=1, state=first.state,
    )
    emit("fresh_head", {
        "day2_requests": pages_requested, "head_rechecked": "all" in pages_requested,
    })


if __name__ == "__main__":
    main()
