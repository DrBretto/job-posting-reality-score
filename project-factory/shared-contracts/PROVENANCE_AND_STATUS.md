# PROVENANCE_AND_STATUS

## Purpose

Standardize claim labeling, source lineage, and status tags for all factory outputs.

## Claim Labels (Required)

Use one primary label for claims and recommendations:

- `evidence`: directly supported by a cited source, measurement, or repository artifact
- `inference`: reasoned conclusion derived from evidence
- `speculation`: hypothesis, idea, or projection requiring validation
- `operator_preference`: stylistic or strategic preference chosen by the operator

When a section mixes labels, split it or annotate line-by-line/bullet-by-bullet.

## Source Lineage (Minimum)

For major outputs, preserve lineage to inputs:

- packet id / run id
- source files, notes, or external references used
- date/time or version when captured (if relevant)
- reliability assessment (`high`, `medium`, `low`, `unknown`)

## Artifact Status Tags

Use these status tags in manifests, registries, and headers where applicable:

- `draft`
- `checkpointed`
- `under_review`
- `approved_for_promotion`
- `superseded`
- `archived`

## Run Status Tags

Use these run-level statuses in packet footers and run manifests:

- `not_started`
- `in_progress`
- `blocked`
- `budget_exhausted`
- `stage_complete`
- `completed`
- `stopped`

## Task State Tags

Use these task / phase states in trackers and status files:

- `planned`
- `staged`
- `in_progress`
- `blocked`
- `completed`
- `parked`
- `closed`

Do not invent custom limbo states when one of the standard task states fits.

## Reliability Guidance

- Mark uncited summaries as `inference` or `speculation`, not `evidence`.
- If evidence is mixed quality, keep the strongest and weakest sources visible.
- If a source cap or time cap was hit, state that in the output header and gate recommendation.
