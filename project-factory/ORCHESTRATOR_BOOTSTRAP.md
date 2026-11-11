# ORCHESTRATOR_BOOTSTRAP

## Routing update — 2026-09-26 18:27Z, recovery release DEPLOYED

**CURRENT STATE (2026-09-26 18:27Z) — supersedes everything below it that says P07–P10 are local.**
P10 was deployed at 14:22Z by the Career Factory release run and broke discovery in production
(first round could not read its own never-written state: no `s3:ListBucket`) while the report kept
failing on its vocabulary guard. The recovery release is now DEPLOYED and live-verified: one IAM
statement (discovery may list `discovery/*` only) plus discovery/report code. The ordinary round run
after deployment, under the deployed roles, succeeded end to end — discovery 4/4 keyless feeds and
297 jobs, assemble 15/15 boards, `daily_report` persisted for 2026-09-26 with 56 retained candidates
(15 from discovery), digest accepted by SES, and `scripts/inspect_discovery_integration.py` returned
`ACCEPTANCE_MET`. Still NOT verified: an unattended scheduled round (next 07:05 / 09:00), and digest
receipt. Adzuna remains credential-gated. Record, evidence, rollback: `../Infotropy Book/book-factory/runs/20260926_career-radar-production-recovery-v1/`
(`EXECUTION_RETURN.md`, `RELEASE_PROPOSAL.md`); plan: `docs/plans/2026-09-26-radar-production-recovery.md`.
The live baseline for the NEXT release is this build; see `infra/DEPLOY.md` § Release gate.

The P10 routing update below ("P10 is executed locally … next step is authorization") is stale: P10
was deployed at 14:22Z and has been superseded in production by the recovery release. Its evidence stands.

## Routing update — 2026-09-26, P10 executed locally

P10 is **executed locally**:
`project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/`.
Read `OPERATOR_RETURN.md` first, then `INDEPENDENT_REVIEW.md`, `VALIDATION.md` and
`DEPLOYMENT_HANDOFF.md`.

The RED `policy-check` that halted P09's release sequence is **resolved, by implementing behavior
rather than refreshing a hash**: the 2026-09-26 *Adjacent roles: software problem-solving, not
customer service* clarification is now a screening rule (`customer-service-queue`, ruleset 1.5.0),
and no call-center / customer-service / phone-support / help-desk handling existed anywhere in `src/`
before this run. The other two 2026-09-26 additions are application-process permissions and are
deliberately NOT implemented as screening or as submission authority. `policy-check` now exits 0 and
the projection is `1.1.0` with 9 mapped rules, packaged into all six function artifacts.

Measured on the 282-posting captured corpus through the real caller path: 5 roles newly excluded with
duty evidence, 6 reasons made more honest, and the 11 retained candidates unchanged job id for job id.

A bounded independent review returned `revise` with three material findings — internal help-desk
ownership hard-excluded, a call-center title cleared to ELIGIBLE, and missed external-support
phrasings including one silent pass. All were repaired, rechecked against the reviewer's own cases and
pinned by regressions, and every build/baseline/release check was re-run afterwards. 433 tests pass;
preflight PASSES with `CHANGE_SET_IS_CODE_ONLY` across 6/6 artifacts; the P06 baseline verifies 36/36;
rollback preflight exits 0 leaving the working tree byte-identical.

**The next step is a fresh explicit operator authorization** for this repaired radar's deployment and
one controlled ordinary live round. P06's approval is spent and P06 remains the last verified live
version. Nothing was deployed, invoked, committed, staged or pushed, and AWS was not contacted. No
applications were submitted and no part of the submission pilot was built. No new committee and no new
broad review by default. This routing update supersedes the older "review P09 next" instructions
below, not their evidence.

## Current State Summary

Job Posting Reality Score is a deployed serverless AWS job-search radar and completed AWS refresher.
The committee roadmap remains under `docs/roadmap/committee-v1/`, but verified code and AWS state
supersede its old phase forecasts.

Current direction as of 2026-09-26: P06 **deployed P01–P05 and verified four keyless feeds**, but
the product goal is still blocked IN PRODUCTION: the deployed code has no connection between
discovered jobs and the morning candidate report. P07 closed that connection locally, P08 made the
publication durable across an interrupted write, and **P09 is now executed locally** — it moved the
durable acceptance point, replaced owed-debt eviction with compaction, and made the release and
reconciliation checks reject the conditions they name. **P10 has since aligned screening
with the operator's current preferences and re-verified the release; its RED policy check is
resolved.** The next step is fresh deployment authorization. P06's approval is spent. No new
committee.

Latest run: `project-factory/outputs/open-market-discovery/runs/20260925_publication_commit_boundary_and_verification_v1/`.
Read `OPERATOR_RETURN.md`, then `VALIDATION.md`, then `DEPLOYMENT_HANDOFF.md` — which **supersedes
P08's** on four points — and `FAILURE_MATRIX.md` for the boundary evidence. P09 is local only:
nothing deployed, invoked, committed, staged or pushed, and AWS was not contacted.

**That operator decision is now closed by P10, not by a hash refresh.** `policy-check` was RED
because two operator-owned documents outside this repository
(`../Infotropy Book/INBOX/Employment Search/APPLICATION_WORKFLOW.md` and `OPERATING_PLAN.md`) were
edited on 2026-09-26. P09 correctly declined to touch candidate policy. P10 implemented the one
screening change those edits actually ask for — the call-center / external-customer-service exclusion,
which had no implementation anywhere — then refreshed the projection. `policy-check` exits 0 and the
preflight runs to completion. **The only remaining gate is a fresh deployment authorization.**

What P09 changed, in one paragraph: a feed's owed publication is now its own object
(`discovery/owed/provider=<p>/owed_publication.json`) and the FIRST durable write of that feed's
round, ahead of `raw/`, `normalized/`, `status/` and the SUCCESS sentinels — so nothing durable
precedes acceptance and the state P08 had, captured-but-unrecoverable, no longer exists. All sixteen
write boundaries from acceptance to settlement were refused in turn and every one either accepts
nothing or accepts and recovers without the feed returning the posting. 393 tests pass.

Two P08 facts still matter before any deploy and are unchanged: the change set is **six code-only
function updates, not two** (every function inherits `CodeUri: ../`, so P07's stop rule would have
rejected a correct deploy), and the rollback restores a **hash-verified P06 baseline** archived at
`…/20260925_durable_discovery_publication_release_repair_v1/evidence/p06_baseline_src.tar.gz`. P09
reconstructs the baseline BUILD from that archive rather than from the temporary directory P08's
handoff named, which no longer exists. P05's handoff remains the record of the release P06
performed, and its August data downgrade is unchanged; historical evidence is preserved.

The central change: employer is now a property of the JOB, not of the source. Monitoring can only
answer "what is open at this employer" and so structurally could not surface an unnamed one;
discovery answers "who is hiring for this work" and can. Measured on live data, employers reaching
the system that are absent from the registry went from 0 to 161 in the P01 sweep and 216 in the
larger P03 sweep — employers observed, not postings and not monitored sources.

P05 closed the two blockers the P04 review reproduced. Recent traversal now records the ranges it
still OWES separately from what it has OBSERVED, so a failed or partial page is no longer erased by a
frontier that advanced from the pages that did load, and a newly published continuation no longer
overwrites a saved one. Every outbound attempt spends its request. Deployment and rollback now name the
template and an absolute config path, so they select the build that was verified rather than a
nonexistent root template or a stale build with no discovery function. 316 tests pass; 12 of 20 new
tests fail against a reconstructed P04 source. Its persisted-report tests supplied missing wiring
and do not prove production integration. P06 established one production fetch on all four keyless
feeds; authenticated Adzuna, sustained transport reliability, the careers-URL resolver and source
admission remain separate checks. P07 wired useful discoveries into the ordinary report and P08 made
that publication durable across an interrupted write; both are local and neither is deployed.

Historical baseline verified on 2026-08-02, extended by P06:

- `jprs-v1` is deployed and scheduled in `us-east-1`.
- The production registry contains 15 validated targets.
- Branch `codex/real-job-radar` contains the deployed usefulness pass: Brett-specific deterministic
  ranking, readable links, SES delivery, timing repair, and tests.
- A controlled run completed 15/15 collection and produced 519 scorecards with 41 useful matches.
- SES identity, first digest delivery, and same-day duplicate suppression are verified.
- Bedrock narration remains disabled.
- Ashby collection is now ENABLED in the working tree; its identity concern was closed on
  2026-09-24 with live evidence (1,083 postings across four boards, all stable UUIDs). No Ashby
  board is in the registry yet, so nothing changes until one is added.

## Operating Mode

**Direct implementation with an explicit AWS boundary.**

The orchestrator may inspect local and AWS state read-only, implement code/docs/tests, run local
verification, and commit/push an owned feature branch. It must obtain Brett's explicit approval
before deployment, SSM changes, destructive cloud actions, or merging to `main`.

This is not a governance-packet task. Do not invoke the Infotropy governance spine for ordinary work
in this repository.

## Active Checkpoint

Read in this order:

1. `START_HERE.md`
2. `docs/plans/2026-09-24-open-market-job-discovery.md`
3. `docs/PLAN.md`
4. `git status` and the latest commit
5. Live AWS state when a deployment decision depends on it

P06 is executed: the overhaul is deployed and its four keyless feeds are live-verified. P07, P08,
P09 and P10 are executed LOCALLY and are not in the deployed stack. P10 closed the policy-projection
divergence by implementing the missing screening behavior, survived a bounded independent review that
returned `revise` on three material findings (all repaired and pinned), and re-verified the whole
release sequence afterwards. 433 tests pass. Seek fresh deployment approval. No new committee.
Leave the stack deployed meanwhile: discovery cannot write `current/` or `events/`, nothing is
corrupting, and no rollback or data downgrade is needed. Separately **pending and NOT verified**: the
first unattended round on 2026-09-26 (discovery 07:05), whose exact evidence paths are in the P06 run's
`evidence/p06_live_verification_summary.md` §6; it must not be recorded as passed before it runs. No new
broad review by default. P05 `ORCHESTRATOR_REVIEW.md` still controls on rollback: an August rollback
requires the previously specified job-data downgrade.
Because the DEPLOYED code's discovery jobs do not yet reach the report, daily use is still unchanged
until this repair ships: read the monitored results plus wider discovery,
verify every credible fit, and hand accepted opportunities to Career Factory for bespoke
applications. Neither a prepared application nor an old application folder proves submission — the
new history projection encodes exactly that distinction, and a scan can never conclude a submission
on its own.

## State Resolution Order

1. Current operator instruction.
2. `AGENTS.md` and `CLAUDE.md`.
3. Verified AWS and repository state.
4. Active implementation plan.
5. Accepted ADRs.
6. Historical committee roadmap.

Never copy private account identifiers, ARNs, access keys, notification addresses, or secrets into
repository files or chat.
