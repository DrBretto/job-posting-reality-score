# Project Plan

## Goals

1. Produce a useful daily shortlist of current roles for Brett.
2. Preserve public posting history so changes, disappearances, and repost patterns are evidence-backed.
3. Rank attention transparently around Brett's demonstrated agentic AI, applied AI, backend/platform,
   AWS, automation, and developer-tooling experience.
4. Keep AWS architecture skills fresh through inspectable serverless components and explicit manual
   checkpoints.
5. Keep expected operating cost below `$5/month` without always-on infrastructure.

## Constraints

- One AWS account and one region: `us-east-1`.
- Public ATS/company-career sources only; no authenticated scraping.
- No automated applications or personal-contact harvesting.
- No NAT Gateway, EC2, RDS, OpenSearch, EKS, Kinesis, paid Glue, or provisioned concurrency.
- S3 is the evidence store and versioning remains off.
- Bedrock is optional and remains disabled; no LLM sets scores or authoritative facts.
- AWS deployment, SSM changes, destructive actions, and merges to `main` require operator approval.
- Private account identifiers, ARNs, access keys, emails, and secrets never enter Git.

## Architecture

Daily collection:

`EventBridge Scheduler -> enumerate Lambda -> RUN_OPEN manifest -> SQS/DLQ -> collector -> S3`

Daily interpretation:

`EventBridge Scheduler -> Step Functions -> differ -> current/events -> report -> S3 + SES`

The collector owns `raw/`, `normalized/`, and `status/`. The differ alone owns `current/` and
`events/`. Failed or partial fetches freeze source state and cannot emit disappearance events.

## Milestones

| Phase | Outcome | Status |
|---|---|---|
| P0 | Region, identity, and account guardrails | COMPLETE |
| P1 | Private S3 evidence substrate | COMPLETE |
| P2 | Public ATS connector and collector Lambda | COMPLETE |
| P3 | SQS, DLQ, retries, and redrive lab | COMPLETE |
| P4 | Scheduled collection and enumerate step | COMPLETE |
| P5 | Multi-source fan-out and complete-run manifest | COMPLETE |
| P6 | Evidence-backed differ and mass-drop protection | COMPLETE |
| P7 | Daily report, SES path, monitoring, and runbook | DEPLOYED AND VERIFIED |
| P8 | Optional constrained Bedrock narration | DEFERRED / OFF |
| P9 | SAM infrastructure reconstruction | COMPLETE AND DEPLOYED |
| P10 | Parquet/Athena historical analysis | DEFERRED UNTIL HISTORY JUSTIFIES IT |

## Current Work

The active plan is
[2026-08-02 real-job radar](plans/2026-08-02-real-job-radar.md).

The usefulness pass is deployed. Its controlled run completed 15/15 targets and produced a ranked
519-job report with 41 useful matches. SES delivery and same-day duplicate suppression are verified.

## Next Product Steps

1. Let history accumulate while using the digest for daily applications.
2. Record application outcomes in a small explicit schema before changing score weights from
   outcomes.
3. Add a target-board health review and prune companies that stop producing relevant roles.
4. Consider Parquet/Athena only when accumulated history answers a concrete question better than the
   existing JSON records.

## Non-Goals

- Inferring deceptive intent from posting behavior.
- Broad prestige-company monitoring without current role relevance.
- A commercial dashboard before the personal digest proves useful.
- LLM-based scoring where deterministic evidence is sufficient.
- Replacing human review of a posting or automating submission.
