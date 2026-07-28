# Project Plan

## Goals

1. Build a useful daily radar for selected public job boards.
2. Preserve immutable posting history so changes and reposts can be proven from evidence.
3. Rank attention using transparent fit and activity signals, without pretending to know whether a
   listing is genuine.
4. Rebuild Brett's working recall of AWS by constructing P0-P8 manually in the console.
5. Keep the starter system below `$5/month` under expected use.

## Constraints

- One AWS account and one region: `us-east-1`.
- Public ATS/company-career sources only; respect source terms and rate limits.
- No automated application submission or personal-contact harvesting.
- No NAT Gateway, EC2, RDS, OpenSearch, EKS, paid Glue, Kinesis, provisioned Lambda concurrency, or
  always-on compute in starter scope.
- S3 is the source of truth; versioning remains off.
- Bedrock is off until P8 and may be omitted entirely.
- AWS resources are created manually by Brett through P8. AI may create local code, policies, tests,
  fixtures, and exact console worksheets.
- Never put account IDs, ARNs tied to the private account, access keys, emails, or secrets in Git.

## Architecture

Daily collection:

`EventBridge Scheduler -> enumerate Lambda -> RUN_OPEN manifest -> SQS + DLQ -> collector Lambda -> S3`

Daily interpretation:

`EventBridge Scheduler -> Step Functions Standard -> differ/report Lambdas -> S3 -> SES`

Storage prefixes are separated by ownership. In particular, the collector writes status records but
the differ owns published current state. Raw snapshots use unique write-once keys and cannot be
deleted by execution roles.

## Milestones

| Phase | Outcome | Status |
|---|---|---|
| P0 | Region, identity, cost, and access guardrails | AI KIT READY / MANUAL WORK NOT STARTED |
| P1 | Private S3 record substrate | NOT STARTED |
| P2 | One connector and collector Lambda | NOT STARTED |
| P3 | SQS, DLQ, retries, and redrive recall lab | NOT STARTED |
| P4 | EventBridge Scheduler and explicit enumerate step | NOT STARTED |
| P5 | Multi-source fan-out and complete-run manifests | NOT STARTED |
| P6 | Evidence-backed diff engine and mass-drop protection | NOT STARTED |
| P7 | Daily report, SES delivery, monitoring, and runbook | NOT STARTED |
| P8 | Optional template-constrained Bedrock narration | NOT STARTED |
| P9 | Reconstruct the hand-built stack as IaC | NOT STARTED |
| P10 | Athena/Parquet historical analysis | NOT STARTED |

V1 is P0-P7. P8 is optional. P9 and P10 begin only after V1 works.

## Required Conditions

The committee's five major conditions are part of the build, not optional follow-up:

1. Add an explicit enumerate Lambda and `RUN_OPEN` manifest backbone before P5.
2. Permit LLM narration only through a constrained evidence template before P8.
3. Add cumulative and per-segment mass-drop guards before P6 is complete.
4. Separate collector `status/` ownership from differ `current/` ownership before P2 IAM is final.
5. Enforce finite log retention and a supported cost lockdown at every relevant phase.

Condition 5 is refined by
[ADR 0001](ADR/0001-supported-budget-enforcement.md): AWS Budgets cannot directly disable an
EventBridge schedule. At P4, the `$10` Budget Action will instead attach a deny policy to the
scheduler invocation role, preventing new Lambda, Step Functions, and SQS work.

## Current Work

The active execution plan is
[P0 account guardrails](plans/2026-07-28-p0-account-guardrails.md).
Do not begin P1 until every P0 done-gate item is checked and Brett can answer the recall prompt
without notes.

## Non-Goals

- Calling recycled postings fraudulent or fake.
- Scraping arbitrary websites behind authentication or anti-bot controls.
- Building a commercial dashboard before the personal daily radar is useful.
- Using AI where deterministic collection, normalization, or comparison is sufficient.
- Automating away the AWS console work that this project exists to refresh.
