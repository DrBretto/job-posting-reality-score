# 2026-03-14 - Orchestrator Workflow Hardening

## Context

Harden the generic factory workflow in this template so the default role is an explicit Orchestrator / control plane rather than an implicit primary implementer. Make packet-first delegated labor, state resolution order, task states, session continuity, validation-surface policy, and change-control rules explicit enough to become a reusable solo-template default.

## Plan

- [x] Audit current factory/bootstrap/rule docs against the canonical operating-model notes.
- [x] Add a shared operating-model contract that defines control-plane boundaries, state resolution hierarchy, task states, packet-first execution, validation-surface rules, checkpoint hygiene, and change control.
- [x] Add or tighten the minimal control-plane surfaces: execution timeline, session status, progress tracker, and decision log.
- [x] Update existing bootstrap/packet/meta docs to point at the new rules and remove ambiguity about orchestrator vs implementation labor.
- [x] Update root rule files so future agents default to orchestrator behavior unless the operator explicitly requests direct coding.
- [x] Run sanity checks and summarize new rules, replaced ambiguities, preserved exceptions, and the next unlocked step.

## Execution Log

- Started hardening pass from the existing `project-factory/` scaffold rather than renaming or replacing historical files.
- Replaced a more specific draft hardening spec with the simpler canonical operating-model instructions from the operator.
- Added `OPERATING_MODEL.md`, `EXECUTION_TIMELINE.md`, and `SESSION_STATUS.md` as the minimum new control-plane surfaces.
- Tightened bootstrap, phase ledger, and decision log surfaces around control-plane behavior and recovery.
- Tightened packet templates, delegated-executor prompts, seeded run metadata, and root rule files so the new operating model is operational rather than advisory.
- Verification:
  - `git diff --check` on touched files (pass)
  - `jq` validation of the seeded `run_manifest.json` handoff/acceptance/stop fields (pass)
  - `rg` scan for stale status labels such as `ready_to_run`, `seeded_pending_first_run`, and `seeded_idle` under `project-factory/` (no matches)

## Follow-ups

- Consider adding a tiny packet-creation helper later if repeated projects need faster kickoff from the hardened model.
