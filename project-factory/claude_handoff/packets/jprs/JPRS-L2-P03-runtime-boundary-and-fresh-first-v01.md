# Run Packet: JPRS-L2-P03-runtime-boundary-and-fresh-first-v01

## Header

- project_slug: jprs
- phase_key: runtime-boundary-and-fresh-first
- execution_profile: FULL_BUILD
- handoff_target: Claude Code
- run_id: 20260924_runtime_boundary_and_fresh_first_v1
- run_root: project-factory/outputs/open-market-discovery/runs/20260924_runtime_boundary_and_fresh_first_v1/
- status: staged; not executed

## Outcome and context

Deliver a locally tested discovery release that reaches useful jobs at previously unknown employers
and prioritizes genuine new openings for Brett's morning application round. Preserve the broad,
cross-industry implementation. This is a focused continuation, not a committee, rebuild, or new
company-scoring service. The goal is near-term income and employment, not raw posting counts.

P02 executed and 209 tests pass independently, but review reproduced three remaining blockers:
the actual HTTP call still loses Adzuna credentials; screening suppresses later mandatory duties
after an earlier negation and rejects optional video; and rollback's old reader rejects new records.
Read and reproduce the review, not just this summary. Its fresh-first item is a subsequent operator
clarification, not a claim that P02 was instructed to implement a specific 24-hour priority.

## Read first

1. `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `project-factory/ORCHESTRATOR_BOOTSTRAP.md`, factory
   shared contracts and `project-factory/claude_handoff/RUN_OUTPUT_CONTRACT.md`.
2. `docs/plans/2026-09-24-open-market-job-discovery.md` and current factory state. The plan controls
   the whole objective; this packet supplies bounded execution and acceptance.
3. P02 run `project-factory/outputs/open-market-discovery/runs/20260924_open_market_release_repair_v1/`:
   `ORCHESTRATOR_REVIEW.md`, `evidence/orchestrator_review_probes.py`, `VALIDATION.md`,
   `DEPLOYMENT_HANDOFF.md`, `run_manifest.json`, saved rehearsal reports and relevant evidence.
4. P01 `DESIGN.md` and review; P02 packet for the acceptance rows whose closure is disputed.
5. The five central candidate/workflow files named in the controlling plan, read-only. Do not
   invent exclusions or put preferences in AGENTS.md. Company/team research remains downstream.
6. `src/discovery/`, `src/common/connectors.py`, `src/common/models.py`, `src/candidate/screening.py`,
   relevant differ/report paths, config, tests, `infra/DEPLOY.md` and the baseline code at `e549a73`.

## Authority and write surface

Work only in `/Users/drbretto/Desktop/Projects/job-posting-reality-score`, using this repository's
file-based factory, not the Infotropy MCP spine. Preserve the dirty P01/P02 implementation.
Allowed: scoped local code/config/tests/docs, local builds, mocked services, bounded public reads.
Not allowed: AWS/SSM/registry mutations, deployment, signup, paid service, real secret discovery,
email/applications, changing collection/report schedules, commits, branches, staging, resets or pushes.
Do not change AGENTS/shared contracts or sibling candidate files. No Inbox application materials.

Create run_root before outputs; resume a checkpoint if present. Preserve historical P01/P02 claims
and artifacts, qualifying them through review links rather than silently rewriting their evidence.

## Work and acceptance

### 1. Test and fix the real runtime boundary

Start with the review probe. Exercise the default Lambda handler with mocked SSM/S3 and intercept
the actual HTTP request. Keep `_live_fetcher` and credential propagation real: replacing the faulty
function with a passing substitute cannot validate it. With credentials only in mocked SSM, every
Adzuna request must carry them. Missing keys remain visibly gated; provider disablement still works.
Retain location scopes without narrowing all search to NH. Inspect stored and error artifacts for
fake-secret leakage. Preserve host validation and redaction. No live authenticated success claim
without a real authorized search; an absent real key does not block this local regression.

### 2. Aggregate screening evidence correctly

Reproduce all four review examples. Examine all relevant requirements, not just the first match.
A negated or optional step cannot cancel a separate mandatory step. Building sales tooling cannot
cancel an explicit quota or cold-call duty elsewhere, including within the same sentence. Optional
candidate video with a non-video alternative is not a mandatory-video exclusion. Apply this logic
consistently to other policy families where it is used, including AI interviews and drug screening.
Use paired cases, reordered clauses, HTML/native variants and representative captured postings.
Uncertain meaning goes to review, never a fabricated exemption or keyword-only rejection. Preserve
all actual hard exclusions and accepted roles; do not solve tests by disabling screening wholesale.
Show changed dispositions and downstream effects, not just a growing unit-test count.

### 3. Make rollback safe for persisted state as well as source files

The old `CanonicalJob` rejects the new model's additive fields. Trace the shared monitored-job,
diff-state and event paths that would exist after the new release runs. Demonstrate a local/mocked
forward-run then rollback/read/restart scenario against the exact baseline, including jobs that
have not been refreshed again. Design the smallest reversible rollback strategy that preserves
source and data and does not manufacture removals. Do not merely assert additive compatibility,
increase tolerance without reasoning, or tell the operator to delete/rebuild production state.
Any eventual state-writing recovery steps need explicit deployment-time approval and a preserved
backup; this packet rehearses them only. Validate command syntax separately from data compatibility.

### 4. Fresh-first discovery and morning reporting

The operator wants to find strong fits promptly, ideally apply within the first 24 hours. This is
a priority, not an age cutoff or a guarantee over delayed providers. In the existing architecture:

- Give new arrivals prompt attention even while a multi-day browse/query backlog is nonempty.
  Preserve bounded, fair catch-up; do not choose between restarting at page one forever and never
  checking page one until the entire history is exhausted. Decide the scheduling mechanism from
  actual source order/cursor contracts, explaining the smallest sufficient change.
- Preserve original posting date and its source. A feed publication date is not automatically the
  employer's original date. Updated, first-discovered, last-verified and application-history NEW
  must not become synonyms for newly posted. Preserve first-seen across repeats and dedup aliases.
- The report should prioritize fresh credible fits, retain missed-day catch-up and older strong
  discoveries, and label unknown ages and source delays. No hidden candidate quota and no exclusion
  simply for exceeding 24 hours. A fresh bad fit must not outrank a strong fit merely for being fresh.
- Test a job inserted at the head between runs with backlog still present, a missed day/weekend,
  an older job imported today, undated jobs, updates/reposts, duplicate sources, failed fetches and
  retry/resumption. Prove the actual persisted report behavior, not only an in-memory query list.
- Respect current schedules and documented source limits. If those cannot meet the target, state
  the achievable latency and a bounded optional cadence change for later approval; do not change it.

### 5. Verify, reconcile and stop

Run focused regressions, full suite, policy check, SAM validate/build, and a bounded rehearsal.
Use independent reviewer contexts if available for screening and actual runtime/data boundaries;
do not simulate independence. Fixed code must receive a fresh boundary check, not only the tests
authored with it. If unavailable, disclose it and leave the orchestrator review gate explicit.

Reconcile report cohorts and counts; correct cost arithmetic using stated runtime/request bounds.
Synchronize existing live plan/bootstrap/status/registries with the actual completed run and next
gate; do not leave P02 both staged and completed or describe 821 combined jobs as 221 new employers.

## Outputs and stop condition

Run manifest, checkpoint, gate decision, `OPERATOR_RETURN.md`, `VALIDATION.md`, corrected
`DEPLOYMENT_HANDOFF.md`, reproducible boundary evidence and the readable fresh-first report.
State separately: local acceptance, real-provider acceptance, deployment, and operator approvals.

Stop at locally verified repair and fresh-first readiness. Do not deploy, submit, buy, provision,
commit or invent missing evidence. If any acceptance remains unpassed, name it and checkpoint the
useful completed work. The orchestrator reviews the resulting code/artifacts before release approval.
