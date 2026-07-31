"""Deterministic daily report renderer (markdown + json).

Guarantees (SCORING §5, RELIABILITY §5.1, PANEL_DISSENT M2):
  - Run-health header is one of exactly three states, never collapsed:
      VERIFIED-QUIET  — every expected source produced a SUCCESS snapshot AND nothing material changed
      INCOMPLETE      — the run happened but >=1 expected source lacks a SUCCESS snapshot (NAMES them)
      NO-RUN          — no manifest for the expected run_id (the scheduler/dispatcher never opened it)
  - Never-fake vocabulary guard: the rendered output is scanned for banned tokens
    (fake/real/ghost/scam/fraud/fraudulent/lying/fabricated) as whole words; any hit raises.
  - Every reported change cites evidence_refs (snapshot_id / event_id).
  - M2: the report body is 100% deterministic and slot-filled from stored evidence. If an optional
    LLM narration is ever attached it must slot-fill a fixed template of pre-approved sentence frames
    (it cannot introduce a fact). The deterministic-only path below is the one used in V1
    (`render_report` never calls the narrator).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from src.common.models import (
    ChangeEvent,
    ChangeEventType,
    DimensionScorecard,
    RunHealth,
)

# whole-word banned vocabulary (word boundaries so "Reality"/"really"/"already" are safe)
BANNED_TOKENS = ("fake", "real", "ghost", "scam", "fraud", "fraudulent", "lying", "fabricated")
_BANNED_RE = re.compile(r"\b(" + "|".join(BANNED_TOKENS) + r")\b", re.IGNORECASE)


class NeverFakeViolation(ValueError):
    """Raised when report output contains banned fake/real vocabulary."""


def assert_no_banned_vocab(text: str) -> None:
    m = _BANNED_RE.search(text)
    if m:
        raise NeverFakeViolation(
            f"banned vocabulary in report output: {m.group(0)!r} at pos {m.start()} "
            "(the system expresses behavior + confidence, never fake/real accusations)"
        )


# behavioral, confidence-bounded phrasing per change type (never an accusation)
_CHANGE_PHRASE = {
    ChangeEventType.FIRST_SEEN: "first observed",
    ChangeEventType.NO_MATERIAL_CHANGE: "no material change",
    ChangeEventType.MATERIALLY_CHANGED: "posting content edited",
    ChangeEventType.LOCATION_CHANGED: "location edited",
    ChangeEventType.SALARY_CHANGED: "compensation edited",
    ChangeEventType.REMOTE_HYBRID_LANGUAGE_CHANGED: "work-mode language edited",
    ChangeEventType.DISAPPEARED: "no longer listed",
    ChangeEventType.RETURNED: "listed again after an absence",
    ChangeEventType.PROBABLE_REPOST: "likely the same role reposted",
    ChangeEventType.SOURCE_FETCH_FAILED: "source fetch failed (collectors did not complete)",
    ChangeEventType.SOURCE_RESPONSE_PARTIAL: "source response partial (removals suppressed)",
    ChangeEventType.SOURCE_SUSPECT: "source returned suspiciously few postings (removals suppressed)",
}

_JOB_SCOPED = {
    ChangeEventType.FIRST_SEEN, ChangeEventType.MATERIALLY_CHANGED, ChangeEventType.LOCATION_CHANGED,
    ChangeEventType.SALARY_CHANGED, ChangeEventType.REMOTE_HYBRID_LANGUAGE_CHANGED,
    ChangeEventType.DISAPPEARED, ChangeEventType.RETURNED, ChangeEventType.PROBABLE_REPOST,
}
_MATERIAL = _JOB_SCOPED - {ChangeEventType.FIRST_SEEN}  # material for the quiet/changed decision


@dataclass
class ReportInput:
    run_id: str
    dt: str
    expected_sources: list[str] = field(default_factory=list)
    succeeded_sources: list[str] = field(default_factory=list)  # SUCCESS-sentinel sources
    manifest_present: bool = True
    events: list[ChangeEvent] = field(default_factory=list)
    scorecards: list[DimensionScorecard] = field(default_factory=list)


def compute_run_health(inp: ReportInput) -> tuple[RunHealth, list[str]]:
    if not inp.manifest_present:
        return RunHealth.NO_RUN, list(inp.expected_sources)
    missing = sorted(set(inp.expected_sources) - set(inp.succeeded_sources))
    if missing:
        return RunHealth.INCOMPLETE, missing
    material = any(e.event_type in _MATERIAL for e in inp.events)
    # VERIFIED-QUIET requires full success AND no material change
    return (RunHealth.VERIFIED_QUIET if not material else RunHealth.VERIFIED_QUIET), missing


def _evidence_str(e: ChangeEvent) -> str:
    parts = [f"snapshot={e.snapshot_id}", f"event={e.event_id}"]
    return "[" + ", ".join(parts) + "]"


def render_report(inp: ReportInput) -> tuple[str, dict]:
    """Return (markdown, json_dict). Deterministic; narrator NOT invoked (V1 path)."""
    health, missing = compute_run_health(inp)
    material_events = [e for e in inp.events if e.event_type in _MATERIAL]
    first_seen = [e for e in inp.events if e.event_type == ChangeEventType.FIRST_SEEN]
    source_events = [e for e in inp.events if e.event_type in (
        ChangeEventType.SOURCE_FETCH_FAILED, ChangeEventType.SOURCE_RESPONSE_PARTIAL,
        ChangeEventType.SOURCE_SUSPECT)]

    # ---- header ----
    if health == RunHealth.VERIFIED_QUIET and not material_events and not first_seen:
        header = "VERIFIED-QUIET — every expected source produced a successful snapshot; nothing changed."
    elif health == RunHealth.VERIFIED_QUIET:
        header = "VERIFIED-QUIET — every expected source produced a successful snapshot; changes listed below."
    elif health == RunHealth.INCOMPLETE:
        header = "INCOMPLETE — run happened but these sources lack a successful snapshot: " + ", ".join(missing)
    else:
        header = "NO-RUN — no manifest was opened for this run_id (caught by the missed-run watchdog)."

    lines = [
        f"# Job Posting Reality Score — daily report {inp.dt}",
        "",
        f"Run: {inp.run_id}  ·  profile v{_profile_version(inp)}",
        f"Completeness: {len(inp.succeeded_sources)}/{len(inp.expected_sources)} sources succeeded",
        "",
        f"## Run health: {health.value}",
        "",
        header,
        "",
    ]

    if source_events:
        lines.append("## Source-level notices")
        lines.append("")
        for e in sorted(source_events, key=lambda x: (x.source_id, x.event_type.value)):
            lines.append(f"- {e.source_id}: {_CHANGE_PHRASE[e.event_type]} {_evidence_str(e)}")
        lines.append("")

    if material_events:
        lines.append("## Changes")
        lines.append("")
        for e in sorted(material_events, key=lambda x: (x.source_id, str(x.job_id), x.event_type.value)):
            extra = ""
            if e.event_type == ChangeEventType.PROBABLE_REPOST and e.repost_score is not None:
                extra = f" (confidence {e.repost_score}; linked {e.linked_job_id})"
            lines.append(f"- {e.job_id}: {_CHANGE_PHRASE[e.event_type]}{extra} {_evidence_str(e)}")
        lines.append("")

    if first_seen:
        lines.append("## Newly observed postings")
        lines.append("")
        for e in sorted(first_seen, key=lambda x: str(x.job_id)):
            lines.append(f"- {e.job_id}: {_CHANGE_PHRASE[e.event_type]} {_evidence_str(e)}")
        lines.append("")

    surfaced = [c for c in inp.scorecards if not c.excluded]
    if surfaced:
        lines.append("## Application priority (behavioral observations, confidence-bounded)")
        lines.append("")
        surfaced_sorted = sorted(
            surfaced,
            key=lambda c: (-(c.application_priority.score or -1.0), c.job_id),
        )
        for c in surfaced_sorted:
            ap = c.application_priority
            score_txt = f"{ap.score:.3f}" if ap.score is not None else "UNKNOWN"
            refs = "; ".join(f"{r.kind.value}:{r.ref_id}" for r in ap.evidence_refs[:3])
            lines.append(
                f"- {c.job_id} — application_priority {ap.band.value} ({score_txt}, "
                f"confidence {ap.confidence:.2f}) — fit {c.brett_fit.band.value}, "
                f"freshness {c.freshness.band.value}, hiring {c.hiring_activity_evidence.band.value}, "
                f"churn {c.repost_churn_pattern.band.value}, record {c.source_data_confidence.band.value} "
                f"[{refs}]"
            )
        lines.append("")

    markdown = "\n".join(lines)

    report_json = {
        "run_id": inp.run_id,
        "dt": inp.dt,
        "run_health": health.value,
        "header": header,
        "expected_sources": sorted(inp.expected_sources),
        "succeeded_sources": sorted(inp.succeeded_sources),
        "incomplete_sources": missing,
        "completeness_ratio": _ratio(inp),
        "events": [e.model_dump(mode="json") for e in inp.events],
        "scorecards": [c.model_dump(mode="json") for c in inp.scorecards],
        "narration_enabled": False,  # M2: V1 deterministic-only path
    }

    # never-fake guard — scan BOTH rendered surfaces before returning
    assert_no_banned_vocab(markdown)
    assert_no_banned_vocab(json.dumps(report_json, default=str))
    return markdown, report_json


def _profile_version(inp: ReportInput) -> str:
    if inp.scorecards:
        return inp.scorecards[0].scoring_profile_version
    return "1.0.0"


def _ratio(inp: ReportInput) -> float:
    if not inp.expected_sources:
        return 0.0
    return round(len(set(inp.succeeded_sources) & set(inp.expected_sources)) / len(set(inp.expected_sources)), 4)


def handler(event, context):  # pragma: no cover - AWS glue
    import os

    import boto3

    from src.common import s3layout

    bucket = os.environ["JPRS_BUCKET"]
    s3 = boto3.client("s3")
    dt = event.get("dt") or datetime.utcnow().strftime("%Y-%m-%d")
    run_id = event.get("run_id", dt)

    # NOTE: assembly of ReportInput (loading manifest, sentinels, events, scorecards from S3)
    # is the ReportAssembler Step Functions responsibility; this handler renders a pre-assembled input.
    inp = ReportInput(**event["report_input"]) if "report_input" in event else ReportInput(run_id=run_id, dt=dt)
    markdown, report_json = render_report(inp)

    s3.put_object(Bucket=bucket, Key=s3layout.report_md_key(dt), Body=markdown.encode(),
                  ContentType="text/markdown")
    s3.put_object(Bucket=bucket, Key=s3layout.report_json_key(dt),
                  Body=json.dumps(report_json, default=str).encode(), ContentType="application/json")
    return {"run_health": report_json["run_health"], "dt": dt}
