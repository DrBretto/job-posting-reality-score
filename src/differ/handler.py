"""The change-detection brain (DATA_MODEL §5, RELIABILITY §5, PANEL_DISSENT M3).

THE INVARIANT (DATA_MODEL §0): a `disappeared` change-event may ONLY be emitted when diffed against
a SUCCESSFUL snapshot of the same source. A failed/partial/throttled fetch NEVER marks jobs removed.
This is enforced structurally: on a FROZEN status the diff returns early with a source-scoped event,
freezes all job states, and pauses grace clocks.

Gates owned here (RELIABILITY §5.2 + M3):
  (a) successful-snapshot precondition (the freeze),
  (b) consecutive-absence grace N (counted in SUCCESS snapshots, not days),
  (c) single-step mass-drop SUSPECT guard,
  (d) M3 cumulative/trend SUSPECT guard (catch a 50%+50% two-day bleed),
  (e) M3 per-segment completeness guard (catch a silent-subset SUCCESS).

Pure-function core (`diff_source`) so it is fully testable with synthetic fixtures; `handler` is the
thin Lambda/SQS wrapper around it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field

from src.common.models import (
    SCHEMA_VERSION,
    SUCCESSFUL_STATUSES,
    FROZEN_STATUSES,
    CanonicalJob,
    ChangeEvent,
    ChangeEventType,
    JobLifecycleState,
    SnapshotStatus,
    SourceSnapshot,
)


@dataclass(frozen=True)
class DiffConfig:
    grace_successful_snapshots: int = 2      # D1
    single_step_drop: float = 0.60           # mass-drop guard (drop >60% or to zero vs prior SUCCESS)
    cumulative_window: int = 3               # M3 rolling window of prior SUCCESS counts
    cumulative_drop: float = 0.60            # M3 cumulative shrink threshold across the window
    reopen_window_days: int = 30             # D5 repost reopen window
    repost_threshold: float = 0.70           # D5 repost confidence bar


class JobStateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str
    state: JobLifecycleState = JobLifecycleState.ACTIVE
    content_hash: str = ""
    field_hashes: dict[str, str] = Field(default_factory=dict)
    first_seen_at: datetime
    last_seen_at: datetime
    absence_count: int = 0
    disappeared_at: datetime | None = None
    # repost-match evidence
    requisition_id: str | None = None
    title_norm: str = ""
    canonical_location: str = ""
    department: str | None = None
    team: str | None = None
    identity_low_confidence: bool = False


class DiffState(BaseModel):
    """Differ's persisted per-source state. On a FROZEN snapshot this is returned unchanged."""

    model_config = ConfigDict(extra="forbid")
    source_id: str
    jobs: dict[str, JobStateRecord] = Field(default_factory=dict)
    success_count_history: list[int] = Field(default_factory=list)
    last_success_snapshot_id: str | None = None
    schema_version: str = SCHEMA_VERSION


@dataclass
class DiffResult:
    events: list[ChangeEvent]
    state: DiffState
    current_jobs: list[CanonicalJob] | None  # None => do not overwrite current/ (frozen run)
    suspect: bool = False
    suspect_reason: str | None = None
    frozen: bool = False


def _seg(job_dept: str | None) -> str:
    return (job_dept or "__none__").strip().lower()


def _event(
    etype: ChangeEventType,
    *,
    source_id: str,
    run_id: str,
    as_of: datetime,
    snapshot_id: str,
    job_id: str | None = None,
    prior_snapshot_id: str | None = None,
    changed_fields: list[str] | None = None,
    content_hash: str | None = None,
    linked_job_id: str | None = None,
    repost_score: float | None = None,
    notes: str | None = None,
) -> ChangeEvent:
    key = job_id or source_id
    return ChangeEvent(
        event_id=f"{run_id}:{key}:{etype.value}",
        event_type=etype,
        source_id=source_id,
        job_id=job_id,
        run_id=run_id,
        as_of=as_of,
        snapshot_id=snapshot_id,
        prior_snapshot_id=prior_snapshot_id,
        changed_fields=changed_fields or [],
        content_hash=content_hash,
        linked_job_id=linked_job_id,
        repost_score=repost_score,
        notes=notes,
    )


def _repost_score(new: CanonicalJob, old: JobStateRecord) -> float:
    score = 0.0
    if new.requisition_id and old.requisition_id and new.requisition_id == old.requisition_id:
        score += 0.5
    from src.common.normalize import _norm_key  # local import to avoid cycle at module import

    if _norm_key(new.title) and _norm_key(new.title) == old.title_norm:
        score += 0.2
    if new.canonical_location and new.canonical_location == old.canonical_location:
        score += 0.15
    if (new.department or None) == (old.department or None) and (new.team or None) == (old.team or None):
        score += 0.1
    if new.field_hashes.get("body_hash") and old.field_hashes.get("body_hash") == new.field_hashes.get("body_hash"):
        score += 0.05
    return round(score, 4)


def diff_source(
    state: DiffState | None,
    snapshot: SourceSnapshot,
    jobs: list[CanonicalJob],
    *,
    run_id: str,
    today: datetime,
    config: DiffConfig | None = None,
) -> DiffResult:
    """Pure diff of one source's current snapshot against its persisted state."""
    cfg = config or DiffConfig()
    source_id = snapshot.source_id
    as_of = snapshot.fetched_at
    prior_snap_id = state.last_success_snapshot_id if state else None

    # ---- FROZEN: the invariant. No removals, states frozen, grace paused. --------------------
    if snapshot.status in FROZEN_STATUSES:
        etype = (
            ChangeEventType.SOURCE_FETCH_FAILED
            if snapshot.status == SnapshotStatus.FETCH_FAILED
            else ChangeEventType.SOURCE_RESPONSE_PARTIAL
        )
        ev = _event(
            etype,
            source_id=source_id,
            run_id=run_id,
            as_of=as_of,
            snapshot_id=snapshot.snapshot_id,
            prior_snapshot_id=prior_snap_id,
            notes=f"status={snapshot.status.value}; job states frozen, grace paused, zero removals",
        )
        # return state completely unchanged (deep-copied so callers can't mutate history)
        carried = state.model_copy(deep=True) if state else DiffState(source_id=source_id)
        return DiffResult(events=[ev], state=carried, current_jobs=None, frozen=True)

    if snapshot.status not in SUCCESSFUL_STATUSES:  # defensive
        raise ValueError(f"unexpected snapshot status: {snapshot.status}")

    # ---- SUCCESS / EMPTY_SUCCESS ------------------------------------------------------------
    new_state = state.model_copy(deep=True) if state else DiffState(source_id=source_id)
    prior_jobs = new_state.jobs
    prior_count = new_state.success_count_history[-1] if new_state.success_count_history else None
    n = len(jobs)
    events: list[ChangeEvent] = []

    current_ids = {j.job_id for j in jobs}

    # ---- SUSPECT detection (single-step + M3 cumulative + M3 silent-subset) -----------------
    suspect_reason: str | None = None
    if prior_count is not None and prior_count > 0:
        # (c) single-step mass-drop
        if n == 0 or (prior_count - n) / prior_count > cfg.single_step_drop:
            suspect_reason = f"mass-drop single-step ({prior_count}->{n} vs prior SUCCESS)"
        else:
            # (d) M3 cumulative/trend: compare current vs max over the rolling window of prior SUCCESS
            window = new_state.success_count_history[-cfg.cumulative_window:]
            if window:
                wmax = max(window)
                if wmax > 0 and (wmax - n) / wmax > cfg.cumulative_drop:
                    suspect_reason = (
                        f"cumulative bleed (window max {wmax} -> {n} exceeds "
                        f"{int(cfg.cumulative_drop * 100)}% over {len(window)} SUCCESS snapshots)"
                    )
            # (e) M3 silent-subset: a whole prior-present segment vanished while others persist
            if suspect_reason is None:
                prior_present = [r for r in prior_jobs.values() if r.state == JobLifecycleState.ACTIVE]
                prior_segs: dict[str, int] = {}
                for r in prior_present:
                    prior_segs[_seg(r.department)] = prior_segs.get(_seg(r.department), 0) + 1
                cur_segs: dict[str, int] = {}
                for j in jobs:
                    cur_segs[_seg(j.department)] = cur_segs.get(_seg(j.department), 0) + 1
                vanished = [s for s, c in prior_segs.items() if c > 0 and cur_segs.get(s, 0) == 0]
                survived = any(cur_segs.get(s, 0) > 0 for s in prior_segs)
                if vanished and survived and len(prior_segs) > 1:
                    suspect_reason = f"silent-subset SUCCESS (segments omitted: {sorted(vanished)})"

    suspect = suspect_reason is not None
    if suspect:
        events.append(_event(
            ChangeEventType.SOURCE_SUSPECT,
            source_id=source_id, run_id=run_id, as_of=as_of,
            snapshot_id=snapshot.snapshot_id, prior_snapshot_id=prior_snap_id,
            notes=f"{suspect_reason}; removals SUPPRESSED this run",
        ))

    # ---- present jobs: first-seen / returned / field + material changes ----------------------
    reopen_cutoff = today - timedelta(days=cfg.reopen_window_days)
    disappeared_pool = [
        r for r in prior_jobs.values()
        if r.state == JobLifecycleState.DISAPPEARED
        and r.disappeared_at is not None
        and r.disappeared_at >= reopen_cutoff
    ]

    for job in jobs:
        existing = prior_jobs.get(job.job_id)
        if existing is None:
            # brand-new id -> first-seen (first_seen_at is OUR earliest SUCCESS observation)
            events.append(_event(
                ChangeEventType.FIRST_SEEN,
                source_id=source_id, run_id=run_id, as_of=as_of,
                snapshot_id=snapshot.snapshot_id, job_id=job.job_id,
                content_hash=job.content_hash,
            ))
            # repost matching against recently-disappeared jobs
            best = None
            best_score = 0.0
            for old in disappeared_pool:
                s = _repost_score(job, old)
                if s > best_score:
                    best_score, best = s, old
            if best is not None and best_score >= cfg.repost_threshold:
                events.append(_event(
                    ChangeEventType.PROBABLE_REPOST,
                    source_id=source_id, run_id=run_id, as_of=as_of,
                    snapshot_id=snapshot.snapshot_id, job_id=job.job_id,
                    linked_job_id=best.job_id, repost_score=best_score,
                    notes=f"likely the same role reposted (confidence {best_score})",
                ))
            prior_jobs[job.job_id] = _fresh_record(job, first_seen=as_of, last_seen=as_of)
            continue

        # existing job present again
        prev_state = existing.state
        if prev_state == JobLifecycleState.DISAPPEARED:
            events.append(_event(
                ChangeEventType.RETURNED,
                source_id=source_id, run_id=run_id, as_of=as_of,
                snapshot_id=snapshot.snapshot_id, job_id=job.job_id,
            ))
        # PENDING_REMOVAL returning within grace is cancelled silently (churn signal, not disappearance)
        existing.absence_count = 0
        existing.state = JobLifecycleState.ACTIVE
        existing.last_seen_at = as_of

        # content-change detection
        if existing.content_hash == job.content_hash:
            events.append(_event(
                ChangeEventType.NO_MATERIAL_CHANGE,
                source_id=source_id, run_id=run_id, as_of=as_of,
                snapshot_id=snapshot.snapshot_id, job_id=job.job_id,
                content_hash=job.content_hash,
            ))
        else:
            changed = [
                fh for fh in job.field_hashes
                if existing.field_hashes.get(fh) != job.field_hashes.get(fh)
            ]
            emitted_specific = False
            if "salary_hash" in changed:
                events.append(_field_event(ChangeEventType.SALARY_CHANGED, job, changed, source_id, run_id, as_of, snapshot))
                emitted_specific = True
            if "location_hash" in changed:
                events.append(_field_event(ChangeEventType.LOCATION_CHANGED, job, changed, source_id, run_id, as_of, snapshot))
                emitted_specific = True
            if "workmode_hash" in changed:
                events.append(_field_event(ChangeEventType.REMOTE_HYBRID_LANGUAGE_CHANGED, job, changed, source_id, run_id, as_of, snapshot))
                emitted_specific = True
            other = [c for c in changed if c in ("title_hash", "body_hash")]
            if other or not emitted_specific:
                events.append(_field_event(ChangeEventType.MATERIALLY_CHANGED, job, changed, source_id, run_id, as_of, snapshot))

        # refresh stored hashes + repost evidence
        existing.content_hash = job.content_hash
        existing.field_hashes = dict(job.field_hashes)
        _refresh_repost_fields(existing, job)

    # ---- absent jobs: grace clock -> PENDING_REMOVAL -> DISAPPEARED (only if NOT suspect) -----
    if not suspect:
        for job_id, rec in prior_jobs.items():
            if job_id in current_ids:
                continue
            if rec.state == JobLifecycleState.DISAPPEARED:
                continue  # already gone; no repeat event
            rec.absence_count += 1
            if rec.absence_count >= cfg.grace_successful_snapshots:
                rec.state = JobLifecycleState.DISAPPEARED
                rec.disappeared_at = as_of
                events.append(_event(
                    ChangeEventType.DISAPPEARED,
                    source_id=source_id, run_id=run_id, as_of=as_of,
                    snapshot_id=snapshot.snapshot_id, job_id=job_id,
                    prior_snapshot_id=prior_snap_id,
                    notes=f"absent in {rec.absence_count} consecutive SUCCESS snapshots (grace)",
                ))
            else:
                rec.state = JobLifecycleState.PENDING_REMOVAL
    # when suspect: absent jobs are frozen (absence_count untouched, no removal events)

    # ---- baseline / history maintenance ------------------------------------------------------
    new_state.last_success_snapshot_id = snapshot.snapshot_id
    if not suspect:
        # only a trusted SUCCESS updates the count baseline (a guarded drop must not poison it)
        new_state.success_count_history.append(n)
        new_state.success_count_history = new_state.success_count_history[-(cfg.cumulative_window + 2):]

    return DiffResult(
        events=events,
        state=new_state,
        current_jobs=jobs,
        suspect=suspect,
        suspect_reason=suspect_reason,
        frozen=False,
    )


def _field_event(etype, job, changed, source_id, run_id, as_of, snapshot) -> ChangeEvent:
    return _event(
        etype,
        source_id=source_id, run_id=run_id, as_of=as_of,
        snapshot_id=snapshot.snapshot_id, job_id=job.job_id,
        changed_fields=sorted(changed), content_hash=job.content_hash,
    )


def _fresh_record(job: CanonicalJob, *, first_seen: datetime, last_seen: datetime) -> JobStateRecord:
    from src.common.normalize import _norm_key

    return JobStateRecord(
        job_id=job.job_id,
        state=JobLifecycleState.ACTIVE,
        content_hash=job.content_hash,
        field_hashes=dict(job.field_hashes),
        first_seen_at=first_seen,
        last_seen_at=last_seen,
        absence_count=0,
        requisition_id=job.requisition_id,
        title_norm=_norm_key(job.title),
        canonical_location=job.canonical_location,
        department=job.department,
        team=job.team,
        identity_low_confidence=job.identity_low_confidence,
    )


def _refresh_repost_fields(rec: JobStateRecord, job: CanonicalJob) -> None:
    from src.common.normalize import _norm_key

    rec.requisition_id = job.requisition_id
    rec.title_norm = _norm_key(job.title)
    rec.canonical_location = job.canonical_location
    rec.department = job.department
    rec.team = job.team
    rec.identity_low_confidence = job.identity_low_confidence


# --------------------------------------------------------------------------------------------------
# Lambda handler (thin S3 wrapper). Reads persisted state + latest snapshot, writes events/+current/.
# --------------------------------------------------------------------------------------------------
def build_snapshot_from_status(status_doc: dict) -> SourceSnapshot:
    """Reconstruct the SourceSnapshot the differ needs from the collector's status/ doc.

    The collector persists status/_source_status.json (source_id/status/snapshot_id/fetched_at/...)
    rather than a full SourceSnapshot JSON, so the differ rebuilds the fields diff_source uses.
    """
    fetched = status_doc["fetched_at"]
    return SourceSnapshot(
        snapshot_id=status_doc["snapshot_id"],
        source_id=status_doc["source_id"],
        fetched_at=datetime.fromisoformat(fetched) if isinstance(fetched, str) else fetched,
        status=SnapshotStatus(status_doc["status"]),
        http_status=status_doc.get("http_status"),
        job_count_observed=status_doc.get("job_count_observed"),
        error_class=status_doc.get("error_class"),
    )


def run_diff(s3, bucket: str, provider: str, board: str, *, run_id: str, dt: str, today: datetime) -> dict:
    """Load this source's status + normalized jobs + prior state from S3, diff, and persist.

    Testable with a mocked S3 (moto) — this is the glue the pure `diff_source` needs. It DERIVES the
    keys it reads (status/ + normalized/ are deterministic) instead of being handed them, which is
    exactly the contract gap that used to make the Map branch fail silently to DEGRADED.
    """
    from src.common import s3layout

    status_doc = _load_json(s3, bucket, s3layout.source_status_key(provider, board), default=None)
    if status_doc is None:
        # collector produced no status for this source this run -> nothing to diff; skip safely
        return {"skipped": "no_source_status", "provider": provider, "board": board}

    snapshot = build_snapshot_from_status(status_doc)
    jobs = [
        CanonicalJob.model_validate(j)
        for j in _load_json(s3, bucket, s3layout.normalized_key(provider, board, dt), default=[])
    ]

    state = None
    state_key = s3layout.current_state_key(provider, board)
    raw_state = _load_json(s3, bucket, state_key, default=None)
    if raw_state is not None:
        state = DiffState.model_validate(raw_state)

    result = diff_source(state, snapshot, jobs, run_id=run_id, today=today)

    _put_json(s3, bucket, s3layout.events_key(provider, board, dt),
              [e.model_dump(mode="json") for e in result.events])
    _put_json(s3, bucket, state_key, result.state.model_dump(mode="json"))
    if result.current_jobs is not None:
        _put_json(s3, bucket, s3layout.current_jobs_key(provider, board),
                  [j.model_dump(mode="json") for j in result.current_jobs])

    return {
        "events": len(result.events),
        "frozen": result.frozen,
        "suspect": result.suspect,
        "suspect_reason": result.suspect_reason,
        "provider": provider,
        "board": board,
    }


def handler(event, context):
    import boto3

    bucket = os.environ["JPRS_BUCKET"]
    s3 = boto3.client("s3")
    provider = event["provider"]
    board = event["board_token"]
    today = datetime.now(timezone.utc)
    run_id = event.get("run_id") or today.strftime("%Y-%m-%d")
    dt = event.get("dt") or run_id  # run_id is a YYYY-MM-DD date; snapshots/events partition by it
    return run_diff(s3, bucket, provider, board, run_id=run_id, dt=dt, today=today)


def _load_json(s3, bucket, key, default="__raise__"):
    import botocore.exceptions

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read())
    except botocore.exceptions.ClientError:
        if default == "__raise__":
            raise
        return default


def _put_json(s3, bucket, key, body):
    s3.put_object(
        Bucket=bucket, Key=key,
        Body=json.dumps(body, separators=(",", ":"), default=str).encode(),
        ContentType="application/json",
    )
