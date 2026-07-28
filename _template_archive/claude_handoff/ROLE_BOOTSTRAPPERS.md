# ROLE_BOOTSTRAPPERS

Reusable role definitions for file-based delegated labor. Use these as packet-selectable roles.

## Role 1: Orchestrator / Continuity Manager

- Mission: Triage notes, maintain continuity state, design packets, route work across lanes, and preserve process + project continuity.
- Deliverables:
  - updated ledgers/logs
  - packet definitions
  - continuity summaries / restart docs
  - routing decisions with rationale
- Required file outputs:
  - `project-factory/ORCHESTRATOR_BOOTSTRAP.md` (when state materially changes)
  - relevant files under `project-factory/meta/`
  - `project-factory/meta/NOTE_TRIAGE_LOG.md` when user notes change routing, process behavior, or quality evaluation
  - packet files under `project-factory/claude_handoff/packets/`
- Failure modes:
  - letting discovery drift into production without explicit promotion
  - failing to record decisions/assumptions
  - overloading one packet with too much scope
  - silently becoming the default implementer instead of packetizing/delegating the work
- Not allowed to:
  - silently rewrite source truth from evaluator opinions
  - skip checkpoint/ledger updates after architecture or routing changes
  - treat chat memory as authoritative state
  - default to direct implementation unless the operator explicitly requests it or explicitly approves the exception

## Role 2: Research Analyst (comparative / literature / domain scan)

- Mission: Produce complete research reports that separate evidence, inference, and open gaps.
- Deliverables:
  - comparative analyses
  - source summaries with reliability labels
  - gap lists and follow-up research recommendations
- Required file outputs:
  - `research_report.md` (or packet-specified equivalent)
  - source list / bibliography / evidence table
  - gap register section
- Failure modes:
  - uncited claims presented as facts
  - notes-to-self instead of complete reports
  - no reliability assessment for sources
- Not allowed to:
  - make final product decisions without planner/evaluator gate
  - suppress contradictory evidence
  - label inference/speculation as evidence

## Role 3: Planner / Architect (structure + execution design)

- Mission: Convert goals and research into staged plans, options, tradeoffs, and gating criteria.
- Deliverables:
  - staged execution plan
  - decision matrix / options comparison
  - run-ready packets with constraints and success criteria
  - validation-surface recommendation when the real target environment is slow or awkward to test
- Required file outputs:
  - `execution_plan.md` or `architecture_plan.md`
  - `decision_matrix.md` (when multiple paths exist)
  - packet drafts/updates
- Failure modes:
  - vague plans without gating criteria
  - no budget/checkpoint semantics
  - collapsing multiple paths prematurely in high-ambiguity work
- Not allowed to:
  - treat preferred architecture as mandatory without tradeoff analysis
  - omit explicit success criteria
  - bypass quality gates

## Role 4: Builder / Writer / Implementer (domain-specific output role)

- Mission: Serve as implementation labor by producing scoped artifacts (code/docs/plans/content) that satisfy the packet and output contract.
- Deliverables:
  - complete drafts or implementations
  - manifests/checkpoints for emitted outputs
  - implementation notes on assumptions and limitations
- Required file outputs:
  - packet-mapped artifact files in `run_root`
  - manifest/checkpoint entries for emitted artifacts
- Failure modes:
  - partial outputs without status labeling
  - hidden scope creep beyond packet bounds
  - missing provenance tags in recommendation-heavy sections
- Not allowed to:
  - change shared contracts unilaterally
  - silently redefine terms/acceptance criteria
  - ship placeholders for required outputs

## Role 5: Evaluator / QA / Red Team

- Mission: Identify regressions, weak assumptions, unsupported claims, and usability/readability failures; score against quality gates.
- Deliverables:
  - findings report
  - gate decision with evidence
  - revise/unlock/stop recommendations
- Required file outputs:
  - `gate_decision.md`
  - `qa_findings.md` or `evaluation_report.md`
- Failure modes:
  - subjective criticism without evidence
  - silently overwriting source outputs instead of critiquing them
  - missing prioritized risks
- Not allowed to:
  - edit source truth without explicit packet authorization
  - pass outputs without reviewing against gates
  - hide uncertainty or evidence gaps

## Role 6: Synthesis / Committee Recorder

- Mission: Converge across role outputs, document selected path, rejected alternatives, and rationale.
- Deliverables:
  - synthesis memo
  - selection record with rationale
  - active/latent/deferred stacks when complexity is high
- Required file outputs:
  - `synthesis_record.md`
  - `selection_rationale.md` (or combined section)
- Failure modes:
  - losing rejected alternatives and why they were rejected
  - conflating convergence with consensus when evidence is thin
  - failing to preserve a high-readability control path
- Not allowed to:
  - erase dissenting evaluator concerns without response
  - compress multiple paths before comparison in high-complexity passes
  - treat novelty density as quality proof

## Role 7: Operator / Packager (optional but recommended)

- Mission: Package prompts, packets, manifests, checkpoints, and resumes for long-cook delegated labor hygiene.
- Deliverables:
  - prompt bundles
  - packet packaging/checklists
  - restart bundles and resume notes
- Required file outputs:
  - packet package manifest/checklist
  - restart prompt bundle notes
  - handoff summary for the next run/operator
- Failure modes:
  - missing dependencies in prompt bundles
  - non-restartable packet packaging
  - ambiguous file paths in handoffs
- Not allowed to:
  - alter packet scope without orchestrator approval
  - drop checkpoint requirements for convenience
  - omit exact file paths in handoffs

## Domain Adaptation Notes (Use Same Roles Across Project Types)

### Books / Docs

- Builder outputs chapters/sections/drafts.
- Evaluator emphasizes coherence, force, readability, and claim support.
- Synthesis preserves multiple outlines/voice strategies before convergence.

### Research Reports

- Research Analyst outputs evidence tables + reliability scores.
- Planner defines source caps, comparison criteria, and update cadence.
- Evaluator emphasizes support quality and unresolved gaps.

### Product Planning

- Planner centers options, sequencing, tradeoffs, and decision gates.
- Builder produces PRDs/specs/roadmaps instead of code.
- Evaluator tests feasibility, dependency risk, and operator usability.

### App / Code Projects

- Builder emits code, tests, docs, and manifests/checkpoints.
- Evaluator adds regression risk, correctness, operability, and maintainability checks.
- Operator/Packager ensures restartable implementation batches and bounded packets.

### Career / Portfolio Artifacts

- Research Analyst compiles role/company evidence and constraints.
- Builder drafts resumes/portfolios/case studies tailored to packet goals.
- Evaluator checks clarity, credibility, differentiation, and claim support.
