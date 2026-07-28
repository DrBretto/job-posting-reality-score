# EXECUTION_TIMELINE

Use this file as the roadmap / sequencing surface for the factory. It is lower priority than completed outputs and current status trackers, but higher priority than bootstrap summaries.

## Current Sequence

1. `completed` - scaffold the generic factory surfaces under `project-factory/`
2. `completed` - harden the operating model so the default role is the Orchestrator / control plane
3. `staged` - execute the first bounded `FOUNDATION` packet to validate the packet/handoff workflow on this repo
4. `planned` - refine the template only if the first `FOUNDATION` run exposes gaps worth codifying

## Timeline Entries

| date | state | event | artifact_paths | next_unlocked_task |
| --- | --- | --- | --- | --- |
| 2026-02-26 | `completed` | Seeded the generic factory scaffold, starter packet, and output roots. | `project-factory/ORCHESTRATOR_BOOTSTRAP.md`, `project-factory/claude_handoff/packets/FOUNDATION_kickoff_template-factory-bootstrap.md` | Validate the scaffold with a real packet run |
| 2026-03-14 | `completed` | Hardened the workflow around control-plane boundaries, state resolution, continuity surfaces, and packet discipline. | `project-factory/shared-contracts/OPERATING_MODEL.md`, `project-factory/meta/SESSION_STATUS.md`, `project-factory/meta/PHASE_LEDGER.md` | Run the staged `FOUNDATION` packet |
