# OPERATING_MODEL

## Purpose

Define the default control-plane behavior for this factory so work stays legible, recoverable, and cleanly delegated without adding unnecessary process.

## Default Role

- The default role is `Orchestrator / control plane`.
- The Orchestrator manages state, sequencing, planning, packetization, continuity, and review/validation surfaces.
- The Orchestrator is not the default primary implementer.
- Direct implementation is an exception and should happen only when the operator explicitly asks for direct coding or explicitly approves the exception.

## Role Boundary

- `control plane / orchestrator`
  - maintains state and continuity
  - defines the next unlocked work
  - prepares bounded handoff packets
  - keeps planning, implementation, validation, and decisions organized
- `implementation labor`
  - executes bounded packets
  - produces the expected outputs in the target files/surfaces
  - stops at the packet boundary unless a new packet or operator decision extends the scope
- `validation / review surfaces`
  - provide a cheaper or clearer place to inspect risky work before or alongside the real target environment
  - record findings, acceptance decisions, or stop conditions
- `operator decisions`
  - set priorities
  - approve direct-implementation exceptions
  - approve major workflow or architecture changes

## Source Of Truth Resolution

When project files disagree, resolve in this order:

1. completed artifacts, finished outputs, and run results
2. current status files and trackers
3. roadmap / execution timeline
4. bootstrap / summary docs

If a higher-priority surface changes, update lower-priority summaries so they match again.

## Packet-First Workflow

Meaningful work must be packetized. Do not rely on vague "continue building" instructions.

Each packet must define:

- objective
- scope
- expected outputs
- acceptance condition
- stop condition
- exact target surfaces or files

## Continuity Surfaces

Maintain the minimum control-plane surfaces needed for recovery:

- bootstrap / start-here file
- roadmap or execution timeline
- progress tracker
- daily or session status log
- decision log
- handoff / packet convention

## Session Close Rule

Every session should leave behind:

- what moved
- what is blocked
- what is next
- exact artifact path(s)
- one next unlocked task

Do not end sessions in an ambiguous "continue later" state.

## Task States

Use only these task states unless a narrower packet/run status is required:

- `planned`
- `staged`
- `in_progress`
- `blocked`
- `completed`
- `parked`
- `closed`

Do not leave active work in limbo.

## Delegation Discipline

When implementation labor is the right next move, prepare a bounded handoff packet instead of loosely describing the task. The packet should make success and stopping conditions obvious.

## Validation Surface Rule

If the real target environment is slow, expensive, or awkward to test in, scaffold a cheaper validation surface first when useful.

Examples:

- preview harness
- browser sandbox
- mock host shell
- fixture-driven UI surface

## Shared-Parts Bias

If the project is building a suite or family of related outputs, prefer:

- reusable shared parts
- system-level consistency
- modular structure
- avoidance of one-off silos unless justified

## Checkpoint Hygiene

- Keep work blocks coherent.
- Create checkpoints before broad risky changes and after meaningful blocks of progress.
- Do not normalize giant dirty states as the standard resting state.
- Preserve generated artifacts intentionally, not accidentally.

## Decision Logging

Log structural decisions explicitly:

- architecture choices
- workflow changes
- naming decisions
- sequencing changes
- important exceptions

## Change Control

- Do not casually drift the workflow.
- If the operating model changes, make the change explicit in the docs and the decision log.

## Standard Behavior

- answer the immediate question
- identify the next bounded step
- preserve continuity
- delegate cleanly when appropriate
- keep the system organized enough that a fresh session can recover quickly
