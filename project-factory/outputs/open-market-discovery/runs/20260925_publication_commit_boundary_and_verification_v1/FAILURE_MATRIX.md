# Bounded failure matrix — durable acceptance to publication and settlement (P09)

Scope: `evidence/p09_publication_boundary_matrix.json`, produced by
`scripts/p09_publication_boundary_matrix.py`, which derives its table and its expectations from
`tests/test_publication_commit_boundary.py`. Every row is one refused external `PutObject` inside
the real discovery stage, with the feed returning the posting once and **nothing** on any later
attempt — so anything that comes back came from durable storage, not from asking the provider again.

Provenance: `evidence`. Fixture: a synthetic insurance-company role, never a vacancy.

## The sequence

`persist` makes a finite, fully known list of external storage writes. Per provider, in provider
order:

1. **ACCEPT** — the feed's own owed-publication record. The FIRST durable write of its round.
2. `raw/`, `normalized/`, `status/` for each of that feed's snapshots.
3. that feed's SUCCESS sentinels.

Then once for the run: the aggregate owed receipt; coverage; traversal state; growth; proposed
registry; the **drain** (view commit → settle that feed's record → refresh the aggregate); and the
residual coverage receipt.

## The matrix

`durably accepted` is read from storage at the moment of the failure — still owed, or already
folded into the view and settled. `recovered` means the posting reached the morning report on the
same-run retry AND on the following round, from both of which the feed returned nothing.

| boundary refused | durably accepted | recovery source | recovered |
| --- | --- | --- | --- |
| `acceptance_record` | no | not accepted — round incomplete, the feed must return the posting again | no |
| `acceptance_record_stored_then_timeout` | yes | the feed's owed-publication record | yes |
| `raw_snapshot` | yes | the feed's owed-publication record | yes |
| `normalized` | yes | the feed's owed-publication record | yes |
| `source_status` | yes | the feed's owed-publication record | yes |
| `success_sentinel` | yes | the feed's owed-publication record | yes |
| `aggregate_receipt` | yes | the feed's owed-publication record | yes |
| `coverage_receipt` | yes | the feed's owed-publication record | yes |
| `traversal_state` | yes | the feed's owed-publication record | yes |
| `source_growth` | yes | the feed's owed-publication record | yes |
| `proposed_registry` | yes | the feed's owed-publication record | yes |
| `live_view_commit` | yes | the feed's owed-publication record | yes |
| `live_view_stored_then_timeout` | yes | already published; the owed batch replayed idempotently | yes |
| `settle_owed_record` | yes | already published; the owed batch replayed idempotently | yes |
| `aggregate_receipt_refresh` | yes | already published; the owed batch replayed idempotently | yes |
| `residual_coverage_receipt` | yes | already published; the owed batch replayed idempotently | yes |

`aggregate_receipt` is the boundary the P08 review's own probe refuses. It is one row here, not the
repair: fixing that key alone would have repaired that probe and nothing else.

`acceptance_record_stored_then_timeout` and `live_view_stored_then_timeout` are the ambiguous-
response case — the write really happened and the caller never learned it. Nothing else can produce
that state, and it is the one failure where retrying blindly would be wrong if replay were not
idempotent.

## The one row that does not recover, and why that is the honest answer

`acceptance_record` is the acceptance point itself. Refusing it leaves the round incomplete and the
observations unaccepted, and the feed must return the posting again.

That is not a weakened claim, because acceptance is the **first** durable write of the feed's round:
`test_a_refused_acceptance_leaves_no_other_durable_trace_to_be_lost` asserts that after this
refusal, `raw/`, `normalized/` and `discovery/` hold nothing at all for that feed. There is no state
in which a posting is durably captured and unrecoverable — which is exactly the state P08 had, and
the reason its review reproduced a loss.

The cost of that ordering is stated rather than hidden: a failure at step 2 can leave a **published
posting whose raw snapshot is missing for that date**. That is a gap in the audit trail, and it is
preferred to the alternative the earlier order produced — an intact audit trail for a posting the
morning report could never show.

## Invariants asserted alongside the matrix

In `tests/test_publication_commit_boundary.py` and `tests/test_durable_discovery_publication.py`:

- the same-run retry and the following round both recover, with the job absent from both later feed
  responses
- original observation time and run attribution survive: `observed_run_ids == [the round that
  actually observed it]` and `observation_count == 1` on every recovering row, so the recovery
  rounds do not appear as rounds that saw the posting
- no duplicate report row, and nothing stays owed after a healthy round
- an older replay cannot roll back a newer observation
- a refused acceptance for one feed costs that feed's batch only; a peer feed's accepted work
  survives in its own record
- accepted debt beyond the five-batch bound is **compacted**, not discarded, and the first healthy
  round after such a backlog publishes every owed posting rather than evicting the oldest by
  enqueuing its own empty batch
- request budgets, traversal debt and the recent-range ledger are unchanged across an interruption

## What this matrix does NOT establish

- anything about real S3. `moto` grants every permission and models no eventual consistency. These
  are the code's behavior under a refused write, not S3's semantics or the IAM policy. The declared
  grants are checked against the real template in `tests/test_discovery_to_report_integration.py`.
- anything about a **concurrent** second writer. Every row is serial: one scheduled writer doing
  read-modify-write on its own objects, which is the profile `discovery/_discovery_state.json`
  already has. No exactly-once claim under concurrency is made or supported here.
- anything about the live market, or about any posting being real.
