"""Deterministic daily report renderer (markdown + json).

Guarantees carried forward from V1:
  - Never-fake vocabulary guard: system-authored language is scanned for banned tokens as whole
    words; provider-supplied strings are redacted before scanning because they are evidence labels,
    not system claims.
  - Every reported change cites evidence_refs (snapshot_id / event_id).
  - 100% deterministic, slot-filled from stored evidence. The narrator is never invoked.

Three things this version repairs, all named in the September 24 plan:

1. HEALTH WAS ONE AXIS AND ONE OF ITS BRANCHES WAS DEAD.
   `compute_run_health` computed `material` and then returned `VERIFIED_QUIET` on *both* sides of its
   own conditional, so the variable did nothing. Worse, fifteen successful configured fetches read as
   an all-clear. Health is now four independent axes — collection, discovery coverage, freshness,
   interpretation — and no axis is permitted to phrase itself as market coverage.

2. CANDIDATES WERE HIDDEN IN JSON.
   A 20-row cap ended with "N additional matching roles are retained in JSON", which is not a human
   handoff. The digest keeps a short highlights section AND the same document now carries the
   complete readable list: every retained credible role, with a direct link and a reason.

3. EMPLOYER WAS A PROPERTY OF THE SOURCE.
   A hardcoded fifteen-entry `_COMPANY_LABELS` map translated board tokens into company names. That
   map is gone: the employer comes off the job, which is what lets a posting from an employer nobody
   has named yet render correctly.
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
    HistoryStatus,
    RunHealth,
    ScreenOutcome,
    SnapshotStatus,
    SourceKind,
    VerificationState,
)
from src.candidate.ownership import OwnershipAssessment, TeamStructure
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
    ChangeEventType.SOURCE_SUSPECT: "source coverage is in question (removals suppressed)",
    ChangeEventType.SOURCE_SEGMENT_CLOSED: "a department segment was confirmed closed",
    ChangeEventType.SOURCE_DISCOVERY_PARTIAL: "discovery covered part of its query plan",
}

_JOB_SCOPED = {
    ChangeEventType.FIRST_SEEN, ChangeEventType.MATERIALLY_CHANGED, ChangeEventType.LOCATION_CHANGED,
    ChangeEventType.SALARY_CHANGED, ChangeEventType.REMOTE_HYBRID_LANGUAGE_CHANGED,
    ChangeEventType.DISAPPEARED, ChangeEventType.RETURNED, ChangeEventType.PROBABLE_REPOST,
}
_MATERIAL = _JOB_SCOPED - {ChangeEventType.FIRST_SEEN}  # material for the quiet/changed decision
_SOURCE_SCOPED = {
    ChangeEventType.SOURCE_FETCH_FAILED, ChangeEventType.SOURCE_RESPONSE_PARTIAL,
    ChangeEventType.SOURCE_SUSPECT, ChangeEventType.SOURCE_SEGMENT_CLOSED,
    ChangeEventType.SOURCE_DISCOVERY_PARTIAL,
}
# Highlights cap for the digest's short section ONLY. It never hides a candidate: the complete
# readable list below it is uncapped.
_MAX_HIGHLIGHTS = 20
_MAX_EVENT_ITEMS = 15


# Documented provider lag, so a feed's publication date is never presented as the employer's own.
# Remotive's legal notice states its feed is delayed 24 hours.
SOURCE_LAG_HOURS: dict[str, int] = {"remotive": 24}
# Adzuna's query uses max_days_old=30, so its rows can be up to a month old by construction.
SOURCE_LOOKBACK_DAYS: dict[str, int] = {"adzuna": 30}

FRESH_WINDOW_HOURS = 24


def _aware(value: datetime | None) -> datetime | None:
    """Coerce a possibly-naive stored datetime to UTC.

    Defensive: a record written before `_iso` normalized zones would otherwise make the whole report
    raise rather than render.
    """
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def age_label(
    *,
    provider_published_at: datetime | None,
    provider_updated_at: datetime | None,
    first_seen_at: datetime | None,
    now: datetime,
    source_lag_hours: int | None = None,
) -> str:
    """Human age, naming WHICH date it rests on and never inventing one.

    The four dates are not synonyms (plan §3). A feed publication date is the provider's, not
    necessarily the employer's, so stated lag travels with it. With no date at all the answer is
    "unknown", qualified by when JPRS first saw it — not a guess.
    """
    now = _aware(now)
    provider_published_at = _aware(provider_published_at)
    provider_updated_at = _aware(provider_updated_at)
    first_seen_at = _aware(first_seen_at)

    def hours(then: datetime) -> float:
        return max(0.0, (now - then).total_seconds() / 3600.0)

    if provider_published_at is not None:
        age = hours(provider_published_at)
        label = f"published {_humanize(age)} ago (provider date)"
        if source_lag_hours:
            label += f"; provider publishes on a {source_lag_hours}h delay, so the employer's own date may be earlier"
        return label
    if provider_updated_at is not None:
        return (
            f"no publication date; employer last edited it {_humanize(hours(provider_updated_at))} "
            "ago (an edit is not a new posting)"
        )
    if first_seen_at is not None:
        return (
            f"age unknown — the source published no date; first seen by JPRS "
            f"{_humanize(hours(first_seen_at))} ago, which is a floor on its age, not its age"
        )
    return "age unknown and never observed"


def _humanize(hours_value: float) -> str:
    if hours_value < 1:
        return "under an hour"
    if hours_value < 48:
        return f"{int(round(hours_value))}h"
    return f"{int(hours_value // 24)}d"


def _report_dt_of(key: str) -> str:
    """The `dt=` partition a report key belongs to, or "" when the key is not partitioned."""
    for part in key.split("/"):
        if part.startswith("dt="):
            return part[3:]
    return ""


@dataclass
class RunTiming:
    """When this round actually looked, and when the last round that reported actually finished.

    Both come from durable artifacts other stages already write, never from the wall clock and never
    from the calendar day. The end of the UTC calendar day — which this module used before — made a
    07:05 posting look like it arrived seventeen hours in the future, and made every "since the
    previous round" comparison impossible because there was no previous boundary to compare against.
    """

    run_started_at: datetime | None = None
    previous_run_at: datetime | None = None
    previous_run_id: str | None = None
    basis: str = "unknown"
    cold_start_run: bool = False
    # Which key of the previous report the identity set was recovered from, and whether that key is
    # capped. A pre-discovery report carried its rows ONLY in `top_matches`, which is capped at the
    # highlight limit — so it evidences what the operator was SHOWN, and nothing about postings it
    # did not list. Keeping the distinction stops a recovered boundary from being read as a complete
    # census of the previous round's candidates.
    previously_reported_source: str | None = None
    previously_reported_truncated: bool = False
    # The job ids the previous round's report actually showed. This, not a timestamp comparison, is
    # what "new since the last round" means: a posting Brett has not been shown yet. Identity needs
    # no clock, so it cannot be skewed by a replay, a late report, or two stages on different clocks.
    previously_reported_ids: frozenset[str] = frozenset()

    def to_json(self) -> dict:
        return {
            "run_started_at": self.run_started_at.isoformat() if self.run_started_at else None,
            "previous_run_at": self.previous_run_at.isoformat() if self.previous_run_at else None,
            "previous_run_id": self.previous_run_id,
            "basis": self.basis,
            "cold_start_run": self.cold_start_run,
            "previously_reported_count": len(self.previously_reported_ids),
            "previously_reported_source": self.previously_reported_source,
            "previously_reported_truncated": self.previously_reported_truncated,
            # Which mechanism decided "new since the last round". `reported-ids` is exact; the
            # timestamp fallback applies only when a previous report exists but listed no rows.
            "boundary": "reported-ids" if self.previously_reported_ids else (
                "timestamp" if self.previous_run_at else "cold-start"),
        }


def resolve_run_timing(s3, bucket: str, run_id: str, dt: str, *, now: datetime | None = None) -> RunTiming:
    """Read this round's start and the previous reported round's finish out of S3.

    `run_started_at` is the RUN_OPEN manifest's `opened_at`, written by ENUMERATE before any
    collection — the earliest truthful mark of "this round started looking".

    `previous_run_at` is the `report_generated_at` of the most recent EARLIER persisted report. A
    persisted report is itself the evidence that the round got as far as reporting, so a round that
    failed leaves none and is skipped rather than being credited with an observation it never made.
    Using the previous report's generation time, not its start, means a posting first seen partway
    through that round is not re-announced the next morning.

    The current run's own report is excluded, so a retry compares against the previous round instead
    of against its own first attempt and reporting zero new arrivals.
    """
    from src.common import s3layout

    manifest = _load_json(s3, bucket, s3layout.run_manifest_key(run_id), default=None) or {}
    started = _parse_datetime(manifest.get("opened_at")) if manifest.get("opened_at") else None
    basis = "manifest.opened_at"
    if started is None:
        # No manifest: the report still has a real invocation time, and saying so is better than
        # inventing a start or falling back to the end of the calendar day.
        started = _aware(now) or datetime.now(timezone.utc)
        basis = "report_invocation_time (RUN_OPEN manifest absent)"

    # Which reports are EARLIER is decided by the round they belong to (the dt in the key), and the
    # boundary VALUE is that round's finish. Ordering by the stored wall-clock stamp instead would
    # break on any replay of an earlier day, and would compare two different clocks.
    previous_at: datetime | None = None
    previous_id: str | None = None
    reported_ids: frozenset[str] = frozenset()
    reported_source: str | None = None
    reported_truncated = False
    candidates = sorted(
        (key for key in _list_keys(s3, bucket, "reports/") if key.endswith("report.json")),
        key=_report_dt_of, reverse=True,
    )
    for key in candidates:
        key_dt = _report_dt_of(key)
        if key_dt and key_dt >= dt:
            # Not an earlier round. This is also what stops a RETRY of this round from reading its
            # own first attempt as "the previous round" and reporting nothing new.
            continue
        prior = _load_json(s3, bucket, key, default=None) or {}
        # The previous round's FINISH, not its start: a posting first seen partway through that
        # round was already in its report and must not be re-announced the next morning.
        generated = prior.get("report_generated_at")
        stamp = _parse_datetime(generated) if generated else None
        if stamp is None:
            # A report written by an earlier release, before this field existed. Its run start is the
            # best durable mark it carries; it is earlier than its finish, so freshness errs toward
            # showing a row rather than hiding one.
            legacy = (prior.get("timing") or {}).get("run_started_at")
            stamp = _parse_datetime(legacy) if legacy else None
        # Which rows that report actually showed Brett. The new format carries every retained
        # candidate in `complete_candidate_list`; a report written before that key existed carried
        # its rows only in `top_matches`, capped at the highlight limit, with an EMPTY
        # `complete_candidate_list` beside it. Reading only the first key made such a report look
        # like a round that showed nothing, so the boundary was discarded and every posting came
        # back as new the following morning.
        #
        # The fallback recovers exactly the identities that report evidences — the ones it listed —
        # and records that the list was capped. It does NOT treat the cap as a census: a posting
        # missing from a capped list was not shown to Brett either, which is precisely what
        # "new since the last report" asks, so those postings are correctly still new.
        ids = frozenset(
            row.get("job_id") for row in prior.get("complete_candidate_list", [])
            if row.get("job_id")
        )
        id_source = "complete_candidate_list" if ids else None
        truncated = False
        if not ids:
            ids = frozenset(
                row.get("job_id") for row in prior.get("top_matches", []) if row.get("job_id")
            )
            if ids:
                id_source, truncated = "top_matches", True
        if stamp is None and not ids:
            # Nothing usable in this report at all: keep looking further back.
            continue
        # The id list is taken even when no timestamp could be read. Identity needs no clock, so a
        # report from the previous release still answers "has Brett seen this posting" exactly — and
        # the first round after a deploy is the one case where that matters most.
        previous_at, previous_id = (_aware(stamp) if stamp else None,
                                    prior.get("run_id") or key_dt or key)
        reported_ids = ids
        reported_source, reported_truncated = id_source, truncated
        break

    return RunTiming(
        run_started_at=_aware(started),
        previous_run_at=previous_at,
        previous_run_id=previous_id,
        basis=basis,
        cold_start_run=previous_id is None,
        previously_reported_ids=reported_ids,
        previously_reported_source=reported_source,
        previously_reported_truncated=reported_truncated,
    )


def cold_start_sources(
    jobs: list[CanonicalJob],
    observations: dict[str, int] | None = None,
) -> set[str]:
    """Sources where `first_seen_at` carries no freshness information.

    On a source's FIRST successful observation every posting shares one `first_seen_at`: they did not
    all arrive since the last round, we simply started watching. Counting them as fresh arrivals
    would overstate freshness on the very first run.

    `observations` is the source's real success history from `current/state`. It is what decides,
    because timestamp cardinality alone cannot: a warm source that happens to carry ONE posting also
    has one distinct stamp, and reading that as a cold start suppressed a genuinely new arrival at
    every single-opening source. Cardinality is used only for a source with no history recorded.
    """
    seen: dict[str, set] = {}
    for job in jobs:
        seen.setdefault(job.source_id, set()).add(job.first_seen_at)
    cold: set[str] = set()
    for source, stamps in seen.items():
        count = (observations or {}).get(source)
        if count is not None:
            # Authoritative: one recorded successful observation means this is the first look.
            if count <= 1:
                cold.add(source)
            continue
        if len(stamps) <= 1:
            cold.add(source)
    return cold


def is_fresh_arrival(
    job: CanonicalJob,
    *,
    now: datetime,
    previous_run_at: datetime | None,
    cold_start: frozenset[str] | set[str] = frozenset(),
    previously_reported: frozenset[str] | set[str] | None = None,
) -> bool:
    """True when this posting is newly available to act on.

    Two independent ways to qualify, because either alone would miss cases:
      - the provider says it was published inside the fresh window, or
      - the previous round's report did not show it AND the observation is informative
        (see `cold_start_sources`). When no previous report is available, when JPRS first observed
        it falls back in as the weaker signal.
    Freshness NEVER excludes anything; it only decides which section a row is highlighted in.
    """
    now = _aware(now)
    published = _aware(job.provider_published_at)
    first_seen = _aware(job.first_seen_at)
    previous_run_at = _aware(previous_run_at)
    if published is not None:
        if (now - published).total_seconds() <= FRESH_WINDOW_HOURS * 3600:
            return True
    if job.source_id in cold_start:
        # First run for this source: first-seen tells us when WE started looking, not when the
        # employer posted. Publication date above is the only admissible evidence.
        return False
    if previously_reported is not None:
        # The previous round's report is on hand, so "new" is exact: Brett has not been shown this
        # posting. No clock arithmetic, so a weekend gap, a failed round, a retry and a replay all
        # give the same answer, and a posting first seen partway through the previous round — which
        # that report already showed — does not come back as new.
        return job.job_id not in previously_reported
    if previous_run_at is not None and first_seen is not None:
        # No previous report to compare against: fall back to when we first saw it.
        if first_seen >= previous_run_at:
            return True
    return False


# --------------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------------
@dataclass
class CoverageInput:
    """What discovery actually covered. Deliberately shaped to state what it did NOT cover."""

    discovery_attempted: list[str] = field(default_factory=list)
    discovery_succeeded: list[str] = field(default_factory=list)
    query_families_total: int = 0
    query_families_covered: int = 0
    query_families_saturated: list[str] = field(default_factory=list)
    query_families_deferred: list[str] = field(default_factory=list)
    query_families_never_run: list[str] = field(default_factory=list)
    backlog_items: int = 0
    backlog_reason: str | None = None
    budgets: dict = field(default_factory=dict)
    # Sources implemented but not runnable because a credential is absent. Named, not hidden.
    credential_gated: list[dict] = field(default_factory=list)
    inaccessible: list[dict] = field(default_factory=list)
    attributions: list[str] = field(default_factory=list)
    previously_unseen_employers: list[str] = field(default_factory=list)
    admission_summary: dict = field(default_factory=dict)
    policy_projection_note: str | None = None
    # The application-history projection's own state, kept out of `policy_projection_note` because
    # the two answer different questions and a reader needs this one on its own. See
    # `_history_projection_state`: missing / stale / current / known_empty are four distinguishable
    # answers, and before this they were two — the report announced a MISSING projection and said
    # nothing at all about a stale one, which from inside the report looks exactly like a current one.
    history_projection: dict = field(default_factory=dict)
    # Postings discovery captured durably but has not yet folded into a feed's live view, so this
    # report cannot show them. provider -> [{run_id, observed_at, job_ids, ...}]. Read from the
    # coverage receipt, never inferred: an empty candidate list and an unpublished capture look
    # identical from here, and only one of them means the operator saw everything there was.
    pending_publication: dict = field(default_factory=dict)

    def pending_publication_job_count(self) -> int:
        return sum(
            len(batch.get("job_ids", []))
            for batches in self.pending_publication.values() for batch in batches
        )


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
    # --- open-market additions (all optional so the monitoring-only path is unchanged) -----------
    screen_results: dict = field(default_factory=dict)   # job_id -> ScreenResult
    # job_id -> OwnershipAssessment. Optional: a report built without it behaves exactly as before,
    # which keeps the monitoring-only path and every existing fixture unchanged.
    ownership_results: dict = field(default_factory=dict)
    history_status: dict = field(default_factory=dict)   # job_id -> (HistoryStatus, note|None)
    coverage: CoverageInput | None = None
    dedup: dict = field(default_factory=dict)
    # Run timing, for the fresh-first cohort. Optional: without them the report simply has no
    # "since the last round" boundary and falls back to the provider publication window.
    run_started_at: datetime | None = None
    previous_run_at: datetime | None = None
    # source_id -> count of recorded successful observations, from current/state. Decides cold start.
    source_observations: dict[str, int] = field(default_factory=dict)
    # Job ids the previous round's report showed; None when there is no previous report to read.
    previously_reported_ids: frozenset[str] | None = None
    timing: dict = field(default_factory=dict)
    # Provider text the differ holds for the postings this run's events name — above all the ones
    # that disappeared and so are not in `jobs` — because its notes quote it (a DISAPPEARED note
    # names the posting's department segment, lowercased). Read from each board's
    # `_diff_state.json`; used only to recognize that source text inside those notes.
    state_source_text: set[str] = field(default_factory=set)
    # What the round actually evaluated. Empty for a ReportInput built directly (tests, fixtures),
    # which the renderer treats as "everything in `jobs` was evaluated".
    evaluation: dict = field(default_factory=dict)
    # The company-first financing watchlist (discovery/signals/latest.json). Never candidates.
    company_signals: dict | None = None
    # Memo for `_cold_start(inp)`. Keyed on the job list's identity and length so a caller that
    # replaces or extends `jobs` after construction gets a fresh answer rather than a stale one.
    _cold_start_memo: tuple | None = field(default=None, repr=False, compare=False)


def _cold_start(inp: ReportInput) -> set[str]:
    """`cold_start_sources` for this report, computed once.

    It is a property of the whole population, not of a row, yet `_match_json` recomputed it twice per
    rendered row. At 4,671 postings and 2,792 rendered rows that was 26 million `set.add` calls and
    15.5 of the 51 seconds a local replay of the 2026-11-11 report took — the largest single cost in
    the report, and pure repetition. Same inputs, same answer, once.
    """
    key = (id(inp.jobs), len(inp.jobs), id(inp.source_observations))
    memo = inp._cold_start_memo
    if memo is None or memo[0] != key:
        memo = (key, cold_start_sources(inp.jobs, inp.source_observations))
        inp._cold_start_memo = memo
    return memo[1]


# --------------------------------------------------------------------------------------------------
# Health: four axes, none of which may claim market coverage
# --------------------------------------------------------------------------------------------------
@dataclass
class HealthAxes:
    collection: RunHealth
    collection_missing: list[str]
    discovery: str
    discovery_detail: str
    freshness: str
    interpretation: str
    interpretation_detail: str

    def to_json(self) -> dict:
        return {
            "collection": self.collection.value,
            "collection_missing_sources": self.collection_missing,
            "discovery_coverage": self.discovery,
            "discovery_coverage_detail": self.discovery_detail,
            "freshness": self.freshness,
            "interpretation": self.interpretation,
            "interpretation_detail": self.interpretation_detail,
        }


def compute_run_health(inp: ReportInput) -> tuple[RunHealth, list[str]]:
    """Collection health only: did every EXPECTED source produce a SUCCESS sentinel?

    Unchanged contract for the monitoring path, with the dead branch removed. `material` used to be
    computed here and then discarded by a conditional whose arms were identical; whether anything
    changed is a separate question from whether collection completed, and it is answered by the
    freshness axis instead of being folded into this one.
    """
    if not inp.manifest_present:
        return RunHealth.NO_RUN, list(inp.expected_sources)
    missing = sorted(set(inp.expected_sources) - set(inp.succeeded_sources))
    if missing:
        return RunHealth.INCOMPLETE, missing
    return RunHealth.VERIFIED_QUIET, missing


def compute_health_axes(inp: ReportInput) -> HealthAxes:
    collection, missing = compute_run_health(inp)
    cov = inp.coverage

    # --- discovery coverage -----------------------------------------------------------------------
    if cov is None or not cov.discovery_attempted:
        discovery = "NOT-RUN"
        discovery_detail = (
            "no employer-independent discovery ran in this report; the results below describe the "
            "configured employers that were monitored, which is not a search of the open market"
        )
    else:
        failed = sorted(set(cov.discovery_attempted) - set(cov.discovery_succeeded))
        pending_jobs = cov.pending_publication_job_count()
        incomplete = bool(
            failed or cov.backlog_items or cov.query_families_deferred
            or cov.query_families_never_run or cov.query_families_saturated
            or cov.credential_gated or pending_jobs
        )
        discovery = "PARTIAL" if incomplete else "PLAN-COVERED"
        bits = [
            f"{len(cov.discovery_succeeded)}/{len(cov.discovery_attempted)} discovery sources "
            f"returned results",
            f"{cov.query_families_covered}/{cov.query_families_total} query families covered",
        ]
        if failed:
            bits.append(f"failed: {', '.join(failed)}")
        if cov.query_families_saturated:
            bits.append(
                f"hit a result ceiling (more may exist): {', '.join(cov.query_families_saturated)}"
            )
        if cov.query_families_deferred:
            bits.append(f"deferred to a later run: {', '.join(cov.query_families_deferred)}")
        if cov.query_families_never_run:
            bits.append(f"never run yet: {', '.join(cov.query_families_never_run)}")
        if cov.backlog_items:
            bits.append(f"{cov.backlog_items} query items queued and resumable")
        if cov.credential_gated:
            bits.append(
                "not runnable without a credential: "
                + ", ".join(sorted(g.get("provider", "?") for g in cov.credential_gated))
            )
        if pending_jobs:
            # Captured but not yet published. Distinct from every other entry here: the postings
            # exist and are durable, so this is not a gap in what was searched but a gap between
            # what was found and what this report could show.
            bits.append(
                f"{pending_jobs} already-captured posting(s) are awaiting publication into "
                f"{', '.join(sorted(cov.pending_publication))} and cannot appear below yet"
            )
        discovery_detail = "; ".join(bits)

    # --- freshness --------------------------------------------------------------------------------
    material = [e for e in inp.events if e.event_type in _MATERIAL]
    first_seen = [e for e in inp.events if e.event_type == ChangeEventType.FIRST_SEEN]
    if first_seen or material:
        freshness = "CHANGED"
    else:
        freshness = "NO-CHANGE-OBSERVED"

    # --- interpretation health --------------------------------------------------------------------
    suspect = [e for e in inp.events if e.event_type == ChangeEventType.SOURCE_SUSPECT]
    partial = [e for e in inp.events if e.event_type == ChangeEventType.SOURCE_RESPONSE_PARTIAL]
    failed_fetch = [e for e in inp.events if e.event_type == ChangeEventType.SOURCE_FETCH_FAILED]
    closed = [e for e in inp.events if e.event_type == ChangeEventType.SOURCE_SEGMENT_CLOSED]
    leads = sum(
        1 for j in inp.jobs if j.verification_state == VerificationState.UNVERIFIED_LEAD
    )
    if suspect or partial or failed_fetch:
        interpretation = "DEGRADED"
        parts = []
        if failed_fetch:
            parts.append(f"{len(failed_fetch)} source(s) could not be downloaded")
        if partial:
            parts.append(f"{len(partial)} source(s) returned an incomplete response")
        if suspect:
            parts.append(
                f"{len(suspect)} source(s) have coverage in question, so their removals are held"
            )
        interpretation_detail = "; ".join(parts)
    else:
        interpretation = "CLEAN"
        interpretation_detail = "no source-level condition is suppressing removals"
    if closed:
        interpretation_detail += (
            f"; {len(closed)} previously-held department segment(s) were confirmed closed and "
            "released this run"
        )
    if leads:
        interpretation_detail += (
            f"; {leads} posting(s) are aggregator leads whose employer posting has not been "
            "confirmed directly"
        )

    return HealthAxes(
        collection=collection,
        collection_missing=missing,
        discovery=discovery,
        discovery_detail=discovery_detail,
        freshness=freshness,
        interpretation=interpretation,
        interpretation_detail=interpretation_detail,
    )


# --------------------------------------------------------------------------------------------------
# rendering helpers
# --------------------------------------------------------------------------------------------------
def _evidence_str(e: ChangeEvent) -> str:
    return f"[snapshot={e.snapshot_id}, event={e.event_id}]"


def _employer(job: CanonicalJob, source_labels: dict[str, str]) -> str:
    """Employer for display, from the JOB.

    The former hardcoded company-label table is deliberately gone. The registry's operator-curated
    slug is still honored as a fallback for a board source that did not state a company name.
    """
    if job.employer_name:
        return job.employer_name
    slug = source_labels.get(job.source_id) or job.source_id.partition(":")[2] or job.source_id
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _source_employer(source_id: str, source_labels: dict[str, str]) -> str:
    slug = source_labels.get(source_id) or source_id.partition(":")[2] or source_id
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _md_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")


def _job_link(job: CanonicalJob) -> str:
    title = _md_text(job.title)
    url = job.posting_url or job.apply_url or ""
    return f"[{title}]({url})" if url else title


def _screen(inp: ReportInput, job_id: str):
    return inp.screen_results.get(job_id)


def _history(inp: ReportInput, job_id: str) -> tuple[HistoryStatus, str | None]:
    entry = inp.history_status.get(job_id)
    if entry is None:
        return HistoryStatus.NEW, None
    if isinstance(entry, tuple):
        return entry
    return entry, None


def _ownership(inp: ReportInput, job_id: str) -> OwnershipAssessment | None:
    return inp.ownership_results.get(job_id)


def _ownership_retained(inp: ReportInput, card: DimensionScorecard) -> bool:
    """A plausible software-ownership opening that the fit band gate alone would erase.

    `APPLICATION_WORKFLOW.md` § "Broad ownership and first/sole-engineer preference": *"Keep eligible
    broad-ownership roles available for human/LLM review even when an AI-oriented keyword score is
    low; scoring may prioritize effort, not silently erase plausible openings."*

    Before this path existed, a card reached a readable section only at `brett_fit >= 0.40`. That
    score is AI-weighted by construction — its title lane pays 0.30 for `agentic`, and an ordinary
    internal-applications title matches no title lane at all — so a remote internal-applications role
    at an unknown ordinary employer landed in `below_fit_threshold_job_ids`: a bare identity in JSON,
    with no title, no link and no reason anywhere a human reads.

    Four things this is NOT, each load-bearing:

      - It is not an unconditional promotion. Admission requires the POSTING to have established
        broad or first/sole ownership. Silence establishes nothing and is not admitted.
      - It does not weaken a hard exclusion. A screening EXCLUDED verdict still drops the card, and
        so do scoring's two verified facts about the role: a non-target title and an ineligible
        geography. Only the fit NUMBER is set aside here, because only the number is an artifact of
        AI-keyword weighting.
      - It does not promote anything into "strong". An ownership-retained card lands in the
        needs-a-check section, ranked last, with its evidence on the row.
      - It does not infer ownership. See `src/candidate/ownership.py`: no title, headcount or
        company-size reading anywhere in it.
    """
    if card.brett_fit.band in (Band.HIGH, Band.MEDIUM) and not card.excluded:
        return False  # already admitted on fit; this path adds nothing
    detail = card.brett_fit.detail
    if int(detail.get("blocked_role", 0)) or int(detail.get("blocked_geography", 0)):
        # Verified facts about the role, not a keyword score. A sales title and an ineligible
        # worksite stay excluded however broad the ownership language is.
        return False
    screen = _screen(inp, card.job_id)
    if screen is not None and screen.outcome == ScreenOutcome.EXCLUDED.value:
        return False
    assessment = _ownership(inp, card.job_id)
    return assessment is not None and assessment.is_broad_ownership_candidate


def _ranked(inp: ReportInput) -> list[DimensionScorecard]:
    """Every credible card, ranked. Screening EXCLUDED cards are handled in their own section."""
    eligible = [
        card for card in inp.scorecards
        if (not card.excluded and card.brett_fit.band in (Band.HIGH, Band.MEDIUM))
        or _ownership_retained(inp, card)
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


def _why_fit(card: DimensionScorecard) -> str:
    """A short human reason, not a restatement of the number."""
    detail = card.brett_fit.detail
    signals = _signal_summary(card)
    path = str(detail.get("recall_path", ""))
    bits = []
    if signals:
        bits.append(f"matches on {signals}")
    if path == "work-evidence":
        bits.append("ordinary title, but the described work is in lane")
    elif path == "work-evidence-nontechnical-title":
        bits.append("title is outside the usual lane; kept for the work described")
    if detail.get("is_stretch_level"):
        bits.append("stretch level — judge the actual scope")
    geography = str(detail.get("geography", ""))
    if geography:
        bits.append(geography.replace("-", " "))
    return "; ".join(bits) or "scored on stored evidence"


def _gaps(inp: ReportInput, job: CanonicalJob, card: DimensionScorecard) -> str:
    """Important gaps and process checks — the half of the row that prevents wasted mornings."""
    bits: list[str] = []
    screen = _screen(inp, job.job_id)
    if screen is not None:
        for hit in screen.pending_checks:
            bits.append(hit.reason)
    if job.verification_state == VerificationState.UNVERIFIED_LEAD:
        bits.append("aggregator lead: confirm against the employer posting before preparing")
    if job.salary is None:
        bits.append("no published compensation")
    if job.identity_low_confidence:
        bits.append("posting identity is low confidence at this source")
    if card.application_priority.band == Band.UNKNOWN:
        bits.append("too few observations to assess hiring activity yet")
    return "; ".join(bits[:4])


def _dates(job: CanonicalJob) -> str:
    """Four distinct dates, never interchanged. An imported posting is not 'newly posted'."""
    parts = []
    if job.provider_published_at:
        parts.append(f"employer published {job.provider_published_at.date()}")
    if job.provider_updated_at:
        parts.append(f"employer updated {job.provider_updated_at.date()}")
    if job.first_seen_at:
        parts.append(f"first seen by JPRS {job.first_seen_at.date()}")
    if job.verified_at:
        parts.append(f"last verified {job.verified_at.date()}")
    return "; ".join(parts)


def _location(job: CanonicalJob) -> str:
    base = job.raw_location or job.canonical_location or "location not stated"
    if job.secondary_locations:
        base += f" (also: {', '.join(job.secondary_locations[:3])})"
    return base


def _comp(job: CanonicalJob) -> str:
    if job.salary is None:
        return "compensation not published"
    lo, hi = job.salary.min, job.salary.max
    if lo and hi:
        return f"{lo:,.0f}-{hi:,.0f} {job.salary.currency or ''}".strip()
    if lo or hi:
        return f"{(lo or hi):,.0f} {job.salary.currency or ''}".strip()
    return "compensation published without a stated range"


def _match_json(card: DimensionScorecard, job: CanonicalJob, inp: ReportInput) -> dict:
    screen = _screen(inp, job.job_id)
    status, note = _history(inp, job.job_id)
    return {
        "source_id": card.source_id,
        "job_id": card.job_id,
        "employer": _employer(job, inp.source_labels),
        "source_kind": job.source_kind.value,
        "discovery_query": job.discovery_query,
        "discovery_query_family": job.discovery_query_family,
        "title": job.title,
        "location": _location(job),
        "remote_mode": job.remote_hybrid_language.value,
        "employment_type": job.employment_type.value,
        "compensation": _comp(job),
        "posting_url": job.posting_url or job.apply_url or None,
        "apply_url": job.apply_url or job.posting_url or None,
        "verification_state": job.verification_state.value,
        "uncertainty": list(job.uncertainty),
        "provider_published_at": (
            job.provider_published_at.isoformat() if job.provider_published_at else None
        ),
        "provider_updated_at": (
            job.provider_updated_at.isoformat() if job.provider_updated_at else None
        ),
        "first_seen_at": job.first_seen_at.isoformat() if job.first_seen_at else None,
        "verified_at": job.verified_at.isoformat() if job.verified_at else None,
        "fit_score": card.brett_fit.score,
        "fit_band": card.brett_fit.band.value,
        "priority_score": card.application_priority.score,
        "priority_band": card.application_priority.band.value,
        "priority_confidence": card.application_priority.confidence,
        "recall_path": card.brett_fit.detail.get("recall_path"),
        "why_fit": _why_fit(card),
        "gaps_and_checks": _gaps(inp, job, card),
        "signals": _signal_summary(card),
        "screen_outcome": screen.outcome if screen is not None else None,
        "screen_detail": screen.to_json() if screen is not None else None,
        # Ownership scope, carried whole so a reviewer can see the phrase each verdict rests on.
        # `None` when the assessment was not run, which is different from an assessment that found
        # nothing — and both are different from confirmed sole ownership.
        "ownership": (
            _ownership(inp, job.job_id).to_json()
            if _ownership(inp, job.job_id) is not None else None
        ),
        "retained_on_ownership_evidence": _ownership_retained(inp, card),
        "age_label": _age_of(job, inp, inp.run_started_at
                             or datetime.fromisoformat(f"{inp.dt}T23:59:59+00:00")),
        "is_fresh_arrival": is_fresh_arrival(
            job,
            now=inp.run_started_at or datetime.fromisoformat(f"{inp.dt}T23:59:59+00:00"),
            previous_run_at=inp.previous_run_at,
            cold_start=_cold_start(inp),
            previously_reported=inp.previously_reported_ids,
        ),
        "first_observation_run_for_source": job.source_id in _cold_start(inp),
        "source_lag_hours": SOURCE_LAG_HOURS.get(job.source_id.partition(":")[0]),
        "source_lookback_days": SOURCE_LOOKBACK_DAYS.get(job.source_id.partition(":")[0]),
        "history_status": status.value if hasattr(status, "value") else str(status),
        "history_note": note,
        "provenance": [p.model_dump(mode="json") for p in job.provenance],
        "possible_duplicate_of": list(job.possible_duplicate_of),
    }


def _event_subject(event: ChangeEvent, jobs_by_id: dict[str, CanonicalJob], inp: ReportInput) -> str:
    job = jobs_by_id.get(event.job_id or "")
    if job is None:
        return str(event.job_id or event.source_id)
    return f"{_job_link(job)} at {_employer(job, inp.source_labels)}"


def _source_values(inp: ReportInput) -> list[str]:
    """Provider-supplied strings that may legitimately contain otherwise guarded vocabulary.

    Discovery widens this a lot: employer names, industries and screening evidence spans are all
    provider text now, and an employer legitimately named "Real Estate Partners" must not blow up
    the report.
    """
    from src.common.normalize import normalize_employer, normalize_title_for_matching

    values: set[str] = set(inp.source_labels.values()) | set(inp.expected_sources)
    for job in inp.jobs:
        values.update(filter(None, (
            job.source_id, job.job_id, job.title, job.raw_location, job.canonical_location,
            job.posting_url, job.apply_url, job.employer_name, job.employer_domain,
            job.employer_careers_url, job.industry, job.job_level, job.department, job.team,
            job.discovery_query, job.discovery_query_family, job.apply_host,
            # DERIVED forms of provider text are still provider text. The normalized title is
            # emitted in the scorecard detail, and a posting legitimately titled "Real-Time AI
            # Engineer" normalizes to a string the original title does not contain, so redacting
            # only the original let a sourced word reach the guard.
            normalize_title_for_matching(job.title),
            normalize_employer(job.employer_name),
        )))
        values.update(job.secondary_locations)
        values.update(job.uncertainty)
        for prov in job.provenance:
            values.update(filter(None, (prov.source_id, prov.job_id, prov.posting_url,
                                        prov.discovery_query)))
    for event in inp.events:
        values.update(filter(None, (
            event.source_id, event.job_id, event.event_id, event.snapshot_id,
            event.prior_snapshot_id, event.linked_job_id, event.content_hash,
        )))
    for screen in inp.screen_results.values():
        for bucket in (screen.exclusions, screen.pending_checks, screen.suppressed):
            for hit in bucket:
                if hit.matched_text:
                    values.add(hit.matched_text)
    # Ownership evidence is the employer's own words, exactly as screening's matched text is, and it
    # reaches the report by the same route. Both the matched phrase and the surrounding context are
    # verbatim substrings of the posting — each is TRUNCATED to the same length `to_json` writes, so
    # what is excused here is the exact text that appears in the output and never a longer span.
    # Without this the guard reads an employer's own "real-time reporting" as a system accusation and
    # fails the whole report, which is the shape of the 2026-09-26 production failure.
    for assessment in inp.ownership_results.values():
        for signal in assessment.signals:
            if signal.matched_text:
                values.add(signal.matched_text[:120])
            if signal.context:
                values.add(signal.context[:200])
    cov = inp.coverage
    if cov is not None:
        values.update(cov.attributions)
        values.update(cov.previously_unseen_employers)
        for gated in cov.credential_gated:
            values.update(str(v) for v in gated.values() if v)
        for item in cov.inaccessible:
            values.update(str(v) for v in item.values() if v)
    values.update(_source_employer(s, inp.source_labels) for s in inp.expected_sources)
    values.update(inp.state_source_text)
    # Ids of postings the round did not evaluate are provider-derived identifiers like any other
    # job id ("…-real-estate-analyst"); they reach the JSON through `evaluation`.
    values.update((inp.evaluation or {}).get("not_evaluated_job_ids") or ())
    # Company names and places from the financing watchlist are the filers' own words.
    for sig in (inp.company_signals or {}).get("signals") or ():
        values.update(str(v) for v in (sig.get("company"), sig.get("location"),
                                        sig.get("evidence_url")) if v)
    # The differ's segment spelling ("real estate & workplace"), which its notes quote.
    values.update(_segment_form(v) for v in inp.state_source_text)
    return sorted((str(value) for value in values if value), key=len, reverse=True)


_MAX_WATCHLIST_ROWS = 15


def _graduated_signals(inp: ReportInput) -> list[dict]:
    """The stored round's signals, re-graduated against THIS report's population.

    Discovery graduates against the postings of its own round; the report holds three weeks of
    carried postings, so an employer that posted earlier is matched here too.
    """
    from src.common.normalize import normalize_employer

    sigs = [dict(s) for s in (inp.company_signals or {}).get("signals") or []]
    by_employer: dict[str, list[str]] = {}
    for job in inp.jobs:
        key = normalize_employer(job.employer_name or "")
        if key:
            by_employer.setdefault(key, []).append(job.job_id)
    for sig in sigs:
        ids = by_employer.get(normalize_employer(sig.get("company") or ""))
        if ids:
            sig["status"] = "graduated"
            sig["graduated_by"] = sorted(set(sig.get("graduated_by") or []) | set(ids))
            sig["mandate"] = "an opening at this employer is in this report (see graduated_by)"
    sigs.sort(key=lambda s: (s.get("status") != "graduated", s.get("priority", 2),
                             "".join(chr(105 - ord(c)) if c.isdigit() else c
                                     for c in str(s.get("filing_date") or "")),
                             s.get("company") or ""))
    return sigs


def _watchlist_rows(inp: ReportInput):
    if not inp.company_signals:
        return None
    sigs = _graduated_signals(inp)
    meta = {
        "lookback_days": inp.company_signals.get("lookback_days"),
        "signals": len(sigs),
        "graduated": sum(1 for s in sigs if s.get("status") == "graduated"),
        "failures": inp.company_signals.get("failures") or [],
    }
    return sigs[:_MAX_WATCHLIST_ROWS], meta


def _watchlist_json(inp: ReportInput) -> dict | None:
    if not inp.company_signals:
        return None
    body = {k: v for k, v in inp.company_signals.items() if k != "signals"}
    body["signals"] = _graduated_signals(inp)
    return body


def _segment_form(value: str) -> str:
    """The differ's `_seg` spelling of a department or team: stripped and lowercased."""
    return value.strip().lower()


def _rendered_forms(value: str) -> set[str]:
    """Every spelling a source value can take once it is written into the report.

    The redaction below matches text exactly, and the renderer does not write source text exactly:
    Markdown link text escapes `|`, `[`, `]` and `\\`, and the JSON dump escapes quotes, backslashes
    and every non-ASCII character. A sourced title such as "Senior FullStack Engineer - Real User
    Monitoring (RUM) | …" was therefore redacted in its raw form and missed in its rendered one, and
    the guard read the employer's own word as a system claim (production, 2026-09-26). Only the
    redaction set grows; the text checked and the rule it is checked against are unchanged.
    """
    markdown = _md_text(value)
    return {value, markdown, json.dumps(value)[1:-1], json.dumps(markdown)[1:-1]}


def _note_withheld(event: ChangeEvent) -> bool:
    return (event.event_type in _SOURCE_SCOPED and bool(event.notes)
            and _publishable_source_note(event) is None)


def _event_json(event: ChangeEvent) -> dict:
    """The report's copy of an event, still a valid `ChangeEvent`. A withheld source note is
    blanked here and LISTED in the report's `withheld_source_notes`; the event record under
    `events/` is untouched and still holds the full text."""
    body = event.model_dump(mode="json")
    if _note_withheld(event):
        body["notes"] = None
    return body


def _assert_report_language(markdown: str, report_json: dict, inp: ReportInput) -> None:
    """Fail the report on any guarded word the SYSTEM wrote; excuse only words inside source text.

    A guarded word in the output is excused only when it lies inside a whole-token occurrence of a
    source value (in any rendered spelling, see `_rendered_forms`) that itself contains that word.
    Two defects of the earlier substitute-then-scan form are closed by construction: a short source
    value cut out of the middle of a word ("it" from "Reality") can no longer manufacture a guarded
    word, and the scan no longer rewrites the whole report once per source value, which cost
    seconds on a 2.7 MB report inside a 90-second function.
    """
    excusing: set[str] = set()
    for value in _source_values(inp):
        excusing.update(form for form in _rendered_forms(value) if form and _BANNED_RE.search(form))
    for text in (markdown, json.dumps(report_json, default=str)):
        _assert_only_sourced_vocab(text, excusing)


def _assert_only_sourced_vocab(text: str, excusing: set[str]) -> None:
    hits = list(_BANNED_RE.finditer(text))
    if not hits:
        return
    covered: list[tuple[int, int]] = []
    for form in excusing:
        at = text.find(form)
        while at != -1:
            end = at + len(form)
            before = text[at - 1] if at > 0 else ""
            after = text[end] if end < len(text) else ""
            if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                covered.append((at, end))
            at = text.find(form, at + 1)
    for hit in hits:
        if not any(lo <= hit.start() and hit.end() <= hi for lo, hi in covered):
            raise NeverFakeViolation(
                f"banned vocabulary in report output: {hit.group(0)!r} at pos {hit.start()} "
                "(the system expresses behavior + confidence, never fake/real accusations)"
            )


def _publishable_source_note(event: ChangeEvent) -> str | None:
    """A SOURCE-scoped event's note, if its wording may be published; otherwise None.

    These notes are upstream system text about a feed or a board segment — never about a posting —
    written by the differ or discovery for diagnosis and copied into the report verbatim. When one
    uses vocabulary the report does not publish (the differ's "Treating this as a real closure"),
    it is WITHHELD, visibly, with the durable event named, instead of failing the whole report and
    taking every candidate down with it. The note is not reworded: rewriting system text would be
    worse than not printing it.

    Job-scoped notes are deliberately NOT routed through here. A note on a posting is a claim about
    that posting, and a guarded word there still fails the report exactly as before.
    """
    if not event.notes:
        return None
    try:
        # Both spellings the note will be published in: the JSON dump escapes non-ASCII, which can
        # turn a word the raw check reads as "realé" into one the JSON guard reads as "real".
        assert_no_banned_vocab(event.notes)
        assert_no_banned_vocab(json.dumps(event.notes))
    except NeverFakeViolation:
        return None
    return event.notes


_WITHHELD_NOTE = (
    "(the upstream detail for this notice is withheld: its wording is not publishable in this "
    "report; the full text is the durable event record named here)"
)


# --------------------------------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------------------------------
def render_report(inp: ReportInput) -> tuple[str, dict]:
    """Return (markdown, json_dict). Deterministic; narrator NOT invoked."""
    axes = compute_health_axes(inp)
    health, missing = axes.collection, axes.collection_missing
    material_events = [e for e in inp.events if e.event_type in _MATERIAL]
    first_seen = [e for e in inp.events if e.event_type == ChangeEventType.FIRST_SEEN]
    source_events = [e for e in inp.events if e.event_type in _SOURCE_SCOPED]
    jobs_by_id = {job.job_id: job for job in inp.jobs}
    cov = inp.coverage

    ranked = _ranked(inp)
    pairs = [(card, jobs_by_id[card.job_id]) for card in ranked if card.job_id in jobs_by_id]
    report_now = inp.run_started_at or datetime.fromisoformat(f"{inp.dt}T23:59:59+00:00")
    cold_start = _cold_start(inp)

    # Partition by screening outcome and history. Nothing is dropped; every posting lands somewhere.
    strong: list[tuple] = []
    review: list[tuple] = []
    previously: list[tuple] = []
    for card, job in pairs:
        screen = _screen(inp, job.job_id)
        status, _note = _history(inp, job.job_id)
        if screen is not None and screen.outcome == ScreenOutcome.EXCLUDED.value:
            continue
        if status != HistoryStatus.NEW:
            previously.append((card, job))
        elif screen is not None and screen.outcome == ScreenOutcome.PENDING_CHECK.value:
            review.append((card, job))
        elif _ownership_retained(inp, card):
            # Retained on ownership evidence rather than on the fit number. "Needs a check" is the
            # honest destination: the opening is plausible and the score is not a verdict on it, but
            # calling it strong would be claiming something the score did not say.
            review.append((card, job))
        else:
            strong.append((card, job))

    excluded_rows = [
        (card, jobs_by_id[card.job_id]) for card in inp.scorecards
        if card.job_id in jobs_by_id
        and (_screen(inp, card.job_id) is not None)
        and _screen(inp, card.job_id).outcome == ScreenOutcome.EXCLUDED.value
    ]
    complete_list = strong + review + previously

    # FRESH-FIRST cohort. A highlight, not a filter and not a re-ranking of the complete list:
    # nothing is excluded for being old, and because the complete list below stays fit-ranked, a
    # fresh weak posting cannot outrank a strong one merely for being new.
    def _by_fit(pairs):
        """Fit-descending. Freshness selects the cohort; it never reorders within one."""
        return sorted(
            pairs,
            key=lambda cj: (
                -(cj[0].brett_fit.score if cj[0].brett_fit.score is not None else -1.0),
                cj[0].job_id,
            ),
        )

    fresh_pairs = _by_fit([
        (card, job) for card, job in complete_list
        if is_fresh_arrival(job, now=report_now, previous_run_at=inp.previous_run_at,
                            cold_start=cold_start,
                            previously_reported=inp.previously_reported_ids)
    ])
    fresh_ids = {card.job_id for card, _job in fresh_pairs}
    older_strong = _by_fit([
        (card, job) for card, job in complete_list
        if card.job_id not in fresh_ids
        and card.brett_fit.band in (Band.HIGH, Band.MEDIUM)
        and (card.brett_fit.score or 0) >= 0.45
    ])
    relevant_ids = {card.job_id for card, _ in pairs}
    relevance_order = {card.job_id: i for i, (card, _) in enumerate(pairs)}

    # ---- header ----
    if health == RunHealth.VERIFIED_QUIET and not inp.expected_sources:
        # The fixed employer registry is a verification aid, not the search. With nothing tracked,
        # "every expected source succeeded" would be vacuously true and read as a clean bill of
        # health; say what is actually the case instead.
        collection_line = (
            "no employer boards are tracked this round; nothing here depends on a hand-maintained "
            "employer list, and the discovery line below is the search"
        )
    elif health == RunHealth.VERIFIED_QUIET:
        collection_line = (
            "every expected source produced a successful download"
            + ("; nothing material changed." if axes.freshness == "NO-CHANGE-OBSERVED"
               else "; changes are listed below.")
        )
    elif health == RunHealth.INCOMPLETE:
        collection_line = (
            "these sources lack a successful download: " + ", ".join(missing)
        )
    else:
        collection_line = "no manifest was opened for this run_id (missed-run watchdog)."

    lines = [
        f"# Job Posting Reality Score — daily report {inp.dt}",
        "",
        f"Run: {inp.run_id}  ·  scoring profile v{_profile_version(inp)}",
        f"Tracked employer boards: {len(set(inp.succeeded_sources) & set(inp.expected_sources))}/"
        f"{len(set(inp.expected_sources))} succeeded · discovery feeds: "
        f"{len((inp.coverage.discovery_succeeded if inp.coverage else []) or [])}/"
        f"{len((inp.coverage.discovery_attempted if inp.coverage else []) or [])} returned results",
        "",
        "## Run health",
        "",
        f"- **Collection ({health.value})** — {collection_line}",
        f"- **Discovery coverage ({axes.discovery})** — {axes.discovery_detail}.",
        f"- **Freshness ({axes.freshness})** — "
        f"{len(first_seen)} newly observed, {len(material_events)} edited.",
        f"- **Interpretation ({axes.interpretation})** — {axes.interpretation_detail}.",
        "",
        "> Collection health describes the sources that were actually queried. It is not a "
        "statement about the job market: a complete download of every configured source still "
        "covers only those sources, and the discovery coverage line above is the one that says how "
        "wide the search itself reached.",
        "",
        f"Retained credible roles: {len(complete_list)} "
        f"({len(strong)} new, {len(review)} needing a check, {len(previously)} already in progress). "
        f"Policy exclusions: {len(excluded_rows)}. Postings considered: {len(inp.jobs)}.",
        "",
        # The central workflow states that "the initial JPRS score is not a final rejection gate" and
        # that promising overflow must be preserved "rather than padding the batch or silently
        # discarding opportunities". A count that appears nowhere is a silent discard, so the
        # below-threshold tail is stated here and remains addressable in the JSON.
        f"Below the fit threshold and therefore not listed above: "
        f"{len(_below_threshold_ids(inp, complete_list, excluded_rows))}. These are retained with full "
        f"scores in `daily_report.json` and are not a judgment by the research step — ranking is a "
        f"triage aid, not a verdict.",
        "",
    ]

    ev = inp.evaluation or {}
    if ev and not ev.get("complete", True):
        if ev.get("cohort") == "fresh":
            scope = (
                "This is the DEGRADED report: the full assembly did not complete"
                + (f" ({ev.get('degraded_reason')})" if ev.get("degraded_reason") else "")
                + ", so only postings first observed since "
                + str(ev.get("cohort_window_start") or "the fresh-cohort window")[:16].replace("T", " ")
                + " UTC were evaluated"
            )
        else:
            scope = (
                "The round ran short of time and stopped evaluating newest-first before the "
                "oldest carried postings"
            )
        lines += [
            f"> **Partial evaluation — {ev.get('evaluated', 0)} of {ev.get('population', 0)} postings "
            f"evaluated.** {scope}. The other {ev.get('not_evaluated', 0)} were NOT screened or ranked "
            "this round; they are not rejected, are listed by id in `daily_report.json` "
            "(`evaluation.not_evaluated_job_ids`), are not recorded as shown, and return as unseen "
            "in the next complete round.",
            "",
        ]

    if cov is not None and cov.policy_projection_note:
        lines += [f"Candidate policy: {cov.policy_projection_note}", ""]

    # ---- coverage and backlog ----
    if cov is not None:
        lines += ["## Coverage and backlog", ""]
        if cov.discovery_attempted:
            lines.append(
                f"- Discovery sources queried: {', '.join(sorted(cov.discovery_attempted))}"
            )
            failed = sorted(set(cov.discovery_attempted) - set(cov.discovery_succeeded))
            if failed:
                lines.append(f"- Discovery sources that returned nothing usable: {', '.join(failed)}")
        else:
            lines.append(
                "- No employer-independent discovery source ran; this report covers monitored "
                "employers only"
            )
        if cov.pending_publication_job_count():
            lines.append(
                f"- **{cov.pending_publication_job_count()} discovered posting(s) are captured but "
                f"not yet published** into "
                f"{', '.join(sorted(cov.pending_publication))}, so they are missing from the list "
                "below through a storage interruption and not through any judgment about them. The "
                "next discovery round publishes them without the feed having to return them again"
            )
        lines.append(
            f"- Query families: {cov.query_families_covered}/{cov.query_families_total} covered"
        )
        if cov.query_families_saturated:
            lines.append(
                f"- Hit a result ceiling, so more may exist behind it: "
                f"{', '.join(cov.query_families_saturated)}"
            )
        if cov.query_families_deferred:
            lines.append(
                f"- Deferred to a later run by the request budget, not discarded: "
                f"{', '.join(cov.query_families_deferred)}"
            )
        if cov.query_families_never_run:
            lines.append(f"- Never run yet: {', '.join(cov.query_families_never_run)}")
        if cov.backlog_items:
            lines.append(
                f"- Resumable backlog: {cov.backlog_items} query item(s)"
                + (f" — {cov.backlog_reason}" if cov.backlog_reason else "")
            )
        for gated in cov.credential_gated:
            lines.append(
                f"- **{gated.get('provider')} did not run**: {gated.get('reason')}. "
                f"Required setup: {gated.get('required')}"
            )
        for item in cov.inaccessible:
            lines.append(
                f"- Could not access {item.get('target')}: {item.get('reason')}"
            )
        if cov.previously_unseen_employers:
            shown = sorted(cov.previously_unseen_employers)
            lines.append(
                f"- Employers seen this run that were not in the monitored registry: "
                f"{len(shown)} ({', '.join(shown[:12])}"
                + (", …" if len(shown) > 12 else "") + ")"
            )
        if cov.budgets:
            spent = ", ".join(
                f"{p}: {b.get('requests_spent')}/{b.get('max_requests_per_run')}"
                for p, b in sorted(cov.budgets.items())
            )
            lines.append(f"- Request budgets used: {spent}")
        hp = cov.history_projection or {}
        if hp:
            state = hp.get("state")
            # Bold only when the alarm is earned. See `_history_projection_state`.
            loud = bool(hp.get("alarm"))
            label = {
                "missing": "**Application history: MISSING**",
                "stale": ("**Application history: STALE**" if loud
                          else "Application history: evidence through yesterday"),
                "current": "Application history: current",
                "known_empty": "Application history: present and empty",
            }.get(state, "Application history")
            detail = ""
            if state not in (None, "missing"):
                detail = (
                    f" ({hp.get('entries')} entries, {hp.get('suppressing_entries')} of them "
                    f"submitted/rejected/set aside; built {hp.get('built_at')}; "
                    f"evidence through {hp.get('cutoff') or 'an unstated date'})"
                )
            lines.append(f"- {label}{detail} — {hp.get('note')}")
            if hp.get("unresolved"):
                lines.append(
                    f"- {hp['unresolved']} application(s) are recorded in the evidence but NOT "
                    "settled by it — blocked, held, or claiming both submitted and not-submitted. "
                    "They are held rather than guessed, so they are neither suppressed here nor "
                    "confirmed as sent"
                )
        lines.append("")

    # ---- source notices ----
    if source_events:
        lines += ["## Source notices", ""]
        for e in sorted(source_events, key=lambda x: (x.source_id, x.event_type.value)):
            employer = _source_employer(e.source_id, inp.source_labels)
            published = _publishable_source_note(e)
            note = (
                f" {published}" if published
                else f" {_WITHHELD_NOTE}" if e.notes
                else ""
            )
            lines.append(
                f"- {employer} ({e.source_id}): {_CHANGE_PHRASE[e.event_type]}.{note} "
                f"{_evidence_str(e)}"
            )
        lines.append("")

    # ---- highlights ----
    if strong:
        lines += ["## New strong candidates", ""]
        for card, job in strong[:_MAX_HIGHLIGHTS]:
            lines.append(_row(card, job, inp))
        if len(strong) > _MAX_HIGHLIGHTS:
            lines.append(
                f"- The remaining {len(strong) - _MAX_HIGHLIGHTS} new candidate(s) are listed in "
                f"full in the complete list below — nothing is held back in JSON."
            )
        lines.append("")
    elif inp.scorecards:
        lines += [
            "## New strong candidates", "",
            "No new posting cleared the fit threshold in what was actually searched this run. "
            + (
                "Discovery coverage was partial, so this is not a statement that no such job "
                "exists." if axes.discovery != "PLAN-COVERED" else
                "The planned query set was covered, so this is a completed search with zero strong "
                "matches rather than an incomplete one."
            ),
            "",
        ]

    if fresh_pairs:
        lines += [
            "## New since the last round", "",
            f"{len(fresh_pairs)} credible role(s) that arrived since the previous check or were "
            f"published within {FRESH_WINDOW_HOURS}h. Applying early helps, so these come first — "
            f"but they are ordered by fit, and nothing below is excluded for being older."
            + (
                f" Note: {len(cold_start)} source(s) were observed for the first time this run, so "
                f"for those only a provider publication date counts as evidence of freshness."
                if cold_start else ""
            ),
            "",
        ]
        for card, job in fresh_pairs[:_MAX_HIGHLIGHTS]:
            lines.append(_row(card, job, inp) + f" | {_md_text(_age_of(job, inp, report_now))}")
        if len(fresh_pairs) > _MAX_HIGHLIGHTS:
            lines.append(
                f"- the remaining {len(fresh_pairs) - _MAX_HIGHLIGHTS} fresh role(s) appear in the "
                f"complete list below"
            )
        lines.append("")
    elif inp.scorecards:
        lines += [
            "## New since the last round", "",
            "Nothing credible arrived since the previous check. Older strong fits below are still "
            "worth the morning; this is not an empty day.",
            "",
        ]

    if older_strong:
        lines += [
            "## Older, still strong", "",
            "Retained because the fit is strong, not because they are new. Age is stated on each "
            "row; nothing here is excluded for being older than the fresh window.",
            "",
        ]
        for card, job in older_strong[:_MAX_HIGHLIGHTS]:
            lines.append(_row(card, job, inp) + f" | {_md_text(_age_of(job, inp, report_now))}")
        lines.append("")

    if review:
        lines += [
            "## Needs a check before preparing", "",
            "These are credible on the evidence available, but something specific is unconfirmed.",
            "",
        ]
        ownership_rows = [c for c, _j in review if _ownership_retained(inp, c)]
        if ownership_rows:
            lines += [
                f"{len(ownership_rows)} of these are here because the posting described broad or "
                "first/sole ownership of software, not because of the fit score. That score is "
                "AI-weighted, and a low one is not a judgment on the opening. Where a row says "
                "*team structure not stated*, the posting did not say — it is not inferred from "
                "the title or the employer's size.",
                "",
            ]
        for card, job in review:
            lines.append(_row(card, job, inp))
        lines.append("")

    if previously:
        lines += [
            "## Already prepared, submitted, or set aside", "",
            "Surfaced separately so useful queued work stays visible without being announced as new.",
            "",
        ]
        for card, job in previously:
            status, note = _history(inp, job.job_id)
            suffix = f" — history: {status.value if hasattr(status, 'value') else status}"
            if note:
                suffix += f" ({note})"
            lines.append(_row(card, job, inp) + suffix)
        lines.append("")

    # ---- the complete readable list ----
    if complete_list:
        lines += [
            "## Complete candidate list", "",
            f"All {len(complete_list)} retained credible role(s), each with a direct link and a "
            f"reason. This is the full set — there is no hidden overflow.",
            "",
        ]
        for index, (card, job) in enumerate(complete_list, start=1):
            status, _n = _history(inp, job.job_id)
            screen = _screen(inp, job.job_id)
            lines.append(
                f"{index}. **{_md_text(_employer(job, inp.source_labels))}** — {_job_link(job)}  \n"
                f"   {_md_text(_location(job))} · {_md_text(_comp(job))} · "
                f"{job.employment_type.value} · via `{job.source_id}`"
                + (f" · query `{_md_text(job.discovery_query_family or '')}`"
                   if job.discovery_query_family else "")
                + "  \n"
                f"   fit {card.brett_fit.band.value} "
                f"{_fmt(card.brett_fit.score)} · priority {card.application_priority.band.value} "
                f"{_fmt(card.application_priority.score)} · "
                f"screen {screen.outcome if screen else 'not-screened'} · "
                f"history {status.value if hasattr(status, 'value') else status}  \n"
                f"   why: {_md_text(_why_fit(card))}  \n"
                + (f"   {_md_text(_ownership_note(inp, card))}  \n"
                   if _ownership_note(inp, card) else "")
                + (f"   check: {_md_text(_gaps(inp, job, card))}  \n"
                   if _gaps(inp, job, card) else "")
                + (f"   dates: {_md_text(_dates(job))}  \n" if _dates(job) else "")
                + f"   age: {_md_text(_age_of(job, inp, report_now))}"
                + ("  ·  **new since the last round**" if card.job_id in fresh_ids else "")
                + "  \n"
                + (f"   also seen at: "
                   f"{_md_text(', '.join(sorted({p.source_id for p in job.provenance})))}  \n"
                   if len(job.provenance) > 1 else "")
                + (f"   possibly the same posting as: "
                   f"{_md_text(', '.join(job.possible_duplicate_of[:3]))}  \n"
                   if job.possible_duplicate_of else "")
            )
        lines.append("")

    # ---- company-first watchlist ----
    watch = _watchlist_rows(inp)
    if watch is not None:
        rows, meta = watch
        lines += [
            "## Pre-opening research watchlist (financing signals, not openings)", "",
            f"Companies with a verified SEC Form D financing filing in the last "
            f"{meta.get('lookback_days')} days, classified by the filer as technology "
            f"({meta.get('signals')} companies; {meta.get('graduated')} with an observed opening). "
            "Financing is not a hiring plan, a budget or a contract: none of these is a candidate "
            "or an application target until an opening or a paid mandate is evidenced.",
            "",
        ]
        for sig in rows:
            status = ("OPENING OBSERVED: " + ", ".join(sig.get("graduated_by", [])[:2])
                      if sig.get("status") == "graduated" else "watchlist, mandate unknown")
            lines.append(
                f"- {_md_text(sig.get('company', ''))} — {_md_text(sig.get('location') or 'location '
                'not stated')} · Form {sig.get('form')} filed {sig.get('filing_date')} · "
                f"[filing]({sig.get('evidence_url')}) · {status}"
            )
        if meta.get("signals", 0) > len(rows):
            lines.append(f"- and {meta['signals'] - len(rows)} more in `daily_report.json` "
                         "(`company_watchlist.signals`)")
        for failure in meta.get("failures") or []:
            lines.append(f"- Source note: {_md_text(str(failure))}")
        lines.append("")

    # ---- exclusions with reasons ----
    if excluded_rows:
        lines += ["## Excluded by candidate policy", "",
                  "Grouped by rule, with the text that triggered each one.", ""]
        by_rule: dict[str, list] = {}
        for card, job in excluded_rows:
            screen = _screen(inp, job.job_id)
            for hit in screen.exclusions:
                by_rule.setdefault(hit.rule_id, []).append((job, hit))
        for rule_id in sorted(by_rule):
            lines.append(f"**{rule_id}**")
            for job, hit in by_rule[rule_id][:_MAX_EVENT_ITEMS]:
                lines.append(
                    f"- {_md_text(_employer(job, inp.source_labels))} — {_job_link(job)}: "
                    f"{_md_text(hit.reason)}"
                )
            if len(by_rule[rule_id]) > _MAX_EVENT_ITEMS:
                lines.append(
                    f"- and {len(by_rule[rule_id]) - _MAX_EVENT_ITEMS} more under this rule "
                    f"(all in JSON)"
                )
            lines.append("")

    # ---- changes / newly observed ----
    visible_material = (
        [e for e in material_events if e.job_id in relevant_ids] if inp.scorecards
        else material_events
    )
    visible_first_seen = (
        [e for e in first_seen if e.job_id in relevant_ids] if inp.scorecards else first_seen
    )
    if visible_material:
        lines += ["## Changes", ""]
        ordered = sorted(
            visible_material,
            key=lambda x: (relevance_order.get(x.job_id or "", len(relevance_order)),
                           x.event_type.value),
        )
        for e in ordered[:_MAX_EVENT_ITEMS]:
            extra = ""
            if e.event_type == ChangeEventType.PROBABLE_REPOST and e.repost_score is not None:
                extra = f" (confidence {e.repost_score}; linked {e.linked_job_id})"
            lines.append(
                f"- {_event_subject(e, jobs_by_id, inp)}: {_CHANGE_PHRASE[e.event_type]}{extra} "
                f"{_evidence_str(e)}"
            )
        if len(visible_material) > _MAX_EVENT_ITEMS:
            lines.append(
                f"- {len(visible_material) - _MAX_EVENT_ITEMS} further change(s) are in JSON."
            )
        lines.append("")

    if visible_first_seen:
        lines += ["## Newly observed postings", ""]
        ordered = sorted(
            visible_first_seen,
            key=lambda x: relevance_order.get(x.job_id or "", len(relevance_order)),
        )
        for e in ordered[:_MAX_EVENT_ITEMS]:
            lines.append(
                f"- {_event_subject(e, jobs_by_id, inp)}: {_CHANGE_PHRASE[e.event_type]} "
                f"{_evidence_str(e)}"
            )
        if len(visible_first_seen) > _MAX_EVENT_ITEMS:
            lines.append(
                f"- {len(visible_first_seen) - _MAX_EVENT_ITEMS} further new posting(s) are in JSON."
            )
        lines.append("")

    # ---- dedup + admission + attribution ----
    if inp.dedup:
        lines += [
            "## Duplicates and distinct requisitions", "",
            f"- Merged as the same posting seen more than once: "
            f"{inp.dedup.get('hard_merges', 0)}",
            f"- Cross-linked as possibly the same, both kept for review: "
            f"{inp.dedup.get('soft_possible_duplicate_links', 0)}",
            f"- Deliberately NOT merged because they are distinct openings: "
            f"{inp.dedup.get('links_blocked_as_distinct_requisitions', 0)}",
            "",
        ]
    if cov is not None and cov.admission_summary:
        lines += ["## Newly discovered sources", ""]
        for state, employers in sorted(cov.admission_summary.get("by_state", {}).items()):
            lines.append(f"- {state}: {len(employers)} ({', '.join(employers[:8])}"
                         + (", …" if len(employers) > 8 else "") + ")")
        lines.append("")
    if cov is not None and cov.attributions:
        lines += ["## Source attribution", ""]
        for attribution in sorted(set(cov.attributions)):
            lines.append(f"- {attribution}")
        lines.append("")

    markdown = "\n".join(lines)

    withheld_notes = [
        {"event_id": e.event_id, "source_id": e.source_id, "event_type": e.event_type.value,
         "reason": _WITHHELD_NOTE}
        for e in inp.events if _note_withheld(e)
    ]
    if withheld_notes:
        print(json.dumps({"report": "source_notes_withheld", "count": len(withheld_notes),
                          "event_ids": [row["event_id"] for row in withheld_notes]}))
    report_json = {
        "run_id": inp.run_id,
        "dt": inp.dt,
        # Written so the NEXT round has a durable previous-observation boundary to compare against.
        # A persisted report is the evidence that this round reported; a failed round writes none.
        "report_generated_at": datetime.now(timezone.utc).isoformat(),
        "timing": inp.timing or {
            "run_started_at": inp.run_started_at.isoformat() if inp.run_started_at else None,
            "previous_run_at": inp.previous_run_at.isoformat() if inp.previous_run_at else None,
            "basis": "supplied_directly",
            "cold_start_run": inp.previous_run_at is None,
        },
        "run_health": health.value,
        "health_axes": axes.to_json(),
        "header": collection_line,
        "expected_sources": sorted(inp.expected_sources),
        "succeeded_sources": sorted(inp.succeeded_sources),
        "incomplete_sources": missing,
        "completeness_ratio": _ratio(inp),
        "current_job_count": len(inp.jobs),
        "matching_job_count": len(complete_list),
        "new_strong_count": len(strong),
        "fresh_arrival_count": len(fresh_pairs),
        "older_strong_count": len(older_strong),
        "fresh_window_hours": FRESH_WINDOW_HOURS,
        "needs_check_count": len(review),
        "previously_engaged_count": len(previously),
        # Named separately so "how many openings reached you only because of the ownership
        # preference" is answerable from the artifact instead of inferred.
        "ownership_retained_count": len(
            [c for c, _j in complete_list if _ownership_retained(inp, c)]
        ),
        "ownership_retained_job_ids": sorted(
            c.job_id for c, _j in complete_list if _ownership_retained(inp, c)
        ),
        "confirmed_sole_ownership_job_ids": sorted(
            c.job_id for c, _j in complete_list
            if (_ownership(inp, c.job_id) is not None
                and _ownership(inp, c.job_id).team_structure == TeamStructure.CONFIRMED_SOLE)
        ),
        "policy_excluded_count": len(excluded_rows),
        "below_fit_threshold_count": len(_below_threshold_ids(inp, complete_list, excluded_rows)),
        "below_fit_threshold_job_ids": _below_threshold_ids(inp, complete_list, excluded_rows),
        # Per-identity evidence of what this report CONSUMED, so a reconciliation does not have to
        # infer a disposition for anything absent from a readable section.
        "consumed_job_ids": _consumed_job_ids(inp),
        "complete_candidate_list": [_match_json(c, j, inp) for c, j in complete_list],
        # `top_matches` keeps its original meaning — the ranked best retained candidates — so an
        # existing consumer of the JSON is unaffected. The new three-way split (new / needs-a-check /
        # already in progress) is reported alongside it rather than by redefining this key.
        "top_matches": [_match_json(c, j, inp) for c, j in complete_list[:_MAX_HIGHLIGHTS]],
        "policy_exclusions": [_match_json(c, j, inp) for c, j in excluded_rows],
        "coverage": (
            {
                "discovery_attempted": sorted(cov.discovery_attempted),
                "discovery_succeeded": sorted(cov.discovery_succeeded),
                "query_families_total": cov.query_families_total,
                "query_families_covered": cov.query_families_covered,
                "query_families_saturated": cov.query_families_saturated,
                "query_families_deferred": cov.query_families_deferred,
                "query_families_never_run": cov.query_families_never_run,
                "backlog_items": cov.backlog_items,
                "backlog_reason": cov.backlog_reason,
                "budgets": cov.budgets,
                "credential_gated": cov.credential_gated,
                "inaccessible": cov.inaccessible,
                "previously_unseen_employers": sorted(cov.previously_unseen_employers),
                "admission_summary": cov.admission_summary,
                "attributions": sorted(set(cov.attributions)),
                "policy_projection_note": cov.policy_projection_note,
                # The projection's own state, as a structured record rather than only a sentence,
                # so a later run can compare cutoffs without re-parsing prose.
                "history_projection": cov.history_projection,
                "pending_publication": cov.pending_publication,
                "pending_publication_job_count": cov.pending_publication_job_count(),
            } if cov is not None else None
        ),
        "dedup": inp.dedup or None,
        # What this round evaluated, and what it did not. Absent (None) for a directly built input.
        "evaluation": inp.evaluation or None,
        # Company-first financing signals, kept apart from every candidate list.
        "company_watchlist": _watchlist_json(inp),
        "events": [_event_json(e) for e in inp.events],
        # Counted and named, so a differ regression that starts writing accusatory notes is visible
        # here and in the logs rather than absorbed.
        "withheld_source_notes": withheld_notes,
        "scorecards": [c.model_dump(mode="json") for c in inp.scorecards],
        "narration_enabled": False,  # M2: deterministic-only path
    }

    _assert_report_language(markdown, report_json, inp)
    return markdown, report_json


def _age_of(job: CanonicalJob, inp: ReportInput, now: datetime) -> str:
    provider = job.source_id.partition(":")[0]
    return age_label(
        provider_published_at=job.provider_published_at,
        provider_updated_at=job.provider_updated_at,
        first_seen_at=job.first_seen_at,
        now=now,
        source_lag_hours=SOURCE_LAG_HOURS.get(provider),
    )


def _consumed_job_ids(inp: ReportInput) -> list[str]:
    """Every posting identity this report actually consumed, whatever section it ended in.

    The report is the only place that knows this. Without it, a checker reconciling discovery's
    stored postings against the report has to GUESS at anything absent from a readable section, and
    P08's live check guessed: it read an employer's presence in `previously_unseen_employers` as
    proof that every posting from that employer had been consumed, and labelled a job that never
    reached the consumer "below the fit threshold". Stating the consumed identities here is what
    makes the difference between "scored and not shown" and "never arrived" decidable from the
    artifact instead of inferred by the tool reading it.
    """
    return sorted({job.job_id for job in inp.jobs})


def _below_threshold_ids(inp: ReportInput, complete_list, excluded_rows) -> list[str]:
    """Postings that reached scoring but appear in no readable section.

    Named explicitly, and now by identity rather than only by count, because an unstated count is a
    silent discard and the central workflow forbids silently discarding opportunities. The count is
    the length of this list, so the two cannot disagree.
    """
    listed = {card.job_id for card, _job in complete_list}
    listed |= {card.job_id for card, _job in excluded_rows}
    return sorted(set(_consumed_job_ids(inp)) - listed)


def _fmt(score) -> str:
    return f"{score:.2f}" if score is not None else "UNKNOWN"


def _ownership_note(inp: ReportInput, card: DimensionScorecard) -> str:
    """The ownership-scope half of a row, written so the three states stay distinct.

    An `UNKNOWN` team structure with no breadth evidence renders as nothing at all. It is the
    ordinary case and it is not a gap: the policy forbids inferring structure from a title, company
    size or missing public material, so a posting that did not say is simply a posting that did not
    say.
    """
    assessment = _ownership(inp, card.job_id)
    if assessment is None:
        return ""
    retained = _ownership_retained(inp, card)
    if not assessment.is_broad_ownership_candidate and not retained:
        return ""
    # Short on the row. The reason the ownership-retained rows are here at all is stated ONCE under
    # the section heading — repeating a two-line caveat on every row buries the thing the reader is
    # actually scanning for, which is the scope and the link.
    note = f"ownership: {assessment.label()}"
    if retained:
        note += " · retained on ownership evidence, not on fit"
    return note


def _row(card: DimensionScorecard, job: CanonicalJob, inp: ReportInput) -> str:
    employer = _employer(job, inp.source_labels)
    ownership = _ownership_note(inp, card)
    return (
        f"- {_job_link(job)} — {_md_text(employer)} | {_md_text(_location(job))} | "
        f"fit {card.brett_fit.band.value} {_fmt(card.brett_fit.score)} | "
        f"priority {card.application_priority.band.value} "
        f"{_fmt(card.application_priority.score)} | {_md_text(_why_fit(card))}"
        + (f" | {_md_text(ownership)}" if ownership else "")
    )


def _profile_version(inp: ReportInput) -> str:
    if inp.scorecards:
        return inp.scorecards[0].scoring_profile_version
    return ScoringProfile().version


def _ratio(inp: ReportInput) -> float:
    if not inp.expected_sources:
        return 0.0
    return round(
        len(set(inp.succeeded_sources) & set(inp.expected_sources))
        / len(set(inp.expected_sources)),
        4,
    )


# --------------------------------------------------------------------------------------------------
# assembly from S3
# --------------------------------------------------------------------------------------------------
def assemble_report_input(
    s3, bucket: str, run_id: str, dt: str, *,
    deadline=None, reserve_seconds: float = 0.0, cohort: str = "full",
) -> ReportInput:
    """Build ReportInput from S3: RUN_OPEN manifest (expected), SUCCESS sentinels (succeeded),
    the differ's change events, and the current job set. Completeness = manifest-expected vs
    sentinel-succeeded (never wall-clock), per RELIABILITY §5.1."""
    from src.candidate.history import load_history
    from src.candidate.ownership import assess_ownership
    from src.candidate.policy import check_divergence, load_projection
    from src.candidate.screening import screen_job
    from src.common import s3layout
    from src.common.dedup import deduplicate
    from src.discovery.live import DiscoveryLiveView

    manifest = _load_json(s3, bucket, s3layout.run_manifest_key(run_id), default=None)
    manifest_present = manifest is not None
    # Real timing, from RUN_OPEN and the previous persisted report. This is the wiring whose absence
    # made every production report show zero fresh arrivals while the renderer tests passed.
    timing = resolve_run_timing(s3, bucket, run_id, dt)
    expected_sources = list(manifest.get("expected_sources", [])) if manifest_present else []
    source_labels = dict(manifest.get("source_labels", {})) if manifest_present else {}
    source_kinds = dict(manifest.get("source_kinds", {})) if manifest_present else {}

    expected_source_set = set(expected_sources)
    succeeded: list[str] = []
    for key in _list_keys(s3, bucket, f"status/run={run_id}/"):
        if key.endswith("/SUCCESS.json"):
            segs = dict(s.split("=", 1) for s in key.split("/") if "=" in s)
            p, b = segs.get("provider"), segs.get("board")
            source_id = f"{p}:{b}" if p and b else ""
            if source_id in expected_source_set:
                succeeded.append(source_id)

    events: list[ChangeEvent] = []
    for sid in expected_sources:
        provider, _, board = sid.partition(":")
        for e in _load_json(s3, bucket, s3layout.events_key(provider, board, dt), default=[]):
            events.append(ChangeEvent.model_validate(e))

    jobs: list[CanonicalJob] = []
    # Score "as of" the moment this round started looking, not the end of its calendar day: at
    # 07:05 the end of day is seventeen hours in the future and every age was computed against it.
    scored_as_of = timing.run_started_at or datetime.fromisoformat(f"{dt}T23:59:59+00:00")
    observations: dict[str, int] = {}
    statuses_by_source: dict[str, list[SnapshotStatus]] = {}
    state_source_text: set[str] = set()
    for sid in expected_sources:
        provider, _, board = sid.partition(":")
        raw_jobs = _load_json(s3, bucket, s3layout.current_jobs_key(provider, board), default=[])
        state = _load_json(s3, bucket, s3layout.current_state_key(provider, board), default={})
        state_jobs = state.get("jobs", {})
        # Only postings THIS run's events name: those are the only ones whose notes can quote their
        # department. Collecting every historical record would let a stale lone word ("Fraud")
        # excuse the same word anywhere in the report.
        named = {e.job_id for e in events if e.source_id == sid and e.job_id}
        for record in (state_jobs[job_id] for job_id in named if job_id in state_jobs):
            state_source_text.update(
                str(value) for value in (
                    record.get("department"), record.get("team"), record.get("title_norm"),
                ) if value
            )
        observation_count = max(1, len(state.get("success_count_history", [])))
        observations[sid] = observation_count
        source_events = [event for event in events if event.source_id == sid]
        statuses = [SnapshotStatus.SUCCESS] * observation_count
        if any(e.event_type == ChangeEventType.SOURCE_FETCH_FAILED for e in source_events):
            statuses.append(SnapshotStatus.FETCH_FAILED)
        elif any(e.event_type in (
            ChangeEventType.SOURCE_RESPONSE_PARTIAL, ChangeEventType.SOURCE_SUSPECT
        ) for e in source_events):
            statuses.append(SnapshotStatus.PARTIAL)
        statuses_by_source[sid] = statuses

        for raw_job in raw_jobs:
            job = CanonicalJob.model_validate(raw_job)
            record = state_jobs.get(job.job_id, {})
            if record.get("first_seen_at"):
                job.first_seen_at = _parse_datetime(record["first_seen_at"])
            if record.get("last_seen_at"):
                job.last_seen_at = _parse_datetime(record["last_seen_at"])
            if not job.source_kind and sid in source_kinds:
                job.source_kind = SourceKind(source_kinds[sid])
            jobs.append(job)

    # ---- discovery population ------------------------------------------------------------------
    # The monitored loop above can only ever yield postings from the 15 configured employer boards,
    # because it iterates `expected_sources`. Discovery's postings live in its own feed-keyed view,
    # written by the discovery stage at 07:05 and read here at 09:00. Merging them into `jobs` BEFORE
    # dedup is the whole integration: everything below — dedup, scoring, screening, history, ranking,
    # freshness and the complete candidate list — is population-agnostic and now runs over both.
    discovery_sources = list(manifest.get("expected_discovery_sources", [])) if manifest_present \
        else []
    discovery_status: dict[str, dict] = {}
    for sid in discovery_sources:
        provider, _, _slice = sid.partition(":")
        raw_view = _load_json(s3, bucket, s3layout.discovery_live_key(provider), default=None)
        if raw_view is None:
            # Declared in the manifest but no view on record: discovery has not yet written for this
            # feed. Stated, never inferred as "the feed is empty" — the two look identical here and
            # only one of them means the operator saw everything there was.
            discovery_status[sid] = {"present": False, "live_jobs": 0, "observation_count": 0}
            continue
        view = DiscoveryLiveView.model_validate(raw_view)
        view_jobs = view.canonical_jobs()
        discovery_status[sid] = {
            "present": True,
            "live_jobs": len(view_jobs),
            "observation_count": view.observation_count,
            "last_observed_run_id": view.last_observed_run_id,
            "verified_this_run": view.last_observed_run_id == run_id,
        }
        observations[sid] = max(1, view.observation_count)
        # A feed that did not produce a usable page this run is PARTIAL, not a success. The scoring
        # context reads these, so a posting carried over from an earlier round cannot be scored as
        # though this round re-verified it.
        statuses_by_source[sid] = (
            [SnapshotStatus.SUCCESS] * max(1, view.observation_count)
            if view.last_observed_run_id == run_id
            else [SnapshotStatus.SUCCESS] * max(1, view.observation_count) + [SnapshotStatus.PARTIAL]
        )
        source_labels.setdefault(sid, provider)
        for job in view_jobs:
            if not job.source_kind:
                job.source_kind = SourceKind.DISCOVERY_FEED
            jobs.append(job)

    # Cross-source dedup BEFORE scoring, so one posting is scored once and its provenance is intact.
    jobs, dedup_report = deduplicate(jobs)
    population = jobs

    # ---- evaluation: scoring, screening and ownership, inside the time the round actually has ----
    # These three are pure per-posting work and are ~90% of the report's cost. Until 2026-11-11 they
    # ran over the whole population unconditionally, so a population that outgrew the function's
    # time limit produced NO report at all for 33 consecutive days. They now run newest-first in
    # chunks; when the measured rate says the next chunk would cross into the reserve the round needs
    # to render and publish, evaluation stops and the report says exactly how many postings it did
    # not evaluate. Nothing is dropped: unevaluated postings are listed by id, are not recorded as
    # shown, and therefore come back as unseen in the next round. With time to spare (the ordinary
    # case) every posting is evaluated and the output is identical to evaluating them all at once.
    events_by_source: dict[str, list[ChangeEvent]] = {}
    for e in events:
        events_by_source.setdefault(e.source_id, []).append(e)
    order = _evaluation_order(population)
    cohort_window_start = None
    if cohort == "fresh":
        cohort_window_start = _fresh_cohort_start(timing, scored_as_of)
        first_seen_ids = {e.job_id for e in events if e.event_type == ChangeEventType.FIRST_SEEN}
        order = [
            job for job in order
            if job.job_id in first_seen_ids
            or (_aware(job.first_seen_at) is not None
                and _aware(job.first_seen_at) >= cohort_window_start)
        ]
    stage_seconds = {"scoring": 0.0, "screening": 0.0, "ownership": 0.0}
    cards_by_id: dict[str, DimensionScorecard] = {}
    screen_results: dict = {}
    ownership_results: dict = {}
    stopped_for_budget = False
    eval_started = _monotonic()
    for start in range(0, len(order), EVALUATION_CHUNK):
        chunk = order[start:start + EVALUATION_CHUNK]
        if deadline is not None and cards_by_id:
            per_job = (_monotonic() - eval_started) / len(cards_by_id)
            if deadline() - per_job * len(chunk) < reserve_seconds:
                stopped_for_budget = True
                break
        for job in chunk:
            sid = job.source_id
            source_events = events_by_source.get(sid, [])
            job_events = [e for e in source_events if e.job_id == job.job_id or e.job_id is None]
            t0 = _monotonic()
            cards_by_id[job.job_id] = score_job(
                ScoreContext(
                    job=job,
                    events=job_events,
                    recent_snapshot_statuses=statuses_by_source.get(sid, [SnapshotStatus.SUCCESS]),
                    num_successful_observations=observations.get(sid, 1),
                ),
                today=scored_as_of,
            )
            t1 = _monotonic()
            screen_results[job.job_id] = screen_job(job)
            t2 = _monotonic()
            ownership_results[job.job_id] = assess_ownership(job)
            t3 = _monotonic()
            stage_seconds["scoring"] += t1 - t0
            stage_seconds["screening"] += t2 - t1
            stage_seconds["ownership"] += t3 - t2
    # Population order, not evaluation order, so a complete evaluation renders exactly as before.
    jobs = [job for job in population if job.job_id in cards_by_id]
    scorecards = [cards_by_id[job.job_id] for job in jobs]
    not_evaluated = [job.job_id for job in population if job.job_id not in cards_by_id]
    evaluation = {
        "cohort": cohort,
        "population": len(population),
        "evaluated": len(jobs),
        "not_evaluated": len(not_evaluated),
        "not_evaluated_job_ids": not_evaluated,
        "stopped_for_budget": stopped_for_budget,
        "cohort_window_start": cohort_window_start.isoformat() if cohort_window_start else None,
        "stage_seconds": {k: round(v, 3) for k, v in stage_seconds.items()},
        "complete": not not_evaluated,
    }

    history = load_history() or None
    history_status: dict = {}
    history_note = None
    history_projection = _history_projection_state(history, dt)
    if history is None:
        # Visible, not silent. Without the projection every posting reads NEW, which would quietly
        # re-announce work already submitted — exactly the behavior the plan forbids.
        history_note = (
            "application-history projection not found in the deployment package; every posting "
            "below is labelled NEW because no history was available, NOT because none exists"
        )
    else:
        for job in jobs:
            entry = history.lookup(
                employer_name=job.employer_name,
                title=job.title,
                url=job.apply_url or job.posting_url,
            )
            if entry is None:
                continue
            note = entry.conflict_detail if entry.status_conflict else None
            history_status[job.job_id] = (entry.status, note)

    projection = load_projection()
    policy_note = None

    if projection is None:
        policy_note = (
            "no committed policy projection was found; screening ran on the built-in rules and the "
            "projection should be rebuilt"
        )
    else:
        divergence = check_divergence(projection)
        policy_note = (
            f"projection {projection.projection_version} built "
            f"{projection.built_at.date()} — {divergence.summary()}"
        )

    if history_note:
        policy_note = f"{policy_note}; {history_note}" if policy_note else history_note

    coverage = _assemble_coverage(
        s3, bucket, run_id, population, expected_sources, policy_note,
        discovery_status=discovery_status,
        history_projection=history_projection,
    )

    company_signals = _load_optional_json(s3, bucket, s3layout.discovery_signals_key())

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
        screen_results=screen_results,
        ownership_results=ownership_results,
        history_status=history_status,
        coverage=coverage,
        dedup=dedup_report.to_json(),
        run_started_at=timing.run_started_at,
        previous_run_at=timing.previous_run_at,
        previously_reported_ids=(
            timing.previously_reported_ids if timing.previous_run_id else None),
        source_observations=dict(observations),
        timing=timing.to_json(),
        state_source_text=state_source_text,
        evaluation=evaluation,
        company_signals=company_signals,
    )


# Postings evaluated between budget checks. Small enough that one chunk is a few seconds even on the
# slowest configuration measured; large enough that the check itself costs nothing.
EVALUATION_CHUNK = 200
# The degraded cohort reaches back at least this far, and further when the previous report is newer.
FRESH_COHORT_HOURS = 72


def _monotonic() -> float:
    import time

    return time.monotonic()


def _evaluation_order(jobs: list[CanonicalJob]) -> list[CanonicalJob]:
    """Newest first: when a round cannot evaluate everything, the postings Brett has not seen go first.

    Ordered by when JPRS first observed the posting (descending), then by id so the order is total and
    deterministic. A posting with no first-seen stamp sorts last — carried postings with no timing are
    the ones a later round is best placed to finish.
    """
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return sorted(
        jobs,
        key=lambda job: (-(_aware(job.first_seen_at) or epoch).timestamp(), job.job_id),
    )


def _fresh_cohort_start(timing, scored_as_of: datetime) -> datetime:
    """Start of the degraded cohort: the later of the previous report and `FRESH_COHORT_HOURS` ago.

    Bounded on purpose. When the last published report is weeks old (2026-11-11: thirty-three days),
    "since the last report" is the whole population and would reproduce the very timeout the degraded
    path exists to survive.
    """
    from datetime import timedelta

    floor = _aware(scored_as_of) - timedelta(hours=FRESH_COHORT_HOURS)
    previous = _aware(timing.previous_run_at) if timing.previous_run_at else None
    return max(floor, previous) if previous else floor


def _report_day(dt: str, cutoff):
    """The report's own date, or None when it cannot be read. Never a reassuring fallback."""
    try:
        return datetime.strptime(dt, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _history_projection_state(history, dt: str) -> dict:
    """Four states, and the reason there are four.

    The report has always said so when the projection was MISSING. It said nothing when the
    projection was present but stale, because from inside the report those two look identical —
    a four-day-old projection answers every lookup cheerfully and labels everything it does not
    know as NEW, which is how postings already submitted get re-announced as fresh opportunities.

    `built_at` cannot close that gap on its own: it says when the file was written, not how far its
    evidence reached. `cutoff` is the separate, explicit statement, and the gap between the cutoff
    and the report date is the honest measure. Nothing here claims the history is COMPLETE — it
    cannot be, since an application run may be writing its log while this report reads.
    """
    if history is None:
        return {
            "state": "missing",
            "alarm": True,
            "entries": 0,
            "note": (
                "no application-history projection was found, so every posting below is labelled "
                "NEW because no history was available, NOT because none exists"
            ),
        }

    entries = len(history.entries)
    suppressing = sum(1 for e in history.entries if e.status != HistoryStatus.NEW
                      and e.status != HistoryStatus.PREPARED)
    cutoff = history.cutoff
    built = history.built_at
    payload = {
        "entries": entries,
        "suppressing_entries": suppressing,
        "unresolved": len(getattr(history, "unresolved", []) or []),
        "built_at": built.date().isoformat() if built else None,
        "cutoff": cutoff.date().isoformat() if cutoff else None,
        "report_date": dt,
    }

    if entries == 0:
        payload["state"] = "known_empty"
        # An empty projection whose evidence stops in January is empty about JANUARY. Saying every
        # posting is "genuinely unseen" would be the one completeness claim this block exists to
        # avoid, so the cutoff still governs and an empty-but-stale projection still alarms.
        rd = _report_day(dt, cutoff)
        stale = cutoff is None or rd is None or (rd - cutoff.date()).days >= 2
        payload["alarm"] = stale
        payload["note"] = (
            "the application-history projection is present and contains no entries. That is a "
            "known-empty history, not a missing one"
            + (
                f", but its evidence only reaches {cutoff.date() if cutoff else 'an unstated date'},"
                " so it is empty about that date and says nothing about anything submitted since"
                if stale else
                ": every posting below is genuinely unseen as of its cutoff"
            )
        )
        return payload

    if cutoff is None:
        payload["state"] = "stale"
        payload["gap_days"] = None
        payload["alarm"] = True
        payload["note"] = (
            "the application-history projection declares no evidence cutoff, so how far its "
            "evidence reached is unknown. Treat anything it labels NEW as unconfirmed"
        )
        return payload

    report_day = _report_day(dt, cutoff)
    if report_day is None:
        # A date the code could not parse must not resolve to the most reassuring answer. Falling
        # back to the cutoff produced gap 0 and `current` — a projection of unknown currency
        # reporting itself as fresh.
        payload["state"] = "stale"
        payload["gap_days"] = None
        payload["alarm"] = True
        payload["note"] = (
            f"the application-history projection reaches evidence through {cutoff.date()}, but this "
            f"report's own date ({dt!r}) could not be read, so the gap between them is unknown. "
            "Treat anything labelled NEW as unconfirmed"
        )
        return payload
    gap = (report_day - cutoff.date()).days
    payload["gap_days"] = gap
    # A one-day gap is what a CORRECTLY refreshed projection looks like: the refresh runs with the
    # application round, so the next morning's report is always a day behind it. Raising the alarm
    # there would raise it every single day, and a banner that is always on is one the reader learns
    # to skip — which is the same silence this block exists to break. The facts are printed either
    # way; only the emphasis is earned.
    payload["alarm"] = gap >= 2
    if gap > 0:
        payload["state"] = "stale"
        payload["note"] = (
            f"the application-history projection reaches evidence through {cutoff.date()}, "
            f"{gap} day(s) before this report. Applications submitted after that date are NOT "
            "represented here and would read as NEW. Refresh it with `history-refresh`"
        )
    else:
        payload["state"] = "current"
        payload["alarm"] = False
        payload["note"] = (
            f"the application-history projection reaches evidence through {cutoff.date()}, at or "
            "after this report's date. This is a statement about coverage, not completeness — a "
            "submission made after the refresh ran is still not in it"
        )
    return payload


def _assemble_coverage(
    s3, bucket: str, run_id: str, jobs, expected_sources, policy_note,
    discovery_status: dict[str, dict] | None = None,
    history_projection: dict | None = None,
) -> CoverageInput:
    """Read the discovery coverage document the discovery stage wrote, if there was one."""
    from src.common import s3layout

    doc = _load_json(s3, bucket, s3layout.discovery_coverage_key(run_id), default=None) or {}
    status = discovery_status or {}
    # A feed whose postings are carried from an earlier round is NOT part of this round's coverage.
    # Saying so here is what keeps "we have jobs from this feed" apart from "this feed ran today" —
    # the distinction a report-before-discovery run and a failed discovery run both depend on.
    carried_over = sorted(
        sid for sid, entry in status.items()
        if entry.get("present") and not entry.get("verified_this_run")
    )
    awaiting = sorted(sid for sid, entry in status.items() if not entry.get("present"))
    inaccessible = list(doc.get("inaccessible", []))
    for sid in carried_over:
        entry = status[sid]
        inaccessible.append({
            "target": sid,
            "reason": (
                "this feed was not observed during this run; the postings it contributed below were "
                f"carried from an earlier round (last observed in run "
                f"{entry.get('last_observed_run_id')}) and their last-verification age is stated on "
                "each row. This run adds no coverage from this feed"
            ),
        })
    for sid in awaiting:
        inaccessible.append({
            "target": sid,
            "reason": (
                "this feed is configured and expected, but no stored postings exist for it yet, so "
                "nothing from it can appear below. Absence here is a gap in coverage, not an "
                "observation that the feed holds nothing"
            ),
        })
    monitored = {s.partition(":")[2] for s in expected_sources}
    unseen = sorted({
        job.employer_name for job in jobs
        if job.employer_name
        and job.source_kind == SourceKind.DISCOVERY_FEED
        and job.employer_name.lower().replace(" ", "-") not in monitored
    })
    return CoverageInput(
        discovery_attempted=list(doc.get("discovery_attempted", [])),
        discovery_succeeded=list(doc.get("discovery_succeeded", [])),
        query_families_total=doc.get("query_families_total", 0),
        query_families_covered=doc.get("query_families_covered", 0),
        query_families_saturated=list(doc.get("query_families_saturated", [])),
        query_families_deferred=list(doc.get("query_families_deferred", [])),
        query_families_never_run=list(doc.get("query_families_never_run", [])),
        backlog_items=doc.get("backlog_items", 0),
        backlog_reason=doc.get("backlog_reason"),
        budgets=doc.get("budgets", {}),
        credential_gated=list(doc.get("credential_gated", [])),
        inaccessible=inaccessible,
        attributions=list(doc.get("attributions", [])),
        previously_unseen_employers=unseen,
        admission_summary=doc.get("admission_summary", {}),
        policy_projection_note=policy_note,
        history_projection=history_projection or {},
        pending_publication=doc.get("pending_publication", {}) or {},
    )


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def measure_runtime(*, started_at: float, now: float, budget_seconds: float | None,
                    population: int) -> dict:
    """What this invocation cost, and how much of its budget was left.

    This exists because of a specific silence. On 2026-09-26 the report finished in 80.08 seconds
    against a 90-second timeout and was recorded as a success; the corpus then grew and the next
    three scheduled rounds timed out, producing no report at all. The margin was gone before the
    failure and nothing anywhere read it — the duration sits in the Lambda REPORT log line, which no
    artifact and no reader consults. A number that only appears after the thing has already broken
    is not a measurement.

    `per_1k_population_seconds` is the part worth watching: the dominant stage of the assembly is
    quadratic in corpus size, so the budget does not shrink at the rate the corpus grows.
    """
    elapsed = max(0.0, now - started_at)
    out: dict = {
        "elapsed_seconds": round(elapsed, 2),
        "input_population": population,
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }
    if population > 0:
        out["per_1k_population_seconds"] = round(elapsed / population * 1000, 2)
    if budget_seconds:
        out["timeout_seconds"] = round(budget_seconds, 2)
        out["headroom_seconds"] = round(budget_seconds - elapsed, 2)
        out["headroom_pct"] = round((budget_seconds - elapsed) / budget_seconds * 100, 1)
    return out


def _runtime_line(runtime: dict) -> str:
    """One line, rendered into the report the operator actually opens."""
    bits = [f"ran in {runtime['elapsed_seconds']}s"]
    if "timeout_seconds" in runtime:
        bits.append(
            f"of a {runtime['timeout_seconds']}s budget "
            f"({runtime['headroom_seconds']}s / {runtime['headroom_pct']}% left)"
        )
    bits.append(f"over {runtime['input_population']} postings")
    return "Runtime: " + ", ".join(bits) + "."


def handler(event, context):
    import os
    import time

    import boto3

    from src.common import s3layout

    started_at = time.monotonic()
    bucket = os.environ["JPRS_BUCKET"]
    s3 = boto3.client("s3")
    ctx = event.get("runContext") or {}
    run_id = event.get("run_id") or ctx.get("run_id") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dt = event.get("dt") or ctx.get("dt") or run_id

    # The configured timeout, read from the runtime rather than restated here, so the headroom
    # below cannot disagree with the deployed setting.
    budget_seconds = None
    remaining = getattr(context, "get_remaining_time_in_millis", None)
    if callable(remaining):
        try:
            budget_seconds = remaining() / 1000.0
        except Exception:  # pragma: no cover - a context that cannot answer is not a report failure
            budget_seconds = None

    # `mode` was ignored until 2026-11-11, so the state machine's ReportIncomplete step re-ran the
    # identical full assembly that had just timed out — and timed out too, every day for 33 days.
    # "incomplete" now means what the state machine always meant by it: publish what can be published
    # without the work that failed — the fresh cohort only, stated as degraded.
    mode = str(event.get("mode") or "assemble")
    cohort = "fresh" if mode == "incomplete" else "full"
    degraded_reason = _degraded_reason(ctx) if mode == "incomplete" else None
    deadline = None
    reserve = 0.0
    if budget_seconds is not None:
        def deadline() -> float:  # seconds this invocation still has
            return budget_seconds - (time.monotonic() - started_at)
        # Render, two S3 writes of a multi-megabyte JSON and SES. Measured locally at ~2 s for 4,671
        # postings; the reserve is deliberately far above any plausible Lambda multiple of that.
        reserve = max(45.0, 0.15 * budget_seconds)

    inp = assemble_report_input(
        s3, bucket, run_id, dt, deadline=deadline, reserve_seconds=reserve, cohort=cohort,
    )
    if degraded_reason:
        inp.evaluation["degraded_reason"] = degraded_reason
    if mode == "incomplete":
        # A fresh-cohort report is partial by construction even if the cohort is the whole
        # population; say so rather than letting it read as a complete round.
        inp.evaluation["complete"] = False
    markdown, report_json = render_report(inp)
    report_json["delivery_mode"] = "degraded" if mode == "incomplete" else (
        "partial" if not inp.evaluation.get("complete", True) else "complete")

    runtime = measure_runtime(
        started_at=started_at, now=time.monotonic(),
        budget_seconds=budget_seconds, population=len(inp.jobs),
    )
    report_json["runtime"] = runtime
    # Check the line being appended, and ONLY that line. `render_report` has already guarded its own
    # output with the sourced-vocabulary exemption, which exists because an employer really is
    # called Ghost and a department really is called Fraud, and a report that cannot print its
    # sources' own words is broken in a worse way. Re-running the BLANKET guard over the finished
    # document ignores that exemption and rejects the legitimately sourced title — measured, not
    # feared: it failed `test_source_titles_with_guarded_words_and_escaped_characters_publish_intact`
    # on the word `Real` at position 3251 of a real report. This line is machine-generated from
    # numbers and carries no source text, so the blanket guard is the right one for it alone.
    runtime_line = _runtime_line(runtime)
    assert_no_banned_vocab(runtime_line)
    markdown = markdown.rstrip("\n") + "\n\n" + runtime_line + "\n"

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
        prior_delivery = _load_optional_json(s3, bucket, marker_key)
        if prior_delivery is not None:
            digest_delivery = "already-sent"
        else:
            subject = (
                f"Job radar {dt}: {report_json['new_strong_count']} new, "
                f"{report_json['matching_job_count']} retained "
                f"({report_json['run_health']})"
                + ("" if report_json["delivery_mode"] == "complete"
                   else f" [{report_json['delivery_mode']}]")
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
        "new_strong": report_json["new_strong_count"],
        "digest_delivery": digest_delivery,
        "delivery_mode": report_json["delivery_mode"],
        "evaluated": inp.evaluation.get("evaluated"),
        "population": inp.evaluation.get("population"),
    }


def _degraded_reason(ctx: dict) -> str:
    """One short line naming why the full assembly did not publish, from the Catch payload."""
    err = ctx.get("error") if isinstance(ctx, dict) else None
    if not isinstance(err, dict):
        return "the full assembly step did not complete"
    name = str(err.get("Error") or "").strip()
    if name in ("Sandbox.Timedout", "States.Timeout"):
        return "the full assembly ran out of time"
    return f"the full assembly step failed ({name})" if name else "the full assembly step failed"


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


def _load_optional_json(s3, bucket, key):
    """Load an optional object without treating a permission failure as absence."""
    listing = s3.list_objects_v2(Bucket=bucket, Prefix=key, MaxKeys=1)
    if not any(item.get("Key") == key for item in listing.get("Contents", [])):
        return None
    return _load_json(s3, bucket, key)


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
