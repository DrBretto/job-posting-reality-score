# SESSION_STATUS

## Current Session Snapshot — P10 executed locally, awaiting deployment authorization

- updated_at: 2026-09-26
- session_state: completed (local)
- next_unlocked_task: obtain a fresh explicit operator authorization covering this repaired radar's
  deployment AND one controlled ordinary live round, then execute
  `project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/DEPLOYMENT_HANDOFF.md`
  §4 and §4.1. Without that authorization the work is complete and stops at release readiness.
- result: the RED `policy-check` is resolved by IMPLEMENTING behavior, not by refreshing hashes. The
  2026-09-26 *Adjacent roles: software problem-solving, not customer service* clarification is now a
  screening rule (`customer-service-queue`, ruleset 1.4.0 -> 1.5.0); no call-center,
  customer-service, phone-support or help-desk handling existed anywhere in `src/` beforehand. The
  other two 2026-09-26 additions are application-process permissions and are deliberately NOT
  implemented as screening or as submission authority. Projection rebuilt to `1.1.0`, 9 mapped rules,
  packaged identically into all six function artifacts. `policy-check` exits 0.
- measured consequences: over the 282-posting captured corpus through the real caller path, 5 roles
  newly excluded with duty evidence, 6 reasons made more honest, and the 11 retained candidates
  unchanged job id for job id. Three misfires in the first implementation were found by that audit and
  repaired.
- review: one bounded independent reviewer (fresh context, read-only) returned `revise` on three
  material findings — internal help-desk ownership hard-excluded as external customer service, a
  call-center title cleared to ELIGIBLE by one software verb anywhere in the description, and missed
  external-support phrasings including one silent pass. All repaired, rechecked against the reviewer's
  own cases, pinned by 9 added regressions. Every build/baseline/release check was re-run afterwards.
  433 tests pass; preflight PASSES `CHANGE_SET_IS_CODE_ONLY` 6/6; P06 baseline verifies 36/36;
  rollback preflight exits 0 with the working tree byte-identical.
- known limits, not papered over: the captured corpus produces 0 pending checks for the new rule and
  contains none of the phrasings behind the review's largest finding, so the rule's third state has no
  real-data evidence yet; a PENDING_CHECK posting that also scores below the fit band reaches no
  readable report section; one theoretical report-render path was reasoned from code and never
  reproduced.
- boundary: local only. No deployment, AWS call, invocation, change-set execution, email, application,
  or git branch/stage/commit/push. P06 remains the last verified deployment and its approval is spent.
  Deployment acceptance is NOT met and was NOT sought. No application submission occurred.

## P09 Executor Snapshot — historical local result

- updated_at: 2026-09-26
- session_state: executed_pending_orchestrator_review
- current_review: P09 executed locally; gate `unlock`, REVIEW-ONLY. Its own
  `gate_decision.md` is not a deployment recommendation. P08/ORCHESTRATOR_REVIEW.md's
  `revise_implementation` is now answered, not still open.
- latest_run: `project-factory/outputs/open-market-discovery/runs/20260925_publication_commit_boundary_and_verification_v1/`.
  **Local only. Nothing deployed, invoked, committed, staged, pushed or emailed; AWS was not
  contacted.** `sam validate` and `sam build` are local packaging operations and both exit 0.
- what_moved:
  - The durable acceptance point moved to the FIRST write of each feed's round. A feed's owed
    publication is its own object (`discovery/owed/provider=<p>/owed_publication.json`), written
    before `raw/`, `normalized/`, `status/` and the SUCCESS sentinels — so nothing durable precedes
    acceptance and the state P08 had, captured-but-unrecoverable, no longer exists. Recovery reads
    each provider's derived key plus the legacy aggregate, so a debt the DEPLOYED code wrote is
    settled rather than orphaned; still no `ListBucket`, no `DeleteObject`, no IAM change.
  - The P08 reviewer's UNCHANGED probe went from losing the job in both later reports to matching
    its control in every field; P07's unmodified live-write probe still passes.
  - All SIXTEEN write boundaries from acceptance to settlement were refused in turn, including a
    write that lands and then times out before the caller hears. Every one either accepts nothing
    (one row: the acceptance write itself, where nothing at all was written) or accepts and
    recovers on the same-run retry AND the following round, with the feed returning nothing.
  - Owed debt is COMPACTED, not evicted. The first healthy round after a backlog now publishes
    every owed posting instead of discarding the oldest by enqueuing its own empty batch.
  - The release checks reject what they name: a changed built-template resource property, an added
    or removed function, an unavailable baseline and an unperformed comparison all FAIL; rollback
    verification fails closed before restoring and refuses to restore over the working tree; the
    report states `consumed_job_ids` and `below_fit_threshold_job_ids`, so a stored job missing
    from the report is no longer invented as below-fit.
  - The P06 baseline build is reconstructed from the verified archive, not a temporary directory,
    and the forward and rollback sequences are fail-fast scripts drilled 7/7 with stubbed tools.
  - 393 tests pass (350 before). The change set against the reconstructed baseline is code-only
    across all six functions.
- next_unlocked_task: orchestrator review of the P09 run.
- handoff: `project-factory/outputs/open-market-discovery/runs/20260925_publication_commit_boundary_and_verification_v1/OPERATOR_RETURN.md`,
  then `VALIDATION.md`, then `DEPLOYMENT_HANDOFF.md` — which supersedes P08's on four points.
- boundary: production remains P06 and its approval is spent. Do not deploy using the qualified P08
  handoff. Deployment needs fresh authorization after review.
- operator_decision_open: `policy-check` is RED. Two operator-owned documents outside this
  repository (`../Infotropy Book/INBOX/Employment Search/APPLICATION_WORKFLOW.md` and
  `OPERATING_PLAN.md`) were edited on 2026-09-26 and the committed screening projection no longer
  matches them. P09 changed no policy source; refreshing the projection is a candidate-policy
  decision. The release preflight halts there by design.
- pending_not_verified: a real registry-absent job in a delivered report; the unattended round on
  2026-09-26 (P06 code, not checked here); authenticated Adzuna; source admission and the careers-URL
  resolver. None of these is resolved by local tests.

## P08 Executor Snapshot — historical, qualified by the current review

- updated_at: 2026-09-25
- session_state: executed_pending_deployment_decision
- current_review: P08 executed and closed BOTH P07-review findings locally; awaiting orchestrator
  inspection and a fresh deployment decision. P07's review (`P07/ORCHESTRATOR_REVIEW.md`) remains the
  record of WHY P08 existed; its `revise_implementation` is now answered, not still open.
- latest_run: P08 executed — `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/`.
  **Local only. Nothing deployed, invoked, committed, staged, pushed or emailed; AWS was not contacted
  at all** — the bounded read-only retrieval the packet permitted for the rollback baseline was not
  needed, because an intact local P06 build was found and hash-verified instead.
  **R1, interrupted publication.** `persist()` committed `raw/`, `normalized/`, `status/`, the SUCCESS
  sentinel, coverage, traversal state and growth, and only THEN wrote the live view the report reads —
  so one failed write left an observation durable and unreachable, and the same-day retry destroyed the
  last trace by overwriting `normalized/` for that `dt`. The order is now snapshots → OWE → progress →
  DRAIN → residual receipt. Observations are owed to `discovery/_pending_publication.json` (one object
  at one KNOWN key, because the discovery role has `GetObject`/`PutObject` on `discovery/*` and neither
  `ListBucket` nor `DeleteObject` — a scanning or deleting design would have been an IAM change), and
  drained one feed at a time, each feed's debt cleared only after its view commits. Replay is exactly
  idempotent (per-posting `observed_run_ids`) and monotonic in time, so a batch owed twice cannot
  duplicate a row, inflate observation history, roll back a newer observation or disturb another feed.
  Verified with the P07 reviewer's OWN unmodified probe (diff-verified byte-identical): the interrupted
  arm went from 0 candidates on both the same-run retry and the following report to matching the
  uninterrupted control in EVERY field — with the feed returning nothing on both later fetches, so it is
  replay of the capture and not a re-fetch. Owed publication is visible to the operator: coverage
  receipt, report JSON, a `PARTIAL` discovery health axis, and a named line in the rendered report.
  11 new fault-injection regressions refuse one real `PutObject` inside the mocked client; 350 tests
  pass (339 before) and P07's integration is behaviorally unchanged.
  **R2.1, package scope.** DERIVED by hashing the verified P06 package against a fresh build rather
  than asserted: **6 of 6 function artifacts change**, not the 2 P07's handoff claimed — every function
  inherits `CodeUri: ../`, so a shared-module edit reaches all of them. P07's stop rule would therefore
  have REJECTED a correct deploy; it is replaced. Six application-code paths differ, the built templates
  are byte-identical, and `infra/template.yaml`, `infra/samconfig.toml` and `config/discovery_sources.yaml`
  match P06's recorded SHA-256 exactly. Verdict `CHANGE_SET_IS_CODE_ONLY`.
  **R2.2, rollback baseline.** P07 proposed copying the already-edited working files aside, which would
  have "restored" the version being rolled back. A real baseline was found: the local P06 build matches
  P06's own recorded per-file hashes on 36/36 source files in 6/6 packaged functions (`BASELINE_VERIFIED`).
  It is archived in-repo at the run's `evidence/p06_baseline_src.tar.gz` so it cannot evaporate with a
  reboot, and the full restore-and-return cycle was drilled in a scratch directory (`DRILL_PASSED`) with
  no git reset/checkout/stash anywhere in the procedure.
  **R2.3, live acceptance check.** `scripts/inspect_discovery_integration.py` reconciles every stored
  discovery identity to a disposition in the real report schema and checks EMPLOYER identity against
  `config/companies.yaml` rather than comparing source ids. Exercised on reports the real stages
  produced: 5/5 controls, including the zero-fit vs missing-consumer pair that produces identical-looking
  reports and that P07's proposed check could not separate.
- superseded_run: P07 executed — `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/`.
  The discovery-to-report edge is closed LOCALLY and is NOT deployed. Discovery now writes a durable
  feed-keyed live view at `discovery/live/provider={p}/live_jobs.json`; `assemble_report_input` reads
  the manifest's `expected_discovery_sources` and merges those postings into the job population before
  dedup, so screening, ranking, history and freshness run over both populations. Verified by re-running
  the P06 reviewer's OWN unmodified probe: 0 candidate rows before, 1 after, from an employer absent
  from the registry. A 23-case acceptance harness drives the real enumerate, collector, discovery,
  differ and report stages with only HTTP/AWS/SES mocked, and asserts structurally that no intermediate
  artifact is test-authored. Two further defects repaired: discovery job identity was bound to the
  pagination cursor (one posting became a different job on every page/day), and `resolve_run_timing`
  recovered previously-reported ids only from `complete_candidate_list`, so the already-delivered
  2026-09-25 report — whose rows live in `top_matches` — read as a round that showed nothing and would
  have re-announced everything the next morning. P05's two conditional report tests were re-scoped onto
  the real producers and their "real internal wiring" claim withdrawn; P05's own evidence is untouched.
  NO infrastructure, IAM, schedule or state-machine change was required, and that is asserted by tests
  against the real template and ASL file. 339 tests pass (316 before), policy projection matches, SAM
  validates and builds. Nothing deployed, committed, staged, branched or pushed.
- return_review: P06 deployment and one-run transport evidence accepted at their stated scope;
  product acceptance refused. Independent real enumerate/discovery/report probe produces one
  normalized job and zero candidates without hand-written intermediate state. P05's stronger
  integration inference is withdrawn in P06/ORCHESTRATOR_REVIEW.md; conditional tests remain valid.
  P07 prepared under the standing follow-up instruction. No runtime code, AWS or git mutation by review.
- what_moved: P06 executed under explicit operator deployment approval, recorded before any cloud
  mutation. **The overhaul is DEPLOYED to `jprs-v1` in `us-east-1`.** The change set was read before
  executing: 6 adds (discovery function, its role, log group, scheduler role, schedule, A8 alarm), 9
  non-destructive modifies, 0 removals, 0 replacements, every detail RequiresRecreation Never. Collect
  07:00 and assemble 09:00 America/New_York, the 15-board registry, retained storage and every existing
  parameter value (including the three email settings, which have no template default) were preserved;
  the new `jprs-discovery-daily` schedule is the reviewed cron(5 7) in the same timezone, not an invented
  cadence. **The live-transport gate is closed for the four keyless feeds:** one production
  `jprs-discovery` invocation attempted and succeeded on all four, `inaccessible: 0`, 295 jobs across 218
  employers, real descending-cursor pagination, every source inside its configured cap, Adzuna named as
  credential-gated rather than silently skipped. The P05 resumability invariant held on real data without
  injecting any failure: `head_pending` empty and the receipt's `inaccessible` empty, agreeing. Report
  timing now reads `manifest.opened_at` in production where the old code wrote null, and same-date digest
  suppression was honored, so zero emails were sent. **The product goal is NOT delivered: none of the 295
  discovered jobs can become candidate rows.** The report's 35 rows are all greenhouse/ATS_BOARD.
  `enumerate` files discovery ids under `expected_discovery_sources` while the report loads jobs only
  from `expected_sources` and never reads that field, and `current/` is differ-owned with the differ
  invoked once per `/jprs/companies` entry, so `current/` holds nothing but `provider=greenhouse/`. An
  absent integration, not an empty valid result; it predates the deployment and was surfaced rather than
  improvised over. It also corrects the record on P05: those two persisted-report regressions passed
  because the test harness itself wrote `expected_sources` and `current/` for discovery sources, so they
  never proved the wiring existed. Second finding: the first post-deploy report read
  `timing.boundary: cold-start` because the real old-format reports carry an empty
  `complete_candidate_list`; next-round recovery expected but not verified. No commit, branch, push, reset,
  registry or SSM change; the uncommitted tree is intact.
- blocked: nothing is blocked. P07's two blocking findings are closed locally by P08. The only gate
  left is the operator's fresh deployment approval; P06's is spent on P06. P06's DEPLOYED report still
  lacks discovery candidates and will until this repair ships. Separate:
  authenticated Adzuna, general-industry coverage, employer admission, the careers-URL resolver live
  path. One production run is not a durability claim for the transport.
- what_is_next: orchestrator inspects P08's targeted repairs and returns a fresh deployment decision.
  Read `P08/OPERATOR_RETURN.md`, then `VALIDATION.md` sections 1-4, then `DEPLOYMENT_HANDOFF.md`
  section 2 (the corrected stop rule: expect SIX code-only function updates) and section 6 (the drilled
  rollback). No new committee. Leave P06 deployed; no deployment or rollback is authorized yet.
- pending_not_verified: **Live acceptance is still UNPROVEN after P08.** No registry-absent job has appeared in
  a report actually delivered. The check is now `scripts/inspect_discovery_integration.py`, with the
  fetch-then-inspect commands in the P08 `DEPLOYMENT_HANDOFF.md` section 5.1; it separates a legitimately
  thin day from a broken integration and from owed publication. A zero must be recorded as a zero, with
  its evidence, and not re-run away. Separately, the first unattended round on the DEPLOYED (P06) code fires 2026-09-26 (collect 07:00,
  discovery 07:05, assemble 09:00 America/New_York). Whether the report then reads
  `timing.boundary: reported-ids` with `previous_run_id: 2026-09-25` instead of `cold-start` is NOT
  verified. Exact evidence paths in the deployment run's
  `evidence/p06_live_verification_summary.md` section 6. No automation was created to wait for it and it
  must not be recorded as passed before it runs.
- exact_artifact_paths:
  - `project-factory/claude_handoff/packets/jprs/JPRS-L2-P08-durable-discovery-publication-and-release-repair-v01.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/ORCHESTRATOR_REVIEW.md`
  - `project-factory/claude_handoff/packets/jprs/JPRS-L2-P07-discovery-to-report-integration-v01.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/ORCHESTRATOR_REVIEW.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/OPERATOR_RETURN.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/evidence/p06_live_verification_summary.md`  (the five claims, kept separate)
  - `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/gate_decision.md`  (`revise_implementation`)
  - `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/checkpoint.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/evidence/p06_live_discovery_coverage.json`
  - `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/evidence/pre_discovery_report_2026-09-25/`
  - `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/DEPLOYMENT_HANDOFF.md`  (the instruction this deployment followed)
  - `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/ORCHESTRATOR_REVIEW.md`
  - `START_HERE.md`
  - `docs/plans/2026-09-24-open-market-job-discovery.md`
  - `docs/plans/2026-09-25-resumable-discovery-release-repair.md`
  - `src/discovery/`, `src/enumerate/handler.py`, `src/report/handler.py`, `src/differ/handler.py`
  - `infra/template.yaml`, `infra/DEPLOY.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/OPERATOR_RETURN.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/DEPLOYMENT_HANDOFF.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/VALIDATION.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/gate_decision.md`  (`unlock`, review-only)
  - `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/evidence/p07_stage_trace.json`
  - `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/evidence/p07_sample_report.md`
  - `src/discovery/live.py`, `tests/test_discovery_to_report_integration.py`
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/OPERATOR_RETURN.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/VALIDATION.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/DEPLOYMENT_HANDOFF.md`  (supersedes P07's on change set, rollback and the thin-day check)
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/gate_decision.md`  (`unlock`, review-only)
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/checkpoint.md`
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/evidence/p08_before_repair_interrupted_publish.json` and `p08_after_repair_interrupted_publish.json`
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/evidence/p08_package_scope.txt`, `p08_rollback_baseline_verification.txt`, `p08_rollback_drill.txt`, `p08_live_check_exercise.txt`
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/evidence/p06_baseline_src.tar.gz`  (the verified rollback baseline)
  - `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/evidence/p08_sample_report_interrupted_round.md` and `p08_sample_report_recovered_round.md`
  - `scripts/inspect_discovery_integration.py`, `tests/test_durable_discovery_publication.py`
- next_unlocked_task: inspect P08's targeted repairs, then request fresh deployment approval.

## Verified Boundaries

- Production is on the 15-target registry. Never change the registry during a run.
- Bedrock remains off. **Ashby is now ON** — its identity concern was closed on 2026-09-24 with
  live evidence (1,083 postings across four boards, all carrying stable UUIDs). No Ashby board is
  in the registry yet, so nothing changes until one is added.
- No automated applications or personal-contact harvesting.
- Never record private account identifiers, ARNs, keys, MFA codes, or notification addresses.
- The 15-board production baseline remains a monitor, not proof of market-wide coverage. The new
  report enforces this itself: run health is split into four axes and collection health states in
  words that it is not a claim about the job market.
- **The DEPLOYED code is now the P01-P05 overhaul, deployed 2026-09-25.** It is still UNCOMMITTED in
  the working tree, so the tree and the deployed stack must not diverge unnoticed.
- Discovery is live at 07:05 America/New_York and writes only `discovery/`, `raw/`, `normalized/`
  and `status/`. It cannot write `current/` or `events/`, which is why leaving it running is safe.
- Discovery's jobs do NOT reach the candidate report **in the deployed stack**. That remains true of
  production until the P07 repair is approved and deployed. The repair exists only in the working tree.
  Do not describe the radar as market-wide, and do not describe P07's behavior as production behavior.
- P07 adds ONE new stored shape, `discovery/live/provider={p}/live_jobs.json`, written only by
  discovery and read only by report. The deployed P06 code never reads or writes that key, so a mixed
  deploy degrades to today's behavior rather than failing. No existing object's shape changes.
- A deploy must never omit `--template-file` or pass a relative `--config-file`. Omitting the
  template selects a nonexistent root template, or a stale build with no discovery function in it.
- Candidate preferences remain in the Career Factory workflow named by the controlling plan.
