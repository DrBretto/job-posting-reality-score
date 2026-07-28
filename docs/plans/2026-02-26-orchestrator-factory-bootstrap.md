# 2026-02-26 - Orchestrator Factory Workflow Bootstrap

## Context

Add a generic file-based orchestrator + delegated-labor factory workflow scaffold to this template repository so future projects can inherit the process pattern without importing domain-specific content. Align `CLAUDE.md`, `.cursorrules`, and `AGENTS.md` so agents know when and how to use the factory.

## Plan

- [x] Inspect repo surface area and infer default lanes/artifact types for this template.
- [x] Scaffold `project-factory/` continuity, shared contracts, metadata logs, handoff system, and output architecture.
- [x] Create reusable role bootstrappers, run packet templates, and a runnable `FOUNDATION` kickoff packet.
- [x] Update `ORCHESTRATOR_BOOTSTRAP.md` with exact current state and assumptions.
- [x] Patch `CLAUDE.md`, `.cursorrules`, and `AGENTS.md` to include orchestrator factory usage guidance.
- [x] Run fast checks / sanity validation and summarize results.

## Execution Log

- Initialized plan doc and created feature branch `codex/orchestrator-factory-bootstrap`.
- Confirmed repo is a template project with docs/scripts/skills artifacts and pre-existing local changes unrelated to this task; changes will stay tightly scoped.
- Inferred default lanes as `discovery`, `production`, `shared-contracts`, plus template-specific `template-ops` based on repo contents (`docs`, `scripts`, `codex-skills`, rule files).
- Scaffolded `project-factory/` with continuity docs, shared contracts, metadata ledgers, delegated-labor handoff templates, output registry/roots, and a seeded `FOUNDATION` kickoff packet.
- Added optional companion `project-factory/ORCHESTRATOR_FACTORY_RESTART_PROMPT_TEMPLATE.md` for quick downstream reuse.
- Added `project-factory/meta/NOTE_TRIAGE_LOG.md` plus note-triage template/support so midstream user notes are logged with triage/actions/evidence/outcomes.
- Extended delegated-labor templates with recurring/nightly run support fields (`recurring_mode`, convergence stop rule, autopilot safety expectations).
- Updated `CLAUDE.md`, `.cursorrules`, and `AGENTS.md` with factory-mode guidance (bootstrap/contracts first, lane boundaries, resumable packet hygiene).
- Ran targeted sanity checks:
  - `git diff --check` on touched files (pass)
  - `jq` validation on seeded `run_manifest.json` (pass)
  - `rg` scan for `TODO|TBD` in new files (only instructional mention in contract doc)

## Follow-ups

- Consider adding a zero-decision variant prompt that hardcodes preferred factory folder names if the generic version sees frequent use.
- Consider a helper script to create the first factory packet/phase in new repos automatically from these templates.
