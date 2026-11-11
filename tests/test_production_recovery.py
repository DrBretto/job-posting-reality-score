"""Production recovery regressions: discovery's first round under real IAM, and report publication.

What happened in production on 2026-09-26
-----------------------------------------
Two defects, both reproduced from live logs and real inputs before these tests were written
(evidence in the governed run `20260926_career-radar-production-recovery-v1`):

  DISCOVERY  `persist()` begins by reading every feed's owed-publication object. None had ever been
             written. The discovery role holds `s3:GetObject` on `discovery/*` and NO `s3:ListBucket`,
             and S3 answers a GetObject for a missing key with 403 AccessDenied when the caller cannot
             list the bucket (404 only when it can). `_load_optional` correctly refuses to read a 403
             as absence, so the object could never be created. Every moto-backed test passed,
             because moto grants everything and always answers 404.

  REPORT     the vocabulary guard failed the whole report twice over: once on the differ's own
             SOURCE_SEGMENT_CLOSED note ("Treating this as a real closure"), and once on a job title
             containing `|`, which Markdown escaping turned into text the exact-match source
             redaction no longer recognized ("Senior FullStack Engineer - Real User Monitoring").

Why these tests carry their own IAM model
-----------------------------------------
`RoleS3` applies ONE function's declared statements, read from the real `infra/template.yaml`, to
every S3 call the production code makes, and applies S3's documented 403/404 rule for a missing
key. It is the smallest model that could have caught the discovery deadlock, and it is the model
the repair is argued from, so it is stated rather than hidden:

  - an object action is allowed when an Allow statement names the action and a resource pattern
    that matches `arn:aws:s3:::<bucket>/<key>`;
  - `s3:ListBucket` is allowed for a prefix when an Allow statement names the bucket ARN and, if it
    carries a `StringLike` `s3:prefix` condition, one of its patterns matches that prefix;
  - a GetObject/HeadObject for a missing key is 404 when ListBucket is allowed for the key itself as
    the prefix, and 403 otherwise.

The third rule's prefix-conditioned case is NOT documentation-derived; it is observed. The report
role holds exactly such a grant (`s3:prefix` `discovery/*`), and under P10 at 10:29 EDT on
2026-09-26 it read four never-written `discovery/live/provider=*/live_jobs.json` keys through a
loader that raises on AccessDenied and reached the render step. So in this account a
prefix-conditioned grant turns absence under that prefix into 404. If that ever stopped holding,
the report's own discovery read would fail the same way and these tests would still be the place
to encode it.

What these tests do NOT establish: anything about IAM propagation delay, explicit Deny policies in
other accounts, bucket policies beyond the TLS-only one this stack declares, or the live market.
Every payload is synthetic unless labelled otherwise.
"""

from __future__ import annotations

import fnmatch
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import boto3
import botocore.exceptions
import pydantic
import pytest
from botocore.client import BaseClient
from moto import mock_aws

from src.common import s3layout
from src.common.models import ChangeEvent, ChangeEventType
from src.report.handler import (
    NeverFakeViolation,
    ReportInput,
    _CHANGE_PHRASE,
    _md_text,
    assert_no_banned_vocab,
    render_report,
)
from src.scoring.scoring import ScoreContext, score_job
from tests.conftest import make_job
from tests.test_discovery_to_report_integration import (
    BUCKET,
    MONITORED_BOARD,
    MONITORED_PAYLOAD,
    UNREGISTERED_FIT,
    Harness,
    _feed_payload,
    _fetch_result,
    _single_page_fetcher,
    _statements,
    _template,
)
from tests.test_durable_discovery_publication import RefuseOnePut

RUN = "2026-09-26"
NEXT = "2026-09-27"
HIMALAYAS_JOB = "himalayas:all#internal-tools"
OWED_KEY = s3layout.discovery_owed_publication_key("himalayas")
LIVE_KEY = s3layout.discovery_live_key("himalayas")
STATE_KEY = s3layout.discovery_state_key()
GROWTH_KEY = s3layout.source_growth_key()

# The one statement this repair adds. Everything else in the discovery role is P10's, unchanged.
REPAIR_SID = "DiscoveryListOwnPrefix"


# ==================================================================================================
# The IAM model
# ==================================================================================================
def _as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def _arn_pattern(resource) -> str:
    """`arn:aws:s3:::${BucketName}/discovery/*` -> `arn:aws:s3:::<bucket>/discovery/*`."""
    return str(resource).replace("${BucketName}", BUCKET)


class RoleS3:
    """One Lambda role's S3 authority, from the real template, plus S3's missing-key rule."""

    def __init__(self, statements: list[dict], *, label: str,
                 conditioned_list_counts_for_get: bool = True):
        self.statements = [s for s in statements if s.get("Effect") == "Allow"]
        self.label = label
        # Whether a prefix-CONDITIONED list grant turns a missing-key GetObject into 404. Observed
        # true for the report role in this account (see module docstring) but not documented, so
        # discovery must not depend on it; see the test that sets this False.
        self.conditioned_list_counts_for_get = conditioned_list_counts_for_get
        # Genuine access loss on an EXISTING object: prefixes whose GetObject is denied anyway.
        self.revoked: list[str] = []
        # Transient/unavailable reads: prefix -> S3 error code returned instead of the object.
        self.failing: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    # -- policy evaluation -----------------------------------------------------------------------
    def allows_object(self, action: str, key: str) -> bool:
        arn = f"arn:aws:s3:::{BUCKET}/{key}"
        for statement in self.statements:
            if action not in _as_list(statement.get("Action")):
                continue
            if any(fnmatch.fnmatchcase(arn, _arn_pattern(r))
                   for r in _as_list(statement.get("Resource"))):
                return True
        return False

    def allows_list(self, prefix: str | None) -> bool:
        bucket_arn = f"arn:aws:s3:::{BUCKET}"
        for statement in self.statements:
            if "s3:ListBucket" not in _as_list(statement.get("Action")):
                continue
            if bucket_arn not in [_arn_pattern(r) for r in _as_list(statement.get("Resource"))]:
                continue
            condition = (statement.get("Condition") or {}).get("StringLike", {})
            patterns = condition.get("s3:prefix")
            if patterns is None:
                return True
            if prefix is not None and any(
                fnmatch.fnmatchcase(prefix, p) for p in _as_list(patterns)
            ):
                return True
        return False

    def _missing_is_404(self, key: str) -> bool:
        if self.allows_list(None) or self.allows_list(""):
            return True  # an unconditioned grant: documented behavior
        return self.conditioned_list_counts_for_get and self.allows_list(key)

    # -- S3 behavior -----------------------------------------------------------------------------
    def _denied(self, operation: str, detail: str):
        return botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDenied",
                       "Message": f"{self.label} is not authorized to perform: {detail}"}},
            operation,
        )

    def handle(self, original, client, operation, params):
        if client.meta.service_model.service_name != "s3" or params.get("Bucket") != BUCKET:
            return original(client, operation, params)
        key = params.get("Key", "")
        self.calls.append((operation, key or params.get("Prefix", "")))
        if operation in ("GetObject", "HeadObject"):
            if any(key.startswith(p) for p in self.revoked):
                raise self._denied(operation, f"s3:GetObject on {key} (revoked)")
            for prefix, code in self.failing.items():
                if key.startswith(prefix):
                    raise botocore.exceptions.ClientError(
                        {"Error": {"Code": code, "Message": f"injected {code}"}}, operation
                    )
            if not self.allows_object("s3:GetObject", key):
                raise self._denied(operation, f"s3:GetObject on {key}")
            try:
                return original(client, operation, params)
            except botocore.exceptions.ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in ("NoSuchKey", "404", "NotFound") and not self._missing_is_404(key):
                    raise self._denied(operation, "s3:ListBucket") from None
                raise
        if operation == "PutObject":
            if not self.allows_object("s3:PutObject", key):
                raise self._denied(operation, f"s3:PutObject on {key}")
            return original(client, operation, params)
        if operation in ("ListObjectsV2", "ListObjects"):
            if not self.allows_list(params.get("Prefix")):
                raise self._denied(operation, f"s3:ListBucket prefix={params.get('Prefix')}")
            return original(client, operation, params)
        if operation == "DeleteObject":
            if not self.allows_object("s3:DeleteObject", key):
                raise self._denied(operation, f"s3:DeleteObject on {key}")
        return original(client, operation, params)

    @contextmanager
    def active(self):
        original = BaseClient._make_api_call
        role = self

        def _make_api_call(client, operation, params):
            return role.handle(original, client, operation, params)

        with patch.object(BaseClient, "_make_api_call", _make_api_call):
            yield self


def discovery_role(*, repaired: bool = True, conditioned_list_counts_for_get: bool = True
                   ) -> RoleS3:
    statements = _statements(_template(), "DiscoveryFunction")
    if not repaired:
        statements = [s for s in statements if s.get("Sid") != REPAIR_SID]
    return RoleS3(statements, label="DiscoveryFunctionRole" + ("" if repaired else " (P10)"),
                  conditioned_list_counts_for_get=conditioned_list_counts_for_get)


def report_role() -> RoleS3:
    return RoleS3(_statements(_template(), "ReportFunction"), label="ReportFunctionRole")


# ==================================================================================================
# Harness
# ==================================================================================================
@pytest.fixture
def harness():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="jprs-recovery-collect")["QueueUrl"]
        h = Harness(s3, queue_url)
        h.sqs = sqs
        yield h


def _raw(harness, key: str) -> bytes | None:
    try:
        return harness.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    except botocore.exceptions.ClientError:
        return None


def _json(harness, key: str):
    body = _raw(harness, key)
    return json.loads(body) if body is not None else None


def _discovery_objects(harness) -> dict[str, bytes]:
    return {key: _raw(harness, key) for key in harness.keys("discovery/")}


def _monitored_round(harness, run_id: str) -> None:
    """Enumerate, then collect EVERY registry board, as production does.

    The shared harness only collects the board it has a payload for. A board never collected has no
    source status, the differ skips it, and the report — which cannot list `events/` — then meets a
    403 for its missing events object. Production collects all fifteen, so these tests do too; the
    boards other than the shared harness's are empty (a synthetic control, not a market claim).
    """
    harness.enumerate_round(run_id)
    manifest = _json(harness, s3layout.run_manifest_key(run_id))
    boards = {source.partition(":")[2]: {"jobs": []} for source in manifest["expected_sources"]}
    boards[MONITORED_BOARD] = MONITORED_PAYLOAD
    harness.collect_monitored(run_id, boards=boards)


def _diff_every_registry_board(harness, run_id: str) -> None:
    """One differ invocation per manifest source, as the assemble Map state does in production.

    The shared harness diffs only the one board it supplies a payload for. Under the report's real
    role that is not enough: the report has no list grant on `events/`, so a registry board with no
    events object for the day is a 403, not an empty list. Production writes one per board per day
    (the differ writes unconditionally), so the tests do too.
    """
    from src.differ.handler import handler as differ

    manifest = _json(harness, s3layout.run_manifest_key(run_id))
    with patch.dict("os.environ", harness.env):
        for source_id in manifest["expected_sources"]:
            provider, _, board = source_id.partition(":")
            differ({"provider": provider, "board_token": board, "run_id": run_id, "dt": run_id},
                   None)


def _discover_as(harness, role: RoleS3, run_id: str, *, fetcher) -> dict:
    with role.active():
        return harness.discover(run_id, fetcher=fetcher)


def _interrupted_round(harness, run_id: str, *, records) -> None:
    """A round whose live-view write fails, under the REPAIRED role: debt exists, view does not."""
    role = discovery_role()
    with role.active():
        injector = RefuseOnePut(LIVE_KEY)
        with injector.patch():
            with pytest.raises(TimeoutError):
                harness.discover(run_id, fetcher=_single_page_fetcher(records))
    assert injector.injected, "the injected failure never fired; the test proves nothing"


# ==================================================================================================
# 1. The production fault, reproduced under the P10 policy
# ==================================================================================================
def test_p10_policy_reproduces_the_production_deadlock(harness):
    """Fresh state + P10's discovery role = AccessDenied on the first owed read, and nothing written.

    This is the 2026-09-26 10:27 EDT failure. It is kept, rather than deleted once fixed, because it
    is the proof that the model below can see the defect at all: a model that passes P10 would be
    worthless evidence for the repair.
    """
    _monitored_round(harness, RUN)
    role = discovery_role(repaired=False)
    with pytest.raises(botocore.exceptions.ClientError) as caught:
        _discover_as(harness, role, RUN, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))

    error = caught.value.response["Error"]
    assert error["Code"] == "AccessDenied"
    assert "s3:ListBucket" in error["Message"]
    # The read that raised concerned a discovery object that has never been written. In production
    # (P10 code) it was a GetObject of the first owed-publication object, because P10 read the
    # traversal state and growth ledger through a loader that swallowed the same 403. This code
    # establishes absence by listing the exact key and reads state strictly, so under P10's policy
    # it stops on the first listing, of the state object — for the same missing permission.
    operation, failed_key = role.calls[-1]
    assert operation in ("GetObject", "ListObjectsV2"), role.calls
    assert failed_key.startswith("discovery/"), role.calls
    assert _raw(harness, failed_key) is None
    # The deadlock: the object cannot be created because the read that precedes creation fails.
    assert harness.keys("discovery/owed/") == []
    assert harness.keys("discovery/live/") == []


# ==================================================================================================
# 2. Fresh initialization under the repaired policy
# ==================================================================================================
def test_the_repaired_policy_initializes_fresh_state_and_publishes_to_the_report(harness):
    """No discovery object exists; the round creates them all and the job reaches the report.

    The report runs under ITS declared role too, so the handoff between the two roles is checked
    against the template rather than against moto's grant-everything default.
    """
    _monitored_round(harness, RUN)
    assert harness.keys("discovery/") == []

    result = _discover_as(harness, discovery_role(), RUN,
                          fetcher=_single_page_fetcher([UNREGISTERED_FIT]))

    assert result["live_jobs_total"] == 1, result
    assert sorted(_json(harness, LIVE_KEY)["jobs"]) == [HIMALAYAS_JOB]
    owed = _json(harness, OWED_KEY)
    assert owed is not None and owed["batches"] == {}, owed  # created, then settled
    assert _json(harness, STATE_KEY) is not None
    assert _json(harness, GROWTH_KEY) is not None

    _diff_every_registry_board(harness, RUN)
    with report_role().active():
        harness.report(RUN)
    report = harness.saved_report(RUN)
    assert HIMALAYAS_JOB in [row["job_id"] for row in report["complete_candidate_list"]]


def test_discovery_initializes_even_if_s3_ignored_the_conditioned_grant_on_a_missing_get(harness):
    """The repair must not rest on the undocumented part of S3's 403/404 rule.

    Here a missing-key GetObject is 403 even with the `discovery/*` list grant. Discovery still
    starts, because it establishes absence with an exact-key ListObjectsV2 — a request that carries
    `s3:prefix` and so is matched by the grant by definition — and only then reads.
    """
    _monitored_round(harness, RUN)
    role = discovery_role(conditioned_list_counts_for_get=False)
    result = _discover_as(harness, role, RUN, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    assert result["live_jobs_total"] == 1, result
    assert sorted(_json(harness, LIVE_KEY)["jobs"]) == [HIMALAYAS_JOB]
    # Absence was decided by listing, never by a failed read.
    missing_gets = [key for op, key in role.calls
                    if op == "GetObject" and _raw(harness, key) is None]
    assert missing_gets == [], missing_gets


def test_the_only_iam_change_is_one_list_statement_scoped_to_the_discovery_prefix():
    """The permission delta is exactly one statement, and it cannot reach any other prefix."""
    statements = _statements(_template(), "DiscoveryFunction")
    added = [s for s in statements if s.get("Sid") == REPAIR_SID]
    assert len(added) == 1
    statement = added[0]
    assert statement["Effect"] == "Allow"
    assert _as_list(statement["Action"]) == ["s3:ListBucket"]
    assert [_arn_pattern(r) for r in _as_list(statement["Resource"])] == [f"arn:aws:s3:::{BUCKET}"]
    assert statement["Condition"] == {"StringLike": {"s3:prefix": ["discovery/*"]}}

    role = discovery_role()
    assert role.allows_list("discovery/owed/provider=himalayas/owed_publication.json")
    for elsewhere in ("", None, "reports/", "raw/", "runs/", "current/", "normalized/", "status/"):
        assert not role.allows_list(elsewhere), elsewhere
    # And nothing else about the role moved: still no delete, still no write outside its tiers.
    assert not role.allows_object("s3:DeleteObject", OWED_KEY)
    assert not role.allows_object("s3:PutObject", "current/provider=x/board=y/current_jobs.json")
    assert not role.allows_object("s3:PutObject", s3layout.report_json_key(RUN))
    list_statements = [s for s in statements if "s3:ListBucket" in _as_list(s.get("Action"))]
    assert list_statements == added


# ==================================================================================================
# 3. Existing owed data, and a retry without another feed occurrence
# ==================================================================================================
def test_existing_owed_data_is_published_by_a_retry_whose_feed_no_longer_has_the_job(harness):
    _monitored_round(harness, RUN)
    _interrupted_round(harness, RUN, records=[UNREGISTERED_FIT])
    owed_before = _json(harness, OWED_KEY)
    assert [j["job_id"] for b in owed_before["batches"]["himalayas"] for j in b["jobs"]] == [
        HIMALAYAS_JOB
    ]
    assert _raw(harness, LIVE_KEY) is None

    # Same-run retry: the feed window no longer holds the posting.
    _discover_as(harness, discovery_role(), RUN, fetcher=_single_page_fetcher([]))

    assert sorted(_json(harness, LIVE_KEY)["jobs"]) == [HIMALAYAS_JOB]
    assert _json(harness, OWED_KEY)["batches"] == {}

    _diff_every_registry_board(harness, RUN)
    with report_role().active():
        harness.report(RUN)
    rows = harness.saved_report(RUN)["complete_candidate_list"]
    assert [r["job_id"] for r in rows if r["job_id"] == HIMALAYAS_JOB] == [HIMALAYAS_JOB]


def test_existing_owed_data_survives_into_the_next_days_round(harness):
    _monitored_round(harness, RUN)
    _interrupted_round(harness, RUN, records=[UNREGISTERED_FIT])

    _monitored_round(harness, NEXT)
    _discover_as(harness, discovery_role(), NEXT, fetcher=_single_page_fetcher([]))

    record = _json(harness, LIVE_KEY)["jobs"][HIMALAYAS_JOB]
    # It is published as the round that actually observed it, not as a fresh sighting.
    assert record["first_seen_run_id"] == RUN
    assert record["observed_run_ids"] == [RUN]
    assert _json(harness, OWED_KEY)["batches"] == {}


# ==================================================================================================
# 4. Genuine access loss stays visible and discards nothing
# ==================================================================================================
def test_a_denied_read_of_an_existing_owed_object_stops_the_round_and_keeps_the_debt(harness):
    _monitored_round(harness, RUN)
    _interrupted_round(harness, RUN, records=[UNREGISTERED_FIT])
    before = _discovery_objects(harness)

    role = discovery_role()
    role.revoked.append(OWED_KEY)
    _monitored_round(harness, NEXT)
    with pytest.raises(botocore.exceptions.ClientError) as caught:
        _discover_as(harness, role, NEXT, fetcher=_single_page_fetcher([]))
    assert caught.value.response["Error"]["Code"] == "AccessDenied"

    # Nothing under discovery/ changed: the debt was not read as empty and then overwritten.
    assert _discovery_objects(harness) == before


@pytest.mark.parametrize("key", [STATE_KEY, GROWTH_KEY])
def test_a_denied_read_of_existing_traversal_or_growth_state_stops_instead_of_resetting(
    harness, key
):
    """P10 read these through a loader that swallowed EVERY client error, AccessDenied included.

    A denied read therefore started from an empty ledger and then overwrote the real one at the end
    of the round — losing owed traversal ranges or the operator's sticky source disables without a
    word. Absence is still fine (see the fresh-initialization case); denial is not absence.
    """
    _monitored_round(harness, RUN)
    _discover_as(harness, discovery_role(), RUN, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    before = _discovery_objects(harness)
    assert key in before

    role = discovery_role()
    role.revoked.append(key)
    _monitored_round(harness, NEXT)
    with pytest.raises(botocore.exceptions.ClientError) as caught:
        _discover_as(harness, role, NEXT, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    assert caught.value.response["Error"]["Code"] == "AccessDenied"
    assert _discovery_objects(harness) == before


# ==================================================================================================
# 5. Corrupt or unavailable state stops the round and preserves the object
# ==================================================================================================
@pytest.mark.parametrize("key", [OWED_KEY, STATE_KEY, GROWTH_KEY])
def test_corrupt_existing_state_stops_the_round_and_is_not_overwritten(harness, key):
    _monitored_round(harness, RUN)
    _interrupted_round(harness, RUN, records=[UNREGISTERED_FIT])
    # Corruption is an OUTSIDE event, so it is the one intermediate this test writes itself.
    harness.s3.put_object(Bucket=BUCKET, Key=key, Body=b'{"batches": {"himalayas": [trunc')
    before = _discovery_objects(harness)

    _monitored_round(harness, NEXT)
    with pytest.raises((json.JSONDecodeError, pydantic.ValidationError)):
        _discover_as(harness, discovery_role(), NEXT, fetcher=_single_page_fetcher([]))
    assert _discovery_objects(harness) == before


@pytest.mark.parametrize("code", ["InternalError", "SlowDown", "ServiceUnavailable"])
@pytest.mark.parametrize("key", [STATE_KEY, GROWTH_KEY, OWED_KEY])
def test_an_unavailable_read_of_one_existing_object_stops_the_round_and_writes_nothing(
    harness, key, code
):
    """Only the named object's read fails. For the traversal state and the growth ledger this is
    failure-first: P10 swallowed exactly this error, started from an empty ledger and overwrote the
    real one. The owed object was already strict in P10 and is kept as a regression guard."""
    _monitored_round(harness, RUN)
    _interrupted_round(harness, RUN, records=[UNREGISTERED_FIT])
    before = _discovery_objects(harness)
    assert key in before

    role = discovery_role()
    role.failing[key] = code
    _monitored_round(harness, NEXT)
    with pytest.raises(botocore.exceptions.ClientError) as caught:
        _discover_as(harness, role, NEXT, fetcher=_single_page_fetcher([]))
    assert caught.value.response["Error"]["Code"] == code
    assert _discovery_objects(harness) == before


# ==================================================================================================
# 6. Source titles publish intact
# ==================================================================================================
# SYNTHETIC controls. The first reproduces the production title's SHAPE (a guarded word plus `|`);
# the second adds curly quotes and brackets, which JSON and Markdown each escape differently.
PIPE_TITLE = "Senior FullStack Engineer - Real User Monitoring (RUM) | Observability | Remote US"
QUOTED_TITLE = "Staff Engineer, “Real-Time” Fraud Signals [Payments Platform]"


def _titled(record: dict, *, title: str, slug: str) -> dict:
    row = dict(record)
    row["title"] = title
    row["companySlug"] = slug
    row["companyName"] = slug.replace("-", " ").title() + " Mutual"
    row["applicationLink"] = f"https://himalayas.app/companies/{slug}/jobs/{slug}-role"
    row["guid"] = row["applicationLink"]
    return row


def test_source_titles_with_guarded_words_and_escaped_characters_publish_intact(harness):
    records = [
        _titled(UNREGISTERED_FIT, title=PIPE_TITLE, slug="lakes-region"),
        _titled(UNREGISTERED_FIT, title=QUOTED_TITLE, slug="merrimack-valley"),
    ]
    _monitored_round(harness, RUN)
    _discover_as(harness, discovery_role(), RUN, fetcher=_single_page_fetcher(records))
    _diff_every_registry_board(harness, RUN)
    with report_role().active():
        harness.report(RUN)

    report = harness.saved_report(RUN)
    rows = {row["title"]: row for row in report["complete_candidate_list"]}
    # Both postings are present, retained, and carry their titles byte for byte.
    assert PIPE_TITLE in rows, sorted(rows)
    assert QUOTED_TITLE in rows, sorted(rows)
    markdown = harness.saved_markdown(RUN)
    assert _md_text(PIPE_TITLE) in markdown
    assert _md_text(QUOTED_TITLE) in markdown


def _scored(job):
    return score_job(ScoreContext(job=job), today=datetime(2026, 9, 26, tzinfo=timezone.utc))


def _input_with(job, events=()) -> ReportInput:
    return ReportInput(
        run_id=RUN, dt=RUN,
        expected_sources=[job.source_id], succeeded_sources=[job.source_id],
        jobs=[job], scorecards=[_scored(job)], events=list(events),
    )


def _job(title: str):
    job = make_job(
        "rum-1", source_id="greenhouse:example", title=title,
        description="Build LLM agents and Python backend services on AWS.",
        location="Remote - United States", remote="remote",
    )
    job.posting_url = "https://job-boards.greenhouse.io/example/jobs/rum-1"
    return job


@pytest.mark.parametrize("title", [PIPE_TITLE, QUOTED_TITLE, "Fraud Operations Data Engineer"])
def test_render_keeps_sourced_titles_across_markdown_and_json_escaping(title):
    md, js = render_report(_input_with(_job(title)))
    assert _md_text(title) in md
    assert title in [row["title"] for row in js["complete_candidate_list"]]


# ==================================================================================================
# 7. System-authored claims: source-scoped notes are withheld, never published; the guard stays
# ==================================================================================================
DIFFER_NOTE = (
    "department segment(s) ['people team'] have been absent from 2 consecutive healthy successful "
    "downloads while the rest of the board stayed intact (9 postings). Treating this as a real "
    "closure: the removal grace clock now runs for its postings instead of being held indefinitely."
)


def _event(etype, *, job_id=None, notes=None, eid="evt-1"):
    return ChangeEvent(
        event_id=eid, event_type=etype, source_id="greenhouse:example", job_id=job_id,
        run_id=RUN, as_of=datetime(2026, 9, 26, tzinfo=timezone.utc), snapshot_id="snap-1",
        notes=notes,
    )


def test_the_differs_segment_closed_note_is_withheld_and_the_report_still_publishes():
    """The exact production note. It is system text, so it is not published — and it no longer
    takes the whole morning report down with it."""
    event = _event(ChangeEventType.SOURCE_SEGMENT_CLOSED, notes=DIFFER_NOTE, eid="evt-closed")
    md, js = render_report(_input_with(_job("Senior Backend Engineer"), [event]))

    assert "real closure" not in md and "real closure" not in json.dumps(js)
    # Withheld visibly, with the durable record named, never silently.
    notice = next(line for line in md.splitlines() if "evt-closed" in line)
    assert _CHANGE_PHRASE[ChangeEventType.SOURCE_SEGMENT_CLOSED] in notice
    assert "withheld" in notice
    copy = next(e for e in js["events"] if e["event_id"] == "evt-closed")
    assert copy["notes"] is None, copy
    ChangeEvent.model_validate(copy)  # the report's copy is still a valid event record
    assert [row["event_id"] for row in js["withheld_source_notes"]] == ["evt-closed"]
    # The job is untouched by the withheld note.
    assert [row["title"] for row in js["complete_candidate_list"]] == ["Senior Backend Engineer"]


def test_a_publishable_source_note_is_still_published_verbatim():
    note = "department segment(s) ['design'] were absent from 1 of 2 required healthy downloads"
    event = _event(ChangeEventType.SOURCE_SUSPECT, notes=note, eid="evt-suspect")
    md, js = render_report(_input_with(_job("Senior Backend Engineer"), [event]))
    assert note in md
    copy = next(e for e in js["events"] if e["event_id"] == "evt-suspect")
    assert copy["notes"] == note
    assert js["withheld_source_notes"] == []


@pytest.mark.parametrize("department", ["Real Estate & Workplace", "SIU & Fraud"])
def test_a_disappeared_postings_note_quoting_its_department_publishes(department):
    """The differ's DISAPPEARED note quotes the posting's department in its lowercased segment
    form. The posting itself has left `jobs`; its department is still in the differ's state, and
    that is where the report now takes the redaction value from."""
    job = _job("Senior Backend Engineer")
    note = (f"absent in 2 consecutive SUCCESS snapshots (grace); its department segment "
            f"{department.strip().lower()!r} was confirmed closed after independent corroboration")
    event = _event(ChangeEventType.DISAPPEARED, job_id="greenhouse:example#gone-1", notes=note,
                   eid="evt-gone")
    inp = _input_with(job, [event])
    with pytest.raises(NeverFakeViolation):  # without the differ's state, it is unrecognizable
        render_report(inp)
    inp.state_source_text = {department}
    md, js = render_report(inp)
    copy = next(e for e in js["events"] if e["event_id"] == "evt-gone")
    assert copy["notes"] == note  # published verbatim: job-scoped notes are never withheld


def test_a_job_scoped_claim_beside_a_quoted_department_still_fails():
    """Redacting the department does not blind the guard to the system's own words around it."""
    job = _job("Senior Backend Engineer")
    note = "its department segment 'real estate & workplace' was a ghost team; posting is fake"
    event = _event(ChangeEventType.DISAPPEARED, job_id="greenhouse:example#gone-1", notes=note)
    inp = _input_with(job, [event])
    inp.state_source_text = {"Real Estate & Workplace"}
    with pytest.raises(NeverFakeViolation):
        render_report(inp)


def test_a_source_note_that_only_fails_once_json_escaped_is_withheld():
    # "real\u00e9" passes the raw check (\u00e9 is a word character, so there is no
    # boundary after "real"), but the JSON dump writes an escape whose backslash IS a boundary.
    note = "segment real\u00e9 absent"
    event = _event(ChangeEventType.SOURCE_SUSPECT, notes=note, eid="evt-esc")
    _md, js = render_report(_input_with(_job("Senior Backend Engineer"), [event]))
    assert [row["event_id"] for row in js["withheld_source_notes"]] == ["evt-esc"]


def test_a_job_scoped_note_accusing_a_posting_still_fails_the_report():
    """A note ON A POSTING is a claim about that posting. That stays a hard failure, unchanged."""
    job = _job("Senior Backend Engineer")
    event = _event(ChangeEventType.MATERIALLY_CHANGED, job_id=job.job_id,
                   notes="this looks like a fake posting")
    with pytest.raises(NeverFakeViolation):
        render_report(_input_with(job, [event]))


@pytest.mark.parametrize("phrase", [
    "confirmed a fake posting", "a real vacancy", "likely a scam", "ghost listing",
])
def test_report_authored_claims_are_still_rejected_even_beside_a_guarded_source_title(
    monkeypatch, phrase
):
    """The report's OWN wording is checked exactly as before, including when a sourced title that
    legitimately contains a guarded word is on the same page — redacting the title must not blind
    the guard to the system's sentence."""
    monkeypatch.setitem(_CHANGE_PHRASE, ChangeEventType.SOURCE_SEGMENT_CLOSED, phrase)
    event = _event(ChangeEventType.SOURCE_SEGMENT_CLOSED, eid="evt-own")
    with pytest.raises(NeverFakeViolation):
        render_report(_input_with(_job(PIPE_TITLE), [event]))


def test_the_vocabulary_rule_itself_is_unchanged():
    for bad in ("This job is fake", "a real vacancy", "clearly a scam", "fraudulent listing"):
        with pytest.raises(NeverFakeViolation):
            assert_no_banned_vocab(bad)
    assert_no_banned_vocab("Job Posting Reality Score — really already surfaced")


def test_only_postings_this_runs_events_name_contribute_differ_state_text():
    """A stale record's lone word must not become an excuse for that word anywhere in the report."""
    from src.report.handler import assemble_report_input

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sid = "greenhouse:example"
        s3.put_object(Bucket=BUCKET, Key=s3layout.run_manifest_key(RUN), Body=json.dumps({
            "run_id": RUN, "opened_at": "2026-09-26T11:00:00Z",
            "expected_sources": [sid], "source_labels": {sid: "example"},
        }).encode())
        record = {"department": None, "team": None, "title_norm": None}
        s3.put_object(Bucket=BUCKET, Key=s3layout.current_state_key("greenhouse", "example"),
                      Body=json.dumps({"jobs": {
                          f"{sid}#gone": {**record, "department": "Real Estate & Workplace"},
                          f"{sid}#stale": {**record, "department": "Fraud", "team": "ghost"},
                      }}).encode())
        s3.put_object(Bucket=BUCKET, Key=s3layout.current_jobs_key("greenhouse", "example"),
                      Body=b"[]")
        gone = _event(ChangeEventType.DISAPPEARED, job_id=f"{sid}#gone", eid="evt-gone")
        gone.source_id = sid
        s3.put_object(Bucket=BUCKET, Key=s3layout.events_key("greenhouse", "example", RUN),
                      Body=json.dumps([gone.model_dump(mode="json")]).encode())
        inp = assemble_report_input(s3, BUCKET, RUN, RUN)
    assert inp.state_source_text == {"Real Estate & Workplace"}
