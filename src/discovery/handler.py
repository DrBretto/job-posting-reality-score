"""Discovery stage — the employer-independent search.

Runs before collection. For each configured discovery source it fetches under budget, maps records
into the same `CanonicalJob` shape monitoring uses, writes them through the same forward tiers
(raw/ → normalized/ → status/ + SUCCESS sentinel), observes every employer it saw, evaluates the
admission policy, and writes a coverage receipt the report renders verbatim.

The pure core (`run_discovery`) takes an injected fetcher, so the whole stage is testable against
fixtures with zero network. `handler` is the thin AWS wrapper.

What this stage must never do, each corresponding to a specific failure the plan names:
  - claim unattended discovery when only a fallback import ran
  - drop query work silently when the budget runs out (it goes to the resumable backlog)
  - admit a source merely because it was observed
  - mutate the active production registry (it PROPOSES rows; applying them is an operator action)
  - treat a posting's text as an instruction
"""

from __future__ import annotations

import gzip
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from src.common import s3layout
from src.common.models import (
    CanonicalJob,
    Provider,
    SnapshotStatus,
    SourceKind,
    VerificationState,
)
from src.discovery.admission import (
    AdmissionPolicy,
    SourceRegistryGrowth,
    admit_pass,
    observe,
    proposed_registry_entries,
)
from src.discovery.budget import (
    BacklogItem,
    DiscoveryState,
    allocate,
    coverage_summary,
    mark_deferred,
    record_coverage,
    well_covered_families,
)
from src.discovery.connectors import (
    AdzunaConnector,
    BulkFeedConnector,
    DiscoveryConnector,
    PaginatedFeedConnector,
    discovery_providers,
    get_discovery_connector,
    keyless_discovery_providers,
)
from src.discovery.live import (
    DiscoveryLiveView,
    PendingPublication,
    PendingPublicationBatch,
    publish_live_view,
)
from src.discovery.queries import build_query_plan, is_obvious_non_job
from src.discovery.resolve import resolve_careers_urls


# Location scopes for a query-capable source.
#
# `None` is the provider default — nationwide plus remote — and it stays FIRST because dropping it
# would trade one coverage gap for another. The review was explicit: "Do not solve this by limiting
# all searches to NH." The state/metro scopes supplement that breadth; they never replace it.
# Updated 2026-09-24 after the operator-confirmed "Location and Compensation" section: Boston and
# Portsmouth commuting are excluded, so a Boston-scoped search mostly returns onsite roles the
# screener now rejects. Boston-headquartered REMOTE roles still arrive through the nationwide and
# remote scopes, so nothing is lost by dropping that scope — only wasted request budget.
# How far back the feed-HEAD walk keeps going. The head phase exists to surface arrivals promptly,
# so it walks while pages still hold postings from roughly the last three days — wide enough to cover
# a missed weekend, narrow enough that it cannot turn into a crawl of the whole feed. An undated
# posting counts as recent, so a provider that publishes no dates never causes a new arrival to be
# walked past; the page budget, not the date, is what bounds the walk.
HEAD_RECENT_HOURS = 72


def _aware_dt(value: datetime | None) -> datetime | None:
    """Coerce a possibly-naive timestamp to UTC so comparisons cannot raise."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


LOCATION_SCOPES: tuple[str | None, ...] = (
    None,                       # nationwide / unscoped
    "remote",                   # explicitly remote-tagged listings
    "New Hampshire",            # home state, where onsite is genuinely possible
)


def enabled_discovery_providers(config_path: str | None = None) -> list[str]:
    """Every provider enabled in `config/discovery_sources.yaml`, credential-gated ones included.

    Falls back to the full connector registry when the config is unreadable, because defaulting to
    FEWER sources is how a gated source disappears from the coverage receipt instead of being
    reported. An explicit `enabled: false` is still honored — intentional disablement is a decision,
    absence of config is not.
    """
    from src.enumerate.handler import load_discovery_sources

    path = config_path or os.environ.get(
        "JPRS_DISCOVERY_YAML", "config/discovery_sources.yaml"
    )
    try:
        sources = load_discovery_sources(path)
    except Exception:  # noqa: BLE001 - unreadable config must not shrink coverage silently
        return discovery_providers()
    if not sources:
        return discovery_providers()
    return [s.provider.value for s in sources if s.enabled]


@dataclass
class DiscoveryOutcome:
    run_id: str
    jobs: list[CanonicalJob] = field(default_factory=list)
    attempted: list[str] = field(default_factory=list)
    succeeded: list[str] = field(default_factory=list)
    credential_gated: list[dict] = field(default_factory=list)
    inaccessible: list[dict] = field(default_factory=list)
    attributions: list[str] = field(default_factory=list)
    rejected_non_jobs: int = 0
    resolution: dict = field(default_factory=dict)
    state: DiscoveryState = field(default_factory=DiscoveryState)
    growth: SourceRegistryGrowth = field(default_factory=SourceRegistryGrowth)
    admission: dict = field(default_factory=dict)
    snapshots: list[tuple] = field(default_factory=list)  # (snapshot, jobs, raw_bytes)

    def coverage_doc(self) -> dict:
        doc = {
            "run_id": self.run_id,
            "discovery_attempted": sorted(self.attempted),
            "discovery_succeeded": sorted(self.succeeded),
            "credential_gated": self.credential_gated,
            "inaccessible": self.inaccessible,
            "attributions": sorted(set(self.attributions)),
            "records_rejected_as_not_an_opening": self.rejected_non_jobs,
            "employers_observed": len(self.growth.candidates),
            "admission_summary": self.admission,
            "careers_url_resolution": self.resolution,
        }
        doc.update(coverage_summary(self.state))
        return doc


def _employer_disabled(growth: SourceRegistryGrowth, employer: str) -> bool:
    from src.common.normalize import normalize_employer

    return normalize_employer(employer) in set(growth.operator_disabled)


def run_discovery(
    *,
    run_id: str,
    now: datetime,
    fetcher,
    providers: list[str] | None = None,
    state: DiscoveryState | None = None,
    growth: SourceRegistryGrowth | None = None,
    known_employers: set[str] | None = None,
    policy: AdmissionPolicy | None = None,
    monitored_count: int | None = 0,
    env: dict | None = None,
    max_pages_per_source: int | None = None,
    location_scopes: tuple[str | None, ...] | None = None,
) -> DiscoveryOutcome:
    """Pure discovery pass.

    `fetcher(provider, board_token, url) -> FetchResult` is injected so fixtures and the live path
    share one code path. Everything else is deterministic given `now`.
    """
    env = env if env is not None else os.environ
    state = state or DiscoveryState()
    growth = growth or SourceRegistryGrowth()
    policy = policy or AdmissionPolicy()
    known_employers = known_employers or set()
    # Default to every ENABLED provider, not only the keyless ones.
    #
    # R1: the old default was `keyless_discovery_providers()`, which made Adzuna unreachable on the
    # path production actually takes — supplying credentials changed nothing, and the coverage
    # receipt did not even mention it. A credential-gated source must be REACHED so that its gate
    # can be reported; skipping it silently is what hid the defect.
    providers = providers or enabled_discovery_providers()

    state.reset_for_run(run_id)
    outcome = DiscoveryOutcome(run_id=run_id, state=state, growth=growth)

    # Queries must not name an employer we already monitor; the plan builder enforces it and raises
    # if a phrase ever regresses into a company lookup.
    deprioritize = well_covered_families(state, current_run_id=run_id)
    plan = build_query_plan(known_employers=known_employers, deprioritize=deprioritize)

    for provider in providers:
        connector = get_discovery_connector(provider)

        # Bind credential-carrying connectors to the RESOLVED env. `with_env` returns a new
        # instance, so a per-run secret never mutates the shared registry object.
        if isinstance(connector, AdzunaConnector):
            connector = connector.with_env(env)

        # Credential gate: named, not silently skipped, and it blocks only this source.
        if isinstance(connector, AdzunaConnector) and not connector.credentials_present(env):
            outcome.credential_gated.append({
                "provider": provider,
                "reason": (
                    "Adzuna requires app_id and app_key on every request; without them the API "
                    "returns 400. This is the source that provides general, all-industry US "
                    "breadth, so its absence is a real coverage limit, not a formality."
                ),
                "required": f"{connector.ENV_APP_ID} and {connector.ENV_APP_KEY}",
            })
            continue

        outcome.attempted.append(provider)
        if connector.attribution:
            outcome.attributions.append(connector.attribution)
        budget = state.budget_for(
            provider, max_pages_per_source or connector.max_requests_per_run
        )

        if isinstance(connector, PaginatedFeedConnector):
            # FRESH-FIRST plus bounded catch-up.
            #
            # Measured source contract (Himalayas, 2026-09-24): the browse cursor is a DESCENDING
            # timestamp — page 1 held a 14:20 posting and each saved cursor pointed strictly older.
            # So resuming only from the saved cursor walks away from new arrivals and never returns,
            # which is exactly what the review's two-run probe observed.
            #
            # The rule: spend one page on the HEAD every run so a posting that appeared since the
            # last check is seen promptly, then spend the remaining budget continuing the backfill
            # from the saved cursor. The saved cursor tracks the CATCH-UP position only, so the
            # backfill still advances monotonically instead of restarting at page one forever.
            # When the budget is a single page and a backfill is outstanding, head and catch-up
            # alternate by run, so neither is permanently starved.
            pages_budget = max_pages_per_source or connector.max_requests_per_run
            saved_cursor = state.source_cursors.get(provider)
            saved_pending = state.pending_head(provider)
            head_frontier = _aware_dt(_parse_iso(state.head_frontier_at.get(provider)))
            head_newest: list = []
            any_success = False
            pages_done = 0
            stopped_early = False
            inaccessible_before = len(outcome.inaccessible)

            def _walk(worklist, budget, *, phase, stop_at=None, frontier=None,
                      recent_only=False):
                """Fetch pages from `worklist`, following each page's own continuation first.

                `worklist` holds `(cursor, on_head_chain)` pairs. Returns the cursors this walk could
                NOT traverse, newest first — its debt. A page that raised, came back labelled
                something other than a success, or was never reached before the budget ran out stays
                in that list. Returning it is the repair: the old walk returned a single position and
                a stop reason, and every reason but "budget" made the caller drop the range, while
                the observed frontier advanced anyway and claimed it.

                `on_head_chain` marks the contiguous chain that starts at page one. Only that chain
                may stop at `frontier`. It is the one walk whose coverage runs unbroken from the
                newest posting downward, so arriving at already-observed ground really does mean the
                rest was read. A chain resumed from an owed range carries no such guarantee: stopping
                it at the frontier would discard a continuation that nothing else records, which is
                the same silent loss in a new place. Resumed chains still end at the recent-time
                horizon, the backfill's position, the feed end or a repeated cursor, so they remain
                bounded and cannot become a recrawl.
                """
                nonlocal any_success, pages_done, stopped_early
                work: list[tuple[str | None, bool]] = list(worklist)
                owed: list[str] = []
                visited: set[str | None] = set()
                spent = 0
                while work and spent < budget and budget_obj.remaining > 0:
                    cursor, on_head_chain = work.pop(0)
                    if cursor in visited:
                        continue
                    visited.add(cursor)
                    token = cursor or "all"
                    # Charge the attempt BEFORE making it. A budget that counts only completed
                    # downloads is not a bound — the review measured 4 requests under a budget of 3
                    # because the request that raised was free.
                    budget_obj.requests_spent += 1
                    pages_done += 1
                    spent += 1
                    try:
                        fr = fetcher(provider, token, connector.endpoint(token))
                    except Exception as exc:  # noqa: BLE001 - one page must not fail the stage
                        budget_obj.failures += 1
                        outcome.inaccessible.append({
                            "target": f"{provider} {phase} page {spent}",
                            "reason": f"fetch raised {type(exc).__name__}: {exc}",
                        })
                        stopped_early = True
                        # The range stays OWED. A failure is not coverage. Page one needs no entry:
                        # it is requested first on every run regardless.
                        if cursor:
                            owed.append(cursor)
                        continue
                    snapshot, jobs = connector.build_snapshot(token, fr)
                    if snapshot.status not in (
                        SnapshotStatus.SUCCESS, SnapshotStatus.EMPTY_SUCCESS
                    ):
                        outcome.inaccessible.append({
                            "target": f"{provider} {phase} page {spent}",
                            "reason": (
                                f"download labelled {snapshot.status.value}"
                                + (f" ({snapshot.error_class})" if snapshot.error_class else "")
                            ),
                        })
                        outcome.snapshots.append((snapshot, [], fr.raw_bytes))
                        stopped_early = True
                        # A partial body is a partial READ: the range is still owed, exactly as a
                        # raised request is. Its continuation token cannot be trusted either.
                        if cursor:
                            owed.append(cursor)
                        continue
                    kept = _filter_and_stamp(jobs, outcome, now=now)
                    outcome.jobs.extend(kept)
                    outcome.snapshots.append((snapshot, kept, fr.raw_bytes))
                    any_success = True

                    families: dict[str, int] = {}
                    for job in kept:
                        for family in (job.discovery_query_family or "").split(","):
                            if family:
                                families[family] = families.get(family, 0) + 1
                    for family, count in families.items():
                        record_coverage(
                            state, family_key=family, run_id=run_id, now=now,
                            records=count, pages=1, saturated=False,
                        )

                    # Did this page still hold recent arrivals? Only a recent-phase walk asks. An
                    # undated posting counts as recent: the walk must not step PAST a new arrival
                    # because the provider published no date. The page budget, not the date, bounds it.
                    if recent_only:
                        horizon = now - timedelta(hours=HEAD_RECENT_HOURS)
                        published = [_aware_dt(j.provider_published_at) for j in kept]
                        page_has_recent = (not kept) or any(
                            stamp is None or stamp >= horizon for stamp in published
                        )
                        newest = max((s for s in published if s is not None), default=None)
                        if newest is not None and on_head_chain:
                            # Observation is recorded only from the contiguous chain, so the frontier
                            # can never be advanced by a page reached out of order.
                            head_newest.append(newest)
                        if not page_has_recent:
                            # Older than the recent window: from here down is the backfill's work,
                            # a boundary in TIME rather than a claim about what was read.
                            continue
                        if (
                            on_head_chain and frontier is not None
                            and newest is not None and newest <= frontier
                        ):
                            # The contiguous chain has reached ground it already covered. Ranges the
                            # walk still owes are in `head_pending`, not implied by this stop.
                            continue

                    try:
                        nxt = connector.next_cursor(json.loads(fr.raw_bytes.decode("utf-8")))
                    except Exception:  # noqa: BLE001 - a missing token just ends the walk
                        nxt = None
                    if not nxt:
                        continue                      # reached the end of the feed
                    if stop_at is not None and nxt == stop_at:
                        # Met the historical backfill's own position. Handing over avoids spending a
                        # second request on the page the catch-up is about to fetch.
                        continue
                    if nxt in visited or any(nxt == pending for pending, _ in work):
                        if nxt in visited:
                            outcome.inaccessible.append({
                                "target": provider,
                                "reason": (
                                    f"provider repeated pagination cursor {nxt!r}; stopped to avoid "
                                    "an endless crawl, coverage is partial"
                                ),
                            })
                            stopped_early = True
                        # Already walked this run, or already owed: do not queue it twice.
                        continue
                    # Follow this page's own continuation before any older owed range: the feed is
                    # ordered newest first, so depth-first here IS newest-first.
                    work.insert(0, (nxt, on_head_chain))
                return owed + [cursor for cursor, _ in work if cursor and cursor not in visited]

            budget_obj = budget
            # Page one always leads: seeing a posting that appeared since the last check is the
            # operator's priority. Ranges still owed from earlier runs follow it, newest first.
            head_work = [(None, True)] + [(cursor, False) for cursor in saved_pending]
            dropped_pending: list[str] = []
            if saved_cursor is None:
                # No backfill outstanding: this walk IS the catch-up, so it must not stop at the
                # recent horizon. Owed ranges lie on the same descending chain and are walked
                # through on the way down; whatever is still unreached stays owed.
                owed = _walk(head_work, pages_budget, phase="head")
                state.source_cursors[provider] = owed[0] if owed else None
                dropped_pending = state.set_pending_head(provider, owed[1:])
                state.last_feed_phase[provider] = "head"
            elif pages_budget >= 2:
                # The head walk CONTINUES while it is still finding recent arrivals, because a burst
                # or a missed weekend puts new postings on page two and beyond. Previously it took
                # exactly one page and threw away the continuation cursor, so a job on page two was
                # never fetched and the run jumped straight back to the historical backlog.
                #
                # It is bounded two ways so the old catch-up cannot be starved: at least one page is
                # always reserved for the backfill, and the walk stops as soon as a page holds
                # nothing recent, reaches ground a previous run already covered, or meets the
                # backfill's own position. Anything still unfetched is SAVED and resumed next run.
                head_budget = pages_budget - 1
                before_head = pages_done
                head_owed = _walk(
                    head_work, head_budget, phase="head", stop_at=saved_cursor,
                    frontier=head_frontier, recent_only=True,
                )
                head_pages = pages_done - before_head
                dropped_pending = state.set_pending_head(provider, head_owed)
                if head_owed:
                    # Recent ranges still outstanding: visible and resumable, never discarded. This
                    # now covers a page that FAILED or came back partial as well as one the budget
                    # never reached — the old code reported only the budget case and dropped the rest.
                    outcome.inaccessible.append({
                        "target": f"{provider} recent arrivals",
                        "reason": (
                            f"{len(head_owed)} recent page range(s) are still untraversed after the "
                            f"{head_pages} page(s) this run could spend on the feed head; every one "
                            "is saved and resumed next run, and one page was still reserved for the "
                            "historical backfill"
                        ),
                    })

                catch_up_budget = max(1, pages_budget - head_pages)
                catch_up_owed = _walk(
                    [(saved_cursor, False)], catch_up_budget, phase="catch-up"
                )
                state.source_cursors[provider] = catch_up_owed[0] if catch_up_owed else None
                state.last_feed_phase[provider] = "both"
            else:
                # One page and a backfill outstanding. The head is NOT negotiable: the operator's
                # priority is seeing a posting that appeared since the last check, and alternating
                # would make a fresh job wait a whole run. So the head takes the page and the
                # backfill's starvation is REPORTED rather than hidden — a visible tradeoff the
                # operator can fix by raising the budget, not a silent choice made for them.
                head_owed = _walk(head_work, 1, phase="head", stop_at=saved_cursor,
                                  frontier=head_frontier, recent_only=True)
                dropped_pending = state.set_pending_head(provider, head_owed)
                state.last_feed_phase[provider] = "head"
                if head_owed:
                    outcome.inaccessible.append({
                        "target": f"{provider} recent arrivals",
                        "reason": (
                            f"page budget is 1, so {len(head_owed)} recent page range(s) could not "
                            "be traversed this run; each is saved and resumed rather than dropped"
                        ),
                    })
                outcome.inaccessible.append({
                    "target": f"{provider} backfill",
                    "reason": (
                        "page budget is 1 and a backfill is outstanding, so the single page went to "
                        "the feed head to keep new arrivals prompt; the backfill made no progress "
                        "this run. Two or more pages per run lets both proceed "
                        f"(this source's configured budget is {connector.max_requests_per_run})."
                    ),
                })

            if dropped_pending:
                # Only reachable if a feed keeps producing untraversed recent ranges faster than the
                # budget can drain them. Persisted state stays bounded, and the loss is stated.
                outcome.inaccessible.append({
                    "target": f"{provider} recent arrivals",
                    "reason": (
                        f"{len(dropped_pending)} oldest untraversed recent range(s) exceeded the "
                        "per-source limit on saved ranges and were dropped; coverage of them is "
                        "partial and the historical backfill is the remaining path to those pages"
                    ),
                })

            # Remember the newest posting the CONTIGUOUS chain from page one saw, so the next run can
            # stop there instead of paying to re-read it. This is an observation, not a coverage
            # claim: ranges this run could not traverse are recorded in `head_pending`, and the stop
            # above is applied only to that same contiguous chain. Separating the two is the repair —
            # P04 advanced this frontier from the pages it did read and so claimed the ones it did not.
            if head_newest:
                newest_seen = max(head_newest)
                previous_frontier = _aware_dt(_parse_iso(state.head_frontier_at.get(provider)))
                if previous_frontier is None or newest_seen > previous_frontier:
                    state.head_frontier_at[provider] = newest_seen.isoformat()

            remaining = state.source_cursors.get(provider)
            still_owed = state.pending_head(provider)
            if any_success:
                outcome.succeeded.append(provider)
            if remaining or still_owed or stopped_early:
                for family, cov in state.coverage.items():
                    if cov.last_covered_run == run_id:
                        cov.saturated = True
                        cov.next_cursor = remaining
                state.backlog.pending.append(BacklogItem(
                    family_key=f"{provider}-feed", phrase=f"{provider} browse continuation",
                    page=pages_done + 1, where=None,
                ))
                state.backlog.reason = (
                    state.backlog.reason
                    or (
                        f"{provider} feed has {len(still_owed)} untraversed recent page range(s) "
                        "plus its historical position saved; all resumable"
                        if still_owed and remaining else
                        f"{provider} feed has more pages; position saved and resumable"
                        if remaining else
                        f"{provider} has {len(still_owed)} untraversed recent page range(s) saved "
                        "and resumable"
                        if still_owed else
                        f"{provider} pagination stopped before the end of the feed; coverage partial"
                    )
                )
            else:
                state.backlog.pending = [
                    item for item in state.backlog.pending
                    if item.family_key != f"{provider}-feed"
                ]

        elif isinstance(connector, BulkFeedConnector):
            # One request returns the provider's whole current feed; the query plan is applied
            # locally. Coverage is therefore "everything this feed published", which is recorded
            # per family so the report can say which questions the feed actually answered.
            board_token = "all"
            try:
                fr = fetcher(provider, board_token, connector.endpoint(board_token))
            except Exception as exc:  # noqa: BLE001 - one source must not fail the stage
                budget.failures += 1
                outcome.inaccessible.append(
                    {"target": provider, "reason": f"fetch raised {type(exc).__name__}: {exc}"}
                )
                continue
            budget.requests_spent += 1
            snapshot, jobs = connector.build_snapshot(board_token, fr)
            if snapshot.status not in (SnapshotStatus.SUCCESS, SnapshotStatus.EMPTY_SUCCESS):
                outcome.inaccessible.append({
                    "target": provider,
                    "reason": (
                        f"download labelled {snapshot.status.value}"
                        + (f" ({snapshot.error_class})" if snapshot.error_class else "")
                    ),
                })
                outcome.snapshots.append((snapshot, [], fr.raw_bytes))
                continue

            kept = _filter_and_stamp(jobs, outcome, now=now)
            outcome.succeeded.append(provider)
            outcome.jobs.extend(kept)
            outcome.snapshots.append((snapshot, kept, fr.raw_bytes))

            families: dict[str, int] = {}
            for job in kept:
                for family in (job.discovery_query_family or "").split(","):
                    if family:
                        families[family] = families.get(family, 0) + 1
            for family, count in families.items():
                record_coverage(
                    state, family_key=family, run_id=run_id, now=now, records=count, pages=0,
                )
            # A bulk feed answers whatever it answers; it cannot be asked for more, so nothing here
            # is marked saturated. Its ceiling is the feed's own size, which is not a hidden limit.
        else:
            # Query-driven source: phrase x location scope, under the request budget.
            scopes = location_scopes if location_scopes is not None else LOCATION_SCOPES
            carried = [
                item for item in state.backlog.pending
                if not item.family_key.endswith("-feed")
            ]
            work, backlog = allocate(
                plan, budget, backlog_first=carried, location_scopes=scopes,
            )
            feed_items = [i for i in state.backlog.pending if i.family_key.endswith("-feed")]
            backlog.pending = feed_items + backlog.pending
            state.backlog = backlog
            if backlog.pending:
                mark_deferred(
                    state, {item.family_key for item in backlog.pending},
                    backlog.reason or "request budget exhausted",
                )
            any_success = False
            for item in work:
                family, phrase, page, where = (
                    item.family_key, item.phrase, item.page, item.where or ""
                )
                token = f"{page}|{phrase}|{where}"
                try:
                    fr = fetcher(provider, token, connector.endpoint(token))
                except Exception as exc:  # noqa: BLE001
                    budget.failures += 1
                    outcome.inaccessible.append(
                        {"target": f"{provider} {item.label()}",
                         "reason": f"fetch raised {type(exc).__name__}: {exc}"}
                    )
                    # A failed query returns to the backlog so the next run retries it.
                    state.backlog.pending.append(item)
                    continue
                budget.requests_spent += 1
                snapshot, jobs = connector.build_snapshot(token, fr)
                if snapshot.status not in (SnapshotStatus.SUCCESS, SnapshotStatus.EMPTY_SUCCESS):
                    outcome.inaccessible.append({
                        "target": f"{provider} {item.label()}",
                        "reason": f"download labelled {snapshot.status.value}",
                    })
                    state.backlog.pending.append(item)
                    continue
                for job in jobs:
                    job.discovery_query = phrase
                    job.discovery_query_family = family
                kept = _filter_and_stamp(jobs, outcome, now=now)
                outcome.jobs.extend(kept)
                outcome.snapshots.append((snapshot, kept, fr.raw_bytes))
                any_success = True
                # A full page strongly suggests more results exist behind it.
                saturated = len(jobs) >= connector.results_per_page
                record_coverage(
                    state, family_key=family, run_id=run_id, now=now,
                    records=len(kept), pages=1, saturated=saturated,
                )
                if saturated:
                    state.backlog.pending.append(BacklogItem(
                        family_key=family, phrase=phrase, page=page + 1, where=item.where,
                    ))
                    state.backlog.reason = (
                        state.backlog.reason
                        or "one or more query families returned a full page; the next page is queued"
                    )
            if any_success:
                outcome.succeeded.append(provider)

    # ---- observe employers, then evaluate admission -------------------------------------------
    for job in outcome.jobs:
        if not job.employer_name:
            continue
        observe(
            growth,
            employer_name=job.employer_name,
            now=now,
            source_id=job.source_id,
            query=job.discovery_query or job.discovery_query_family,
            job_id=job.job_id,
            careers_url=job.employer_careers_url or job.apply_url or job.posting_url,
        )
    # ---- resolve employer careers URLs so growth has something to admit -----------------------
    # Measured on 2026-09-24: the keyless feeds publish aggregator apply links only, and none of
    # their payloads embed an employer board URL. Without this step every discovered employer stays
    # an unsupported lead, so the growth loop needs it — bounded, guarded, and off by default.
    needing = [
        (candidate.employer_name, candidate.careers_url or "")
        for candidate in sorted(
            growth.candidates.values(),
            key=lambda c: (-c.observation_count, c.employer_key),
        )
        if candidate.board_token is None and candidate.careers_url
    ]
    resolution = resolve_careers_urls(needing, now=now, env=env)
    outcome.resolution = {
        "enabled": resolution.enabled,
        "disabled_reason": resolution.disabled_reason,
        "requests_spent": resolution.spent,
        "resolved": len(resolution.resolved),
        "refused": resolution.refused[:10],
        "candidates_needing_resolution": len(needing),
    }
    for employer_name, careers_url in resolution.resolved.items():
        observe(growth, employer_name=employer_name, now=now, careers_url=careers_url)

    if monitored_count is None:
        outcome.admission = {
            "skipped": (
                "the run manifest could not be read, so the monitored-source count is unknown; "
                "no admission decision is made this round and every candidate keeps its state"
            ),
        }
    else:
        outcome.admission = admit_pass(
            growth, policy, monitored_count=monitored_count, now=now
        )

    # An operator-disabled employer's postings are dropped from the result set here, after being
    # counted, so the disable is honored without pretending the employer was never seen.
    outcome.jobs = [
        job for job in outcome.jobs if not _employer_disabled(growth, job.employer_name)
    ]
    return outcome


def _filter_and_stamp(jobs, outcome: DiscoveryOutcome, *, now: datetime) -> list[CanonicalJob]:
    """Drop records that are plainly not an actionable opening; stamp verification metadata.

    This is the crawler's only filter. Role suitability is the screener's job, so nothing is removed
    here for being a poor fit — only for not being a job opening at all.
    """
    kept: list[CanonicalJob] = []
    for job in jobs:
        reason = is_obvious_non_job(job.title, job.description_text)
        if reason:
            outcome.rejected_non_jobs += 1
            continue
        if not job.employer_name:
            # No employer means we cannot dedupe it, verify it, or tell the operator who to apply
            # to. It is a lead with no subject; record it as inaccessible rather than shipping it.
            outcome.inaccessible.append({
                "target": job.job_id,
                "reason": "record carried no employer name; cannot verify or deduplicate it",
            })
            continue
        job.source_kind = SourceKind.DISCOVERY_FEED
        kept.append(job)
    return kept


# --------------------------------------------------------------------------------------------------
# AWS wrapper
# --------------------------------------------------------------------------------------------------
def _live_fetcher(provider: str, board_token: str, url: str):
    """Fetch the URL the CALLER built, not one this function rebuilds.

    The previous version threw `url` away and called `fetch_raw(board_token)` on the unbound registry
    connector, which rebuilt the endpoint from `os.environ`. That silently stripped credentials
    resolved from SSM. The URL passed in was already built by the env-bound connector, so it is the
    authoritative one; `fetch_raw` still validates its host.
    """
    connector = get_discovery_connector(provider)
    return connector.fetch_raw(board_token, url=url)


def _load_optional(s3, bucket: str, key: str):
    """Read a JSON object that may not exist yet, without swallowing a permission failure.

    Absence is established by LISTING the exact key, never inferred from a failed GetObject. S3
    answers a GetObject for a missing key with 403 unless the caller may list the bucket, and
    whether a prefix-CONDITIONED list grant counts for that implicit check is observed rather than
    documented. A ListObjectsV2 whose Prefix is the key carries `s3:prefix` = the key, which the
    role's `discovery/*` grant matches by definition. So: listed absent -> None; listed present ->
    GetObject, and any failure of it (403, 5xx) raises; a refused listing raises. A corrupt object
    raises from the JSON parse. This is the report's `_load_optional_json` pattern.
    """
    listing = s3.list_objects_v2(Bucket=bucket, Prefix=key, MaxKeys=1)
    if not any(item.get("Key") == key for item in listing.get("Contents", [])):
        return None
    return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())


def _usable_by_provider(outcome: DiscoveryOutcome) -> dict[str, bool]:
    """Did each provider this run TOUCHED return at least one usable page?

    Every provider that was attempted appears, including one whose pages all failed. A feed missing
    from this map entirely would leave its view frozen and unexplained on exactly the runs where the
    explanation matters.
    """
    usable: dict[str, bool] = {provider: False for provider in outcome.attempted}
    for snapshot, _jobs, _raw in outcome.snapshots:
        provider = snapshot.source_id.partition(":")[0]
        usable[provider] = usable.get(provider, False) or (
            snapshot.status in (SnapshotStatus.SUCCESS, SnapshotStatus.EMPTY_SUCCESS)
        )
    return usable


def _recoverable_providers(outcome: DiscoveryOutcome) -> list[str]:
    """Every feed whose accepted-capture object this run must read, in a deterministic order.

    Recovery may not depend on which providers this particular run touched: the whole point of the
    debt is that a feed which failed, or was not reached at all, still has work owed from an earlier
    round. The set is therefore the full connector registry plus anything this run touched, which
    keeps every key DERIVED rather than discovered: recovery never lists a prefix to find debt.
    """
    return sorted({
        *discovery_providers(),
        *outcome.attempted,
        *(job.source_id.partition(":")[0] for job in outcome.jobs),
    })


def load_pending_publication(s3, bucket: str, providers: list[str] | None = None
                             ) -> PendingPublication:
    """Read what is owed, from every feed's accepted-capture object and the aggregate.

    The per-feed objects are the record of acceptance and are the authority. The aggregate object is
    read as well, and unioned in, because the currently deployed code writes only that one — a debt
    it recorded must be settled by the first run of this code, not orphaned by it.
    """
    pending = PendingPublication()
    for provider in providers if providers is not None else discovery_providers():
        raw = _load_optional(s3, bucket, s3layout.discovery_owed_publication_key(provider))
        if raw:
            pending = pending.merged(PendingPublication.model_validate(raw))
    raw_aggregate = _load_optional(s3, bucket, s3layout.discovery_pending_publication_key())
    if raw_aggregate:
        pending = pending.merged(PendingPublication.model_validate(raw_aggregate))
    return pending


def _put_owed_publication(s3, bucket: str, provider: str, pending: PendingPublication) -> None:
    """Write ONE feed's accepted-capture object. This write is the durable acceptance point."""
    s3.put_object(
        Bucket=bucket, Key=s3layout.discovery_owed_publication_key(provider),
        Body=pending.for_provider(provider).model_dump_json().encode(),
        ContentType="application/json",
    )


def _put_pending_publication(s3, bucket: str, pending: PendingPublication) -> None:
    """Refresh the aggregate object the coverage receipt and the report read.

    Not the acceptance record and not what recovery depends on, so a failure here costs visibility
    for one round and no accepted observation.
    """
    s3.put_object(
        Bucket=bucket, Key=s3layout.discovery_pending_publication_key(),
        Body=pending.model_dump_json().encode(), ContentType="application/json",
    )


def accept_observations(s3, bucket: str, pending: PendingPublication, provider: str,
                        jobs: list[CanonicalJob], *, run_id: str, now: datetime,
                        feed_produced_usable_page: bool
                        ) -> tuple[PendingPublication, list[dict]]:
    """Durably ACCEPT one feed's observations for this run. The commit boundary, in one call.

    `normalized/` is not a usable handoff: it is keyed by the page and the `dt` that produced it,
    nothing downstream reads it, and a same-day retry OVERWRITES it — so after an interrupted
    publication the retry's empty feed window destroys the only durable trace of the posting. The
    debt written here is keyed by run and provider, is unioned rather than replaced by a retry, and
    survives until the live view it belongs to has committed.

    It is written per feed and BEFORE that feed's SUCCESS sentinels, so no marker claiming the round
    succeeded can precede the record that makes the round's work recoverable.
    """
    pending, notices = pending.owe(
        provider,
        PendingPublicationBatch(
            run_id=run_id,
            observed_at=now,
            feed_produced_usable_page=feed_produced_usable_page,
            jobs=jobs,
        ),
        now=now,
    )
    _put_owed_publication(s3, bucket, provider, pending)
    return pending, notices


def drain_publication(s3, bucket: str, pending: PendingPublication, *, run_id: str, now: datetime
                      ) -> tuple[dict, PendingPublication]:
    """Publish every owed batch into its feed's live view — the report's actual input.

    Writing `normalized/` alone was the gap P06 measured: it is a per-fetch record keyed by the page
    that produced it, and nothing downstream reads it. The live view is the durable, feed-keyed
    candidate representation, owned solely by this stage and consumed solely by report assembly.

    A feed whose pages all failed this run is merged with `feed_produced_usable_page=False`, so its
    postings keep their previous verification age instead of being silently re-aged, and its success
    history does not advance. That is what stops a failed round from presenting yesterday's coverage
    as today's success.

    One feed at a time, and each feed's debt is cleared only after ITS view has committed. So a
    failure partway through leaves every feed in one of two states and never a third: view committed
    and nothing owed, or view untouched and the work still explicitly owed. A failure in the narrow
    window between those two writes leaves a committed batch owed a second time, which the replay
    absorbs — a posting records which runs observed it, so re-applying a batch changes nothing.
    """
    summary: dict[str, dict] = {}
    for provider in pending.owed_providers():
        batches = list(pending.batches[provider])
        key = s3layout.discovery_live_key(provider)
        raw_prior = _load_optional(s3, bucket, key)
        prior = DiscoveryLiveView.model_validate(raw_prior) if raw_prior else None
        source_id = f"{provider}:{DiscoveryConnector.FEED_SLICE}"
        view = publish_live_view(prior, batches, source_id=source_id, now=now)
        s3.put_object(
            Bucket=bucket, Key=key, Body=view.model_dump_json().encode(),
            ContentType="application/json",
        )
        pending = pending.settle(provider)
        # Settle the accepted-capture object FIRST: it is the one recovery reads, so clearing it is
        # what actually ends the debt. The aggregate is refreshed after, and a failure between the
        # two leaves only a stale receipt — the batch is settled and the next round's load agrees.
        _put_owed_publication(s3, bucket, provider, pending)
        _put_pending_publication(s3, bucket, pending)

        this_run = [batch for batch in batches if batch.run_id == run_id]
        replayed = [batch for batch in batches if batch.run_id != run_id]
        summary[source_id] = {
            "live_jobs": len(view.jobs),
            "observed_this_run": sum(len(batch.jobs) for batch in this_run),
            "feed_produced_usable_page": any(
                batch.feed_produced_usable_page for batch in this_run
            ),
            "observation_count": view.observation_count,
            "retired_for_retention": len(view.retired_for_retention),
            # Recovery is stated, never implied by a count that happens to be right. A replayed batch
            # keeps the run id and the observation time of the round that actually saw the posting.
            "replayed_runs": sorted({
                every for batch in replayed for every in batch.all_run_ids()
            }),
            "replayed_observations": sum(len(batch.jobs) for batch in replayed),
        }
    return summary, pending


def _coverage_body(outcome: DiscoveryOutcome, pending: PendingPublication,
                   bound_notices: list[dict]) -> bytes:
    """The coverage receipt, carrying whatever publication is still owed.

    Owed batches are added to `inaccessible` as well as to their own field, because that is the list
    the morning report renders. A receipt that said a source succeeded while its postings were still
    waiting to be published would be the quiet erasure this repair exists to prevent — the report
    would show a coverage claim no candidate row backs up.
    """
    doc = outcome.coverage_doc()
    owed = pending.summary()
    entries = list(doc.get("inaccessible", [])) + list(bound_notices)
    for provider, batches in owed.items():
        for batch in batches:
            entries.append({
                "target": f"{provider} pending publication from run {batch['run_id']}",
                "reason": (
                    f"{len(batch['job_ids'])} posting(s) observed in run {batch['run_id']} are "
                    "durably captured but have not yet been folded into this feed's live view, so "
                    "they cannot appear below yet. They are owed and will be published by the next "
                    "discovery round without the feed having to return them again"
                ),
                "job_ids": batch["job_ids"],
            })
    doc["inaccessible"] = entries
    doc["pending_publication"] = owed
    # Kept under its established name because the report and the release checks already read it.
    # Its contents are no longer only losses: a `compaction` notice reports attribution folded away
    # with every posting still owed, and a `retention` notice reports the one case that removes
    # anything — a posting the live view's own retention would retire in the same merge.
    doc["pending_publication_dropped"] = bound_notices
    doc["pending_publication_bounds"] = bound_notices
    return json.dumps(doc, default=str).encode()


def persist(s3, bucket: str, outcome: DiscoveryOutcome, *, run_id: str, dt: str,
            now: datetime | None = None) -> dict:
    """Write discovery results through the same forward tiers monitoring uses.

    The ORDER here is the repair, so it is stated rather than left to be inferred. Per provider, in
    provider order:

      1. ACCEPT — union this feed's observations into its own owed-publication object and write it.
         This is the FIRST durable write of the feed's round, and it is the durable acceptance
         point. Putting it first is what makes the acceptance statement decidable rather than a
         label: there is no state in which a posting is durably captured but not yet recoverable,
         because nothing durable precedes it. Before it, the round is simply incomplete and the
         provider must return the posting again; after it, no later failure can put the posting out
         of automatic reach.
      2. that feed's snapshots — `raw/`, `normalized/`, `status/`. The court of record of HOW the
         postings were obtained. The cost of ordering these second is explicit: a failure here can
         leave a published posting whose raw snapshot is missing for that date. That is a gap in the
         audit trail, and it is preferred to the alternative the earlier order produced, which was
         an intact audit trail for a posting the morning report could never show.
      3. that feed's SUCCESS sentinels, so no marker claiming the round succeeded is ever written
         before the record that makes the round's work recoverable.

    Then once for the run:

      4. the aggregate owed-publication receipt, then coverage, traversal state, growth and the
         proposed registry. Coverage carries the owed set, so progress cannot read as complete while
         observations are unpublished.
      5. DRAIN — publish each feed's owed batches into its live view, settle that feed's own object,
         then refresh the aggregate.
      6. rewrite the receipt with the residual, which is reached only if the drain completed.

    P07 had neither (2) nor (5): the live-view write simply followed the progress records, and a
    storage failure there stranded observations that were already durable. P08 added them but put
    (2) after every forward-tier write and behind ONE aggregate key, so refusing that single write
    stranded a posting that was already durably normalized — nothing owed, nothing to replay, and a
    same-day retry that overwrote `normalized/` for that `dt` with an emptier feed window.
    """
    now = now or datetime.now(timezone.utc)
    written = 0
    bound_notices: list[dict] = []
    pending = load_pending_publication(s3, bucket, _recoverable_providers(outcome))

    jobs_by_provider: dict[str, list[CanonicalJob]] = {}
    for job in outcome.jobs:
        jobs_by_provider.setdefault(job.source_id.partition(":")[0], []).append(job)
    usable = _usable_by_provider(outcome)
    snapshots_by_provider: dict[str, list[tuple]] = {}
    for entry in outcome.snapshots:
        snapshots_by_provider.setdefault(entry[0].source_id.partition(":")[0], []).append(entry)

    for provider in sorted({*usable, *jobs_by_provider, *snapshots_by_provider}):
        # ---- 1. the durable acceptance point, before any other write for this feed ---------------
        pending, notices = accept_observations(
            s3, bucket, pending, provider, jobs_by_provider.get(provider, []),
            run_id=run_id, now=now,
            feed_produced_usable_page=usable.get(provider, False),
        )
        bound_notices.extend(notices)

        # ---- 2. the court of record for this feed -------------------------------------------------
        for snapshot, jobs, raw_bytes in snapshots_by_provider.get(provider, []):
            _, _, board = snapshot.source_id.partition(":")
            if raw_bytes:
                raw_key = s3layout.raw_snapshot_key(provider, board, dt, snapshot.snapshot_id)
                s3.put_object(
                    Bucket=bucket, Key=raw_key, Body=gzip.compress(raw_bytes),
                    ContentType="application/json", ContentEncoding="gzip",
                )
            s3.put_object(
                Bucket=bucket, Key=s3layout.normalized_key(provider, board, dt),
                Body=json.dumps([j.model_dump(mode="json") for j in jobs], default=str).encode(),
                ContentType="application/json",
            )
            s3.put_object(
                Bucket=bucket, Key=s3layout.source_status_key(provider, board),
                Body=json.dumps({
                    "source_id": snapshot.source_id,
                    "status": snapshot.status.value,
                    "snapshot_id": snapshot.snapshot_id,
                    "fetched_at": snapshot.fetched_at.isoformat(),
                    "job_count_observed": snapshot.job_count_observed,
                    "http_status": snapshot.http_status,
                    "error_class": snapshot.error_class,
                    "source_kind": SourceKind.DISCOVERY_FEED.value,
                }, default=str).encode(),
                ContentType="application/json",
            )
            written += 1

        # ---- 3. the success markers, last ----------------------------------------------------------
        for snapshot, _jobs, _raw in snapshots_by_provider.get(provider, []):
            _, _, board = snapshot.source_id.partition(":")
            if snapshot.status not in (SnapshotStatus.SUCCESS, SnapshotStatus.EMPTY_SUCCESS):
                continue
            s3.put_object(
                Bucket=bucket,
                Key=s3layout.collect_sentinel_key(run_id, provider, board),
                Body=json.dumps({
                    "run_id": run_id, "source_id": snapshot.source_id,
                    "snapshot_id": snapshot.snapshot_id, "status": snapshot.status.value,
                    "job_count": snapshot.job_count_observed,
                    "written_at": datetime.now(timezone.utc).isoformat(),
                }).encode(),
                ContentType="application/json",
            )

    # ---- 4. the aggregate receipt, then progress --------------------------------------------------
    _put_pending_publication(s3, bucket, pending)
    s3.put_object(
        Bucket=bucket, Key=s3layout.discovery_coverage_key(run_id),
        Body=_coverage_body(outcome, pending, bound_notices),
        ContentType="application/json",
    )
    s3.put_object(
        Bucket=bucket, Key=s3layout.discovery_state_key(),
        Body=outcome.state.model_dump_json().encode(), ContentType="application/json",
    )
    s3.put_object(
        Bucket=bucket, Key=s3layout.source_growth_key(),
        Body=outcome.growth.model_dump_json().encode(), ContentType="application/json",
    )
    # PROPOSED registry rows. Nothing applies them automatically: the active registry is never
    # mutated by a run, which is both the plan's requirement and what keeps a growth loop from
    # changing what tomorrow collects without the operator seeing it.
    s3.put_object(
        Bucket=bucket, Key=s3layout.proposed_registry_key(run_id),
        Body=json.dumps(proposed_registry_entries(outcome.growth), indent=2).encode(),
        ContentType="application/json",
    )
    # ---- 5. drain the owed publication into each feed's live view ---------------------------------
    live, pending = drain_publication(s3, bucket, pending, run_id=run_id, now=now)

    # ---- 6. the residual receipt, reached only if the drain completed -----------------------------
    s3.put_object(
        Bucket=bucket, Key=s3layout.discovery_coverage_key(run_id),
        Body=_coverage_body(outcome, pending, bound_notices),
        ContentType="application/json",
    )
    return {
        "snapshots_written": written,
        "live_views": live,
        "live_jobs_total": sum(entry["live_jobs"] for entry in live.values()),
        "replayed_observations": sum(
            entry.get("replayed_observations", 0) for entry in live.values()
        ),
        "pending_publication": pending.summary(),
        "pending_publication_dropped": bound_notices,
        "pending_publication_bounds": bound_notices,
    }


def _resolve_secrets(env=None) -> dict:  # pragma: no cover - AWS glue
    """Pull credential-gated API keys from SSM SecureString at runtime.

    Keys are NOT CloudFormation parameters and NOT template values: a secret in a template ends up
    in the stack's change sets and console history. The Lambda reads them at invoke time from a
    parameter path the operator populates separately, and if the path is absent the source simply
    stays credential-gated and says so in the coverage receipt.
    """
    import boto3

    env = dict(env if env is not None else os.environ)
    prefix = env.get("JPRS_SECRETS_SSM_PREFIX")
    if not prefix:
        return env
    try:
        ssm = boto3.client("ssm")
        page = ssm.get_parameters_by_path(Path=prefix, WithDecryption=True, Recursive=True)
        for param in page.get("Parameters", []):
            name = param["Name"].rsplit("/", 1)[-1]
            if param.get("Value"):
                env[name] = param["Value"]
    except Exception as exc:  # noqa: BLE001 - a missing/denied path is a gate, not a crash
        print(json.dumps({
            "discovery": "secrets_unavailable",
            "detail": f"{type(exc).__name__}: {exc}",
            "effect": "credential-gated sources stay gated and are named in the coverage receipt",
        }))
    return env


def handler(event, context):  # pragma: no cover - AWS glue
    import boto3

    bucket = os.environ["JPRS_BUCKET"]
    s3 = boto3.client("s3")
    now = datetime.now(timezone.utc)
    run_id = event.get("run_id") or now.strftime("%Y-%m-%d")
    dt = event.get("dt") or run_id

    state, growth = load_discovery_state(s3, bucket)
    raw_manifest = _load(s3, bucket, s3layout.run_manifest_key(run_id))
    manifest = raw_manifest or {}
    labels = manifest.get("source_labels", {}) or {}
    known = {str(v) for v in labels.values()}
    # Unknown, not zero, when the manifest could not be read: a zero would let admission pass the
    # monitored-source ceiling and persist a sticky ADMITTED on an assumption.
    monitored_count = (
        len(manifest.get("expected_sources", []) or []) if raw_manifest is not None else None
    )

    providers = [
        p.strip() for p in (os.environ.get("JPRS_DISCOVERY_PROVIDERS", "") or "").split(",")
        if p.strip()
    ] or None

    outcome = run_discovery(
        run_id=run_id, now=now, fetcher=_live_fetcher, providers=providers,
        state=state, growth=growth, known_employers=known, monitored_count=monitored_count,
        env=_resolve_secrets(),
    )
    result = persist(s3, bucket, outcome, run_id=run_id, dt=dt, now=now)
    return {
        "run_id": run_id,
        "discovery_attempted": sorted(outcome.attempted),
        "discovery_succeeded": sorted(outcome.succeeded),
        "jobs_discovered": len(outcome.jobs),
        "employers_observed": len(outcome.growth.candidates),
        "credential_gated": [g["provider"] for g in outcome.credential_gated],
        **result,
    }


def load_discovery_state(s3, bucket: str) -> tuple[DiscoveryState, SourceRegistryGrowth]:
    """Read the traversal state and growth ledger, starting empty ONLY when they do not exist.

    Both are rewritten at the end of every round, so a read that failed for any reason other than
    absence must stop the round: the previous loader turned a denied or unavailable read into an
    empty ledger and then overwrote the real one with it, losing owed traversal ranges and the
    operator's sticky source disables without a word. Absence is established by listing the exact
    key (`_load_optional`), which is what the role's `discovery/*` list grant is for; a refused
    listing, a failed read of a listed object and a corrupt object all raise.
    """
    state = DiscoveryState()
    raw_state = _load_optional(s3, bucket, s3layout.discovery_state_key())
    if raw_state is not None:
        state = DiscoveryState.model_validate(raw_state)
    growth = SourceRegistryGrowth()
    raw_growth = _load_optional(s3, bucket, s3layout.source_growth_key())
    if raw_growth is not None:
        growth = SourceRegistryGrowth.model_validate(raw_growth)
    return state, growth


def _load(s3, bucket, key):  # pragma: no cover - AWS glue
    """Lenient read, for the run manifest only.

    Discovery never writes the manifest and holds no list grant on `runs/`, so a manifest enumerate
    has not written yet is indistinguishable from a denied one. It supplies employer labels and the
    monitored-source count. An unreadable manifest therefore yields "unknown": labels are empty for
    the round, and admission is skipped rather than decided against a count of zero (see
    `handler`), so nothing derived from a failed read is persisted as a decision.
    """
    import botocore.exceptions

    try:
        return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    except botocore.exceptions.ClientError:
        return None
