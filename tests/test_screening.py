"""Candidate screening tests — acceptance rows 4 and 5.

Row 5's hard half is not the exclusions, it is the MISFIRES: "boilerplate and unknown information do
not misfire". Every guarded case below is a specific failure mode the central policy names, so each
is tested in both directions — the real exclusion fires, and the look-alike does not.

UNKNOWN is a first-class third state throughout: PENDING_CHECK is neither a pass nor a rejection.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.candidate.screening import (
    Section,
    screen_job,
    segment_description,
)
from src.common.models import (
    CanonicalJob,
    IdKind,
    RemoteMode,
    ScreenOutcome,
    VerificationState,
)

from src.candidate.screening import HUMAN_FIRST_HOLD  # noqa: E402

NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)
PROCESS_OK = "Interview process: two video calls on Zoom with the engineering team."


def _job(
    title, description, *, location="Remote, US", remote=RemoteMode.REMOTE,
    verification=VerificationState.FEED_COMPLETE, uncertainty=None, secondary=None,
):
    return CanonicalJob(
        source_id="t:src", job_id=f"t:src#{abs(hash(title + description)) % 10**8}",
        id_kind=IdKind.NATIVE_ID, title=title, description_text=description,
        raw_location=location, canonical_location=location.lower(),
        secondary_locations=secondary or [],
        remote_hybrid_language=remote, verification_state=verification,
        uncertainty=uncertainty or [], last_seen_at=NOW,
    )


def _outcome(job) -> str:
    return screen_job(job).outcome


def _rules(job, bucket="exclusions") -> set[str]:
    result = screen_job(job)
    return {h.rule_id for h in getattr(result, bucket)}


# --------------------------------------------------------------------------------------------------
# Section segmentation — the mechanism the misfire guards rest on
# --------------------------------------------------------------------------------------------------
def test_segmentation_separates_benefits_from_responsibilities():
    segments = segment_description(
        "What you'll do: build internal tools. Requirements: five years of Python. "
        "Benefits: health insurance and commission eligibility. "
        "Interview process: two video calls."
    )
    sections = {s.section for s in segments}
    assert Section.RESPONSIBILITIES in sections
    assert Section.REQUIREMENTS in sections
    assert Section.BENEFITS in sections
    assert Section.PROCESS in sections
    commission_sections = {s.section for s in segments if "commission" in s.text.lower()}
    assert commission_sections == {Section.BENEFITS}


# --------------------------------------------------------------------------------------------------
# Row 5 — sales
# --------------------------------------------------------------------------------------------------
def test_real_sales_ownership_is_excluded():
    job = _job(
        "Senior Software Engineer",
        "The role: you will own the sales pipeline, run outbound prospecting and close new "
        f"business. Requirements: quota-carrying experience. {PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.EXCLUDED.value
    assert "sales-ownership" in _rules(job)


def test_sales_title_is_excluded():
    for title in ("Account Executive", "Sales Engineer", "Solutions Consultant",
                  "Business Development Representative"):
        job = _job(title, f"You will work with customers. {PROCESS_OK}")
        assert _outcome(job) == ScreenOutcome.EXCLUDED.value, title
        assert "sales-ownership" in _rules(job), title


def test_commission_in_a_benefits_block_does_not_misfire():
    """The first misfire the plan names: benefits boilerplate is not a quota."""
    job = _job(
        "Senior Software Engineer",
        "What you'll do: build internal tools and integrations. Requirements: five years Python. "
        f"Benefits: competitive salary, commission eligibility for some roles, 401k. {PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.ELIGIBLE.value
    result = screen_job(job)
    guarded = {h.rule_id: h.suppressed_by for h in result.suppressed}
    assert guarded.get("sales-ownership") == "benefits-boilerplate guard"


def test_building_tools_for_the_sales_org_is_engineering_not_sales():
    """SEARCH_PREFERENCES explicitly allows GTM/RevOps engineering without quota or closing."""
    job = _job(
        "Senior Software Engineer, GTM Engineering",
        "What you will do: build internal tools for the sales team, own CRM integration and "
        f"Salesforce integration work. There is no quota. {PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.ELIGIBLE.value
    assert "sales-ownership" not in _rules(job)


def test_a_sales_title_with_genuine_quota_language_still_excludes():
    """The GTM guard must not become a loophole for an actual sales job."""
    job = _job(
        "Sales Engineer",
        "You will carry a quota, own the sales pipeline and close deals. We also have a CRM "
        f"integration. {PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.EXCLUDED.value


# --------------------------------------------------------------------------------------------------
# Row 5 — clearance and government
# --------------------------------------------------------------------------------------------------
def test_clearance_requirement_is_excluded():
    for phrase in ("an active TS/SCI security clearance", "a Public Trust determination",
                   "ability to obtain a clearance", "a federal suitability process",
                   "passing a drug screening"):
        job = _job("Software Engineer", f"Requirements: {phrase}. {PROCESS_OK}")
        assert _outcome(job) == ScreenOutcome.EXCLUDED.value, phrase
        assert "clearance-government" in _rules(job), phrase


def test_government_adjacency_without_a_clearance_is_pending_not_excluded():
    """Policy: government-adjacent roles need operator reconsideration, not an automatic verdict."""
    job = _job(
        "Software Engineer",
        f"The role: build data tools for our government customers in the public sector. {PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.PENDING_CHECK.value
    assert "clearance-government" in _rules(job, "pending_checks")
    assert "clearance-government" not in _rules(job)


def test_eeo_boilerplate_mentioning_veterans_does_not_misfire():
    job = _job(
        "Senior Software Engineer",
        "What you'll do: build backend services in Python. "
        "We are an equal employment opportunity employer; all qualified applicants receive "
        "consideration without regard to protected veteran status or disability. "
        f"{PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.ELIGIBLE.value
    assert "clearance-government" not in _rules(job)


# --------------------------------------------------------------------------------------------------
# Row 5 — frontend specialization
# --------------------------------------------------------------------------------------------------
def test_frontend_specialist_title_is_excluded():
    for title in ("Frontend Engineer", "UI Engineer", "Design Systems Engineer", "Web Designer"):
        job = _job(title, f"You will build interfaces. {PROCESS_OK}")
        assert _outcome(job) == ScreenOutcome.EXCLUDED.value, title
        assert "frontend-specialist" in _rules(job), title


def test_frontend_depth_requirement_is_excluded():
    job = _job(
        "Software Engineer",
        "The role: own our design system ownership and deliver pixel-perfect visual polish across "
        f"the product. {PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.EXCLUDED.value
    assert "frontend-specialist" in _rules(job)


def test_full_stack_role_mentioning_react_is_not_a_frontend_specialist():
    """React is a supporting capability. A full-stack owner is a target, not an exclusion."""
    job = _job(
        "FullStack Engineer",
        "What you'll do: own a bounded internal tool end-to-end — backend APIs in Python plus a "
        f"React dashboard, including some component library ownership. {PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.ELIGIBLE.value
    result = screen_job(job)
    assert any(
        h.rule_id == "frontend-specialist" and h.suppressed_by == "full-stack/backend scope guard"
        for h in result.suppressed
    )


# --------------------------------------------------------------------------------------------------
# Row 5 — recorded video vs a live human call
# --------------------------------------------------------------------------------------------------
def test_recorded_candidate_video_is_excluded():
    for phrase in ("please record a short video introduction",
                   "upload your video answers to our one-way interview",
                   "complete a HireVue assessment",
                   "submit a pre-recorded video"):
        job = _job("Software Engineer", f"Application process: {phrase}.")
        # Held under the human-first rule (2026-10-12), not rejected.
        assert _outcome(job) == ScreenOutcome.PENDING_CHECK.value, phrase
        assert "recorded-video" in {h.rule_id for h in screen_job(job).pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}, phrase


def test_live_human_video_call_is_not_a_recorded_video_application():
    """The policy explicitly permits live conversations with human interviewers over video."""
    job = _job(
        "Software Engineer",
        "The role: build backend services. Interview process: a 30 minute video call on Google "
        "Meet with two engineers, then a panel over Zoom.",
    )
    assert _outcome(job) == ScreenOutcome.ELIGIBLE.value
    assert "recorded-video" not in _rules(job)


# --------------------------------------------------------------------------------------------------
# Row 5 — AI interviewer vs AI in the product
# --------------------------------------------------------------------------------------------------
def test_ai_conducted_interview_is_excluded():
    for phrase in ("your first screen will be an interview with our AI interviewer",
                   "we use an AI-led interview for the first round",
                   "an automated AI screen precedes the human rounds"):
        job = _job("Software Engineer", f"Hiring process: {phrase}.")
        assert _outcome(job) == ScreenOutcome.PENDING_CHECK.value, phrase
        assert "ai-interview" in {h.rule_id for h in screen_job(job).pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}, phrase


def test_company_building_ai_is_not_an_ai_interview():
    job = _job(
        "Applied AI Engineer",
        "About us: we build an AI-powered platform. The role: you will integrate LLMs into "
        f"internal workflows. {PROCESS_OK}",
    )
    assert _outcome(job) == ScreenOutcome.ELIGIBLE.value
    assert "ai-interview" not in _rules(job)


# --------------------------------------------------------------------------------------------------
# Row 5 — location eligibility from New Hampshire
# --------------------------------------------------------------------------------------------------
def test_non_us_only_location_is_excluded():
    job = _job("Backend Engineer", f"You will build APIs. {PROCESS_OK}",
               location="Berlin, Germany", remote=RemoteMode.ONSITE)
    assert _outcome(job) == ScreenOutcome.EXCLUDED.value
    assert "location-eligibility" in _rules(job)


def test_us_remote_and_new_england_locations_are_eligible():
    for location in ("Remote, US", "Remote (US)", "Manchester, NH", "Boston, MA",
                     "United States", "Anywhere"):
        job = _job("Backend Engineer", f"You will build APIs. {PROCESS_OK}", location=location)
        assert _outcome(job) != ScreenOutcome.EXCLUDED.value, location


def test_missing_location_is_pending_not_assumed_in_either_direction():
    job = _job("Backend Engineer", f"You will build APIs. {PROCESS_OK}", location="",
               remote=RemoteMode.UNSPECIFIED)
    assert _outcome(job) == ScreenOutcome.PENDING_CHECK.value
    assert "location-eligibility" in _rules(job, "pending_checks")


def test_onsite_requirement_far_from_new_hampshire_is_excluded():
    job = _job(
        "Backend Engineer",
        "The role: you must be located in San Francisco and work on-site three days per week. "
        f"{PROCESS_OK}",
        location="San Francisco, CA", remote=RemoteMode.ONSITE,
    )
    assert _outcome(job) == ScreenOutcome.EXCLUDED.value
    assert "location-eligibility" in _rules(job)


def test_no_relocation_or_travel_commitment_is_invented():
    """The screener must not resolve a non-local role by assuming Brett would move."""
    job = _job("Backend Engineer", f"You will build APIs. {PROCESS_OK}",
               location="Austin, TX", remote=RemoteMode.UNSPECIFIED)
    result = screen_job(job)
    text = " ".join(h.reason for h in result.exclusions + result.pending_checks).lower()
    assert "relocat" not in text
    assert result.outcome in (ScreenOutcome.PENDING_CHECK.value, ScreenOutcome.EXCLUDED.value)


# --------------------------------------------------------------------------------------------------
# Row 5 — the rule that stops the system claiming an absence it never observed
# --------------------------------------------------------------------------------------------------
def test_truncated_aggregator_description_yields_an_explicit_pending_process_check():
    job = _job(
        "AI Automation Engineer", "Build internal automation for our...",
        verification=VerificationState.UNVERIFIED_LEAD,
        uncertainty=["aggregator_description_truncated"],
    )
    result = screen_job(job)
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value
    hit = next(h for h in result.pending_checks if h.rule_id == "process-not-inspectable")
    # It must say the absence has NOT been established, not that the role is clean.
    assert "has NOT been established" in hit.reason
    assert "video" in hit.reason and "AI-interview" in hit.reason


def test_a_posting_with_no_process_section_still_asks_for_a_form_inspection():
    job = _job("Software Engineer", "You will build Python services on AWS.")
    result = screen_job(job)
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value
    assert "process-not-inspectable" in {h.rule_id for h in result.pending_checks}


def test_screen_result_serializes_with_its_evidence():
    """A wrong exclusion must be diagnosable: every verdict carries the text that caused it."""
    job = _job("Software Engineer", "Requirements: an active TS/SCI clearance. " + PROCESS_OK)
    payload = screen_job(job).to_json()
    assert payload["outcome"] == ScreenOutcome.EXCLUDED.value
    hit = payload["exclusions"][0]
    assert hit["rule_id"] == "clearance-government"
    assert hit["matched_text"]
    assert hit["section"]
    assert payload["ruleset_version"]
