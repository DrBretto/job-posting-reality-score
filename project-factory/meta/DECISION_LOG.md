# DECISION_LOG

Record process and path decisions with enough detail to resume without chat history.

## D-001 - Adopt `project-factory/` as default factory root

- Date: 2026-02-26
- Status: accepted
- Context: Generic orchestrator factory bootstrap requested for the template repo.
- Decision: Use `project-factory/` as the default root with `meta/`, `claude_handoff/`, and `outputs/` subdirectories.
- Consequences: New repos can start with zero-decision defaults and rename later if needed.

## D-002 - Seed template-specific optional lane `template-ops`

- Date: 2026-02-26
- Status: accepted
- Context: This repo is a reusable template with scripts and bootstrap assets beyond pure documents.
- Decision: Add optional lane `template-ops` to the standard lane set in addition to `discovery`, `production`, and `shared-contracts`.
- Consequences: Template maintenance work can remain explicit without overloading `production`.

## D-003 - Seed two canonical artifact roots in outputs registry

- Date: 2026-02-26
- Status: accepted
- Context: The factory scaffold should demonstrate output architecture, status docs, and run directories immediately.
- Decision: Seed `factory-system-bootstrap` and `template-ops-playbook` roots under `project-factory/outputs/` with starter run folders.
- Consequences: Downstream projects get a concrete pattern to copy and adapt.

## D-004 - Default the factory role to Orchestrator / control plane

- Date: 2026-03-14
- Status: accepted
- Context: The template needs a clearer default that preserves sequencing, delegation, and recovery.
- Decision: Treat the Orchestrator as the default control plane rather than the default primary implementer. Direct coding is an explicit exception, not the silent default.
- Consequences: Meaningful implementation work should usually move through bounded packets instead of vague continuation.

## D-005 - Adopt explicit state resolution and continuity surfaces

- Date: 2026-03-14
- Status: accepted
- Context: Recovery after context loss needs a clear answer for what to trust first.
- Decision: Resolve conflicting files in this order: completed artifacts/run results, current status trackers, roadmap/timeline, then bootstrap/summary docs. Maintain `SESSION_STATUS.md`, `PHASE_LEDGER.md`, `EXECUTION_TIMELINE.md`, and this decision log as the minimum control-plane recovery surfaces.
- Consequences: Lower-priority summaries must be updated when higher-priority state changes.

## D-006 - Standardize task states and packet fields

- Date: 2026-03-14
- Status: accepted
- Context: Work drift and ambiguous "continue later" states make delegation and recovery harder than necessary.
- Decision: Use the standard task states `planned`, `staged`, `in_progress`, `blocked`, `completed`, `parked`, and `closed`. Require packets to include objective, scope, expected outputs, acceptance condition, stop condition, and exact target surfaces/files.
- Consequences: Status trackers and handoff packets become more legible and easier to resume.
