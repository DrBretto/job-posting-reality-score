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

import re
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

SCORING_PROFILE_VERSION = "1.1.0"
FIT_RULESET_VERSION = "1.1.0"

# Per-dimension scorer versions (independent semver, stamped onto each emitted score).
_V = {
    "brett_fit": "1.1.0",
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
    brett_fit_floor: float = 0.25
    # freshness decay horizon (days)
    freshness_horizon_days: int = 180
    # min successful observations before freshness/hiring/churn are assessable
    min_observations: int = 2


# Fit is intentionally role-first. A generic job description can mention AI, data, Python, or an
# engineering team without making the actual role relevant. Title signals establish the lane; skill
# signals then distinguish Brett's strongest applied-AI, agentic, backend, and AWS work.
_TITLE_SIGNALS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("agentic-ai", re.compile(r"\b(agentic|ai agents?|agent systems?|multi[- ]agent)\b", re.I), 0.30),
    ("applied-ai", re.compile(r"\b(applied ai|generative ai|genai|ai engineer|llm engineer)\b", re.I), 0.28),
    ("ai-focus", re.compile(r"\b(ai|artificial intelligence|ml|llm)\b", re.I), 0.18),
    ("machine-learning", re.compile(r"\b(machine learning|ml engineer|data scientist)\b", re.I), 0.24),
    ("research-engineering", re.compile(r"\b(research engineer|research scientist)\b", re.I), 0.20),
    ("forward-deployed", re.compile(r"\bforward[- ]deployed engineer\b", re.I), 0.18),
    ("backend", re.compile(r"\b(back[- ]?end|api)\b", re.I), 0.18),
    ("platform", re.compile(r"\b(platform|infrastructure|developer experience|devex)\b", re.I), 0.18),
    ("automation", re.compile(r"\b(automation|workflow)\b", re.I), 0.18),
    ("data-engineering", re.compile(r"\b(data engineer|data platform)\b", re.I), 0.16),
    ("software-engineering", re.compile(r"\b(software engineer|software developer|full[- ]stack)\b", re.I), 0.14),
)

_SKILL_SIGNALS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("agents", re.compile(r"\b(agentic|ai agents?|agent systems?|multi[- ]agent|tool[- ]using)\b", re.I), 0.12),
    ("mcp", re.compile(r"\b(model context protocol|mcp)\b", re.I), 0.10),
    ("llms", re.compile(r"\b(llms?|large language models?|generative ai|genai)\b", re.I), 0.09),
    ("evals", re.compile(r"\b(evals?|evaluation harness|model evaluation)\b", re.I), 0.07),
    ("retrieval", re.compile(r"\b(rag|retrieval[- ]augmented|semantic search|vector (database|store))\b", re.I), 0.06),
    ("python", re.compile(r"\bpython\b", re.I), 0.08),
    ("aws-serverless", re.compile(r"\b(aws|amazon web services|bedrock|lambda|serverless|step functions?)\b", re.I), 0.08),
    ("orchestration", re.compile(r"\b(orchestrat(?:e|ion)|workflow engine|structured outputs?)\b", re.I), 0.07),
    ("typescript-node", re.compile(r"\b(typescript|node(?:\.js|js)?)\b", re.I), 0.05),
    ("apis-backend", re.compile(r"\b(apis?|back[- ]?end|microservices?)\b", re.I), 0.05),
    ("data-pipelines", re.compile(r"\b(data pipelines?|etl|elt)\b", re.I), 0.04),
)

_TECHNICAL_TITLE_RE = re.compile(
    r"\b(engineer|developer|architect|scientist|devops|sre|site reliability|technical)\b", re.I
)
_NON_TARGET_TITLE_RE = re.compile(
    r"\b(account executive|sales|marketing|recruit(?:er|ing)|talent|customer success|"
    r"product manager|program manager|project manager|finance|legal|counsel|designer|"
    r"people operations|human resources|business development|analyst)\b",
    re.I,
)
_MANAGEMENT_TITLE_RE = re.compile(r"\b(manager|director|head of|vice president|vp)\b", re.I)
_STRETCH_TITLE_RE = re.compile(r"\b(staff|principal|distinguished)\b", re.I)
_BLOCKED_TECH_TITLE_RE = re.compile(
    r"\b(pre[- ]sales|sales engineer|top secret|ts/sci|security clearance)\b", re.I
)

_LOCAL_LOCATION_RE = re.compile(
    r"\b(new hampshire|nh|massachusetts|ma|boston|cambridge|waltham|lowell|andover|"
    r"portsmouth|manchester|nashua|concord)\b",
    re.I,
)
_US_ELIGIBLE_RE = re.compile(
    r"\b(united states|u\.?s\.?a?|north america|anywhere|global)\b", re.I
)
_NON_US_RE = re.compile(
    r"\b(canada|united kingdom|uk|europe|emea|ireland|sweden|netherlands|germany|france|"
    r"spain|portugal|poland|italy|belgium|denmark|norway|finland|switzerland|austria|"
    r"czechia|czech republic|romania|serbia|croatia|greece|hungary|bulgaria|estonia|"
    r"latvia|lithuania|ukraine|israel|south africa|india|singapore|japan|australia|"
    r"new zealand|latin america|latam|mexico|brazil|argentina|colombia|chile|peru)\b",
    re.I,
)
_REMOTE_BODY_RE = re.compile(
    r"\b(location\s*:?\s*remote|available for remote work|remote role|fully remote|remote-first|"
    r"work remotely|home-based|distributed team)\b",
    re.I,
)
_US_WIDE_ONLY_RE = re.compile(r"^(united states|us|usa|u\.s\.)$", re.I)


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


def _geography(job: CanonicalJob) -> tuple[str, float, bool]:
    """Return (classification, adjustment, ineligible) for Brett's remote/NH/MA search."""
    location = f"{job.raw_location or ''} {job.canonical_location}".strip()
    local = bool(_LOCAL_LOCATION_RE.search(location))
    us_eligible = bool(_US_ELIGIBLE_RE.search(location))
    says_remote = bool(re.search(r"\bremote\b", location, re.I))
    non_us = bool(_NON_US_RE.search(location))
    body_remote = bool(_REMOTE_BODY_RE.search(job.description_text or ""))
    effective_remote = job.remote_hybrid_language.value == "REMOTE" or says_remote or body_remote

    if effective_remote:
        if non_us and not us_eligible:
            return "remote-outside-us", 0.0, True
        return "remote-compatible", 0.05, False
    if local:
        return "nh-ma-compatible", 0.05, False
    if job.remote_hybrid_language.value in ("HYBRID", "ONSITE"):
        return "nonlocal-hybrid-or-onsite", 0.0, True
    if non_us and not us_eligible:
        return "outside-us", 0.0, True
    canonical = (job.canonical_location or "").strip()
    if canonical and _US_WIDE_ONLY_RE.fullmatch(canonical):
        return "us-wide-location", -0.03, False
    if location:
        return "nonlocal-location-without-remote-evidence", 0.0, True
    return "location-compatible-or-unspecified", 0.0, False


# --------------------------------------------------------------------------------------------------
# Dimension scorers
# --------------------------------------------------------------------------------------------------
def score_brett_fit(ctx: ScoreContext, profile: ScoringProfile) -> DimensionScore:
    job = ctx.job
    title = job.title or ""
    description = job.description_text or ""
    title_signals: list[str] = []
    skill_signals: list[str] = []
    title_total = 0.0
    skill_total = 0.0
    for label, pattern, weight in _TITLE_SIGNALS:
        if pattern.search(title):
            title_total += weight
            title_signals.append(label)
    for label, pattern, weight in _SKILL_SIGNALS:
        if pattern.search(description):
            skill_total += weight
            skill_signals.append(label)

    technical_title = bool(_TECHNICAL_TITLE_RE.search(title))
    blocked_role = (
        (bool(_NON_TARGET_TITLE_RE.search(title)) and not technical_title)
        or bool(_BLOCKED_TECH_TITLE_RE.search(title))
    )
    blocked_title_lane = not title_signals
    geography, geography_adjustment, geography_blocked = _geography(job)
    # Overlapping phrases (for example "agentic AI engineer") are evidence of one strong lane, not
    # three independent careers. Caps prevent overlap from erasing seniority/location adjustments.
    total = min(0.55, title_total) + min(0.40, skill_total) + geography_adjustment
    seniority_adjustment = 0.0
    if _MANAGEMENT_TITLE_RE.search(title):
        seniority_adjustment = -0.20
    elif _STRETCH_TITLE_RE.search(title):
        seniority_adjustment = -0.08
    total += seniority_adjustment
    if blocked_role or blocked_title_lane or geography_blocked:
        total = 0.0

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
        detail={
            "title_signals": ",".join(sorted(title_signals)),
            "skill_signals": ",".join(sorted(skill_signals)),
            "geography": geography,
            "blocked_role": int(blocked_role),
            "blocked_title_lane": int(blocked_title_lane),
            "blocked_geography": int(geography_blocked),
            "title_signal_score": round(min(0.55, title_total), 3),
            "skill_signal_score": round(min(0.40, skill_total), 3),
            "seniority_adjustment": seniority_adjustment,
            "ruleset_version": FIT_RULESET_VERSION,
        },
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
