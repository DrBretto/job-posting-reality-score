"""Data-compatible rollback: make persisted state readable by the previous release.

WHY THIS EXISTS
---------------
The P02 handoff asserted that the new model's additive fields "are ignored by the previous reader".
That was wrong, and the review proved it: at revision `e549a73`, `CanonicalJob` and `DiffState` both
use `ConfigDict(extra="forbid")`. Reading a current monitored-job record through the exact historical
model raises on **18** added fields (`employer_name`, `source_kind`, `verification_state`,
`provenance`, …), and the differ's own state is strict too. Two new `ChangeEventType` values would
also fail the old enum.

So a source-only rollback — even the safe worktree kind — leaves the previous code unable to read the
state the new code wrote. Reverting source is necessary but not sufficient.

THE STRATEGY, AND WHY IT IS THE SMALLEST ONE
-------------------------------------------
Downgrade the *records*, not the schema:

  1. back up every object first, under a timestamped prefix, before touching anything;
  2. drop only the keys the baseline model does not declare — no value is rewritten;
  3. preserve **every** job id and every grace clock, so the old differ sees the same population it
     saw before and cannot manufacture a removal;
  4. drop only the event records whose `event_type` the old enum cannot parse.

Alternatives considered and rejected: widening the old model (it is a historical revision and must not
be edited), telling the operator to delete or rebuild production state (destroys history and would
produce removals), and asserting tolerance without testing it (the defect being repaired).

This module is pure and offline apart from the S3 helper. Nothing here runs automatically: a
state-writing recovery is a deployment-time operator action with the backup it creates, and this
packet only rehearses it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

# Fields the baseline (`e549a73`) models declare. Anything outside these sets is dropped on
# downgrade. Derived by reading that revision, not by guessing.
BASELINE_CANONICAL_JOB_FIELDS = frozenset({
    "source_id", "job_id", "id_kind", "provider_native_id", "provider_internal_id",
    "requisition_id", "identity_low_confidence",
    "title", "department", "team", "canonical_location", "raw_location",
    "remote_hybrid_language", "employment_type", "salary", "description_text",
    "posting_url", "apply_url",
    "provider_created_at", "provider_updated_at", "provider_published_at",
    "first_seen_at", "last_seen_at",
    "content_hash", "field_hashes",
    "schema_version", "normalizer_version", "ingested_snapshot_id",
})

BASELINE_DIFF_STATE_FIELDS = frozenset({
    "source_id", "jobs", "success_count_history", "last_success_snapshot_id", "schema_version",
})

BASELINE_JOB_STATE_RECORD_FIELDS = frozenset({
    "job_id", "state", "content_hash", "field_hashes", "first_seen_at", "last_seen_at",
    "absence_count", "disappeared_at", "requisition_id", "title_norm", "canonical_location",
    "department", "team", "identity_low_confidence",
})

BASELINE_EVENT_TYPES = frozenset({
    "first-seen", "no-material-change", "materially-changed", "location-changed", "salary-changed",
    "remote-hybrid-language-changed", "disappeared", "returned", "probable-repost",
    "source-fetch-failed", "source-response-partial", "source-suspect",
})

# The baseline stamps this schema version; a downgraded record claiming 1.1.0 would be a lie about
# which shape it is in.
BASELINE_SCHEMA_VERSION = "1.0.0"


def downgrade_canonical_job(record: dict) -> dict:
    """Strip fields the baseline model does not declare. Idempotent; rewrites no value but the
    schema stamp."""
    out = {k: v for k, v in record.items() if k in BASELINE_CANONICAL_JOB_FIELDS}
    out["schema_version"] = BASELINE_SCHEMA_VERSION
    return out


def downgrade_current_jobs(records: list[dict]) -> list[dict]:
    """Downgrade a `current_jobs.json` payload.

    Every record survives. Dropping a job here would make the previous differ see it absent and,
    after its grace window, emit a disappearance for a posting that never closed.
    """
    return [downgrade_canonical_job(r) for r in records]


def downgrade_diff_state(state: dict) -> dict:
    """Downgrade a `_diff_state.json` payload, preserving job ids and grace clocks."""
    out = {k: v for k, v in state.items() if k in BASELINE_DIFF_STATE_FIELDS}
    jobs = {}
    for job_id, record in (state.get("jobs") or {}).items():
        jobs[job_id] = {
            k: v for k, v in record.items() if k in BASELINE_JOB_STATE_RECORD_FIELDS
        }
    out["jobs"] = jobs
    out["schema_version"] = BASELINE_SCHEMA_VERSION
    return out


def downgrade_events(events: list[dict]) -> tuple[list[dict], int]:
    """Keep events the baseline enum can parse; report how many were dropped.

    A dropped event is a lost *observation*, not a lost job: the event log is append-only evidence,
    and the job population lives in `current/`. Nothing about the live job set changes.
    """
    kept = [e for e in events if e.get("event_type") in BASELINE_EVENT_TYPES]
    return kept, len(events) - len(kept)


# --------------------------------------------------------------------------------------------------
# S3 orchestration — backup first, then rewrite in place
# --------------------------------------------------------------------------------------------------
def _list_keys(s3, bucket: str, prefix: str) -> list[str]:
    keys, token = [], None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        response = s3.list_objects_v2(**kwargs)
        keys.extend(item["Key"] for item in response.get("Contents", []))
        if response.get("IsTruncated"):
            token = response.get("NextContinuationToken")
        else:
            return keys


def downgrade_bucket_state(
    s3,
    bucket: str,
    *,
    dt: str,
    now: datetime | None = None,
    dry_run: bool = False,
) -> dict:
    """Back up and downgrade `current/` and `events/` so the baseline release can read them.

    Returns an operator-readable report. With `dry_run=True` nothing is written and the report
    describes what would change — which is how this gets rehearsed before it is ever approved.
    """
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    backup_prefix = f"rollback-backup/{stamp}/"

    report = {
        "dry_run": dry_run,
        "backup_prefix": backup_prefix,
        "objects_backed_up": 0,
        "backup_keys": [],
        "current_jobs_objects": 0,
        "current_jobs_records": 0,
        "diff_state_objects": 0,
        "diff_state_jobs_preserved": 0,
        "event_objects": 0,
        "events_dropped_unknown_type": 0,
        "fields_dropped": set(),
        "notes": [],
    }

    targets = [k for k in _list_keys(s3, bucket, "current/")]
    targets += [k for k in _list_keys(s3, bucket, f"events/") if f"dt={dt}" in k]

    for key in targets:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        try:
            payload = json.loads(body)
        except ValueError:
            report["notes"].append(f"{key}: not JSON, left untouched")
            continue

        if not dry_run:
            backup_key = backup_prefix + key
            s3.put_object(Bucket=bucket, Key=backup_key, Body=body,
                          ContentType="application/json")
            report["backup_keys"].append(backup_key)
        report["objects_backed_up"] += 1

        if key.endswith("current_jobs.json") and isinstance(payload, list):
            for record in payload:
                report["fields_dropped"] |= (
                    set(record) - BASELINE_CANONICAL_JOB_FIELDS
                )
            new_payload = downgrade_current_jobs(payload)
            report["current_jobs_objects"] += 1
            report["current_jobs_records"] += len(new_payload)
            assert len(new_payload) == len(payload), "downgrade must not drop a job"
        elif key.endswith("_diff_state.json") and isinstance(payload, dict):
            report["fields_dropped"] |= set(payload) - BASELINE_DIFF_STATE_FIELDS
            new_payload = downgrade_diff_state(payload)
            report["diff_state_objects"] += 1
            report["diff_state_jobs_preserved"] += len(new_payload.get("jobs", {}))
            assert len(new_payload.get("jobs", {})) == len(payload.get("jobs", {})), (
                "downgrade must not drop a tracked job"
            )
        elif "events/" in key and isinstance(payload, list):
            new_payload, dropped = downgrade_events(payload)
            report["event_objects"] += 1
            report["events_dropped_unknown_type"] += dropped
        else:
            continue

        if not dry_run:
            s3.put_object(
                Bucket=bucket, Key=key,
                Body=json.dumps(new_payload, separators=(",", ":"), default=str).encode(),
                ContentType="application/json",
            )

    report["fields_dropped"] = sorted(report["fields_dropped"])
    report["notes"].append(
        "Every job id and grace clock was preserved, so the previous release sees the same job "
        "population and cannot emit a disappearance for a posting that never closed."
    )
    if not dry_run:
        report["notes"].append(
            f"Originals are at s3://{bucket}/{backup_prefix} — restore from there to undo this."
        )
    return report
