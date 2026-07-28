# TERM_LOCKS

## Purpose

Optional term definitions to keep recurring role outputs consistent.

## Locked Terms

| term | definition | scope | change_rule |
| --- | --- | --- | --- |
| `lane` | A bounded workflow track (`discovery`, `production`, `shared-contracts`, optional project lane) with explicit promotion rules. | factory-wide | update via `meta/DECISION_LOG.md` |
| `control plane` | The Orchestrator layer that manages state, sequencing, packetization, continuity, and review/validation surfaces. | factory-wide | update via `shared-contracts/OPERATING_MODEL.md` + decision log |
| `packet` | File-based run instruction unit with header/body/footer, budgets, and resume semantics. | factory-wide | update via `claude_handoff/RUN_PACKET_TEMPLATE.md` + decision log |
| `gate` | Explicit stage outcome (`unlock`, `revise_<stage>`, `stop`) backed by evidence. | factory-wide | update via `shared-contracts/QUALITY_GATES.md` |
