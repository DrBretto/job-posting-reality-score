# SOURCE_REGISTER — Pricing Fragment (ADHOC-FINOPS-COST-ENGINEER)

> Fragment for merge into master `SOURCE_REGISTER.md`. All figures **region us-east-1**.
> Retrieval date **2026-07-28**. Method: WebFetch/WebSearch against AWS primary pricing
> pages (`aws.amazon.com/*/pricing`) plus, where the primary page did not render its rate
> table, AWS-published rate data surfaced via secondary aggregators (flagged).
>
> VERIFIED = read from the AWS primary pricing page this run.
> VERIFIED* = AWS-published rate obtained via secondary aggregator (primary page did not
> render the numeric table); value is long-standing and cross-checks.
> UNVERIFIED = primary page did not render and no confident cross-check; best-known value flagged.

| # | Item | Value | Unit | Source URL | Region | Retrieval | Status |
|---|------|-------|------|-----------|--------|-----------|--------|
| 1 | Lambda requests | $0.20 | per 1M requests | https://aws.amazon.com/lambda/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 2 | Lambda compute (x86) | $0.0000166667 | per GB-second | https://aws.amazon.com/lambda/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 3 | Lambda free tier (perpetual) | 1,000,000 req + 400,000 GB-s | per month | https://aws.amazon.com/lambda/pricing/ | global | 2026-07-28 | VERIFIED |
| 4 | Step Functions Standard | $0.025 ($0.000025/transition) | per 1,000 state transitions | https://aws.amazon.com/step-functions/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 5 | Step Functions Standard free tier (perpetual) | 4,000 | state transitions/month | https://aws.amazon.com/step-functions/pricing/ | global | 2026-07-28 | VERIFIED |
| 6 | Step Functions Express requests | $1.00 | per 1M requests | https://aws.amazon.com/step-functions/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 7 | Step Functions Express duration | $0.00001667 | per GB-second | https://aws.amazon.com/step-functions/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 8 | SQS Standard requests | $0.40 | per 1M requests | https://aws.amazon.com/sqs/pricing/ | us-east-1 | 2026-07-28 | UNVERIFIED (primary page rate table did not render; long-standing published rate) |
| 9 | SQS free tier (perpetual) | 1,000,000 | requests/month | https://aws.amazon.com/sqs/pricing/ | global | 2026-07-28 | VERIFIED |
| 10 | EventBridge Scheduler invocations | $1.00 | per 1M invocations | https://aws.amazon.com/eventbridge/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 11 | EventBridge Scheduler free tier (perpetual) | 14,000,000 | invocations/month | https://aws.amazon.com/eventbridge/pricing/ | global | 2026-07-28 | VERIFIED |
| 12 | EventBridge custom event bus ingestion | $1.00 | per 1M events (64KB/event) | https://aws.amazon.com/eventbridge/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 13 | S3 Standard storage (first 50TB) | $0.023 | per GB-month | https://aws.amazon.com/s3/pricing/ (rendered via cloudzero/AWS-published 2026-05-12) | us-east-1 | 2026-07-28 | VERIFIED* |
| 14 | S3 PUT/COPY/POST/LIST | $0.005 | per 1,000 requests | https://aws.amazon.com/s3/pricing/ (AWS-published via secondary) | us-east-1 | 2026-07-28 | VERIFIED* |
| 15 | S3 GET/SELECT | $0.0004 | per 1,000 requests | https://aws.amazon.com/s3/pricing/ (AWS-published via secondary) | us-east-1 | 2026-07-28 | VERIFIED* |
| 16 | S3 free tier (12-MONTH, accounts created before 2025-07-15) | 5 GB + 20,000 GET + 2,000 PUT | per month, 12 mo | https://aws.amazon.com/s3/pricing/ | global | 2026-07-28 | VERIFIED* |
| 17 | AWS Free Tier structural change | New accounts (after 2025-07-15) get $200 credits / 6 months INSTEAD of classic per-service 12-month tiers | — | https://aws.amazon.com/free/ (via secondary) | global | 2026-07-28 | UNVERIFIED (secondary; confirm against aws.amazon.com/free) |
| 18 | CloudWatch Logs ingestion (Standard) | $0.50 | per GB | https://aws.amazon.com/cloudwatch/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 19 | CloudWatch Logs storage/archive | $0.03 | per GB-month | https://aws.amazon.com/cloudwatch/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 20 | CloudWatch Logs free tier (perpetual) | 5 GB (ingest+archive+scan) | per month | https://aws.amazon.com/cloudwatch/pricing/ | global | 2026-07-28 | VERIFIED |
| 21 | CloudWatch alarm (standard) | $0.10 | per alarm-metric-month | https://aws.amazon.com/cloudwatch/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 22 | CloudWatch custom metric (first 10k) | $0.30 | per metric-month | https://aws.amazon.com/cloudwatch/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 23 | CloudWatch dashboard | $3.00 | per dashboard-month | https://aws.amazon.com/cloudwatch/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 24 | CloudWatch free tier (perpetual) | 10 alarms + 10 custom metrics + 3 dashboards | per month | https://aws.amazon.com/cloudwatch/pricing/ | global | 2026-07-28 | VERIFIED |
| 25 | Bedrock Claude 3.5 Sonnet (on-demand) input | $3.00 | per 1M tokens | https://aws.amazon.com/bedrock/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 26 | Bedrock Claude 3.5 Sonnet (on-demand) output | $15.00 | per 1M tokens | https://aws.amazon.com/bedrock/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 27 | Bedrock Claude 3 Haiku (on-demand) input | $0.25 ($0.00025/1K) | per 1M tokens | https://aws.amazon.com/bedrock/pricing/ (via secondary + repo estimate) | us-east-1 | 2026-07-28 | UNVERIFIED (primary Haiku 3 row not rendered; cross-checks repo bedrock_client.py + secondary) |
| 28 | Bedrock Claude 3 Haiku (on-demand) output | $1.25 ($0.00125/1K) | per 1M tokens | https://aws.amazon.com/bedrock/pricing/ (via secondary + repo estimate) | us-east-1 | 2026-07-28 | UNVERIFIED (as above) |
| 29 | Bedrock batch inference discount | 50% off on-demand | — | https://aws.amazon.com/bedrock/pricing/ (secondary) | us-east-1 | 2026-07-28 | UNVERIFIED |
| 30 | Athena SQL (data scanned) | $5.00 | per TB scanned | https://aws.amazon.com/athena/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 31 | Athena minimum per query | 10 MB | per query (stated for federated sources; standard S3 queries round up per query) | https://aws.amazon.com/athena/pricing/ | us-east-1 | 2026-07-28 | VERIFIED (federated minimum) / PARTIAL (S3-query rounding not restated) |
| 32 | Glue Data Catalog free tier (perpetual) | 1,000,000 objects + 1,000,000 requests | per month | https://aws.amazon.com/glue/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 33 | Glue Data Catalog storage (over 1M objects) | $1.00 | per 100,000 objects-month | https://aws.amazon.com/glue/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 34 | Glue Data Catalog requests (over 1M) | $1.00 | per 1M requests | https://aws.amazon.com/glue/pricing/ | us-east-1 | 2026-07-28 | PARTIAL (implied by example; per-M rate not restated on page) |
| 35 | SES à la carte outbound | $0.10 | per 1,000 emails | https://aws.amazon.com/ses/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 36 | SES Essentials plan outbound (0–10M) | $0.16 | per 1,000 emails | https://aws.amazon.com/ses/pricing/ | us-east-1 | 2026-07-28 | VERIFIED |
| 37 | SNS email deliveries | $2.00 | per 100,000 (first 1,000/mo free) | https://aws.amazon.com/sns/pricing/ | us-east-1 | 2026-07-28 | UNVERIFIED (primary rate table did not render; long-standing published rate) |
| 38 | Data transfer OUT to internet | first 100 GB/mo free, then $0.09/GB | per GB-month | https://aws.amazon.com/s3/pricing/ (AWS-published via secondary) | us-east-1 | 2026-07-28 | VERIFIED* |

## Notes / uncertainty
- **Perpetual vs 12-month free tiers matter.** Lambda, SQS, Step Functions, EventBridge
  Scheduler, CloudWatch, Glue Data Catalog, and the 100GB/mo data-transfer-out allowance are
  **always-free** (they do not lapse). Only the **S3 12-month free tier** (#16) lapses — and
  its impact on this workload is pennies (see cost model).
- **Bedrock model landscape is shifting.** Primary page shows Claude 3.5 Sonnet at $3/$15 and
  advertises "Sonnet 5 promotional launch pricing $2/$10 through 2026-08-31." Haiku 3 row did
  not render on the primary page this run; $0.25/$1.25 per 1M is carried from the repo's own
  `src/llm/bedrock_client.py` estimate (matches secondary) and is flagged UNVERIFIED. Re-pull
  before committing Bedrock to a scaled daily loop.
- **Repo cross-check:** `bedrock_client.py` docstrings state Haiku ~$0.00025/1K in, ~$0.00125/1K
  out; Sonnet ~$0.003/1K in, ~$0.015/1K out. These equal $0.25/$1.25 and $3/$15 per 1M — the
  repo estimates are consistent with 2026-07-28 rates.
- **Re-verify before scale-up:** #8 (SQS rate), #13–17 (S3 + free-tier change), #27–29 (Haiku/batch),
  #34 (Glue request rate), #37 (SNS) should be re-pulled from primary pages when the primary
  tables render, prior to expansion-scale commitment.
