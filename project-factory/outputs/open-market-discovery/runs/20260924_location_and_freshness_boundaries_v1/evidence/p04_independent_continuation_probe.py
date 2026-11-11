from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from src.common.connectors import FetchResult
from src.discovery.budget import DiscoveryState
from src.discovery.handler import run_discovery

NOW = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)


def page(label, next_cursor, age_hours):
    description = (
        "Responsibilities: build Python backend services, internal tools, AWS Lambda integrations "
        "and LLM evaluation workflows. Interview process: two live video calls with the team."
    )
    return {
        "jobs": [{
            "title": "Senior Software Engineer", "companyName": f"Employer {label}",
            "companySlug": label, "excerpt": description, "description": description,
            "applicationLink": f"https://himalayas.app/companies/x/jobs/{label}",
            "guid": f"https://himalayas.app/companies/x/jobs/{label}",
            "locationRestrictions": "['United States']", "employmentType": "Full Time",
            "pubDate": str(int((NOW - timedelta(hours=age_hours)).timestamp())),
        }],
        "nextCursor": next_cursor, "totalCount": 999,
    }


class Feed:
    def __init__(self, pages, fail_on=()):
        self.pages = pages
        self.fail_on = set(fail_on)
        self.requested = []

    def __call__(self, provider, token, url):
        cursor = parse_qs(urlparse(url).query).get("cursor", [None])[0]
        self.requested.append(cursor)
        if cursor in self.fail_on:
            raise TimeoutError(f"page {cursor} timed out")
        return FetchResult(
            raw_bytes=json.dumps(self.pages[cursor]).encode(), http_status=200,
            error_class=None, endpoint_url=url, request_at=NOW, response_at=NOW,
        )


def discover(feed, state, run_id):
    return run_discovery(
        run_id=run_id, now=NOW, fetcher=feed, providers=["himalayas"],
        state=state, env={}, max_pages_per_source=3,
    )


def fixture():
    pages = {
        None: page("fresh-one", "NEW_TWO", 1),
        "NEW_TWO": page("fresh-two", "OLD", 2),
    }
    for number in range(20):
        cursor = "OLD" if number == 0 else f"OLD_{number}"
        pages[cursor] = page(f"historical-{number}", f"OLD_{number + 1}", 300 + number)
    return pages


def failed_page_case():
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    pages = fixture()
    first = Feed(pages, fail_on={"NEW_TWO"})
    discover(first, state, "failure-first")
    first_state = state.model_dump(mode="json")
    second = Feed(pages)
    result = discover(second, state, "failure-retry")
    return {
        "first_requests": first.requested,
        "head_cursor_after_failure": first_state["head_cursors"],
        "frontier_after_failure": first_state["head_frontier_at"],
        "second_requests": second.requested,
        "missing_fresh_job": "Employer fresh-two" not in {job.employer_name for job in result.jobs},
        "attempts_exceed_budget": len(first.requested) > 3,
    }


def new_burst_case():
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    pages = fixture()
    pages[None] = page("burst-one", "B2", 1)
    pages["B2"] = page("burst-two", "B3", 2)
    pages["B3"] = page("burst-three", "OLD", 3)
    first = Feed(pages)
    discover(first, state, "burst-first")
    saved_before_second = state.head_cursors.get("himalayas")
    pages[None] = page("newer-one", "NEWER_TWO", 0.1)
    pages["NEWER_TWO"] = page("newer-two", "B2", 0.2)
    second = Feed(pages)
    second_result = discover(second, state, "burst-second")
    third = Feed(pages)
    third_result = discover(third, state, "burst-third")
    collected = {job.employer_name for job in second_result.jobs + third_result.jobs}
    return {
        "first_requests": first.requested,
        "saved_before_second": saved_before_second,
        "second_requests": second.requested,
        "third_requests": third.requested,
        "missing_fresh_job": "Employer newer-two" not in collected,
    }


if __name__ == "__main__":
    print(json.dumps({
        "scope": "synthetic feed payloads through real run_discovery; no network or AWS",
        "failed_second_page": failed_page_case(),
        "new_burst_during_resume": new_burst_case(),
    }, indent=2))
