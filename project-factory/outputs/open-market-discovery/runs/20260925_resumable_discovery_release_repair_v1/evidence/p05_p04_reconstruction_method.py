"""Reconstruct the pre-P05 (P04) discovery source inside the scratch copy.

Purpose: run the new P05 regression tests against the code they were written to catch, so
"these tests fail on P04" is a measured statement rather than an assertion.

Each replacement is asserted, so a silent partial revert cannot masquerade as a result.
"""
from __future__ import annotations

import sys

BUDGET = "src/discovery/budget.py"
HANDLER = "src/discovery/handler.py"


def revert(path: str, current: str, original: str, label: str) -> None:
    text = open(path).read()
    if current not in text:
        print(f"FAIL — cannot revert (current text absent): {label}")
        sys.exit(1)
    open(path, "w").write(text.replace(current, original, 1))
    print(f"reverted: {label}")


# ---------------------------------------------------------------- budget.py: state fields
revert(
    BUDGET,
    '''    # DERIVED compatibility mirror of `head_pending`: the newest range still owed, or None.
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
    head_frontier_at: dict[str, str] = Field(default_factory=dict)''',
    '''    # An UNFINISHED head continuation.
    head_cursors: dict[str, str | None] = Field(default_factory=dict)
    # Newest provider publication timestamp already observed per source (ISO-8601).
    head_frontier_at: dict[str, str] = Field(default_factory=dict)''',
    "budget: state fields",
)

# ------------------------------------------------------------- budget.py: accessor methods
revert(
    BUDGET,
    '''    def pending_head(self, provider: str) -> list[str]:
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

    def coverage_for(self, family_key: str) -> FamilyCoverage:''',
    '''    def coverage_for(self, family_key: str) -> FamilyCoverage:''',
    "budget: accessor methods",
)

# -------------------------------------------------------------------- handler.py: the walk
revert(
    HANDLER,
    open("/private/tmp/claude-501/p04check/p05_walk.txt").read(),
    open("/private/tmp/claude-501/p04check/p04_walk.txt").read(),
    "handler: _walk",
)

# ------------------------------------------------------------- handler.py: saved_pending read
revert(
    HANDLER,
    '''            saved_cursor = state.source_cursors.get(provider)
            saved_pending = state.pending_head(provider)''',
    '''            saved_cursor = state.source_cursors.get(provider)
            saved_head = state.head_cursors.get(provider)''',
    "handler: saved_pending read",
)

# ------------------------------------------------------------------ handler.py: branch one
revert(
    HANDLER,
    '''            budget_obj = budget
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
            elif pages_budget >= 2:''',
    '''            budget_obj = budget
            if saved_cursor is None:
                # No backfill outstanding: the head walk IS the catch-up.
                end_cursor, exhausted, _reason = _walk(None, pages_budget, phase="head")
                state.source_cursors[provider] = end_cursor
                state.head_cursors[provider] = None
                state.last_feed_phase[provider] = "head"
            elif pages_budget >= 2:''',
    "handler: branch one",
)

# ------------------------------------------------------------------ handler.py: branch two
revert(
    HANDLER,
    '''                head_budget = pages_budget - 1
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
            else:''',
    '''                head_budget = pages_budget - 1
                before_head = pages_done
                head_end, _head_exhausted, head_reason = _walk(
                    None, head_budget, phase="head", stop_at=saved_cursor,
                    frontier=head_frontier, recent_only=True,
                    resume_after_first=saved_head if saved_head != saved_cursor else None,
                )
                head_pages = pages_done - before_head
                if head_reason == "budget" and head_end:
                    # Still recent pages outstanding: visible and resumable, never discarded.
                    state.head_cursors[provider] = head_end
                    outcome.inaccessible.append({
                        "target": f"{provider} recent arrivals",
                        "reason": (
                            f"new postings continued past the {head_pages} page(s) this run could "
                            "spend on the feed head; position saved and resumed next run, and one "
                            "page was still reserved for the historical backfill"
                        ),
                    })
                else:
                    state.head_cursors[provider] = None

                catch_up_budget = max(1, pages_budget - head_pages)
                end_cursor, exhausted, _reason = _walk(
                    saved_cursor, catch_up_budget, phase="catch-up"
                )
                state.source_cursors[provider] = end_cursor
                state.last_feed_phase[provider] = "both"
            else:''',
    "handler: branch two",
)

# ---------------------------------------------------------------- handler.py: branch three
revert(
    HANDLER,
    '''                head_owed = _walk(head_work, 1, phase="head", stop_at=saved_cursor,
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
                outcome.inaccessible.append({''',
    '''                _walk(None, 1, phase="head", stop_at=saved_cursor, frontier=head_frontier,
                      recent_only=True)
                state.last_feed_phase[provider] = "head"
                exhausted = False
                outcome.inaccessible.append({''',
    "handler: branch three",
)

# ------------------------------------------------- handler.py: frontier + backlog reporting
revert(
    HANDLER,
    '''            if dropped_pending:
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
            if head_newest:''',
    '''            # Remember the newest posting the head actually saw.
            if head_newest:''',
    "handler: frontier comment + dropped reporting",
)

revert(
    HANDLER,
    '''            remaining = state.source_cursors.get(provider)
            still_owed = state.pending_head(provider)
            if any_success:
                outcome.succeeded.append(provider)
            if remaining or still_owed or stopped_early:''',
    '''            remaining = state.source_cursors.get(provider)
            if any_success:
                outcome.succeeded.append(provider)
            if remaining or stopped_early:''',
    "handler: backlog condition",
)

revert(
    HANDLER,
    '''                state.backlog.reason = (
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
                )''',
    '''                state.backlog.reason = (
                    state.backlog.reason
                    or (
                        f"{provider} feed has more pages; position saved and resumable"
                        if remaining else
                        f"{provider} pagination stopped before the end of the feed; coverage partial"
                    )
                )''',
    "handler: backlog reason",
)

print("\\nP04 reconstruction complete.")
