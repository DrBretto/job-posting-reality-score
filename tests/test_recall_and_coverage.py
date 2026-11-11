"""Recall, calibration, health and coverage — acceptance rows 2, 4, 7, 8, 10, 11.

Four of these are REGRESSION tests for defects the plan identified by observation on 2026-09-24. Each
one fails against the pre-overhaul behavior:

  the `FullStack` title scoring 0.00 while `Full Stack` scored 0.38
  a novel or ordinary title being erased by a title-only empty-match gate
  a department that genuinely closed freezing its postings ACTIVE forever
  candidates past row 20 being hidden in JSON instead of handed to the operator
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.candidate.screening import screen_job
from src.common.models import (
    CanonicalJob,
    ChangeEventType,
    HistoryStatus,
    IdKind,
    RemoteMode,
    RunHealth,
    SnapshotStatus,
    SourceKind,
    VerificationState,
)
from src.differ.handler import diff_source
from src.report.handler import (
    CoverageInput,
    ReportInput,
    compute_health_axes,
    compute_run_health,
    render_report,
)
from src.scoring.scoring import ScoreContext, ScoringProfile, score_job
from tests.conftest import make_job, make_snapshot

TODAY = datetime(2026, 9, 24, tzinfo=timezone.utc)
PROCESS_OK = "Interview process: two video calls with the team."

APPLIED_AI_WORK = (
    "What you will do: you will build LLM integrations and agentic workflows, design Python "
    "services on AWS Lambda, and own the evaluation harness. " + PROCESS_OK
)
ORDINARY_INTERNAL_WORK = (
    "What you will do: you will automate manual back-office processes, build Python services on "
    "AWS, integrate our warehouse and accounting systems through REST APIs, and add an LLM-based "
    "document data extraction step. You will own these internal tools end to end. " + PROCESS_OK
)


def _fit(title, description, location="Remote - United States"):
    job = make_job("k", title=title, description=description, location=location, remote="remote")
    return score_job(ScoreContext(job=job), today=TODAY)


# --------------------------------------------------------------------------------------------------
# REGRESSION 1 — the title spelling defect (row 2)
# --------------------------------------------------------------------------------------------------
def test_fullstack_spelling_variants_all_score_identically():
    """Before the repair: `FullStack` -> 0.00, `Full Stack` -> 0.38. Same role, same work."""
    scores = {
        spelling: _fit(f"{spelling} Engineer", APPLIED_AI_WORK).brett_fit.score
        for spelling in ("FullStack", "Full Stack", "Full-Stack", "Fullstack", "full stack")
    }
    assert len(set(scores.values())) == 1, scores
    assert all(score > 0.25 for score in scores.values()), scores


def test_other_compound_spellings_are_also_folded():
    for a, b in (("Backend Engineer", "Back-End Engineer"),
                 ("DevOps Engineer", "Dev Ops Engineer"),
                 ("GenAI Engineer", "Gen AI Engineer")):
        assert _fit(a, APPLIED_AI_WORK).brett_fit.score == \
            _fit(b, APPLIED_AI_WORK).brett_fit.score, (a, b)


# --------------------------------------------------------------------------------------------------
# REGRESSION 2 — the title-only hard zero (row 2)
# --------------------------------------------------------------------------------------------------
def test_ambiguous_and_novel_titles_survive_on_work_evidence():
    """The plan names these exact titles. A title-only gate cannot silently remove them."""
    titles = (
        "Application Engineer",
        "Business Systems Engineer",
        "Integration Developer",
        "Automation Engineer",
        "Hands-on AI Architect",
    )
    for title in titles:
        card = _fit(title, ORDINARY_INTERNAL_WORK)
        assert card.excluded is False, title
        assert card.brett_fit.score >= ScoringProfile().brett_fit_floor, (
            title, card.brett_fit.score
        )


def test_an_ordinary_title_uses_the_work_evidence_path_at_lower_confidence():
    # "Application Engineer" is genuinely ambiguous — it also names customer-facing hardware roles —
    # so it earns no title lane and must be carried by the described work instead.
    card = _fit("Application Engineer", ORDINARY_INTERNAL_WORK)
    assert card.brett_fit.detail["recall_path"] == "work-evidence"
    # Real eligibility, honestly weaker evidence than a title-lane match.
    assert card.brett_fit.confidence < 1.0


# --------------------------------------------------------------------------------------------------
# Row 4 — calibration: practical seniors above topical-only specialists
# --------------------------------------------------------------------------------------------------
def test_practical_senior_match_ranks_above_a_topical_only_specialist():
    practical = _fit("Senior Software Engineer", ORDINARY_INTERNAL_WORK)
    specialist = _fit(
        "AI Research Scientist",
        "Requirements: a PhD and a publication record in generative AI. You will publish papers "
        "and present at conferences. " + PROCESS_OK,
    )
    assert practical.brett_fit.score > specialist.brett_fit.score


def test_staff_title_is_a_labelled_stretch_not_a_rejection():
    card = _fit("Staff Applied AI Engineer", APPLIED_AI_WORK)
    assert card.excluded is False
    assert card.brett_fit.detail["is_stretch_level"] == 1
    # and it ranks below the equivalent senior role rather than being removed
    senior = _fit("Senior Applied AI Engineer", APPLIED_AI_WORK)
    assert senior.brett_fit.score > card.brett_fit.score


def test_pay_above_the_orientation_is_not_a_rejection():
    """~$150K is an orientation, not a gate."""
    from src.common.models import SalarySource, SalaryStruct

    job = make_job("high", title="Senior Applied AI Engineer", description=APPLIED_AI_WORK,
                   location="Remote - United States", remote="remote")
    job.salary = SalaryStruct(min=280000, max=340000, currency="USD", period="year",
                             source=SalarySource.STATED)
    card = score_job(ScoreContext(job=job), today=TODAY)
    assert card.excluded is False
    assert screen_job(job).outcome != "EXCLUDED"


def test_adjacent_learnable_skills_remain_viable():
    """A required framework Brett has not specialized in is not an unmet requirement."""
    job = make_job("go", title="Senior Backend Engineer", description=(
        "What you will do: you will build backend services in Go alongside Python on AWS. "
        + PROCESS_OK
    ), location="Remote - United States", remote="remote")
    card = score_job(ScoreContext(job=job), today=TODAY)
    assert card.excluded is False
    assert screen_job(job).outcome != "EXCLUDED"


# --------------------------------------------------------------------------------------------------
# Row 4 — false positives must still be rejected
# --------------------------------------------------------------------------------------------------
def test_false_positive_cases_are_rejected_or_ranked_low():
    """The plan's own false-positive list. Ambiguous words in the wrong context must not pass."""
    cases = {
        "plc-only": ("Automation Engineer",
                     "You will program Allen-Bradley PLCs and configure SCADA HMI panels on the "
                     "plant floor. Requirements: ladder logic. No software development. "
                     + PROCESS_OK),
        "frontend-polish": ("Software Engineer",
                            "The role: own our design system ownership and pixel-perfect visual "
                            "polish. " + PROCESS_OK),
        "presales": ("Staff Applied AI Engineer - Pre-Sales",
                     "You will support the sales team in customer demos. " + PROCESS_OK),
        "clearance": ("Applied AI Engineer, Federal",
                      "Requirements: an active Top Secret clearance. " + PROCESS_OK),
    }
    for name, (title, description) in cases.items():
        job = make_job(name, title=title, description=description,
                       location="Remote - United States", remote="remote")
        card = score_job(ScoreContext(job=job), today=TODAY)
        screen = screen_job(job)
        rejected = card.excluded or screen.outcome == "EXCLUDED"
        assert rejected, (name, card.brett_fit.score, screen.outcome)


def test_positive_counterexamples_with_the_same_ambiguous_words_survive():
    """Proves discrimination rather than keyword presence."""
    cases = {
        # "automation" in an ordinary software context, not a plant floor
        "software-automation": ("Automation Engineer",
                                "What you will do: you will automate manual back-office workflows "
                                "with Python services on AWS and integrate internal systems. "
                                + PROCESS_OK),
        # "React" present, but the role owns full-stack scope
        "fullstack-with-react": ("FullStack Engineer",
                                 "What you will do: you will own a bounded internal tool end to "
                                 "end, backend APIs plus a React dashboard. " + PROCESS_OK),
        # builds tooling for sales without owning sales results
        "gtm-engineering": ("Software Engineer, GTM Engineering",
                            "What you will do: you will build internal tools for the sales team "
                            "and own CRM integration. No quota. " + PROCESS_OK),
    }
    for name, (title, description) in cases.items():
        job = make_job(name, title=title, description=description,
                       location="Remote - United States", remote="remote")
        card = score_job(ScoreContext(job=job), today=TODAY)
        screen = screen_job(job)
        assert not card.excluded, (name, card.brett_fit.score)
        assert screen.outcome != "EXCLUDED", (name, screen.human_reason())


# --------------------------------------------------------------------------------------------------
# REGRESSION 3 — health recovery from a genuinely closed department (row 7)
# --------------------------------------------------------------------------------------------------
def _board(day, *, include_people=True):
    jobs = [make_job(f"e{i}", department="engineering", fetched_at=day) for i in range(3)]
    if include_people:
        jobs.append(make_job("p1", department="people team", title="Recruiter", fetched_at=day))
    return jobs


def _run(state, jobs, day, run_id):
    snapshot = make_snapshot(SnapshotStatus.SUCCESS, n=len(jobs), fetched_at=day)
    return diff_source(state, snapshot, jobs, run_id=run_id, today=day)


def test_a_partial_feed_still_freezes_removals_indefinitely():
    """Row 7: genuine truncation protection is NOT relaxed by the recovery path."""
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    result = _run(None, _board(base), base, "d0")
    result = _run(result.state, _board(base + timedelta(days=1)), base + timedelta(days=1), "d1")
    for i in range(2, 7):
        day = base + timedelta(days=i)
        result = _run(result.state, [make_job("e0", department="engineering", fetched_at=day)],
                      day, f"d{i}")
        assert result.suspect is True
        assert result.suspect_kind == "mass_drop"
        assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in result.events)
    # the count baseline stays frozen, which is what protects against a poisoned trend
    assert result.state.success_count_history == [4, 4]
    assert result.state.suspect_streak == 5


def test_an_independently_corroborated_department_closure_recovers():
    """Row 7 regression: before the repair this latched forever and never released."""
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    result = _run(None, _board(base), base, "d0")
    result = _run(result.state, _board(base + timedelta(days=1)), base + timedelta(days=1), "d1")
    people = "greenhouse:acme#p1"
    assert result.state.jobs[people].state.value == "ACTIVE"

    # day 2: the department vanishes. Ambiguous -> suppress, and say what was actually observed.
    day2 = base + timedelta(days=2)
    result = _run(result.state, _board(day2, include_people=False), day2, "d2")
    assert result.suspect is True
    assert result.suspect_kind == "silent_subset"
    suspect_note = next(
        e.notes for e in result.events if e.event_type == ChangeEventType.SOURCE_SUSPECT
    )
    assert "NOT a low download count" in suspect_note
    assert "segment" in suspect_note
    assert result.state.jobs[people].absence_count == 0      # grace clock paused

    # day 3: a second independent healthy snapshot agrees -> confirmed closure, latch releases.
    day3 = base + timedelta(days=3)
    result = _run(result.state, _board(day3, include_people=False), day3, "d3")
    assert result.suspect is False
    assert result.confirmed_closed_segments == ["people team"]
    assert any(
        e.event_type == ChangeEventType.SOURCE_SEGMENT_CLOSED for e in result.events
    )
    assert result.state.jobs[people].state.value == "PENDING_REMOVAL"

    # day 4: the ordinary grace clock completes the removal.
    day4 = base + timedelta(days=4)
    result = _run(result.state, _board(day4, include_people=False), day4, "d4")
    assert result.state.jobs[people].state.value == "DISAPPEARED"
    assert any(e.event_type == ChangeEventType.DISAPPEARED for e in result.events)


def test_a_returning_department_resets_its_corroboration_streak():
    """A segment that comes back is not evidence of anything; the counter must not accumulate."""
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    result = _run(None, _board(base), base, "d0")
    result = _run(result.state, _board(base + timedelta(days=1)), base + timedelta(days=1), "d1")
    day2 = base + timedelta(days=2)
    result = _run(result.state, _board(day2, include_people=False), day2, "d2")
    assert result.state.segment_absence_streak.get("people team") == 1
    day3 = base + timedelta(days=3)
    result = _run(result.state, _board(day3, include_people=True), day3, "d3")
    assert "people team" not in result.state.segment_absence_streak
    assert result.state.jobs["greenhouse:acme#p1"].state.value == "ACTIVE"


def test_suspect_streak_and_observed_counts_explain_a_long_running_condition():
    """Row 7: a warning must state the condition, and a repeat must show the trend."""
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    result = _run(None, [make_job(f"j{i}") for i in range(100)], base, "d0")
    for i in range(1, 4):
        day = base + timedelta(days=i)
        result = _run(result.state, [make_job(f"j{i}") for i in range(5)], day, f"d{i}")
    note = next(e.notes for e in result.events if e.event_type == ChangeEventType.SOURCE_SUSPECT)
    assert "consecutive run" in note
    assert "observed counts while suppressed" in note
    assert result.state.suppressed_count_history == [5, 5, 5]


# --------------------------------------------------------------------------------------------------
# REGRESSION 4 — health axes and the overflow cap (rows 8, 10, 11)
# --------------------------------------------------------------------------------------------------
def _discovery_job(index, *, employer, title, description):
    return CanonicalJob(
        source_id="remotive:all", job_id=f"remotive:all#{index}", id_kind=IdKind.NATIVE_ID,
        provider_native_id=str(index), employer_name=employer, title=title,
        description_text=description, posting_url=f"https://remotive.com/remote-jobs/{index}",
        apply_url=f"https://remotive.com/remote-jobs/{index}",
        source_kind=SourceKind.DISCOVERY_FEED, verification_state=VerificationState.FEED_COMPLETE,
        raw_location="USA", canonical_location="united states",
        remote_hybrid_language=RemoteMode.REMOTE, first_seen_at=TODAY, last_seen_at=TODAY,
    )


def _report_with(n_candidates, **kwargs):
    jobs, cards, screens = [], [], {}
    for i in range(n_candidates):
        job = _discovery_job(
            i, employer=f"Employer {i:02d} Logistics",
            title="Business Systems Engineer", description=ORDINARY_INTERNAL_WORK,
        )
        jobs.append(job)
        cards.append(score_job(ScoreContext(job=job), today=TODAY))
        screens[job.job_id] = screen_job(job)
    inp = ReportInput(
        run_id="2026-09-24", dt="2026-09-24",
        expected_sources=["remotive:all"], succeeded_sources=["remotive:all"],
        jobs=jobs, scorecards=cards, screen_results=screens, **kwargs,
    )
    return inp, render_report(inp)


def test_more_than_twenty_candidates_stay_readable_with_links_and_reasons():
    """Row 8 regression: the old cap ended with 'retained in JSON', which is not a handoff."""
    inp, (md, js) = _report_with(27)
    assert js["matching_job_count"] == 27
    assert len(js["complete_candidate_list"]) == 27
    # every single one is readable in the markdown, with its link and its reason
    for job in inp.jobs:
        assert job.employer_name in md
        assert job.posting_url in md
    assert "Complete candidate list" in md
    assert "All 27 retained credible role(s)" in md
    # and the old hiding language is gone
    assert "retained in JSON" not in md


def test_collection_health_is_never_phrased_as_market_coverage():
    """Row 11: fifteen successful fetches cannot yield an all-market claim."""
    _inp, (md, js) = _report_with(3)
    assert "It is not a statement about the job market" in md
    axes = js["health_axes"]
    assert set(axes) >= {
        "collection", "discovery_coverage", "freshness", "interpretation",
    }


def test_health_axes_are_independent():
    """The old single axis returned VERIFIED_QUIET on both arms of its own conditional."""
    inp = ReportInput(
        run_id="r", dt="2026-09-24",
        expected_sources=["greenhouse:a", "greenhouse:b"], succeeded_sources=["greenhouse:a"],
    )
    axes = compute_health_axes(inp)
    assert axes.collection == RunHealth.INCOMPLETE
    assert axes.collection_missing == ["greenhouse:b"]
    # discovery did not run at all, and that is stated rather than folded into collection health
    assert axes.discovery == "NOT-RUN"
    assert "not a search of the open market" in axes.discovery_detail


def test_compute_run_health_still_answers_only_the_collection_question():
    complete = ReportInput(run_id="r", dt="d", expected_sources=["a"], succeeded_sources=["a"])
    assert compute_run_health(complete)[0] == RunHealth.VERIFIED_QUIET
    missing = ReportInput(run_id="r", dt="d", expected_sources=["a", "b"],
                          succeeded_sources=["a"])
    health, names = compute_run_health(missing)
    assert health == RunHealth.INCOMPLETE and names == ["b"]
    no_run = ReportInput(run_id="r", dt="d", expected_sources=["a"], manifest_present=False)
    assert compute_run_health(no_run)[0] == RunHealth.NO_RUN


def test_partial_discovery_coverage_is_reported_with_its_backlog_and_gates():
    """Rows 8 + 10: saturation, deferral, backlog and the credential gate all surface."""
    coverage = CoverageInput(
        discovery_attempted=["remotive", "remoteok"],
        discovery_succeeded=["remotive"],
        query_families_total=14, query_families_covered=9,
        query_families_saturated=["internal-tools"],
        query_families_deferred=["sector-retail"],
        query_families_never_run=["data-extraction"],
        backlog_items=11, backlog_reason="request budget exhausted; resumable",
        budgets={"remotive": {"requests_spent": 1, "max_requests_per_run": 1}},
        credential_gated=[{
            "provider": "adzuna",
            "reason": "requires app_id and app_key",
            "required": "ADZUNA_APP_ID and ADZUNA_APP_KEY",
        }],
        inaccessible=[{"target": "remoteok", "reason": "download labelled FETCH_FAILED"}],
        attributions=["Jobs via Remotive (remotive.com)."],
        previously_unseen_employers=["Northbridge Freight Systems"],
    )
    _inp, (md, js) = _report_with(2, coverage=coverage)
    assert js["health_axes"]["discovery_coverage"] == "PARTIAL"
    assert "Coverage and backlog" in md
    assert "internal-tools" in md and "sector-retail" in md and "data-extraction" in md
    assert "11 query item(s)" in md
    assert "ADZUNA_APP_ID" in md
    assert "adzuna did not run" in md
    assert "Jobs via Remotive" in md          # attribution is rendered, per provider terms
    assert "Northbridge Freight Systems" in md


def test_zero_strong_matches_distinguishes_incomplete_from_completed_search():
    """Row 8: an empty result must say which of the two situations it is."""
    partial = CoverageInput(discovery_attempted=["remotive"], discovery_succeeded=["remotive"],
                            query_families_total=14, query_families_covered=9,
                            query_families_never_run=["data-extraction"])
    jobs = [_discovery_job(0, employer="Frontend Only Co", title="Frontend Engineer",
                           description="You will own our design system. " + PROCESS_OK)]
    cards = [score_job(ScoreContext(job=jobs[0]), today=TODAY)]
    inp = ReportInput(
        run_id="r", dt="2026-09-24", expected_sources=["remotive:all"],
        succeeded_sources=["remotive:all"], jobs=jobs, scorecards=cards,
        screen_results={jobs[0].job_id: screen_job(jobs[0])}, coverage=partial,
    )
    md, js = render_report(inp)
    assert js["new_strong_count"] == 0
    assert "not a statement that no such job exists" in md

    full = CoverageInput(discovery_attempted=["remotive"], discovery_succeeded=["remotive"],
                         query_families_total=14, query_families_covered=14)
    inp.coverage = full
    md2, _js2 = render_report(inp)
    assert "completed search with zero strong matches" in md2


def test_history_labels_route_rows_into_separate_sections():
    """Row 6 + row 8: queued work is surfaced separately, not re-announced as new."""
    jobs, cards, screens = [], [], {}
    for i, status in enumerate((HistoryStatus.NEW, HistoryStatus.PREPARED,
                                HistoryStatus.SUBMITTED)):
        job = _discovery_job(i, employer=f"Employer {i}", title="Business Systems Engineer",
                             description=ORDINARY_INTERNAL_WORK)
        jobs.append(job)
        cards.append(score_job(ScoreContext(job=job), today=TODAY))
        screens[job.job_id] = screen_job(job)
    history = {
        jobs[1].job_id: (HistoryStatus.PREPARED, None),
        jobs[2].job_id: (HistoryStatus.SUBMITTED, None),
    }
    inp = ReportInput(
        run_id="r", dt="2026-09-24", expected_sources=["remotive:all"],
        succeeded_sources=["remotive:all"], jobs=jobs, scorecards=cards,
        screen_results=screens, history_status=history,
    )
    md, js = render_report(inp)
    assert js["new_strong_count"] == 1
    assert js["previously_engaged_count"] == 2
    assert "Already prepared, submitted, or set aside" in md
    # all three are still in the complete list — nothing was dropped
    assert js["matching_job_count"] == 3


def test_excluded_rows_are_reported_with_the_reason_that_excluded_them():
    """Row 5 + row 8: exclusions are visible and explained, not silently removed."""
    job = _discovery_job(0, employer="Cleared Systems Group", title="Software Engineer",
                         description="Requirements: an active TS/SCI clearance. " + PROCESS_OK)
    card = score_job(ScoreContext(job=job), today=TODAY)
    inp = ReportInput(
        run_id="r", dt="2026-09-24", expected_sources=["remotive:all"],
        succeeded_sources=["remotive:all"], jobs=[job], scorecards=[card],
        screen_results={job.job_id: screen_job(job)},
    )
    md, js = render_report(inp)
    assert js["policy_excluded_count"] == 1
    assert "Excluded by candidate policy" in md
    assert "clearance-government" in md
    assert js["policy_exclusions"][0]["screen_detail"]["exclusions"][0]["matched_text"]


def test_employer_comes_from_the_job_not_a_hardcoded_table():
    """Row 1 support: the fifteen-entry company-label map is gone."""
    import src.report.handler as report_module

    assert not hasattr(report_module, "_COMPANY_LABELS")
    job = _discovery_job(0, employer="Northbridge Freight Systems",
                         title="Business Systems Engineer", description=ORDINARY_INTERNAL_WORK)
    card = score_job(ScoreContext(job=job), today=TODAY)
    inp = ReportInput(
        run_id="r", dt="2026-09-24", expected_sources=["remotive:all"],
        succeeded_sources=["remotive:all"], jobs=[job], scorecards=[card],
        screen_results={job.job_id: screen_job(job)},
    )
    md, js = render_report(inp)
    assert "Northbridge Freight Systems" in md
    assert js["complete_candidate_list"][0]["employer"] == "Northbridge Freight Systems"


def test_dates_are_not_interchanged():
    """Plan §3: published, updated, first observed and last verified mean different things."""
    job = _discovery_job(0, employer="Old Posting Co", title="Business Systems Engineer",
                         description=ORDINARY_INTERNAL_WORK)
    job.provider_published_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    job.first_seen_at = TODAY
    job.verified_at = TODAY
    card = score_job(ScoreContext(job=job), today=TODAY)
    inp = ReportInput(
        run_id="r", dt="2026-09-24", expected_sources=["remotive:all"],
        succeeded_sources=["remotive:all"], jobs=[job], scorecards=[card],
        screen_results={job.job_id: screen_job(job)},
    )
    md, js = render_report(inp)
    row = js["complete_candidate_list"][0]
    assert row["provider_published_at"].startswith("2026-06-01")
    assert row["first_seen_at"].startswith("2026-09-24")
    # the markdown distinguishes them in words, so an old posting is never called newly posted
    assert "employer published 2026-06-01" in md
    assert "first seen by JPRS 2026-09-24" in md
