# REPORT_TEMPLATES

Reusable report skeletons for delegated-labor runs. Copy into the run root and fill completely.

## Research Report Template

```markdown
# Research Report: <topic>

## Scope
- Objective:
- Packet ID:
- Run ID:
- Source cap / time cap:

## Findings
- [evidence] ...
- [inference] ...
- [speculation] ...

## Source Reliability Table
| source | type | reliability | notes |
| --- | --- | --- | --- |

## Gaps / Unknowns
- ...

## Recommended Next Moves
- [inference] ...
```

## Planner / Architect Decision Matrix Template

```markdown
# Decision Matrix: <decision>

## Options
| option | description | benefits | risks | cost | confidence |
| --- | --- | --- | --- | --- | --- |

## Gating Criteria
- ...

## Recommendation
- [inference] ...
```

## Evaluator Gate Decision Template

```markdown
# Gate Decision

- Packet ID:
- Run ID:
- Stage:
- Outcome: unlock | revise_<stage> | stop

## Evidence Reviewed
- ...

## Scores (0-5)
- coherence:
- force_impact:
- readability_usability:
- support_provenance:
- gimmick_overfit_risk (reverse):

## Findings
- ...

## Top Risks
- ...

## Recommendation
- ...
```

## Synthesis Record Template

```markdown
# Synthesis Record

## Inputs Reviewed
- ...

## Selected Path
- ...

## Rejected Alternatives (with reasons)
- ...

## Active / Latent / Deferred Stack (if applicable)
- active:
- latent:
- deferred:
```

## Operator / Packager Handoff Summary Template

```markdown
# Handoff Summary

## Packet Bundle Contents
- ...

## Preconditions Checked
- ...

## Resume Steps
1. ...
2. ...

## Known Risks / Missing Inputs
- ...
```

## Note Triage Record Template (append to metadata logs)

```markdown
## <date> - Note Triage

- summary:
- triage: `confirmed | partially_confirmed | subjective | stale`
- actions_taken:
- evidence_artifacts:
- outcome_assessment:
- process_docs_patched: `none | list of files`
```
