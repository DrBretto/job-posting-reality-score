"""Five-tier S3 key builders (DATA_MODEL §7) with the PANEL_DISSENT M4 prefix split.

M4 fix: prefix-scoped S3 IAM cannot separate two files under one prefix. So the authoritative
live-job set and the collector's source-status object live under DIFFERENT top prefixes:

  collector OWNS (writes):  status/  raw/  normalized/
  differ    OWNS (writes):  current/  events/
  report    OWNS (writes):  reports/

`current/` therefore contains ONLY the differ's `current_jobs.json` (a `current/*` IAM grant to
the collector no longer implies write to the live-job set). Source status moved to `status/`.

No S3 versioning anywhere (operator hard rule); retention is via lifecycle policy. Derived tiers
carry a `schema_v=` top prefix so version-scoped replay is a clean key-prefix operation.
"""

from __future__ import annotations

from src.common.models import SCHEMA_VERSION

# ----- Tier 1a: current/ (DIFFER-owned) — authoritative live-job set, overwritten each run --------


def current_jobs_key(provider: str, board: str) -> str:
    return f"current/provider={provider}/board={board}/current_jobs.json"


def current_state_key(provider: str, board: str) -> str:
    """Differ's persisted per-source diff state (job states, grace clocks, count history)."""
    return f"current/provider={provider}/board={board}/_diff_state.json"


# ----- Tier 1b: status/ (COLLECTOR-owned) — drives "did collectors run" -----------------------


def source_status_key(provider: str, board: str) -> str:
    return f"status/provider={provider}/board={board}/_source_status.json"


def collect_sentinel_key(run_id: str, provider: str, board: str) -> str:
    """Per-task SUCCESS sentinel; written only after raw is durably in S3 (RELIABILITY §5.1)."""
    return f"status/run={run_id}/provider={provider}/board={board}/SUCCESS.json"


# ----- Tier 2: raw/ (COLLECTOR-owned) — immutable court-of-record, WORM + lifecycle ------------


def raw_snapshot_key(provider: str, board: str, dt: str, snapshot_id: str) -> str:
    return f"raw/provider={provider}/board={board}/dt={dt}/snapshot={snapshot_id}.json.gz"


def raw_receipt_key(provider: str, board: str, dt: str, snapshot_id: str) -> str:
    return f"raw/provider={provider}/board={board}/dt={dt}/receipt={snapshot_id}.json"


# ----- Tier 3: normalized/ (COLLECTOR-owned) — canonical jobs, versioned, replayable ------------


def normalized_key(provider: str, board: str, dt: str, schema_v: str = SCHEMA_VERSION) -> str:
    major = schema_v.split(".")[0]
    return f"normalized/schema_v={major}/provider={provider}/board={board}/dt={dt}/jobs.json"


# ----- Tier 4: events/ (DIFFER-owned) — change-event log, append-only ---------------------------


def events_key(provider: str, board: str, dt: str, schema_v: str = SCHEMA_VERSION) -> str:
    major = schema_v.split(".")[0]
    return f"events/schema_v={major}/provider={provider}/board={board}/dt={dt}/events.json"


# ----- Tier 5: reports/ (REPORT-owned) — daily human report + scoring output --------------------


def report_json_key(dt: str) -> str:
    return f"reports/dt={dt}/daily_report.json"


def report_md_key(dt: str) -> str:
    return f"reports/dt={dt}/daily_report.md"


# ----- Manifest (ENUMERATE-owned) — M1 completeness backbone ------------------------------------


def run_manifest_key(run_id: str) -> str:
    return f"runs/run={run_id}/RUN_OPEN.json"
