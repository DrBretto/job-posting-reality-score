"""P07 acceptance: a posting from an unregistered employer reaches the saved morning report.

What this file is for
---------------------
P06 deployed discovery and measured 295 jobs across 218 employers from four live feeds, and then
every one of the report's 35 candidates came from a monitored Greenhouse board. The producer wrote
`normalized/`; the consumer read the differ-owned `current/` set for the manifest's `expected_sources`
only. Nothing joined them. This harness is the regression that fails on that code and passes on this.

The production boundary it holds itself to
------------------------------------------
Only external HTTP, AWS and SES are mocked. Every intermediate artifact is written by the stage that
owns it in production, in the order production invokes them:

    enumerate  (real handler)   -> RUN_OPEN manifest + SQS fan-out
    collector  (real collect_one, drained from the real queue) -> raw/ normalized/ status/ sentinels
    discovery  (real handler)   -> normalized/ + discovery/ live view
    differ     (real handler, once per registry company, as the Map state does) -> current/ events/
    report     (real handler)   -> reports/ + the digest

This harness never writes a manifest, `expected_sources`, a normalized or current job set, a
screening decision, a scorecard or a ReportInput of its own. The only thing it supplies is provider
bytes and the shipped configuration, which is exactly what the outside world supplies in production.
`tests/conftest.py` history/policy fixtures and the committed `config/application_history.json` are
pre-existing fixtures and are identified as such where they are relied on.

Fixture provenance, kept separate on purpose
--------------------------------------------
Two kinds of provider payload appear below and they are never mixed:

  REAL CAPTURE   payloads captured from the live feeds on 2026-09-24 and stored under the P04 run's
                 `rehearsal/fixtures/`. Used to prove each provider's own parse/normalize path still
                 carries records onto the common candidate path. A candidate appearing from one of
                 these is evidence about JPRS's handling, NOT a claim that the posting is open today.

  SYNTHETIC      payloads written here to control one variable (a fitting role, an excluded role, a
                 duplicate, a stale round). They prove pipeline behavior and nothing about the market.
"""

from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from src.common import s3layout
from src.common.connectors import FetchResult
from src.common.models import ScreenOutcome, SnapshotStatus

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = (
    ROOT / "project-factory/outputs/open-market-discovery/runs"
    / "20260924_location_and_freshness_boundaries_v1/rehearsal/fixtures"
)
BUCKET = "jprs-p07-acceptance"
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)

# An internal-tools / applied-engineering role at an employer that is NOT a software vendor and NOT
# in `config/companies.yaml`. It is the counterexample to employer whitelisting: no admission, no
# registry edit and no roster expansion may be required for it to reach the report.
UNREGISTERED_FIT = {
    "title": "Senior Software Engineer, Internal Tools and Automation",
    "companyName": "Granite State Mutual Insurance",
    "companySlug": "granite-state-mutual",
    "employmentType": "Full Time",
    "locationRestrictions": "['United States']",
    "applicationLink": "https://himalayas.app/companies/granite-state-mutual/jobs/internal-tools",
    "guid": "https://himalayas.app/companies/granite-state-mutual/jobs/internal-tools",
    "excerpt": (
        "We are an insurance carrier, not a software company, and our internal tools team is how "
        "the business runs. Responsibilities: build and maintain Python backend services and "
        "TypeScript internal applications, own AWS Lambda integrations, and stand up LLM evaluation "
        "workflows for claims triage. Remote throughout the United States. Interview process: two "
        "live video calls with the engineering team and a take-home review session."
    ),
}
UNREGISTERED_FIT["description"] = UNREGISTERED_FIT["excerpt"]

# A posting the candidate policy excludes for a stated reason. The exclusion must be attributed to
# the rule that fired, never to a fit score and never by silently dropping the row.
EXCLUDED_BY_POLICY = {
    "title": "Enterprise Account Executive",
    "companyName": "Northgate Revenue Group",
    "companySlug": "northgate-revenue",
    "employmentType": "Full Time",
    "locationRestrictions": "['United States']",
    "applicationLink": "https://himalayas.app/companies/northgate/jobs/enterprise-ae",
    "guid": "https://himalayas.app/companies/northgate/jobs/enterprise-ae",
    "excerpt": (
        "Own a named-account territory and carry an annual quota. Responsibilities: close new "
        "business, run the full sales cycle from prospecting to signature, and forecast pipeline "
        "weekly. Remote throughout the United States."
    ),
}
EXCLUDED_BY_POLICY["description"] = EXCLUDED_BY_POLICY["excerpt"]


def _feed_payload(records: list[dict], *, cursor=None, published_hours_ago: float = 2.0) -> dict:
    # Anchored to the REAL clock, not the fixed `NOW` above, because every stage these payloads are
    # fed to reads `datetime.now` — the report's 24-hour fresh window is measured against the real
    # clock. Pinning the publication date to a calendar date made "published two hours ago" true
    # only on the day the fixture was written: `test_the_round_after_the_old_format_report_writes_
    # the_new_format` began failing the day after P08 ran, on unchanged code, once that date was
    # more than 24 hours old. A fixture that decays into a failure is a defect in the fixture.
    now = datetime.now(timezone.utc)
    jobs = []
    for record in records:
        row = dict(record)
        row.setdefault(
            "pubDate",
            str(int((now - timedelta(hours=published_hours_ago)).timestamp())),
        )
        jobs.append(row)
    return {"jobs": jobs, "nextCursor": cursor, "totalCount": len(jobs)}


def _fetch_result(payload: bytes | dict, url: str = "https://example.invalid/feed") -> FetchResult:
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return FetchResult(
        raw_bytes=raw, http_status=200, error_class=None,
        endpoint_url=url, request_at=NOW, response_at=NOW,
    )


def _failed_fetch(url: str = "https://example.invalid/feed") -> FetchResult:
    return FetchResult(
        raw_bytes=None, http_status=None, error_class="timeout",
        endpoint_url=url, request_at=NOW, response_at=NOW,
    )


# A single monitored Greenhouse posting, so every discovery-side assertion below is made in the
# presence of the existing monitored population. A discovery-only demo could hide a regression there.
MONITORED_BOARD = "machinifyinc"
MONITORED_PAYLOAD = {
    "jobs": [{
        "id": 900001,
        "internal_job_id": 900001,
        "requisition_id": "R-900001",
        "title": "Senior Backend Engineer",
        "location": {"name": "Remote - US"},
        "content": (
            "Build Python backend services and AWS Lambda integrations for the platform team. "
            "Remote throughout the United States. Interview process: two live video calls."
        ),
        "departments": [{"name": "Engineering"}],
        "offices": [{"name": "Remote"}],
        "absolute_url": "https://boards.greenhouse.io/machinifyinc/jobs/900001",
        "updated_at": "2026-09-20T00:00:00Z",
    }]
}


class Harness:
    """Drives the real stages against one mocked S3/SQS/SES world, one round at a time."""

    def __init__(self, s3, queue_url: str):
        self.s3 = s3
        self.queue_url = queue_url
        self.env = {
            "JPRS_BUCKET": BUCKET,
            "AWS_DEFAULT_REGION": "us-east-1",
            "JPRS_COLLECT_QUEUE_URL": queue_url,
            "JPRS_COMPANIES_SSM": "",
            "JPRS_COMPANIES_YAML": "config/companies.yaml",
            "JPRS_DISCOVERY_YAML": "config/discovery_sources.yaml",
            "JPRS_SECRETS_SSM_PREFIX": "",
            "SES_SENDER": "",
            "DIGEST_RECIPIENT": "",
        }
        self.trace: list[dict] = []

    # -- stages ---------------------------------------------------------------------------------
    def enumerate_round(self, run_id: str) -> dict:
        from src.enumerate.handler import handler as enumerate_sources

        with patch.dict(os.environ, self.env):
            return enumerate_sources({"run_id": run_id}, None)

    def collect_monitored(self, run_id: str, *, boards: dict[str, dict] | None = None) -> list[dict]:
        """Drain the real queue through the real collector, with only the HTTP call mocked."""
        from src.collector.handler import collect_one

        boards = boards if boards is not None else {MONITORED_BOARD: MONITORED_PAYLOAD}
        results = []
        while True:
            messages = self.sqs.receive_message(
                QueueUrl=self.queue_url, MaxNumberOfMessages=10
            ).get("Messages", [])
            if not messages:
                break
            for message in messages:
                msg = json.loads(message["Body"])
                payload = boards.get(msg["board_token"])
                if payload is None:
                    self.sqs.delete_message(
                        QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"]
                    )
                    continue
                with patch.dict(os.environ, self.env), patch(
                    "src.common.connectors.Connector.fetch_raw",
                    return_value=_fetch_result(payload),
                ):
                    results.append(collect_one(self.s3, BUCKET, msg))
                self.sqs.delete_message(
                    QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"]
                )
        return results

    def discover(self, run_id: str, *, fetcher, providers: str = "himalayas") -> dict:
        from src.discovery.handler import handler as discovery

        env = dict(self.env, JPRS_DISCOVERY_PROVIDERS=providers)
        with patch.dict(os.environ, env), patch(
            "src.discovery.handler._live_fetcher", side_effect=fetcher
        ):
            return discovery({"run_id": run_id, "dt": run_id}, None)

    def diff_monitored(self, run_id: str, *, boards: list[str] | None = None) -> list[dict]:
        """One differ invocation per registry company, as the assemble Map state does."""
        from src.differ.handler import handler as differ

        boards = boards if boards is not None else [MONITORED_BOARD]
        out = []
        with patch.dict(os.environ, self.env):
            for board in boards:
                out.append(differ(
                    {"provider": "greenhouse", "board_token": board,
                     "run_id": run_id, "dt": run_id},
                    None,
                ))
        return out

    def report(self, run_id: str, *, env_extra: dict | None = None) -> dict:
        from src.report.handler import handler as report

        with patch.dict(os.environ, dict(self.env, **(env_extra or {}))):
            return report({"run_id": run_id, "dt": run_id}, None)

    # -- readers --------------------------------------------------------------------------------
    def saved_report(self, run_id: str) -> dict:
        body = self.s3.get_object(
            Bucket=BUCKET, Key=s3layout.report_json_key(run_id)
        )["Body"].read()
        return json.loads(body)

    def saved_markdown(self, run_id: str) -> str:
        return self.s3.get_object(
            Bucket=BUCKET, Key=s3layout.report_md_key(run_id)
        )["Body"].read().decode()

    def keys(self, prefix: str) -> list[str]:
        return [
            item["Key"]
            for item in self.s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", [])
        ]

    def normalized_job_ids(self) -> list[str]:
        ids = []
        for key in self.keys("normalized/"):
            body = json.loads(self.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
            ids.extend(job["job_id"] for job in body)
        return ids

    def live_view_ids(self, provider: str) -> list[str]:
        raw = json.loads(self.s3.get_object(
            Bucket=BUCKET, Key=s3layout.discovery_live_key(provider)
        )["Body"].read())
        return sorted(raw["jobs"])

    def record_stage_trace(self, label: str, run_id: str) -> dict:
        """A compact per-round census: identities and counts at every stage boundary."""
        report = self.saved_report(run_id)
        rows = report["complete_candidate_list"]
        excluded = report["policy_exclusions"]
        entry = {
            "label": label,
            "run_id": run_id,
            "fetched_normalized_job_ids": sorted(set(self.normalized_job_ids())),
            "discovery_live_view_ids": {
                provider: self.live_view_ids(provider)
                for provider in ("himalayas",)
                if s3layout.discovery_live_key(provider) in self.keys("discovery/live/")
            },
            "counts": {
                "postings_considered": report["current_job_count"],
                "deduplicated_hard_merges": (report.get("dedup") or {}).get("hard_merges", 0),
                "retained_credible": report["matching_job_count"],
                "excluded_by_policy": report["policy_excluded_count"],
                "below_fit_threshold": report["below_fit_threshold_count"],
                "needing_a_check": report["needs_check_count"],
                "fresh_arrivals": report["fresh_arrival_count"],
            },
            "report_candidate_ids": [row["job_id"] for row in rows],
            "excluded_ids_with_reason": {
                row["job_id"]: [
                    f"{hit['rule_id']}: {hit['reason']}"
                    for hit in (row.get("screen_detail") or {}).get("exclusions", [])
                ]
                for row in excluded
            },
            "discovery_candidate_ids": [
                row["job_id"] for row in rows if row["source_kind"] == "DISCOVERY_FEED"
            ],
            "monitored_candidate_ids": [
                row["job_id"] for row in rows if row["source_kind"] == "ATS_BOARD"
            ],
        }
        self.trace.append(entry)
        return entry


@pytest.fixture
def harness():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="jprs-p07-collect")["QueueUrl"]
        h = Harness(s3, queue_url)
        h.sqs = sqs
        yield h


def _round(harness, run_id, *, fetcher, collect=True, diff=True, report=True):
    """One complete production round in the order the deployed schedules invoke it."""
    harness.enumerate_round(run_id)
    if collect:
        harness.collect_monitored(run_id)
    harness.discover(run_id, fetcher=fetcher)
    if diff:
        harness.diff_monitored(run_id)
    if report:
        harness.report(run_id)


def _single_page_fetcher(records, *, cursor=None):
    def fetcher(provider, token, url):
        return _fetch_result(_feed_payload(records, cursor=cursor), url)
    return fetcher


# ==================================================================================================
# Case 1 — an unregistered employer's fitting job reaches the saved shortlist
# ==================================================================================================
def test_unregistered_employer_reaches_the_saved_report_with_link_and_reason(harness):
    """SYNTHETIC fit control. The acceptance condition of the whole packet.

    The employer is absent from `config/companies.yaml` and is not a software vendor, and nothing
    admits it, expands the roster or edits the registry. The row must arrive with a usable apply link
    and a stated reason, alongside the monitored population.
    """
    run_id = "2026-09-25"
    _round(harness, run_id, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    report = harness.saved_report(run_id)

    rows = {row["job_id"]: row for row in report["complete_candidate_list"]}
    discovery_rows = [r for r in rows.values() if r["source_kind"] == "DISCOVERY_FEED"]
    assert discovery_rows, sorted(rows)

    row = discovery_rows[0]
    assert row["employer"] == "Granite State Mutual Insurance"
    # Not admitted, not monitored, not in the registry the manifest enumerated.
    assert row["source_id"] not in report["expected_sources"]
    assert "granite-state-mutual" not in json.dumps(report["expected_sources"])
    # Usable: a link the operator can act on and a reason they can judge.
    assert row["apply_url"], row
    assert row["why_fit"], row
    assert row["fit_band"] in ("HIGH", "MEDIUM")
    assert row["screen_outcome"] == ScreenOutcome.ELIGIBLE.value

    # It is in the human document, not only the JSON.
    markdown = harness.saved_markdown(run_id)
    assert "Granite State Mutual Insurance" in markdown

    # The monitored path still produced its own candidate in the same report.
    assert any(r["source_kind"] == "ATS_BOARD" for r in rows.values()), sorted(rows)
    harness.record_stage_trace("case1_unregistered_employer", run_id)


def test_the_same_inputs_produce_no_discovery_candidate_without_the_integration(harness):
    """The regression's other half: P06's consumer, on identical external inputs, yields nothing.

    This does not re-create P06's code. It disables the ONE thing P07 added — report assembly's
    reading of the discovery live view — and shows the candidate disappears while the monitored
    population is untouched. Without this, a passing test above could not distinguish "the
    integration works" from "the fixture happened to reach a path that already existed".
    """
    run_id = "2026-09-25"
    harness.enumerate_round(run_id)
    harness.collect_monitored(run_id)
    harness.discover(run_id, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    harness.diff_monitored(run_id)

    # The producer still wrote everything P06's producer wrote.
    assert any("provider=himalayas" in key for key in harness.keys("normalized/"))

    with patch("src.common.s3layout.discovery_live_key", return_value="discovery/live/absent.json"):
        harness.report(run_id)
    report = harness.saved_report(run_id)
    rows = report["complete_candidate_list"]
    assert [r for r in rows if r["source_kind"] == "DISCOVERY_FEED"] == []
    assert [r for r in rows if r["source_kind"] == "ATS_BOARD"], "monitored path must be unaffected"


# ==================================================================================================
# Case 2 — every enabled keyless provider's own payload path feeds the common candidate path
# ==================================================================================================
@pytest.mark.parametrize("provider,capture", [
    ("remotive", "remotive.json"),
    ("remoteok", "remoteok.json"),
    ("jobicy", "jobicy.json"),
    ("himalayas", "himalayas_page1.json"),
])
def test_each_keyless_provider_capture_replays_onto_the_common_candidate_path(
    harness, provider, capture
):
    """REAL CAPTURE replay, 2026-09-24. Provider handling only — not a claim about open roles.

    Nothing here asserts that any employer below is hiring today: these are stored bytes from one
    morning. What is asserted is that each provider's own parse/normalize path still carries records
    into the live view and out through the same screening and ranking the monitored path uses.
    """
    path = CAPTURES / capture
    if not path.is_file():  # pragma: no cover - capture set is committed with the P04 run
        pytest.skip(f"captured payload {capture} is not present")
    raw = path.read_bytes()

    run_id = "2026-09-25"
    harness.enumerate_round(run_id)
    harness.collect_monitored(run_id)
    result = harness.discover(
        run_id, fetcher=lambda p, token, url: _fetch_result(raw, url), providers=provider,
    )
    harness.diff_monitored(run_id)
    harness.report(run_id)

    assert result["jobs_discovered"] > 0, result
    # The live view is the durable representation, written by the real producer.
    live_ids = harness.live_view_ids(provider)
    assert live_ids, result
    assert all(job_id.startswith(f"{provider}:all#") for job_id in live_ids), live_ids[:5]

    report = harness.saved_report(run_id)
    considered = {row["job_id"] for row in report["scorecards"]}
    # Every stored posting reached scoring; none was dropped between the view and the pipeline.
    assert set(live_ids) <= considered, sorted(set(live_ids) - considered)[:5]
    # And every one of them was screened, which is what makes the candidate list policy-governed.
    assert report["policy_excluded_count"] + report["matching_job_count"] \
        + report["below_fit_threshold_count"] >= len(live_ids)


# ==================================================================================================
# Case 3 — policy exclusion, honest unresolved rows, history, and nothing hidden by the cap
# ==================================================================================================
def test_ineligible_job_is_excluded_for_the_stated_policy_reason(harness):
    """SYNTHETIC control. Excluded by a named rule, and visible as excluded — not deleted."""
    run_id = "2026-09-25"
    _round(harness, run_id, fetcher=_single_page_fetcher([UNREGISTERED_FIT, EXCLUDED_BY_POLICY]))
    report = harness.saved_report(run_id)

    excluded = {row["job_id"]: row for row in report["policy_exclusions"]}
    ae_rows = [r for r in excluded.values() if r["employer"] == "Northgate Revenue Group"]
    assert ae_rows, sorted(excluded)
    detail = ae_rows[0]["screen_detail"]
    assert ae_rows[0]["screen_outcome"] == ScreenOutcome.EXCLUDED.value
    rule_ids = {hit["rule_id"] for hit in detail["exclusions"]}
    assert "sales-ownership" in rule_ids, detail
    # Excluded for the policy reason, never for its fit score, and never silently: the rule that
    # fired carries its own stated reason and the matched text that triggered it.
    fired = [hit for hit in detail["exclusions"] if hit["rule_id"] == "sales-ownership"][0]
    assert fired["reason"], fired
    assert fired["matched_text"], fired

    # The fitting posting is unaffected by its neighbour's exclusion.
    kept = {row["job_id"] for row in report["complete_candidate_list"]}
    assert any("granite-state-mutual" in job_id or "internal-tools" in job_id for job_id in kept), \
        sorted(kept)
    harness.record_stage_trace("case3_policy_exclusion", run_id)


def test_history_distinguishes_submitted_from_prepared_and_unknown(harness):
    """PRE-EXISTING FIXTURE: the committed `config/application_history.json`, identified as such.

    Two of its rows carry different statuses that must never collapse into each other: Apiphani is
    SUBMITTED on stated evidence, Acquisition.com is PREPARED with materials but no submission. A
    posting with no history entry stays NEW, which is an absence of evidence, not a third status.
    """
    from src.candidate.history import load_history

    history = load_history()
    assert history is not None, "the committed history projection is the fixture under test"

    submitted = history.lookup(
        employer_name="Apiphani",
        title="Senior Software Engineer, AI and LLMs",
        url="https://job-boards.greenhouse.io/apiphani/jobs/4893893007",
    )
    prepared = history.lookup(
        employer_name="Acquisition.com",
        title="Senior AI Engineer",
        url="https://jobs.ashbyhq.com/acquisition/9789dd49-c6bd-4672-8cd3-9f67f2dea7c1/application",
    )
    assert submitted is not None and prepared is not None
    assert submitted.status.value == "SUBMITTED"
    assert prepared.status.value == "PREPARED"
    assert submitted.status != prepared.status

    unknown = history.lookup(
        employer_name="Granite State Mutual Insurance",
        title="Senior Software Engineer, Internal Tools and Automation",
        url=UNREGISTERED_FIT["applicationLink"],
    )
    assert unknown is None, "no entry must mean NEW, never an inferred status"


# The packet's known-duplicate control, at the posting's REAL remoteOK identity. Submitted through
# Ashby on 2026-09-26 and confirmed by the employer's own page; the feed carries this URL and the
# application used the other one, so before the alias list the two never met.
SUBMITTED_VIA_A_DIFFERENT_URL = {
    "title": "Senior Software Engineer Case Execution",
    "companyName": "Pivotal Health",
    "companySlug": "pivotal-health",
    "employmentType": "Full Time",
    "locationRestrictions": "['United States']",
    "applicationLink": (
        "https://remoteOK.com/remote-jobs/"
        "remote-senior-software-engineer-case-execution-pivotal-health-1136795"
    ),
    "guid": (
        "https://remoteOK.com/remote-jobs/"
        "remote-senior-software-engineer-case-execution-pivotal-health-1136795"
    ),
    "excerpt": (
        "Own claim orchestration and case execution workflows end to end. Responsibilities: build "
        "and maintain Python backend services on AWS, design decision logic over healthcare "
        "reimbursement data, and own the reliability of the pipeline. Remote throughout the United "
        "States. Interview process: live video conversations with the engineering team."
    ),
}
SUBMITTED_VIA_A_DIFFERENT_URL["description"] = SUBMITTED_VIA_A_DIFFERENT_URL["excerpt"]

# A DIFFERENT requisition at the same employer. The control's other half, and the more expensive
# failure of the two: suppressing a live opening because the company already has one submission.
DISTINCT_REQUISITION_SAME_EMPLOYER = dict(
    SUBMITTED_VIA_A_DIFFERENT_URL,
    title="Staff Platform Engineer",
    applicationLink="https://remoteOK.com/remote-jobs/remote-staff-platform-engineer-pivotal-health-9900001",
    guid="https://remoteOK.com/remote-jobs/remote-staff-platform-engineer-pivotal-health-9900001",
)


def test_an_application_submitted_under_another_url_is_not_announced_as_new(harness):
    """The whole point of the history repair, through the real assembly path.

    This posting was submitted on 2026-09-26 and confirmed by the employer. It reaches the report
    through the aggregator URL, and the application was made on the employer's Ashby URL. Before the
    projection carried aliases the report labelled it NEW and re-announced work already done.
    """
    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([SUBMITTED_VIA_A_DIFFERENT_URL]))
    report = harness.saved_report(run_id)

    rows = [r for r in report["complete_candidate_list"] if r["employer"] == "Pivotal Health"]
    assert rows, json.dumps([r["employer"] for r in report["complete_candidate_list"]])
    assert rows[0]["history_status"] == "SUBMITTED", rows[0]
    # And it is not sitting in the fresh-candidate counts.
    assert report["new_strong_count"] == 0, report["new_strong_count"]
    assert report["previously_engaged_count"] >= 1


def test_a_submission_only_the_alias_list_can_reach_is_not_announced_as_new(harness):
    """The alias made load-bearing, through real assembly.

    The aggregator says "Airspace Link" / "Backend Software Engineer". The application was made at
    "Airspace Link, Inc." / "Backend Software Engineer (Golang)" on Paylocity, on 2026-09-27.
    Employer AND title differ, so the employer+title fallback cannot connect them and only the
    recorded alias can. Neutralising the alias list turns this row NEW.
    """
    posting = dict(
        UNREGISTERED_FIT,
        title="Backend Software Engineer",
        companyName="Airspace Link",
        companySlug="airspace-link",
        applicationLink=(
            "https://remoteOK.com/remote-jobs/"
            "remote-backend-software-engineer-airspace-link-1137409"
        ),
        guid=(
            "https://remoteOK.com/remote-jobs/"
            "remote-backend-software-engineer-airspace-link-1137409"
        ),
        excerpt=(
            "Build and own Go backend services and their AWS infrastructure for our airspace data "
            "platform. Responsibilities: design APIs, own data pipelines, and support the services "
            "you ship. Remote anywhere in the United States. Interview process: live video "
            "conversations with the engineering team."
        ),
    )
    posting["description"] = posting["excerpt"]

    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([posting]))
    report = harness.saved_report(run_id)

    rows = [r for r in report["complete_candidate_list"] if r["employer"] == "Airspace Link"]
    assert rows, json.dumps([r["employer"] for r in report["complete_candidate_list"]])
    assert rows[0]["history_status"] == "SUBMITTED", rows[0]


def test_a_distinct_requisition_at_that_same_employer_still_reaches_the_report(harness):
    """Deduplicating harder than the evidence supports is how a real opening disappears."""
    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([DISTINCT_REQUISITION_SAME_EMPLOYER]))
    report = harness.saved_report(run_id)

    rows = [r for r in report["complete_candidate_list"] if r["employer"] == "Pivotal Health"]
    assert rows, json.dumps([r["employer"] for r in report["complete_candidate_list"]])
    assert rows[0]["title"] == "Staff Platform Engineer"
    assert rows[0]["history_status"] == "NEW", rows[0]


def test_the_report_says_how_far_the_history_evidence_reached(harness):
    """A present-but-stale projection used to be indistinguishable from a current one on the page."""
    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    report = harness.saved_report(run_id)

    state = report["coverage"]["history_projection"]
    assert state["state"] in ("current", "stale", "known_empty", "missing")
    assert state["cutoff"], "the projection must declare how far its evidence reached"

    markdown = harness.saved_markdown(run_id)
    assert "Application history" in markdown
    assert state["cutoff"] in markdown


def test_broad_ownership_retention_still_reaches_the_report_after_the_history_change(harness):
    """The release's other half. A low-fit, no-AI posting that establishes sole ownership of
    software must still arrive — the history work must not have cost it."""
    sole_owner = dict(
        UNREGISTERED_FIT,
        title="Internal Applications Developer",
        companyName="Northfield Supply Company",
        companySlug="northfield-supply",
        applicationLink="https://himalayas.app/companies/northfield-supply/jobs/internal-applications",
        guid="https://himalayas.app/companies/northfield-supply/jobs/internal-applications",
        excerpt=(
            "We distribute industrial fasteners. You would be our only software engineer, owning "
            "our internal systems end to end. Nobody here writes software today. You will decide "
            "what to build, build it, and support it. Remote throughout the United States."
        ),
    )
    sole_owner["description"] = sole_owner["excerpt"]

    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([sole_owner]))
    report = harness.saved_report(run_id)

    rows = [r for r in report["complete_candidate_list"]
            if r["employer"] == "Northfield Supply Company"]
    assert rows, json.dumps([r["employer"] for r in report["complete_candidate_list"]])
    assert report["ownership_retained_count"] >= 1
    assert rows[0]["history_status"] == "NEW"


def test_every_credible_result_survives_beyond_the_highlight_cap(harness):
    """The complete list is uncapped; `top_matches` is a highlight, not the candidate set."""
    from src.report.handler import _MAX_HIGHLIGHTS

    records = []
    for index in range(_MAX_HIGHLIGHTS + 6):
        row = dict(UNREGISTERED_FIT)
        row["companyName"] = f"Granite Employer {index:02d}"
        row["companySlug"] = f"granite-employer-{index:02d}"
        # Himalayas derives its stable key from the LAST path segment, so the distinguishing part
        # has to be there — otherwise 26 postings would legitimately collapse to one id.
        row["guid"] = f"https://himalayas.app/companies/g{index:02d}/jobs/internal-tools-{index:02d}"
        row["applicationLink"] = row["guid"]
        records.append(row)

    run_id = "2026-09-25"
    _round(harness, run_id, fetcher=_single_page_fetcher(records))
    report = harness.saved_report(run_id)

    assert len(report["top_matches"]) <= _MAX_HIGHLIGHTS
    assert len(report["complete_candidate_list"]) > _MAX_HIGHLIGHTS, report["matching_job_count"]
    # Nothing credible is reachable only through the cap.
    highlighted = {row["job_id"] for row in report["top_matches"]}
    complete = {row["job_id"] for row in report["complete_candidate_list"]}
    assert highlighted <= complete
    # The overflow beyond the highlight cap is readable in the document, not only in the JSON.
    markdown = harness.saved_markdown(run_id)
    beyond_cap = [row for row in report["complete_candidate_list"][_MAX_HIGHLIGHTS:]]
    assert beyond_cap
    assert any(row["employer"] in markdown for row in beyond_cap), beyond_cap[0]["employer"]


# ==================================================================================================
# Case 4 — identity: duplicates, distinct requisitions, and a posting that moves page
# ==================================================================================================
def test_the_same_posting_on_a_new_page_and_a_new_day_keeps_one_identity(harness):
    """The cursor is a fetch coordinate. Moving pages must not mint a second posting.

    Round one delivers the posting on page one. Round two delivers it behind a different cursor, on
    a later date. Identity, first observation and observation history must all survive that.
    """
    run_id_one, run_id_two = "2026-09-25", "2026-09-26"

    def day_one(provider, token, url):
        return _fetch_result(_feed_payload([UNREGISTERED_FIT], cursor=None), url)

    def day_two(provider, token, url):
        # Page one now holds a newer posting; the original has slid behind a cursor.
        newer = dict(UNREGISTERED_FIT)
        newer["companyName"] = "Seacoast Analytics"
        newer["companySlug"] = "seacoast-analytics"
        newer["guid"] = "https://himalayas.app/companies/seacoast/jobs/platform"
        newer["applicationLink"] = newer["guid"]
        if token in ("all", "", None):
            return _fetch_result(_feed_payload([newer], cursor="PAGE_TWO"), url)
        return _fetch_result(_feed_payload([UNREGISTERED_FIT], cursor=None), url)

    _round(harness, run_id_one, fetcher=day_one)
    first_ids = harness.live_view_ids("himalayas")
    assert len(first_ids) == 1, first_ids

    _round(harness, run_id_two, fetcher=day_two)
    second_ids = harness.live_view_ids("himalayas")

    # The original posting is still exactly one record, under the same id, despite the new cursor.
    assert set(first_ids) <= set(second_ids), (first_ids, second_ids)
    assert len(second_ids) == 2, second_ids

    raw = json.loads(harness.s3.get_object(
        Bucket=BUCKET, Key=s3layout.discovery_live_key("himalayas")
    )["Body"].read())
    carried = raw["jobs"][first_ids[0]]
    assert carried["observation_count"] == 2, carried
    assert carried["first_seen_run_id"] == run_id_one
    assert carried["last_seen_run_id"] == run_id_two
    # First observation is preserved and is NOT the publication date.
    assert carried["job"]["first_seen_at"] != carried["job"]["last_seen_at"]

    report = harness.saved_report(run_id_two)
    ids = [row["job_id"] for row in report["complete_candidate_list"]]
    assert len(ids) == len(set(ids)), ids
    harness.record_stage_trace("case4_identity_across_pages", run_id_two)


def test_a_duplicate_across_two_feeds_appears_once_with_provenance(harness):
    """The same apply target seen on two different feeds is one row; two requisitions stay two.

    This is the shape the operator actually meets: an aggregator and a second aggregator both carry
    one employer posting. Each feed mints its own native id, so only the canonical apply target can
    tell that they are the same requisition — and the absorbed sighting must survive the merge.
    """
    distinct = dict(UNREGISTERED_FIT)
    distinct["title"] = "Senior Software Engineer, Claims Platform"
    distinct["guid"] = "https://himalayas.app/companies/granite-state-mutual/jobs/claims-platform"
    distinct["applicationLink"] = distinct["guid"]

    remotive_twin = {
        "id": 55501,
        "company_name": "Granite State Mutual Insurance",
        "title": UNREGISTERED_FIT["title"],
        # The SAME canonical apply target as the Himalayas record above.
        "url": UNREGISTERED_FIT["applicationLink"],
        "description": UNREGISTERED_FIT["description"],
        "candidate_required_location": "USA",
        "job_type": "full_time",
        "category": "Software Development",
        "publication_date": "2026-09-25T10:00:00",
    }

    def two_feeds(provider, token, url):
        if provider == "remotive":
            return _fetch_result({"jobs": [remotive_twin]}, url)
        return _fetch_result(_feed_payload([UNREGISTERED_FIT, distinct]), url)

    run_id = "2026-09-25"
    harness.enumerate_round(run_id)
    harness.collect_monitored(run_id)
    harness.discover(run_id, fetcher=two_feeds, providers="himalayas,remotive")
    harness.diff_monitored(run_id)
    harness.report(run_id)

    report = harness.saved_report(run_id)
    rows = {row["job_id"]: row for row in report["complete_candidate_list"]}
    discovery_rows = [r for r in rows.values() if r["source_kind"] == "DISCOVERY_FEED"]

    # Both feeds stored their own record, so the merge below is a genuine cross-source merge.
    assert harness.live_view_ids("himalayas") and harness.live_view_ids("remotive")

    titles = [row["title"] for row in discovery_rows]
    assert titles.count("Senior Software Engineer, Internal Tools and Automation") == 1, titles
    # The separate requisition at the same employer is NOT collapsed into it.
    assert "Senior Software Engineer, Claims Platform" in titles, titles

    merged = [
        row for row in discovery_rows
        if row["title"] == "Senior Software Engineer, Internal Tools and Automation"
    ][0]
    # "We also saw this on the other feed" survives the merge.
    assert merged["provenance"], merged
    sighted = {entry["source_id"] for entry in merged["provenance"]}
    assert len(sighted) >= 2, merged["provenance"]
    assert (report.get("dedup") or {}).get("hard_merges", 0) >= 1, report.get("dedup")
    harness.record_stage_trace("case4_dedup", run_id)


# ==================================================================================================
# Case 5 — failed, partial and late discovery across persisted rounds
# ==================================================================================================
def test_a_failed_discovery_round_loses_nothing_and_claims_no_coverage(harness):
    """A feed that could not be read must not age, drop or re-verify a single posting.

    Round one observes the posting. Round two's fetch fails outright. The posting must still reach
    the report, the report must say the feed was not observed this run, and it must not present the
    carried postings as this round's coverage.
    """
    run_id_one, run_id_two = "2026-09-25", "2026-09-26"
    _round(harness, run_id_one, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    before = harness.live_view_ids("himalayas")

    def failing(provider, token, url):
        raise TimeoutError("feed unreachable")

    _round(harness, run_id_two, fetcher=failing)
    after = harness.live_view_ids("himalayas")
    assert after == before, (before, after)

    raw = json.loads(harness.s3.get_object(
        Bucket=BUCKET, Key=s3layout.discovery_live_key("himalayas")
    )["Body"].read())
    carried = raw["jobs"][before[0]]
    # A run that could not look has no standing to age or re-verify anything.
    assert carried["last_seen_run_id"] == run_id_one
    assert carried["observation_count"] == 1
    assert raw["last_observed_run_id"] == run_id_one
    assert not any(
        note.startswith("last observed in this feed on")
        for note in carried["job"]["uncertainty"]
    ), carried["job"]["uncertainty"]

    report = harness.saved_report(run_id_two)
    # The posting is still shown — a failed round must not silently drop a candidate.
    assert any(
        row["source_kind"] == "DISCOVERY_FEED" for row in report["complete_candidate_list"]
    ), report["complete_candidate_list"]
    # And the report says the feed added nothing this round, rather than implying it succeeded.
    inaccessible = json.dumps(report["coverage"]["inaccessible"])
    assert "himalayas:all" in inaccessible, inaccessible
    assert "carried from an earlier round" in inaccessible, inaccessible
    assert "himalayas" not in report["coverage"]["discovery_succeeded"], report["coverage"]
    harness.record_stage_trace("case5_failed_round", run_id_two)


def test_absence_from_a_later_feed_window_is_not_treated_as_closure(harness):
    """Feed churn is not a closure signal, and the row says so in those words."""
    run_id_one, run_id_two = "2026-09-25", "2026-09-26"
    _round(harness, run_id_one, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))

    other = dict(UNREGISTERED_FIT)
    other["companyName"] = "Seacoast Analytics"
    other["companySlug"] = "seacoast-analytics"
    other["guid"] = "https://himalayas.app/companies/seacoast/jobs/platform"
    other["applicationLink"] = other["guid"]
    _round(harness, run_id_two, fetcher=_single_page_fetcher([other]))

    raw = json.loads(harness.s3.get_object(
        Bucket=BUCKET, Key=s3layout.discovery_live_key("himalayas")
    )["Body"].read())
    original = [job_id for job_id in raw["jobs"] if "internal-tools" in job_id][0]
    record = raw["jobs"][original]
    # Retained, not removed, not marked disappeared.
    assert record["last_seen_run_id"] == run_id_one
    marker = [
        note for note in record["job"]["uncertainty"]
        if note.startswith("last observed in this feed on")
    ]
    assert marker, record["job"]["uncertainty"]
    assert "not a signal that the opening ended" in marker[0]

    report = harness.saved_report(run_id_two)
    shown = {row["job_id"] for row in report["complete_candidate_list"]}
    assert original in shown, sorted(shown)


def test_a_late_arriving_discovery_round_reaches_the_following_report(harness):
    """Report-before-discovery loses nothing: the next round picks the posting up."""
    run_id_one, run_id_two = "2026-09-25", "2026-09-26"

    # Round one: report runs with no discovery at all.
    harness.enumerate_round(run_id_one)
    harness.collect_monitored(run_id_one)
    harness.diff_monitored(run_id_one)
    harness.report(run_id_one)
    first = harness.saved_report(run_id_one)
    assert [r for r in first["complete_candidate_list"] if r["source_kind"] == "DISCOVERY_FEED"] == []
    # The absence is stated, not passed off as an empty market.
    assert "no stored postings exist for it yet" in json.dumps(first["coverage"]["inaccessible"])

    # Round two: discovery lands and the posting appears.
    _round(harness, run_id_two, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    second = harness.saved_report(run_id_two)
    assert [r for r in second["complete_candidate_list"] if r["source_kind"] == "DISCOVERY_FEED"]
    harness.record_stage_trace("case5_late_discovery", run_id_two)


def test_the_request_budget_and_owed_ranges_still_hold_under_the_live_view(harness):
    """P05's behavior is preserved: a failed page stays owed and the budget is not overspent."""
    from src.discovery.budget import DiscoveryState

    calls: list[str] = []

    def paging(provider, token, url):
        calls.append(token)
        if token == "PAGE_TWO":
            raise TimeoutError("page unreachable")
        if token in ("all", "", None):
            return _fetch_result(_feed_payload([UNREGISTERED_FIT], cursor="PAGE_TWO"), url)
        return _fetch_result(_feed_payload([UNREGISTERED_FIT], cursor=None), url)

    run_id = "2026-09-25"
    _round(harness, run_id, fetcher=paging)

    # The configured Himalayas budget is 2 pages per run; a raised request is still charged.
    assert len(calls) <= 2, calls
    raw_state = json.loads(harness.s3.get_object(
        Bucket=BUCKET, Key=s3layout.discovery_state_key()
    )["Body"].read())
    state = DiscoveryState.model_validate(raw_state)
    owed = state.pending_head("himalayas") or [state.source_cursors.get("himalayas")]
    assert "PAGE_TWO" in [c for c in owed if c], (owed, state.source_cursors)


# ==================================================================================================
# Case 6 — the old-report fallback, the next round, and same-date digest suppression
# ==================================================================================================
def test_the_pre_discovery_report_shape_still_supplies_a_previous_round_boundary(harness):
    """PRE-EXISTING SHAPE: empty `complete_candidate_list`, populated `top_matches`, no timing.

    That is the shape of the report already delivered on 2026-09-25. Read only through
    `complete_candidate_list` it looked like a round that showed nothing, so the boundary was thrown
    away and cold start was declared. The recovered identities are what that report EVIDENCES — the
    rows it listed — and the recovery records that the list was capped rather than exhaustive.
    """
    from src.report.handler import resolve_run_timing

    old = {
        "run_id": "2026-09-25",
        "dt": "2026-09-25",
        "run_health": "VERIFIED-QUIET",
        "expected_sources": ["greenhouse:machinifyinc"],
        "complete_candidate_list": [],
        "top_matches": [
            {"job_id": f"greenhouse:machinifyinc#{n}", "employer": "Machinify"} for n in range(20)
        ],
    }
    harness.s3.put_object(
        Bucket=BUCKET, Key=s3layout.report_json_key("2026-09-25"),
        Body=json.dumps(old).encode(),
    )
    harness.enumerate_round("2026-09-26")
    timing = resolve_run_timing(harness.s3, BUCKET, "2026-09-26", "2026-09-26")

    assert timing.cold_start_run is False, "an old-format report is still a previous round"
    assert timing.previous_run_id == "2026-09-25"
    assert len(timing.previously_reported_ids) == 20
    assert timing.previously_reported_source == "top_matches"
    # The cap is recorded, so nothing downstream may read the set as a complete census.
    assert timing.previously_reported_truncated is True
    # The old shape carried no finish stamp; identity still answers the question without one.
    assert timing.previous_run_at is None


def test_cold_start_is_still_distinguished_from_a_recovered_boundary(harness):
    """A genuine first round must not be dressed up as having a previous boundary."""
    from src.report.handler import resolve_run_timing

    harness.enumerate_round("2026-09-25")
    timing = resolve_run_timing(harness.s3, BUCKET, "2026-09-25", "2026-09-25")
    assert timing.cold_start_run is True
    assert timing.previously_reported_ids == frozenset()
    assert timing.previously_reported_source is None
    assert timing.previously_reported_truncated is False


def test_the_round_after_the_old_format_report_writes_the_new_format(harness):
    """Old format in, new format out, with the boundary honored across the transition."""
    old = {
        "run_id": "2026-09-25", "dt": "2026-09-25",
        "complete_candidate_list": [],
        "top_matches": [{"job_id": "greenhouse:machinifyinc#900001", "employer": "Machinify"}],
    }
    harness.s3.put_object(
        Bucket=BUCKET, Key=s3layout.report_json_key("2026-09-25"),
        Body=json.dumps(old).encode(),
    )
    run_id = "2026-09-26"
    _round(harness, run_id, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
    report = harness.saved_report(run_id)

    assert report["timing"]["previously_reported_source"] == "top_matches"
    assert report["timing"]["previously_reported_truncated"] is True
    assert report["timing"]["cold_start_run"] is False
    assert report["complete_candidate_list"], "the new format carries the complete list"
    # The monitored posting the old report already showed is not re-announced as a fresh arrival.
    monitored = [
        row for row in report["complete_candidate_list"]
        if row["job_id"] == "greenhouse:machinifyinc#900001"
    ]
    if monitored:
        assert monitored[0]["is_fresh_arrival"] is False, monitored[0]
    # The discovered posting, which no earlier report showed, is new.
    discovered = [
        row for row in report["complete_candidate_list"] if row["source_kind"] == "DISCOVERY_FEED"
    ]
    assert discovered and discovered[0]["is_fresh_arrival"] is True, discovered
    harness.record_stage_trace("case6_old_format_transition", run_id)


def test_same_date_digest_is_sent_once_and_never_actually_delivered(harness):
    """SES is mocked; a second run on the same date must not send again. No mail leaves the test."""
    run_id = "2026-09-25"
    sent: list[dict] = []

    def fake_send(ses, *, sender, recipient, subject, body):
        sent.append({"recipient": recipient, "subject": subject})
        return "message-id-0001"

    env = {"SES_SENDER": "sender@example.invalid", "DIGEST_RECIPIENT": "brett@example.invalid"}
    with patch("src.report.handler.send_digest", side_effect=fake_send):
        harness.enumerate_round(run_id)
        harness.collect_monitored(run_id)
        harness.discover(run_id, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
        harness.diff_monitored(run_id)
        first = harness.report(run_id, env_extra=env)
        second = harness.report(run_id, env_extra=env)

    assert first["digest_delivery"] == "sent"
    assert second["digest_delivery"] == "already-sent"
    assert len(sent) == 1, sent
    assert sent[0]["recipient"] == "brett@example.invalid"


# ==================================================================================================
# The stage trace, reviewed for test-authored links
# ==================================================================================================
def test_the_stage_trace_reconciles_and_contains_no_test_authored_intermediate(harness, tmp_path):
    """One end-to-end round, censused stage by stage, with the population difference reconciled.

    This is the check the packet asks for by name: look at the final trace specifically for a link a
    test wrote rather than a producer. The assertion is structural — every id in the report must be
    traceable back to bytes this test supplied through a provider fetch, and the only S3 writers must
    be the five production stages.
    """
    run_id = "2026-09-25"
    _round(harness, run_id, fetcher=_single_page_fetcher([UNREGISTERED_FIT, EXCLUDED_BY_POLICY]))
    entry = harness.record_stage_trace("acceptance_round", run_id)

    report = harness.saved_report(run_id)
    # Population reconciliation: every posting considered is accounted for in exactly one bucket.
    counts = entry["counts"]
    assert counts["postings_considered"] == (
        counts["retained_credible"] + counts["excluded_by_policy"]
        + counts["below_fit_threshold"]
    ), counts

    # Both populations are present, so this is not a discovery-only demonstration.
    assert entry["discovery_candidate_ids"], entry
    assert entry["monitored_candidate_ids"], entry

    # Every candidate id traces to a normalized record a real producer wrote.
    normalized = set(entry["fetched_normalized_job_ids"])
    for job_id in entry["report_candidate_ids"]:
        assert job_id in normalized, (job_id, sorted(normalized))

    # The discovery rows trace to the live view the discovery stage wrote, not to anything here.
    live = set(entry["discovery_live_view_ids"]["himalayas"])
    assert set(entry["discovery_candidate_ids"]) <= live, (entry["discovery_candidate_ids"], live)

    # No object exists under a prefix this test wrote directly: the only writers are the stages.
    prefixes = {key.split("/", 1)[0] for key in harness.keys("")}
    assert prefixes <= {"runs", "raw", "normalized", "status", "current", "events", "discovery",
                        "reports"}, prefixes

    trace_path = tmp_path / "p07_stage_trace.json"
    trace_path.write_text(json.dumps(harness.trace, indent=2, default=str))
    assert json.loads(trace_path.read_text())
    assert report["run_id"] == run_id


# ==================================================================================================
# Declared deployment surface: permissions and invocation order, checked against the real files
#
# Mocked S3 grants everything, so the harness above cannot establish IAM. These read the actual
# local template and state machine instead, so the deployment claims in the handoff are machine-
# checked rather than asserted in prose.
# ==================================================================================================
def _template() -> dict:
    """Load the SAM template with its intrinsic functions reduced to inspectable text."""
    import yaml

    class _Loader(yaml.SafeLoader):
        pass

    def _passthrough(loader, node):
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        return loader.construct_mapping(node, deep=True)

    for tag in ("!Sub", "!Ref", "!GetAtt", "!Equals", "!If", "!Join", "!Select", "!Split"):
        _Loader.add_constructor(tag, _passthrough)
    return yaml.load((ROOT / "infra/template.yaml").read_text(), Loader=_Loader)


def _statements(template: dict, function: str) -> list[dict]:
    out = []
    for policy in template["Resources"][function]["Properties"].get("Policies", []):
        if isinstance(policy, dict):
            out.extend(policy.get("Statement", []))
    return out


def _granted(statements: list[dict], action: str) -> set[str]:
    resources: set[str] = set()
    for statement in statements:
        actions = statement.get("Action")
        actions = actions if isinstance(actions, list) else [actions]
        if action not in actions:
            continue
        declared = statement.get("Resource")
        declared = declared if isinstance(declared, list) else [declared]
        resources.update(str(item) for item in declared)
    return resources


def _covers(resources: set[str], key: str) -> bool:
    """True when some granted `.../prefix/*` resource covers this object key."""
    for resource in resources:
        _, _, tail = resource.partition("}/")
        if tail.endswith("*") and key.startswith(tail[:-1]):
            return True
    return False


def test_the_live_view_key_is_covered_by_the_declared_iam_on_both_sides():
    """Discovery must be able to write and re-read it; report must be able to read it.

    The live view deliberately lives under `discovery/`, which discovery already owns and report is
    already granted, so this integration needs no IAM change. That is a claim about the template, so
    it is checked against the template.
    """
    template = _template()
    key = s3layout.discovery_live_key("himalayas")
    assert key.startswith("discovery/")

    discovery = _statements(template, "DiscoveryFunction")
    report = _statements(template, "ReportFunction")

    # Producer: writes it, and reads the prior round's copy back before merging.
    assert _covers(_granted(discovery, "s3:PutObject"), key), key
    assert _covers(_granted(discovery, "s3:GetObject"), key), key
    # Consumer: reads it, and must NOT be able to write it — one writer, by construction.
    assert _covers(_granted(report, "s3:GetObject"), key), key
    assert not _covers(_granted(report, "s3:PutObject"), key), (
        "report must remain unable to write the discovery-owned view"
    )
    # The differ's ownership of current/ is untouched by this change.
    assert not _covers(_granted(discovery, "s3:PutObject"), "current/provider=x/board=y/f.json")


def test_discovery_is_scheduled_before_the_assemble_run_that_reads_it():
    """The producer must run before the consumer on the paths the deployment actually declares."""
    template = _template()
    params = template["Parameters"]
    # Both schedules are cron-in-timezone; discovery must precede assemble on the same day.
    discovery_cron = params["DiscoveryCron"]["Default"]
    assemble_cron = params["AssembleCron"]["Default"]

    def hour_minute(expression: str) -> tuple[int, int]:
        inner = expression[expression.index("(") + 1:expression.rindex(")")].split()
        return int(inner[1]), int(inner[0])

    assert hour_minute(discovery_cron) < hour_minute(assemble_cron), (
        discovery_cron, assemble_cron
    )
    assert params["TimeZone"]["Default"] == "America/New_York"
    # The discovery schedule targets the discovery function directly; report is reached through the
    # assemble state machine. Neither routing is changed by this repair.
    assert template["Resources"]["DiscoverySchedule"]["Properties"]["Target"]["Arn"] \
        == "DiscoveryFunction.Arn"
    assert template["Resources"]["AssembleSchedule"]["Properties"]["Target"]["Arn"] \
        == "DailyAssembleStateMachine"


def test_the_assemble_state_machine_still_reaches_report_without_a_new_stage():
    """The repair adds no state, no task and no new invocation edge."""
    definition = json.loads(
        (ROOT / "infra/statemachine/jprs-daily-assemble.asl.json").read_text()
    )
    states = definition["States"]
    assert set(states) == {"LoadCompanies", "DiffAllCompanies", "BuildReport", "ReportIncomplete"}
    assert states["DiffAllCompanies"]["Next"] == "BuildReport"
    # Report is still the only consumer invoked here, and discovery is NOT in this machine: it runs
    # on its own earlier schedule, which is why no state-machine change was required.
    assert "Discovery" not in json.dumps(definition)
