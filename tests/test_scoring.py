"""Scoring tests: determinism, evidence-linkage, UNKNOWN honesty."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.common.models import (
    Band,
    ChangeEvent,
    ChangeEventType,
    IdKind,
    SnapshotStatus,
)
from src.scoring.scoring import (
    ScoreContext,
    ScoringProfile,
    score_job,
    scorecard_to_stable_json,
)
from tests.conftest import FIXED_NOW, make_job

TODAY = datetime(2026, 7, 24, tzinfo=timezone.utc)


def _first_seen_event(job, at):
    return ChangeEvent(
        event_id=f"e-fs-{job.job_id}", event_type=ChangeEventType.FIRST_SEEN,
        source_id=job.source_id, job_id=job.job_id, run_id="d1", as_of=at,
        snapshot_id="snap-1",
    )


def _material_event(job, at, eid="e-mat-1"):
    return ChangeEvent(
        event_id=eid, event_type=ChangeEventType.MATERIALLY_CHANGED,
        source_id=job.source_id, job_id=job.job_id, run_id="d2", as_of=at,
        snapshot_id="snap-2",
    )


def _rich_ctx():
    job = make_job("a", description="python aws serverless machine learning platform")
    job.first_seen_at = FIXED_NOW - timedelta(days=10)
    job.provider_updated_at = FIXED_NOW
    events = [
        _first_seen_event(job, FIXED_NOW - timedelta(days=10)),
        _material_event(job, FIXED_NOW - timedelta(days=2)),
    ]
    return ScoreContext(
        job=job, events=events,
        recent_snapshot_statuses=[SnapshotStatus.SUCCESS, SnapshotStatus.SUCCESS, SnapshotStatus.SUCCESS],
        num_successful_observations=3,
    )


def test_determinism_byte_identical_rescoring():
    """T2: same events + same profile + pinned today -> byte-identical scorecards across two runs."""
    ctx = _rich_ctx()
    a = score_job(ctx, today=TODAY, profile=ScoringProfile())
    b = score_job(_rich_ctx(), today=TODAY, profile=ScoringProfile())
    assert scorecard_to_stable_json(a) == scorecard_to_stable_json(b)


def test_evidence_linkage_no_score_without_ref():
    """T3: every non-UNKNOWN dimension score carries >= 1 EvidenceRef."""
    card = score_job(_rich_ctx(), today=TODAY)
    for name in ("brett_fit", "freshness", "hiring_activity_evidence",
                 "repost_churn_pattern", "source_data_confidence", "application_priority"):
        dim = getattr(card, name)
        if dim.band != Band.UNKNOWN:
            assert dim.evidence_refs, f"{name} has a score but no evidence_refs"


def test_unknown_honesty_single_observation():
    """T6: a single-observation job yields UNKNOWN (not a middle default) for time-based dims."""
    job = make_job("solo", description="python role")
    job.first_seen_at = FIXED_NOW
    ctx = ScoreContext(
        job=job, events=[_first_seen_event(job, FIXED_NOW)],
        recent_snapshot_statuses=[SnapshotStatus.SUCCESS], num_successful_observations=1,
    )
    card = score_job(ctx, today=TODAY)
    assert card.freshness.band == Band.UNKNOWN
    assert card.freshness.score is None
    assert card.hiring_activity_evidence.band == Band.UNKNOWN
    assert card.repost_churn_pattern.band == Band.UNKNOWN
    # brett_fit is still computable from canonical fields
    assert card.brett_fit.band != Band.UNKNOWN


def test_content_hash_id_lowers_source_confidence():
    job = make_job("weak", id_kind=IdKind.CONTENT_HASH, identity_low_confidence=True)
    job.first_seen_at = FIXED_NOW - timedelta(days=5)
    ctx = ScoreContext(job=job, events=[_first_seen_event(job, FIXED_NOW - timedelta(days=5))],
                       recent_snapshot_statuses=[SnapshotStatus.SUCCESS, SnapshotStatus.PARTIAL],
                       num_successful_observations=2)
    card = score_job(ctx, today=TODAY)
    strong = make_job("strong", id_kind=IdKind.NATIVE_ID)
    strong.first_seen_at = FIXED_NOW - timedelta(days=5)
    strong_ctx = ScoreContext(job=strong, events=[_first_seen_event(strong, FIXED_NOW - timedelta(days=5))],
                              recent_snapshot_statuses=[SnapshotStatus.SUCCESS, SnapshotStatus.SUCCESS],
                              num_successful_observations=2)
    strong_card = score_job(strong_ctx, today=TODAY)
    assert card.source_data_confidence.score < strong_card.source_data_confidence.score


def test_weakest_link_composite_confidence():
    """Composite confidence = min of feeding confidences, not the average."""
    card = score_job(_rich_ctx(), today=TODAY)
    feeders = [card.brett_fit.confidence, card.freshness.confidence,
               card.hiring_activity_evidence.confidence, card.repost_churn_pattern.confidence,
               card.source_data_confidence.confidence]
    assert card.application_priority.confidence == min(feeders)


def test_agentic_applied_ai_role_scores_high():
    job = make_job(
        "agentic",
        title="Senior Agentic AI Engineer",
        description=(
            "Build multi-agent LLM systems with MCP, evaluation harnesses, Python, AWS Bedrock, "
            "tool use, orchestration, and backend APIs."
        ),
        location="Remote - United States",
        remote="remote",
    )
    card = score_job(ScoreContext(job=job), today=TODAY)
    assert card.brett_fit.band == Band.HIGH
    assert card.brett_fit.score >= 0.85
    assert card.excluded is False
    assert "agentic-ai" in card.brett_fit.detail["title_signals"]
    assert "mcp" in card.brett_fit.detail["skill_signals"]


def test_staff_title_remains_visible_but_ranks_below_equivalent_senior_role():
    description = "Build agentic LLM systems with MCP, Python, AWS, orchestration, and evals."
    senior = make_job(
        "senior", title="Senior AI Engineer", description=description,
        location="Remote - United States", remote="remote",
    )
    staff = make_job(
        "staff", title="Staff AI Engineer", description=description,
        location="Remote - United States", remote="remote",
    )
    senior_card = score_job(ScoreContext(job=senior), today=TODAY)
    staff_card = score_job(ScoreContext(job=staff), today=TODAY)
    assert staff_card.brett_fit.band == Band.HIGH
    assert staff_card.brett_fit.score < senior_card.brett_fit.score


def test_fit_terms_use_word_boundaries():
    """The strings retail/email/html must not accidentally count as AI or ML evidence."""
    job = make_job(
        "boundaries",
        title="Retail Platform Analyst",
        description="Maintain retail email templates written in HTML.",
        location="Remote",
        remote="remote",
    )
    card = score_job(ScoreContext(job=job), today=TODAY)
    assert card.brett_fit.score < ScoringProfile().brett_fit_floor
    assert "llms" not in card.brett_fit.detail["skill_signals"]
    assert card.excluded is True


def test_non_engineering_ai_role_is_excluded():
    job = make_job(
        "pm",
        title="Product Manager, AI Platform",
        description="Own an agentic LLM platform using MCP, Python, AWS, and evaluation tooling.",
        location="Remote - United States",
        remote="remote",
    )
    card = score_job(ScoreContext(job=job), today=TODAY)
    assert card.brett_fit.score == 0.0
    assert card.brett_fit.detail["blocked_role"] == 1
    assert card.excluded is True


def test_company_boilerplate_cannot_rescue_unrelated_engineering_title():
    job = make_job(
        "field-app",
        title="Field Application Engineer (Integrated Photonics)",
        description=(
            "Our AI company uses LLM agents, Python, AWS, MCP, orchestration, evals, and data pipelines."
        ),
        location="Remote - United States",
        remote="remote",
    )
    card = score_job(ScoreContext(job=job), today=TODAY)
    assert card.brett_fit.detail["blocked_title_lane"] == 1
    assert card.excluded is True


def test_presales_and_clearance_specific_roles_are_excluded():
    for key, title in (
        ("presales", "Staff Applied AI Engineer - Pre-Sales"),
        ("clearance", "Applied AI Engineer, Federal - Top Secret Clearance"),
    ):
        job = make_job(
            key,
            title=title,
            description="Build LLM agents with Python, MCP, AWS, and evaluation tooling.",
            location="Remote - United States",
            remote="remote",
        )
        card = score_job(ScoreContext(job=job), today=TODAY)
        assert card.brett_fit.detail["blocked_role"] == 1
        assert card.excluded is True


def test_specific_nonlocal_office_requires_remote_evidence():
    onsite = make_job(
        "palo-alto",
        title="Forward Deployed Engineer",
        description="Work with customers and build Python AI systems.",
        location="Palo Alto, California, United States",
    )
    remote = make_job(
        "austin-remote",
        title="AI Software Engineer",
        description="This role is available for remote work with occasional travel to Austin.",
        location="Austin, Texas, United States",
    )
    onsite_card = score_job(ScoreContext(job=onsite), today=TODAY)
    remote_card = score_job(ScoreContext(job=remote), today=TODAY)
    assert onsite_card.brett_fit.detail["blocked_geography"] == 1
    assert onsite_card.excluded is True
    assert remote_card.brett_fit.detail["blocked_geography"] == 0
    assert remote_card.excluded is False


def test_remote_role_restricted_to_canada_is_excluded():
    job = make_job(
        "canada",
        title="Agentic AI Engineer",
        description="Build LLM agents in Python on AWS.",
        location="Remote - Canada",
        remote="remote",
    )
    card = score_job(ScoreContext(job=job), today=TODAY)
    assert card.brett_fit.detail["blocked_geography"] == 1
    assert card.excluded is True


def test_remote_role_restricted_to_europe_is_excluded():
    job = make_job(
        "sweden",
        title="Backend Engineer - Platform | Sweden | Remote",
        description="Build a Python platform for LLM services and data pipelines.",
        location="Sweden (Remote)",
        remote="remote",
    )
    card = score_job(ScoreContext(job=job), today=TODAY)
    assert card.brett_fit.detail["blocked_geography"] == 1
    assert card.excluded is True
