# RUN_OUTPUT_CONTRACT

## Purpose

Define the minimum output set and status semantics for delegated-labor runs.

## Required Per-Run Outputs (Default)

Each run root should contain or produce equivalents of:

- `run_manifest.json` or `run_manifest.md`
  - packet id, run id, stage, status, timestamps, active roles, outputs emitted
- `checkpoint.md`
  - current state, completed items, remaining work, blockers, resume steps
- `gate_decision.md` (for stages that require evaluation)
  - outcome (`unlock`, `revise_<stage>`, `stop`) with evidence and risks
- role-specific reports/artifacts required by the packet

If a packet overrides filenames, it must still provide the same information.

## Output Quality Requirements

- Files must be complete and readable without chat context.
- Claims and recommendations must include provenance labels (`evidence`, `inference`, `speculation`, `operator_preference`).
- Explicitly state missing evidence, capped source budgets, and assumptions.
- Do not leave placeholder TODO stubs for required outputs.

## Manifest Fields (Minimum)

- `packet_id`
- `execution_profile`
- `project_slug`
- `phase_key`
- `run_id`
- `stage`
- `handoff_target`
- `status`
- `active_roles`
- `inputs_used`
- `outputs_emitted`
- `budget_caps`
- `acceptance_condition`
- `stop_condition`
- `checkpoint_path`
- `next_stage`
- `top_risks`

## Checkpoint Requirements (Minimum)

- What moved
- What is blocked / uncertain
- What is next
- Exact artifact paths emitted or updated and their status
- One next unlocked task
- Resume command or resume steps
