# ORCHESTRATOR_BOOTSTRAP

## Current State Summary

Job Posting Reality Score is a manual-first AWS refresher and a practical job-search radar.
The committee roadmap is complete and preserved under `docs/roadmap/committee-v1/`.

Current truth:

- P0 local operator kit and IAM policy drafts are ready for inspection.
- P0 AWS console work is not complete.
- No project AWS resources have been created by an AI agent.
- No application code has been implemented.
- The source repository is new and does not extend the older Company Fit Radar codebase.

## Operating Mode

**Direct implementation with a manual AWS boundary.**

The orchestrator may inspect local/AWS state read-only, create local source code and documentation,
write tests and fixtures, and verify artifacts. Brett manually creates and configures AWS resources
through P8. Never bulk-deploy the architecture, silently create cloud resources, or mark a phase
complete from document existence alone.

## Active Phases

| Phase | Status | Next gate |
|---|---|---|
| P0 account guardrails | READY FOR BRETT | Complete `docs/operator/phase-0/P0_CONSOLE_WORKSHEET.md` |
| P1 S3 substrate | LOCKED | P0 done-gate and no-notes answer |
| P2-P8 manual V1/V1.5 | LOCKED | Preceding phase complete |
| P9 IaC reconstruction | LOCKED | Working V1 |
| P10 Athena history | LOCKED | Sufficient accumulated data |

## Next Unlocked Action

`docs/operator/phase-0/P0_CONSOLE_WORKSHEET.md`

Brett performs the console steps. The AI may answer questions and run read-only verification, but it
does not click through or create the resources for him.

## State Resolution Order

When documents disagree, resolve in this order:

1. Current operator instruction.
2. `CLAUDE.md` and `AGENTS.md`.
3. `docs/PLAN.md`.
4. Accepted ADRs under `docs/ADR/`.
5. `docs/roadmap/committee-v1/JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md`.
6. Other committee reference artifacts.

An accepted local ADR may correct an unsupported implementation detail in the committee roadmap
without changing its objective.

## Resume Instructions

1. Read `README.md`, `docs/PLAN.md`, and the current phase plan.
2. Read `git status` and the latest commit before editing.
3. Confirm the current phase from the table above and from observable AWS evidence.
4. Keep manual and AI-owned work separate.
5. Update the execution log as work is completed.
6. Do not advance phases until the current done-gate and recall prompt both pass.
