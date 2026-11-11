# Run Packet: JPRS-L2-P05-resumable-discovery-release-repair-v01

## Header

- project_slug: jprs
- phase_key: resumable-discovery-release-repair
- execution_profile: FULL_BUILD
- handoff_target: Claude Code
- run_id: 20260925_resumable_discovery_release_repair_v1
- run_root: project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/
- status: staged; not executed

## Objective

Finish the remaining local release repairs so Brett's morning job radar can surface recent useful
openings without losing them during interrupted or overlapping feed walks. Preserve the existing
open-market implementation and prepare a deployment handoff that selects the code actually tested.
The product serves near-term employment/income; it is not a pagination research project. This is a
bounded implementation repair, not a committee, source expansion, screening redesign or rebuild.

P01–P04 executed, nothing deployed or committed. Independent P04 review confirms 296 passing tests,
the location reproductions and production report timing. It nevertheless reproduces two ways of
silently skipping new jobs, failed attempts exceeding the request budget, and an unbound deployment
template. Those are the scope. Prior successful fixes are not reopened.

## Read first

1. JPRS `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, factory bootstrap/shared contracts and
   `project-factory/claude_handoff/RUN_OUTPUT_CONTRACT.md`.
2. `docs/plans/2026-09-24-open-market-job-discovery.md`, `docs/PLAN.md` and current factory status.
3. P04 run `project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/`:
   `ORCHESTRATOR_REVIEW.md`, `evidence/p04_independent_continuation_probe.py`, its saved results,
   `DEPLOYMENT_HANDOFF.md`, `VALIDATION.md`, report probe and rehearsal artifacts. Preserve them.
4. Actual state persistence and callers in `src/discovery/{handler,budget}.py`, paginated connectors,
   `src/cli.py`, enumeration/collection/report boundaries and
   `tests/test_location_and_freshness_boundaries.py`, especially its pagination fixtures.
5. `infra/samconfig.toml`, `infra/template.yaml`, current deployment/build docs, and the installed
   SAM template/config selection code needed to verify commands locally.

Candidate policies remain in the sibling sources named in the controlling plan. Consult them only
if relevant; do not copy sensitive candidate details or change the approved policy in this repair.

## Authority and write surface

Use the file-based factory in `/Users/drbretto/Desktop/Projects/job-posting-reality-score`, not the
Infotropy MCP spine. Create the run directory before outputs; resume if a checkpoint exists.
Allowed: targeted discovery/state/caller/tests changes, local mocked-service verification, local
builds, corrected deployment documentation, this run and existing factory continuity surfaces.
Keep the uncommitted tree intact and unrelated work untouched.

Not allowed: AWS/SSM/registry mutations, deployment, real credentials, signup or paid calls,
schedule changes, application/email submission, sibling candidate files, AGENTS/shared-contract
edits, staging/reset/checkout/branch/commit/push. No new Inbox application files. Do not execute
the implementation first and then re-run it as a review; perform one coherent repair and validation.

## Work and acceptance

### 1. Reproduce, then repair the traversal state

Run the independent P04 probe unchanged before editing runtime. Its first scenario keeps a long
historical backlog open while a recent page fails; its second introduces newer pages while an older
recent continuation is pending. Both must stop silently dropping those jobs.

Inspect the transition model before patching individual branches. Observation of a timestamp is
not proof the intervening range was traversed. A pending recent range must not be discarded by a
failure, a later head read or replacement with another range. New pages arriving ahead of a saved
continuation must remain reachable. Choose the smallest coherent state representation that meets
these conditions; do not prescribe a large queue framework or an unlimited recrawl.

Count all outbound fetch attempts against the source budget, including exceptions and partial
responses. Preserve first-page priority and bounded historical progress. If work exceeds capacity,
show what remains and keep it resumable. Do not promise every posting within 24 hours regardless of
provider/budget; the requirement is prompt prioritized discovery without silent loss.

Verify across serialized state round trips and repeated invocations, with a backlog long enough
that accidental exhaustion cannot restart the feed and hide a bug. Cover failed/partial middle
pages, saved continuation plus a new multi-page burst, unchanged head, multiple resumptions,
repeated cursors, budget exhaustion and the actual timestamp cursor contract. Use bounded cases
with known reachable IDs; prove eventual collection within the test's finite capacity and honest
pending coverage while incomplete. Preserve dedup/first-seen history and old-state readability.

Make at least the two review scenarios reach persisted candidate reports through mocked external
services, not only a requested-URL log. Keep production internal wiring real. Add regression tests
that fail on P04, including the attempted-request budget failure. No network is needed for these.

### 2. Bind deployment to its verified build

P04 builds into `/tmp/jprs-build` and deploys without an explicit template. The installed CLI selects
a nonexistent root template here; a stale default build could also be selected. Correct the forward
handoff so template and config paths unambiguously select the verified build, independent of stale
default artifacts. Confirm through local argument/config resolution without invoking AWS/deploy.
Keep the existing quiesce -> data downgrade -> source rollback -> resume ordering and non-destructive
worktree method. Check forward and rollback command selections, not just their prose descriptions.

### 3. Validate and stop at the release decision

Run focused regressions, the full suite, policy projection check, SAM validation/build and the bounded
persisted-report scenarios. Preserve credential/polarity/location/timing/downgrade regressions.
Record before/after results and distinguish synthetic/captured data from live transport. Reconcile
existing live plan/status/registry/phase/timeline/bootstrap surfaces; leave prior returns/evidence
intact, qualifying earlier acceptance through this run rather than rewriting history.

## Outputs

Normal run manifest/checkpoint/gate decision; concise `OPERATOR_RETURN.md`; `VALIDATION.md` with
executable before/after evidence; corrected `DEPLOYMENT_HANDOFF.md`; persisted regression reports.
The packet is not accepted merely because tests pass: the two formerly missed jobs must be accounted
for under persisted multi-run state, and deployment must select the tested artifact.

## Stop and next

Stop with these bounded local repairs and a release recommendation. No deployment or commit.
If a concrete blocker remains, identify its reproduction and consequence; do not default to a broad
new review because this is P05. Once this gate passes, the next action is operator-approved controlled
deployment with live HTTP checks, not further speculative polishing. Authenticated Adzuna, general-
industry coverage and source admission remain distinct activation checks, not prerequisites for
truthfully deploying the working keyless discovery paths.
