"""P09: every distinct write boundary from durable acceptance to settlement, exercised.

What this file is for
---------------------
P08 repaired the live-view write and left the boundary one write earlier open. Its review refused
the FIRST write of the pending-publication ledger and reproduced the same loss: a posting already
durably normalized reached no report, in that round or any later one, because nothing recorded that
it was owed. Repairing that one key would have repaired that one probe.

So the sequence is enumerated instead. `persist` makes a FINITE, fully known list of external
storage writes for a feed, and each one is refused in turn here, with the feed returning nothing on
every later attempt. For each boundary this file records the same two facts: was the observation
durably ACCEPTED, and if so, what recovered it.

The acceptance point
--------------------
A feed's owed-publication object is the FIRST durable write of its round. That is what makes the
acceptance statement decidable rather than a label: nothing durable precedes it, so there is no
state in which a posting is captured but not yet recoverable. A failure at or before that write
leaves the round incomplete and the posting unaccepted — the feed must return it again, and nothing
here promises otherwise. A failure at ANY later write leaves the posting owed and recoverable
without the provider returning it.

What these tests do NOT establish
---------------------------------
  - anything about real S3. `moto` grants every permission and models no eventual consistency, so
    these prove the code's behavior under a refused write, not S3's own semantics or the IAM policy.
    The declared grants are checked against the real template in the P07 integration file.
  - anything about a CONCURRENT second writer. Discovery is one scheduled stage doing
    read-modify-write on its own objects — the profile `discovery/_discovery_state.json` already
    has. Every case below is serial, and nothing here makes two simultaneous discovery invocations
    safe or claims exactly-once semantics under concurrency.
  - anything about the live market. Every payload is synthetic; the insurance-company role is a test
    control and never a vacancy to apply to.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import boto3
import pytest
from botocore.client import BaseClient
from moto import mock_aws

from src.common import s3layout
from tests.test_discovery_to_report_integration import (
    BUCKET,
    UNREGISTERED_FIT,
    Harness,
    _round,
    _single_page_fetcher,
)

FIRST_RUN = "2026-09-25"
NEXT_RUN = "2026-09-26"
PROVIDER = "himalayas"
BOARD = "all"
JOB_ID = "himalayas:all#internal-tools"

OWED_KEY = s3layout.discovery_owed_publication_key(PROVIDER)
AGGREGATE_KEY = s3layout.discovery_pending_publication_key()
LIVE_KEY = s3layout.discovery_live_key(PROVIDER)
COVERAGE_KEY = s3layout.discovery_coverage_key(FIRST_RUN)

# Recovery sources, named so the matrix says WHERE the posting came back from rather than only that
# it did. "already published" is a distinct answer from "owed": it means the view had committed and
# the replay was absorbed without duplicating or inflating anything.
NOT_ACCEPTED = "not accepted — round incomplete, the feed must return the posting again"
FROM_OWED = "the feed's owed-publication record"
ALREADY_PUBLISHED = "already published; the owed batch replayed idempotently"


class FailAt:
    """Refuse the Nth `PutObject` to a key, either before or AFTER the service has stored it.

    `after_commit` is the ambiguous-response case the packet names: the write really happened and
    the caller never learned it. Nothing else can produce that state, and it is the one failure
    where retrying blindly would be wrong if replay were not idempotent.
    """

    def __init__(self, key: str, *, occurrence: int = 1, after_commit: bool = False,
                 prefix: bool = False):
        self.key = key
        self.occurrence = occurrence
        self.after_commit = after_commit
        self.prefix = prefix
        self.seen = 0
        self.injected: list[str] = []
        self.failure: str | None = None
        self._original = BaseClient._make_api_call

    def _matches(self, key: str | None) -> bool:
        if not key:
            return False
        return key.startswith(self.key) if self.prefix else key == self.key

    def __call__(self, client, operation, parameters):
        if operation != "PutObject" or not self._matches(parameters.get("Key")):
            return self._original(client, operation, parameters)
        self.seen += 1
        if self.seen != self.occurrence or self.injected:
            return self._original(client, operation, parameters)
        self.injected.append(parameters["Key"])
        if self.after_commit:
            # The object IS written; only the caller's answer is lost.
            self._original(client, operation, parameters)
            raise TimeoutError(f"P09-injected timeout AFTER storing {parameters['Key']}")
        raise TimeoutError(f"P09-injected storage failure writing {parameters['Key']}")

    def patch(self):
        injector = self

        def _make_api_call(client, operation, parameters):
            return injector(client, operation, parameters)

        return patch.object(BaseClient, "_make_api_call", _make_api_call)


# (label, injector factory, the observation was durably accepted, what recovered it)
BOUNDARIES: list[tuple[str, object, bool, str]] = [
    ("acceptance_record", lambda: FailAt(OWED_KEY), False, NOT_ACCEPTED),
    ("acceptance_record_stored_then_timeout",
     lambda: FailAt(OWED_KEY, after_commit=True), True, FROM_OWED),
    ("raw_snapshot", lambda: FailAt(f"raw/provider={PROVIDER}/", prefix=True), True, FROM_OWED),
    ("normalized",
     lambda: FailAt(s3layout.normalized_key(PROVIDER, BOARD, FIRST_RUN)), True, FROM_OWED),
    ("source_status",
     lambda: FailAt(s3layout.source_status_key(PROVIDER, BOARD)), True, FROM_OWED),
    ("success_sentinel",
     lambda: FailAt(s3layout.collect_sentinel_key(FIRST_RUN, PROVIDER, BOARD)), True, FROM_OWED),
    ("aggregate_receipt", lambda: FailAt(AGGREGATE_KEY), True, FROM_OWED),
    ("coverage_receipt", lambda: FailAt(COVERAGE_KEY), True, FROM_OWED),
    ("traversal_state", lambda: FailAt(s3layout.discovery_state_key()), True, FROM_OWED),
    ("source_growth", lambda: FailAt(s3layout.source_growth_key()), True, FROM_OWED),
    ("proposed_registry",
     lambda: FailAt(s3layout.proposed_registry_key(FIRST_RUN)), True, FROM_OWED),
    ("live_view_commit", lambda: FailAt(LIVE_KEY), True, FROM_OWED),
    ("live_view_stored_then_timeout",
     lambda: FailAt(LIVE_KEY, after_commit=True), True, ALREADY_PUBLISHED),
    ("settle_owed_record", lambda: FailAt(OWED_KEY, occurrence=2), True, ALREADY_PUBLISHED),
    ("aggregate_receipt_refresh",
     lambda: FailAt(AGGREGATE_KEY, occurrence=2), True, ALREADY_PUBLISHED),
    ("residual_coverage_receipt",
     lambda: FailAt(COVERAGE_KEY, occurrence=2), True, ALREADY_PUBLISHED),
]


@pytest.fixture
def harness():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="jprs-p09-collect")["QueueUrl"]
        h = Harness(s3, queue_url)
        h.sqs = sqs
        yield h


def _read(harness, key: str, default=None):
    import botocore.exceptions

    try:
        return json.loads(harness.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except botocore.exceptions.ClientError:
        return default


def _discovery_ids(report: dict) -> list[str]:
    return sorted(
        row["job_id"] for row in report["complete_candidate_list"]
        if row["source_kind"] == "DISCOVERY_FEED"
    )


def exercise(harness, injector) -> dict:
    """One round interrupted at a named boundary, then the two ordinary recovery paths.

    The feed returns the posting once and NOTHING afterwards, so anything that comes back came from
    durable storage rather than from asking the provider again.
    """
    harness.enumerate_round(FIRST_RUN)
    harness.collect_monitored(FIRST_RUN)
    with injector.patch():
        try:
            harness.discover(FIRST_RUN, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
        except TimeoutError as error:
            injector.failure = str(error)
    assert injector.injected, "the injected failure never fired; this boundary proves nothing"
    assert injector.failure, "discovery swallowed the storage failure instead of surfacing it"

    owed_after_failure = _read(harness, OWED_KEY, default={})
    owed_at_failure = any(
        job["job_id"] == JOB_ID
        for batches in (owed_after_failure.get("batches") or {}).values()
        for batch in batches for job in batch["jobs"]
    )
    published_before_recovery = JOB_ID in (_read(harness, LIVE_KEY, default={}).get("jobs") or {})
    # Accepted means the observation is on durable record somewhere the ordinary path reaches: still
    # owed, or already folded into the view and the debt settled. The late boundaries are the second
    # case, and reading only the owed record there would report a settled posting as unaccepted.
    accepted = owed_at_failure or published_before_recovery

    # Recovery path 1 — the same round is retried and the feed no longer holds the posting.
    harness.discover(FIRST_RUN, fetcher=_single_page_fetcher([]))
    harness.diff_monitored(FIRST_RUN)
    harness.report(FIRST_RUN)
    same_run = _discovery_ids(harness.saved_report(FIRST_RUN))

    # Recovery path 2 — the next ordinary round, again with the posting absent from the feed.
    _round(harness, NEXT_RUN, fetcher=_single_page_fetcher([]))
    following = _discovery_ids(harness.saved_report(NEXT_RUN))

    record = _read(harness, LIVE_KEY, default={"jobs": {}})["jobs"].get(JOB_ID) or {}
    return {
        "injected_failure": injector.failure,
        "durably_accepted_at_failure": accepted,
        "owed_at_failure": owed_at_failure,
        "published_before_recovery": published_before_recovery,
        "same_run_retry_discovery_candidates": same_run,
        "following_run_discovery_candidates": following,
        "observed_run_ids": record.get("observed_run_ids", []),
        "observation_count": record.get("observation_count"),
        "still_owed": bool((_read(harness, OWED_KEY, default={}).get("batches") or {})),
    }


@pytest.mark.parametrize(
    "label,factory,expect_accepted,expect_source",
    BOUNDARIES,
    ids=[row[0] for row in BOUNDARIES],
)
def test_every_write_boundary_either_accepts_and_recovers_or_accepts_nothing(
    harness, label, factory, expect_accepted, expect_source
):
    """The whole claim, one boundary at a time.

    Either the observation was never durably accepted — in which case the round is honestly
    incomplete and nothing was promised — or it was accepted, and it reaches the morning report
    without the provider returning it. There is no third outcome anywhere in the sequence.
    """
    result = exercise(harness, factory())

    assert result["durably_accepted_at_failure"] is expect_accepted, result
    if not expect_accepted:
        assert result["same_run_retry_discovery_candidates"] == [], result
        assert result["following_run_discovery_candidates"] == [], result
        assert expect_source == NOT_ACCEPTED
        return

    assert result["same_run_retry_discovery_candidates"] == [JOB_ID], result
    assert result["following_run_discovery_candidates"] == [JOB_ID], result
    # Replay never inflates the observation history, however many times a batch is re-applied, and
    # the recovery rounds saw nothing so they must not appear as rounds that observed the posting.
    assert result["observed_run_ids"] == [FIRST_RUN], result
    assert result["observation_count"] == 1, result
    # Nothing stays owed once a healthy round has run.
    assert result["still_owed"] is False, result
    if expect_source == ALREADY_PUBLISHED:
        assert result["published_before_recovery"] is True, result
    else:
        assert result["published_before_recovery"] is False, result


def test_a_refused_acceptance_leaves_no_other_durable_trace_to_be_lost(harness):
    """The unaccepted case is honest, not merely unrecoverable.

    A failure before acceptance must not leave a posting written into the court of record with no
    way back to the report — that state is exactly the defect. Because acceptance is the FIRST
    durable write of the feed's round, refusing it means nothing for that feed was written at all.
    """
    harness.enumerate_round(FIRST_RUN)
    injector = FailAt(OWED_KEY)
    with injector.patch():
        with pytest.raises(TimeoutError):
            harness.discover(FIRST_RUN, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))

    written = harness.keys(f"raw/provider={PROVIDER}/") + harness.keys("discovery/")
    assert written == [], written
    assert harness.keys(f"normalized/schema_v=1/provider={PROVIDER}/") == []


def test_a_partial_multi_provider_round_keeps_the_peer_feeds_accepted_work(harness):
    """One feed's refused acceptance costs that feed's batch and nothing else.

    P08 held the whole run's debt in ONE object, so a single refused write took every feed's work
    with it. The record is per feed now, and this is the case that says so.
    """
    from tests.test_durable_discovery_publication import REMOTIVE_FIT, _two_feeds

    harness.enumerate_round(FIRST_RUN)
    injector = FailAt(s3layout.discovery_owed_publication_key("remotive"))
    with injector.patch():
        with pytest.raises(TimeoutError):
            harness.discover(FIRST_RUN, fetcher=_two_feeds, providers="himalayas,remotive")

    himalayas = _read(harness, OWED_KEY, default={})
    owed_ids = sorted(
        job["job_id"]
        for batches in (himalayas.get("batches") or {}).values()
        for batch in batches for job in batch["jobs"]
    )
    assert owed_ids == [JOB_ID], himalayas
    assert _read(harness, s3layout.discovery_owed_publication_key("remotive")) is None
    assert REMOTIVE_FIT["company_name"]  # the refused feed's posting is simply not accepted

    # The next ordinary round publishes the accepted feed from its own record, and the refused one
    # is accepted normally when it is reached again.
    _round(harness, NEXT_RUN, fetcher=_two_feeds, )
    assert JOB_ID in harness.live_view_ids(PROVIDER)
