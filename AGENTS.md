# Codex Project Rules

## Role

Codex is used for targeted edits, bug fixes, quick refactors, and small-to-medium feature work in this repository.

## Canonical Rules

- `CLAUDE.md` is the canonical source of workflow, planning, dependency, security, platform, testing, and git rules.
- `.cursorrules` applies as additional precision/diff-control guidance.
- If this file conflicts with `CLAUDE.md`, `CLAUDE.md` wins.

## Session Start (Required)

Before coding:

1. Read `docs/PLAN.md`.
2. Check `docs/plans/` for active/in-progress plan docs.
3. Skim `docs/POSTMORTEMS.md` for known pitfalls.
4. If deployment is involved, read `docs/DEPLOY.md`.

If a file is missing, note it and continue.

## Factory Workflow (If Present)

If this repo includes `project-factory/` and the task touches orchestrator state, delegated packets, or factory outputs:

1. Read `project-factory/ORCHESTRATOR_BOOTSTRAP.md`.
2. Read `project-factory/shared-contracts/OPERATING_MODEL.md`, `project-factory/shared-contracts/BOUNDARY_AND_NONCLAIMS.md`, `project-factory/shared-contracts/PROVENANCE_AND_STATUS.md`, and `project-factory/shared-contracts/QUALITY_GATES.md`.
3. Read `project-factory/meta/SESSION_STATUS.md`, `project-factory/meta/PHASE_LEDGER.md`, `project-factory/meta/EXECUTION_TIMELINE.md`, and `project-factory/meta/DECISION_LOG.md`.
4. If packet/run work is involved, read `project-factory/claude_handoff/RUN_OUTPUT_CONTRACT.md` and the relevant packet in `project-factory/claude_handoff/packets/`.
5. Default to the Orchestrator / control-plane role. Do not silently become the primary implementer unless the operator explicitly asks for direct coding.
6. Keep lane boundaries explicit (`discovery` vs `production`) and do not silently promote speculative content.
7. Keep factory continuity files in sync (`project-factory/ORCHESTRATOR_BOOTSTRAP.md`, `project-factory/meta/*`, checkpoints/manifests) so runs remain restartable.

## Planning and Execution

- For any non-trivial change (multi-file or behavior-changing), create/update a task plan in `docs/plans/YYYY-MM-DD-<short-task-name>.md` with:
  - `## Context`
  - `## Plan`
  - `## Execution Log`
  - `## Follow-ups`
- Keep the plan synchronized with work completed.
- Exception: single-file, single-line fixes may skip plan docs.
- Complete tasks end-to-end: plan -> implement -> check -> fix -> commit -> push.
- Ask before deploy and before merge to `main`.

## Guardrails

- Read files before editing them.
- Search for existing files/components before creating new ones.
- Keep diffs tight; avoid unrelated reformatting.
- Verify functions/APIs/imports exist before using them.
- Do not leave placeholder TODO stubs for required functionality.
- Do not add speculative abstractions not needed by the task.
- Follow all security defaults and dependency discipline in `CLAUDE.md`.
- Follow platform constraints in `CLAUDE.md` (AWS, Lambda, Unity, JUCE/audio-thread safety).

## Checks and Git

- Run fastest relevant checks after edits (typecheck, lint, tests, build/smoke when available).
- Fix failing checks before committing.
- Use feature branches for non-trivial work.
- Use clear imperative commit messages.
- Never force-push or rewrite history unless explicitly requested.
- Never commit secrets.

## Completion Summary

For non-trivial tasks, report:

- What changed
- Files modified
- Checks run and results
- Git actions taken
