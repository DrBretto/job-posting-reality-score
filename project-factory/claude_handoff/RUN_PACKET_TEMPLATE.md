# RUN_PACKET_TEMPLATE

Use this template for file-based, resumable delegated runs. Packets should be small enough to complete within bounded budgets.

## Standard Execution Profiles

- `FOUNDATION`: inventory, scope, source plan, baseline research, contracts, output mapping
- `FULL_BUILD`: staged run with research + planning + build + evaluation + synthesis
- `EPIC_STRESS_TEST`: multi-path generation + scored comparison + split-by-design option + nightly checkpoints

## Packet Template

```markdown
# Run Packet: <packet_id>

## Header
- packet_id: `<packet_id>`
- execution_profile: `FOUNDATION | FULL_BUILD | EPIC_STRESS_TEST`
- project_slug: `<project_slug>`
- phase_key: `<phase_key>`
- run_id: `<run_id>`
- run_root: `<path>`
- handoff_target: `<delegated executor / review surface / operator>`
- stage: `<stage_name>`
- resume_from: `<none | checkpoint path | file>`
- skip_completed: `true | false`
- budget_caps:
  - time_minutes: `<int>`
  - retries: `<int>`
  - source_cap: `<int or n/a>`
- checkpoint_policy:
  - on_stage_complete: `true`
  - on_budget_exhausted: `true`
  - near_context_limit: `true`
  - interval_hint_minutes: `<int | n/a>`
- recurring_mode:
  - enabled: `true | false`
  - autopilot_safe: `true | false`
  - resume_packet_chain: `<none | packet id list/path>`
  - convergence_stop_rule: `<plateau | decision_complete | diminishing_returns | packet-defined>`
- output_mapping:
  - `<logical_name>` -> `<exact file path>`

## Body
- objective:
- scope:
- active_roles:
- inputs:
- constraints:
- expected_outputs:
- acceptance_condition:
- stop_condition:
- success_criteria:
- failure_routing_if_blocked:

## Footer (to complete during/after run)
- completion_status: `not_started | in_progress | blocked | budget_exhausted | stage_complete | completed | stopped`
- outputs_emitted:
- next_stage:
- checkpoint_path:
- gate_recommendations:
- top_risks:
```

## Packet Design Rules

- Prefer staged packets over monolithic runs.
- Treat each meaningful work unit as a bounded packet, not a vague continuation.
- Include exact file paths for outputs.
- Keep resume semantics explicit (`resume_from`, `skip_completed`).
- State failure routing before execution starts.
- If ambition is high, branch first (multiple paths), then converge later.

## Nightly / Long-Cook Notes

- Use `recurring_mode.enabled: true` only when the stage is safe to checkpoint and resume.
- Require an explicit `convergence_stop_rule` for unattended recurring runs.
- Keep packet scope narrow enough that a checkpointed partial run is still useful.
