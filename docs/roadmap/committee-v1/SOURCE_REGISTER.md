# SOURCE_REGISTER — Job Posting Reality Score Roadmap Committee

Master register of every external fact the committee relied on, with source URL, retrieval
date, region assumption, and verification status. Assembled by the run executor from the
FinOps seat's pricing fragment (`SOURCE_REGISTER_PRICING.md`), the Data seat's ATS-connector
verifications, and the Reliability/Architecture seats' AWS-behavior verifications.

**Retrieval date for all rows: 2026-07-28. Region assumption: us-east-1.**

Legend: **VERIFIED** = read from the primary vendor page/doc this run. **VERIFIED\*** =
vendor-published value obtained via secondary aggregator because the primary page did not render
its table; long-standing and cross-checked. **UNVERIFIED** = primary did not render / no
confident cross-check; best-known value carried and flagged. **PARTIAL** = partially confirmed.

---

## 1. AWS pricing (region us-east-1)

The full 38-row pricing table lives in **`SOURCE_REGISTER_PRICING.md`** (kept as a separate
fragment for the FinOps audit trail). Headline verification status:

- **VERIFIED (primary AWS pricing pages):** Lambda requests/compute/free-tier; Step Functions
  Standard + Express + free-tier; SQS free-tier; EventBridge Scheduler + custom bus; CloudWatch
  logs/alarms/custom-metrics/dashboards/free-tier; Bedrock Claude 3.5 Sonnet $3/$15 per 1M;
  Athena $5/TB; Glue Data Catalog free-tier + storage; SES à la carte $0.10/1k + Essentials.
- **VERIFIED\* (AWS-published via secondary; primary table did not render):** S3 storage
  $0.023/GB-mo, PUT $0.005/1k, GET $0.0004/1k, S3 12-month free tier, 100GB/mo egress free.
- **UNVERIFIED (carried, re-pull before scale-up):** SQS $0.40/1M; Claude 3 Haiku $0.25/$1.25
  per 1M (cross-checks repo `bedrock_client.py` + secondary); Bedrock batch 50%-off; Glue
  request per-M rate (PARTIAL); SNS email $2/100k; the AWS Free-Tier structural change (new
  accounts after 2025-07-15 → $200/6-month credits instead of classic 12-month tiers).
- **Model-landscape note:** primary Bedrock page advertises "Claude Sonnet 5 promo $2/$10 through
  2026-08-31." Bedrock is OFF in V1; re-pull before committing it to a scaled daily loop.

## 2. ATS public API endpoints (Data seat, verified 2026-07-28)

| # | Provider | Endpoint | Auth | Stable job id? | Source | Status |
|---|----------|----------|------|----------------|--------|--------|
| A1 | Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | none (public) | YES — native `id` + `internal_job_id` + `requisition_id` + `updated_at` | developers.greenhouse.io job-board API docs | VERIFIED |
| A2 | Lever | `api.lever.co/v0/postings/{site}?mode=json` | none (public) | YES — native UUID `id`; `createdAt` present but UNDOCUMENTED; no `updatedAt` | Lever postings API docs | VERIFIED (endpoint/auth/id); `createdAt` UNVERIFIED (community-confirmed, undocumented) |
| A3 | Ashby | `api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true` | none (public) | NO native id → parse UUID from `jobUrl` slug → else content-hash | Ashby posting API docs | VERIFIED (endpoint/auth); job-id permanence UNVERIFIED — **Ashby onboarding gated on this** |

Compliance posture: sanctioned public read-only APIs only. No authenticated scraping, LinkedIn
scraping, contact harvesting, auto-apply, or message sending. Per-GET numeric rate limits are
**UNVERIFIED (none published by any of the three)** → design self-throttles (1 req/source/day,
ETag-cached, identifying User-Agent, honor 429/503 backoff).

## 3. AWS behavioral facts (Reliability + Architecture seats, primary docs, 2026-07-28)

| # | Fact | Status |
|---|------|--------|
| B1 | SQS DLQ + `maxReceiveCount` + redrive (StartMessageMoveTask) semantics | VERIFIED (primary AWS docs) |
| B2 | SQS visibility timeout: default 30s, max 12h | VERIFIED |
| B3 | Lambda SQS event source mapping: at-least-once, partial-batch via `ReportBatchItemFailures` | VERIFIED |
| B4 | Step Functions Standard `Retry` / `Catch` (`States.ALL`) semantics | VERIFIED |
| B5 | Athena partition projection (`projection.enabled='true'`) needs NO Glue crawler | VERIFIED (primary Athena docs) |
| B6 | S3 immutability without versioning via write-once keys + lifecycle (versioning stays OFF — operator hard rule) | VERIFIED (design pattern; consistent with S3 docs) |
| B7 | "Visibility timeout ≥ 6× Lambda function timeout" best-practice ratio | UNVERIFIED — carried as a build-time gate (ADR-25); confirm against Lambda ESM best-practices page |
| B8 | EventBridge Scheduler native missed-invocation metric + Scheduler DLQ | UNVERIFIED — design avoids the dependency via a custom success-heartbeat alarm (A2); Scheduler DLQ alarm (A8) UNVERIFIED |
| B9 | CloudWatch custom-metric / alarm charge vs the perpetual free tier at this scale | UNVERIFIED (impact bounded; free tier = 10 alarms + 10 custom metrics) |
| B10 | Athena `injected` vs `enum` partition projection for the `board` key | UNVERIFIED — settle at the Athena phase (P10) |

## 4. Carried UNVERIFIED items → resolution gate

Each UNVERIFIED item above is carried into the build with a named gate; none blocks V1:

- SQS/SNS/Haiku/Glue pricing rows → **re-pull primary pages before expansion-scale (P10) cost commitment.**
- Ashby job-id permanence → **verify before onboarding Ashby (gates the Ashby connector; Greenhouse is V1).**
- Lever `createdAt` reliability → **treat as advisory; change detection relies on our content-hash, not the provider timestamp.**
- Visibility-timeout 6× ratio (B7) → **confirm at the SQS/DLQ phase (P3) before wiring the queue.**
- Scheduler missed-run metric / DLQ (B8) → **already engineered around (custom heartbeat A2); confirm A8 at P7 if a Scheduler DLQ is added.**
- Athena projection key type (B10) → **settle at P10.**

Provenance: all rows retrieved 2026-07-28 by the committee's specialist subagents via
WebFetch/WebSearch against primary vendor documentation, with secondary aggregators used only
where a primary page failed to render its table (flagged VERIFIED\*/UNVERIFIED accordingly).
