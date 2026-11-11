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

from src.common.normalize import normalize_title_for_matching
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

SCORING_PROFILE_VERSION = "1.2.0"
FIT_RULESET_VERSION = "1.3.0"

# Per-dimension scorer versions (independent semver, stamped onto each emitted score).
_V = {
    "brett_fit": "1.3.0",
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
    # A research title is NOT inherently a better target than a software-engineering title
    # (SEARCH_PREFERENCES says so explicitly), and the September 23 clarification made getting hired
    # quickly the priority over an impressive title. Weighted accordingly.
    ("research-engineering", re.compile(r"\b(research engineer|research scientist)\b", re.I), 0.10),
    ("forward-deployed", re.compile(r"\bforward[- ]deployed engineer\b", re.I), 0.18),
    ("backend", re.compile(r"\b(back[- ]?end|api)\b", re.I), 0.18),
    ("platform", re.compile(r"\b(platform|infrastructure|developer experience|devex)\b", re.I), 0.18),
    ("automation", re.compile(r"\b(automation|workflow)\b", re.I), 0.18),
    ("data-engineering", re.compile(r"\b(data engineer|data platform)\b", re.I), 0.16),
    # Ordinary senior software engineering is a PRIMARY target, not a consolation lane. The old 0.14
    # was tuned when only AI-titled roles counted, and it left a legitimate full-stack internal-tools
    # role scoring 0.24 against a 0.25 exclusion floor.
    ("software-engineering", re.compile(r"\b(software engineer|software developer|full[- ]stack)\b", re.I), 0.22),
    # The plan's worked scenario lives here: ordinary titles that mean internal/business systems work.
    # Deliberately NARROW. "application engineer" was tried here and removed: it also matches
    # "Field Application Engineer (Integrated Photonics)", a customer-facing hardware role. An
    # ambiguous title belongs on the work-evidence recall path, where the description decides,
    # not in a title lane that grants credit before anything about the work is known.
    ("internal-tools", re.compile(
        r"\b(internal tools?|internal systems?|business systems?|business applications?|"
        r"integration developer|integration engineer|automation developer)\b",
        re.I), 0.20),
)

# Requirements that mark a specialist track Brett cannot substantiate in an interview. The plan lists
# "AI research requiring a specialist track record" as a false positive, and the workflow warns
# against converting experimental work into "years of independently mastered specialist production
# engineering". This is about the ROLE's stated bar, not about the title.
_SPECIALIST_BAR_RE = re.compile(
    r"\b(ph\.?d\.?|doctorate|publication record|published (?:papers|research)|"
    r"first[- ]author|peer[- ]reviewed publications?|research track record|"
    r"present at conferences|nips|neurips|icml|iclr|"
    r"(?:1[0-9]|[89])\+?\s*years)\b",
    re.I,
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
    r"people operations|human resources|business development)\b",
    re.I,
)
# A title word that says nothing reliable about the work. "Business Systems Analyst" and "Business
# Systems Engineer" were the same posting in the 2026-11-11 audit — first in-house software hire,
# founder access, Python/AWS internal platform — and the Analyst spelling scored 0.00 with
# `blocked_role` set while the Engineer spelling scored 0.41. An analyst title now blocks only when the
# role's own duties do not establish engineering work (`_ENGINEERING_DUTY_RE` below, plus a technical
# skill stated in role context). An analyst who reads dashboards is still blocked; one who builds and
# runs the company's software is evaluated on that work.
_DUTY_DEFERRED_TITLE_RE = re.compile(r"\b(analyst|analytics)\b", re.I)
# Engineering work stated as a duty: a BUILD verb and a software-system object. Deliberately stricter
# than screening's software-artifact guard — "own the roadmap", "design reports" and "maintain
# dashboards" are not engineering, and a bare "own" is product ownership as often as code ownership.
_ENGINEERING_DUTY_RE = re.compile(
    r"\b(?:build|building|develop|developing|implement|implementing|architect(?:ing)?|"
    r"writ(?:e|ing)|code|coding|program(?:ming)?|deploy(?:ing)?|ship(?:ping)?|"
    r"maintain(?:ing)?|integrat(?:e|ing)|automat(?:e|ing))\s+"
    r"(?:(?:and|&|or)\s+(?:own|run|maintain|operate|evolve|support)\s+)?"
    r"(?:[A-Za-z0-9\-+/&.]+\s+){0,4}"
    r"(?:software|applications?|apps?|services?|apis?|integrations?|platforms?|infrastructure|"
    r"pipelines?|internal tools?|tooling|backends?|systems?|code|codebase|automations?|agents?)\b",
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


# Sentences that describe the COMPANY rather than the ROLE. A description saying "our AI company uses
# LLM agents" is evidence about the employer's stack, not about what this job does — and the plan is
# explicit: "Do not elevate a role solely because the description repeats AI terms."
_COMPANY_FRAMING_RE = re.compile(
    r"(\bour\s+(?:ai\s+)?(?:company|team|platform|product|mission|clients?|customers?|technology|"
    r"stack)\b|\bwe\s+(?:are|use|build|believe|were\s+founded|have\s+built|help)\b|"
    r"\bfounded\s+in\b|\babout\s+(?:us|the\s+company)\b|\bjoin\s+(?:us|our)\b|"
    r"\bcompany\s+(?:uses|is\s+building)\b)",
    re.I,
)
# Sentences that describe what the PERSON will do. These carry real weight.
_ROLE_FRAMING_RE = re.compile(
    r"(\byou(?:'ll| will)?\s+(?:be\s+)?(?:build|design|own|develop|implement|create|deliver|lead|"
    r"work|integrate|automate|maintain|ship|architect)|\byour\s+(?:role|responsibilities|work)\b|"
    r"\bresponsibilities\b|\brequirements\b|\bqualifications\b|\bexperience\s+(?:with|in|building)\b|"
    r"\bmust\s+have\b|\bwe(?:'re| are)\s+looking\s+for\b|\bthe\s+role\b|\bin\s+this\s+role\b|"
    r"\bwhat\s+you(?:'ll| will)\s+do\b|\bskills?\b|\bproficien|\bfamiliarity\s+with\b)",
    re.I,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+|\n+")


def _split_role_vs_company(description: str) -> tuple[str, str]:
    """Split a description into (role-context text, company-context-only text).

    A sentence counts as role context when it describes the work or the requirements. A sentence that
    only describes the employer is company context. Unframed sentences default to ROLE context, so an
    ordinary unstructured posting is not penalized for lacking marketing language — the split exists
    to stop boilerplate from *earning* credit, not to demand a particular writing style.
    """
    if not description:
        return "", ""
    role_parts: list[str] = []
    company_parts: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(description):
        piece = sentence.strip()
        if not piece:
            continue
        is_company = bool(_COMPANY_FRAMING_RE.search(piece))
        is_role = bool(_ROLE_FRAMING_RE.search(piece))
        if is_company and not is_role:
            company_parts.append(piece)
        else:
            role_parts.append(piece)
    return " ".join(role_parts), " ".join(company_parts)


# How much a skill signal is worth when it appears ONLY in company boilerplate. Small but nonzero:
# an employer's stack is weak evidence about the role, not zero evidence.
_BOILERPLATE_SKILL_WEIGHT = 0.25


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
    # REPAIR 1 — title spelling. Patterns are matched against the NORMALIZED title, so an employer's
    # choice to write `FullStack` instead of `Full Stack` no longer changes the score. The live
    # defect: a Grafana posting titled `FullStack` scored 0.00 while the same role spelled
    # `Full Stack` scored 0.38, because every pattern required a separator.
    title_display = job.title or ""
    title = normalize_title_for_matching(title_display)
    description = job.description_text or ""
    title_signals: list[str] = []
    skill_signals: list[str] = []
    title_total = 0.0
    skill_total = 0.0
    for label, pattern, weight in _TITLE_SIGNALS:
        if pattern.search(title):
            title_total += weight
            title_signals.append(label)
    # Skill signals are weighted by CONTEXT. A term in "you will build X" is evidence about the role;
    # the same term in "our AI company uses X" is evidence about the employer. Without this split a
    # description that merely repeats AI vocabulary in its company blurb outranked a genuine
    # ordinary-title applied-AI role — measured at 0.69 versus 0.59 before the fix.
    role_text, company_text = _split_role_vs_company(description)
    role_skill_total = 0.0
    boilerplate_skill_total = 0.0
    for label, pattern, weight in _SKILL_SIGNALS:
        in_role = bool(pattern.search(role_text))
        in_company = bool(pattern.search(company_text))
        if in_role:
            role_skill_total += weight
            skill_signals.append(label)
        elif in_company:
            boilerplate_skill_total += weight
            skill_signals.append(f"{label}(company-blurb)")
    skill_total = role_skill_total + _BOILERPLATE_SKILL_WEIGHT * boilerplate_skill_total

    technical_title = bool(_TECHNICAL_TITLE_RE.search(title))
    duty_deferred_title = bool(_DUTY_DEFERRED_TITLE_RE.search(title)) and not technical_title
    engineering_duties = bool(_ENGINEERING_DUTY_RE.search(role_text)) and role_skill_total > 0
    # The title stands in for the work only when the work is not stated. When it is, the work decides.
    duty_established_title = duty_deferred_title and engineering_duties
    blocked_role = (
        (bool(_NON_TARGET_TITLE_RE.search(title)) and not technical_title)
        or (duty_deferred_title and not engineering_duties)
        or bool(_BLOCKED_TECH_TITLE_RE.search(title))
    )
    geography, geography_adjustment, geography_blocked = _geography(job)

    # REPAIR 2 — the title-only hard zero is gone.
    #
    # `blocked_title_lane = not title_signals` used to force the score to 0.0 whenever no title
    # pattern matched, which erased every novel or ordinary title regardless of the work described.
    # The plan requires work-based recall and states that "a title-only empty-match gate cannot
    # silently remove them", and the acceptance case is an ordinary title doing real applied-AI work.
    #
    # Replacement: when the title carries no recognized lane but IS technical and the description
    # shows real work signals, the work itself earns credit at reduced confidence. Exclusions still
    # zero the score — but those are verified facts about the role, not guesses about a title.
    recall_path = "title-signal"
    work_based_credit = 0.0
    if not title_signals:
        # The credit derives from ROLE-context skill only. Boilerplate cannot buy a recall path: that
        # is what let an unrelated engineering title ride in on a company AI blurb.
        if (technical_title or duty_established_title) and role_skill_total > 0:
            # Capped below the strong-title band: this is genuine eligibility, not a promise.
            work_based_credit = min(0.20, role_skill_total * 0.6)
            recall_path = "work-evidence"
        elif role_skill_total > 0:
            work_based_credit = min(0.08, role_skill_total * 0.3)
            recall_path = "work-evidence-nontechnical-title"
        else:
            recall_path = "no-signal"

    total = (
        min(0.55, title_total)
        + min(0.40, skill_total)
        + work_based_credit
        + geography_adjustment
    )
    seniority_adjustment = 0.0
    if _MANAGEMENT_TITLE_RE.search(title):
        seniority_adjustment = -0.20
    elif _STRETCH_TITLE_RE.search(title):
        # A Staff/Principal title is a STRETCH label, not a rejection: the policy says "Do not reject
        # Staff or architect roles merely because of the title." A small adjustment keeps ordinary
        # senior roles ahead without removing the stretch from consideration.
        seniority_adjustment = -0.08
    total += seniority_adjustment

    # A stated specialist bar lowers the score without removing the role: the policy says to label
    # credible stretches honestly rather than to hide them.
    specialist_bar = bool(_SPECIALIST_BAR_RE.search(description))
    specialist_adjustment = -0.15 if specialist_bar else 0.0
    total += specialist_adjustment

    if blocked_role or geography_blocked:
        total = 0.0

    score = _clamp(total)
    # Confidence reflects how much evidence the score rests on. A work-evidence match with no title
    # lane is real but weaker, and says so rather than borrowing the confidence of a title match.
    if not job.description_text:
        confidence = 0.5
    elif recall_path.startswith("work-evidence"):
        confidence = 0.7
    else:
        confidence = 1.0
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
            "title_deferred_to_duties": int(duty_established_title),
            "blocked_geography": int(geography_blocked),
            "recall_path": recall_path,
            "normalized_title": title,
            "title_signal_score": round(min(0.55, title_total), 3),
            "skill_signal_score": round(min(0.40, skill_total), 3),
            "role_context_skill_score": round(role_skill_total, 3),
            "company_blurb_skill_score": round(boilerplate_skill_total, 3),
            "work_based_credit": round(work_based_credit, 3),
            "seniority_adjustment": seniority_adjustment,
            "specialist_bar_adjustment": specialist_adjustment,
            "states_specialist_bar": int(specialist_bar),
            "is_stretch_level": int(bool(_STRETCH_TITLE_RE.search(title))),
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
