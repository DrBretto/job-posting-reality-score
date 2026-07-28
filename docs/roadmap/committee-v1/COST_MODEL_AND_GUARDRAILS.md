# COST MODEL & GUARDRAILS — Job Posting Reality Score

**Seat:** ADHOC-FINOPS-COST-ENGINEER · **Scope:** ROADMAP ONLY (no AWS resources created)
**Region:** us-east-1 · **Rates as of:** 2026-07-28 (see `SOURCE_REGISTER_PRICING.md`)
**Target:** starter architecture **< $5/month** under modeled normal usage.

---

## 1. How to read this model

Three scales, from the shared context:

- **(a) Learning / V1** — 1 ATS provider + 3 companies, 1 daily run.
- **(b) Useful** — 3 ATS providers + 10–20 companies (model at 15), 1 daily run.
- **(c) Expansion** — ~100 companies + historical analytics (Parquet + Athena).

Two things kept separate throughout:

1. **Free-tier-dependent $0** vs **ordinary low-usage $** — every line notes whether it is zero
   because usage is genuinely tiny, or zero only because a free tier is absorbing it.
2. **Perpetual free tier** (never lapses: Lambda, SQS, Step Functions, EventBridge Scheduler,
   CloudWatch, Glue Catalog, 100GB/mo egress) vs **12-month free tier** (S3 only — lapses, or is
   already lapsed if Brett's account predates its own 12-month window).

**Bedrock is modeled as OPTIONAL and defaults OFF in V1.** It is shown as a separate add-on line
because it is the single largest swing factor at scale and must never be a silent cost.

---

## 2. Shared assumptions

| Parameter | V1 | Useful | Expansion |
|---|---|---|---|
| Companies tracked | 3 | 15 | 100 |
| ATS providers | 1 | 3 | 3+ |
| Runs/day | 1 | 1 | 1 |
| Runs/month | ~30 | ~30 | ~30 |
| Step Functions transitions/run | ~15 | ~40 | ~150–250 |
| Lambda invocations/run | ~10 | ~20 | ~120 |
| Lambda mem / avg duration | 256MB / 2s | 256MB / 3s | 256MB / 3s |
| SQS messages/month | ~300 | ~1,350 | ~9,000 |
| Snapshot payload size | 10–50 KB JSON | 10–50 KB | 10–50 KB |
| S3 PUTs/month | ~90 | ~600–1,200 | ~3,000–9,000 |
| S3 GETs/month | ~180 | ~2,000–5,000 | ~10,000–50,000 |
| Cumulative S3 storage (yr 1) | <0.1 GB | 0.5–2 GB | 2–10 GB |
| CloudWatch log ingest/month | <0.5 GB | 1–3 GB | 3–8 GB |
| Athena queries/month | 0 | 0 | 100–500 |
| Athena scan/query (Parquet, partitioned) | — | — | 10–100 MB |
| Bedrock (if enabled) model | Haiku (opt) | Haiku (opt) | Haiku (opt) |

---

## 3. Per-service line-item cost tables

All dollar figures are **modeled monthly, us-east-1**. "FT" = absorbed by free tier.
Bedrock and delivery are add-on lines below the core subtotal.

### 3a. Learning / V1 (3 companies)

| Service | Usage | Rate | Monthly $ | Free-tier note |
|---|---|---|---|---|
| Lambda | 300 req; ~150 GB-s | $0.20/1M; $1.67e-5/GB-s | $0.00 | FT (perpetual 1M req/400k GB-s) |
| Step Functions (Standard) | ~450 transitions | $0.025/1k | $0.00 | FT (perpetual 4,000) |
| SQS | ~300 req | $0.40/1M | $0.00 | FT (perpetual 1M) |
| EventBridge Scheduler | 30 invocations | $1.00/1M | $0.00 | FT (perpetual 14M) |
| S3 storage | <0.1 GB | $0.023/GB | $0.00 | ordinary-tiny (≈$0.002 even w/o FT) |
| S3 requests | 90 PUT + 180 GET | $0.005/1k; $0.0004/1k | $0.00 | ordinary-tiny (≈$0.0006 even w/o FT) |
| CloudWatch logs | <0.5 GB ingest | $0.50/GB | $0.00 | FT (perpetual 5GB) |
| CloudWatch alarms/dash | 2–3 alarms, 1 dash | $0.10; $3.00 | $0.00 | FT (perpetual 10 alarms/3 dash) |
| Data transfer out | <1 GB | $0.09/GB | $0.00 | FT (perpetual 100GB) |
| **Core subtotal** | | | **≈ $0.00** | essentially free, mostly ordinary-tiny |
| Bedrock (OPTIONAL, Haiku) | 30 calls, ~2k in/500 out | $0.25/$1.25 per 1M | +$0.03 | not FT; opt-in only |
| Delivery (SES à la carte) | ~30 emails | $0.10/1k | +$0.003 | — |
| **V1 TOTAL** | | | **≈ $0.00–0.05** | |

### 3b. Useful (15 companies)

| Service | Usage | Rate | Monthly $ | Free-tier note |
|---|---|---|---|---|
| Lambda | 600 req; ~450 GB-s | $0.20/1M; $1.67e-5/GB-s | $0.00 | FT (perpetual) |
| Step Functions (Standard) | ~1,200 transitions | $0.025/1k | $0.00 | FT (perpetual 4,000) |
| SQS | ~1,350 req | $0.40/1M | $0.00 | FT (perpetual 1M) |
| EventBridge Scheduler | 30 invocations | $1.00/1M | $0.00 | FT (perpetual) |
| S3 storage | 0.5–2 GB | $0.023/GB | $0.01–0.05 | ordinary low (or FT if <5GB & within 12mo) |
| S3 requests | ~1,200 PUT + ~5k GET | $0.005/1k; $0.0004/1k | ≈$0.01 | ordinary low |
| CloudWatch logs | 1–3 GB ingest | $0.50/GB | $0.00 | FT (perpetual 5GB) — nearing cliff |
| CloudWatch alarms/dash | 3–5 alarms, 1 dash | $0.10; $3.00 | $0.00 | FT (perpetual) |
| Data transfer out | <2 GB | $0.09/GB | $0.00 | FT (perpetual 100GB) |
| **Core subtotal** | | | **≈ $0.02–0.10** | |
| Bedrock (OPTIONAL, Haiku) | 30 runs, ~5k in/1k out | $0.25/$1.25 per 1M | +$0.08 | not FT; opt-in |
| Bedrock (if Sonnet instead) | same tokens | $3/$15 per 1M | +$0.90 | flagged — 10× Haiku |
| Delivery (SES) | ~30 emails | $0.10/1k | +$0.003 | — |
| **USEFUL TOTAL** | | | **≈ $0.10–0.30 (Haiku)** / **≈ $1.00 (Sonnet daily)** | |

### 3c. Expansion (~100 companies + historical analytics)

| Service | Usage | Rate | Monthly $ | Free-tier note |
|---|---|---|---|---|
| Lambda | ~3,600 req; ~2,700 GB-s (+compaction) | $0.20/1M; $1.67e-5/GB-s | $0.00 | FT (perpetual) |
| Step Functions (Standard) | 4,500–7,500 transitions | $0.025/1k | $0.02–0.30 | FT covers 4,000; **see Express note** |
| SQS | ~9,000 req | $0.40/1M | $0.00 | FT (perpetual 1M) |
| EventBridge Scheduler | 30 invocations | $1.00/1M | $0.00 | FT (perpetual) |
| S3 storage | 2–10 GB (w/ lifecycle) | $0.023/GB | $0.05–0.23 | ordinary low; FT already lapsed likely |
| S3 requests | ~9k PUT + ~50k GET | $0.005/1k; $0.0004/1k | ≈$0.05–0.07 | ordinary low |
| CloudWatch logs | 3–8 GB ingest | $0.50/GB | $0.00–1.50 | **cliff: FT covers 5GB, overage billed** |
| CloudWatch alarms/dash | 5–8 alarms, 1–2 dash | $0.10; $3.00 | $0.00–0.30 | FT covers 10 alarms/3 dash |
| Athena | 100–500 queries, 10–100MB each (disciplined) | $5/TB | $0.13–0.50 | **swing risk — see guardrail G5** |
| Glue Data Catalog | <1M objects, <1M requests | $1/100k; $1/1M | $0.00 | FT (perpetual 1M/1M) |
| Data transfer out | <10 GB | $0.09/GB | $0.00 | FT (perpetual 100GB) |
| **Core subtotal (disciplined)** | | | **≈ $0.40–2.50** | dominated by CW logs + Athena |
| Bedrock (OPTIONAL, Haiku) | 30 runs, ~20k in/3k out | $0.25/$1.25 per 1M | +$0.26 | not FT; opt-in |
| Bedrock (if Sonnet daily, 100 co.) | same tokens | $3/$15 per 1M | +$3.15 | **would nearly blow budget alone** |
| Delivery (SES) | ~30 emails | $0.10/1k | +$0.003 | — |
| **EXPANSION TOTAL (Haiku, disciplined)** | | | **≈ $1.00–2.50** | |
| **EXPANSION TOTAL (undisciplined)** | | | **> $5 possible** | Athena unpartitioned + Sonnet daily + unbounded logs |

**Standard vs Express (Step Functions) at expansion:** Standard bills per transition ($0.025/1k)
and is cheapest at low transition counts (our case). Express bills per request + GB-s duration and
wins only at very high transition volumes. At ≤7,500 transitions/month Standard costs pennies and
its execution history aids the *learning* telos — **keep Standard**; revisit only if a future
high-frequency loop pushes transitions past ~1M/month.

---

## 4. Free-tier cliffs (what breaks when a free tier lapses)

| Free tier | Type | If it lapses, added cost | Assessment |
|---|---|---|---|
| Lambda 1M req + 400k GB-s | **Perpetual** | n/a — never lapses | safe |
| SQS 1M req | **Perpetual** | n/a | safe |
| Step Functions 4,000 transitions | **Perpetual** | n/a | safe |
| EventBridge Scheduler 14M | **Perpetual** | n/a | safe |
| CloudWatch 5GB logs / 10 alarms / 3 dash | **Perpetual** | n/a — but **overage above 5GB is billed at $0.50/GB regardless** | the real lever is log *volume*, not tier lapse (see G4) |
| Glue Catalog 1M objects/requests | **Perpetual** | n/a | safe at 100-company scale |
| Data transfer out 100GB/mo | **Perpetual** | n/a | safe |
| **S3 5GB / 20k GET / 2k PUT** | **12-MONTH** | If lapsed: storage ≈$0.02–0.23/mo, requests ≈$0.06/mo | **negligible** — the workload is pennies with or without it |
| **New-account $200 / 6-month credit** | one-time | After 6 months credits gone, all above steady-state rates apply | applies only if this is a **new** account; steady-state model above already assumes NO credit |

**Bottom line on cliffs:** the only *structural* free-tier dependency is CloudWatch's 5GB log
allowance at expansion scale, and it is a **volume** problem controllable by retention + log level,
not a lapse. Everything else is either perpetual or pennies. The model totals above are shown at
**steady-state (no free tier assumed to persist)** — so a lapse changes nothing material.

---

## 5. Guardrail set (control → concrete setting → owner → trigger)

| ID | Control | Concrete setting | Default | Owner | Trigger / escalation |
|---|---|---|---|---|---|
| G1 | **AWS Budgets** | Monthly cost budget = **$5**; alert emails at 50% / 80% / 100% actual + 80% forecast. Second "ceiling" budget at **$10** with a Budgets *action* (SNS notify; optional stop-scheduler). | on | BRETT_MANUAL_AWS | Any alert email → investigate within 24h; forecast >$5 → pause scale-up |
| G2 | **Cost-allocation tags** | Tag every resource `Project=job-posting-reality-score`, `Env={v1,useful,expansion}`, `ManagedBy=brett`. Activate the tags in Billing → Cost allocation tags. | on | BRETT_MANUAL_AWS | Monthly Cost Explorer group-by-`Project`; any untagged spend → tag it |
| G3 | **S3 lifecycle retention (versioning FORBIDDEN)** | Bucket **versioning = Off** (hard rule). Lifecycle rules: expire raw snapshot JSON after **400 days**; transition to Standard-IA at **90 days** (if kept for history); **abort incomplete multipart uploads after 7 days**. No cross-region replication. | on | BRETT_MANUAL_AWS (create) / AI (policy JSON) | Storage >5 GB → shorten expiry or add IA/Glacier IR transition |
| G4 | **CloudWatch log retention** | Set explicit `retentionInDays` on **every** log group (default is *Never Expire*): **30 days** for app/ops logs, 14 for debug. Keep Lambda log level at INFO in prod (DEBUG off). | on | BRETT_MANUAL_AWS / AI (config) | Monthly ingest approaching 5 GB → drop to 14 days / reduce log verbosity |
| G5 | **Athena scan control** | Dedicated **workgroup** with `BytesScannedCutoffPerQuery = 1 GB`; enforce workgroup output location; **require** partition pruning (by company/date) + **Parquet + snappy**. Optional per-workgroup data-scanned control/monitor. | on (at expansion) | AI (schema/SQL) / BRETT_MANUAL_AWS (workgroup) | Any query hitting the 1GB cutoff → repartition/compress before raising limit |
| G6 | **Bedrock invocation/token caps** | Bedrock **feature-flagged OFF in V1**. When enabled: **Haiku default** for routine daily summaries; **Sonnet gated to on-demand/manual only**; per-run **max_tokens cap** in code (already present in `bedrock_client.py`); CloudWatch alarm on monthly Bedrock spend. Consider batch inference (50% off) for non-urgent summaries. | Bedrock OFF | AI (code flags) / BRETT_MANUAL_AWS (model access) | Monthly Bedrock spend >$1 → review; Sonnet-daily proposal → explicit approval |
| G7 | **Teardown controls** | No always-on infra (idle cost ≈ $0). Single documented teardown runbook keyed off the `Project` tag; disabling the **EventBridge Scheduler** halts all runs instantly. | on | BRETT_MANUAL_AWS | Project pause → disable scheduler; project end → run tagged-resource teardown |
| G8 | **Excluded-service ban** | **No** NAT Gateway, EC2, RDS, OpenSearch, Kubernetes/EKS, paid Glue crawler, paid Glue ETL job, Lambda Provisioned Concurrency, Kinesis, or always-on Fargate in starter scope. | enforced | BRETT_MANUAL_AWS / committee | Any proposal to add one → explicit cost review + operator approval (these are the only things that blow $5) |

---

## 6. Under-$5 verdict

| Scale | Modeled total (Haiku / no Bedrock) | Verdict |
|---|---|---|
| **V1** | ≈ $0.00–0.05/mo | **PASS** (trivially; essentially free) |
| **Useful** | ≈ $0.10–0.30/mo (≈$1.00 if Sonnet used daily) | **PASS** |
| **Expansion** | ≈ $1.00–2.50/mo with guardrails | **PASS — only with G4 + G5 + G6 active** |

**Overall: PASS.** The starter and useful architectures hold **well under $5/month** with wide
margin. The expansion architecture holds under $5 **only with the guardrails on**.

**What would break the < $5 target:**
1. **A banned always-on service** (G8) — a single NAT Gateway alone is ≈$32/mo; RDS ≈$12+/mo;
   OpenSearch ≈$25+/mo. These are the only line items that blow the budget on their own. **Confirmed
   excluded** from starter scope per shared context.
2. **Athena scanning unpartitioned / uncompressed data** — a handful of full-table scans over raw
   JSON can reach $2.50+/mo. Controlled by G5 (Parquet + partitions + 1GB cutoff).
3. **Sonnet used for daily 100-company summaries** — ≈$3.15/mo on its own. Controlled by G6
   (Haiku default, Sonnet on-demand only).
4. **Unbounded CloudWatch log retention / DEBUG logging at scale** — overage above 5GB at $0.50/GB.
   Controlled by G4.
5. **Lambda Provisioned Concurrency** or any provisioned/always-on toggle silently enabled.

With G4/G5/G6/G8 enforced, none of these can occur silently; AWS Budgets (G1) is the backstop.

---

## 7. Acceptance tests

- **AT1 — model reconciles:** Recomputing each scale's line items from `SOURCE_REGISTER_PRICING.md`
  rates yields totals ≤ the modeled ceilings: V1 ≤ $0.10, Useful ≤ $1, Expansion ≤ $3 (Haiku, guardrails on).
- **AT2 — budget exists:** An AWS Budget of $5 exists with alert thresholds at 50/80/100% + forecast;
  a simulated 80% breach sends the alert email.
- **AT3 — no versioning + lifecycle present:** Every S3 bucket reports `Versioning != Enabled` AND has
  at least one lifecycle rule (expiry and/or abort-incomplete-MPU).
- **AT4 — finite log retention:** Every CloudWatch log group has a finite `retentionInDays` (none set
  to Never Expire).
- **AT5 — Athena cutoff enforced:** The analytics workgroup has `BytesScannedCutoffPerQuery` set
  (≤1GB); a deliberately oversized query is rejected rather than billed.
- **AT6 — full tag attribution:** Cost Explorer grouped by `Project` tag attributes 100% of the
  project's spend; zero untagged project resources.
- **AT7 — Bedrock off by default + capped:** V1 config has Bedrock disabled; enabling requires an
  explicit flag; the per-call `max_tokens` cap is present in the invocation path.
- **AT8 — teardown to zero:** Running the tag-based teardown removes/disables all tagged resources;
  disabling the scheduler halts runs; post-teardown Cost Explorer trends to ≈$0.

---

## 8. Decisions (default / owner / trigger) — summary

| Decision | Default | Owner | Trigger to revisit |
|---|---|---|---|
| Orchestration engine | Step Functions **Standard** | committee → BRETT_MANUAL_AWS | transitions > ~1M/mo → evaluate Express |
| Bedrock in V1 | **OFF** (feature-flagged) | AI_IMPLEMENTATION | operator opts in for daily summaries |
| Bedrock model tier | **Haiku** default; Sonnet on-demand only | AI + BRETT | Sonnet-daily need → explicit approval + cost review |
| Delivery channel | **SES à la carte** ($0.10/1k) | BRETT_MANUAL_AWS | prefer SNS email if simpler; both ≈$0 at 30/mo |
| S3 retention | lifecycle expiry (no versioning) | BRETT_MANUAL_AWS + AI | storage > 5GB |
| Log retention | 30 days | BRETT + AI | ingest nearing 5GB free |
| Athena format | Parquet+snappy, partitioned, 1GB cutoff | AI (schema) + BRETT (workgroup) | query hits cutoff |
| Budget ceiling | $5 alert + $10 action | BRETT_MANUAL_AWS | any alert |
| Excluded services | NAT/EC2/RDS/OpenSearch/K8s/paid-Glue banned | committee + BRETT | any add proposal → cost review |

---

*Rates and verification status: see `SOURCE_REGISTER_PRICING.md` (same run dir). Re-verify
UNVERIFIED items (SQS rate, Haiku 3 tokens, SNS rate, Glue request rate, S3 free-tier change)
against primary AWS pages before committing Bedrock or Athena to a scaled daily loop.*
