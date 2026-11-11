"""Regression tests for the R1–R4 release defects found in the P01 orchestrator review.

Every test in this file was written to FAIL against the P01 implementation and was confirmed failing
before any repair. The reproduction transcript is in the P02 run root under
`evidence/defect_reproduction_before_repair.txt`.

What each group pins down:

  R1  the Adzuna runtime. P01's own test passed `providers=["adzuna"]` explicitly, so it never
      exercised the DEFAULT path — which could not reach Adzuna at all — and the connector read
      `os.environ` while the Lambda passed SSM values in a dict, so a real credential could never
      reach a request. Tests here run at the HANDLER boundary with mocked AWS and captured
      transport, which is the gap that let both slip through.
  R2  Himalayas is a cursor-paginated browse endpoint capped at 20 jobs per request (provider docs,
      2026-09-24), not a bulk feed. One request was treated as the whole feed.
  R3  screening polarity. "No security clearance is required" was EXCLUDED for clearance, and
      "build tools for the sales team to research prospects" was EXCLUDED as sales ownership.
  R4  the documented rollback was rejected by the AWS CLI, and the documented full rollback would
      have destroyed the uncommitted implementation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from src.common.connectors import FetchResult
from src.common.models import CanonicalJob, IdKind, RemoteMode, ScreenOutcome
from src.discovery.connectors import AdzunaConnector, get_discovery_connector

from src.candidate.screening import HUMAN_FIRST_HOLD  # noqa: E402

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
BUCKET = "jprs-test-bucket"
FAKE_ID = "TEST_APP_ID_abc123"
FAKE_KEY = "TEST_APP_KEY_xyz789"
PROCESS_OK = "Interview process: two video calls with the team."


def _fr(payload, url="local://fixture"):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return FetchResult(raw_bytes=raw, http_status=200, error_class=None,
                       endpoint_url=url, request_at=NOW, response_at=NOW)


def _job(description, title="Senior Software Engineer", **kw):
    return CanonicalJob(
        source_id="t:src", job_id=f"t:src#{abs(hash(description + title)) % 10**8}",
        id_kind=IdKind.NATIVE_ID, title=title, description_text=description,
        raw_location=kw.pop("location", "Remote, US"),
        canonical_location="remote, us", remote_hybrid_language=RemoteMode.REMOTE, **kw,
    )


# ==================================================================================================
# R1 — the Adzuna runtime, tested at the handler boundary
# ==================================================================================================
@pytest.fixture
def aws_env(monkeypatch):
    """Mocked S3 + SSM, with the real process environment cleared of any Adzuna credential."""
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    monkeypatch.setenv("JPRS_BUCKET", BUCKET)
    monkeypatch.setenv("JPRS_SECRETS_SSM_PREFIX", "/jprs/secrets")
    monkeypatch.delenv("JPRS_DISCOVERY_PROVIDERS", raising=False)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        yield


def _put_ssm_credentials():
    ssm = boto3.client("ssm", region_name="us-east-1")
    ssm.put_parameter(Name="/jprs/secrets/ADZUNA_APP_ID", Value=FAKE_ID, Type="SecureString")
    ssm.put_parameter(Name="/jprs/secrets/ADZUNA_APP_KEY", Value=FAKE_KEY, Type="SecureString")


def _capture_transport(monkeypatch):
    """Replace the live fetcher with a capture that records the URL actually requested."""
    import src.discovery.handler as handler_module

    captured: list[tuple[str, str]] = []

    def fake_fetcher(provider, board_token, url):
        captured.append((provider, url))
        connector = get_discovery_connector(provider)
        if provider == "adzuna":
            payload = {"results": [{
                "id": f"adz-{len(captured)}",
                "title": "Business Systems Engineer",
                "created": "2026-09-22T00:00:00Z",
                "company": {"display_name": f"Granite Supply {len(captured)}"},
                "location": {"display_name": "Manchester, New Hampshire"},
                "description": "You will automate internal back-office processes...",
                "redirect_url": f"https://www.adzuna.com/details/{len(captured)}",
                "category": {"label": "IT Jobs"},
            }]}
        elif provider == "remoteok":
            payload = []
        else:
            payload = {"jobs": []}
        return _fr(payload, url)

    monkeypatch.setattr(handler_module, "_live_fetcher", fake_fetcher)
    return captured


def test_r1_default_handler_path_reaches_authenticated_adzuna_requests(aws_env, monkeypatch):
    """R1: with credentials in SSM, the DEFAULT handler path must actually query Adzuna.

    Fails before repair: the default was `keyless_discovery_providers()`, so Adzuna was unreachable
    no matter what credentials existed.
    """
    from src.discovery.handler import handler

    _put_ssm_credentials()
    captured = _capture_transport(monkeypatch)

    result = handler({"run_id": "2026-09-24"}, None)

    assert "adzuna" in result["discovery_attempted"], result
    adzuna_urls = [url for provider, url in captured if provider == "adzuna"]
    assert adzuna_urls, "no Adzuna request was made on the default path"
    # the credential resolved from SSM must reach the outbound request
    assert all(f"app_id={FAKE_ID}" in url for url in adzuna_urls)
    assert all(f"app_key={FAKE_KEY}" in url for url in adzuna_urls)


def test_r1_missing_credentials_remain_a_visible_gate_on_the_default_path(aws_env, monkeypatch):
    """R1: with NO credential anywhere, the default path must NAME Adzuna as gated.

    Fails before repair: Adzuna was absent from the default provider list, so it was neither
    attempted nor reported — the coverage receipt simply did not mention it.
    """
    from src.discovery.handler import handler

    captured = _capture_transport(monkeypatch)
    result = handler({"run_id": "2026-09-24"}, None)

    assert "adzuna" in result["credential_gated"], result
    assert "adzuna" not in result["discovery_attempted"]
    assert not [u for p, u in captured if p == "adzuna"], "gated source must not be requested"

    s3 = boto3.client("s3", region_name="us-east-1")
    from src.common import s3layout

    doc = json.loads(s3.get_object(
        Bucket=BUCKET, Key=s3layout.discovery_coverage_key("2026-09-24"))["Body"].read())
    gated = {g["provider"] for g in doc["credential_gated"]}
    assert "adzuna" in gated
    assert any("ADZUNA_APP_ID" in g["required"] for g in doc["credential_gated"])


def test_r1_location_coverage_includes_us_remote_and_state_scoped_searches(aws_env, monkeypatch):
    """R1: both US-remote and location-scoped work must be represented, without narrowing
    every search to one state.

    Fails before repair: no request ever carried `where`.
    """
    from src.discovery.handler import handler

    _put_ssm_credentials()
    captured = _capture_transport(monkeypatch)
    handler({"run_id": "2026-09-24"}, None)

    adzuna_urls = [url for provider, url in captured if provider == "adzuna"]
    assert adzuna_urls
    with_where = [u for u in adzuna_urls if "where=" in u]
    without_where = [u for u in adzuna_urls if "where=" not in u]
    # location-scoped coverage exists...
    assert with_where, "no location-scoped Adzuna search was issued"
    # ...and nationwide/remote coverage is NOT abandoned in favor of one state
    assert without_where, "every search was location-narrowed; nationwide coverage was lost"
    joined = " ".join(with_where).lower()
    assert "hampshire" in joined, "New Hampshire coverage missing"
    assert any("remote" in u.lower() for u in adzuna_urls), "US-remote coverage missing"


def test_r1_credentials_never_appear_in_stored_artifacts(aws_env, monkeypatch):
    """R1: no receipt, coverage doc, normalized record or status object may carry the credential.

    Fails before repair: SourceReceipt.endpoint_url stored the full signed URL, and the receipt is
    written to raw/ in S3.
    """
    from src.discovery.handler import handler

    _put_ssm_credentials()
    _capture_transport(monkeypatch)
    handler({"run_id": "2026-09-24"}, None)

    s3 = boto3.client("s3", region_name="us-east-1")
    leaked = []
    token = None
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET):
        for item in page.get("Contents", []):
            body = s3.get_object(Bucket=BUCKET, Key=item["Key"])["Body"].read()
            if FAKE_ID.encode() in body or FAKE_KEY.encode() in body:
                leaked.append(item["Key"])
    assert leaked == [], f"credentials leaked into stored artifacts: {leaked}"


def test_r1_intentional_provider_disablement_is_respected(aws_env, monkeypatch, tmp_path):
    """R1: a provider marked `enabled: false` in config must not run even with credentials."""
    from src.discovery.handler import handler

    config = tmp_path / "discovery_sources.yaml"
    config.write_text(
        "discovery_sources:\n"
        "  - provider: adzuna\n"
        "    kind: query_feed\n"
        "    enabled: false\n"
        "    auth: app_id_and_key\n"
        "    credential_env: [ADZUNA_APP_ID, ADZUNA_APP_KEY]\n"
        "  - provider: remotive\n"
        "    kind: bulk_feed\n"
        "    enabled: true\n"
        "    auth: none\n"
    )
    monkeypatch.setenv("JPRS_DISCOVERY_YAML", str(config))
    _put_ssm_credentials()
    captured = _capture_transport(monkeypatch)

    result = handler({"run_id": "2026-09-24"}, None)
    assert "adzuna" not in result["discovery_attempted"]
    assert "adzuna" not in result.get("credential_gated", [])  # disabled, not gated
    assert not [u for p, u in captured if p == "adzuna"]
    assert "remotive" in result["discovery_attempted"]


def test_r1_connector_uses_injected_env_not_process_environment(monkeypatch):
    """R1: the unit-level root cause. `endpoint()` read os.environ directly."""
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    connector = AdzunaConnector().with_env({"ADZUNA_APP_ID": FAKE_ID, "ADZUNA_APP_KEY": FAKE_KEY})
    url = connector.endpoint("1|internal tools engineer|New Hampshire")
    assert f"app_id={FAKE_ID}" in url
    assert f"app_key={FAKE_KEY}" in url
    assert "where=New+Hampshire" in url or "where=New%20Hampshire" in url
    # the shared registry instance must NOT have been mutated
    assert AdzunaConnector.credentials_present({}) is False


# ==================================================================================================
# R2 — honest pagination and resumption
# ==================================================================================================
def _himalayas_page(index, cursor_out, *, employer_prefix="Page"):
    return {
        "jobs": [{
            "title": "Senior Software Engineer",
            "companyName": f"{employer_prefix} {index} Freight Systems",
            "companySlug": f"p{index}-freight",
            "excerpt": "You will build Python services on AWS and automate internal processes.",
            "description": "You will build Python services on AWS and automate internal processes.",
            "applicationLink": f"https://himalayas.app/companies/p{index}-freight/jobs/se",
            "guid": f"https://himalayas.app/companies/p{index}-freight/jobs/se-{index}",
            "locationRestrictions": "['United States']",
            "employmentType": "Full Time",
        }],
        "nextCursor": cursor_out,
        "totalCount": 500,
    }


def test_r2_a_relevant_employer_beyond_page_one_reaches_the_report():
    """R2: the core loss mode. One request was treated as the whole feed.

    Fails before repair: exactly one request was made and page two never arrived.
    """
    from src.discovery.handler import run_discovery

    pages = {None: _himalayas_page(1, "CURSOR_2"), "CURSOR_2": _himalayas_page(2, None)}
    seen_cursors = []

    def fetcher(provider, token, url):
        cursor = None
        if "cursor=" in url:
            cursor = url.split("cursor=")[1].split("&")[0]
        seen_cursors.append(cursor)
        return _fr(pages[cursor], url)

    outcome = run_discovery(run_id="r", now=NOW, fetcher=fetcher, providers=["himalayas"], env={})
    employers = {job.employer_name for job in outcome.jobs}
    assert "Page 2 Freight Systems" in employers, (
        f"page-two employer never arrived; cursors requested: {seen_cursors}"
    )
    assert len(seen_cursors) >= 2


def test_r2_remaining_pages_persist_their_cursor_and_resume_next_run():
    """R2: bounded work may defer pages, but must persist and resume the cursor."""
    from src.discovery.budget import DiscoveryState
    from src.discovery.handler import run_discovery

    pages = {
        None: _himalayas_page(1, "CURSOR_2"),
        "CURSOR_2": _himalayas_page(2, "CURSOR_3"),
        "CURSOR_3": _himalayas_page(3, None),
    }

    def fetcher(provider, token, url):
        cursor = url.split("cursor=")[1].split("&")[0] if "cursor=" in url else None
        return _fr(pages[cursor], url)

    state = DiscoveryState()
    # CONTRACT CHANGE (P03/F1): at a 1-page budget the head check now claims the page, because a
    # posting that appeared since the last check must not wait a run. Resumption therefore needs at
    # least 2 pages — one for the head, the rest for catch-up. The starvation case at budget 1 is
    # covered by `test_f1_budget_of_one_page_reports_backfill_starvation`.
    first = run_discovery(run_id="r1", now=NOW, fetcher=fetcher, providers=["himalayas"],
                          state=state, env={}, max_pages_per_source=2)
    doc = first.coverage_doc()
    assert doc["backlog_items"] >= 1 or doc["query_families_saturated"], (
        "deferred pages left no trace; coverage falsely reads complete"
    )
    # With no prior cursor the first run has no backfill to protect, so the head walk IS the
    # catch-up and spends the whole budget: two pages, ending at CURSOR_3.
    saved = first.state.source_cursors.get("himalayas")
    assert saved == "CURSOR_3", f"cursor not persisted, got {saved!r}"

    second = run_discovery(run_id="r2", now=NOW, fetcher=fetcher, providers=["himalayas"],
                           state=first.state, env={}, max_pages_per_source=2)
    # Run two rechecks the head (page 1) AND resumes the backfill from CURSOR_3, which is the last
    # page of this fixture's chain, so the feed is now exhausted and the cursor clears.
    fetched_employers = {job.employer_name for job in second.jobs}
    assert "Page 1 Freight Systems" in fetched_employers, "the head was not rechecked"
    assert "Page 3 Freight Systems" in fetched_employers, "the backfill did not resume"
    assert second.state.source_cursors.get("himalayas") is None, "feed should now be exhausted"


def test_r2_a_finite_budget_reports_partial_coverage_not_false_completion():
    from src.discovery.handler import run_discovery

    def fetcher(provider, token, url):
        return _fr(_himalayas_page(1, "STILL_MORE"), url)

    outcome = run_discovery(run_id="r", now=NOW, fetcher=fetcher, providers=["himalayas"],
                            env={}, max_pages_per_source=2)
    doc = outcome.coverage_doc()
    assert doc["query_families_saturated"] or doc["backlog_items"], (
        "a feed with a live nextCursor must not report complete coverage"
    )


def test_r2_pagination_stops_and_does_not_loop_on_a_repeated_cursor():
    """A provider echoing the same cursor must not cause an endless crawl."""
    from src.discovery.handler import run_discovery

    calls = {"n": 0}

    def fetcher(provider, token, url):
        calls["n"] += 1
        return _fr(_himalayas_page(1, "SAME_CURSOR"), url)

    run_discovery(run_id="r", now=NOW, fetcher=fetcher, providers=["himalayas"], env={},
                  max_pages_per_source=10)
    assert calls["n"] <= 10


def test_r2_a_timeout_mid_pagination_keeps_the_cursor_for_the_next_run():
    from src.discovery.budget import DiscoveryState
    from src.discovery.handler import run_discovery

    def fetcher(provider, token, url):
        if "cursor=CURSOR_2" in url:
            raise TimeoutError("connection timed out")
        return _fr(_himalayas_page(1, "CURSOR_2"), url)

    state = DiscoveryState()
    outcome = run_discovery(run_id="r1", now=NOW, fetcher=fetcher, providers=["himalayas"],
                            state=state, env={}, max_pages_per_source=4)
    assert outcome.jobs, "page one should still be kept when page two fails"
    assert any("himalayas" in item["target"] for item in outcome.inaccessible)
    assert outcome.state.source_cursors.get("himalayas") == "CURSOR_2", (
        "a failed page must leave its cursor in place so the next run retries it"
    )


def test_r2_rate_limited_page_is_recorded_and_resumable():
    from src.common.connectors import FetchResult as FR
    from src.discovery.handler import run_discovery

    def fetcher(provider, token, url):
        if "cursor=" in url:
            return FR(raw_bytes=None, http_status=429, error_class="http_429",
                      endpoint_url=url, request_at=NOW, response_at=NOW)
        return _fr(_himalayas_page(1, "CURSOR_2"), url)

    outcome = run_discovery(run_id="r", now=NOW, fetcher=fetcher, providers=["himalayas"],
                            env={}, max_pages_per_source=4)
    assert outcome.jobs
    assert any("himalayas" in i["target"] for i in outcome.inaccessible)
    assert outcome.state.source_cursors.get("himalayas") == "CURSOR_2"


def test_r2_himalayas_requests_the_provider_documented_page_size():
    """Provider docs, 2026-09-24: 'limit: the number of jobs to retrieve (max 20)'."""
    connector = get_discovery_connector("himalayas")
    url = connector.endpoint("all")
    assert "limit=20" in url, f"asking for more than the documented maximum: {url}"


def test_r2_adzuna_full_page_queues_its_next_page():
    """The same loss mode on the query feed: a full page means more results exist behind it."""
    from src.discovery.handler import run_discovery

    connector = AdzunaConnector()

    def fetcher(provider, token, url):
        results = [{
            "id": f"a{i}", "title": "Software Engineer", "created": "2026-09-22T00:00:00Z",
            "company": {"display_name": f"Co {i}"},
            "location": {"display_name": "Remote"},
            "description": "You will build Python services...",
            "redirect_url": f"https://www.adzuna.com/details/{i}",
        } for i in range(connector.results_per_page)]
        return _fr({"results": results}, url)

    outcome = run_discovery(
        run_id="r", now=NOW, fetcher=fetcher, providers=["adzuna"],
        env={"ADZUNA_APP_ID": FAKE_ID, "ADZUNA_APP_KEY": FAKE_KEY},
    )
    doc = outcome.coverage_doc()
    assert doc["query_families_saturated"], "a full Adzuna page must mark the family saturated"
    assert doc["backlog_items"], "the next page must be queued, not dropped"


# ==================================================================================================
# R3 — screening polarity and whose work a sentence describes
# ==================================================================================================
@pytest.mark.parametrize("description", [
    "The role: build backend services. Requirements: No security clearance is required. " + PROCESS_OK,
    "Requirements: Python. This position does not require a security clearance. " + PROCESS_OK,
    "Requirements: Python, AWS. No clearance needed. " + PROCESS_OK,
    "We do not require any security clearance for this role. " + PROCESS_OK,
])
def test_r3_negated_clearance_requirement_is_not_an_exclusion(description):
    """R3: 'No security clearance is required' was EXCLUDED before repair."""
    from src.candidate.screening import screen_job

    result = screen_job(_job(description))
    rules = {hit.rule_id for hit in result.exclusions}
    assert "clearance-government" not in rules, result.human_reason()


@pytest.mark.parametrize("description", [
    "Application process: We do not require a recorded video. " + PROCESS_OK,
    "There is no video interview and no recorded video submission. " + PROCESS_OK,
    "Our process never asks candidates to record a video. " + PROCESS_OK,
])
def test_r3_negated_video_requirement_is_not_an_exclusion(description):
    from src.candidate.screening import screen_job

    result = screen_job(_job(description))
    assert "recorded-video" not in {hit.rule_id for hit in result.exclusions}, result.human_reason()


@pytest.mark.parametrize("description", [
    "What you will do: Build tools for the sales team to research prospects. "
    "Requirements: Python. " + PROCESS_OK,
    "What you will do: you will build growth features whose output reaches members or prospects. "
    "Requirements: Python, AWS. " + PROCESS_OK,
    "The role: maintain the platform our account executives use to manage their pipeline. "
    "Requirements: Python. " + PROCESS_OK,
    "You will build internal dashboards that help the revenue team track quota attainment. "
    + PROCESS_OK,
])
def test_r3_building_for_a_sales_team_is_not_owning_sales(description):
    """R3: tooling and product descriptions are not the candidate's forbidden duties."""
    from src.candidate.screening import screen_job

    result = screen_job(_job(description))
    assert "sales-ownership" not in {hit.rule_id for hit in result.exclusions}, (
        result.human_reason()
    )


@pytest.mark.parametrize("description", [
    "The role: you will own the sales pipeline, run outbound prospecting and close new business. "
    "Requirements: quota-carrying experience. " + PROCESS_OK,
    "You will carry a quota and be responsible for closing deals. " + PROCESS_OK,
    "Your responsibilities include cold calling and generating new prospects. " + PROCESS_OK,
])
def test_r3_genuine_sales_ownership_is_still_excluded(description):
    """The repair must not erase the real exclusion."""
    from src.candidate.screening import screen_job

    result = screen_job(_job(description))
    assert "sales-ownership" in {hit.rule_id for hit in result.exclusions}, result.human_reason()


@pytest.mark.parametrize("description", [
    "Requirements: an active TS/SCI security clearance is required. " + PROCESS_OK,
    "Requirements: you must be able to obtain a Public Trust determination. " + PROCESS_OK,
])
def test_r3_genuine_clearance_requirement_is_still_excluded(description):
    from src.candidate.screening import screen_job

    result = screen_job(_job(description))
    assert "clearance-government" in {hit.rule_id for hit in result.exclusions}


@pytest.mark.parametrize("description", [
    "Application process: please record a short video introduction. " + PROCESS_OK,
    "You will complete a one-way video interview before meeting the team.",
])
def test_r3_genuine_recorded_video_is_still_excluded(description):
    from src.candidate.screening import screen_job

    result = screen_job(_job(description))
    assert "recorded-video" in {h.rule_id for h in result.pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}
    assert "recorded-video" not in {hit.rule_id for hit in result.exclusions}


def test_r3_optional_versus_required_language_is_distinguished():
    """'Clearance a plus' is not a requirement, but it IS worth a human look."""
    from src.candidate.screening import screen_job

    result = screen_job(_job(
        "Requirements: Python and AWS. A security clearance is a plus but not required. "
        + PROCESS_OK
    ))
    assert "clearance-government" not in {hit.rule_id for hit in result.exclusions}
    assert result.outcome != ScreenOutcome.EXCLUDED.value


def test_r3_ambiguous_scope_is_retained_for_review_not_discarded():
    """R3 acceptance: where deterministic evidence cannot settle it, route to review."""
    from src.candidate.screening import screen_job

    result = screen_job(_job(
        "The role: you will work closely with the sales team on pipeline visibility and may help "
        "with some customer outreach. Requirements: Python. " + PROCESS_OK
    ))
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value, result.human_reason()
    assert "sales-ownership" in {hit.rule_id for hit in result.pending_checks}


def test_r3_html_encoded_source_text_is_screened_as_received():
    """Feeds ship entity-encoded prose; polarity must survive decoding."""
    from src.candidate.screening import screen_job

    result = screen_job(_job(
        "Requirements: Python. This role doesn&#39;t require a security clearance &amp; has no "
        "recorded video step. " + PROCESS_OK
    ))
    rules = {hit.rule_id for hit in result.exclusions}
    assert "clearance-government" not in rules, result.human_reason()
    assert "recorded-video" not in rules, result.human_reason()


def test_r3_norm_text_decodes_html_entities():
    from src.common.normalize import norm_text

    assert norm_text("doesn&#39;t require") == "doesn't require"
    assert norm_text("sales &amp; marketing") == "sales & marketing"
    assert norm_text("a&nbsp;b") == "a b"


# ==================================================================================================
# R4 — deployment/rollback readiness, validated locally
# ==================================================================================================
def _handoff_text() -> str:
    """The CURRENT handoff of record.

    Points at the newest run so these properties are asserted against the document an operator would
    actually follow, not a superseded one. Falls back to the P02 handoff if P03 has not been written.
    """
    base = Path("project-factory/outputs/open-market-discovery/runs")
    for run in ("20260924_runtime_boundary_and_fresh_first_v1",
                "20260924_open_market_release_repair_v1"):
        path = base / run / "DEPLOYMENT_HANDOFF.md"
        if path.is_file():
            return path.read_text()
    pytest.skip("no deployment handoff written yet")


def test_r4_documented_partial_disable_carries_every_required_cli_parameter():
    """R4: the P01 command was rejected by the CLI. UpdateSchedule is a full replace."""
    text = _handoff_text()
    assert "update-schedule" in text
    block = text[text.index("update-schedule") - 400: text.index("update-schedule") + 1600]
    # Either the field-preserving --cli-input-json round-trip, or every required flag present.
    uses_round_trip = "get-schedule" in block and "--cli-input-json" in block
    has_all_flags = all(
        flag in block for flag in
        ("--flexible-time-window", "--schedule-expression", "--target")
    )
    assert uses_round_trip or has_all_flags, (
        "documented disable would be rejected: UpdateSchedule requires "
        "--flexible-time-window, --schedule-expression and --target"
    )


def test_r4_full_rollback_does_not_destroy_the_uncommitted_working_tree():
    """R4: `git checkout <rev> -- src/ infra/ config/` would overwrite the implementation.

    Naming the command in order to forbid it is correct documentation, so this checks INTENT: if the
    destructive form appears at all, it must be inside an explicit prohibition, and a non-destructive
    method must be given.
    """
    text = _handoff_text()
    destructive = "git checkout e549a73 -- src/"
    if destructive in text:
        window = text[max(0, text.index(destructive) - 200): text.index(destructive)]
        assert "do not run" in window.lower() or "**do not" in window.lower(), (
            "the destructive checkout appears without being forbidden"
        )
    # and a method that leaves the working tree intact must be documented
    lowered = text.lower()
    assert "git worktree add" in lowered, "no non-destructive rollback method is given"
    assert "never checked out, reset, stashed or staged" in lowered or "untouched" in lowered


def test_r4_partial_disable_is_distinguished_from_full_rollback():
    text = _handoff_text().lower()
    assert "partial" in text
    assert "does not revert" in text or "does not roll back" in text


def test_r4_cost_claim_is_sourced_and_makes_no_free_tier_entitlement_claim():
    text = _handoff_text()
    assert "$0 additional in practice" not in text
    lowered = text.lower()
    assert "assumption" in lowered
    # a bare free-tier entitlement claim must not be asserted
    assert "free tier covers" not in lowered
    assert "pricing" in lowered


def test_r4_remaining_gates_are_named_not_closed_by_one_switch():
    text = _handoff_text().lower()
    assert "adzuna" in text
    assert "proposed" in text  # source growth proposes registry rows; it does not monitor
    for phrase in ("closes the gate", "closes all gates", "one switch closes"):
        assert phrase not in text
