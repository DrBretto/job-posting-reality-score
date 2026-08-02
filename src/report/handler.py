"""Deterministic daily report renderer (markdown + json).

Guarantees (SCORING §5, RELIABILITY §5.1, PANEL_DISSENT M2):
  - Run-health header is one of exactly three states, never collapsed:
      VERIFIED-QUIET  — every expected source produced a SUCCESS snapshot AND nothing material changed
      INCOMPLETE      — the run happened but >=1 expected source lacks a SUCCESS snapshot (NAMES them)
      NO-RUN          — no manifest for the expected run_id (the scheduler/dispatcher never opened it)
  - Never-fake vocabulary guard: system-authored report language is scanned for banned tokens
    (fake/real/ghost/scam/fraud/fraudulent/lying/fabricated) as whole words; sourced titles,
    locations, URLs, and identifiers are redacted before scanning because they are evidence labels,
    not system claims.
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
from datetime import datetime, timezone

from src.common.models import (
    Band,
    CanonicalJob,
    ChangeEvent,
    ChangeEventType,
    DimensionScorecard,
    RunHealth,
    SnapshotStatus,
)
from src.scoring.scoring import ScoreContext, ScoringProfile, score_job

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
_MAX_MATCHES = 20
_MAX_EVENT_ITEMS = 15

_COMPANY_LABELS = {
    "axiomatic-ai": "Axiomatic AI",
    "bolt-new": "Bolt.new",
    "cadence-solutions": "Cadence Solutions",
    "cargomatic": "Cargomatic",
    "future": "Future",
    "grafana-labs": "Grafana Labs",
    "icon": "ICON",
    "implicit": "Implicit",
    "legion-intelligence": "Legion Intelligence",
    "machinify": "Machinify",
    "mozilla": "Mozilla",
    "nimble-gravity": "Nimble Gravity",
    "snorkel-ai": "Snorkel AI",
    "tailscale": "Tailscale",
    "warp": "Warp",
}


@dataclass
class ReportInput:
    run_id: str
    dt: str
    expected_sources: list[str] = field(default_factory=list)
    succeeded_sources: list[str] = field(default_factory=list)  # SUCCESS-sentinel sources
    manifest_present: bool = True
    events: list[ChangeEvent] = field(default_factory=list)
    scorecards: list[DimensionScorecard] = field(default_factory=list)
    jobs: list[CanonicalJob] = field(default_factory=list)
    source_labels: dict[str, str] = field(default_factory=dict)


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


def _company_name(source_id: str, source_labels: dict[str, str]) -> str:
    slug = source_labels.get(source_id) or source_id.partition(":")[2] or source_id
    return _COMPANY_LABELS.get(slug, slug.replace("-", " ").title())


def _md_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")


def _job_link(job: CanonicalJob) -> str:
    title = _md_text(job.title)
    url = job.posting_url or job.apply_url or ""
    return f"[{title}]({url})" if url else title


def _ranked_matches(inp: ReportInput) -> list[DimensionScorecard]:
    eligible = [
        card for card in inp.scorecards
        if not card.excluded and card.brett_fit.band in (Band.HIGH, Band.MEDIUM)
    ]
    return sorted(
        eligible,
        key=lambda card: (
            -(card.application_priority.score if card.application_priority.score is not None else -1.0),
            -(card.brett_fit.score if card.brett_fit.score is not None else -1.0),
            card.job_id,
        ),
    )


def _signal_summary(card: DimensionScorecard) -> str:
    detail = card.brett_fit.detail
    signals: list[str] = []
    for key in ("title_signals", "skill_signals"):
        signals.extend(s for s in str(detail.get(key, "")).split(",") if s)
    return ", ".join(signals[:6])


def _match_json(card: DimensionScorecard, job: CanonicalJob, inp: ReportInput) -> dict:
    return {
        "source_id": card.source_id,
        "job_id": card.job_id,
        "company": _company_name(card.source_id, inp.source_labels),
        "title": job.title,
        "location": job.raw_location or job.canonical_location or "Location not stated",
        "remote_mode": job.remote_hybrid_language.value,
        "posting_url": job.posting_url or job.apply_url or None,
        "first_seen_at": job.first_seen_at.isoformat() if job.first_seen_at else None,
        "fit_score": card.brett_fit.score,
        "fit_band": card.brett_fit.band.value,
        "priority_score": card.application_priority.score,
        "priority_band": card.application_priority.band.value,
        "priority_confidence": card.application_priority.confidence,
        "signals": _signal_summary(card),
    }


def _event_subject(event: ChangeEvent, jobs_by_id: dict[str, CanonicalJob], inp: ReportInput) -> str:
    job = jobs_by_id.get(event.job_id or "")
    if job is None:
        return str(event.job_id or event.source_id)
    return f"{_job_link(job)} at {_company_name(event.source_id, inp.source_labels)}"


def _source_values(inp: ReportInput) -> list[str]:
    """Provider-supplied strings that may legitimately contain otherwise guarded vocabulary."""
    values: set[str] = set(inp.source_labels.values()) | set(inp.expected_sources)
    for job in inp.jobs:
        values.update(filter(None, (
            job.source_id, job.job_id, job.title, job.raw_location, job.canonical_location,
            job.posting_url, job.apply_url,
        )))
    for event in inp.events:
        values.update(filter(None, (
            event.source_id, event.job_id, event.event_id, event.snapshot_id,
            event.prior_snapshot_id, event.linked_job_id, event.content_hash,
        )))
    values.update(_company_name(source_id, inp.source_labels) for source_id in inp.expected_sources)
    return sorted((str(value) for value in values if value), key=len, reverse=True)


def _assert_report_language(markdown: str, report_json: dict, inp: ReportInput) -> None:
    markdown_guard = markdown
    json_guard = json.dumps(report_json, default=str)
    for value in _source_values(inp):
        markdown_guard = markdown_guard.replace(value, "<SOURCE_VALUE>")
        json_guard = json_guard.replace(value, "<SOURCE_VALUE>")
    assert_no_banned_vocab(markdown_guard)
    assert_no_banned_vocab(json_guard)


def render_report(inp: ReportInput) -> tuple[str, dict]:
    """Return (markdown, json_dict). Deterministic; narrator NOT invoked (V1 path)."""
    health, missing = compute_run_health(inp)
    material_events = [e for e in inp.events if e.event_type in _MATERIAL]
    first_seen = [e for e in inp.events if e.event_type == ChangeEventType.FIRST_SEEN]
    source_events = [e for e in inp.events if e.event_type in (
        ChangeEventType.SOURCE_FETCH_FAILED, ChangeEventType.SOURCE_RESPONSE_PARTIAL,
        ChangeEventType.SOURCE_SUSPECT)]
    jobs_by_id = {job.job_id: job for job in inp.jobs}
    ranked = _ranked_matches(inp)
    ranked_pairs = [(card, jobs_by_id[card.job_id]) for card in ranked if card.job_id in jobs_by_id]
    top_pairs = ranked_pairs[:_MAX_MATCHES]
    relevant_ids = {card.job_id for card, _ in ranked_pairs}
    relevance_order = {card.job_id: index for index, (card, _) in enumerate(ranked_pairs)}
    visible_material = (
        [event for event in material_events if event.job_id in relevant_ids]
        if inp.scorecards else material_events
    )
    visible_first_seen = (
        [event for event in first_seen if event.job_id in relevant_ids]
        if inp.scorecards else first_seen
    )

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
            company = _company_name(e.source_id, inp.source_labels)
            lines.append(f"- {company} ({e.source_id}): {_CHANGE_PHRASE[e.event_type]} {_evidence_str(e)}")
        lines.append("")

    if top_pairs:
        lines.append("## Best current matches")
        lines.append("")
        for card, job in top_pairs:
            fit = card.brett_fit
            priority = card.application_priority
            fit_score = f"{fit.score:.2f}" if fit.score is not None else "UNKNOWN"
            priority_score = f"{priority.score:.2f}" if priority.score is not None else "UNKNOWN"
            location = _md_text(job.raw_location or job.canonical_location or "Location not stated")
            company = _company_name(card.source_id, inp.source_labels)
            signals = _signal_summary(card)
            signal_text = f" | signals: {signals}" if signals else ""
            lines.append(
                f"- {_job_link(job)} - {company} | {location} | fit {fit.band.value} {fit_score} | "
                f"priority {priority.band.value} {priority_score}{signal_text}"
            )
        if len(ranked_pairs) > _MAX_MATCHES:
            lines.append(f"- {len(ranked_pairs) - _MAX_MATCHES} additional matching roles are retained in JSON.")
        lines.append("")
    elif inp.scorecards:
        lines.extend(["## Best current matches", "", "No current postings cleared the fit threshold today.", ""])

    if visible_material:
        lines.append("## Changes")
        lines.append("")
        ordered = sorted(
            visible_material,
            key=lambda x: (relevance_order.get(x.job_id or "", len(relevance_order)), x.event_type.value),
        )
        for e in ordered[:_MAX_EVENT_ITEMS]:
            extra = ""
            if e.event_type == ChangeEventType.PROBABLE_REPOST and e.repost_score is not None:
                extra = f" (confidence {e.repost_score}; linked {e.linked_job_id})"
            subject = _event_subject(e, jobs_by_id, inp)
            lines.append(f"- {subject}: {_CHANGE_PHRASE[e.event_type]}{extra} {_evidence_str(e)}")
        if len(visible_material) > _MAX_EVENT_ITEMS:
            lines.append(f"- {len(visible_material) - _MAX_EVENT_ITEMS} additional matching-role changes are retained in JSON.")
        lines.append("")

    if visible_first_seen:
        lines.append("## Newly observed postings")
        lines.append("")
        ordered = sorted(
            visible_first_seen,
            key=lambda x: relevance_order.get(x.job_id or "", len(relevance_order)),
        )
        for e in ordered[:_MAX_EVENT_ITEMS]:
            subject = _event_subject(e, jobs_by_id, inp)
            lines.append(f"- {subject}: {_CHANGE_PHRASE[e.event_type]} {_evidence_str(e)}")
        if len(visible_first_seen) > _MAX_EVENT_ITEMS:
            lines.append(f"- {len(visible_first_seen) - _MAX_EVENT_ITEMS} additional matching new postings are retained in JSON.")
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
        "current_job_count": len(inp.jobs),
        "matching_job_count": len(ranked_pairs),
        "top_matches": [_match_json(card, job, inp) for card, job in top_pairs],
        "events": [e.model_dump(mode="json") for e in inp.events],
        "scorecards": [c.model_dump(mode="json") for c in inp.scorecards],
        "narration_enabled": False,  # M2: V1 deterministic-only path
    }

    # Scan both surfaces after redacting provider-supplied labels. Event notes remain unredacted.
    _assert_report_language(markdown, report_json, inp)
    return markdown, report_json


def _profile_version(inp: ReportInput) -> str:
    if inp.scorecards:
        return inp.scorecards[0].scoring_profile_version
    return ScoringProfile().version


def _ratio(inp: ReportInput) -> float:
    if not inp.expected_sources:
        return 0.0
    return round(len(set(inp.succeeded_sources) & set(inp.expected_sources)) / len(set(inp.expected_sources)), 4)


def assemble_report_input(s3, bucket: str, run_id: str, dt: str) -> ReportInput:
    """Build ReportInput from S3: RUN_OPEN manifest (expected), SUCCESS sentinels (succeeded),
    and the differ's change events. This is the assembler the render step always needed; without it
    the report rendered an empty 0/0 input. Completeness = manifest-expected vs sentinel-succeeded
    (never wall-clock), per RELIABILITY §5.1."""
    from src.common import s3layout

    manifest = _load_json(s3, bucket, s3layout.run_manifest_key(run_id), default=None)
    manifest_present = manifest is not None
    expected_sources = list(manifest.get("expected_sources", [])) if manifest_present else []
    source_labels = dict(manifest.get("source_labels", {})) if manifest_present else {}

    succeeded: list[str] = []
    for key in _list_keys(s3, bucket, f"status/run={run_id}/"):
        if key.endswith("/SUCCESS.json"):
            segs = dict(s.split("=", 1) for s in key.split("/") if "=" in s)
            p, b = segs.get("provider"), segs.get("board")
            if p and b:
                succeeded.append(f"{p}:{b}")

    events: list[ChangeEvent] = []
    for sid in expected_sources:
        provider, _, board = sid.partition(":")
        for e in _load_json(s3, bucket, s3layout.events_key(provider, board, dt), default=[]):
            events.append(ChangeEvent.model_validate(e))

    jobs: list[CanonicalJob] = []
    scorecards: list[DimensionScorecard] = []
    scored_as_of = datetime.fromisoformat(f"{dt}T23:59:59+00:00")
    for sid in expected_sources:
        provider, _, board = sid.partition(":")
        raw_jobs = _load_json(s3, bucket, s3layout.current_jobs_key(provider, board), default=[])
        state = _load_json(s3, bucket, s3layout.current_state_key(provider, board), default={})
        state_jobs = state.get("jobs", {})
        observation_count = max(1, len(state.get("success_count_history", [])))
        source_events = [event for event in events if event.source_id == sid]
        statuses = [SnapshotStatus.SUCCESS] * observation_count
        if any(event.event_type == ChangeEventType.SOURCE_FETCH_FAILED for event in source_events):
            statuses.append(SnapshotStatus.FETCH_FAILED)
        elif any(event.event_type in (
            ChangeEventType.SOURCE_RESPONSE_PARTIAL, ChangeEventType.SOURCE_SUSPECT
        ) for event in source_events):
            statuses.append(SnapshotStatus.PARTIAL)

        for raw_job in raw_jobs:
            job = CanonicalJob.model_validate(raw_job)
            record = state_jobs.get(job.job_id, {})
            if record.get("first_seen_at"):
                job.first_seen_at = _parse_datetime(record["first_seen_at"])
            if record.get("last_seen_at"):
                job.last_seen_at = _parse_datetime(record["last_seen_at"])
            job_events = [
                event for event in source_events
                if event.job_id == job.job_id or event.job_id is None
            ]
            jobs.append(job)
            scorecards.append(score_job(
                ScoreContext(
                    job=job,
                    events=job_events,
                    recent_snapshot_statuses=statuses,
                    num_successful_observations=observation_count,
                ),
                today=scored_as_of,
            ))

    return ReportInput(
        run_id=run_id,
        dt=dt,
        expected_sources=expected_sources,
        succeeded_sources=sorted(set(succeeded)),
        manifest_present=manifest_present,
        events=events,
        scorecards=scorecards,
        jobs=jobs,
        source_labels=source_labels,
    )


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def handler(event, context):
    import os

    import boto3

    from src.common import s3layout

    bucket = os.environ["JPRS_BUCKET"]
    s3 = boto3.client("s3")
    ctx = event.get("runContext") or {}
    run_id = event.get("run_id") or ctx.get("run_id") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dt = event.get("dt") or ctx.get("dt") or run_id

    inp = assemble_report_input(s3, bucket, run_id, dt)
    markdown, report_json = render_report(inp)

    s3.put_object(Bucket=bucket, Key=s3layout.report_md_key(dt), Body=markdown.encode(),
                  ContentType="text/markdown")
    s3.put_object(Bucket=bucket, Key=s3layout.report_json_key(dt),
                  Body=json.dumps(report_json, default=str).encode(), ContentType="application/json")

    digest_delivery = "disabled"
    sender = os.environ.get("SES_SENDER", "").strip()
    recipient = os.environ.get("DIGEST_RECIPIENT", "").strip()
    if bool(sender) != bool(recipient):
        raise ValueError("SES_SENDER and DIGEST_RECIPIENT must be configured together")
    if sender and recipient:
        marker_key = s3layout.digest_delivery_key(dt)
        prior_delivery = _load_json(s3, bucket, marker_key, default=None)
        if prior_delivery is not None:
            digest_delivery = "already-sent"
        else:
            subject = (
                f"Job radar {dt}: {report_json['matching_job_count']} matching roles "
                f"({report_json['run_health']})"
            )
            message_id = send_digest(
                boto3.client("ses"), sender=sender, recipient=recipient,
                subject=subject, body=markdown,
            )
            s3.put_object(
                Bucket=bucket,
                Key=marker_key,
                Body=json.dumps({
                    "dt": dt,
                    "recipient": recipient,
                    "message_id": message_id,
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                }, separators=(",", ":")).encode(),
                ContentType="application/json",
            )
            digest_delivery = "sent"
    return {
        "run_health": report_json["run_health"], "dt": dt,
        "expected": len(inp.expected_sources), "succeeded": len(inp.succeeded_sources),
        "events": len(inp.events), "matches": report_json["matching_job_count"],
        "digest_delivery": digest_delivery,
    }


def send_digest(ses, *, sender: str, recipient: str, subject: str, body: str) -> str:
    """Send the deterministic Markdown report as a plain-text SES email."""
    response = ses.send_email(
        Source=sender,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )
    return response["MessageId"]


def _load_json(s3, bucket, key, default="__raise__"):
    import botocore.exceptions

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read())
    except botocore.exceptions.ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if default != "__raise__" and code in ("NoSuchKey", "NoSuchObject", "404", "NotFound"):
            return default
        raise


def _list_keys(s3, bucket, prefix):
    keys, token = [], None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        keys.extend(o["Key"] for o in resp.get("Contents", []))
        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
        else:
            break
    return keys
