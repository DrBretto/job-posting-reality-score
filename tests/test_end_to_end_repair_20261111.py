"""Acceptance for PKT-CAREER-RADAR-END-TO-END-REPAIR-V1 (2026-11-11), through the real producers.

Every case runs enumerate -> discovery -> report against one mocked S3 world, with only the HTTP
layer replaced. The fixed employer registry is EMPTY for the discovery cases: nothing here may depend
on a hand-maintained employer list to reach review.

Synthetic postings establish regression coverage. The dated live run that establishes source
behaviour is in the run directory (LIVE_SEARCH_SAMPLE.md), not here.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.common import s3layout
from tests.test_discovery_to_report_integration import BUCKET, Harness, _fetch_result

ROOT = Path(__file__).resolve().parents[1]
STORY_ID = 50338728

DUTIES = (
    "We are a funded freight-brokerage company (seed, $4M raised) and you will be our first "
    "in-house software hire, working directly with the founder. Responsibilities: build and own our "
    "internal operations platform in Python on AWS, migrate the inherited system our agency built, "
    "integrate our carrier APIs and accounting system, and maintain the internal tools our "
    "operations team uses every day. We use coding agents in our workflow; you review and ship. "
    "Interview process: a call with the founder, then a technical conversation."
)


def _post(item_id: int, header: str, body: str) -> dict:
    return {"id": item_id, "type": "comment", "author": f"poster{item_id}",
            "created_at": "2026-11-03T15:00:00Z", "text": f"{header}<p>{body}"}


POSTS = {
    # The acceptance role: unknown employer, no ATS (static careers page), unconventional title,
    # continuing engineering ownership, cash pay stated.
    "analyst": _post(101, "Northwind Freight Co | Business Systems Analyst | REMOTE (US) | "
                          "$140K-$165K | Full-time", DUTIES),
    # Identical duties under an Engineer title at a second unknown employer.
    "engineer": _post(102, "Southwind Freight Co | Business Systems Engineer | REMOTE (US) | "
                           "$140K-$165K | Full-time", DUTIES),
    # An analyst whose duties are not engineering.
    "plain_analyst": _post(103, "Ledgerline Accounting | Financial Analyst | REMOTE (US) | "
                                "$90K | Full-time",
                           "Responsibilities: analyze monthly results in Excel, design reports and "
                           "dashboards for leadership and present variance findings. Interview "
                           "process: two calls."),
    # A lookalike that pays no cash.
    "equity_only": _post(104, "Moonshot Freight Labs | Founding Engineer | REMOTE (US) | "
                              "Equity only | Full-time",
                         DUTIES + " Compensation: this is an equity-only role until we raise."),
    # Real engineering ownership with an actual location exclusion.
    "onsite_far": _post(105, "Harbor Point Robotics | Platform Engineer | ONSITE, Austin, TX | "
                             "$150K | Full-time",
                        DUTIES.replace("our first in-house software hire", "an engineer on site")
                        + " This role is onsite in our Austin, TX office five days a week."),
    # Known operator exclusions still hold.
    "sales": _post(106, "Quota Systems Inc | Account Executive | REMOTE (US) | OTE $200K",
                   "Responsibilities: carry an annual sales quota and close new business. "
                   "Interview process: two calls."),
    "voice": _post(107, "Sonic Lines | Voice AI Engineer | REMOTE (US) | $170K",
                   "Responsibilities: you will build voice agents and telephony integrations and "
                   "tune speech recognition. Interview process: calls."),
    "video": _post(108, "Tapeline Logistics | Software Engineer | REMOTE (US) | $150K",
                   "Responsibilities: build backend services in Python. Application process: "
                   "please record a short video introduction before any interview."),
}

THREAD = {"id": STORY_ID, "title": "Ask HN: Who is hiring? (November 2026)",
          "children": list(POSTS.values())}
SEARCH = {"hits": [{"objectID": str(STORY_ID), "title": THREAD["title"]}]}


def _hn_fetcher(provider, token, url):
    if "search_by_date" in url:
        return _fetch_result(SEARCH, url)
    return _fetch_result(THREAD, url)


@pytest.fixture
def world(tmp_path):
    from moto import mock_aws
    import boto3

    empty_registry = tmp_path / "companies.yaml"
    empty_registry.write_text("companies: []\n")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="jprs-e2e-collect")["QueueUrl"]
        h = Harness(s3, queue_url)
        h.sqs = sqs
        h.env["JPRS_COMPANIES_YAML"] = str(empty_registry)
        yield h


def _discovery_round(h: Harness, run_id: str = "2026-11-11"):
    manifest = h.enumerate_round(run_id)
    h.discover(run_id, fetcher=_hn_fetcher, providers="hn_hiring")
    return manifest


def _rows(report: dict) -> dict:
    return {row["employer"]: row for row in report["complete_candidate_list"]}


def _all_cards(report: dict) -> dict:
    by_id = {c["job_id"]: c for c in report["scorecards"]}
    return by_id


# ==================================================================================================
# Discovery and duty-first screening, registry disconnected
# ==================================================================================================
def test_registry_is_empty_and_an_unknown_no_ats_analyst_role_reaches_review(world):
    manifest = _discovery_round(world)
    assert manifest["expected"] == 0 if "expected" in manifest else True
    world.report("2026-11-11")
    report = world.saved_report("2026-11-11")
    assert report["expected_sources"] == []              # the fixed registry is disconnected
    rows = _rows(report)
    row = rows["Northwind Freight Co"]
    assert row["title"] == "Business Systems Analyst"
    assert row["source_kind"] == "DISCOVERY_FEED"
    # No supported ATS: the apply path is the post itself (no link) — never a Greenhouse/Lever board.
    assert "greenhouse" not in (row["apply_url"] or "") and "lever" not in (row["apply_url"] or "")
    assert row["posting_url"] == "https://news.ycombinator.com/item?id=101"
    assert row["compensation"] and "140" in row["compensation"]
    assert row["ownership"]["is_broad_ownership_candidate"] is True
    md = world.saved_markdown("2026-11-11")
    assert "Northwind Freight Co" in md
    assert "no employer boards are tracked this round" in md


def test_the_same_duties_score_the_same_under_analyst_and_engineer_titles(world):
    _discovery_round(world)
    world.report("2026-11-11")
    report = world.saved_report("2026-11-11")
    rows = _rows(report)
    analyst, engineer = rows["Northwind Freight Co"], rows["Southwind Freight Co"]
    assert analyst["fit_score"] == engineer["fit_score"] > 0.3
    cards = _all_cards(report)
    a = cards[analyst["job_id"]]["brett_fit"]["detail"]
    assert a["blocked_role"] == 0 and a["title_deferred_to_duties"] == 1


def test_an_analyst_without_engineering_duties_is_still_not_offered(world):
    _discovery_round(world)
    world.report("2026-11-11")
    report = world.saved_report("2026-11-11")
    assert "Ledgerline Accounting" not in _rows(report)
    card = next(c for c in report["scorecards"] if c["job_id"].endswith("#103"))
    assert card["brett_fit"]["detail"]["blocked_role"] == 1


def test_equity_only_lookalike_and_far_onsite_role_are_excluded_with_reasons(world):
    _discovery_round(world)
    world.report("2026-11-11")
    report = world.saved_report("2026-11-11")
    rows = _rows(report)
    assert "Moonshot Freight Labs" not in rows
    assert "Harbor Point Robotics" not in rows
    excluded = {r["employer"]: r for r in report["policy_exclusions"]}
    rules = lambda emp: {h["rule_id"] for h in excluded[emp]["screen_detail"]["exclusions"]}  # noqa: E731
    assert "no-cash-pay" in rules("Moonshot Freight Labs")
    assert "location-eligibility" in rules("Harbor Point Robotics")


def test_known_operator_exclusions_still_hold_and_the_video_gate_is_held_not_rejected(world):
    _discovery_round(world)
    world.report("2026-11-11")
    report = world.saved_report("2026-11-11")
    excluded = {r["employer"]: r for r in report["policy_exclusions"]}
    assert "sales-ownership" in {h["rule_id"] for h in
                                 excluded["Quota Systems Inc"]["screen_detail"]["exclusions"]}
    assert "voice-telephony" in {h["rule_id"] for h in
                                 excluded["Sonic Lines"]["screen_detail"]["exclusions"]}
    held = _rows(report)["Tapeline Logistics"]
    assert held["screen_outcome"] == "PENDING_CHECK"
    reasons = [h["reason"] for h in held["screen_detail"]["pending_checks"]]
    assert any(r.startswith("HUMAN-FIRST HOLD:") for r in reasons), reasons


# ==================================================================================================
# Company-first watchlist: financing is not a mandate
# ==================================================================================================
def _efts(names_states):
    return {"hits": {"total": {"value": len(names_states)}, "hits": [
        {"_source": {"display_names": [f"{n}  (CIK 000{i})"], "ciks": [f"000{i}"],
                     "file_date": "2026-11-05", "form": "D", "adsh": f"000{i}-26-000001",
                     "biz_states": [st], "biz_locations": [loc]}}
        for i, (n, st, loc) in enumerate(names_states, start=1)
    ]}}


def test_a_financed_company_with_no_opening_stays_on_the_watchlist(world):
    from src.discovery.handler import persist_signal_round

    _discovery_round(world)
    payload = _efts([("Granite Lake Robotics, Inc.", "NH", "Meredith, NH"),
                     ("Northwind Freight Co", "MA", "Boston, MA"),
                     ("Granite Growth Fund I, L.P.", "NH", "Concord, NH")])
    with patch.dict(os.environ, dict(world.env, JPRS_COMPANY_SIGNALS="on")):
        summary = persist_signal_round(
            world.s3, BUCKET, run_id="2026-11-11", now=datetime(2026, 11, 11, tzinfo=timezone.utc),
            jobs=[], fetch=lambda url: _fetch_result(payload, url))
    assert summary["signals"] == 2                       # the fund is not an operating company
    world.report("2026-11-11")
    report = world.saved_report("2026-11-11")
    watch = {s["company"]: s for s in report["company_watchlist"]["signals"]}
    lake = watch["Granite Lake Robotics, Inc."]
    assert lake["status"] == "watchlist" and lake["mandate"].startswith("unknown")
    assert lake["priority"] == 0                         # home state first
    assert "Granite Lake Robotics, Inc." not in _rows(report)   # never a candidate
    # The same employer with an observed opening graduates, naming the posting.
    northwind = watch["Northwind Freight Co"]
    assert northwind["status"] == "graduated" and northwind["graduated_by"]
    md = world.saved_markdown("2026-11-11")
    assert "Pre-opening research watchlist" in md and "mandate unknown" in md


# ==================================================================================================
# Delivery: budget-aware publication, degraded path, idempotent digest
# ==================================================================================================
class _Ctx:
    def __init__(self, seconds):
        import time

        self._end = time.monotonic() + seconds

    def get_remaining_time_in_millis(self):
        import time

        return int((self._end - time.monotonic()) * 1000)


class _FixedCtx:
    def __init__(self, seconds):
        self.seconds = seconds

    def get_remaining_time_in_millis(self):
        return int(self.seconds * 1000)


def _report_with(world, run_id, *, mode="assemble", ctx=None, ctx_error=None, env_extra=None):
    from src.report.handler import handler as report

    event = {"run_id": run_id, "dt": run_id, "mode": mode,
             "runContext": {"run_id": run_id, "dt": run_id,
                            **({"error": {"Error": ctx_error}} if ctx_error else {})}}
    with patch.dict(os.environ, dict(world.env, **(env_extra or {}))):
        return report(event, ctx)


def test_a_round_short_of_time_publishes_a_partial_report_that_names_what_it_skipped(world):
    import src.report.handler as rh

    _discovery_round(world)
    # A deterministic clock that advances one second per reading, so "this round is slow" is a fact
    # of the test rather than of the machine. Budget 60 s, reserve 45 s, one posting per chunk.
    ticks = iter(range(10_000))
    with patch.object(rh, "EVALUATION_CHUNK", 1), \
            patch("time.monotonic", side_effect=lambda: float(next(ticks))):
        out = _report_with(world, "2026-11-11", ctx=_FixedCtx(60.0))
    report = world.saved_report("2026-11-11")
    ev = report["evaluation"]
    assert out["delivery_mode"] == "partial" and report["delivery_mode"] == "partial"
    assert ev["stopped_for_budget"] is True and ev["evaluated"] >= 1
    assert ev["evaluated"] + ev["not_evaluated"] == ev["population"]
    assert len(ev["not_evaluated_job_ids"]) == ev["not_evaluated"]
    md = world.saved_markdown("2026-11-11")
    assert "Partial evaluation" in md and "return as unseen" in md
    # Unevaluated postings are not recorded as shown.
    shown = {r["job_id"] for r in report["complete_candidate_list"]}
    assert not shown & set(ev["not_evaluated_job_ids"])


def test_a_generous_budget_evaluates_everything_and_matches_the_unbudgeted_report(world):
    _discovery_round(world)
    _report_with(world, "2026-11-11")
    unbudgeted = world.saved_report("2026-11-11")
    _report_with(world, "2026-11-11", ctx=_Ctx(900.0))
    budgeted = world.saved_report("2026-11-11")
    assert budgeted["evaluation"]["complete"] is True
    for key in ("complete_candidate_list", "policy_exclusions", "below_fit_threshold_job_ids",
                "matching_job_count", "new_strong_count"):
        assert budgeted[key] == unbudgeted[key], key


def test_the_degraded_path_publishes_the_fresh_cohort_and_says_why(world):
    _discovery_round(world)
    out = _report_with(world, "2026-11-11", mode="incomplete", ctx_error="Sandbox.Timedout")
    report = world.saved_report("2026-11-11")
    assert out["delivery_mode"] == "degraded"
    assert report["evaluation"]["cohort"] == "fresh"
    assert report["evaluation"]["degraded_reason"] == "the full assembly ran out of time"
    md = world.saved_markdown("2026-11-11")
    assert "This is the DEGRADED report" in md


def test_degraded_then_full_on_one_day_sends_exactly_one_digest(world):
    import boto3

    ses = boto3.client("ses", region_name="us-east-1")
    for address in ("radar@example.invalid", "brett@example.invalid"):
        ses.verify_email_identity(EmailAddress=address)
    env = {"SES_SENDER": "radar@example.invalid", "DIGEST_RECIPIENT": "brett@example.invalid"}
    _discovery_round(world)
    first = _report_with(world, "2026-11-11", mode="incomplete", ctx_error="Sandbox.Timedout",
                         env_extra=env)
    second = _report_with(world, "2026-11-11", env_extra=env)
    assert first["digest_delivery"] == "sent"
    assert second["digest_delivery"] == "already-sent"
    # The persisted report is the complete one; the marker still names the single send.
    assert world.saved_report("2026-11-11")["delivery_mode"] == "complete"
    marker = json.loads(world.s3.get_object(
        Bucket=BUCKET, Key=s3layout.digest_delivery_key("2026-11-11"))["Body"].read())
    assert marker["message_id"]


# ==================================================================================================
# Infrastructure facts the repair depends on
# ==================================================================================================
def test_build_report_does_not_retry_a_deterministic_timeout():
    asl = json.loads((ROOT / "infra/statemachine/jprs-daily-assemble.asl.json").read_text())
    retry = asl["States"]["BuildReport"]["Retry"][0]["ErrorEquals"]
    assert "States.TaskFailed" not in retry and "States.ALL" not in retry
    assert asl["States"]["BuildReport"]["Catch"][0]["Next"] == "ReportIncomplete"
    assert asl["States"]["ReportIncomplete"]["Parameters"]["Payload"]["mode"] == "incomplete"


def test_report_function_has_one_full_vcpu():
    text = (ROOT / "infra/template.yaml").read_text()
    block = text[text.index("  ReportFunction:"):text.index("  ReportFunction:") + 4000]
    assert "MemorySize: 1769" in block and "Timeout: 300" in block
