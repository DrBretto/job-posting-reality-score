"""The candidate-policy projection.

`APPLICATION_WORKFLOW.md` and its four companion files in the sibling Infotropy repository are the
single authority for candidate screening. This run does not edit them and must not fork them.

Two constraints pull against each other:

  1. "Do not ... create another prose policy that can drift from them."
  2. Production is a Lambda. `../Infotropy Book` does not exist there.

The resolution is a *projection*, not a copy. The screening rules live in `screening.py` as reviewed,
tested, deterministic code. This module records, for each rule, which policy source it was mapped
from — plus every source's content hash. Nothing here restates the policy in prose, so there is no
second document to drift; what it can detect is that a source CHANGED, at which point the run says
the projection is stale instead of silently screening against yesterday's policy.

Privacy boundary: the projection stores screening criteria and hashes only. The master resume,
contact details, personal circumstances and the reasoning behind preferences never enter it, never
reach a provider, and never appear in fixtures, logs or reports.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

PROJECTION_VERSION = "1.2.0"
DEFAULT_PROJECTION_PATH = "config/candidate_policy.json"

# The five central sources, relative to this repository's parent directory. These paths are used ONLY
# by the local refresh command; production reads the committed projection.
POLICY_SOURCE_PATHS: tuple[tuple[str, str], ...] = (
    ("workflow", "../Infotropy Book/INBOX/Employment Search/APPLICATION_WORKFLOW.md"),
    ("preferences", "../Infotropy Book/INBOX/Employment Search/SEARCH_PREFERENCES.md"),
    ("operating_plan", "../Infotropy Book/INBOX/Employment Search/OPERATING_PLAN.md"),
    ("candidate_facts", "../Infotropy Book/INBOX/Employment Search/CANDIDATE_FACTS.md"),
    (
        "master_resume",
        "../Infotropy Book/career-factory/outputs/candidates/brett-westerlund/"
        "master-resume/MASTER_RESUME.latest.md",
    ),
)

# Which source each screening rule was mapped from. This is the "reviewed policy mapping" the plan
# asks for: it makes the derivation auditable without duplicating the policy text.
RULE_SOURCE_MAP: dict[str, tuple[str, ...]] = {
    "sales-ownership": ("workflow", "preferences", "operating_plan"),
    # 2026-09-26: "Adjacent roles: software problem-solving, not customer service". The workflow
    # file carries the clarification and the Screen Before Preparing line; the operating plan
    # keeps older customer-service experience as communication evidence, never a target lane.
    "customer-service-queue": ("workflow", "operating_plan"),
    "clearance-government": ("workflow", "preferences", "operating_plan"),
    "frontend-specialist": ("workflow", "preferences"),
    "recorded-video": ("workflow",),
    "ai-interview": ("workflow",),
    "location-eligibility": ("workflow", "preferences"),
    # Emitted by the same location logic; it was missing from this map, so the projection did
    # not record its derivation. Noted in this run's independent review.
    "location-residency": ("workflow", "preferences"),
    "process-not-inspectable": ("workflow",),
    # 2026-09-28: "Broad ownership and first/sole-engineer preference". Not an exclusion — the only
    # entry here that RETAINS rather than rejects. The workflow section says to keep eligible
    # broad-ownership roles available for review "even when an AI-oriented keyword score is low",
    # and `src/candidate/ownership.py` plus the report's retention path are what implement it. It is
    # mapped here for the same reason every exclusion is: so a change to the source shows up as a
    # stale projection rather than as screening that quietly means something else.
    "broad-ownership-retention": ("workflow",),
    # 2026-11-11 (PKT-CAREER-RADAR-END-TO-END-REPAIR-V1): the human-first rule (workflow, 10-12)
    # now HOLDS recorded-video / AI-interview / pre-interview evaluations rather than excluding
    # them; the voice/telephony exclusion is the workflow's 10-17 section.
    "pre-interview-evaluation": ("workflow",),
    "voice-telephony": ("workflow", "preferences"),
    # Packet-stated boundary for the funded-small-company search, carried by the operating plan's
    # objective (money and a job) and the workflow's contract/continuity sections.
    "no-cash-pay": ("workflow", "operating_plan"),
    "ai-training-only": ("workflow",),
}

# Calibration knobs, mapped from Target Calibration. Orientations, never gates — the plan is explicit
# that ~$150K is "a useful compensation target, not a minimum, maximum, or exact band".
CALIBRATION: dict[str, object] = {
    "compensation_orientation_usd": 150_000,
    "compensation_is_a_gate": False,
    "years_competitive_low": 5,
    "years_competitive_high": 7,
    "applied_ai_is_advantage_not_requirement": True,
    "staff_or_architect_title_is_blanket_rejection": False,
    "pay_above_orientation_is_blanket_rejection": False,
    "adjacent_learnable_skill_equals_unmet_requirement": False,
    "home_state": "NH",
}


class PolicySourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    path: str
    sha256: str
    bytes: int
    modified_at: datetime | None = None


class CandidatePolicyProjection(BaseModel):
    """Versioned projection of the central policy. Committed; read by production."""

    model_config = ConfigDict(extra="forbid")
    projection_version: str = PROJECTION_VERSION
    built_at: datetime
    sources: list[PolicySourceRef] = Field(default_factory=list)
    rule_source_map: dict[str, list[str]] = Field(default_factory=dict)
    calibration: dict = Field(default_factory=dict)
    note: str = (
        "Projection of the central candidate policy. The authority is the source files listed "
        "here; the screening rules are code in src/candidate/screening.py. This file intentionally "
        "contains NO policy prose and NO personal data — only source hashes, the rule-to-source "
        "mapping, and calibration orientations."
    )

    def source(self, key: str) -> PolicySourceRef | None:
        for ref in self.sources:
            if ref.key == key:
                return ref
        return None


class PolicyDivergence(BaseModel):
    """What changed between the committed projection and the live sources."""

    model_config = ConfigDict(extra="forbid")
    checked_at: datetime
    sources_available: bool
    changed: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)

    @property
    def diverged(self) -> bool:
        return bool(self.changed or self.missing)

    def summary(self) -> str:
        if not self.sources_available:
            return (
                "policy sources not reachable from here (expected in production: the sibling "
                "repository is not deployed); screening used the committed projection"
            )
        if not self.diverged:
            return "projection matches all policy sources"
        parts = []
        if self.changed:
            parts.append("changed since the projection was built: " + ", ".join(sorted(self.changed)))
        if self.missing:
            parts.append("not found at the recorded path: " + ", ".join(sorted(self.missing)))
        return "; ".join(parts)


def _hash_file(path: Path) -> tuple[str, int, datetime]:
    raw = path.read_bytes()
    return (
        hashlib.sha256(raw).hexdigest(),
        len(raw),
        datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
    )


def build_projection(repo_root: str | Path = ".", *, now: datetime | None = None):
    """Read the live policy sources and build a fresh projection.

    Local operator command only. Returns (projection, missing_paths) — a missing source is reported,
    never silently skipped, because a projection built from four of five sources is not the policy.
    """
    root = Path(repo_root)
    sources: list[PolicySourceRef] = []
    missing: list[str] = []
    for key, rel in POLICY_SOURCE_PATHS:
        path = (root / rel).resolve()
        if not path.is_file():
            missing.append(f"{key}={rel}")
            continue
        sha, size, mtime = _hash_file(path)
        sources.append(PolicySourceRef(
            key=key, path=rel, sha256=sha, bytes=size, modified_at=mtime
        ))
    projection = CandidatePolicyProjection(
        built_at=now or datetime.now(timezone.utc),
        sources=sources,
        rule_source_map={k: list(v) for k, v in sorted(RULE_SOURCE_MAP.items())},
        calibration=dict(CALIBRATION),
    )
    return projection, missing


def load_projection(path: str | Path = DEFAULT_PROJECTION_PATH) -> CandidatePolicyProjection | None:
    p = Path(path)
    if not p.is_file():
        return None
    return CandidatePolicyProjection.model_validate(json.loads(p.read_text()))


def save_projection(
    projection: CandidatePolicyProjection, path: str | Path = DEFAULT_PROJECTION_PATH
) -> None:
    Path(path).write_text(json.dumps(projection.model_dump(mode="json"), indent=2) + "\n")


def check_divergence(
    projection: CandidatePolicyProjection,
    repo_root: str | Path = ".",
    *,
    now: datetime | None = None,
) -> PolicyDivergence:
    """Compare the committed projection against the live sources, when they are reachable.

    In production the sources are absent, which is expected and is NOT divergence — it is reported
    as "not reachable" so the report can say which of the two situations it is in.
    """
    root = Path(repo_root)
    now = now or datetime.now(timezone.utc)
    reachable = any((root / rel).is_file() for _key, rel in POLICY_SOURCE_PATHS)
    if not reachable:
        return PolicyDivergence(checked_at=now, sources_available=False)

    changed: list[str] = []
    missing: list[str] = []
    unchanged: list[str] = []
    for ref in projection.sources:
        path = (root / ref.path).resolve()
        if not path.is_file():
            missing.append(ref.key)
            continue
        sha, _size, _mtime = _hash_file(path)
        (unchanged if sha == ref.sha256 else changed).append(ref.key)
    recorded = {r.key for r in projection.sources}
    for key, rel in POLICY_SOURCE_PATHS:
        if key not in recorded and (root / rel).is_file():
            changed.append(f"{key} (present but absent from the projection)")
    return PolicyDivergence(
        checked_at=now, sources_available=True,
        changed=changed, missing=missing, unchanged=unchanged,
    )
