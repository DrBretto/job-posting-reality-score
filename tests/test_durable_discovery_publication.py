"""P08 regressions: an interrupted publication owes its observations instead of losing them.

What this file is for
---------------------
P07 connected discovery to the morning report. Its review then reproduced the remaining defect with
an independent probe: `persist` committed `raw/`, `normalized/`, `status/`, the SUCCESS sentinel,
coverage and traversal state, and only THEN wrote the live view the report reads. One storage failure
at that last write stranded a posting that was already durably captured — the same-run retry met a
changed feed window, overwrote `normalized/` for the same `dt`, and the job reached no report, ever.

Every case below injects that failure at the ACTUAL external storage boundary, by refusing one
`PutObject` inside the mocked AWS client, and then drives the real stages across rounds. The producer
writes every intermediate record; this file supplies only provider bytes, exactly as the outside world
does. `test_no_intermediate_record_in_these_cases_is_written_by_this_test` asserts that structurally
rather than asking to be believed.

What these tests establish
--------------------------
  - an already-captured observation survives a failed publication and reaches a later report without
    the provider returning the job again
  - the debt is visible in the coverage receipt and in the rendered report while it is outstanding
  - replay is idempotent: no duplicate row, no inflated observation history, no rolled-back newer
    observation, no damage to another feed's committed work
  - a failure between committing a view and clearing its debt is absorbed by the next round

What they do NOT establish
--------------------------
  - anything about real S3. `moto` grants every permission, so these prove the code's behavior under
    a refused write, not the IAM policy or S3's own semantics. The declared grants are checked
    separately, against the real template, in `test_discovery_to_report_integration.py`.
  - anything about the live market. Every payload here is synthetic, written to control one variable.
    The insurance-company role is a test control and never a vacancy to apply to.
  - anything about a concurrent second writer. Discovery is one scheduled stage doing read-modify-write
    on its own objects, which is the profile `_discovery_state.json` already has; nothing here tests
    two simultaneous discovery invocations, and nothing here makes that safe.
  - real-world durability of `raw/`. A dropped batch is said to be recoverable from `raw/` by hand;
    that path is stated in the receipt, not exercised here.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from botocore.client import BaseClient
from moto import mock_aws

from src.common import s3layout
from src.discovery.connectors import get_discovery_connector
from src.discovery.live import MAX_OWED_BATCHES_PER_PROVIDER

from tests.test_discovery_to_report_integration import (
    BUCKET,
    UNREGISTERED_FIT,
    Harness,
    _feed_payload,
    _fetch_result,
    _single_page_fetcher,
)

FIRST_RUN = "2026-09-25"
NEXT_RUN = "2026-09-26"
LIVE_KEY = s3layout.discovery_live_key("himalayas")
PENDING_KEY = s3layout.discovery_pending_publication_key()

# A second employer on a second feed, so the multi-provider cases are a genuine partial write rather
# than one feed observed twice. SYNTHETIC control.
REMOTIVE_FIT = {
    "id": 77701,
    "company_name": "Winnipesaukee Mutual Benefit",
    "title": "Senior Software Engineer, Platform Automation",
    "url": "https://remotive.com/remote-jobs/software-dev/platform-automation-77701",
    "description": (
        "We are a regional benefits administrator, not a software company. Build and maintain Python "
        "backend services and TypeScript internal applications, own AWS Lambda integrations, and "
        "stand up LLM evaluation workflows. Remote throughout the United States. Interview process: "
        "two live video calls with the engineering team."
    ),
    "candidate_required_location": "USA",
    "job_type": "full_time",
    "category": "Software Development",
    "publication_date": "2026-09-25T10:00:00",
}


@pytest.fixture
def harness():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="jprs-p08-collect")["QueueUrl"]
        h = Harness(s3, queue_url)
        h.sqs = sqs
        yield h


# --------------------------------------------------------------------------------------------------
# Fault injection at the real external-storage boundary
# --------------------------------------------------------------------------------------------------
class RefuseOnePut:
    """Refuse one `PutObject` to a named key, optionally only after another key has been written.

    The refusal happens inside the boto3 client, so the failing call is the one the production code
    actually makes. `arm_after` is how the narrow window between committing a view and clearing its
    debt is reached: nothing else can place a failure between two consecutive writes.
    """

    def __init__(self, key: str, *, arm_after: str | None = None):
        self.key = key
        self.arm_after = arm_after
        self.armed = arm_after is None
        self.injected: list[str] = []
        self.failure: str | None = None
        self._original = BaseClient._make_api_call

    def __call__(self, client, operation, parameters):
        if operation == "PutObject" and parameters.get("Key") == self.arm_after:
            self.armed = True
        if (
            self.armed and not self.injected
            and operation == "PutObject" and parameters.get("Key") == self.key
        ):
            self.injected.append(self.key)
            raise TimeoutError(f"P08-injected storage failure writing {self.key}")
        return self._original(client, operation, parameters)

    def patch(self):
        # Wrapped in a plain function on purpose: an instance assigned to the class attribute is not
        # a descriptor, so boto3's `self._make_api_call(...)` would never pass the client through.
        injector = self

        def _make_api_call(client, operation, parameters):
            return injector(client, operation, parameters)

        return patch.object(BaseClient, "_make_api_call", _make_api_call)


def _discover_through(harness, injector, run_id, *, fetcher, providers="himalayas"):
    """Run the real discovery handler with one storage write refused; return the raised error."""
    with injector.patch():
        try:
            harness.discover(run_id, fetcher=fetcher, providers=providers)
        except TimeoutError as error:
            injector.failure = str(error)
    assert injector.injected, "the injected failure never fired; the test proves nothing"
    assert injector.failure, "discovery swallowed the storage failure instead of surfacing it"
    return injector.failure


def _read(harness, key: str, default=None):
    import botocore.exceptions

    try:
        return json.loads(harness.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except botocore.exceptions.ClientError:
        return default


def _pending(harness) -> dict:
    return (_read(harness, PENDING_KEY, default={}) or {}).get("batches", {})


def _owed_job_ids(harness, provider: str) -> list[str]:
    return sorted(
        job["job_id"]
        for batch in _pending(harness).get(provider, []) for job in batch["jobs"]
    )


def _live_record(harness, provider: str, job_id: str) -> dict:
    view = _read(harness, s3layout.discovery_live_key(provider), default={"jobs": {}})
    return view["jobs"][job_id]


def _discovery_rows(report: dict) -> list[dict]:
    return [
        row for row in report["complete_candidate_list"]
        if row["source_kind"] == "DISCOVERY_FEED"
    ]


def _two_feeds(provider, token, url):
    if provider == "remotive":
        return _fetch_result({"jobs": [REMOTIVE_FIT]}, url)
    return _fetch_result(_feed_payload([UNREGISTERED_FIT]), url)


HIMALAYAS_JOB = "himalayas:all#internal-tools"


# ==================================================================================================
# Case 1 — the interrupted round owes what it captured
# ==================================================================================================
def test_an_interrupted_publication_owes_the_captured_job_instead_of_losing_it(harness):
    """The failure is surfaced, and the observation is recorded as owed by the producer itself.

    Establishes that the debt exists and names the job. It does NOT yet establish recovery; cases 2
    and 3 do that, and they are separate because a ledger nothing drains would be worse than useless.
    """
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(LIVE_KEY), FIRST_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )

    # Captured durably, as the review established: this is not a recovery of bytes never saved.
    assert HIMALAYAS_JOB in harness.normalized_job_ids()
    # And now owed, by key and by job id.
    assert _owed_job_ids(harness, "himalayas") == [HIMALAYAS_JOB], _pending(harness)
    # The view itself never committed, so nothing claims the posting is published.
    assert _read(harness, LIVE_KEY) is None

    coverage = _read(harness, s3layout.discovery_coverage_key(FIRST_RUN))
    # Coverage still records the fetch success honestly — it did succeed — but it can no longer read
    # as a complete round, because the same receipt says the posting is waiting to be published.
    assert "himalayas" in coverage["discovery_succeeded"]
    assert HIMALAYAS_JOB in coverage["pending_publication"]["himalayas"][0]["job_ids"]
    assert any(
        HIMALAYAS_JOB in entry.get("job_ids", []) for entry in coverage["inaccessible"]
    ), coverage["inaccessible"]


def test_the_interrupted_round_report_says_the_posting_is_captured_but_unpublished(harness):
    """The morning report distinguishes "nothing qualified" from "something is owed to you".

    This is the invariant that stops the repair from being invisible: an operator reading the report
    on the interrupted morning must be able to tell that a posting is missing for a storage reason and
    not because the search or the screener rejected it.
    """
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(LIVE_KEY), FIRST_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )
    harness.diff_monitored(FIRST_RUN)
    harness.report(FIRST_RUN)

    report = harness.saved_report(FIRST_RUN)
    # The posting genuinely cannot be shown yet — that is the honest state, not a defect.
    assert _discovery_rows(report) == []
    coverage = report["coverage"]
    assert coverage["pending_publication_job_count"] == 1, coverage
    axes = report["health_axes"]
    assert axes["discovery_coverage"] == "PARTIAL", axes
    assert "awaiting publication" in axes["discovery_coverage_detail"], axes

    markdown = harness.saved_markdown(FIRST_RUN)
    assert "captured but not yet published" in markdown, markdown
    # The monitored population is untouched by the discovery-side failure.
    assert [row for row in report["complete_candidate_list"]
            if row["source_kind"] == "ATS_BOARD"], report["complete_candidate_list"]


# ==================================================================================================
# Case 2 — recovery, with the feed no longer offering the job
# ==================================================================================================
def test_the_same_run_retry_publishes_the_owed_job_from_an_empty_feed(harness):
    """The retry's feed window no longer holds the posting, and it is published anyway.

    This is the exact shape the reviewer's probe measured. An empty feed is used deliberately: if the
    retry could only succeed because the provider returned the job again, nothing would be recovered.
    """
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(LIVE_KEY), FIRST_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )

    result = harness.discover(FIRST_RUN, fetcher=_single_page_fetcher([]))
    assert result["replayed_observations"] == 0, result  # same run, so not a replay: still owed work
    assert harness.live_view_ids("himalayas") == [HIMALAYAS_JOB]
    assert _pending(harness).get("himalayas") in (None, []), _pending(harness)

    harness.diff_monitored(FIRST_RUN)
    harness.report(FIRST_RUN)
    report = harness.saved_report(FIRST_RUN)
    assert [row["job_id"] for row in _discovery_rows(report)] == [HIMALAYAS_JOB]
    assert report["coverage"]["pending_publication_job_count"] == 0
    # One row, not two: the owed batch and the retry are the same observation.
    assert len(_discovery_rows(report)) == 1


def test_the_following_run_publishes_it_and_keeps_the_original_observation_timing(harness):
    """A whole round later, with the job gone from the feed, it still reaches that day's report.

    It arrives as YESTERDAY's observation. Recovery that restamped the posting as freshly fetched
    would be a different defect wearing the fix's clothes: the operator would be told a stale posting
    was just seen on the feed.
    """
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(LIVE_KEY), FIRST_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )
    harness.diff_monitored(FIRST_RUN)
    harness.report(FIRST_RUN)

    harness.enumerate_round(NEXT_RUN)
    harness.collect_monitored(NEXT_RUN)
    result = harness.discover(NEXT_RUN, fetcher=_single_page_fetcher([]))
    harness.diff_monitored(NEXT_RUN)
    harness.report(NEXT_RUN)

    assert result["replayed_observations"] == 1, result
    assert result["live_views"][f"himalayas:all"]["replayed_runs"] == [FIRST_RUN], result

    report = harness.saved_report(NEXT_RUN)
    assert [row["job_id"] for row in _discovery_rows(report)] == [HIMALAYAS_JOB]

    record = _live_record(harness, "himalayas", HIMALAYAS_JOB)
    # Attributed to the round that actually saw it, in both the ledger and the timestamps.
    assert record["observed_run_ids"] == [FIRST_RUN], record
    assert record["observation_count"] == 1
    assert record["last_seen_run_id"] == FIRST_RUN
    view = _read(harness, LIVE_KEY)
    assert datetime.fromisoformat(record["job"]["last_seen_at"]) < datetime.fromisoformat(
        view["last_observed_at"]
    ), (record["job"]["last_seen_at"], view["last_observed_at"])
    # The feed WAS read on the following run, so its own success history advanced.
    assert view["last_observed_run_id"] == NEXT_RUN
    assert sorted(view["observed_run_ids"]) == [FIRST_RUN, NEXT_RUN]


# ==================================================================================================
# Case 3 — partial write across two feeds
# ==================================================================================================
def test_a_partial_multi_provider_write_commits_one_feed_and_leaves_the_other_owed(harness):
    """Two feeds, one refused write: each feed ends committed-and-settled or untouched-and-owed.

    The forbidden third state is a feed whose debt was cleared while its view never committed. That
    is the state in which an observation disappears silently, so it is what this asserts against.
    """
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(s3layout.discovery_live_key("remotive")), FIRST_RUN,
        fetcher=_two_feeds, providers="himalayas,remotive",
    )

    # himalayas is drained before remotive, so it is committed AND cleared.
    assert harness.live_view_ids("himalayas") == [HIMALAYAS_JOB]
    assert "himalayas" not in _pending(harness), _pending(harness)
    # remotive's view never committed and its observation is still owed, by name.
    assert _read(harness, s3layout.discovery_live_key("remotive")) is None
    owed = _owed_job_ids(harness, "remotive")
    assert owed and all(job_id.startswith("remotive:") for job_id in owed), owed


def test_the_next_round_recovers_the_owed_feed_without_disturbing_the_committed_one(harness):
    """Recovering one feed may not roll back, re-age or duplicate another feed's committed work."""
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(s3layout.discovery_live_key("remotive")), FIRST_RUN,
        fetcher=_two_feeds, providers="himalayas,remotive",
    )
    committed = _live_record(harness, "himalayas", HIMALAYAS_JOB)

    harness.enumerate_round(NEXT_RUN)
    harness.collect_monitored(NEXT_RUN)
    # Both feeds now return nothing: recovery cannot come from the providers.
    harness.discover(NEXT_RUN, fetcher=_single_page_fetcher([]), providers="himalayas,remotive")
    harness.diff_monitored(NEXT_RUN)
    harness.report(NEXT_RUN)

    assert _pending(harness) == {} or all(
        not batches for batches in _pending(harness).values()
    ), _pending(harness)
    recovered = _read(harness, s3layout.discovery_live_key("remotive"))
    assert list(recovered["jobs"]), recovered
    assert list(recovered["jobs"].values())[0]["observed_run_ids"] == [FIRST_RUN]

    # The feed that committed on the interrupted round is byte-identical afterwards apart from the
    # staleness sentence a second unobserved round legitimately adds.
    after = _live_record(harness, "himalayas", HIMALAYAS_JOB)
    assert after["observed_run_ids"] == committed["observed_run_ids"] == [FIRST_RUN]
    assert after["job"]["last_seen_at"] == committed["job"]["last_seen_at"]
    assert after["last_seen_run_id"] == FIRST_RUN

    report = harness.saved_report(NEXT_RUN)
    ids = [row["job_id"] for row in _discovery_rows(report)]
    assert len(ids) == len(set(ids)) == 2, ids


# ==================================================================================================
# Case 4 — the failure between committing a view and clearing its debt
# ==================================================================================================
def test_a_batch_owed_after_its_view_committed_replays_without_duplicating_or_inflating(harness):
    """The narrowest window: the view is written, then clearing the debt fails.

    The batch is therefore owed a second time although it has already been published. Replay has to
    be idempotent rather than merely convergent, which is why a posting records WHICH runs observed it
    instead of carrying a bare counter.
    """
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(PENDING_KEY, arm_after=LIVE_KEY), FIRST_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )

    # Published, and still owed. Both at once is the state under test.
    assert harness.live_view_ids("himalayas") == [HIMALAYAS_JOB]
    assert _owed_job_ids(harness, "himalayas") == [HIMALAYAS_JOB], _pending(harness)
    before = _live_record(harness, "himalayas", HIMALAYAS_JOB)

    harness.enumerate_round(NEXT_RUN)
    harness.collect_monitored(NEXT_RUN)
    harness.discover(NEXT_RUN, fetcher=_single_page_fetcher([]))
    harness.diff_monitored(NEXT_RUN)
    harness.report(NEXT_RUN)

    after = _live_record(harness, "himalayas", HIMALAYAS_JOB)
    assert after["observed_run_ids"] == before["observed_run_ids"] == [FIRST_RUN]
    assert after["observation_count"] == 1
    assert after["job"]["last_seen_at"] == before["job"]["last_seen_at"]
    assert harness.live_view_ids("himalayas") == [HIMALAYAS_JOB]
    assert _pending(harness).get("himalayas") in (None, []), _pending(harness)

    rows = [row["job_id"] for row in _discovery_rows(harness.saved_report(NEXT_RUN))]
    assert rows == [HIMALAYAS_JOB], rows


def test_a_replayed_batch_cannot_roll_back_a_newer_observation(harness):
    """An older owed batch arriving after a newer round must not undo the newer observation.

    Round one is interrupted and owes the posting. Round two sees it again and commits the view, but
    fails to clear the debt. Round three therefore replays BOTH batches over a view that already holds
    round two's timing. Round one's observation is older; it may add to the history and it may correct
    a first sighting backwards, but it may not make the posting look last-seen a day earlier.
    """
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(LIVE_KEY), FIRST_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )
    harness.enumerate_round(NEXT_RUN)
    harness.collect_monitored(NEXT_RUN)
    _discover_through(
        harness, RefuseOnePut(PENDING_KEY, arm_after=LIVE_KEY), NEXT_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )
    published = _live_record(harness, "himalayas", HIMALAYAS_JOB)
    assert published["observed_run_ids"] == [FIRST_RUN, NEXT_RUN], published
    assert published["last_seen_run_id"] == NEXT_RUN

    third = "2026-09-27"
    harness.enumerate_round(third)
    harness.collect_monitored(third)
    harness.discover(third, fetcher=_single_page_fetcher([]))

    after = _live_record(harness, "himalayas", HIMALAYAS_JOB)
    # No rollback, and no inflation from replaying two already-published batches.
    assert after["last_seen_run_id"] == NEXT_RUN
    assert after["job"]["last_seen_at"] == published["job"]["last_seen_at"]
    assert after["observed_run_ids"] == [FIRST_RUN, NEXT_RUN]
    assert after["observation_count"] == 2
    assert after["first_seen_run_id"] == FIRST_RUN
    assert harness.live_view_ids("himalayas") == [HIMALAYAS_JOB]


# ==================================================================================================
# Case 5 — the bound on stored debt, and the costs the repair must not change
# ==================================================================================================
def _backlog_beyond_the_cap(harness, *, extra_rounds: int = 2) -> tuple[list[str], list[str]]:
    """Fail publication for more consecutive rounds than the batch bound allows.

    Each round observes a DIFFERENT posting, so the debt cannot stay small by coincidence: after the
    cap is exceeded, every one of these job ids has to still be owed or the bound has discarded an
    accepted observation. Returns the run ids and the job ids, in order.
    """
    rounds = [
        f"2026-10-{day:02d}"
        for day in range(1, MAX_OWED_BATCHES_PER_PROVIDER + 1 + extra_rounds)
    ]
    job_ids: list[str] = []
    for index, run_id in enumerate(rounds):
        record = dict(UNREGISTERED_FIT)
        record["guid"] = f"https://himalayas.app/companies/granite-state-mutual/jobs/role-{index}"
        record["applicationLink"] = record["guid"]
        job_ids.append(f"himalayas:all#role-{index}")
        harness.enumerate_round(run_id)
        _discover_through(
            harness, RefuseOnePut(LIVE_KEY), run_id,
            fetcher=_single_page_fetcher([record]),
        )
    return rounds, job_ids


def test_the_owed_ledger_is_bounded_by_compacting_and_never_by_discarding(harness):
    """Stored state stays bounded, and no accepted posting is discarded to keep it that way.

    P08 dropped the oldest batch above the bound and its own regression required the drop. The
    review was right that this encodes a defect: an observation that is durably accepted is owed to
    the morning report, and a count of rounds is not a reason to stop owing it. The bound now folds
    the oldest rounds into one carry-forward batch instead. What it gives up is per-round
    attribution, which the receipt states; what it must never give up is the postings.
    """
    rounds, job_ids = _backlog_beyond_the_cap(harness)

    owed = _pending(harness)["himalayas"]
    assert len(owed) <= MAX_OWED_BATCHES_PER_PROVIDER, [b["run_id"] for b in owed]
    # Every posting from every failed round is still owed, including the oldest ones.
    assert _owed_job_ids(harness, "himalayas") == sorted(job_ids)
    # The rounds beyond the bound were folded together, not thrown away.
    carried = owed[0]
    assert carried["compacted_run_ids"], owed
    assert set(carried["compacted_run_ids"]) <= set(rounds)

    coverage = _read(harness, s3layout.discovery_coverage_key(rounds[-1]))
    notices = coverage["pending_publication_bounds"]
    compaction = [n for n in notices if n.get("bound") == "compaction"]
    assert compaction, notices
    assert "Every posting is still owed" in compaction[0]["reason"]
    # The bound is visible where the operator reads it, not only in a field nothing renders.
    assert any(entry.get("job_ids") == compaction[0]["job_ids"]
               for entry in coverage["inaccessible"]), coverage["inaccessible"]
    # Nothing was removed, so no retention notice fires at this age.
    assert [n for n in notices if n.get("bound") == "retention"] == []


def test_the_first_healthy_round_after_that_backlog_publishes_every_owed_posting(harness):
    """The recovery round must not be the thing that loses the oldest job.

    P08's bound ran on `owe`, before the drain, so the first healthy round evicted the oldest batch
    merely by enqueuing its own — and that round's batch is empty, because the feed window has long
    since moved past those postings. The round that finally works is the worst possible moment to
    discard the debt, so it is tested directly.
    """
    rounds, job_ids = _backlog_beyond_the_cap(harness)
    recovery_run = "2026-10-20"

    harness.enumerate_round(recovery_run)
    harness.collect_monitored(recovery_run)
    harness.discover(recovery_run, fetcher=_single_page_fetcher([]))
    harness.diff_monitored(recovery_run)
    harness.report(recovery_run)

    # Published from the debt alone: the feed returned nothing in the recovery round.
    assert harness.live_view_ids("himalayas") == sorted(job_ids)
    assert _pending(harness).get("himalayas", []) == []
    report = harness.saved_report(recovery_run)
    assert sorted(row["job_id"] for row in _discovery_rows(report)) == sorted(job_ids)
    # And the timing is the round that actually observed each posting, not the recovery round.
    for index, job_id in enumerate(job_ids):
        record = _live_record(harness, "himalayas", job_id)
        assert recovery_run not in record["observed_run_ids"], record
        assert record["last_seen_run_id"] in rounds, record


def test_an_owed_posting_older_than_the_view_retention_is_removed_and_says_so(harness):
    """The one bound that removes anything, and the reason it is not an arbitrary cap.

    A posting owed for longer than the live view's own retention window would be retired by the very
    merge that published it, so carrying it further buys nothing. That is the view's existing rule
    reaching the debt, not a second policy, and it is unreachable until publication has failed for
    `RETENTION_DAYS` running.
    """
    from datetime import timedelta, timezone

    from src.discovery.live import (
        PendingPublication,
        PendingPublicationBatch,
        RETENTION_DAYS,
    )

    now = datetime.now(timezone.utc)
    harness.enumerate_round(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(LIVE_KEY), FIRST_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )
    owed_job = PendingPublication.model_validate(
        _read(harness, PENDING_KEY)
    ).batches["himalayas"][0].jobs[0]

    stale = PendingPublicationBatch(
        run_id="2026-01-01", observed_at=now - timedelta(days=RETENTION_DAYS + 2),
        feed_produced_usable_page=True, jobs=[owed_job],
    )
    fresh = PendingPublicationBatch(
        run_id="2026-10-01", observed_at=now, feed_produced_usable_page=True, jobs=[],
    )
    pending = PendingPublication(batches={"himalayas": [stale]})
    updated, notices = pending.owe("himalayas", fresh, now=now)

    assert [b.run_id for b in updated.batches["himalayas"]] == ["2026-10-01"]
    assert notices and notices[0]["bound"] == "retention"
    assert notices[0]["job_ids"] == [HIMALAYAS_JOB]
    assert "would retire them in the same merge" in notices[0]["reason"]
    # Without a clock the bound cannot fire at all, so retention is never applied by accident.
    unchanged, none_fired = pending.owe("himalayas", fresh)
    assert none_fired == []
    assert len(unchanged.batches["himalayas"]) == 2


def test_an_interrupted_publication_does_not_spend_extra_requests_or_erase_traversal_debt(harness):
    """The repair may not buy recovery with request budget or with the owed-page bookkeeping.

    The page budget and the recent-range debt P05 established are the two things a naive "just fetch
    it again" recovery would quietly consume, so they are asserted across the interruption.
    """
    pages: list[str] = []

    def paging(provider, token, url):
        pages.append(token)
        payload = _feed_payload(
            [UNREGISTERED_FIT] if token == "all" else [],
            cursor=f"CURSOR_{len(pages)}",
        )
        return _fetch_result(payload, url)

    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(harness, RefuseOnePut(LIVE_KEY), FIRST_RUN, fetcher=paging)

    # The interruption happens after the fetching is done, so it can neither add a request to the
    # per-source budget nor refund one. The budget is read from the connector rather than restated.
    budget = get_discovery_connector("himalayas").max_requests_per_run
    assert 0 < len(pages) <= budget, (pages, budget)
    state = _read(harness, s3layout.discovery_state_key())
    assert state, "traversal state must still be persisted on an interrupted round"

    before_pages = len(pages)
    harness.discover(FIRST_RUN, fetcher=paging)
    # The retry pays its own page budget for its own fetch; recovery itself costs no request.
    assert len(pages) - before_pages <= budget, (pages, budget)
    assert harness.live_view_ids("himalayas") == [HIMALAYAS_JOB]
    after = _read(harness, s3layout.discovery_state_key())
    # The saved continuation survives the interrupted round and its retry.
    assert after["source_cursors"].get("himalayas") or after.get("head_cursors"), after


# ==================================================================================================
# The structural check: every intermediate record here is written by production code
# ==================================================================================================
def test_no_intermediate_record_in_these_cases_is_written_by_this_test(harness):
    """The pending ledger and the live view must be producer-written, or these cases prove nothing.

    Two independent assertions. The first is textual: this module contains no S3 write call at all, so
    it cannot have seeded a record even accidentally. The second is a prefix census of the bucket after
    an interrupted round and its recovery — every top-level prefix present belongs to a production
    stage that owns it.
    """
    source = Path(__file__).read_text()
    # Each needle is split across two adjacent literals, which Python joins at compile time while the
    # file's own text does not contain the joined form. Without that, this check would fail on itself.
    for forbidden in ("put" "_object", "upload" "_file", "upload" "_fileobj", "copy" "_object"):
        assert forbidden not in source, forbidden

    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    _discover_through(
        harness, RefuseOnePut(LIVE_KEY), FIRST_RUN,
        fetcher=_single_page_fetcher([UNREGISTERED_FIT]),
    )
    # The owed ledger exists before this test has written anything anywhere.
    assert _pending(harness)["himalayas"], _pending(harness)
    harness.discover(FIRST_RUN, fetcher=_single_page_fetcher([]))
    harness.diff_monitored(FIRST_RUN)
    harness.report(FIRST_RUN)

    prefixes = {key.split("/", 1)[0] for key in harness.keys("")}
    assert prefixes <= {"runs", "raw", "normalized", "status", "current", "events", "discovery",
                        "reports"}, prefixes
    assert PENDING_KEY in harness.keys("discovery/")
    assert [row["job_id"] for row in _discovery_rows(harness.saved_report(FIRST_RUN))] == [
        HIMALAYAS_JOB
    ]
