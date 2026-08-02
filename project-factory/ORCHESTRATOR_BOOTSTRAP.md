# ORCHESTRATOR_BOOTSTRAP

## Current State Summary

Job Posting Reality Score is a deployed serverless AWS job-search radar and completed AWS refresher.
The committee roadmap remains under `docs/roadmap/committee-v1/`, but verified code and AWS state
supersede its old phase forecasts.

Current truth as of 2026-08-02:

- `jprs-v1` is deployed and scheduled in `us-east-1`.
- The production registry contains 15 validated targets.
- Branch `codex/real-job-radar` contains the deployed usefulness pass: Brett-specific deterministic
  ranking, readable links, SES delivery, timing repair, and tests.
- A controlled run completed 15/15 collection and produced 519 scorecards with 41 useful matches.
- SES identity, first digest delivery, and same-day duplicate suppression are verified.
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

The current sequence is: read the daily shortlist -> choose one to three roles -> verify each live
posting -> tailor and apply manually -> let history accumulate.

## State Resolution Order

1. Current operator instruction.
2. `AGENTS.md` and `CLAUDE.md`.
3. Verified AWS and repository state.
4. Active implementation plan.
5. Accepted ADRs.
6. Historical committee roadmap.

Never copy private account identifiers, ARNs, access keys, notification addresses, or secrets into
repository files or chat.
