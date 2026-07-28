# NOTE_TRIAGE_LOG

Append durable signals from user notes dropped midstream. Do not convert every note into a permanent rule.

## Usage Rules

- Triage each note as `confirmed`, `partially_confirmed`, `subjective`, or `stale`.
- Record actions taken and evidence artifacts.
- Patch role docs/templates/contracts only when the note changes process behavior or quality requirements.
- Preserve outcome assessment so future runs can tell whether the note improved results.

## Entries

### 2026-02-26 - Seed Bootstrap Entry

- summary: Initialized note triage log as part of generic orchestrator factory scaffold.
- triage: `confirmed`
- actions_taken: Added a dedicated metadata log for note triage and wired it into resume instructions.
- evidence_artifacts: `project-factory/meta/NOTE_TRIAGE_LOG.md`, `project-factory/ORCHESTRATOR_BOOTSTRAP.md`
- outcome_assessment: Improves continuity for midstream notes and prevents accidental rule bloat.
- process_docs_patched: `project-factory/ORCHESTRATOR_BOOTSTRAP.md`

### 2026-03-14 - Canonical Operating Model Simplification

- summary: Replaced a more specific hardening draft with a simpler canonical operating model centered on control-plane behavior, packet discipline, and lightweight continuity.
- triage: `confirmed`
- actions_taken: Added `OPERATING_MODEL.md`, `EXECUTION_TIMELINE.md`, `SESSION_STATUS.md`, and tightened packet/rule docs to match the simplified canon.
- evidence_artifacts: `project-factory/shared-contracts/OPERATING_MODEL.md`, `project-factory/meta/EXECUTION_TIMELINE.md`, `project-factory/meta/SESSION_STATUS.md`, `project-factory/claude_handoff/RUN_PACKET_TEMPLATE.md`
- outcome_assessment: The factory remains generic while gaining a clearer default role and better recovery surfaces.
- process_docs_patched: `project-factory/ORCHESTRATOR_BOOTSTRAP.md`, `project-factory/shared-contracts/PROVENANCE_AND_STATUS.md`, `CLAUDE.md`, `.cursorrules`, `AGENTS.md`
