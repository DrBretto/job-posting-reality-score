# QUALITY_GATES

## Purpose

Define explicit gate outcomes and evidence requirements so the factory can stop, revise, or advance without ambiguity.

## Gate Outcomes (Required)

- `unlock`: stage passes; next stage may start
- `revise_<stage>`: stage must be revised before progression (example: `revise_research`)
- `stop`: terminate or pause path due to risk, weak support, or diminishing returns

All gate decisions must include evidence, risks, and recommended next action.

## Gate Evidence Requirements

A valid gate decision includes:

- stage and packet id
- outputs reviewed
- scoring summary (or explicit rationale if scoring is not applicable)
- key evidence / support quality notes
- top 1-3 risks
- recommended outcome (`unlock`, `revise_<stage>`, `stop`)

## Generic Scoring Rubric (0-5)

Use when evaluating creative/document/product/code outputs. Adapt weights per packet.

- `coherence`: internal consistency, structure, flow
- `force_impact`: usefulness, leverage, persuasion, practical effect
- `readability_usability`: clarity, operator/reader ergonomics
- `support_provenance`: evidence quality, citations, traceability
- `gimmick_overfit_risk` (reverse score): novelty inflation, complexity without value

## Default Unlock Guidance

- `unlock` if no critical failures and weighted average >= 3.5
- `revise_<stage>` if any critical failure exists or weighted average is between 2.0 and 3.49
- `stop` if weighted average < 2.0, evidence is missing for key claims, or diminishing returns threshold is reached

These defaults are starting points; packet-specific criteria may override them if documented.

## Long-Cook Convergence Stop Rules

For recurring/nightly runs, stop or converge when one of these is true:

- plateau in scores across successive comparable runs
- decision completeness reached (clear option selected with rationale)
- diminishing-return threshold hit relative to budget/time
