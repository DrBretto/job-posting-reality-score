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
