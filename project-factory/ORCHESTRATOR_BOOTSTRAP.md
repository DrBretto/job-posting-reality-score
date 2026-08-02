# ORCHESTRATOR_BOOTSTRAP

## Current State Summary

Job Posting Reality Score is a deployed serverless AWS job-search radar and completed AWS refresher.
The committee roadmap remains under `docs/roadmap/committee-v1/`, but verified code and AWS state
supersede its old phase forecasts.

Current truth as of 2026-08-02:

- `jprs-v1` is deployed and scheduled in `us-east-1`.
- The production registry still contains three original build targets.
- Branch `codex/real-job-radar` contains the pending usefulness pass: 15 validated targets,
  Brett-specific deterministic ranking, readable links, SES delivery, timing repair, and tests.
- AWS deployment and `/jprs/companies` have not been changed for this pass.
- Bedrock narration and Ashby collection remain disabled.

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
2. `docs/plans/2026-08-02-real-job-radar.md`
3. `docs/PLAN.md`
4. `git status` and the latest commit
5. Live AWS state when a deployment decision depends on it

The current sequence is: finish local validation -> commit/push feature branch -> request deployment
approval -> deploy code -> update SSM between runs -> force and verify one complete run.

## State Resolution Order

1. Current operator instruction.
2. `AGENTS.md` and `CLAUDE.md`.
3. Verified AWS and repository state.
4. Active implementation plan.
5. Accepted ADRs.
6. Historical committee roadmap.

Never copy private account identifiers, ARNs, access keys, notification addresses, or secrets into
repository files or chat.
