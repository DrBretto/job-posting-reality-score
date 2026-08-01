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
| P5 | Step Functions orchestration | **DONE** — jprs-collect-fanout (Map + Retry + Catch); 2 companies collected, bad one caught -> FAILED_ISOLATED, run green. End of hands-on interview-refresher set. |
| DEPLOYED | Live in AWS (acct 767398003959, us-east-1), stack jprs-v1 | **WORKING END-TO-END** — collection verified (3 boards, snapshots+sentinels, DLQ clean, daily schedule armed); assemble verified (differ tracks 908 postings, report 3/3 sources, correct run-health). Fixed post-deploy contract mismatches from the parallel build: env var names, S3 prefixes (manifest->runs), bucket policy (removed encrypt-header deny), ASL companies path, differ input (derive from status/), report assembler (was never wired), report role s3:ListBucket. Added moto integration tests (5) that exercise the real handler glue. Budget/cost-fence REMOVED per operator (not needed for a pennies/mo app). |
| P6-P10 | Change-detection + scoring + report + observability + IaC | **DONE (all-AI, deploy-ready)** — full V1 app (3 connectors, M1 enumerate, differ w/ disappearance invariant + M3 guards, 6-dim scoring, honest report, narrator-OFF); **40 pytest passing**; SAM template deploys whole stack (M4 prefix-split IAM, M5 budget-lockdown + 30d log retention), **sam validate + cfn-lint clean**. Reconciled handler paths (src.*) + CodeUri + requirements.txt + .samignore. Bedrock off; Ashby gated; Athena (P10) deferred until history exists. Ready for `sam build && sam deploy`. |
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
