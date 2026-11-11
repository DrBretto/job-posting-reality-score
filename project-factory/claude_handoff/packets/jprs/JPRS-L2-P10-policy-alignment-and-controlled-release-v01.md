# JPRS-L2-P10 — Current candidate policy and controlled radar release

Status: staged; not executed. Authored 2026-09-26.

## Objective and source

Finish the smallest remaining release step so Brett can receive useful openings from employers
outside the original registry. Align screening with his current centrally recorded preferences,
verify the complete P07–P10 candidate, and prepare a release. Deploy and verify one ordinary live
round only if Brett supplies fresh, explicit authorization for this release.

The purpose is employment and income, not an indefinitely polished job-search system. Brett wants
to catch up on older viable openings, then stay current with fresh ones, with no arbitrary number
of good opportunities discarded. Hundreds of applications is an intended workload, not a verified
inventory or a promise of submission throughput. Radar release does not implement applications.

Source: P09's actual return, validation, failure matrix and release handoff; the operator's current
APPLICATION_WORKFLOW.md; and his request to move this working radar toward backlog catch-up.
P09 is complete locally. Its recorded 393 passing tests are prior evidence, not this run's result.
Production remains P06 unless current read-only evidence establishes otherwise.

## Authority, executor shape and boundaries

- One implementation executor. Use one fresh, bounded review context for the policy meaning and
  changed production path after implementation; no new committee or general architecture audit.
  If a fresh reviewer is unavailable, say so rather than simulate an independent review.
- Local policy alignment and verification are authorized. The preferences are already decided;
  do not ask Brett to restate them. Explicitly approve only behavior supported by those sources.
- Deployment is NOT authorized by this file, prior P06 approval, urgency, or executing this packet.
  Accept a fresh, explicit operator instruction permitting this repaired radar's deployment and
  one controlled ordinary live round after checks pass. Record its actual wording and scope.
  Without it, finish local work and stop release-ready with the exact remaining approval boundary.
- If approved, the authorization covers the existing stack's code-only release and one ordinary
  round, including its existing digest to the existing recipient. It does not cover IAM, schedules,
  parameters, credentials, fees, new sources, limits, retention, or notification routing changes.
- Work in /Users/drbretto/Desktop/Projects/job-posting-reality-score. This is its native file-based
  factory, not an Infotropy governance run. Do not open or close an Infotropy spine run for it.
- No applications, employer messages, resume generation, submission automation build, or batch
  approval in this packet. No commits, staging, branches, resets, stashes, pushes or merges.
  Preserve unrelated and concurrent work. Do not repair packaging or other parked issues.

## Read first

Read the native AGENTS.md, CLAUDE.md, .cursorrules, factory bootstrap, shared contracts, current
status and active plan as routed there. Then directly inspect:

1. project-factory/outputs/open-market-discovery/runs/20260925_publication_commit_boundary_and_verification_v1/
   OPERATOR_RETURN.md, VALIDATION.md, FAILURE_MATRIX.md, gate_decision.md, DEPLOYMENT_HANDOFF.md,
   and evidence needed to verify the named claims. Preserve all historical run evidence.
2. /Users/drbretto/Desktop/Projects/Infotropy Book/INBOX/Employment Search/APPLICATION_WORKFLOW.md
   (especially target calibration, adjacent roles, location/compensation, screening, and backlog).
3. In that same central directory: SEARCH_PREFERENCES.md and OPERATING_PLAN.md. Use
   CANDIDATE_FACTS.md and the expanded master named by src/candidate/policy.py only as needed;
   never copy contact details or personal profile data into tests, provider calls or reports.
4. src/candidate/policy.py, src/candidate/screening.py, config/candidate_policy.json,
   src/scoring/scoring.py, relevant report/collector callers and their existing tests.
5. scripts/release_preflight.sh, scripts/reconstruct_p06_baseline_build.sh,
   scripts/check_release_change_set.py, scripts/rollback_preflight.sh,
   scripts/verify_rollback_baseline.py and scripts/inspect_discovery_integration.py.

Inspect changes since P09 before editing. Material concurrent code changes require a fresh
comparison, not reusing P09's build identity. Read current sources, not a summary of them.

## Work

### 1. Reconcile policy meaning, not just fingerprints

Reproduce policy-check. Explain the actual source delta briefly in the return. Separate screening
changes from application-process changes such as approved resume-core reuse and batch submission.
Those process permissions are not new job exclusions or permission to submit in this packet.

The existing projection builder stores hashes and a static mapping; refreshing it alone does not
implement new screening behavior. Implement the smallest tested change needed for these current
preferences, then update the rule mapping/version and refresh the projection from current sources:

- Do not target call centers, external customer service or customer phone-support queues.
- Preserve software building and problem ownership for internal users: applications, automation,
  integrations, data handling, reporting, and practical AI where useful. AI is not required.
- Meetings, requirements conversations and ordinary communication are not the prohibited work.
- Building software FOR a call center/support department is not WORKING its support queue.
- Companies without an existing engineering team are attractive, not a requirement that rejects
  companies with one. Stable employment and credible duties matter more than title progression.
- Keep existing location, compensation, experience and interview preferences. No new salary floor,
  title ban, AI-keyword requirement, or assumption of mastery of every specialist IT platform.

Use responsibilities and clause meaning, not a global banned-word list. Ambiguous or insufficient
evidence stays visible for review; do not invent a negative. Do not make a vague application-support
title automatically suitable either. Explain each definite exclusion with its actual duty evidence.
Do not change central preference documents to make the check green or duplicate their policy here.

### 2. Verify candidate consequences and preserve P09

Add regressions that distinguish external phone/customer-service work from internal software
ownership, software for customer-service teams, normal human interviews/meetings, and unknown
duties. Include an ordinary internal software role with no AI wording and a role at an established
engineering employer. Preserve existing tests for salary flexibility and contextual title handling.
Demonstrate the new defect regressions fail against the pre-P10 behavior where applicable.

Run the real screening/ranking path over the same available captured postings before and after.
Record counts and IDs/reasons for every changed disposition. Inspect all new exclusions and
promising newly retained roles; fix unsupported losses. Keep synthetic controls distinctly labeled
and never present them as vacancies. Report the captured set's limits; do not claim market coverage.

Have the bounded fresh reviewer check those changes against the original policy and inspect the
actual caller path, not just helpers. Resolve material findings in this run and recheck the repair.
Run the full existing suite, policy-check, SAM validation/build and P09's real release preflight.
Preserve the sixteen-boundary recovery coverage, debt compaction, negative release controls and
report disposition reconciliation. Do not lower or bypass a gate to finish.

### 3. Prepare the exact release; optionally perform it with authorization

Use P09's DEPLOYMENT_HANDOFF.md and fail-fast scripts, with fresh build/baseline paths. Reconstruct
and verify the archived P06 baseline; do not depend on an old temporary directory. Bind the tested
source, projection and build identities to the template passed to deployment. A local package
comparison is not evidence of an AWS change set; label each separately.

Expect six function artifacts to change due to shared packaging. Verify the change is code-only;
do not treat the number alone as proof. Stop on added/removed resources, permissions, schedules,
parameters, retention or other non-code changes. Preserve existing private notification parameters
without printing or reconstructing their values. Never restore baseline files over the working tree.

If authorization is absent: deliver the validated handoff and stop. If authorization is present:
verify account/stack and fresh baseline, follow the verified forward sequence, and perform one
ordinary live round within existing limits. Do not overlap an active round. An already-running
ordinary round can supply the evidence if its deployed code and coherent run artifacts match.
Respect delivery deduplication; do not force a duplicate digest or widen recipient settings.

Reconcile live discovery, pending/owed data, live views and the consumed/report dispositions using
the existing inspector on one coherent report generation. Trace an actual registry-absent employer's
qualified role into the ordinary report when live data provides one. Never seed production, quietly
relax fit, or rerun until a desirable role appears. INTEGRATION_OK on a legitimately thin day is not
ACCEPTANCE_MET. Partial/missing/incoherent evidence stays named, not treated as a quiet day.
Distinguish report persisted, delivery attempted, SES acceptance, and verified delivery; do not
claim Brett received a digest merely because the sender accepted it. Scheduled/unattended behavior
is a separate claim and must remain unverified unless its actual execution is observed.

If a release needs rollback, stop mutation and state the problem. Execute rollback only with
explicit authorization covering it, using the verified isolated P06 baseline. Preserve owed objects
and warn that the old code does not drain them. Do not reset or discard the uncommitted work.

## Write surface and outputs

- src/candidate/, config/candidate_policy.json and directly related regression tests. Change scoring
  or its callers only if the captured-data audit exposes a concrete contradiction of current policy;
  no ranking redesign. Other runtime/release code changes require a named in-scope regression.
- The new run directory:
  project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/
  Create it before execution. Use the native run manifest, checkpoint and gate fields; combine
  supporting narrative where possible. Provide OPERATOR_RETURN.md, DEPLOYMENT_HANDOFF.md and
  machine-readable evidence of policy consequences, tests, package comparison and any live run.
- Update only current native tracker/plan/bootstrap pointers and this packet's registry status.
  Historical runs, packets and evidence remain intact. Do not write any central Infotropy files,
  AGENTS.md, CLAUDE.md, shared contracts, resumes or personal-answer profiles.

The final return leads with what works FOR THE USER: local-only or deployed, live report outcome,
real candidates if observed, and the one actual remaining blocker. Include a compact downstream
pointer to the existing backlog-catch-up section of APPLICATION_WORKFLOW.md: after live verification,
reconcile older still-open jobs and submission history, research promising companies, obtain batch
approval, verify a real supported-form pilot, then scale. Preserve fresh arrivals during catch-up.
Do not create a second automation plan or pretend this packet supplied that functionality.

## Acceptance and stop

Local acceptance requires policy meaning implemented (not only rehashed), current projection,
the disposition-delta audit, bounded review outcome, passing regressions/full suite/build/preflight,
verified baseline and a self-contained release handoff. Name any exception; no passing-by-omission.

Deployment acceptance additionally requires fresh authorization, the exact verified code-only
release, and the observed coherent live reconciliation/delivery outcome. Report unmet positive
live acceptance separately from a legitimate zero. Local completion never implies live acceptance.

Stop at local release readiness without deployment approval, or after the authorized controlled
release and verification. Stop on unsafe/unverifiable release conditions or scope expansion; record
the precise blocker and preserve completed work. Do not request another broad committee by default.
No application submissions occur here. Next work is release if still unauthorized, otherwise the
existing employment backlog/pilot workflow once the ordinary live path has been verified.
