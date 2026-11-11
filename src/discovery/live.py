"""Discovery's durable live-job view — the candidate representation report assembly consumes.

Why this exists at all
----------------------
Discovery already wrote `normalized/`, a per-fetch record of what one page returned. Report assembly
does not read it, and could not: it iterates the manifest's `expected_sources` (monitored employer
boards) and loads the DIFFER-owned `current/` set for each. So a posting from an employer nobody has
named reached S3 and stopped there — 295 jobs across 218 employers on 2026-09-25, zero of them in the
report. This module is the missing durable representation, and `assemble_report_input` is its reader.

Why it is not `current/` and not the differ
-------------------------------------------
The differ answers "what changed at this employer's board", and it may do so because an ATS board
returns the employer's ENTIRE open list. Absence from a healthy snapshot is therefore evidence about
the posting, and the grace clock, mass-drop guard and silent-subset latch are all built on that.

A discovery feed returns a moving WINDOW over many employers, bounded by a page budget. A posting
absent from today's window may have scrolled past the pages this run could afford, may sit behind a
cursor the budget never reached, or may be gone. Those are not distinguishable from the window, so
this view never derives closure from absence. It records POSITIVE observations only:

  observed this run    -> upsert, `last_seen_at` advances, observation count increments
  not observed         -> retained unchanged, with a stated last-verification age
  feed produced nothing usable this run -> nothing is said about any posting at all

The one bounded expiry is a RETENTION limit (`RETENTION_DAYS`), not a closure judgement, and it is
reported as such. Without it the view would grow without limit; with it, a posting that has not been
re-observed for three weeks stops being carried and the report says so in those words.

Why publication is owed, and why the debt is written where it is
----------------------------------------------------------------
Writing the view is the LAST thing a discovery run does, and it is a separate external storage call
from the ones that already committed the same observations to `raw/`, `normalized/`, `status/` and
the coverage receipt. P07's review reproduced what a failure there costs: the posting is durably
captured, the retry meets a different feed window, `normalized/` for that `dt` is overwritten by the
retry, and the job never reaches the candidate representation in that run or any later one.

So the observations are OWED before publication is attempted (`PendingPublication`), and the debt is
cleared only after the view they belong to has committed. Replay is exactly idempotent rather than
merely convergent, because the failure can also land between those two writes: a posting records
which runs actually observed it, and no replay may move an observation backwards in time.

P08's review then found the same shape of defect one write earlier. P08 recorded the debt ONCE, at
an aggregate key, after every forward-tier write had committed — so refusing that first write
stranded a posting that was already durably normalized, with nothing owed and nothing to replay.
The debt is now written PER FEED (`s3layout.discovery_owed_publication_key`), and it is the FIRST
durable write of that feed's round — before `raw/`, before `normalized/`, before any sentinel. That
write is the durable acceptance point, and putting it first is what makes the acceptance statement
decidable: nothing durable precedes it, so there is no state in which a posting is captured but not
yet recoverable. One refused write costs that feed's new batch and nothing else.

And the bound on the debt no longer discards: see `MAX_OWED_BATCHES_PER_PROVIDER`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field

from src.common.models import SCHEMA_VERSION, CanonicalJob, SourceKind

# How long a posting is carried without being re-observed. A retention bound on stored state, never
# a statement that the opening closed. Three weeks spans a missed weekend, a multi-day outage and a
# budget-starved backfill with room to spare, and still keeps the view bounded.
RETENTION_DAYS = 21

# Prefix for the machine-greppable staleness marker, so each run REPLACES the previous one instead
# of appending a new sentence to the job every day.
STALE_MARKER_PREFIX = "last observed in this feed on "

# How many distinct unpublished batches one feed carries before the oldest ones are COMPACTED into
# a single carry-forward batch. P08 dropped them instead, and its own regression test required the
# drop; the review was right that this is a defect rather than a policy. An observation that is
# durably accepted is owed to the morning report, and a count of rounds is not a reason to stop
# owing it — the first healthy round after a backlog would itself have evicted the oldest job merely
# by enqueuing its own empty batch.
#
# Compaction keeps the bound without the loss: the jobs are unioned by identity and the earliest
# observation time of each is kept, so nothing becomes unreachable. What it does give up is per-round
# attribution for the folded rounds, and that is reported rather than silent. Across consecutive
# failed rounds a feed returns largely the same postings, so the union is barely larger than one
# round — which is exactly why this bound is affordable and dropping was never necessary.
MAX_OWED_BATCHES_PER_PROVIDER = 5

# Upper bound on the per-posting observation ledger. Retention already caps a posting at three weeks
# of daily rounds, so this is only reached by a pathological run cadence; keeping the most recent
# entries preserves the recent-replay idempotence that actually matters.
MAX_OBSERVED_RUN_IDS = 64


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class DiscoveryLiveJob(BaseModel):
    """One posting this feed has surfaced, with the observation record that owns its timing."""

    model_config = ConfigDict(extra="forbid")
    job: CanonicalJob
    first_seen_run_id: str
    last_seen_run_id: str
    # Runs in which this posting was ACTUALLY observed. Not runs that happened.
    observation_count: int = 1
    # WHICH runs those were. `observation_count` is this list's length, and that is the whole point:
    # a replayed batch names the run it came from, so re-applying it cannot inflate the count no
    # matter how many times, or in what order, it is replayed. A bare counter could only ever be
    # convergent; this is idempotent. Empty on a record written before this field existed, and seeded
    # from `last_seen_run_id` the first time such a record is touched.
    observed_run_ids: list[str] = Field(default_factory=list)
    # Ids this posting has previously carried. Kept so a released identity repair, or a provider that
    # rotates its own slugs, stays diagnosable instead of silently minting a second posting.
    alias_job_ids: list[str] = Field(default_factory=list)

    def runs_observed(self) -> list[str]:
        """The observation ledger, with a pre-ledger record read as its one recorded run."""
        return list(self.observed_run_ids) or [self.last_seen_run_id]


class DiscoveryLiveView(BaseModel):
    """Everything one discovery feed currently believes is open, and when it last looked."""

    model_config = ConfigDict(extra="forbid")
    source_id: str
    jobs: dict[str, DiscoveryLiveJob] = Field(default_factory=dict)
    # Run ids in which this feed produced at least one usable page. This is the feed's success
    # history, and it is what tells the report whether a first observation carries freshness
    # information — the same question `cold_start_sources` asks of a monitored board.
    observed_run_ids: list[str] = Field(default_factory=list)
    last_observed_run_id: str | None = None
    last_observed_at: datetime | None = None
    # Postings dropped by the retention bound in the most recent merge, and when.
    retired_for_retention: list[str] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @property
    def observation_count(self) -> int:
        return len(self.observed_run_ids)

    def canonical_jobs(self) -> list[CanonicalJob]:
        """The postings, with the view's authoritative timing already applied."""
        return [record.job for record in self.jobs.values()]


def _humanize_days(days: float) -> str:
    if days < 1:
        return "under a day"
    whole = int(days)
    return "1 day" if whole == 1 else f"{whole} days"


def _staleness_marker(*, last_seen_at: datetime, now: datetime) -> str:
    """The sentence a posting carries when this run did not see it again.

    Phrased as an observation about OUR coverage, because that is all an absent record supports. It
    deliberately does not say the posting closed, was withdrawn, or is stale in itself.
    """
    age = max(0.0, (now - last_seen_at).total_seconds() / 86400.0)
    return (
        f"{STALE_MARKER_PREFIX}{last_seen_at.date().isoformat()} "
        f"({_humanize_days(age)} ago) and not observed again since; a feed returns a moving window "
        "under a page budget, so absence from it is a gap in coverage and not a signal that the "
        "opening ended — confirm with the employer before ruling it out"
    )


def _without_stale_marker(job: CanonicalJob) -> list[str]:
    return [note for note in job.uncertainty if not note.startswith(STALE_MARKER_PREFIX)]


def merge_live_view(
    prior: DiscoveryLiveView | None,
    observed: list[CanonicalJob],
    *,
    source_id: str,
    run_id: str,
    now: datetime,
    feed_produced_usable_page: bool,
    retention_days: int = RETENTION_DAYS,
    observed_at: datetime | None = None,
) -> DiscoveryLiveView:
    """Fold one batch of observations into the durable view. Pure: no S3, no clock.

    `feed_produced_usable_page` is the gate that keeps a failed or wholly-inaccessible run from
    saying anything about any posting. On a failed run the view is returned with its postings and
    their timing untouched and its success history NOT extended, so the next report can see that the
    feed has not been re-verified rather than reading yesterday's coverage as today's.

    `now` is when this PUBLICATION is happening; `observed_at` is when the batch was OBSERVED, and it
    defaults to `now` for the ordinary case where a run publishes what it just fetched. They separate
    for a replayed batch, and keeping them apart is what stops recovery from lying: the posting keeps
    the timing of the round that actually saw it, so a job stranded yesterday is republished as
    yesterday's observation and not announced as freshly fetched. Retention and the staleness sentence
    are still measured from `now`, because those describe how current the stored view is.

    Replay is monotonic in time. A batch older than what the view already holds may add an observation
    and correct a first-sighting backwards, but it may not move `last_seen_at`, `last_seen_run_id` or
    the posting's content backwards — otherwise a batch owed from an interrupted round would roll back
    a later round's successful work on the same posting.
    """
    now = _aware(now)
    observed_at = _aware(observed_at) or now
    view = (
        prior.model_copy(deep=True)
        if prior is not None
        else DiscoveryLiveView(source_id=source_id)
    )
    view.source_id = source_id
    view.retired_for_retention = []

    if not feed_produced_usable_page:
        # Nothing was learned. Not even an absence: a run that could not read the feed has no
        # standing to age a posting it never looked for.
        return view

    if run_id not in view.observed_run_ids:
        view.observed_run_ids.append(run_id)
    if view.last_observed_at is None or observed_at >= view.last_observed_at:
        # Only a batch at least as recent as what the view records may claim to be its latest look.
        # Replaying an interrupted round must not make the feed appear to have gone quiet since.
        view.last_observed_run_id = run_id
        view.last_observed_at = observed_at

    seen_now: set[str] = set()
    for job in observed:
        fresh = job.model_copy(deep=True)
        fresh.source_kind = SourceKind.DISCOVERY_FEED
        existing = view.jobs.get(fresh.job_id)
        if existing is None:
            fresh.first_seen_at = _aware(fresh.first_seen_at) or observed_at
            fresh.last_seen_at = observed_at
            fresh.uncertainty = _without_stale_marker(fresh)
            view.jobs[fresh.job_id] = DiscoveryLiveJob(
                job=fresh, first_seen_run_id=run_id, last_seen_run_id=run_id,
                observation_count=1, observed_run_ids=[run_id],
            )
        else:
            existing_last = _aware(existing.job.last_seen_at)
            superseded = existing_last is not None and existing_last > observed_at
            # A newer observation of the same posting already stands. Keep ITS content and timing;
            # this older batch contributes only the fact that it was also observed back then.
            base = (existing.job if superseded else fresh).model_copy(deep=True)
            base.source_kind = SourceKind.DISCOVERY_FEED
            # The posting keeps the FIRST time we ever saw it. A description edit, a move to another
            # page, or a second sighting in the same run must not restart its clock — and publication
            # date is a separate field, so re-observing an old posting never renames it newly posted.
            existing_first = _aware(existing.job.first_seen_at)
            base.first_seen_at = min(
                [stamp for stamp in (existing_first, observed_at) if stamp is not None]
            )
            base.last_seen_at = existing_last if superseded else observed_at
            base.uncertainty = _without_stale_marker(base)
            runs = existing.runs_observed()
            if run_id not in runs:
                runs.append(run_id)
            runs = runs[-MAX_OBSERVED_RUN_IDS:]
            first_run = existing.first_seen_run_id
            if existing_first is None or observed_at < existing_first:
                first_run = run_id
            view.jobs[fresh.job_id] = DiscoveryLiveJob(
                job=base,
                first_seen_run_id=first_run,
                last_seen_run_id=existing.last_seen_run_id if superseded else run_id,
                observation_count=len(runs),
                observed_run_ids=runs,
                alias_job_ids=list(existing.alias_job_ids),
            )
        seen_now.add(fresh.job_id)

    horizon = now - timedelta(days=retention_days)
    for job_id, record in list(view.jobs.items()):
        if job_id in seen_now:
            continue
        last_seen = _aware(record.job.last_seen_at) or now
        if last_seen < horizon:
            view.retired_for_retention.append(job_id)
            del view.jobs[job_id]
            continue
        notes = _without_stale_marker(record.job)
        notes.append(_staleness_marker(last_seen_at=last_seen, now=now))
        record.job.uncertainty = notes

    view.retired_for_retention.sort()
    return view


# --------------------------------------------------------------------------------------------------
# Owed publication — the durable handoff between capture and the candidate representation
# --------------------------------------------------------------------------------------------------
class PendingPublicationBatch(BaseModel):
    """One round's observations of one feed, owed until they have reached that feed's live view."""

    model_config = ConfigDict(extra="forbid")
    run_id: str
    observed_at: datetime
    # False for a round that reached the feed but produced no usable page. Carried so a replay makes
    # the same statement the original round would have: nothing, about any posting.
    feed_produced_usable_page: bool
    jobs: list[CanonicalJob] = Field(default_factory=list)
    # Other rounds whose owed observations were folded into this batch by the bound below. Empty for
    # an ordinary batch. Kept so the coverage receipt can still name every round the debt covers,
    # even though the live view will record the representative `run_id` as the observing round.
    compacted_run_ids: list[str] = Field(default_factory=list)

    def all_run_ids(self) -> list[str]:
        """Every round this batch's observations came from, oldest identifier first."""
        return sorted({self.run_id, *self.compacted_run_ids})

    def merged_with(self, other: PendingPublicationBatch) -> PendingPublicationBatch:
        """Union two attempts at the same round. Additive, because a retry may see LESS.

        The interrupted round captured the posting and the retry's feed window no longer holds it.
        Replacing the owed batch with the retry's would therefore erase exactly the observation the
        debt exists to protect, so the jobs are unioned by identity and the earlier attempt's
        observation time is the one kept.
        """
        by_id = {job.job_id: job for job in self.jobs}
        for job in other.jobs:
            by_id[job.job_id] = job
        return PendingPublicationBatch(
            run_id=self.run_id,
            observed_at=min(_aware(self.observed_at), _aware(other.observed_at)),
            feed_produced_usable_page=(
                self.feed_produced_usable_page or other.feed_produced_usable_page
            ),
            jobs=[by_id[job_id] for job_id in sorted(by_id)],
            compacted_run_ids=sorted(
                ({*self.compacted_run_ids, *other.compacted_run_ids, other.run_id}
                 - {self.run_id})
            ),
        )


class PendingPublication(BaseModel):
    """Every observation discovery has captured but not yet folded into a live view.

    Stored at KNOWN keys, one per feed, plus the aggregate object the receipt and the report read.
    Known rather than discovered is a design constraint, not a preference: recovery never scans a
    prefix and never deletes, because the provider list is already known from the connector
    registry. Clearing is rewriting the object without the settled batch. The role holds
    `s3:ListBucket` conditioned on `discovery/*` because every optional read lists its own exact
    key to establish that it does not exist yet — never to search for debt. Without that grant a
    never-written key could not be told from a denied one and the first round deadlocked. The role
    still holds no `DeleteObject`.

    Its concurrency profile is the one `discovery/_discovery_state.json` and `_source_growth.json`
    already have — a single scheduled writer doing read-modify-write — so it adds no new hazard class.
    """

    model_config = ConfigDict(extra="forbid")
    # provider -> batches owed, oldest observation first.
    batches: dict[str, list[PendingPublicationBatch]] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def owed_providers(self) -> list[str]:
        return sorted(provider for provider, owed in self.batches.items() if owed)

    def for_provider(self, provider: str) -> PendingPublication:
        """Just one feed's debt, in the shape its own accepted-capture object stores."""
        owed = self.batches.get(provider) or []
        return PendingPublication(
            batches={provider: [item.model_copy(deep=True) for item in owed]} if owed else {}
        )

    def merged(self, other: PendingPublication) -> PendingPublication:
        """Union two records of the same debt, batch by batch.

        Used where the per-provider accepted-capture objects are combined, and where the aggregate
        object the previously deployed code wrote is folded in so its debt is settled rather than
        orphaned. Union rather than replacement, for the same reason `merged_with` is additive: the
        two records may each hold an observation the other does not.
        """
        updated = self.model_copy(deep=True)
        for provider, owed in other.batches.items():
            for batch in owed:
                updated, _notices = updated.owe(provider, batch.model_copy(deep=True))
        return updated

    def owe(
        self,
        provider: str,
        batch: PendingPublicationBatch,
        *,
        max_batches: int = MAX_OWED_BATCHES_PER_PROVIDER,
        retention_days: int = RETENTION_DAYS,
        now: datetime | None = None,
    ) -> tuple[PendingPublication, list[dict]]:
        """Record a debt, keep it bounded, and never make an accepted observation unreachable.

        Returns the new state and the notices the coverage receipt must render. A notice is raised
        only when the bound actually acted, and it always names the job ids it concerns — the bound
        being visible is the point, and a bound that silently discards an accepted posting is the
        defect this replaced.

        Two bounds, and only one of them removes anything:

        `compacted`  the oldest batches beyond `max_batches` are folded into ONE carry-forward batch.
                     Jobs are unioned by identity and each keeps the earliest time it was observed,
                     so every accepted posting is still owed and still publishable. What is lost is
                     per-round attribution for the folded rounds, which the notice states.

        `expired`    a posting whose observation is older than the live view's own retention horizon
                     is dropped, because publishing it would retire it in the same merge. This is the
                     view's existing retention rule reaching the debt, not a second policy, and it is
                     unreachable until publication has failed for `retention_days` running.
        """
        owed = [item.model_copy(deep=True) for item in self.batches.get(provider, [])]
        for index, existing in enumerate(owed):
            if existing.run_id == batch.run_id:
                owed[index] = existing.merged_with(batch)
                break
        else:
            owed.append(batch.model_copy(deep=True))
        owed.sort(key=lambda item: (_aware(item.observed_at), item.run_id))

        notices: list[dict] = []
        if now is not None:
            horizon = _aware(now) - timedelta(days=retention_days)
            kept: list[PendingPublicationBatch] = []
            for item in owed:
                if _aware(item.observed_at) < horizon and item.jobs:
                    notices.append({
                        "target": f"{provider} owed publication from run {item.run_id}",
                        "reason": (
                            f"{len(item.jobs)} posting(s) observed in run {item.run_id} have been "
                            f"owed for longer than the {retention_days}-day retention the live view "
                            "keeps, so publishing them now would retire them in the same merge. "
                            "They are no longer carried. raw/ for that date still holds them and the "
                            "feed returning them again would surface them as a new observation"
                        ),
                        "job_ids": [job.job_id for job in item.jobs],
                        "bound": "retention",
                    })
                    continue
                if _aware(item.observed_at) < horizon:
                    continue
                kept.append(item)
            owed = kept

        if len(owed) > max_batches:
            cut = len(owed) - max_batches + 1
            folded, owed = owed[:cut], owed[cut:]
            carried = folded[0]
            for item in folded[1:]:
                carried = carried.merged_with(item)
            owed.insert(0, carried)
            notices.append({
                "target": f"{provider} owed publication from runs {', '.join(carried.all_run_ids())}",
                "reason": (
                    f"{len(folded)} owed round(s) exceeded the {max_batches}-batch bound on this "
                    f"feed's stored debt and were compacted into one carry-forward batch attributed "
                    f"to run {carried.run_id}. Every posting is still owed and will still be "
                    "published; what is no longer separated is which of those rounds observed which "
                    "posting"
                ),
                "job_ids": [job.job_id for job in carried.jobs],
                "bound": "compaction",
                "compacted_run_ids": carried.all_run_ids(),
            })

        updated = self.model_copy(deep=True)
        if owed:
            updated.batches[provider] = owed
        else:
            updated.batches.pop(provider, None)
        return updated, notices

    def settle(self, provider: str) -> PendingPublication:
        """Clear one feed's debt, after its view has committed."""
        updated = self.model_copy(deep=True)
        updated.batches.pop(provider, None)
        return updated

    def summary(self) -> dict:
        """What is still owed, in the shape the coverage receipt renders.

        Job identities are listed, not just counted: a number alone cannot tell the operator WHICH
        posting is waiting, and a posting waiting in here is one the morning report cannot show yet.
        """
        return {
            provider: [
                {
                    "run_id": batch.run_id,
                    "observed_at": _aware(batch.observed_at).isoformat(),
                    "feed_produced_usable_page": batch.feed_produced_usable_page,
                    "job_ids": [job.job_id for job in batch.jobs],
                    **(
                        {"compacted_run_ids": batch.compacted_run_ids}
                        if batch.compacted_run_ids else {}
                    ),
                }
                for batch in owed
            ]
            for provider, owed in sorted(self.batches.items()) if owed
        }


def publish_live_view(
    prior: DiscoveryLiveView | None,
    batches: list[PendingPublicationBatch],
    *,
    source_id: str,
    now: datetime,
    retention_days: int = RETENTION_DAYS,
) -> DiscoveryLiveView:
    """Apply every owed batch for one feed, oldest observation first, onto the stored view.

    Oldest-first is required rather than convenient: it is the order in which the observations
    happened, so the newest batch is the one whose content and timing end up standing, and a replayed
    older batch cannot present itself as the feed's latest look.
    """
    view = prior
    retired: list[str] = []
    for batch in sorted(batches, key=lambda item: (_aware(item.observed_at), item.run_id)):
        view = merge_live_view(
            view,
            batch.jobs,
            source_id=source_id,
            run_id=batch.run_id,
            now=now,
            observed_at=batch.observed_at,
            feed_produced_usable_page=batch.feed_produced_usable_page,
            retention_days=retention_days,
        )
        retired.extend(view.retired_for_retention)
    if view is None:
        view = DiscoveryLiveView(source_id=source_id)
    view.retired_for_retention = sorted(set(retired))
    return view
