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


def digest_delivery_key(dt: str) -> str:
    return f"reports/dt={dt}/digest_delivery.json"


# ----- Manifest (ENUMERATE-owned) — M1 completeness backbone ------------------------------------


def run_manifest_key(run_id: str) -> str:
    return f"runs/run={run_id}/RUN_OPEN.json"


# ----- Tier 6: discovery/ (DISCOVERY-owned) — open-market search state --------------------------
#
# Discovery is a new writer, so it gets its own top prefix rather than borrowing one. The M4 rule
# that made `current/` differ-only applies here too: prefix-scoped IAM cannot separate two files
# under one prefix, so a writer that needs its own blast radius needs its own prefix.
#
# Discovery WRITES discovery/ and the collector-owned forward tiers for the postings it finds.
# It never writes current/ or events/ (differ-owned) or reports/ (report-owned).


def discovery_coverage_key(run_id: str) -> str:
    """Per-run coverage receipt: what was searched, what saturated, what is still queued."""
    return f"discovery/run={run_id}/coverage.json"


def discovery_state_key() -> str:
    """Persisted budgets, per-family coverage ledger, and the resumable backlog."""
    return "discovery/_discovery_state.json"


def discovery_live_key(provider: str) -> str:
    """Discovery's own live-job view for one feed — the object report assembly consumes.

    This is the discovery-side counterpart of the differ's `current/`, and it is deliberately NOT
    `current/`: that prefix is differ-owned by the M4 rule, and the two lifecycles are not the same
    question. A monitored ATS board returns the employer's WHOLE open list, so a posting's absence
    from a healthy snapshot is evidence about the posting. A discovery feed returns a moving WINDOW
    over many employers, so absence from it is evidence about the window. Reusing the differ's
    disappearance semantics here would read normal feed churn as closure.
    """
    return f"discovery/live/provider={provider}/live_jobs.json"


def discovery_owed_publication_key(provider: str) -> str:
    """One feed's observations, durably accepted and not yet folded into its live view.

    This is discovery's ACCEPTANCE record, and it is per provider for two reasons.

    It is the object whose write makes a round's observations recoverable, so it is the FIRST
    durable write of that provider's round — nothing precedes it, which is what makes the acceptance
    statement decidable rather than a label. P08 recorded the debt once, at an aggregate key, after
    every forward-tier write had already committed: refusing that single write stranded postings that
    were already durably normalized, because the same-day retry met a changed feed window and
    overwrote `normalized/` for that `dt`.

    Per provider, one refused write costs that feed's new batch and nothing else — every peer's
    accepted work and that feed's own earlier batches stay on record. The key is still KNOWN rather
    than discovered: it is derived from the provider, and the provider list comes from the connector
    registry, so recovery never searches a prefix and never deletes. The role's `discovery/`-scoped
    `ListBucket` is what lets a read list this exact key to establish that it has not been written
    yet; without it "not written yet" could not be told from "denied" and the first round stopped.
    """
    return f"discovery/owed/provider={provider}/owed_publication.json"


def discovery_pending_publication_key() -> str:
    """The whole-system view of what publication is owed, across every feed.

    No longer the acceptance record (see `discovery_owed_publication_key`), and no longer the object
    recovery depends on. It is still written after each change, because the coverage receipt and the
    morning report read the owed set from one place, and it is still READ on load so that a debt
    written by the currently deployed code is picked up and settled rather than orphaned.
    """
    return "discovery/_pending_publication.json"


def source_growth_key() -> str:
    """Candidate-source growth ledger + sticky operator disables."""
    return "discovery/_source_growth.json"


def manual_import_key(dt: str) -> str:
    """Operator-supplied URLs awaiting verification (the supplementary import path)."""
    return f"discovery/manual/dt={dt}/imports.json"


def proposed_registry_key(run_id: str) -> str:
    """Registry rows discovery PROPOSES. Applying them stays an operator action."""
    return f"discovery/run={run_id}/proposed_registry.json"
