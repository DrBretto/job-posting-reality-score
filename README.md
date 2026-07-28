# Job Posting Reality Score

Job Posting Reality Score (JPRS) is a low-cost AWS project that preserves public job-posting history
and reports what actually changed. Its first purpose is practical: improve Brett's job search while
rebuilding hands-on fluency with the AWS services that commonly appear in engineering interviews.

The first useful product is:

> Save selected public job postings every day and tell me what changed.

The longer-term product uses that history to identify fresh openings, repeated reposts, requirement
changes, hiring momentum, and the posting characteristics associated with useful application outcomes.
It reports observed behavior and evidence; it does not label jobs or companies "real" or "fake."

## Current State

- Committee roadmap: complete and copied into this repository.
- Current phase: **P0 — account guardrails**.
- AWS resources created by this repository so far: **none**.
- Operating mode: Brett builds AWS resources manually in the console; AI prepares code, policies,
  tests, checklists, and explanations for inspection.
- Region: `us-east-1`.
- V1: P0 through P7.

Start here:

1. Read the [P0 account preflight](docs/operator/phase-0/P0_ACCOUNT_PREFLIGHT.md).
2. Follow the [P0 console worksheet](docs/operator/phase-0/P0_CONSOLE_WORKSHEET.md).
3. Answer the recall prompt in your own words.
4. Run the shared verification before beginning P1.

## Architecture

The planned V1 flow is:

`EventBridge Scheduler -> enumerate Lambda -> SQS/DLQ -> collector Lambda -> immutable S3`

A second scheduled workflow uses Step Functions to compare snapshots, write evidence-backed change
events and reports, and send a daily digest. Bedrock is optional and stays off until P8.

The starter architecture is serverless, single-account, and single-region. It intentionally excludes
NAT Gateway, EC2, RDS, OpenSearch, EKS, Kinesis, paid Glue jobs/crawlers, provisioned Lambda
concurrency, and other always-on services.

## Project Rules

- Public ATS and company-career sources only.
- No automated applications, contact harvesting, or authenticated scraping.
- S3 versioning stays off. Raw history uses unique write-once keys and lifecycle expiration.
- Every execution role receives the shared permissions boundary plus a narrower role policy.
- Every Lambda log group gets finite retention.
- The target operating cost is below `$5/month`; `$10` is the emergency ceiling.
- Manual console work remains manual through P8. IaC reconstruction begins at P9.

## Roadmap

- [Master roadmap](docs/roadmap/committee-v1/JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md)
- [Manual AWS workbook](docs/roadmap/committee-v1/AWS_MANUAL_BUILD_WORKBOOK.md)
- [Reference architecture](docs/roadmap/committee-v1/REFERENCE_ARCHITECTURE.md)
- [Security and threat model](docs/roadmap/committee-v1/SECURITY_AND_THREAT_MODEL.md)
- [Panel dissent and required conditions](docs/roadmap/committee-v1/PANEL_DISSENT.md)
- [Local execution plan](docs/PLAN.md)

## Status Language

`READY` means the local instructions and artifacts exist. `COMPLETE` means the AWS result was
manually built and verified. A document being present never proves that its AWS phase is complete.
