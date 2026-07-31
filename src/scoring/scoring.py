"""Deterministic scoring (SCORING_AND_EVIDENCE_SPEC).

Six independently-inspectable dimensions, each emitting {score, band, confidence, evidence_refs[],
version}. There is NO single opaque number: `application_priority` is a fully decomposable combiner.

Hard rules honored here:
  - UNKNOWN is first-class: a dimension without sufficient evidence says UNKNOWN, it never defaults
    to a middle number.
  - Evidence-linkage: every non-UNKNOWN dimension score carries >= 1 EvidenceRef.
  - Composite confidence = weakest-link min (not average).
  - Determinism: given the same events + same profile version + pinned `today`, scores are
    byte-reproducible. `today` is injected, never read from wall-clock.
  - The LLM never sets any score, band, or confidence (this module imports no LLM).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.common.models import (
    Band,
    CanonicalJob,
    ChangeEvent,
    ChangeEventType,
    DimensionScore,
    DimensionScorecard,
    EvidenceKind,
    EvidenceRef,
    IdKind,
    SnapshotStatus,
)

SCORING_PROFILE_VERSION = "1.0.0"
FIT_RULESET_VERSION = "1.0.0"

# Per-dimension scorer versions (independent semver, stamped onto each emitted score).
_V = {
    "brett_fit": "1.0.0",
    "freshness": "1.0.0",
    "hiring_activity_evidence": "1.0.0",
    "repost_churn_pattern": "1.0.0",
    "source_data_confidence": "1.0.0",
    "application_priority": "1.0.0",
}


@dataclass(frozen=True)
class ScoringProfile:
    version: str = SCORING_PROFILE_VERSION
    # application_priority weights (SCORING §2)
    w_brett_fit: float = 0.40
    w_hiring_activity: float = 0.25
    w_freshness: float = 0.20
    w_repost_churn: float = -0.10   # churn DECREASES priority (never brands the job fake)
    w_source_confidence: float = 0.05
    # bands
    band_high: float = 0.70
    band_medium: float = 0.40
    # exclusions
    brett_fit_floor: float = 0.20
    # freshness decay horizon (days)
    freshness_horizon_days: int = 180
    # min successful observations before freshness/hiring/churn are assessable
    min_observations: int = 2


# fit_ruleset (versioned): deterministic keyword weights over canonical title + description.
_FIT_KEYWORDS: dict[str, float] = {
    "python": 0.15,
    "aws": 0.15,
    "serverless": 0.10,
    "lambda": 0.10,
    "machine learning": 0.20,
    "ml": 0.10,
    "llm": 0.15,
    "ai": 0.15,
    "automation": 0.15,
    "data": 0.10,
    "backend": 0.10,
    "engineer": 0.10,
    "platform": 0.08,
    "infrastructure": 0.08,
}


@dataclass
class ScoreContext:
    """Everything a scorer may read — all from stored evidence, never a live fetch."""

    job: CanonicalJob
    events: list[ChangeEvent] = field(default_factory=list)     # this job's history
    recent_snapshot_statuses: list[SnapshotStatus] = field(default_factory=list)
    num_successful_observations: int = 1


def _band(score: float, profile: ScoringProfile) -> Band:
    if score >= profile.band_high:
        return Band.HIGH
    if score >= profile.band_medium:
        return Band.MEDIUM
    return Band.LOW


def _clamp(v: float) -> float:
    return round(max(0.0, min(1.0, v)), 6)


def _unknown(version: str) -> DimensionScore:
    return DimensionScore(score=None, band=Band.UNKNOWN, confidence=0.2, evidence_refs=[], version=version)


def _canonical_field_ref(job_id: str, field_name: str, as_of: datetime | None) -> EvidenceRef:
    return EvidenceRef(kind=EvidenceKind.CANONICAL_FIELD, ref_id=f"{job_id}#{field_name}", as_of=as_of)


# --------------------------------------------------------------------------------------------------
# Dimension scorers
# --------------------------------------------------------------------------------------------------
def score_brett_fit(ctx: ScoreContext, profile: ScoringProfile) -> DimensionScore:
    job = ctx.job
    hay = f"{job.title}\n{job.description_text}".lower()
    matched: list[str] = []
    total = 0.0
    for kw, w in _FIT_KEYWORDS.items():
        if kw in hay:
            total += w
            matched.append(kw)
    score = _clamp(total)
    # confidence: full text available => confident; title-only => half
    confidence = 1.0 if job.description_text else 0.5
    refs = [
        _canonical_field_ref(job.job_id, "title", job.last_seen_at),
        _canonical_field_ref(job.job_id, "description_text", job.last_seen_at),
    ]
    return DimensionScore(
        score=score, band=_band(score, profile), confidence=confidence,
        evidence_refs=refs, version=_V["brett_fit"],
        detail={"matched_keywords": ",".join(sorted(matched)), "ruleset_version": FIT_RULESET_VERSION},
    )


def _first_seen_event(ctx: ScoreContext) -> ChangeEvent | None:
    for e in ctx.events:
        if e.event_type == ChangeEventType.FIRST_SEEN:
            return e
    return None


def _material_change_events(ctx: ScoreContext) -> list[ChangeEvent]:
    kinds = {
        ChangeEventType.MATERIALLY_CHANGED,
        ChangeEventType.SALARY_CHANGED,
        ChangeEventType.LOCATION_CHANGED,
        ChangeEventType.REMOTE_HYBRID_LANGUAGE_CHANGED,
    }
    return [e for e in ctx.events if e.event_type in kinds]


def score_freshness(ctx: ScoreContext, profile: ScoringProfile, *, today: datetime) -> DimensionScore:
    job = ctx.job
    if ctx.num_successful_observations < profile.min_observations or job.first_seen_at is None:
        # one observation cannot establish change-recency -> UNKNOWN, not a middle default
        return _unknown(_V["freshness"])
    changes = _material_change_events(ctx)
    last_change_at = max((e.as_of for e in changes), default=job.first_seen_at)
    days_since_change = max(0, (today - last_change_at).days)
    score = _clamp(1.0 - days_since_change / profile.freshness_horizon_days)
    refs: list[EvidenceRef] = []
    fs = _first_seen_event(ctx)
    if fs:
        refs.append(EvidenceRef(kind=EvidenceKind.SNAPSHOT, ref_id=fs.snapshot_id, as_of=fs.as_of))
    if changes:
        newest = max(changes, key=lambda e: e.as_of)
        refs.append(EvidenceRef(kind=EvidenceKind.CHANGE_EVENT, ref_id=newest.event_id, as_of=newest.as_of))
    if not refs:  # guarantee linkage for a non-UNKNOWN score
        refs.append(_canonical_field_ref(job.job_id, "first_seen_at", job.first_seen_at))
    return DimensionScore(
        score=score, band=_band(score, profile), confidence=0.9,
        evidence_refs=refs, version=_V["freshness"],
        detail={"days_since_last_material_change": days_since_change,
                "days_since_first_seen": max(0, (today - job.first_seen_at).days)},
    )


def score_hiring_activity(ctx: ScoreContext, profile: ScoringProfile, *, today: datetime) -> DimensionScore:
    if ctx.num_successful_observations < profile.min_observations:
        return _unknown(_V["hiring_activity_evidence"])
    changes = _material_change_events(ctx)
    n = len(changes)
    updated_signal = 0.3 if ctx.job.provider_updated_at is not None else 0.0
    score = _clamp(0.2 * n + updated_signal)
    refs = [EvidenceRef(kind=EvidenceKind.CHANGE_EVENT, ref_id=e.event_id, as_of=e.as_of) for e in changes]
    if not refs:
        fs = _first_seen_event(ctx)
        if fs:
            refs.append(EvidenceRef(kind=EvidenceKind.SNAPSHOT, ref_id=fs.snapshot_id, as_of=fs.as_of))
        else:
            refs.append(_canonical_field_ref(ctx.job.job_id, "provider_updated_at", ctx.job.last_seen_at))
    return DimensionScore(
        score=score, band=_band(score, profile), confidence=0.85,
        evidence_refs=refs, version=_V["hiring_activity_evidence"],
        detail={"material_change_events": n, "has_provider_updated_at": int(updated_signal > 0)},
    )


def score_repost_churn(ctx: ScoreContext, profile: ScoringProfile) -> DimensionScore:
    if ctx.num_successful_observations < profile.min_observations:
        return _unknown(_V["repost_churn_pattern"])
    reposts = [e for e in ctx.events if e.event_type == ChangeEventType.PROBABLE_REPOST]
    cycles = [e for e in ctx.events if e.event_type in (ChangeEventType.DISAPPEARED, ChangeEventType.RETURNED)]
    churn_events = reposts + cycles
    # score = churn INTENSITY (high = more churn); profile subtracts it from priority.
    score = _clamp(0.34 * len(churn_events))
    refs = [EvidenceRef(kind=EvidenceKind.CHANGE_EVENT, ref_id=e.event_id, as_of=e.as_of) for e in churn_events]
    if not refs:
        # no churn observed is itself an evidenced finding (the job's clean history)
        fs = _first_seen_event(ctx)
        ref_id = fs.event_id if fs else f"{ctx.job.job_id}#no-churn"
        refs.append(EvidenceRef(kind=EvidenceKind.CHANGE_EVENT if fs else EvidenceKind.CANONICAL_FIELD,
                                ref_id=ref_id, as_of=ctx.job.last_seen_at))
    return DimensionScore(
        score=score, band=_band(score, profile), confidence=0.85,
        evidence_refs=refs, version=_V["repost_churn_pattern"],
        detail={"repost_links": len(reposts), "disappear_return_events": len(cycles)},
    )


def score_source_data_confidence(ctx: ScoreContext, profile: ScoringProfile) -> DimensionScore:
    job = ctx.job
    score = 1.0
    if job.id_kind == IdKind.CONTENT_HASH or job.identity_low_confidence:
        score -= 0.4
    elif job.id_kind == IdKind.URL_SLUG:
        score -= 0.1
    bad = sum(1 for s in ctx.recent_snapshot_statuses
              if s in (SnapshotStatus.PARTIAL, SnapshotStatus.FETCH_FAILED))
    score -= 0.15 * bad
    if ctx.num_successful_observations < profile.min_observations:
        score -= 0.2
    score = _clamp(score)
    refs = [_canonical_field_ref(job.job_id, "id_kind", job.last_seen_at)]
    for e in ctx.events:
        if e.event_type in (ChangeEventType.SOURCE_FETCH_FAILED,
                            ChangeEventType.SOURCE_RESPONSE_PARTIAL,
                            ChangeEventType.SOURCE_SUSPECT):
            refs.append(EvidenceRef(kind=EvidenceKind.CHANGE_EVENT, ref_id=e.event_id, as_of=e.as_of))
    return DimensionScore(
        score=score, band=_band(score, profile), confidence=0.95,
        evidence_refs=refs, version=_V["source_data_confidence"],
        detail={"id_kind": job.id_kind.value, "degraded_snapshots": bad,
                "successful_observations": ctx.num_successful_observations},
    )


def score_application_priority(
    parts: dict[str, DimensionScore], profile: ScoringProfile
) -> DimensionScore:
    """Deterministic combiner. Fully decomposable; still shown alongside its parts."""
    brett = parts["brett_fit"]
    # cannot rank without a fit signal
    if brett.band == Band.UNKNOWN or brett.score is None:
        ds = _unknown(_V["application_priority"])
        # weakest-link confidence still recorded
        ds.confidence = min(p.confidence for p in parts.values())
        ds.evidence_refs = list(brett.evidence_refs[:1])
        return ds

    def sv(name: str) -> float:
        s = parts[name].score
        return s if s is not None else 0.0

    raw = (
        profile.w_brett_fit * sv("brett_fit")
        + profile.w_hiring_activity * sv("hiring_activity_evidence")
        + profile.w_freshness * sv("freshness")
        + profile.w_repost_churn * sv("repost_churn_pattern")
        + profile.w_source_confidence * sv("source_data_confidence")
    )
    # normalize by the max achievable positive weight so the band thresholds stay meaningful
    max_pos = profile.w_brett_fit + profile.w_hiring_activity + profile.w_freshness + profile.w_source_confidence
    score = _clamp(raw / max_pos)
    confidence = min(p.confidence for p in parts.values())  # weakest-link
    refs: list[EvidenceRef] = []
    for p in parts.values():
        refs.extend(p.evidence_refs[:1])
    return DimensionScore(
        score=score, band=_band(score, profile), confidence=confidence,
        evidence_refs=refs, version=_V["application_priority"],
        detail={"weakest_link_confidence": confidence},
    )


def score_job(
    ctx: ScoreContext,
    *,
    today: datetime,
    profile: ScoringProfile | None = None,
) -> DimensionScorecard:
    profile = profile or ScoringProfile()
    parts = {
        "brett_fit": score_brett_fit(ctx, profile),
        "freshness": score_freshness(ctx, profile, today=today),
        "hiring_activity_evidence": score_hiring_activity(ctx, profile, today=today),
        "repost_churn_pattern": score_repost_churn(ctx, profile),
        "source_data_confidence": score_source_data_confidence(ctx, profile),
    }
    parts["application_priority"] = score_application_priority(parts, profile)

    excluded = False
    reason = None
    if parts["brett_fit"].score is not None and parts["brett_fit"].score < profile.brett_fit_floor:
        excluded, reason = True, f"brett_fit {parts['brett_fit'].score} below floor {profile.brett_fit_floor}"
    if parts["source_data_confidence"].band == Band.UNKNOWN:
        reason = (reason or "") + "; source confidence UNKNOWN (insufficient record)"

    return DimensionScorecard(
        source_id=ctx.job.source_id,
        job_id=ctx.job.job_id,
        brett_fit=parts["brett_fit"],
        freshness=parts["freshness"],
        hiring_activity_evidence=parts["hiring_activity_evidence"],
        repost_churn_pattern=parts["repost_churn_pattern"],
        source_data_confidence=parts["source_data_confidence"],
        application_priority=parts["application_priority"],
        scoring_profile_version=profile.version,
        scored_as_of=today,
        excluded=excluded,
        exclusion_reason=reason,
    )


def scorecard_to_stable_json(card: DimensionScorecard) -> str:
    """Byte-stable serialization for determinism assertions (sorted keys)."""
    import json

    return json.dumps(card.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), default=str)
