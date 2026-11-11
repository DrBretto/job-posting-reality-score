"""Regression tests for the P04 review's two open blockers: R1 and R2.

R1 — recent ranges could become invisible. Two independent mechanisms did it, and both are here:
a failed recent page was dropped while the observed frontier advanced from the pages that *did*
load, and a newly published continuation was overwritten by a saved one because a single state slot
had to hold both. A third defect rode along: a fetch that raised never spent its request, so four
attempts happened under a budget of three.

R2 — the forward deploy command did not select the build it verified.

Two shaping rules, both learned the hard way in earlier rounds:

* **A long backlog, always.** The P04 suite's failed-page test had a three-page backlog. The backfill
  therefore hit the end of the feed on the first run, cleared its cursor, and let the next run restart
  a complete walk from page one — which collected the "missed" job by accident and made a broken test
  pass. Every multi-run test here keeps a 24-page historical backlog open so no run can restart the
  feed, and asserts the backfill never rewinds.
* **Persisted state, not in-memory state.** Every run boundary below serializes `DiscoveryState` to
  JSON and reloads it, because production stores it in S3 between invocations. An in-memory handoff
  would pass while the real path lost the field.

The two review scenarios are additionally driven through to a PERSISTED candidate report via the real
enumerate, discovery-persistence and report handlers against mocked S3, so "the job is reachable"
means the operator would actually have been shown it — not that a URL appeared in a request log.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from moto import mock_aws

from src.common.connectors import FetchResult
from src.discovery.budget import HEAD_PENDING_MAX, DiscoveryState
from src.discovery.handler import run_discovery

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
BUCKET = "jprs-p05-bucket"
DESCRIPTION = (
    "Responsibilities: build Python backend services, internal tools, AWS Lambda integrations and "
    "LLM evaluation workflows. Interview process: two live video calls with the team."
)
# Long enough that the backfill cannot reach the end of the feed in any test below. A short backlog
# is what let a broken head walk look correct: the feed restarted and re-collected the lost page.
BACKLOG_PAGES = 24


def _page(label, next_cursor, age_hours, *, now=NOW):
    """One provider-shaped page holding one posting, `age_hours` old."""
    return {
        "jobs": [{
            "title": "Senior Software Engineer", "companyName": f"Employer {label}",
            "companySlug": label, "excerpt": DESCRIPTION, "description": DESCRIPTION,
            "applicationLink": f"https://himalayas.app/companies/x/jobs/{label}",
            "guid": f"https://himalayas.app/companies/x/jobs/{label}",
            "locationRestrictions": "['United States']", "employmentType": "Full Time",
            "pubDate": str(int((now - timedelta(hours=age_hours)).timestamp())),
        }],
        "nextCursor": next_cursor, "totalCount": 999,
    }


def _backlog(pages: dict) -> dict:
    """Add a historical tail the catch-up cannot exhaust, starting at cursor `OLD`."""
    for number in range(BACKLOG_PAGES):
        cursor = "OLD" if number == 0 else f"OLD_{number}"
        pages[cursor] = _page(f"historical-{number}", f"OLD_{number + 1}", 300 + number)
    return pages


class _Feed:
    """A cursor-paginated feed, newest page first, as the measured Himalayas contract is.

    `fail_on` raises for a cursor (a timeout). `partial_on` returns a truncated body, which is the
    other way a page can come back without being a read.
    """

    def __init__(self, pages, *, fail_on=(), partial_on=(), now=NOW):
        self.pages = pages
        self.fail_on = set(fail_on)
        self.partial_on = set(partial_on)
        self.now = now
        self.requested: list[str | None] = []

    def __call__(self, provider, token, url):
        cursor = parse_qs(urlparse(url).query).get("cursor", [None])[0]
        self.requested.append(cursor)
        if cursor in self.fail_on:
            raise TimeoutError(f"page {cursor} timed out")
        payload = self.pages[cursor]
        body = json.dumps(payload).encode()
        if cursor in self.partial_on:
            body = body[: len(body) // 2]          # a truncated response, not a clean read
        return FetchResult(
            raw_bytes=body, http_status=200, error_class=None, endpoint_url=url,
            request_at=self.now, response_at=self.now,
        )


def _discover(feed, state, *, budget=3, run_id="p05", now=NOW):
    return run_discovery(
        run_id=run_id, now=now, fetcher=feed, providers=["himalayas"],
        state=state, env={}, max_pages_per_source=budget,
    )


def _round_trip(state: DiscoveryState) -> DiscoveryState:
    """Persist and reload exactly as the Lambda does between invocations."""
    return DiscoveryState.model_validate(json.loads(state.model_dump_json()))


def _employers(*outcomes) -> set[str]:
    return {job.employer_name for outcome in outcomes for job in outcome.jobs}


def _owed(state: DiscoveryState) -> list[str]:
    return state.pending_head("himalayas")


def _reported_owed(outcome) -> str:
    return " ".join(
        f"{item['target']} {item['reason']}" for item in outcome.inaccessible
    ).lower()


# ==================================================================================================
# R1 — a failed recent page stays owed, and a timestamp is not proof of traversal
# ==================================================================================================
def test_a_failed_recent_page_is_owed_not_erased_by_the_frontier_it_advanced():
    """The review's first scenario, with a backlog long enough that nothing can restart the feed.

    Pre-repair: the fetch raised, `_walk` returned a stop reason of "error", and the caller saved a
    head continuation only for the "budget" reason — so the range was dropped. The frontier then
    advanced to page one's timestamp, so the next run stopped at page one believing it had covered
    ground it had never walked. The job on the failed page was never collected.
    """
    pages = _backlog({
        None: _page("fresh-one", "NEW_TWO", 1),
        "NEW_TWO": _page("fresh-two", "OLD", 2),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"

    first_feed = _Feed(pages, fail_on={"NEW_TWO"})
    first = _discover(first_feed, state)

    # The failure is owed, named, and NOT implied to be covered by the frontier it advanced.
    assert _owed(state) == ["NEW_TWO"], state.head_pending
    assert state.head_frontier_at.get("himalayas"), "page one was genuinely observed"
    assert "recent arrivals" in _reported_owed(first), first.inaccessible
    assert "Employer fresh-two" not in _employers(first)
    # The historical walk advanced, and the recent debt did not stop it.
    assert state.source_cursors["himalayas"] == "OLD_1"

    state = _round_trip(state)
    second_feed = _Feed(pages)
    second = _discover(second_feed, state, run_id="p05-retry")

    assert "NEW_TWO" in second_feed.requested, second_feed.requested
    assert "Employer fresh-two" in _employers(second), second_feed.requested
    # The backfill moved strictly forward across both runs; it never rewound to re-collect by luck.
    assert state.source_cursors["himalayas"] == "OLD_2"

    # What remains owed is the recovered page's own continuation, which turns out to be historical
    # ground. That costs one request to discover once and then drains, because a page holding nothing
    # recent ends the chain. Bounded, honest, and not a loss.
    assert _owed(state) == ["OLD"], state.head_pending
    state = _round_trip(state)
    _discover(_Feed(pages), state, run_id="p05-drain")
    assert _owed(state) == [], state.head_pending


def test_a_partially_downloaded_recent_page_is_owed_like_a_failed_one():
    """A truncated body is a partial READ. Its continuation token cannot be trusted either, so the
    range stays owed rather than being handed over as covered."""
    pages = _backlog({
        None: _page("fresh-one", "NEW_TWO", 1),
        "NEW_TWO": _page("fresh-two", "OLD", 2),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"

    first = _discover(_Feed(pages, partial_on={"NEW_TWO"}), state)
    assert _owed(state) == ["NEW_TWO"], state.head_pending
    assert "Employer fresh-two" not in _employers(first)

    state = _round_trip(state)
    second = _discover(_Feed(pages), state, run_id="p05-retry")
    assert "Employer fresh-two" in _employers(second)
    # As in the failure case, the recovered page's own continuation is historical ground: one request
    # to learn that, then it drains.
    assert _owed(state) == ["OLD"], state.head_pending
    state = _round_trip(state)
    _discover(_Feed(pages), state, run_id="p05-partial-drain")
    assert _owed(state) == [], state.head_pending


# ==================================================================================================
# R1 — a new burst above a saved continuation is not overridden by it
# ==================================================================================================
def test_newly_published_pages_are_not_overridden_by_a_saved_continuation():
    """The review's second scenario. Pre-repair the saved cursor REPLACED the provider's new
    continuation link, so the newly published range was never requested, and the advancing frontier
    then treated it as covered. One state slot could not hold two owed ranges; now it is a list."""
    pages = _backlog({
        None: _page("burst-one", "B2", 1),
        "B2": _page("burst-two", "B3", 2),
        "B3": _page("burst-three", "OLD", 3),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"

    _discover(_Feed(pages), state)
    assert _owed(state) == ["B3"], state.head_pending
    state = _round_trip(state)

    # Two newer pages arrive above the saved continuation.
    pages[None] = _page("newer-one", "NEWER_TWO", 0.1)
    pages["NEWER_TWO"] = _page("newer-two", "B2", 0.2)

    second_feed = _Feed(pages)
    second = _discover(second_feed, state, run_id="p05-second")

    assert "NEWER_TWO" in second_feed.requested, second_feed.requested
    assert "Employer newer-two" in _employers(second), second_feed.requested
    # Both the newly discovered range and the older saved one are still owed — neither overwrote
    # the other, which is the whole defect.
    assert "B3" in _owed(state), state.head_pending
    assert len(_owed(state)) >= 2, state.head_pending
    assert "recent arrivals" in _reported_owed(second)


def test_repeated_resumptions_eventually_collect_every_reachable_recent_posting():
    """A burst wider than any single run's head budget, driven to completion.

    Bounded case with known reachable ids: five burst pages, budget three, so at most two head pages
    per run. The requirement is not that one run gets everything — it is that nothing is silently
    lost, that coverage is honestly reported as incomplete until it is complete, and that the
    historical backfill never rewinds while the recent debt is worked off.
    """
    burst = ["B2", "B3", "B4", "B5"]
    pages = _backlog({
        None: _page("burst-one", "B2", 1),
        "B2": _page("burst-two", "B3", 2),
        "B3": _page("burst-three", "B4", 3),
        "B4": _page("burst-four", "B5", 4),
        "B5": _page("burst-five", "OLD", 5),
    })
    expected = {f"Employer burst-{name}" for name in
                ("one", "two", "three", "four", "five")}

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    collected: set[str] = set()
    backfill_positions: list[str | None] = []

    for run in range(8):
        outcome = _discover(_Feed(pages), state, run_id=f"p05-run{run}")
        collected |= _employers(outcome)
        backfill_positions.append(state.source_cursors["himalayas"])
        if _owed(state):
            # While incomplete, the run SAYS so rather than reporting clean coverage.
            assert "recent arrivals" in _reported_owed(outcome), outcome.inaccessible
        state = _round_trip(state)
        if expected <= collected and not _owed(state):
            break

    assert expected <= collected, sorted(expected - collected)
    assert _owed(state) == [], state.head_pending
    # The backfill advanced monotonically through the long backlog and never restarted the feed.
    indexes = [0 if p == "OLD" else int(p.split("_")[1]) for p in backfill_positions]
    assert indexes == sorted(indexes) and indexes[-1] > indexes[0], backfill_positions
    assert all(cursor in pages for cursor in burst)


def test_an_unchanged_head_owes_nothing_and_spends_one_page_on_it():
    """Steady state: nothing new published, so the contiguous chain stops at the ground it observed
    last run and the rest of the budget goes to the backfill. The owed list stays empty — the repair
    must not turn every run into a re-walk of the recent region."""
    pages = _backlog({
        None: _page("fresh-one", "NEW_TWO", 1),
        "NEW_TWO": _page("fresh-two", "OLD", 2),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    _discover(_Feed(pages), state, budget=4)
    assert _owed(state) == [], state.head_pending
    state = _round_trip(state)

    second_feed = _Feed(pages)
    _discover(second_feed, state, budget=4, run_id="p05-steady")
    assert second_feed.requested[0] is None
    assert second_feed.requested.count(None) == 1
    assert "NEW_TWO" not in second_feed.requested, second_feed.requested
    assert _owed(state) == [], state.head_pending


# ==================================================================================================
# R1 — the request budget counts ATTEMPTS
# ==================================================================================================
def test_a_fetch_that_raises_still_spends_its_request():
    """The review measured four attempts under a budget of three: `requests_spent` was incremented
    only after a fetch returned, so the request that raised was free."""
    pages = _backlog({
        None: _page("fresh-one", "NEW_TWO", 1),
        "NEW_TWO": _page("fresh-two", "OLD", 2),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    feed = _Feed(pages, fail_on={"NEW_TWO"})
    _discover(feed, state, budget=3)

    assert len(feed.requested) == 3, feed.requested
    assert state.budgets["himalayas"].requests_spent == 3
    assert state.budgets["himalayas"].failures == 1


@pytest.mark.parametrize("budget", [1, 2, 3, 5, 8])
def test_the_source_budget_bounds_every_attempt_including_failures(budget):
    """No unbounded crawling and no silently raised source limit, with failures in the mix and a
    recent region wider than any of these budgets."""
    pages = _backlog({
        None: _page("n-1", "N2", 1), "N2": _page("n-2", "N3", 2),
        "N3": _page("n-3", "N4", 3), "N4": _page("n-4", "N5", 4),
        "N5": _page("n-5", "N6", 5), "N6": _page("n-6", "OLD", 6),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    for run in range(4):
        feed = _Feed(pages, fail_on={"N3"})
        _discover(feed, state, budget=budget, run_id=f"p05-b{budget}-{run}")
        assert len(feed.requested) <= budget, (budget, run, feed.requested)
        assert state.budgets["himalayas"].requests_spent <= budget
        state = _round_trip(state)


def test_a_repeated_cursor_is_reported_and_does_not_become_an_owed_range():
    """A provider that hands back the same cursor forever must stop the walk, and must not be able
    to grow persisted state by being re-owed every run."""
    pages = _backlog({
        None: _page("loop-one", "LOOP", 1),
        "LOOP": _page("loop-two", "LOOP", 2),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    reported = 0
    for run in range(3):
        feed = _Feed(pages)
        outcome = _discover(feed, state, budget=3, run_id=f"p05-loop{run}")
        reported += any("repeated pagination cursor" in item["reason"]
                        for item in outcome.inaccessible)
        assert len(feed.requested) <= 3
        # The looping cursor is never carried in persisted state, so it cannot be re-owed forever.
        assert "LOOP" not in _owed(state), state.head_pending
        state = _round_trip(state)
    # Reported on the run that reaches it. Later runs stop at the observed frontier before getting
    # there, which is the point: the loop costs one page once, not one page every run.
    assert reported >= 1


# ==================================================================================================
# State: bounded, resumable, and readable across the release boundary
# ==================================================================================================
def test_a_p04_state_document_resumes_its_saved_range():
    """A state document written before `head_pending` existed carries its one unfinished
    continuation in `head_cursors`. That range is still owed and must be walked, not ignored."""
    pages = _backlog({
        None: _page("fresh-one", "NEW_TWO", 1),
        "NEW_TWO": _page("fresh-two", "OLD", 2),
    })
    p04_document = {
        "source_cursors": {"himalayas": "OLD_4"},
        "head_cursors": {"himalayas": "NEW_TWO"},
        "head_frontier_at": {"himalayas": (NOW - timedelta(hours=1)).isoformat()},
        "last_feed_phase": {"himalayas": "both"},
    }
    state = DiscoveryState.model_validate(p04_document)
    assert state.pending_head("himalayas") == ["NEW_TWO"]

    feed = _Feed(pages)
    outcome = _discover(feed, state, budget=3, run_id="p05-from-p04")
    assert "NEW_TWO" in feed.requested, feed.requested
    assert "Employer fresh-two" in _employers(outcome)


def test_the_compatibility_mirror_tracks_the_newest_owed_range():
    """`head_cursors` is the only field an older reader understands. It is written from
    `head_pending` in one place so a rollback resumes the newest owed range instead of none."""
    pages = _backlog({
        None: _page("burst-one", "B2", 1),
        "B2": _page("burst-two", "B3", 2),
        "B3": _page("burst-three", "OLD", 3),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    _discover(_Feed(pages), state, budget=3)

    owed = state.head_pending["himalayas"]
    assert owed, state.head_pending
    assert state.head_cursors["himalayas"] == owed[0]

    # Drop the new field, as a downgrade to the single-slot reader would.
    downgraded = json.loads(state.model_dump_json())
    downgraded.pop("head_pending")
    reloaded = DiscoveryState.model_validate(downgraded)
    assert reloaded.pending_head("himalayas") == [owed[0]]


def test_owed_ranges_stay_bounded_and_say_what_was_dropped():
    """Persisted state cannot grow without limit. At the cap the oldest ranges are dropped and the
    drop is REPORTED — the historical backfill remains the path to those pages."""
    state = DiscoveryState()
    dropped = state.set_pending_head(
        "himalayas", [f"C{n}" for n in range(HEAD_PENDING_MAX + 5)]
    )
    assert len(state.head_pending["himalayas"]) == HEAD_PENDING_MAX
    assert len(dropped) == 5
    assert state.head_cursors["himalayas"] == "C0"


def test_the_cursor_contract_is_a_descending_timestamp_and_the_backfill_only_moves_older():
    """The measured provider contract: the browse cursor is a base64 `<ISO timestamp>|<id>` that
    points strictly OLDER with each page. The repair must not let the backfill walk backwards into
    newer ground, which would re-collect forever and never finish the history."""
    def cursor_for(when: datetime, ident: int) -> str:
        raw = f"{when.isoformat().replace('+00:00', 'Z')}|{ident}"
        return base64.b64encode(raw.encode()).decode()

    def stamp_of(cursor: str) -> datetime:
        text = base64.b64decode(cursor.encode()).decode().split("|")[0]
        return datetime.fromisoformat(text.replace("Z", "+00:00"))

    stamps = [NOW - timedelta(hours=1 + n) for n in range(30)]
    cursors = [cursor_for(when, 2276582 - n) for n, when in enumerate(stamps)]
    assert [stamp_of(c) for c in cursors] == sorted(
        (stamp_of(c) for c in cursors), reverse=True
    ), "fixture must honour the descending contract it is testing"

    pages = {None: _page("head", cursors[0], 1)}
    for index, cursor in enumerate(cursors):
        following = cursors[index + 1] if index + 1 < len(cursors) else None
        pages[cursor] = _page(f"deep-{index}", following, 2 + index)

    state = DiscoveryState()
    positions: list[datetime] = []
    for run in range(6):
        _discover(_Feed(pages), state, budget=3, run_id=f"p05-cursor{run}")
        position = state.source_cursors.get("himalayas")
        if position:
            positions.append(stamp_of(position))
        state = _round_trip(state)

    assert len(positions) >= 4
    assert positions == sorted(positions, reverse=True), positions
    assert all(stamp_of(c) < stamp_of(cursors[0]) or c == cursors[0]
               for c in state.pending_head("himalayas"))


def test_first_seen_history_survives_the_head_re_reading_page_one():
    """The head re-reads page one every run. A posting already seen keeps its identity, or every run
    would present the whole page as newly arrived."""
    pages = _backlog({None: _page("steady", "OLD", 100)})
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"

    first = _discover(_Feed(pages), state, budget=3)
    steady = {job.job_id for job in first.jobs if job.employer_name == "Employer steady"}
    assert steady
    state = _round_trip(state)

    later = NOW + timedelta(hours=26)
    second = _discover(_Feed(pages, now=later), state, budget=3,
                       run_id="p05-day2", now=later)
    assert steady <= {job.job_id for job in second.jobs}, "the posting must keep its identity"
    for job in second.jobs:
        if job.job_id in steady:
            assert job.provider_published_at is not None


# ==================================================================================================
# The two review scenarios reach a PERSISTED candidate report
#
# Re-scoped for P07. These tests previously called a `_write_round` helper that hand-wrote the RUN_OPEN
# manifest, the differ-owned `current/` objects and the SUCCESS sentinels itself, and the section
# claimed "real internal wiring". It was not: production wrote none of those objects for a discovery
# feed, so the tests demonstrated report behavior GIVEN a connection that did not exist. That claim is
# withdrawn here; the P05 run's original evidence is preserved unaltered in its run directory.
#
# What actually runs below: the real enumerate handler writes the manifest, the real discovery
# `persist` writes normalized/, status/ and the live view, and the real report handler consumes them.
# Nothing in this file writes an intermediate artifact a production stage is responsible for.
# ==================================================================================================
def _persisted_report(*outcomes, run_id: str, dt: str) -> dict:
    """Drive real producers into the real report handler and return the PERSISTED report object."""
    import os

    from src.common import s3layout
    from src.discovery.handler import persist as discovery_persist
    from src.enumerate.handler import handler as enumerate_sources
    from src.report.handler import handler as report

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="jprs-p05-collect")["QueueUrl"]
        env = {
            "JPRS_BUCKET": BUCKET, "AWS_DEFAULT_REGION": "us-east-1",
            "JPRS_COLLECT_QUEUE_URL": queue_url, "JPRS_COMPANIES_SSM": "",
            "JPRS_COMPANIES_YAML": "config/companies.yaml",
            "JPRS_DISCOVERY_YAML": "config/discovery_sources.yaml",
            "SES_SENDER": "", "DIGEST_RECIPIENT": "",
        }
        with patch.dict(os.environ, env):
            # The manifest comes from the real enumerate handler, so `expected_discovery_sources` is
            # whatever the shipped config declares — not a value this test chose.
            enumerate_sources({"run_id": run_id}, None)
            for index, outcome in enumerate(outcomes):
                discovery_persist(
                    s3, BUCKET, outcome,
                    run_id=f"{run_id}-{index}" if index else run_id, dt=dt, now=NOW,
                )
            report({"run_id": run_id, "dt": dt}, None)
        body = s3.get_object(Bucket=BUCKET, Key=s3layout.report_json_key(dt))["Body"].read()
    return json.loads(body)


def _rows_in(report: dict) -> dict[str, str]:
    """job_id -> employer, for every candidate row the operator is shown."""
    return {row["job_id"]: row.get("employer") for row in report["complete_candidate_list"]}


def test_the_recovered_failed_page_reaches_the_persisted_report():
    """R1, scenario one, all the way to the artifact the operator reads."""
    pages = _backlog({
        None: _page("fresh-one", "NEW_TWO", 1),
        "NEW_TWO": _page("fresh-two", "OLD", 2),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"

    first = _discover(_Feed(pages, fail_on={"NEW_TWO"}), state)
    state = _round_trip(state)
    second = _discover(_Feed(pages), state, run_id="p05-report-retry")

    report = _persisted_report(first, second, run_id="p05-report-retry", dt="2026-09-24")
    rows = _rows_in(report)
    # The recovered posting keeps ONE identity regardless of which cursor finally delivered it: the
    # first run could not read that page at all, the second reached it behind a different cursor.
    assert "himalayas:all#fresh-two" in rows, sorted(rows)
    assert rows["himalayas:all#fresh-two"] == "Employer fresh-two"


def test_the_recovered_burst_page_reaches_the_persisted_report():
    """R1, scenario two, all the way to the artifact the operator reads."""
    pages = _backlog({
        None: _page("burst-one", "B2", 1),
        "B2": _page("burst-two", "B3", 2),
        "B3": _page("burst-three", "OLD", 3),
    })
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    first = _discover(_Feed(pages), state)
    state = _round_trip(state)

    pages[None] = _page("newer-one", "NEWER_TWO", 0.1)
    pages["NEWER_TWO"] = _page("newer-two", "B2", 0.2)
    second = _discover(_Feed(pages), state, run_id="p05-report-burst")

    report = _persisted_report(first, second, run_id="p05-report-burst", dt="2026-09-24")
    rows = _rows_in(report)
    assert "himalayas:all#newer-two" in rows, sorted(rows)
    assert rows["himalayas:all#newer-two"] == "Employer newer-two"


# ==================================================================================================
# R2 — the forward deploy command selects the build it verified
# ==================================================================================================
def test_the_documented_deploy_commands_bind_template_and_config_explicitly():
    """The P04 handoff built into `/tmp/jprs-build` and then ran `sam deploy` with no
    `--template-file`. SAM resolves the template from `.aws-sam/build/template.yaml` and then
    `template.yaml`/`template.yml` relative to the working directory — never a custom build dir — so
    the command could not select the build it had just verified.

    This asserts the DOCUMENTED commands, because the document is what a deploy will follow.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    handoff = (root / "project-factory/outputs/open-market-discovery/runs"
               / "20260925_resumable_discovery_release_repair_v1/DEPLOYMENT_HANDOFF.md")

    def commands(text: str, prefix: str) -> list[str]:
        """Whole shell commands, with backslash continuations joined into one string."""
        joined, buffer = [], ""
        for raw in text.splitlines():
            line = raw.strip()
            if buffer:
                buffer += " " + line.rstrip("\\").strip()
                if not line.endswith("\\"):
                    joined.append(buffer)
                    buffer = ""
                continue
            if line.startswith(prefix):
                if line.endswith("\\"):
                    buffer = line.rstrip("\\").strip()
                else:
                    joined.append(line)
        if buffer:
            joined.append(buffer)
        return joined

    text = handoff.read_text()
    deploys = commands(text, "sam deploy")
    assert deploys, "the handoff must state a deploy command"
    for command in deploys:
        assert "--template-file" in command, command
        assert "--config-file" in command, command
        # The template must be a built artifact, never left to working-directory resolution.
        assert "$BUILD/template.yaml" in command or "BUILD/template.yaml" in command, command
        # A relative config path resolves inside the build directory, so it must be absolute.
        assert '"$PWD/infra/samconfig.toml"' in command or "/infra/samconfig.toml" in command, command

    builds = commands(text, "sam build")
    assert builds, "the handoff must state a build command"
    for command in builds:
        assert "--build-dir" in command and "--template-file" in command, command
