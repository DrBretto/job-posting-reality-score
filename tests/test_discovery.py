"""Discovery tests — acceptance rows 1, 3, 8, 9.

The central property under test: a posting from an employer nobody named can reach the report. The
held-out case enforces that mechanically rather than trusting a comment — no employer name may appear
in the query, and the discovered employer must be absent from the seed registry.

All fixtures are synthetic. No provider payload is committed: several providers restrict
redistribution of their job data, and the plan forbids giant raw dumps.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.common.connectors import FetchResult
from src.common.models import SnapshotStatus, SourceKind, VerificationState
from src.discovery.admission import AdmissionPolicy
from src.discovery.budget import DiscoveryState, SourceBudget, allocate, coverage_summary
from src.discovery.connectors import (
    AdzunaConnector,
    get_discovery_connector,
    keyless_discovery_providers,
)
from src.discovery.handler import run_discovery
from src.discovery.queries import (
    ALL_FAMILIES,
    CompanyNamedInQuery,
    assert_company_independent,
    build_query_plan,
    is_obvious_non_job,
    record_matches_family,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)

# The 15 monitored employers as of this packet. A discovery result naming one of these proves nothing
# about open-market reach, so the held-out test requires an employer OUTSIDE this set.
SEEDED_EMPLOYERS = {
    "Machinify", "ICON", "Cargomatic", "Future", "Axiomatic AI", "Nimble Gravity",
    "Legion Intelligence", "Warp", "Tailscale", "Grafana Labs", "Mozilla", "Snorkel AI",
    "Bolt.new", "Cadence Solutions", "Implicit",
}


def _fr(payload, url="local://fixture"):
    return FetchResult(
        raw_bytes=json.dumps(payload).encode(), http_status=200, error_class=None,
        endpoint_url=url, request_at=NOW, response_at=NOW,
    )


# --------------------------------------------------------------------------------------------------
# Acceptance row 1 — unknown employer reaches the report through a company-independent query
# --------------------------------------------------------------------------------------------------
# A non-software business with an ORDINARY title doing meaningful applied-AI work. This is the plan's
# worked scenario. Note what is NOT here: the employer name appears nowhere in any query, and the
# title contains no AI vocabulary at all.
HELD_OUT_EMPLOYER = "Northbridge Freight Systems"
HELD_OUT_PAYLOAD = {
    "jobs": [
        {
            "id": "hq-99001",
            "url": "https://remotive.com/remote-jobs/backend/business-systems-engineer-99001",
            "title": "Business Systems Engineer",
            "company_name": HELD_OUT_EMPLOYER,
            "category": "Logistics",
            "tags": "['python', 'automation']",
            "job_type": "full_time",
            "publication_date": "2026-09-22T10:00:00",
            "candidate_required_location": "USA",
            "salary": "$140,000 - $165,000",
            "description": (
                "We move freight across the northeast. "
                "What you will do: you will automate manual back-office processes that our "
                "dispatchers run by hand today. You will build Python services on AWS, integrate "
                "our warehouse and accounting systems through REST APIs, and add an LLM-based "
                "document data extraction step for carrier paperwork. You will own these internal "
                "tools end to end. "
                "Requirements: five years of software engineering experience, Python, and comfort "
                "with ambiguous problems. "
                "Interview process: two video calls with the operations director and our engineers."
            ),
        }
    ]
}


def test_held_out_unknown_employer_is_discovered_without_being_named():
    """Row 1: a relevant employer absent from the seed registry arrives via a work-based query."""
    plan = build_query_plan(known_employers=SEEDED_EMPLOYERS)

    # (a) No query names any employer — the property that makes this discovery rather than lookup.
    for _family, phrase in plan.items:
        assert_company_independent(phrase, SEEDED_EMPLOYERS)
    # (b) and the held-out employer is not in a query either, nor in the fixture's configuration.
    for _family, phrase in plan.items:
        assert "northbridge" not in phrase.lower()
        assert "freight" not in phrase.lower()

    def fetcher(provider, token, url):
        assert provider == "remotive"
        return _fr(HELD_OUT_PAYLOAD, url)

    outcome = run_discovery(
        run_id="2026-09-24", now=NOW, fetcher=fetcher, providers=["remotive"],
        known_employers=SEEDED_EMPLOYERS, monitored_count=15, env={},
    )

    # (c) The posting arrived, and its employer was never in the registry.
    assert len(outcome.jobs) == 1
    job = outcome.jobs[0]
    assert job.employer_name == HELD_OUT_EMPLOYER
    assert job.employer_name not in SEEDED_EMPLOYERS
    assert job.source_kind == SourceKind.DISCOVERY_FEED
    # (d) The employer is now an observed candidate source — observed, NOT admitted.
    assert any(
        c.employer_name == HELD_OUT_EMPLOYER for c in outcome.growth.candidates.values()
    )


def test_held_out_job_passes_screening_scoring_and_reaches_the_complete_report():
    """Row 1 continued: prove the whole path, not just the fetch."""
    from src.candidate.screening import screen_job
    from src.common.dedup import deduplicate
    from src.report.handler import ReportInput, render_report
    from src.scoring.scoring import ScoreContext, score_job

    _snap, jobs = get_discovery_connector("remotive").build_snapshot(
        "all", _fr(HELD_OUT_PAYLOAD)
    )
    jobs, dedup_report = deduplicate(jobs)
    job = jobs[0]

    # parsing kept what the operator needs to act
    assert job.title == "Business Systems Engineer"
    assert job.salary is not None and job.salary.min == 140000
    assert job.posting_url.startswith("https://remotive.com/")

    # screening: eligible, and it is NOT excluded by any policy rule
    screen = screen_job(job)
    assert screen.outcome == "ELIGIBLE", screen.human_reason()

    # scoring: retained on WORK evidence despite an ordinary, non-AI title
    card = score_job(ScoreContext(job=job), today=NOW)
    assert card.excluded is False
    # "Business Systems Engineer" is a recognized internal-systems title lane, and the described
    # work reinforces it. Either recall path is acceptable here; what matters is that an ordinary,
    # non-AI title at an unknown employer is RETAINED rather than zeroed.
    assert card.brett_fit.detail["recall_path"] in ("title-signal", "work-evidence")
    assert card.brett_fit.score >= 0.25

    # report: appears in the complete readable list with a link and a reason
    inp = ReportInput(
        run_id="2026-09-24", dt="2026-09-24",
        expected_sources=["remotive:all"], succeeded_sources=["remotive:all"],
        jobs=jobs, scorecards=[card], screen_results={job.job_id: screen},
        dedup=dedup_report.to_json(),
    )
    md, js = render_report(inp)
    assert "Complete candidate list" in md
    assert HELD_OUT_EMPLOYER in md
    assert job.posting_url in md
    assert js["matching_job_count"] == 1
    listed = js["complete_candidate_list"][0]
    assert listed["employer"] == HELD_OUT_EMPLOYER
    assert listed["why_fit"]
    assert listed["posting_url"] == job.posting_url


def test_a_query_that_names_a_known_employer_is_refused():
    """The company-independence invariant is enforced, not documented."""
    with pytest.raises(CompanyNamedInQuery):
        assert_company_independent("machinify applied ai engineer", SEEDED_EMPLOYERS)
    # Casing, punctuation and legal suffixes cannot smuggle a name through.
    with pytest.raises(CompanyNamedInQuery):
        assert_company_independent("Grafana Labs, Inc. backend engineer", SEEDED_EMPLOYERS)
    # An ordinary work phrase is fine.
    assert_company_independent("internal tools engineer", SEEDED_EMPLOYERS)


def test_recall_floor_family_carries_no_ai_vocabulary_and_never_rotates_out():
    """Row 2 support: the floor is why an ordinary title at an ordinary employer can arrive."""
    floor = next(f for f in ALL_FAMILIES if f.key == "ordinary-software")
    assert floor.rotates is False
    blob = " ".join(floor.phrases + floor.match_terms).lower()
    for ai_word in ("ai", "llm", "agentic", "genai", "machine learning"):
        assert f" {ai_word} " not in f" {blob} "


def test_sector_examples_are_not_a_closed_whitelist():
    """Row 2: an employer in an unlisted sector must not be penalized."""
    # A record in a sector nobody enumerated still matches the work families.
    matched = [
        f.key for f in ALL_FAMILIES
        if record_matches_family(
            f, title="Application Engineer",
            description="You will build internal tools for our commercial fishing cooperative.",
        )
    ]
    assert "internal-tools" in matched
    assert "ordinary-software" in matched
    # and no sector family was required for it to match
    assert not any(k.startswith("sector-") for k in matched)


def test_word_boundary_matching_stops_substring_false_positives():
    """A real bug caught against live payloads: `rag` matched inside "storage"."""
    ai = next(f for f in ALL_FAMILIES if f.key == "ai-implementation")
    assert not record_matches_family(
        ai, title="Warehouse Coordinator",
        description="Manage cold storage capacity and fragile freight.",
    )
    assert record_matches_family(
        ai, title="Engineer", description="You will build a RAG pipeline over our documents."
    )


# --------------------------------------------------------------------------------------------------
# Acceptance row 3 — real sources, and fixture vs live is never blurred
# --------------------------------------------------------------------------------------------------
def test_every_keyless_provider_maps_its_own_payload_shape():
    """Row 3: four working, independently-shaped discovery adapters."""
    payloads = {
        "remotive": ({"jobs": [{
            "id": "1", "url": "https://remotive.com/remote-jobs/x", "title": "Backend Engineer",
            "company_name": "Willow Dairy Co-op", "description": "You will build Python services.",
            "candidate_required_location": "USA", "job_type": "full_time",
        }]}, "Willow Dairy Co-op"),
        "remoteok": ([
            {"legal": "attribution notice, not a posting"},
            {"id": "2", "slug": "s", "position": "Integration Developer",
             "company": "Harbor Insurance Group", "description": "You will integrate systems.",
             "location": "United States", "url": "https://remoteok.com/remote-jobs/s"},
        ], "Harbor Insurance Group"),
        "jobicy": ({"jobs": [{
            "id": "3", "url": "https://jobicy.com/jobs/3", "jobTitle": "Automation Engineer",
            "companyName": "Cedar Manufacturing", "jobDescription": "You will automate processes.",
            "jobGeo": "USA", "jobIndustry": "['Manufacturing']", "jobType": "['Full-Time']",
        }]}, "Cedar Manufacturing"),
        "himalayas": ({"jobs": [{
            "title": "Application Engineer", "companyName": "Ridge Health Partners",
            "companySlug": "ridge-health", "description": "You will build internal tools.",
            "applicationLink": "https://himalayas.app/companies/ridge-health/jobs/ae",
            "guid": "https://himalayas.app/companies/ridge-health/jobs/ae",
            "locationRestrictions": "['United States']", "employmentType": "Full Time",
            "minSalary": "140000", "maxSalary": "170000", "currency": "USD",
            "salaryPeriod": "yearly",
        }]}, "Ridge Health Partners"),
    }
    assert set(payloads) == set(keyless_discovery_providers())
    for provider, (payload, expected_employer) in payloads.items():
        snapshot, jobs = get_discovery_connector(provider).build_snapshot("all", _fr(payload))
        assert snapshot.status == SnapshotStatus.SUCCESS, provider
        assert len(jobs) == 1, provider
        assert jobs[0].employer_name == expected_employer, provider
        assert jobs[0].source_kind == SourceKind.DISCOVERY_FEED
        assert jobs[0].posting_url, provider


def test_remoteok_legal_notice_record_is_not_treated_as_a_posting():
    payload = [{"legal": "terms"}, {"id": "9", "position": "Engineer", "company": "Acme",
                                    "description": "d", "url": "https://remoteok.com/x"}]
    _snap, jobs = get_discovery_connector("remoteok").build_snapshot("all", _fr(payload))
    assert len(jobs) == 1 and jobs[0].employer_name == "Acme"


def test_adzuna_is_credential_gated_and_named_not_silently_skipped():
    """Row 3 + row 10: the breadth engine's absence is reported, never glossed over."""
    assert AdzunaConnector.credentials_present({}) is False
    assert AdzunaConnector.credentials_present(
        {"ADZUNA_APP_ID": "a", "ADZUNA_APP_KEY": "b"}
    ) is True

    def fetcher(provider, token, url):  # pragma: no cover - must not be reached
        raise AssertionError("adzuna must not be fetched without credentials")

    outcome = run_discovery(
        run_id="r", now=NOW, fetcher=fetcher, providers=["adzuna"],
        known_employers=SEEDED_EMPLOYERS, env={},
    )
    assert outcome.attempted == []
    assert len(outcome.credential_gated) == 1
    gate = outcome.credential_gated[0]
    assert gate["provider"] == "adzuna"
    assert "ADZUNA_APP_ID" in gate["required"] and "ADZUNA_APP_KEY" in gate["required"]
    doc = outcome.coverage_doc()
    assert doc["credential_gated"][0]["provider"] == "adzuna"


def test_adzuna_predicted_salary_is_never_presented_as_published():
    """An aggregator's salary GUESS must not become a published compensation figure."""
    payload = {"results": [{
        "id": "77", "title": "Software Engineer", "created": "2026-09-20T00:00:00Z",
        "company": {"display_name": "Valley Plumbing Supply"},
        "location": {"display_name": "Manchester, New Hampshire"},
        "description": "You will build internal tools...",
        "redirect_url": "https://www.adzuna.com/details/77",
        "salary_min": 120000, "salary_max": 150000, "salary_is_predicted": "1",
        "category": {"label": "IT Jobs"},
    }]}
    _snap, jobs = AdzunaConnector().build_snapshot("1|software engineer|", _fr(payload))
    job = jobs[0]
    assert job.salary is None
    assert "salary_predicted_by_aggregator_not_published" in job.uncertainty
    # An aggregator description is truncated, so the row is a LEAD, not a verified posting.
    assert job.verification_state == VerificationState.UNVERIFIED_LEAD


def test_a_failing_source_does_not_fail_the_whole_stage():
    """Row 3 + row 8: one bad source is recorded as inaccessible; the others still deliver."""
    def fetcher(provider, token, url):
        if provider == "remoteok":
            raise TimeoutError("connection timed out")
        return _fr(HELD_OUT_PAYLOAD, url)

    outcome = run_discovery(
        run_id="r", now=NOW, fetcher=fetcher, providers=["remotive", "remoteok"],
        known_employers=SEEDED_EMPLOYERS, env={},
    )
    assert "remotive" in outcome.succeeded
    assert "remoteok" not in outcome.succeeded
    assert any("remoteok" in item["target"] for item in outcome.inaccessible)
    assert len(outcome.jobs) == 1  # the healthy source still produced its result


def test_malformed_payload_is_labelled_partial_not_success():
    bad = FetchResult(raw_bytes=b"{not json", http_status=200, error_class=None,
                      endpoint_url="local://x", request_at=NOW, response_at=NOW)
    snapshot, jobs = get_discovery_connector("remotive").build_snapshot("all", bad)
    assert snapshot.status == SnapshotStatus.PARTIAL
    assert jobs == []


# --------------------------------------------------------------------------------------------------
# Acceptance rows 8 + 9 — budgets, saturation, resumable backlog
# --------------------------------------------------------------------------------------------------
def test_budget_exhaustion_defers_work_instead_of_dropping_it():
    """Row 8: a search budget is an operational limit, never a silent truncation."""
    plan = build_query_plan(known_employers=SEEDED_EMPLOYERS)
    budget = SourceBudget(source_provider="adzuna", max_requests_per_run=5)
    work, backlog = allocate(plan, budget)
    assert len(work) == 5
    assert len(backlog) == len(plan) - 5
    assert backlog.reason and "resumable" in backlog.reason
    # nothing was lost: work + backlog reconstructs the whole plan
    assert len(work) + len(backlog) == len(plan)


def test_backlog_runs_first_on_the_next_pass_so_a_family_is_never_starved():
    # CONTRACT CHANGE (P02/R2): a backlog entry is now a `BacklogItem`, not a positional tuple.
    # The work acquired a fourth dimension — the location scope — and a positional tuple silently
    # changes meaning when a dimension is added, which is precisely how deferred work goes missing.
    from src.discovery.budget import BacklogItem

    plan = build_query_plan(known_employers=SEEDED_EMPLOYERS)
    budget = SourceBudget(source_provider="adzuna", max_requests_per_run=3)
    carried = [BacklogItem(family_key="data-extraction", phrase="data pipeline engineer", page=2)]
    work, _backlog = allocate(plan, budget, backlog_first=carried)
    assert work[0].key() == carried[0].key()


def test_coverage_summary_states_what_was_not_covered():
    """Row 8: saturation, deferral and never-run families are all visible."""
    state = DiscoveryState()
    from src.discovery.budget import mark_deferred, record_coverage

    record_coverage(state, family_key="internal-tools", run_id="r", now=NOW, records=4,
                    pages=1, saturated=True)
    mark_deferred(state, ["sector-retail"], "budget exhausted")
    summary = coverage_summary(state)
    assert summary["query_families_saturated"] == ["internal-tools"]
    assert summary["query_families_deferred"] == ["sector-retail"]
    assert "ordinary-software" in summary["query_families_never_run"]
    assert summary["query_families_total"] == len(ALL_FAMILIES)


def test_saturated_family_is_not_deprioritised_next_run():
    """A family with more results behind a ceiling is the opposite of well covered."""
    from src.discovery.budget import record_coverage, well_covered_families

    state = DiscoveryState()
    record_coverage(state, family_key="internal-tools", run_id="r1", now=NOW, records=50,
                    pages=1, saturated=True)
    record_coverage(state, family_key="sector-retail", run_id="r1", now=NOW, records=3,
                    pages=1, saturated=False)
    covered = well_covered_families(state, current_run_id="r2")
    assert "internal-tools" not in covered
    assert "sector-retail" in covered


def test_obvious_non_jobs_are_rejected_but_role_suitability_is_not_the_crawlers_job():
    """Row 3: course pages and talent pools are not openings. Poor fit is the screener's call."""
    assert is_obvious_non_job("Join our talent community", "Register for future opportunities")
    assert is_obvious_non_job("Python Bootcamp", "Our curriculum covers...")
    assert is_obvious_non_job("General Application", "Submit a speculative application")
    # A genuine opening that happens to be a poor fit is NOT filtered here.
    assert is_obvious_non_job("Frontend Engineer", "You will own our design system.") is None


def test_records_without_an_employer_are_not_shipped_as_candidates():
    payload = {"jobs": [{"id": "1", "url": "https://remotive.com/x", "title": "Engineer",
                         "company_name": "", "description": "d"}]}

    def fetcher(provider, token, url):
        return _fr(payload, url)

    outcome = run_discovery(run_id="r", now=NOW, fetcher=fetcher, providers=["remotive"], env={})
    assert outcome.jobs == []
    assert any("no employer name" in i["reason"] for i in outcome.inaccessible)


def test_operator_disabled_employer_is_dropped_after_being_counted():
    """Row 9 + admission: a sticky disable is honored without pretending we never saw them."""
    from src.discovery.admission import SourceRegistryGrowth
    from src.common.normalize import normalize_employer

    growth = SourceRegistryGrowth(
        operator_disabled=[normalize_employer(HELD_OUT_EMPLOYER)]
    )

    def fetcher(provider, token, url):
        return _fr(HELD_OUT_PAYLOAD, url)

    outcome = run_discovery(
        run_id="r", now=NOW, fetcher=fetcher, providers=["remotive"], growth=growth, env={},
    )
    assert outcome.jobs == []
    candidate = growth.candidates[normalize_employer(HELD_OUT_EMPLOYER)]
    assert candidate.state.value == "OPERATOR_DISABLED"
    assert candidate.observation_count == 1  # counted, then dropped


def test_manual_import_is_labelled_and_does_not_count_as_discovery():
    """Row 3: a fallback import must never be presented as unattended discovery."""
    from src.discovery.manual_import import import_urls

    html = """
    <html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting","title":"Internal Tools Engineer",
     "hiringOrganization":{"@type":"Organization","name":"Granite Precision Machining"},
     "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress",
        "addressLocality":"Nashua","addressRegion":"NH","addressCountry":"US"}},
     "employmentType":"FULL_TIME",
     "description":"You will build internal tools and automate our shop floor reporting."}
    </script></head><body></body></html>
    """

    class _Resp:
        body = html.encode()
        final_url = "https://graniteprecision.example/careers/internal-tools"
        http_status = 200

    outcome = import_urls(
        ["https://graniteprecision.example/careers/internal-tools"],
        now=NOW, fetch=lambda url: _Resp(),
    )
    assert len(outcome.jobs) == 1
    job = outcome.jobs[0]
    assert job.employer_name == "Granite Precision Machining"
    assert job.source_kind == SourceKind.MANUAL_IMPORT
    assert "operator_supplied_url" in job.uncertainty
    # SourceKind is what keeps coverage honest: a manual import is not a DISCOVERY_FEED.
    assert job.source_kind != SourceKind.DISCOVERY_FEED


def test_unsupported_page_without_structured_data_becomes_a_verification_lead():
    """Row 3: no JobPosting data means a visible lead, never a record parsed out of prose."""
    from src.discovery.manual_import import import_urls

    class _Resp:
        body = b"<html><body><h1>Careers</h1><p>We are hiring engineers!</p></body></html>"
        final_url = "https://smallbiz.example/careers"
        http_status = 200

    outcome = import_urls(
        ["https://smallbiz.example/careers"], now=NOW, fetch=lambda url: _Resp()
    )
    assert outcome.jobs == []
    assert len(outcome.queued_for_verification) == 1
    assert "no schema.org JobPosting" in outcome.queued_for_verification[0]["reason"]


def test_discovery_never_claims_coverage_it_did_not_achieve():
    """Row 11: the coverage receipt is built from what actually ran."""
    def fetcher(provider, token, url):
        return _fr(HELD_OUT_PAYLOAD, url)

    outcome = run_discovery(
        run_id="r", now=NOW, fetcher=fetcher, providers=["remotive", "adzuna"],
        known_employers=SEEDED_EMPLOYERS, policy=AdmissionPolicy(), env={},
    )
    doc = outcome.coverage_doc()
    assert doc["discovery_attempted"] == ["remotive"]          # adzuna was gated, not attempted
    assert doc["discovery_succeeded"] == ["remotive"]
    assert doc["credential_gated"]                              # and its absence is stated
    assert doc["query_families_never_run"]                      # honest about untouched families
    assert doc["attributions"]                                  # provider terms are honored
