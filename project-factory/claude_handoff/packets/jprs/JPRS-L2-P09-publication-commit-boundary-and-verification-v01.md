# Run Packet: JPRS-L2-P09-publication-commit-boundary-and-verification-v01

## Header

- project_slug: jprs
- phase_key: publication-commit-boundary-and-verification
- execution_profile: BOUNDED_IMPLEMENTATION_AND_ADVERSARIAL_LOCAL_VERIFICATION
- handoff_target: Claude Code
- run_id: 20260925_publication_commit_boundary_and_verification_v1
- run_root: project-factory/outputs/open-market-discovery/runs/20260925_publication_commit_boundary_and_verification_v1/
- status: staged; not executed; no deployment authorization

## Objective

Deliver the existing open-market radar integration safely: useful jobs from employers Brett has
never named must reach the ordinary morning candidate report through the same screening, ranking,
deduplication and history as monitored jobs. Preserve fresh-first discovery, older strong fits,
request budgets and all candidate preferences. No raw-feed dump, company-admission prerequisite or
daily quota. This is a near-term employment tool, not a new infrastructure project.

P07 connected the pipeline. P08 fixed the original live-view-write interruption, preserved replay
timing/idempotence, and recovered a genuine P06 rollback archive. Keep that work. Its independent
review nevertheless reproduces loss at the FIRST pending-ledger write and false-green release
checks. Finish those same boundaries in this packet, not another broad review or redesign.

## Authority, source and read-first

The operator authorizes obvious follow-up packets. This authorizes local repair, NOT deployment.
P06 remains the running build. This repository uses a file-based factory, not the Infotropy MCP.

1. Work in `/Users/drbretto/Desktop/Projects/job-posting-reality-score`. Read AGENTS/CLAUDE, factory
   bootstrap/shared contracts/current trackers, and `RUN_OUTPUT_CONTRACT.md`.
2. Read `docs/plans/2026-09-24-open-market-job-discovery.md`, including the candidate-policy source
   pointers. Update this existing plan before implementation; do not invent another product vision.
3. P08 run `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/`:
   `ORCHESTRATOR_REVIEW.md`, its two `p08_independent_*_probe.py` scripts and corresponding JSON,
   `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`, baseline archive/hash verifier/package checker and
   original unmodified P07 probe. Read the original P08 packet's invariants as context, not as a
   instruction to preserve its faulty write order or five-batch eviction.
4. Actual `src/discovery/{handler,live}.py`, layout, report producer/consumer, inspector script,
   related integration/durability tests and real template/config. Trace actual execution and storage
   boundaries; do not seed intermediates the producer is responsible for creating.
5. P06 run `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/`:
   `evidence/p06_build_identity.txt`, live verification summary and deployment boundary. P08's
   archive contains the 36 hash-verified P06 source files. Preserve it and the uncommitted overhaul.

## Work A — one complete durable acceptance/recovery boundary

Run the reviewer's pending-write probe unchanged BEFORE repairing; capture its output. It drives
real stages with one external PutObject failure, then an empty provider response on retry and the
following round. The control retains the synthetic job; the interrupted arm loses it from reports
although it was already durably normalized. Original P07 live-write probe currently passes.

Define the durable acceptance point and make ordinary recovery find every accepted but unpublished
observation without asking the provider to return it again. Choose the smallest correct design.
Neither renaming the earlier durable records nor weakening the acceptance statement is a repair.
A failure before ANY durable acceptance can remain unaccepted/incomplete; no promise to recover
information that never reached durable storage is required. Once captured durably, however, a later
write failure cannot make the job invisible to recovery or let a changed feed overwrite the only
automatically reachable record.

Do not fix only the probe's particular key. Enumerate the finite persistence sequence from durable
acceptance to publication and settlement, and exercise each distinct failure boundary locally. Include
a successful storage write followed by a timeout before the caller receives success. Use actual
producer/consumer code; mock external storage/HTTP, not the internal function whose behavior is under
test. Report which boundaries were exercised and the recovery source at each.

Required invariants:
- Same-run retry and following-run recovery, with the job absent from both later feed responses.
- Original observation time/run attribution, no duplicate report row or inflated same-run history.
- An older replay cannot replace newer data; partial multi-provider work preserves successful peers.
- Accepted publication debt cannot be evicted merely because it exceeds FIVE batches. P08's
  dropping test encodes a failure, not operator policy. Keep recovery bounded through compaction,
  drain/admission ordering or explicit backpressure as appropriate; neither infinite storage nor
  retaining redundant history forever is required. Outstanding useful observations must remain
  recoverable, and backlog/capture limits must be visible. Test beyond the previous cap and the
  first healthy round after that backlog, so enqueuing an empty round cannot discard the oldest job.
- Preserve request budgets, traversal debt, feed-vs-ATS lifecycle, ordinary candidate policy and
  report behavior. Do not redesign unrelated modules or expand provider access.

If concurrency is not supported, state the actual serial-execution assumption and avoid claiming
exactly-once/concurrent-writer safety from serial tests. This is not a new distributed-locking project.

## Work B — verifiers that reject the conditions they claim to reject

Run the independent release-gate probe unchanged before repairs. It deliberately mutates LOCAL
fixtures to test the checkers; it is not evidence of an actual production IAM edit or vacancy.

### Build/rollback safety

Make the pre-deploy checker compare actual baseline and candidate infrastructure/config/resource
definitions. Printed hashes and warnings are not a failed gate. An IAM/property change, added or
removed function/resource, missing baseline, and an unperformed comparison must not return
CODE_ONLY. Genuine code-only changes and explicitly normalized build-path/CodeUri differences must
pass. Keep the separate later AWS change-set inspection; do not describe local package comparison
as an executed/inspected AWS change set. Do not perform any AWS calls in this packet.

Keep the verified P06 archive; do not reconstruct P06 from HEAD or the already-edited source. Forward
checking and rollback must work without `/private/tmp/claude-501/jprs-build-p06-9H8jKS` surviving.
Validate archive content before restore, ignore only identified metadata, and fail closed on mismatched
or unexpected executable source. Rehearse restore-and-return and a corrupt-archive refusal in scratch
directories. Never replace the actual working-tree `src/` for this rehearsal. Preserve pending/live
objects on a real rollback; distinguish paused recovery on P06 from deletion or irrecoverable loss.

### Per-identity report reconciliation

An employer-name match is NOT evidence that every posting at that employer was consumed. Do not
infer below-fit status from `previously_unseen_employers`. Reconcile each expected discovery identity
to a real retained/excluded/below-fit/dedup-alias/pending disposition at the actual consumer. Add
minimal per-ID report evidence if needed; do not fabricate it inside the inspector or harness.

Test a mixed case where one job is consumed and another from the SAME employer is missing, as well
as different-employer missing input, real below-fit input and legitimate dedup. A positive open-market
witness can remain separately true while integration is partial; do not call all inputs reconciled
or give an overall clean exit when an unexplained identity is missing. Preserve P08's five existing
controls, with accurate statuses if labels change. Preserve employer-identity checking against the
registry and unknown/review-needed handling.

Bind inspection to a coherent report input generation/run. A later live view is not necessarily the
population an older report consumed. A missing expected input is not equivalent to an empty feed.
The check must distinguish absent evidence from an honest zero and remain read-only.

## Release handoff and outputs

Correct the deployment handoff in the new run, preserving prior evidence. Use an explicitly selected
shell, initialized argument arrays, fail-fast verification and the verified build's explicit template
plus absolute SAM config. Separate forward and rollback commands, with rollback checks appropriate
to P06 (which has no live.py). Do not ship another list of commands that prints a failed check and
continues into deployment. Exercise the failure paths locally with mocked tools where needed.

No live success is claimed from fixtures. The later positive product condition is a REAL job from a
registry-absent employer in a report actually delivered. Local tests, code deployment, real ingestion,
delivery and unattended next-round behavior are distinct. A genuine zero must be reported, not
refetched away or replaced with the synthetic insurance/benefits companies.

Create the run_root before outputs; resume an existing checkpoint if present. Produce standard
manifest/checkpoint/gate, `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`, `OPERATOR_RETURN.md`, the bounded
failure matrix and reusable before/after evidence. Keep P08 originals unchanged; put repaired helper
versions in maintained scripts or this new run, with an unambiguous current entrypoint. Update the
existing plan and factory continuity/registry statuses to distinguish executed local work from P06.

## Write scope and exclusions

Allowed: implicated discovery/report/common modules, related tests, local verification scripts,
release documentation, this run_root, existing central plan and factory continuity files.

Not allowed: deployment, AWS calls or invocations, cloud mutation, SSM/registry/credentials, email,
applications, employer contact, new feeds, candidate-policy edits, source admission, changed cadence,
paid/model API calls, packaging redesign, IAM/resource changes, general audit or new committee.
If permissions or architecture truly must change, checkpoint the demonstrated need; do not expand
them here. No git branch/stage/commit/push/reset/stash/checkout. Preserve the uncommitted overhaul.
Do not change AGENTS or shared contracts to solve this task.

## Acceptance and stop

1. The unchanged pending-boundary probe is repaired AND the original live-write probe still passes.
   Across the finite fault matrix, durably accepted jobs are either published or replayably owed,
   including beyond the old batch cap; no test-authored intermediate wiring.
2. Negative release controls now fail for semantic infrastructure differences, unavailable baseline
   and corrupt restore input; legitimate code-only builds and scratch restore/return pass.
3. The mixed same-employer case is not invented as below-fit; all dispositions are backed by real
   per-ID consumer evidence. Honest empty, pending, partial and complete states remain distinct.
4. Targeted tests, full existing suite, candidate-policy check, SAM validation/build and packaged
   module/template selection pass. Show new regressions fail against preserved pre-repair code in
   scratch without changing the actual working checkout. No arbitrary test-count target.
5. Release commands are executable, fail closed and use the preserved baseline. No scope violation.

Stop after these local repairs, checks and handoff. A fresh verifier should try the named negative
controls without the implementer's expected-verdict commentary; this is a bounded verification pass,
not permission for an open-ended audit. If a required condition remains unmet, report it explicitly
with `revise_implementation`. `unlock` means ready for orchestrator review only. The next action after
verified repair is fresh deployment authorization, not another committee by default.
