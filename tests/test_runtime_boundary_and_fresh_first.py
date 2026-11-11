"""Regression tests for the P02 review's remaining blockers: R1, R3, R4 and the fresh-first item.

Each test here failed before the P03 repair; the independent reproduction is
`evidence/review_probe_reproduction.txt` in the P03 run root.

The R1 lesson is baked into how these are written. P02's R1 test replaced `_live_fetcher` — the very
function that was broken — with a capturing substitute, so it asserted the URL passed *into* the
faulty function rather than the request that went *out*. Every R1 test below therefore keeps
`_live_fetcher` and the connector/fetcher wiring intact and mocks at `urllib.request.urlopen`, the
actual transport boundary.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from moto import mock_aws

from src.common.connectors import FetchResult
from src.common.models import CanonicalJob, IdKind, RemoteMode, ScreenOutcome

from src.candidate.screening import HUMAN_FIRST_HOLD  # noqa: E402

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
BUCKET = "jprs-p03-bucket"
FAKE_ID = "FAKE_APP_ID_p03"
FAKE_KEY = "FAKE_APP_KEY_p03"
PROCESS_OK = "Interview process: two video calls with the team."


# ==================================================================================================
# helpers: a transport-level interceptor, not a fetcher substitute
# ==================================================================================================
class _Response:
    """Minimal urlopen-compatible response."""

    def __init__(self, body: bytes = b'{"results": []}', status: int = 200):
        self._body = body
        self.status = status
        self.headers = {}

    def read(self, *_a):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class Transport:
    """Records every URL that actually reaches the HTTP layer."""

    def __init__(self, body: bytes = b'{"results": []}'):
        self.urls: list[str] = []
        self.body = body

    def __call__(self, request, **_kw):
        url = getattr(request, "full_url", str(request))
        self.urls.append(url)
        return _Response(self.body)

    def query(self, index: int = 0) -> dict:
        return parse_qs(urlparse(self.urls[index]).query, keep_blank_values=True)


def _job(description, title="Senior Software Engineer", **kw):
    # canonical_location is DERIVED from the location, not hardcoded. It used to be pinned to
    # "remote, us" whatever was passed, which silently made every fixture look remote and would have
    # let a location test pass for the wrong reason.
    location = kw.pop("location", "Remote, US")
    return CanonicalJob(
        source_id="t:src", job_id=f"t:src#{abs(hash(description + title + location)) % 10**8}",
        id_kind=IdKind.NATIVE_ID, title=title, description_text=description,
        raw_location=location, canonical_location=location.lower(),
        remote_hybrid_language=RemoteMode.REMOTE, **kw,
    )


def _screen(description, title="Senior Software Engineer"):
    from src.candidate.screening import screen_job

    return screen_job(_job(description, title))


# ==================================================================================================
# R1 — credentials must survive the REAL call, not just the URL handed to the fetcher
# ==================================================================================================
def test_r1_credentials_reach_the_actual_http_request_with_live_fetcher_intact():
    """The review's central finding, as a test.

    `_live_fetcher` discarded the authenticated URL it was given, fetched the UNBOUND registry
    connector, and let it rebuild the endpoint from `os.environ` — which was empty. Observed at
    `urlopen`: `app_id=[""]`.
    """
    from src.discovery.handler import _live_fetcher, run_discovery

    transport = Transport()
    with patch.dict(os.environ, {}, clear=True), \
            patch("urllib.request.urlopen", transport):
        run_discovery(
            run_id="p03", now=NOW, fetcher=_live_fetcher, providers=["adzuna"],
            env={"ADZUNA_APP_ID": FAKE_ID, "ADZUNA_APP_KEY": FAKE_KEY},
            max_pages_per_source=1,
        )

    assert transport.urls, "no HTTP request reached the transport"
    query = transport.query(0)
    assert query.get("app_id") == [FAKE_ID], query.get("app_id")
    assert query.get("app_key") == [FAKE_KEY], query.get("app_key")


def test_r1_every_request_that_reaches_the_wire_carries_the_credential():
    """Not just the first: a later location-scoped page must be authenticated too."""
    from src.discovery.handler import _live_fetcher, run_discovery

    transport = Transport()
    with patch.dict(os.environ, {}, clear=True), \
            patch("urllib.request.urlopen", transport):
        run_discovery(
            run_id="p03", now=NOW, fetcher=_live_fetcher, providers=["adzuna"],
            env={"ADZUNA_APP_ID": FAKE_ID, "ADZUNA_APP_KEY": FAKE_KEY},
            max_pages_per_source=6,
        )
    assert len(transport.urls) >= 2
    for index in range(len(transport.urls)):
        query = transport.query(index)
        assert query.get("app_id") == [FAKE_ID], transport.urls[index]
        assert query.get("app_key") == [FAKE_KEY], transport.urls[index]


def test_r1_location_scopes_reach_the_wire_without_narrowing_everything_to_one_state():
    from src.discovery.handler import _live_fetcher, run_discovery

    transport = Transport()
    with patch.dict(os.environ, {}, clear=True), \
            patch("urllib.request.urlopen", transport):
        run_discovery(
            run_id="p03", now=NOW, fetcher=_live_fetcher, providers=["adzuna"],
            env={"ADZUNA_APP_ID": FAKE_ID, "ADZUNA_APP_KEY": FAKE_KEY},
            max_pages_per_source=8,
        )
    scoped = [u for u in transport.urls if "where=" in u]
    unscoped = [u for u in transport.urls if "where=" not in u]
    assert scoped, "no location-scoped request reached the wire"
    assert unscoped, "nationwide coverage was lost"
    assert any("ampshire" in u for u in scoped)


def test_r1_host_validation_still_applies_to_a_supplied_url():
    """Passing a prebuilt URL must not bypass the SSRF allowlist."""
    from src.common.connectors import get_connector

    connector = get_connector("greenhouse")
    with pytest.raises(ValueError, match="allowlist"):
        connector.fetch_raw("acme", url="https://evil.example/steal")


def test_r1_receipt_redacts_the_credential_from_the_supplied_url():
    from src.common.connectors import _receipt
    from src.common.models import Provider

    fr = FetchResult(
        raw_bytes=b"{}", http_status=200, error_class=None,
        endpoint_url=f"https://api.adzuna.com/v1/api/jobs/us/search/1?app_id={FAKE_ID}"
                     f"&app_key={FAKE_KEY}&what=engineer",
        request_at=NOW, response_at=NOW,
    )
    receipt = _receipt(Provider.ADZUNA, fr)
    assert FAKE_ID not in receipt.endpoint_url
    assert FAKE_KEY not in receipt.endpoint_url
    assert "app_id=REDACTED" in receipt.endpoint_url


@mock_aws
def test_r1_default_handler_with_mocked_ssm_authenticates_at_the_transport(monkeypatch):
    """End to end at the handler boundary: SSM -> handler -> connector -> real fetcher -> wire."""
    from src.discovery import handler as handler_module

    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    monkeypatch.setenv("JPRS_BUCKET", BUCKET)
    monkeypatch.setenv("JPRS_SECRETS_SSM_PREFIX", "/jprs/secrets")
    monkeypatch.delenv("JPRS_DISCOVERY_PROVIDERS", raising=False)
    monkeypatch.setenv("JPRS_DISCOVERY_PROVIDERS", "adzuna")

    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    ssm = boto3.client("ssm", region_name="us-east-1")
    ssm.put_parameter(Name="/jprs/secrets/ADZUNA_APP_ID", Value=FAKE_ID, Type="SecureString")
    ssm.put_parameter(Name="/jprs/secrets/ADZUNA_APP_KEY", Value=FAKE_KEY, Type="SecureString")

    transport = Transport()
    # _live_fetcher is NOT replaced. Only the socket layer is.
    with patch("urllib.request.urlopen", transport):
        result = handler_module.handler({"run_id": "2026-09-24"}, None)

    assert "adzuna" in result["discovery_attempted"]
    assert transport.urls, "the handler made no HTTP request"
    assert transport.query(0).get("app_id") == [FAKE_ID]

    # and the fake credential must not have landed in any stored artifact
    s3 = boto3.client("s3", region_name="us-east-1")
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET):
        for item in page.get("Contents", []):
            body = s3.get_object(Bucket=BUCKET, Key=item["Key"])["Body"].read()
            assert FAKE_ID.encode() not in body, item["Key"]
            assert FAKE_KEY.encode() not in body, item["Key"]


def test_r1_missing_credentials_still_produce_a_visible_gate_and_no_request():
    from src.discovery.handler import _live_fetcher, run_discovery

    transport = Transport()
    with patch.dict(os.environ, {}, clear=True), \
            patch("urllib.request.urlopen", transport):
        outcome = run_discovery(
            run_id="p03", now=NOW, fetcher=_live_fetcher, providers=["adzuna"], env={},
        )
    assert transport.urls == []
    assert [g["provider"] for g in outcome.credential_gated] == ["adzuna"]


# ==================================================================================================
# R3 — aggregate ALL requirement evidence, and treat optionality correctly
# ==================================================================================================
def test_r3_optional_recorded_video_with_a_live_alternative_is_not_a_hard_exclusion():
    """Review case 1. Was EXCLUDED."""
    result = _screen(
        "Interview process: A recorded video introduction is optional. "
        "You may instead have a live video call with the team."
    )
    assert "recorded-video" not in {h.rule_id for h in result.exclusions}, result.human_reason()
    assert result.outcome != ScreenOutcome.EXCLUDED.value


def test_r3_a_later_mandatory_video_still_excludes_despite_an_earlier_negation():
    """Review case 2. Was ELIGIBLE — the negation suppressed the rule and the real requirement
    was never examined."""
    result = _screen(
        "Interview process: We do not require a recorded video introduction. "
        "You must complete a one-way video interview in the final round."
    )
    assert "recorded-video" in {h.rule_id for h in result.pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}, result.human_reason()


def test_r3_a_separate_mandatory_drug_screening_still_excludes_after_a_clearance_negation():
    """Review case 3. Was PENDING_CHECK with the clearance rule suppressed."""
    result = _screen(
        "Requirements: No security clearance is required. "
        "You must pass a drug screening before starting."
    )
    assert "clearance-government" in {h.rule_id for h in result.exclusions}, result.human_reason()


def test_r3_sales_tooling_does_not_cancel_an_explicit_quota_in_the_same_sentence():
    """Review case 4. Was PENDING_CHECK with the sales rule suppressed."""
    result = _screen(
        "Responsibilities: You will build tools for the sales team and carry a sales quota."
    )
    assert "sales-ownership" in {h.rule_id for h in result.exclusions}, result.human_reason()


@pytest.mark.parametrize("description", [
    # clause order reversed: the mandatory duty comes first
    "Responsibilities: You will carry a sales quota and build tools for the sales team.",
    # separated by a semicolon
    "Responsibilities: You will build sales tooling; you will also carry a quota.",
    # cold calling alongside tooling
    "You will build internal dashboards for the revenue team and do cold calling daily.",
])
def test_r3_reordered_and_separated_mandatory_sales_duties_still_exclude(description):
    result = _screen(description)
    assert "sales-ownership" in {h.rule_id for h in result.exclusions}, result.human_reason()


def test_r3_pure_sales_tooling_with_no_quota_remains_eligible():
    """The guard must keep working where it was right."""
    result = _screen(
        "What you will do: Build tools for the sales team to research prospects. "
        "Requirements: Python. There is no quota. " + PROCESS_OK
    )
    assert "sales-ownership" not in {h.rule_id for h in result.exclusions}, result.human_reason()


def test_r3_negations_alone_still_suppress_when_there_is_no_later_requirement():
    for description in (
        "Requirements: Python. No security clearance is required. " + PROCESS_OK,
        "Application process: We do not require a recorded video. " + PROCESS_OK,
    ):
        result = _screen(description)
        assert not result.exclusions, (description, result.human_reason())


def test_r3_optional_ai_interview_is_not_treated_as_mandatory():
    result = _screen(
        "Hiring process: an AI-led interview is optional; you may request a human screen instead."
    )
    assert "ai-interview" not in {h.rule_id for h in result.exclusions}, result.human_reason()


def test_r3_mandatory_ai_interview_after_an_optional_mention_still_excludes():
    result = _screen(
        "Hiring process: the AI screen is optional at first. "
        "All candidates must then complete an interview with our AI interviewer."
    )
    assert "ai-interview" in {h.rule_id for h in result.pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}, result.human_reason()


def test_r3_html_encoded_variant_of_the_aggregation_cases_behaves_identically():
    native = _screen(
        "Interview process: We do not require a recorded video introduction. "
        "You must complete a one-way video interview in the final round."
    )
    encoded = _screen(
        "Interview process: We don&#39;t require a recorded video introduction. "
        "You must complete a one-way video interview &amp; nothing else."
    )
    assert "recorded-video" in {h.rule_id for h in native.pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}
    assert "recorded-video" in {h.rule_id for h in encoded.pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}


def test_r3_optional_without_a_stated_alternative_goes_to_review_not_to_a_verdict():
    result = _screen(
        "Interview process: a recorded video introduction is optional for some candidates."
    )
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value, result.human_reason()
    assert "recorded-video" in {h.rule_id for h in result.pending_checks}


def test_r3_genuine_hard_exclusions_are_all_preserved():
    cases = {
        "clearance": ("Requirements: an active TS/SCI security clearance is required. " + PROCESS_OK,
                      "clearance-government"),
        "drug": ("Requirements: you must pass a drug test before starting. " + PROCESS_OK,
                 "clearance-government"),
        "video": ("Application process: please record a short video introduction. ",
                  "recorded-video"),
        "ai": ("Hiring process: your first screen is an interview with our AI interviewer.",
               "ai-interview"),
        "sales-title": ("You will manage customer relationships.", "sales-ownership"),
        "quota": ("You will carry a quota and close new business. " + PROCESS_OK,
                  "sales-ownership"),
        "frontend": ("The role: own our design system and pixel-perfect visual polish. "
                     + PROCESS_OK, "frontend-specialist"),
    }
    for name, (description, rule) in cases.items():
        title = "Account Executive" if name == "sales-title" else "Senior Software Engineer"
        result = _screen(description, title)
        if rule in ("recorded-video", "ai-interview"):
            # Held under the human-first rule rather than excluded (2026-10-12).
            assert rule in {h.rule_id for h in result.pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}, (name, result.human_reason())
            continue
        assert rule in {h.rule_id for h in result.exclusions}, (name, result.human_reason())


def test_r3_an_ordinary_good_role_is_still_eligible():
    result = _screen(
        "What you will do: you will build internal tools and automate back-office processes with "
        "Python services on AWS. Requirements: five years of software engineering. " + PROCESS_OK
    )
    assert result.outcome == ScreenOutcome.ELIGIBLE.value, result.human_reason()


# ==================================================================================================
# R4 — rollback must be safe for PERSISTED STATE, not only source files
# ==================================================================================================
BASELINE_REVISION = "e549a73"


def _baseline_module(path: str, name: str):
    """Load a module from the historical revision without checking anything out."""
    import subprocess
    import types

    source = subprocess.run(
        ["git", "show", f"{BASELINE_REVISION}:{path}"],
        capture_output=True, text=True, check=True,
    ).stdout
    module = types.ModuleType(name)
    module.__dict__["__name__"] = name
    import sys

    sys.modules[name] = module
    exec(compile(source, f"{BASELINE_REVISION}:{path}", "exec"), module.__dict__)
    return module


def test_r4_baseline_reader_rejects_current_records_before_downgrade():
    """The premise the P02 handoff got wrong: additive fields are NOT ignored by the old reader."""
    from src.common.normalize import compute_hashes

    baseline = _baseline_module("src/common/models.py", "_baseline_models_r4a")
    current = CanonicalJob(
        source_id="greenhouse:acme", job_id="greenhouse:acme#1", id_kind=IdKind.NATIVE_ID,
        employer_name="Acme", title="Engineer", description_text="d",
        raw_location="Remote, US", canonical_location="remote, us",
    ).model_dump(mode="json")
    with pytest.raises(Exception) as exc:
        baseline.CanonicalJob.model_validate(current)
    assert "employer_name" in str(exc.value)


def test_r4_downgrade_makes_records_readable_by_the_exact_baseline_model():
    from src.common.rollback import downgrade_canonical_job

    baseline = _baseline_module("src/common/models.py", "_baseline_models_r4b")
    current = CanonicalJob(
        source_id="greenhouse:acme", job_id="greenhouse:acme#1", id_kind=IdKind.NATIVE_ID,
        employer_name="Acme", title="Engineer", description_text="d",
        raw_location="Remote, US", canonical_location="remote, us",
        first_seen_at=NOW, last_seen_at=NOW,
    ).model_dump(mode="json")
    downgraded = downgrade_canonical_job(current)
    restored = baseline.CanonicalJob.model_validate(downgraded)
    assert restored.job_id == "greenhouse:acme#1"
    assert restored.title == "Engineer"


def test_r4_downgrade_preserves_every_job_so_rollback_cannot_manufacture_removals():
    from src.common.rollback import downgrade_current_jobs

    records = [
        CanonicalJob(source_id="greenhouse:acme", job_id=f"greenhouse:acme#{i}",
                     id_kind=IdKind.NATIVE_ID, employer_name="Acme", title=f"Engineer {i}",
                     first_seen_at=NOW, last_seen_at=NOW).model_dump(mode="json")
        for i in range(7)
    ]
    out = downgrade_current_jobs(records)
    assert len(out) == len(records)
    assert {r["job_id"] for r in out} == {r["job_id"] for r in records}


def test_r4_downgrade_preserves_diff_state_job_ids_and_grace_clocks():
    from src.common.rollback import downgrade_diff_state
    from src.differ.handler import DiffState, JobStateRecord

    baseline = _baseline_module("src/differ/handler.py", "_baseline_differ_r4c")
    state = DiffState(
        source_id="greenhouse:acme",
        jobs={"greenhouse:acme#1": JobStateRecord(
            job_id="greenhouse:acme#1", first_seen_at=NOW, last_seen_at=NOW, absence_count=1,
        )},
        success_count_history=[5, 5],
        suspect_streak=3, suspect_kind="silent_subset",
        segment_absence_streak={"people team": 2},
    ).model_dump(mode="json")

    with pytest.raises(Exception):
        baseline.DiffState.model_validate(state)

    downgraded = downgrade_diff_state(state)
    restored = baseline.DiffState.model_validate(downgraded)
    assert set(restored.jobs) == {"greenhouse:acme#1"}
    assert restored.jobs["greenhouse:acme#1"].absence_count == 1   # grace clock preserved
    assert restored.success_count_history == [5, 5]


def test_r4_downgrade_drops_event_types_the_baseline_enum_cannot_parse():
    from src.common.rollback import downgrade_events

    baseline = _baseline_module("src/common/models.py", "_baseline_models_r4d")
    events = [
        {"event_id": "r:s:first-seen", "event_type": "first-seen", "source_id": "s",
         "job_id": "s#1", "run_id": "r", "as_of": NOW.isoformat(), "snapshot_id": "snap"},
        {"event_id": "r:s:closed", "event_type": "source-segment-closed", "source_id": "s",
         "run_id": "r", "as_of": NOW.isoformat(), "snapshot_id": "snap"},
    ]
    kept, dropped = downgrade_events(events)
    assert len(kept) == 1 and dropped == 1
    for event in kept:
        baseline.ChangeEvent.model_validate(event)


@mock_aws
def test_r4_forward_run_then_rollback_read_then_restart_without_removals(monkeypatch):
    """The scenario the review demanded: run forward, downgrade, read with the baseline model, and
    confirm the baseline differ produces no removal for jobs that were never refreshed again."""
    from src.common import s3layout
    from src.common.rollback import downgrade_bucket_state
    from src.differ.handler import diff_source
    from tests.conftest import make_job, make_snapshot
    from src.common.models import SnapshotStatus

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)

    # --- forward run with the CURRENT code: write current_jobs + diff state -----------------------
    jobs = [make_job(f"j{i}", fetched_at=NOW) for i in range(4)]
    snapshot = make_snapshot(SnapshotStatus.SUCCESS, n=len(jobs), fetched_at=NOW)
    result = diff_source(None, snapshot, jobs, run_id="fwd", today=NOW)
    provider, board = "greenhouse", "acme"
    s3.put_object(Bucket=BUCKET, Key=s3layout.current_jobs_key(provider, board),
                  Body=json.dumps([j.model_dump(mode="json") for j in result.current_jobs],
                                  default=str).encode())
    s3.put_object(Bucket=BUCKET, Key=s3layout.current_state_key(provider, board),
                  Body=json.dumps(result.state.model_dump(mode="json"), default=str).encode())
    s3.put_object(Bucket=BUCKET, Key=s3layout.events_key(provider, board, "2026-09-24"),
                  Body=json.dumps([e.model_dump(mode="json") for e in result.events],
                                  default=str).encode())

    baseline_models = _baseline_module("src/common/models.py", "_baseline_models_r4e")
    baseline_differ = _baseline_module("src/differ/handler.py", "_baseline_differ_r4e")

    raw_jobs = json.loads(s3.get_object(
        Bucket=BUCKET, Key=s3layout.current_jobs_key(provider, board))["Body"].read())
    with pytest.raises(Exception):
        baseline_models.CanonicalJob.model_validate(raw_jobs[0])

    # --- downgrade, with a backup kept ----------------------------------------------------------
    report = downgrade_bucket_state(s3, BUCKET, dt="2026-09-24", now=NOW)
    assert report["objects_backed_up"] >= 3
    assert report["current_jobs_records"] == 4
    for key in report["backup_keys"]:
        s3.head_object(Bucket=BUCKET, Key=key)   # backup really exists

    # --- baseline code can now read the state ---------------------------------------------------
    raw_jobs = json.loads(s3.get_object(
        Bucket=BUCKET, Key=s3layout.current_jobs_key(provider, board))["Body"].read())
    restored_jobs = [baseline_models.CanonicalJob.model_validate(r) for r in raw_jobs]
    assert len(restored_jobs) == 4
    raw_state = json.loads(s3.get_object(
        Bucket=BUCKET, Key=s3layout.current_state_key(provider, board))["Body"].read())
    restored_state = baseline_differ.DiffState.model_validate(raw_state)
    assert len(restored_state.jobs) == 4

    # --- restart on the baseline: same jobs present again -> no removals ------------------------
    baseline_snapshot = baseline_models.SourceSnapshot(
        snapshot_id="s2", source_id="greenhouse:acme", fetched_at=NOW + timedelta(days=1),
        status=baseline_models.SnapshotStatus.SUCCESS, job_count_observed=4,
    )
    after = baseline_differ.diff_source(
        restored_state, baseline_snapshot, restored_jobs,
        run_id="rollback", today=NOW + timedelta(days=1),
    )
    removals = [e for e in after.events
                if e.event_type == baseline_models.ChangeEventType.DISAPPEARED]
    assert removals == [], "rollback manufactured removals"
    assert len(after.state.jobs) == 4


def test_r4_downgrade_is_idempotent():
    from src.common.rollback import downgrade_canonical_job

    record = CanonicalJob(
        source_id="s", job_id="s#1", id_kind=IdKind.NATIVE_ID, employer_name="E", title="T",
    ).model_dump(mode="json")
    once = downgrade_canonical_job(record)
    twice = downgrade_canonical_job(once)
    assert once == twice


# ==================================================================================================
# F1 — fresh-first: new arrivals get prompt attention even with a nonempty backlog
# ==================================================================================================
def _him_page(page, cursor_out, *, employer, pub):
    return {
        "jobs": [{
            "title": "Senior Software Engineer",
            "companyName": employer,
            "companySlug": employer.lower().replace(" ", "-"),
            "excerpt": "You will build Python services on AWS and automate internal processes.",
            "description": "You will build Python services on AWS and automate internal processes.",
            "applicationLink": f"https://himalayas.app/companies/x/jobs/{page}",
            "guid": f"https://himalayas.app/companies/x/jobs/{page}",
            "locationRestrictions": "['United States']", "employmentType": "Full Time",
            "pubDate": str(int(pub.timestamp())),
        }],
        "nextCursor": cursor_out, "totalCount": 999,
    }


def test_f1_head_is_rechecked_each_run_even_with_a_saved_backlog_cursor():
    """The review's two-run probe: day two requested only `OLDER_PAGE_2`, never the head.

    The Himalayas cursor is a DESCENDING timestamp (measured: page 1 head 14:20, each cursor older),
    so resuming from a saved cursor walks away from new arrivals and never returns.
    """
    from src.discovery.budget import DiscoveryState
    from src.discovery.handler import run_discovery

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLDER_PAGE_2"

    requested: list[str | None] = []

    def fetcher(provider, token, url):
        cursor = url.split("cursor=")[1].split("&")[0] if "cursor=" in url else None
        requested.append(cursor)
        if cursor is None:
            return FetchResult(
                raw_bytes=json.dumps(_him_page(1, "HEAD_NEXT", employer="Fresh Arrival Co",
                                               pub=NOW)).encode(),
                http_status=200, error_class=None, endpoint_url=url,
                request_at=NOW, response_at=NOW)
        return FetchResult(
            raw_bytes=json.dumps(_him_page(2, "OLDER_PAGE_3", employer="Older Co",
                                           pub=NOW - timedelta(days=9))).encode(),
            http_status=200, error_class=None, endpoint_url=url, request_at=NOW, response_at=NOW)

    outcome = run_discovery(run_id="day2", now=NOW, fetcher=fetcher, providers=["himalayas"],
                            state=state, env={}, max_pages_per_source=2)

    assert None in requested, f"the head was never requested; cursors used: {requested}"
    employers = {j.employer_name for j in outcome.jobs}
    assert "Fresh Arrival Co" in employers, "a new head arrival did not reach the run"
    # catch-up still progressed rather than restarting at page one forever
    assert "OLDER_PAGE_2" in requested, f"backlog catch-up was abandoned: {requested}"
    assert outcome.state.source_cursors["himalayas"] == "OLDER_PAGE_3"


def test_f1_catch_up_progresses_across_runs_without_starving_the_head():
    from src.discovery.budget import DiscoveryState
    from src.discovery.handler import run_discovery

    chain = {None: "C1", "C1": "C2", "C2": "C3", "C3": None}

    def fetcher(provider, token, url):
        cursor = url.split("cursor=")[1].split("&")[0] if "cursor=" in url else None
        return FetchResult(
            raw_bytes=json.dumps(_him_page(cursor or "head", chain.get(cursor),
                                           employer=f"Co {cursor or 'head'}",
                                           pub=NOW)).encode(),
            http_status=200, error_class=None, endpoint_url=url, request_at=NOW, response_at=NOW)

    state = DiscoveryState()
    seen_cursors = []
    for run in range(3):
        outcome = run_discovery(run_id=f"d{run}", now=NOW, fetcher=fetcher,
                                providers=["himalayas"], state=state, env={},
                                max_pages_per_source=2)
        state = outcome.state
        seen_cursors.append(state.source_cursors.get("himalayas"))
    # the saved cursor advances monotonically through the chain
    assert seen_cursors[0] != seen_cursors[1], seen_cursors
    assert None not in seen_cursors[:1]


def test_f1_first_seen_survives_repeat_observation_and_dedup_merge():
    """Plan §3: first-seen must not be reset by a later sighting or by a merge."""
    from src.common.dedup import deduplicate

    earlier = NOW - timedelta(days=5)
    board = CanonicalJob(
        source_id="greenhouse:acme", job_id="greenhouse:acme#1", id_kind=IdKind.NATIVE_ID,
        employer_name="Acme", title="Engineer",
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        first_seen_at=earlier, last_seen_at=NOW,
    )
    feed = CanonicalJob(
        source_id="remotive:all", job_id="remotive:all#9", id_kind=IdKind.NATIVE_ID,
        employer_name="Acme", title="Engineer",
        posting_url="https://boards.greenhouse.io/acme/jobs/1?utm_source=x",
        apply_url="https://boards.greenhouse.io/acme/jobs/1?utm_source=x",
        first_seen_at=NOW, last_seen_at=NOW,
    )
    kept, _report = deduplicate([board, feed])
    assert len(kept) == 1
    assert kept[0].first_seen_at == earlier, "the merge reset first-seen to the newer sighting"


def test_f1_report_separates_fresh_arrivals_without_letting_a_fresh_bad_fit_outrank_a_strong_fit():
    from src.candidate.screening import screen_job
    from src.report.handler import ReportInput, render_report
    from src.scoring.scoring import ScoreContext, score_job

    strong_but_older = CanonicalJob(
        source_id="remotive:all", job_id="remotive:all#strong", id_kind=IdKind.NATIVE_ID,
        employer_name="Older Strong Co", title="Senior Applied AI Engineer",
        description_text=("What you will do: you will build LLM integrations and agentic workflows "
                          "in Python on AWS Lambda and own the evaluation harness. " + PROCESS_OK),
        posting_url="https://remotive.com/remote-jobs/strong",
        apply_url="https://remotive.com/remote-jobs/strong",
        raw_location="USA", canonical_location="united states",
        remote_hybrid_language=RemoteMode.REMOTE,
        provider_published_at=NOW - timedelta(days=20),
        first_seen_at=NOW - timedelta(days=20), last_seen_at=NOW,
    )
    fresh_weak = CanonicalJob(
        source_id="remotive:all", job_id="remotive:all#fresh", id_kind=IdKind.NATIVE_ID,
        employer_name="Fresh Weak Co", title="Software Engineer",
        description_text="You will maintain a legacy reporting script. " + PROCESS_OK,
        posting_url="https://remotive.com/remote-jobs/fresh",
        apply_url="https://remotive.com/remote-jobs/fresh",
        raw_location="USA", canonical_location="united states",
        remote_hybrid_language=RemoteMode.REMOTE,
        provider_published_at=NOW - timedelta(hours=3),
        first_seen_at=NOW, last_seen_at=NOW,
    )
    jobs = [strong_but_older, fresh_weak]
    cards = [score_job(ScoreContext(job=j), today=NOW) for j in jobs]
    screens = {j.job_id: screen_job(j) for j in jobs}
    inp = ReportInput(
        run_id="2026-09-24", dt="2026-09-24", expected_sources=["remotive:all"],
        succeeded_sources=["remotive:all"], jobs=jobs, scorecards=cards,
        screen_results=screens, run_started_at=NOW, previous_run_at=NOW - timedelta(days=1),
    )
    md, js = render_report(inp)

    # a fresh-arrivals surface exists
    assert "New since" in md or "Fresh" in md
    # ...and the complete list is still ordered by fit, so freshness cannot invert quality
    order = [row["job_id"] for row in js["complete_candidate_list"]]
    if "remotive:all#strong" in order and "remotive:all#fresh" in order:
        assert order.index("remotive:all#strong") < order.index("remotive:all#fresh"), order


def test_f1_age_basis_and_source_lag_are_labelled_and_unknown_age_is_not_invented():
    from src.report.handler import age_label

    published = age_label(
        provider_published_at=NOW - timedelta(hours=5), provider_updated_at=None,
        first_seen_at=NOW, now=NOW, source_lag_hours=24,
    )
    assert "publish" in published.lower()
    unknown = age_label(
        provider_published_at=None, provider_updated_at=None,
        first_seen_at=NOW, now=NOW, source_lag_hours=None,
    )
    assert "unknown" in unknown.lower()
    assert "first seen" in unknown.lower()


def test_f1_nothing_is_excluded_merely_for_being_older_than_24_hours():
    from src.candidate.screening import screen_job

    old = _job(
        "What you will do: you will build internal tools with Python on AWS. " + PROCESS_OK,
        provider_published_at=NOW - timedelta(days=45), first_seen_at=NOW - timedelta(days=45),
    )
    assert screen_job(old).outcome == ScreenOutcome.ELIGIBLE.value


def test_f1_budget_of_one_page_reports_backfill_starvation_instead_of_hiding_it():
    """At a 1-page budget the head wins, and the operator is told the backfill did not move."""
    from src.discovery.budget import DiscoveryState
    from src.discovery.handler import run_discovery

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLDER_PAGE_2"
    requested: list[str | None] = []

    def fetcher(provider, token, url):
        cursor = url.split("cursor=")[1].split("&")[0] if "cursor=" in url else None
        requested.append(cursor)
        return FetchResult(
            raw_bytes=json.dumps(_him_page(1, "HEAD_NEXT", employer="Fresh Co", pub=NOW)).encode(),
            http_status=200, error_class=None, endpoint_url=url, request_at=NOW, response_at=NOW)

    outcome = run_discovery(run_id="d", now=NOW, fetcher=fetcher, providers=["himalayas"],
                            state=state, env={}, max_pages_per_source=1)
    assert requested == [None], f"the head must claim the only page, got {requested}"
    assert outcome.state.source_cursors["himalayas"] == "OLDER_PAGE_2", "backfill position kept"
    starved = [i for i in outcome.inaccessible if "backfill" in i["target"]]
    assert starved, "backfill starvation was not reported"
    assert "made no progress" in starved[0]["reason"]


def test_f1_a_first_observation_run_does_not_mark_every_posting_fresh():
    """On a cold start every first_seen_at is identical, which says when WE started looking."""
    from src.report.handler import cold_start_sources, is_fresh_arrival

    undated = [
        CanonicalJob(source_id="remotive:all", job_id=f"remotive:all#{i}",
                     id_kind=IdKind.NATIVE_ID, employer_name=f"Co {i}", title="Engineer",
                     first_seen_at=NOW, last_seen_at=NOW)
        for i in range(5)
    ]
    cold = cold_start_sources(undated)
    assert cold == {"remotive:all"}
    for job in undated:
        assert not is_fresh_arrival(job, now=NOW, previous_run_at=NOW - timedelta(days=1),
                                    cold_start=cold)

    # a published date inside the window is still admissible evidence on a cold start
    dated = undated[0].model_copy(update={"provider_published_at": NOW - timedelta(hours=2)})
    assert is_fresh_arrival(dated, now=NOW, previous_run_at=NOW - timedelta(days=1),
                            cold_start=cold)


def test_f1_on_a_warm_source_an_arrival_since_the_last_round_is_fresh():
    from src.report.handler import cold_start_sources, is_fresh_arrival

    jobs = [
        CanonicalJob(source_id="remotive:all", job_id="remotive:all#old",
                     id_kind=IdKind.NATIVE_ID, employer_name="Old Co", title="Engineer",
                     first_seen_at=NOW - timedelta(days=9), last_seen_at=NOW),
        CanonicalJob(source_id="remotive:all", job_id="remotive:all#new",
                     id_kind=IdKind.NATIVE_ID, employer_name="New Co", title="Engineer",
                     first_seen_at=NOW, last_seen_at=NOW),
    ]
    cold = cold_start_sources(jobs)
    assert cold == set()
    prev = NOW - timedelta(days=1)
    assert not is_fresh_arrival(jobs[0], now=NOW, previous_run_at=prev, cold_start=cold)
    assert is_fresh_arrival(jobs[1], now=NOW, previous_run_at=prev, cold_start=cold)


# ==================================================================================================
# Mid-run policy change: the operator-confirmed "Location and Compensation" section (2026-09-24)
# ==================================================================================================
def test_policy_boston_and_portsmouth_commuting_are_excluded_but_remote_is_not():
    """"Portsmouth and Boston commuting are excluded. An employer headquartered in either city
    remains eligible when the role is genuinely remote from New Hampshire.\""""
    from src.candidate.screening import screen_job
    from src.common.models import RemoteMode

    onsite_boston = _job(
        "The role: you will work on-site three days per week. " + PROCESS_OK,
        location="Boston, MA",
    )
    onsite_boston.remote_hybrid_language = RemoteMode.ONSITE
    result = screen_job(onsite_boston)
    assert "location-eligibility" in {h.rule_id for h in result.exclusions}, result.human_reason()

    remote_at_boston_employer = _job(
        "The role: fully remote from anywhere in the US. " + PROCESS_OK,
        location="Remote, US",
    )
    assert screen_job(remote_at_boston_employer).outcome != ScreenOutcome.EXCLUDED.value


def test_policy_genuinely_local_nh_onsite_remains_eligible():
    from src.candidate.screening import screen_job
    from src.common.models import RemoteMode

    for town in ("Laconia, NH", "Gilford, New Hampshire", "Meredith, NH", "Tilton, NH"):
        job = _job("The role: on-site at our office. " + PROCESS_OK, location=town)
        job.remote_hybrid_language = RemoteMode.ONSITE
        assert screen_job(job).outcome != ScreenOutcome.EXCLUDED.value, town


def test_policy_plymouth_nh_routes_to_review_not_a_verdict():
    """"a possible exception to discuss with Brett, not blanket approval for a longer commute\""""
    from src.candidate.screening import screen_job
    from src.common.models import RemoteMode

    job = _job("The role: on-site at our Plymouth office. " + PROCESS_OK,
               location="Plymouth, New Hampshire")
    job.remote_hybrid_language = RemoteMode.ONSITE
    result = screen_job(job)
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value, result.human_reason()
    assert "discuss with Brett" in " ".join(h.reason for h in result.pending_checks)


def test_policy_compensation_targets_are_not_converted_into_exclusion_rules():
    """"do not convert flexible targets into extra exclusion rules" — $130k and $65/hr are
    explicitly acceptable examples, so nothing may be excluded on pay."""
    from src.candidate.screening import screen_job
    from src.common.models import SalarySource, SalaryStruct

    for lo, hi in ((110_000, 130_000), (130_000, 150_000), (280_000, 340_000)):
        job = _job("What you will do: build internal tools in Python on AWS. " + PROCESS_OK)
        job.salary = SalaryStruct(min=lo, max=hi, currency="USD", period="year",
                                  source=SalarySource.STATED)
        result = screen_job(job)
        assert "compensation" not in " ".join(
            h.rule_id for h in result.exclusions
        ), (lo, hi)
        assert result.outcome != ScreenOutcome.EXCLUDED.value, (lo, hi)


def test_policy_adzuna_scopes_no_longer_spend_budget_on_excluded_commute_metros():
    from src.discovery.handler import LOCATION_SCOPES

    assert None in LOCATION_SCOPES, "nationwide coverage must remain"
    assert "New Hampshire" in LOCATION_SCOPES
    joined = " ".join(s for s in LOCATION_SCOPES if s).lower()
    assert "boston" not in joined
