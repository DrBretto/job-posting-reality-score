# Job Posting Reality Score — Build Log

Shared state tracker for the interactive build loop. AI preps artifacts + console instructions;
Brett does the AWS console work by hand (the recall) and reports back; AI verifies and continues.
Roadmap of record: `Infotropy Book/INBOX/job-posting-reality-score-roadmap/`.

Region: **us-east-1** · Cost target: **< $5/mo** · S3 versioning: **OFF** · No NAT/EC2/RDS/OpenSearch/paid-Glue.

## Phase status

| Phase | What | Status |
|---|---|---|
| P0 | Account guardrails & region baseline | **DONE** — existing guardrails + admin (non-root) + us-east-1 |
| P1 | S3 store | **DONE (minimal)** — bucket only; lifecycle/versioning/policy SKIPPED per operator (interview-focus, not ops hygiene) |
| P2 | Collector Lambda + exec role (IAM / AccessDenied refresher) | **DONE** — jprs-collector fetches Stripe (545 jobs) -> gzip snapshot in raw/; hit the deliberate AccessDenied, fixed with least-priv s3:PutObject on raw/* |
| P3 | SQS + DLQ + redrive (the blanked-on refresher) | **DONE** — SQS-triggered collector; poison msg -> retries (VT 30s, maxReceive 2) -> DLQ -> inspected body/ApproxReceiveCount -> deployed v2 (permanent-404-skip vs transient-raise) -> redrive to custom destination -> drained. Trigger got dropped once + re-added; redrive-to-source failed (CouldNotDetermineMessageSource) so used custom destination. |
| P2 | First collector Lambda + exec role | not started |
| P3 | SQS + DLQ (the recall lab) | not started |
| P4 | EventBridge Scheduler | **DONE** — jprs-daily-collect (rate 5min, SQS SendMessage target, scheduler assumes a role) fired -> snapshot with no manual action; then disabled |
| P5 | Step Functions orchestration | **IN PROGRESS** |
| P6 | Change detection & daily report (V1 deliverable) | not started |
| P7 | CloudWatch alarms & observability | not started |
| P8 | Bedrock digest (optional) | not started |
| P9 | IaC reconstruction | not started |
| P10 | Parquet + Athena (mature, gated) | not started |

## Running log

### 2026-07-31 — P0 started
- Project home created (new repo per REPO_REUSE decision; CFR left untouched as reference).
- Prepared `aws/policies/jprs-permissions-boundary.json` (used at P2 when exec roles are created).
- Handed Brett the P0 console checklist (region + budget + billing alarm + identity + Access Analyzer + wrong-region failure).
- AWAITING: Brett's report on P0 steps.
