"""Discovery budgets, backlog and rotation.

A search budget is an OPERATIONAL limit on requests. It is not an application quota and it is not a
statement about how many jobs exist. The distinction is the whole point of this module: when the
budget runs out, the remaining query work is *persisted and resumable*, the report says what was not
covered, and nothing is silently discarded.

Three properties the plan requires and this enforces:

  saturation is visible   a family that hit its page ceiling is recorded as saturated, so "we stopped
                          looking" never reads as "there was nothing more"
  backlog is resumable    unspent work carries to the next run with its cursor
  rotation is fair        under-covered families move to the front next run, so a low-priority
                          family is deferred, never permanently starved

The recall-floor family is exempt from rotation-based deferral: it is the reason an ordinary title at
an ordinary employer can arrive at all, so it always runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from src.discovery.queries import FAMILIES_BY_KEY, QueryPlan

# How many untraversed recent ranges one source may carry in persisted state. Far more than any real
# three-day burst needs, and small enough that the state document cannot grow without bound.
HEAD_PENDING_MAX = 24


class FamilyCoverage(BaseModel):
    """Per-family coverage ledger, persisted across runs."""

    model_config = ConfigDict(extra="forbid")
    family_key: str
    requests_spent: int = 0
    records_seen: int = 0
    pages_fetched: int = 0
    saturated: bool = False              # hit the page ceiling; more results may exist
    last_covered_run: str | None = None
    last_covered_at: datetime | None = None
    next_cursor: str | None = None       # resume point for a paginating source
    deferred_reason: str | None = None


class SourceBudget(BaseModel):
    """What one source is allowed to spend in one run."""

    model_config = ConfigDict(extra="forbid")
    source_provider: str
    max_requests_per_run: int
    requests_spent: int = 0
    exhausted_at: datetime | None = None
    failures: int = 0
    rate_limited: bool = False

    @property
    def remaining(self) -> int:
        return max(0, self.max_requests_per_run - self.requests_spent)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0


class BacklogItem(BaseModel):
    """One unit of query work still owed.

    A structured record rather than a tuple because the work has four dimensions now — family,
    phrase, page and location scope — and a positional tuple silently changes meaning when a
    dimension is added, which is exactly how deferred work goes missing.
    """

    model_config = ConfigDict(extra="forbid")
    family_key: str
    phrase: str
    page: int = 1
    where: str | None = None

    def key(self) -> tuple[str, str, int, str | None]:
        return (self.family_key, self.phrase, self.page, self.where)

    def label(self) -> str:
        scope = self.where or "nationwide/remote"
        return f"{self.family_key}: {self.phrase!r} p{self.page} [{scope}]"


class DiscoveryBacklog(BaseModel):
    """The resumable remainder. This is what makes 'incomplete' honest instead of terminal."""

    model_config = ConfigDict(extra="forbid")
    pending: list[BacklogItem] = Field(default_factory=list)
    reason: str | None = None

    def __len__(self) -> int:
        return len(self.pending)


class DiscoveryState(BaseModel):
    """Persisted discovery state: budgets, per-family coverage, and the backlog."""

    model_config = ConfigDict(extra="forbid")
    coverage: dict[str, FamilyCoverage] = Field(default_factory=dict)
    budgets: dict[str, SourceBudget] = Field(default_factory=dict)
    backlog: DiscoveryBacklog = Field(default_factory=DiscoveryBacklog)
    last_run_id: str | None = None
    # Employers already admitted as monitored sources; used to keep queries company-independent and
    # to measure "previously unseen".
    seen_employers: list[str] = Field(default_factory=list)
    # Per-source pagination position, persisted so a cursor-paginated feed resumes where it stopped
    # instead of re-reading page one forever. A source whose page failed keeps its cursor so the
    # next run retries that page rather than skipping past it.
    source_cursors: dict[str, str | None] = Field(default_factory=dict)
    # Which phase a source spent its budget on last run: "head" or "catch-up". Only consulted when a
    # source's page budget is 1 and a backfill is outstanding, where the two must alternate so
    # neither new arrivals nor the backfill is permanently starved. Storing the PHASE (not a run id)
    # is deliberate: `reset_for_run` overwrites `last_run_id` before the branch is reached, so
    # comparing run ids silently always chose the head.
    last_feed_phase: dict[str, str] = Field(default_factory=dict)
    # DERIVED compatibility mirror of `head_pending`: the newest range still owed, or None.
    #
    # It was the whole representation in P04, and one slot is what made two jobs disappear: a saved
    # continuation and a newly published continuation both wanted it, so one overwrote the other.
    # `head_pending` is now the truth and this is written from it in exactly one place
    # (`set_pending_head`). It is kept because it is the only field an older reader understands: a
    # rollback that drops `head_pending` still resumes the newest owed range instead of none.
    head_cursors: dict[str, str | None] = Field(default_factory=dict)
    # Recent ranges known to be UNTRAVERSED, newest first — the traversal DEBT.
    #
    # A burst, a missed weekend, a failed page or an exhausted budget can each leave a recent range
    # unfetched, and more than one at a time. Every such range is recorded here until it is actually
    # walked; nothing else may be read as coverage of it. This is deliberately the only place that
    # says "not yet traversed", because the defect being repaired was a *timestamp* being read as
    # proof of traversal.
    head_pending: dict[str, list[str]] = Field(default_factory=dict)
    # Newest provider publication timestamp already OBSERVED per source (ISO-8601). Observation only:
    # it lets the contiguous walk from page one stop when it reaches ground that walk already covered,
    # and it says nothing about ranges listed in `head_pending`. Keeping the two apart is the repair —
    # P04 advanced this from the pages it did read and thereby claimed the pages it did not.
    head_frontier_at: dict[str, str] = Field(default_factory=dict)

    def pending_head(self, provider: str) -> list[str]:
        """Recent ranges still owed for a source, newest first.

        Reads a P04-era state transparently: a document written before `head_pending` existed carries
        its one unfinished continuation in `head_cursors`, and that range is still owed.
        """
        pending = self.head_pending.get(provider)
        if pending is None:
            saved = self.head_cursors.get(provider)
            return [saved] if saved else []
        return [cursor for cursor in pending if cursor]

    def set_pending_head(self, provider: str, cursors: Iterable[str | None]) -> list[str]:
        """Record the ranges still owed, newest first. Returns any dropped by the cap.

        The cap exists because this is PERSISTED state: an unbounded list would let a pathological
        feed grow the state document without limit. Dropping is never silent — the caller reports
        every dropped range as partial coverage.
        """
        ordered: list[str] = []
        for cursor in cursors:
            if cursor and cursor not in ordered:
                ordered.append(cursor)
        kept, dropped = ordered[:HEAD_PENDING_MAX], ordered[HEAD_PENDING_MAX:]
        self.head_pending[provider] = kept
        self.head_cursors[provider] = kept[0] if kept else None
        return dropped

    def coverage_for(self, family_key: str) -> FamilyCoverage:
        cov = self.coverage.get(family_key)
        if cov is None:
            cov = FamilyCoverage(family_key=family_key)
            self.coverage[family_key] = cov
        return cov

    def budget_for(self, provider: str, max_requests: int) -> SourceBudget:
        b = self.budgets.get(provider)
        if b is None or b.max_requests_per_run != max_requests:
            b = SourceBudget(source_provider=provider, max_requests_per_run=max_requests)
            self.budgets[provider] = b
        return b

    def reset_for_run(self, run_id: str) -> None:
        """Start-of-run: clear per-run spend, keep cumulative coverage and the backlog."""
        self.last_run_id = run_id
        for budget in self.budgets.values():
            budget.requests_spent = 0
            budget.exhausted_at = None
            budget.failures = 0
            budget.rate_limited = False


def well_covered_families(state: DiscoveryState, *, current_run_id: str) -> tuple[str, ...]:
    """Families covered by the most recent run, so this run prefers the others.

    Never defers a non-rotating family, and never defers a family that is saturated — a saturated
    family has *more* to give, so it is the opposite of well covered.
    """
    out = []
    for key, cov in state.coverage.items():
        family = FAMILIES_BY_KEY.get(key)
        if family is None or not family.rotates:
            continue
        if cov.saturated:
            continue
        if cov.last_covered_run and cov.last_covered_run != current_run_id:
            if cov.records_seen > 0:
                out.append(key)
    return tuple(sorted(out))


def allocate(
    plan: QueryPlan,
    budget: SourceBudget,
    *,
    backlog_first: Iterable[BacklogItem] = (),
    location_scopes: Iterable[str | None] = (None,),
) -> tuple[list[BacklogItem], DiscoveryBacklog]:
    """Split the plan into what this run can afford and what carries over.

    Backlog work runs FIRST: a query deferred last run has already waited, and letting fresh
    high-priority work jump it forever is exactly how a family gets starved.

    `location_scopes` multiplies each phrase across geographies. `None` means the provider's
    default (nationwide / remote) and MUST stay in the list — narrowing every search to one state
    would trade one coverage gap for another.
    """
    scopes = list(location_scopes) or [None]
    queue: list[BacklogItem] = list(backlog_first)
    for family, phrase in plan.items:
        for where in scopes:
            queue.append(BacklogItem(family_key=family, phrase=phrase, page=1, where=where))

    # de-duplicate while preserving order (a backlog item may also appear in the fresh plan)
    seen: set[tuple] = set()
    ordered: list[BacklogItem] = []
    for item in queue:
        if item.key() in seen:
            continue
        seen.add(item.key())
        ordered.append(item)

    capacity = budget.remaining
    work = ordered[:capacity]
    remainder = ordered[capacity:]
    backlog = DiscoveryBacklog(
        pending=remainder,
        reason=(
            f"{budget.source_provider} request budget of {budget.max_requests_per_run} per run "
            f"exhausted; {len(remainder)} query items carried forward and resumable"
        ) if remainder else None,
    )
    return work, backlog


def record_coverage(
    state: DiscoveryState,
    *,
    family_key: str,
    run_id: str,
    now: datetime,
    records: int,
    pages: int = 1,
    saturated: bool = False,
    next_cursor: str | None = None,
) -> None:
    cov = state.coverage_for(family_key)
    cov.requests_spent += pages
    cov.records_seen += records
    cov.pages_fetched += pages
    cov.saturated = saturated
    cov.last_covered_run = run_id
    cov.last_covered_at = now
    cov.next_cursor = next_cursor
    cov.deferred_reason = None


def mark_deferred(state: DiscoveryState, family_keys: Iterable[str], reason: str) -> None:
    for key in family_keys:
        state.coverage_for(key).deferred_reason = reason


def coverage_summary(state: DiscoveryState) -> dict:
    """Operator-facing coverage facts. Deliberately says what was NOT covered."""
    families_total = len(FAMILIES_BY_KEY)
    covered = [k for k, c in state.coverage.items() if c.records_seen > 0]
    saturated = sorted(k for k, c in state.coverage.items() if c.saturated)
    deferred = sorted(k for k, c in state.coverage.items() if c.deferred_reason)
    never = sorted(set(FAMILIES_BY_KEY) - set(state.coverage))
    return {
        "query_families_total": families_total,
        "query_families_covered": len(covered),
        "query_families_saturated": saturated,
        "query_families_deferred": deferred,
        "query_families_never_run": never,
        "backlog_items": len(state.backlog),
        "backlog_reason": state.backlog.reason,
        "budgets": {
            provider: {
                "max_requests_per_run": b.max_requests_per_run,
                "requests_spent": b.requests_spent,
                "exhausted": b.exhausted,
                "rate_limited": b.rate_limited,
                "failures": b.failures,
            }
            for provider, b in sorted(state.budgets.items())
        },
    }
