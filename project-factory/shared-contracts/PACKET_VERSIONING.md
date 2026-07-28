# PACKET_VERSIONING

## Purpose

Standardize packet naming, versioning, and handoff conventions for all repos using this template's factory workflow.

## Naming Convention

All packets, queues, and structured handoff documents follow this pattern:

```
<PRODUCT>-<LAYER>-<TYPE><SEQ>-<slug>-v<VER>.md
```

| Field | Description | Example |
|-------|-------------|---------|
| PRODUCT | Short product/domain code, uppercase | `GN`, `MW`, `SUITE` |
| LAYER | Functional layer, uppercase | `L1` (spec/strategy), `L2` (implementation), `RS` (research) |
| TYPE | Document type code | `P` (packet), `Q` (queue) |
| SEQ | Zero-padded 2-digit sequence | `01`, `02` |
| slug | Kebab-case descriptor | `spec-sprint`, `validation-kickoff` |
| VER | Zero-padded 2-digit version | `v01`, `v02` |

Example: `GN-L1-P01-spec-sprint-v01.md`

## Queue Files

Queue files group multiple related packets for coordinated execution:

```
<SCOPE>-<LAYER>-Q<SEQ>-<slug>-v<VER>.md
```

Example: `SUITE-RS-Q01-parallel-research-kickoffs-v01.md`

## Directory Structure

- Packets: `project-factory/claude_handoff/packets/<product>/`
- Queues: `project-factory/claude_handoff/queues/<scope>/`

## Versioning Rules

- `v01` is the first version of any packet.
- If a packet is revised, create `v02` at the same path. Do not modify `v01` — archive or rename it.
- If a packet succeeds and the next step is known, create the successor as `P<SEQ+1>` (a new packet, not a version bump).
- Version increments require a corresponding update in `PACKET_REGISTRY.tsv`.

## Packet Required Fields

Every packet must include:

| Field | Description |
|-------|-------------|
| objective | What this packet accomplishes |
| scope | What is in and what is out |
| source | What prior output or decision this depends on |
| acceptance | How to know the work is done |
| stop | When to halt even if not complete |
| next | What happens after completion |

## Registry Files

- `project-factory/claude_handoff/PACKET_REGISTRY.tsv` — tracks all packets
- `project-factory/claude_handoff/QUEUE_REGISTRY.tsv` — tracks all queues
