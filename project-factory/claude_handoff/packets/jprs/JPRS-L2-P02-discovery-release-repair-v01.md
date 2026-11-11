# Run Packet: JPRS-L2-P02-discovery-release-repair-v01

## Header

- project_slug: jprs
- phase_key: open-market-release-repair
- execution_profile: FULL_BUILD
- handoff_target: Claude Code
- run_id: 20260924_open_market_release_repair_v1
- run_root: project-factory/outputs/open-market-discovery/runs/20260924_open_market_release_repair_v1/
- status: staged; not executed
- source: JPRS-L2-P01 and its ORCHESTRATOR_REVIEW.md

## Objective

Preserve the employer-independent discovery implementation and repair the concrete release
defects found in its orchestrator review. The outcome is a dependable broad list for Brett's
daily employment workflow, with no silent pagination losses or keyword-based false exclusions.
This is implementation and verification, not a new planning committee or wholesale rebuild.

The original cross-industry objective remains controlling. JPRS finds opportunities. Career
Factory's executor researches companies and teams, makes reasoned priority recommendations and
tailors applications; the orchestrator reviews those judgments and Brett approves submissions.
Do not translate culture preferences into new automated vetoes or move that research service
into JPRS. No daily quota or perfect-employer requirement is introduced.

## Read first

1. `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `project-factory/ORCHESTRATOR_BOOTSTRAP.md`, relevant
   shared contracts and `project-factory/claude_handoff/RUN_OUTPUT_CONTRACT.md`.
2. `docs/plans/2026-09-24-open-market-job-discovery.md` and the P01 packet.
3. In `project-factory/outputs/open-market-discovery/runs/20260924_open_market_discovery_v1/`:
   `ORCHESTRATOR_REVIEW.md`, `OPERATOR_RETURN.md`, `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`,
   and the monitored-only, live-replay and combined reports under `rehearsal/`.
4. The five central candidate/workflow sources named by the plan, read-only. Read the current
   Company Research section; these changed during P01. Preserve actual exclusions, not guesses.
5. The affected code, existing tests, `config/discovery_sources.yaml`, `infra/template.yaml`,
   `infra/samconfig.toml` and `infra/DEPLOY.md`. Verify file and API behavior before editing.

## Scope and authority

Work in `/Users/drbretto/Desktop/Projects/job-posting-reality-score`. This is the JPRS file-based
factory, not an Infotropy governance-spine run. No sibling repository files are writable.
Allowed: scoped local code/config/tests/docs, local builds, read-only public verification and
read-only inspection of known AWS resources if necessary. No secret hunting in unrelated files.
Not allowed: deployment, cloud/SSM/registry mutation, paid services or signup, messages, email,
applications, new automations, commits, branches, pushes, or staging/resetting others' changes.
An existing dirty tree is the P01 implementation to preserve, not permission to overwrite it.

## Work

1. Reproduce R1–R4 independently and add failing regression tests before repair. Inspect the
   actual stored reports as well as the synthetic examples. Create run_root before writing run
   outputs; resume its checkpoint if present rather than restarting completed work.
2. Repair Adzuna's real default/runtime path. Credential absence is visibly gated; credentials
   resolved from SSM reach outbound requests without requiring a separate process environment.
   Respect intentional provider disablement. Test at the handler boundary with mocked AWS and
   captured transport, not only direct connector calls. Wire location-aware and US-remote search
   coverage without narrowing all work to one state. Never expose credentials in logs/artifacts.
3. Implement honest pagination/resumption for Himalayas against current official API behavior.
   Use browse cursors or filtered search as appropriate; do not treat one page as the full feed.
   Add a beyond-first-page relevant-job test, continuation across runs, budget, timeout, 429 and
   failed-query retry tests. Check other finite feeds and Adzuna backlog for the same loss mode.
   Keep bounded load, visible deferred work and fair progress; do not solve recall by endless
   crawling or by inventing a new fixed candidate cutoff.
4. Repair screening at the root: requirement polarity and whose work a sentence describes.
   Cover negations, optional versus required language, sales-tool/product descriptions versus
   actual quota/prospecting ownership, and encoded HTML as received. Retain real exclusions.
   If deterministic evidence cannot settle a material distinction, route to review rather than
   discard or automatically endorse. Audit the captured engineering-role exclusions and show
   which changed, why, and which remain valid. Do not implement a company-vibe scoring engine.
5. Repair deployment readiness. Validate rollback syntax without executing it, preserve full
   schedule fields and the uncommitted work, and distinguish partial disable from full rollback.
   Bound cost claims using current primary pricing and explicit assumptions; do not assert free
   tier eligibility without evidence. Recheck the production transport gap and source-growth
   boundary: resolver success, proposed registry entries and actual monitoring are distinct.
   Stage any activation/registry writes for approval. Do not claim that a key alone or one switch
   closes a broader gate. Unrelated packaging cleanup is not a prerequisite unless a concrete
   security or runtime defect makes it necessary.
6. Refresh the local policy projection only after comparing the source changes semantically.
   Re-run all existing tests, SAM validation/build and a bounded public-read-only rehearsal.
   Separate fixture tests from live evidence and disclose credential/transport gaps accurately.
   Reconcile result counts and the complete readable report. Scores are candidates for the next
   human/executor research step, not established culture fit or permission to submit.

Official starting references, recheck as needed:
- https://himalayas.app/api
- https://developer.adzuna.com/overview
- https://docs.aws.amazon.com/cli/latest/reference/scheduler/update-schedule.html

## Review shape

This packet authorizes targeted independent reviewer contexts, if available, for repaired
candidate screening and runtime/pagination/rollback behavior. Give each the intended behavior
and actual artifacts, not a requested PASS. Disclose unavailable independent review; do not
simulate reviewers or run another broad committee. Incorporate findings without changing the
candidate preferences or substituting a new product objective.

## Write surface and outputs

Scoped implementation files under `src/`, `tests/`, `config/`, `infra/` and necessary task docs.
No AGENTS/shared-contract changes. Keep existing historical P01 evidence intact; qualify it with
review references instead of laundering its original verdict. Update existing live entrypoints,
plan and trackers to the true latest status.

Run outputs: `run_manifest.json`, `checkpoint.md`, `gate_decision.md`, `VALIDATION.md`,
`DEPLOYMENT_HANDOFF.md`, `OPERATOR_RETURN.md`, and compact reproducible probe/results artifacts
where useful. No Inbox dossiers, resumes or application submissions belong to this repair.

## Acceptance

- R1: default handler + mocked SSM credentials exercises authenticated Adzuna requests; missing
  credentials remain visible; intentional exclusions respected; location coverage verified;
  request/error/report artifacts do not leak credentials.
- R2: an unseeded relevant employer beyond the first page reaches the report; deferred/failed
  work survives and resumes; finite budgets produce honest partial coverage, not false completion.
- R3: negated/optional requirements and work done for a sales team do not create false hard
  exclusions; actual forbidden duties remain excluded; ambiguous cases are retained for review;
  captured posting audit accompanies the regression suite.
- R4: local-validated rollback and deployment instructions preserve state/work and name remaining
  approvals, live gates, source-growth limitations and defensible cost assumptions.
- Existing tests remain green or contract changes are explicitly justified; SAM validates/builds;
  candidate report stays complete and readable, and current source-policy changes are reconciled.
- Whole-object review still asks whether useful unknown-employer openings can reach Brett without
  overfitted screening. More feeds, more tests and raw counts alone cannot pass it.

## Stop and next

Stop at tested local repair readiness with remaining activation requirements explicit. No
deployment occurs under this packet. A missing real Adzuna key may leave its live gate unpassed,
but is not an excuse to leave the locally reproducible runtime defect unresolved. Checkpoint
unfinished work accurately; do not label a blocked gate passed to obtain closure.

After return the orchestrator inspects the repaired artifacts, then requests the specific
deployment/credential/source-growth approvals actually needed. No blanket deploy request until
the demonstrated local defects are closed.
