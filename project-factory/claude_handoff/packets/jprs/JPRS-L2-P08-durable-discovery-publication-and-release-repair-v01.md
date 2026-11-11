# Run Packet: JPRS-L2-P08-durable-discovery-publication-and-release-repair-v01

## Header

- project_slug: jprs
- phase_key: durable-discovery-publication-and-release-repair
- execution_profile: BOUNDED_REPAIR_AND_RELEASE_VERIFICATION
- handoff_target: Claude Code
- run_id: 20260925_durable_discovery_publication_release_repair_v1
- run_root: project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/
- status: staged; not executed; no deployment authorization

## Objective and source

Finish the two concrete release gaps found in the independent P07 review. Preserve P07's working
discovery-to-report integration: employer-independent openings pass through the existing screening,
ranking, deduplication and history without employer admission first. This remains a morning job-search
tool for Brett, not a raw-feed dump, fixed employer list or daily application quota.

P07 genuinely fixes the missing connection; the independent full suite passes 339 tests and P06's
original probe now delivers a candidate. Do not undo or re-plan that work. The remaining code defect
is interrupted publication of already-captured observations. The remaining release work is making
the handoff match the actual package, recoverable deployed baseline and report evidence.

The operator's standing instruction permits obvious follow-up packets. It does not authorize a
deployment. P06 remains live; P07 and this repair are local until fresh explicit approval.

## Read first

1. Work in `/Users/drbretto/Desktop/Projects/job-posting-reality-score`. Read this repo's AGENTS/CLAUDE
   rules, factory bootstrap/contracts/current trackers and `RUN_OUTPUT_CONTRACT.md`. Use its file-based
   factory, not the Infotropy governance MCP.
2. `docs/plans/2026-09-24-open-market-job-discovery.md`, including the candidate-policy authority
   pointers and P07 ownership choice; current policy/history projections. No policy re-derivation.
3. P07 run `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/`:
   `ORCHESTRATOR_REVIEW.md`, independent interrupted-publication probe and JSON, `VALIDATION.md`,
   `DEPLOYMENT_HANDOFF.md`, baseline/build/owned-change evidence and test harness.
4. P06 run `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/`:
   build identity, live verification summary, original producer/consumer probe and review. P05 run's
   verified build-selection and rollback handoff remains relevant only at its stated version scope.
5. Actual discovery handler/persistence/live-view/state, report consumer/coverage, layout and
   connectors, relevant tests, `infra/template.yaml`, SAM config/build artifacts and assembly routing.

## R1 — recover already-captured jobs after interrupted publication

Run the reviewer's unmodified independent probe before repairs. It compares identical external
inputs with and without one storage failure before the live-view write. The original job is durably
captured, but retry sees a changed feed window and both that report and the following one omit it.

Trace durable writes and recovery boundaries, then implement the smallest replayable handoff that
keeps those observations owed until they have reached the candidate representation. Existing durable
artifacts may be reused if they preserve identity and are not overwritten before recovery. Simply
moving the progress write after the live view is not sufficient if the next fetch discards the saved
observations before replay. Choose the implementation; no generic transaction platform is requested.

Invariants:
- Already-durable usable observations are recoverable without the provider returning the job again.
- Progress/coverage cannot quietly erase unmaterialized observations; pending publication is visible.
- A repeated attempt neither duplicates jobs nor inflates observation history for the same run.
- Recovery retains original observation timing/provenance rather than claiming an old job was just
  fetched again. It cannot roll back newer observations or erase another provider's successful work.
- Partial failure at any introduced persistence boundary leaves either a committed view or explicit
  replayable work. Preserve request caps, traversal debt, candidate policy and existing feed-vs-ATS
  lifecycle distinctions. Do not silently drop older useful candidates as a recovery mechanism.

Keep the unmodified probe as before/after evidence. Add focused fault-injection regressions at the
actual external-storage boundaries, including same-run retry and the following run with the job no
longer returned by the feed, and a partial multi-provider write. New intermediate records must be
created by real producer code, not seeded by the harness. Preserve the full normal-path and earlier
P05/P07 regressions. Record what each test does and does not establish; no real cloud failure injection.

## R2 — make the release and live checks trustworthy

1. **Actual package scope.** No infrastructure source change is presently required. All functions
   inherit the shared source root, so new code can change more than the discovery/report artifacts.
   Derive allowed code-only updates from a fresh build and its packaged contents; distinguish those
   from prohibited unexpected IAM, schedule, parameter, state-machine or destructive changes. Do not
   solve this by launching the separately deferred packaging redesign. Content hashes, not mtime,
   establish unchanged source/config. Preserve notification parameters and build/template binding.
2. **Real rollback baseline.** Before recommending deployment, identify and verify a recoverable P06
   artifact/source package against its recorded identity. Prefer an existing intact local build;
   bounded read-only retrieval of the currently deployed code/config is allowed only if needed and
   available. Do not log signed download URLs, credentials, private identifiers or notification values.
   No invocation or cloud write is authorized. If no baseline can be recovered, say so and leave that
   release condition unmet; do not pretend a copy of the already-edited files is the prior version.
   Write executable rollback steps that preserve both the uncommitted overhaul and new durable state,
   including compatibility of any R1 artifacts. No reset/checkout/stash, guessed reverse patch or
   default rollback to the August code. Test recovery locally against the verified version.
3. **Live acceptance.** Provide and locally exercise the exact inspection script/commands on the
   actual report schema. Reconcile discovery-origin consumed identities to retained, excluded,
   below-fit, duplicates/aliases or explicit pending dispositions. Overall counts that can all come
   from monitored jobs do not prove integration. Include controls for a genuine zero-fit discovery
   day and a missing consumer connection, so the check distinguishes them. Verify an actual employer
   absent from the registry, not merely a discovery source ID different from every ATS source ID.
   Use an unknown/review-needed label if employer identity cannot be established.

The live positive condition remains a real registry-absent job in the actual human report after an
approved deployment. A zero is allowed, explained with source-specific evidence; do not insert a
fixture into production or keep refetching to get a pleasing sample. Code deployment, live ingestion,
actual delivery and unattended next-day behavior remain separate checks. Synthetic insurance-company
examples are test data, never recommended vacancies.

## Scope, outputs and stop

Local writes: directly implicated discovery/report/common code and tests, the existing controlling
plan and factory continuity surfaces, corrected deployment documentation, and this run_root. Reuse
existing modules. Create the run root before outputs and resume an existing checkpoint if present.

No deployment, cloud write, invocation, email, applications, employer contact, SSM/registry edits,
new providers, credentials, paid/model calls, schedule changes, source admission or unrelated cleanup.
No git branch, stage, commit, push, reset, stash or checkout. Do not edit central candidate preferences,
AGENTS or shared contracts. Only the bounded read-only baseline retrieval above may contact AWS.

Update the existing plan before implementation. Produce the standard manifest/checkpoint/gate plus
`VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`, `OPERATOR_RETURN.md` and reusable evidence. Preserve prior
failed attempts and receipts. Run targeted before/after probes, full suite, policy check, SAM
validation/build and explicit-template selection. Synchronize current summaries to distinguish
executed local repair from still-running P06; avoid leaving staged/executed contradictions.

Acceptance: the interruption reproduction is repaired through actual producer/consumer code without
test-authored wiring; focused retry/partial-write regressions and the existing suite pass; actual
package scope and a recoverable baseline are demonstrated; and the live inspection distinguishes
empty eligibility from missing ingestion. No broad audit or additional committee is needed.

Stop after local repair/verification and the corrected release handoff. `unlock` means ready for
orchestrator deployment review, not permission to deploy. If a necessary condition remains unmet,
checkpoint it with concrete evidence and `revise_implementation` rather than asserting readiness.
Next: inspect the targeted repairs and seek fresh deployment approval if they pass.
