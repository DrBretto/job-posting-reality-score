# Run Packet: JPRS-L2-P06-controlled-discovery-deployment-v01

## Header

- project_slug: jprs
- phase_key: controlled-discovery-deployment
- execution_profile: CONTROLLED_DEPLOYMENT
- handoff_target: Claude Code
- run_id: 20260925_controlled_discovery_deployment_v1
- run_root: project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/
- status: staged; not executed; deployment approval outstanding

## Objective and source

Put the locally accepted open-market job radar into Brett's existing JPRS service and verify that
real employer-independent feeds reach the morning candidate report. The aim is usable fresh job
opportunities, not more infrastructure or a new review cycle. Preserve the fixed-board monitor,
application history, candidate policy, existing budgets and older strong leads.

P01–P05 executed locally; P05 independently passes 316 tests, the unchanged lost-page reproductions,
persisted-report checks and template-selection checks. See P05 `ORCHESTRATOR_REVIEW.md`. No production
deployment has occurred in this sequence. Tests and mocked transport do not establish live access.

## Approval gate and scope

This packet's existence is NOT deployment approval. Before any cloud mutation, require the
operator's current instruction to explicitly authorize this controlled JPRS deployment. A direction
merely to read/review the packet does not authorize it. Without approval, complete only useful
read-only preflight and request that one decision; do not upload build artifacts or create a change
set. Record the approval message/source when supplied.

With that approval, scope is limited to updating the existing `jprs-v1` stack in `us-east-1` with the
P01–P05 implementation, its declared discovery resources/permissions, and bounded controlled
invocations needed to validate it. Preserve the existing collect/assemble schedules and their
timezones; the new discovery schedule must match the reviewed template. Do not invent a new daily
cadence. Keep Bedrock off, resolver off, current provider request caps and the existing below-$5/month
cost ceiling. Stop if the change set requires destructive replacement, broader/unrelated permissions,
new commercial services or materially greater cost than this scope.

No Adzuna signup, credential provisioning, SSM/registry edits, new admitted employers, paid model
calls, employer contact, applications, new reminders, personal-data uploads, commit/push/branch/reset
or unrelated feature changes. Preserve the full uncommitted tree. Normal digest delivery may go only
to the already-configured operator recipient as part of the approved controlled report; do not
force resend, change recipients or bypass existing same-date suppression.

Use the JPRS file-based factory, not the Infotropy MCP spine. Create run_root before outputs and
resume an existing checkpoint rather than duplicating a release. Local writes: this run's evidence,
deployment clarification if needed, and existing plan/factory continuity surfaces. Runtime repairs
outside a trivial, clearly evidenced launch correction require a separate bounded handoff.

## Read first

1. JPRS `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, factory bootstrap/shared contracts,
   `project-factory/claude_handoff/RUN_OUTPUT_CONTRACT.md`, current status and packet registry.
2. `docs/plans/2026-09-24-open-market-job-discovery.md`,
   `docs/plans/2026-09-25-resumable-discovery-release-repair.md`, `docs/PLAN.md`, `START_HERE.md`.
3. P05 run `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/`:
   `ORCHESTRATOR_REVIEW.md`, `DEPLOYMENT_HANDOFF.md`, `VALIDATION.md`, gate and evidence. Section 6.2
   is authoritative for this release's rollback data requirements; the generic August rollback
   in `infra/DEPLOY.md` is insufficient. Do not interpret "August needs nothing" as no data downgrade.
4. `infra/DEPLOY.md`, `infra/samconfig.toml`, `infra/template.yaml`, discovery configuration,
   actual discovery/enumerate/collector/assembly/report invocation and persistence paths.
5. P03 rollback rehearsal and `src/common/rollback.py` before accepting any recovery plan.

## Execution plan

### 1. Establish the actual deployment boundary

Read current identity/region/stack parameters and health without recording private identifiers or
secrets in Git/chat. Confirm the target from existing configuration, never guess. Inventory existing
schedules, active executions and queue depth; do not overlap a running collection/assembly with a
deployment. Preserve existing notification settings and registry. Missing authentication is a real
blocker, not permission to hunt for other credentials.

Record the working-tree/build identity without committing: owned source hashes, template/config
hashes with secrets excluded, current baseline and dirty-state boundaries. Check approved candidate
policy projection. Re-run local tests/build checks if the tree changed since P05; always create a
fresh build for this deployment and bind its template plus the absolute repository config as P05
section 4 specifies. Verify the built artifact contains the discovery resources.

For the optional selection probe use SAM's own installed interpreter, not a mixed repository/SAM
site-packages environment; the latter failed with OpenSSL `GEN_EMAIL` during independent review.
Do not change dependencies to repair that test-launch choice.

### 2. Deploy only the reviewed change set

After explicit operator approval, prepare and inspect the exact stack change set before executing.
Expected changes are the declared discovery Lambda/log/schedule/role/alarm, supporting parameters and
permissions, and the P01–P05 code updates. Preserve retained storage, history and existing parameter
values. A stale August description of expected changes is not authority to omit discovery.
Stop and report unexpected destructive/unrelated changes. Never deploy an implicit/stale template.

Await stack completion and capture sanitized resource/health evidence. A successful stack update is
deployment evidence only, not job-discovery acceptance. Keep rollback ready; do not reset the source.

### 3. Verify real collection reaches the user-facing report

Inspect the real invocation order and run IDs before triggering anything. Use bounded discovery,
collection and assembly invocations only when quiescent; do not fabricate dates, bypass idempotency,
overwrite evidence solely for a test or mark day-two behavior verified on a same-date retry.

Verify P05 section 5 against real persisted outputs:

- For each configured keyless source, report attempted/succeeded/inaccessible, response validity,
  source budget and retained raw/normalized evidence. Production Lambda HTTP, not a local curl
  surrogate, must establish live access. Partial success is partial coverage, not all-source success.
- Demonstrate at least one registry-absent employer's actual eligible or review-needed job reaching
  the persisted report with its source/application link and honest age/location. No invented strong
  fit, quota or claim that every returned job is suitable. If none appear, distinguish an empty
  valid result from an unverified integration and retain the evidence.
- Verify report timing comes from the manifest and the prior saved report when one exists.
  First deployment does NOT necessarily imply `cold-start`: existing August reports can supply a
  valid prior ID list. Unknown publication age stays unknown. A later scheduled report is needed
  for the real cross-round gate if it cannot be established now without altering the clock.
- Verify pending recent ranges and inaccessible coverage agree; no claimed clean recent coverage
  while owed ranges remain. Inspect actual budget accounting. Do not inject failures into production
  to manufacture this evidence; distinguish naturally observed recovery from local regression proof.
- Confirm the fixed-board monitor and ordinary report/digest behavior remain intact. Honor existing
  recipient and duplicate suppression. At most the normal allowed digest, no forced test-email loop.

Do not keep rerunning providers until a green sample appears. Use current source limits, report
failures and decide whether they require safe containment or a focused follow-up.

### 4. Recovery and honest completion

If deployment or live verification fails, preserve evidence and the uncommitted implementation.
Do not improvise destructive rollback. A source-only August rollback cannot read current job/diff/
event state: required sequence is quiesce writers -> verified backup and data downgrade -> explicitly
bound prior build -> verified restart. The fact August ignores `head_pending` does not remove that
requirement. Seek specific approval before applying a data downgrade, deleting any key or performing
source rollback; ordinary CloudFormation-managed update rollback is distinct. If continued running
would corrupt data, surface the exact containment action for approval rather than silently rewriting
state. Do not restore the old registry as a generic recovery step; this packet never changes it.

## Acceptance and stop

Produce manifest, checkpoint, gate decision, concise operator return and sanitized deployment/live
verification evidence. Separate these claims: local repair accepted; stack deployed; individual
sources live-verified; jobs/report useful; later scheduled freshness verified. No one status implies
the rest. Update existing continuity surfaces with actual state and the exact next pending action.

Stop after approved deployment and bounded immediate verification, or a genuine blocker. Record any
later scheduled-round check as pending with its exact evidence path; do not wait indefinitely, create
an automation or falsely close it. No fresh broad audit by default. Adzuna credentials/general-
industry coverage, employer admission and longer-term completeness remain separate follow-ups.
