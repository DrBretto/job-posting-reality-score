# BOUNDARY_AND_NONCLAIMS

## Purpose

Define lane boundaries and anti-drift rules so speculative exploration does not silently become delivery-bound output.

## Lane Boundary Rules

1. `discovery` and `production` are separate lanes.
2. Content may move from `discovery` to `production` only via an explicit packet or decision entry.
3. `shared-contracts` files are process infrastructure; update them only when the process changes, not for one-off tasks.
4. `template-ops` changes (automation/scripts) follow the same provenance and gate requirements as `production` when user-facing behavior changes.

## Promotion Protocol (Discovery -> Production)

Promotion requires all of the following:

- A packet or decision record naming the promoted item(s)
- Provenance labels retained (`evidence`, `inference`, `speculation`)
- Any unsupported claims rewritten as hypotheses or removed
- A gate decision (`unlock`, `revise_<stage>`, or `stop`) recorded with reasons

## Non-Claims (Default Posture)

Unless explicitly supported and labeled, the Orchestrator and delegated labor must not claim:

- factual correctness of uncited statements
- market/user behavior certainty
- performance improvements from unmeasured changes
- completeness of research when source budgets were capped
- production readiness of drafts that have not passed gates

## Notes Posture (Anti-Bottleneck)

Treat user notes as direction vectors by default:

- `north_star`: desired effect/outcome
- `candidate_move`: tactic/device to test
- `anti_pattern`: what to avoid

Notes are not implementation requirements unless explicitly promoted into a packet, contract, or decision.
