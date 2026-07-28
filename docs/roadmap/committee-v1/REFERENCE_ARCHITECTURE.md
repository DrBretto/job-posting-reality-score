# Reference Architecture — Job Posting Reality Score (V1 Job Radar)

> Seat: `ADHOC-AWS-SERVERLESS-ARCHITECT`. Roadmap only — no resources created, no app code written.
> Companion files owned by other seats: IAM policy JSON (security seat), cost model (cost seat),
> data schemas (data seat). This file references component→role boundaries only.
>
> **Design goal for this lens:** the SMALLEST architecture in which every retained service has a
> real operational OR educational role. Region `us-east-1`. Starter target < $5/month, no always-on
> infra, manual-console build (no IaC in starter).

## AWS facts this design depends on (verified against primary docs, retrieved 2026-07-28)

| Fact | Value | Source |
|---|---|---|
| Step Functions Standard | exactly-once; up to 1 year; priced per state transition; full execution history queryable 90 days; supports `.sync` + `.waitForTaskToken`; `StartExecution` idempotent by execution name while a same-named run is active | docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html |
| Step Functions Express | at-least-once (async) / at-most-once (sync); **5-minute max**; priced per execution+duration+memory; **no persisted history** (CloudWatch Logs only); no `.sync`/`.waitForTaskToken`; no Distributed Map | same |
| EventBridge Scheduler | serverless; cron/rate/one-time; **timezone-aware**; flexible time windows; per-schedule retries + DLQ; templated targets (SQS/SNS/Lambda/EventBridge) + universal target (270+ services incl. StepFunctions `StartExecution`); at-least-once delivery | docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html |
| SQS visibility timeout | **default 30s, max 12h**; set to match/exceed max processing time; extendable via `ChangeMessageVisibility`; at-least-once delivery (dupes possible) | docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html |
| Lambda SQS partial batch response | `ReportBatchItemFailures` returns `{batchItemFailures:[{itemIdentifier: messageId}]}`; a thrown exception fails the WHOLE batch; when enabled, Lambda does not scale down polling on failures | docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html |
| SQS DLQ / redrive | redrive policy `maxReceiveCount` = receives before move to DLQ; DLQ must be same account+Region; DLQ redrive-to-source moves messages back; set DLQ retention > source retention | docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html |

**UNVERIFIED (carry as design assumption, confirm at build):** the "visibility timeout ≥ 6× Lambda
function timeout" rule of thumb is AWS Lambda event-source-mapping guidance but was NOT restated on
the pages fetched above; the verified hard facts are default 30s / max 12h. Design uses 6× as the
default and flags it for the reliability seat to confirm against the Lambda ESM best-practices page.

---

## 1. Context view

```
                         ┌─────────────────────────────────────────┐
   Sanctioned public     │        Job Posting Reality Score          │
   ATS APIs (HTTPS)      │              (V1 Job Radar)               │
   ┌───────────────┐     │                                           │
   │  Greenhouse   │◄────┤  collects selected company boards daily,  │
   │  Lever        │     │  preserves immutable snapshots, reports   │──►  Brett
   │  Ashby        │     │  what MATERIALLY CHANGED each day         │    (daily digest,
   └───────────────┘     │                                           │     1 recipient)
                         └─────────────────────────────────────────┘
                                    │                    ▲
                                    ▼                    │
                          AWS us-east-1 (serverless, pay-per-use, no always-on)

Boundaries / non-goals (bind the whole system):
  • Sanctioned PUBLIC ATS APIs only. No auth scraping, LinkedIn, contact harvest, auto-apply, sends.
  • Observes posting BEHAVIOR. Never asserts a job is fake/real/fraudulent.
  • "Source did not run" MUST be distinguishable from "nothing changed" (see receipts + alarms).
  • Source failure MUST NEVER masquerade as mass job disappearance (see failure/redrive sequence).
  • Dual telos: (1) rebuild AWS recall via MANUAL console build; (2) real daily job-search value.
```

---

## 2. Component view

```
 ┌────────────────────┐        daily cron (tz America/New_York)
 │ EventBridge         │  StartExecution
 │ Scheduler           │────────────────────────────┐
 │  (1 schedule)       │                             ▼
 └────────────────────┘        ┌───────────────────────────────────────────────┐
                               │  Step Functions  STANDARD  "daily-run"          │
                               │  (orchestrator + audit spine + barrier)         │
                               │                                                 │
  ┌──────────┐  invoke         │  [Enumerate] → [FanOut→SQS] → [DrainBarrier]    │
  │ Lambda   │◄────────────────┤        │                          │   (Choice+  │
  │ enumerate│                 │        │                          │    Wait     │
  └──────────┘                 │        │                          │    poll)    │
                               │        ▼                          ▼             │
                               │   SendMessageBatch          [ChangeProcess Map] │
                               │        │                          │             │
                               │        │                    invoke │            │
                               │        │                          ▼             │
                               │        │                    ┌──────────┐        │
                               │        │                    │ Lambda   │        │
                               │        │                    │ differ   │        │
                               │        │                    └──────────┘        │
                               │        ▼                          │             │
                               │  ┌───────────────┐                ▼             │
                               │  │ SQS            │          [BuildReport]───►┌──────────┐
                               │  │ collect-queue  │                │          │ Lambda   │
                               │  └───────┬────────┘                ▼          │ report   │
                               │          │ event-source-mapping  [Digest]     └──────────┘
                               │          ▼ (ReportBatchItemFailures)   │            │
                               │    ┌──────────┐                        ▼            ▼
                               │    │ Lambda   │                 ┌──────────┐   ┌──────────┐
                               │    │ collector│                 │ SES  (or │   │  S3      │
                               │    └────┬─────┘                 │  SNS)    │   │ (report) │
                               │         │ maxReceiveCount=3     └────┬─────┘   └──────────┘
                               │         ▼ (exhausted)                │
                               │    ┌──────────┐                      ▼
                               │    │ SQS DLQ  │                    Brett
                               │    │ collect- │
                               │    │ dlq      │
                               │    └──────────┘
                               └─────────────────────────────────────────────────┘
        All Lambdas + queues + state machine emit to CloudWatch (logs + metrics + alarms).
        S3 single bucket, prefix-partitioned, NO versioning, lifecycle-managed (all tiers).
        Bedrock: OPTIONAL/LATER, explanation-only, never scoring authority.
```

**Component → responsibility / failure boundary / cost / removal test**

| Component | Responsibility | Failure boundary | Cost (qual.) | Removal test |
|---|---|---|---|---|
| EventBridge Scheduler | Fire the daily run at a fixed local time | Its own retries+DLQ; a missed fire = one skipped day, alarmed by "no run today" | Per-invocation, negligible (free tier) | Remove if runs become event-driven (e.g., webhook) rather than time-based, or if a single cron rule elsewhere already fires it |
| Step Functions Standard `daily-run` | Orchestrate phases; provide the collection→change barrier; be the auditable per-run record | A phase failure is caught+recorded; one company never fails the run (isolation lives in SQS + Map Catch) | Per state transition; dozens/run/day; effectively free | Remove if the run collapses to a single Lambda AND you accept losing the durable, inspectable execution history (the audit trail is itself educational + operational value) |
| Lambda `enumerate` | Read company list (S3 config), emit `{provider,board_token,company_id}` array + `run_id`/`date` | Pure/deterministic; failure aborts run early before any partial state | Negligible | Merge into the state machine input if the company list becomes a static ASL array (only viable at ~3 companies) |
| SQS `collect-queue` | Buffer one collection job per company; give per-company retry/backoff independent of siblings | A poison message is isolated per-message, not per-run | Per-request; ~10²/day; negligible | See §8 rejected-alt "SQS vs Map-invoke" — removable at <~20 companies if you accept losing DLQ quarantine + the SQS/DLQ recall drill |
| Lambda `collector` | Fetch ONE company board, write immutable raw + normalized + a success receipt to S3 | Its exception fails only its own message; redelivery→retry; exhaustion→DLQ | Per-invocation; thin handler; negligible | Cannot remove without removing collection; can only be reshaped (Map task vs SQS consumer) |
| SQS `collect-dlq` | Quarantine companies that failed all fetch retries; physical embodiment of "failed fetch ≠ mass removal" | Terminal sink; alarmed on depth>0 | Per-request; near-zero | Remove only if `collect-queue` is removed; the DLQ is the point of the queue for this system |
| Lambda `differ` | Diff today's normalized set vs stored current-state for ONE company **that has a success receipt**; emit change events; update current-state | Runs only for successfully-collected companies; a company with no receipt is skipped (reported "not collected"), never diffed to "all removed" | Negligible | Merge with `collector` only if collect+diff are made a single synchronous step (loses the queue-decouple) |
| Lambda `report` | Assemble daily report from change events + receipts; distinguish "nothing changed" vs "collectors did not run" | Read-only over S3; failure = no digest, alarmed | Negligible | Remove if digest is generated inline by `differ` fan-in (only at tiny scale) |
| SES (or SNS) | Deliver the one daily digest to Brett | Send failure alarmed; report already persisted in S3 | 1 msg/day; negligible | Remove if digest delivery moves to a pull model (Brett reads `s3://…/reports/…`) |
| S3 (single bucket) | All six+ storage tiers (§7); the system's system-of-record | Per-key durability; immutability by unique key (NOT versioning) | Storage + PUT/GET of small JSON; pennies; lifecycle-capped | Not removable — it is the datastore |
| CloudWatch | Logs, metrics, DLQ-depth alarm, "collection did not run" alarm | The ops-level guarantee behind "did the collectors run?" | Log ingestion is the main real cost; short retention keeps it cheap | Not removable in starter — it is how source-silence is detected |
| Bedrock | OPTIONAL/LATER: plain-language narration of stored change evidence | Explanation only; every sentence points to stored evidence; NEVER scoring authority | Per-token; off by default | Remove/keep-off in starter to protect <$5/mo and the "LLM ≠ evidence" rule |

---

## 3. Collection sequence (the "save postings daily" core)

```
Scheduler ─StartExecution─► SFN daily-run
  │
  ├─[Enumerate]  Lambda enumerate → [{company_id, provider, board_token} …], run_id, date
  │
  ├─[FanOut→SQS] SendMessageBatch: ONE message per company
  │        msg = { run_id, date, company_id, provider, board_token }        (grain = 1 company)
  │
  └─[DrainBarrier]  Choice → (all companies have receipt OR are in DLQ?)
              │  no  → Wait(90s) → re-check  (poll loop, cheap in Standard)
              │  yes → proceed to Change-processing (§4)
              ▼
   (meanwhile, decoupled, self-paced:)
   SQS collect-queue ──event-source-mapping──► Lambda collector   (batch size 5, ReportBatchItemFailures)
        for each message (one company):
          1. GET current ATS board via public API (Greenhouse/Lever/Ashby)
          2. PUT immutable raw   → raw/provider=…/company=…/date=…/<fetch_ts>.json.gz   (write-once)
          3. PUT normalized      → normalized/company=…/date=…/listings.json
          4. PUT success receipt → receipts/date=…/company=…json  {status:ok, fetch_ts, count}
          5. return success for this itemIdentifier
        on fetch error: throw for THIS message only → SQS redelivers (visibility timeout elapses)
                        → after maxReceiveCount=3 → message lands in collect-dlq
```

**Idempotency (at-least-once safe):** raw key includes `fetch_ts` (redelivery writes a new
harmless object); normalized/current-state/receipt keys are deterministic per `company+date`
(last-write-wins). A duplicate delivery re-does the same PUTs with the same result — no corruption.

**Message-grain rationale:** one company per message is the correct grain because the diff needs a
company's WHOLE listing set, and per-company isolation is exactly the failure boundary the system
requires. One message per job posting = too fine (can't diff a set); one per provider = too coarse
(one flaky company poisons all of that provider's companies).

**SQS tuning defaults:** batch size 5 + `ReportBatchItemFailures` (a bad company doesn't retry the
good ones in its batch); visibility timeout = 6× collector Lambda timeout (default assumption; e.g.
Lambda 60s → visibility 360s; verified bounds 30s–12h); `maxReceiveCount`=3 → `collect-dlq`;
DLQ retention 14 days (> source retention).

---

## 4. Change-processing sequence

```
[ChangeProcess]  Map over companies (inline Map, MaxConcurrency ~5):
   for each company_id:
     receipt = GET receipts/date=…/company=…json
     ├─ receipt.status == ok ─► Lambda differ:
     │      today   = GET normalized/company=…/date=…/listings.json
     │      base    = GET state/company=…/current.json      (may be empty on first run)
     │      diff    = added / removed / modified  (by stable job_id)
     │      PUT change events → changes/company=…/date=…/events.json   (each event → evidence refs:
     │                                                                   job_id, first_seen, fetch_ts,
     │                                                                   raw key)
     │      PUT state/company=…/current.json = today          (advance baseline; last-write-wins)
     │
     └─ receipt missing / status != ok ─► SKIP diff.
            Record company as "NOT COLLECTED" for the report.  ◄── the load-bearing safety rule:
            NO receipt ⇒ UNKNOWN, never "all jobs removed."

[BuildReport]  Lambda report:
     inputs  = change events (all companies) + receipts (all companies) + DLQ depth
     output  = reports/date=…/report.md (+ .json), with three explicit states per company:
                 • CHANGED   (added/removed/modified, each linked to stored evidence)
                 • NO CHANGE (collected ok, diff empty)
                 • NOT COLLECTED (no success receipt / in DLQ)  ← never shown as "removed"

[Digest]  SES (or SNS) send report to Brett.  Report already persisted in S3 regardless of send.
```

---

## 5. Failure / redrive sequence

```
Company board fetch fails (5xx, timeout, rate-limit):
   collector throws for that itemIdentifier only
     → message stays invisible until visibility timeout elapses, then redelivered
     → attempt 2, attempt 3 …
     → at receive #4 (maxReceiveCount=3) SQS moves message to collect-dlq
     → CloudWatch alarm on collect-dlq ApproximateNumberOfMessagesVisible > 0  → notify

Effect on the run:
   • The failed company has NO success receipt for today.
   • differ SKIPS it. report marks it "NOT COLLECTED".
   • Its stored current-state is NOT advanced and NOT diffed to empty.
   ⇒ a dead board looks like "we couldn't check", NOT "all their jobs vanished".   ✅ requirement met

Whole-provider outage (e.g., Greenhouse down):
   • Every Greenhouse company message fails → all land in DLQ → all "NOT COLLECTED".
   • report header states "Greenhouse collection did not run" (distinct from "nothing changed").
   • "no run at all" is caught separately by the Scheduler/SFN "no execution today" alarm.

Recovery (redrive):
   • Transient outage over → operator uses SQS DLQ redrive-to-source to move messages from
     collect-dlq back to collect-queue → collector reprocesses → receipts written → next run's
     report reflects real state. (Redrive is manual/console in starter = the SQS recall drill.)
   • This is exactly the DLQ path Brett blanked on in interview — made physical and rehearsed.
```

**Two silences, two detectors (never conflated):**
- "Nothing changed" = collector ran, receipt=ok, diff empty → report NO CHANGE.
- "Collectors didn't run" = missing receipt / DLQ depth / no SFN execution → report NOT COLLECTED
  + CloudWatch alarm. This separation is a hard requirement, enforced by the receipt tier + alarms.

---

## 6. Data lifecycle

```
fetch ──► raw (immutable, write-once)     ── lifecycle: →IA 30d →Glacier 90d, expire per retention
             │                                   (the ONLY irreplaceable tier; back up before teardown)
             ▼
          normalized (per company per day)  ── lifecycle: expire after change events derived (e.g., 90d)
             │
             ▼
          differ ──► change-event (per company per day)  ── keep long (cheap, the product's memory)
             │
             ├──► current-state (per company, overwritten)  ── no lifecycle expiry; single writer/run
             │
          receipt (per company per day)  ── keep ≥ a few runs for "did it run?" audit, then expire
             │
             ▼
          report (per day)  ── keep long (cheap); the digest of record
             │
             ▼
          query-result (Athena output)  ── LATER tier; expire aggressively (regenerable)
          parquet/ (analytics)          ── LATER tier; historical-intelligence layer
```

**Hard rule honored:** S3 versioning is NEVER enabled. Immutability of `raw` is achieved by writing
to a unique key per fetch (`<fetch_ts>`), and retention is managed by lifecycle policies — not by
object versions. Single bucket, prefix-partitioned by tier, keeps IAM/least-privilege boundaries
clean (security seat owns the per-prefix policy).

---

## 7. Storage tiers — where each lives and why

| Tier | S3 prefix | Written by | Why here (not a DB) |
|---|---|---|---|
| immutable-raw | `raw/provider=/company=/date=/<fetch_ts>.json.gz` | collector | Exact evidence; append-only; unique-key immutability; the audit floor |
| normalized | `normalized/company=/date=/listings.json` | collector | Parsed canonical set per day; diff input; disposable once change events derived |
| current-state | `state/company=/current.json` | differ | Diff baseline; ONE writer per company per run ⇒ last-write-wins is correct; no concurrent-update need ⇒ no DB |
| change-event | `changes/company=/date=/events.json` | differ | The product's daily output + memory; each event carries evidence refs |
| collection-receipt | `receipts/date=/company=.json` | collector | Ground truth for "did the collectors run?"; separates the two silences |
| report | `reports/date=/report.md` (+`.json`) | report | Digest of record; delivered by SES/SNS |
| query-result / parquet | `athena-results/`, `parquet/` | LATER | Analytics for the mature historical layer; excluded from starter |

---

## 8. Rejected alternatives + reconsideration triggers

**Step Functions Express (rejected; kept Standard).**
Rejected because: 5-minute cap can't hold a poll-and-wait collection barrier at 10–100 companies;
Express keeps NO execution history (audit trail is operational + educational value here); at-least-once
async semantics risk double-processing without added idempotency work. Standard's per-transition cost
is trivial at 1 run/day. **Reconsider if:** the run becomes high-frequency (many/hour), always
completes < 5 min, needs no persisted history, and Standard state-transition cost becomes material —
none currently true.

**Lambda-per-connector (rejected; kept ONE shared collector with a provider adapter).**
Rejected because: three near-identical thin fetchers triple the deploy/IAM/observability surface for
no isolation gain — per-company isolation already lives in the SQS message boundary, not in separate
functions. One `collector` Lambda dispatches on `provider` to a Greenhouse/Lever/Ashby adapter module.
**Reconsider if:** a connector needs a materially different runtime/dependency/timeout/concurrency
profile, or a heavier auth/rate-limit regime, such that co-tenancy in one function causes real
interference.

**SQS collect-queue vs Step Functions Map direct-invoke (kept SQS).**
The smallest possible collection is a synchronous Standard Map calling `collector` per company with a
per-iteration `Catch` — that alone satisfies "one company's failure never fails the run / never marks
mass removal," and it drops SQS+DLQ entirely. Kept SQS+DLQ anyway because: (a) ATS APIs are external
and flaky — independent per-company retry with backoff + a DLQ quarantine is the right operational
fit; (b) the DLQ is the *physical embodiment* of "failed fetch ≠ mass removal" and the exact SQS/DLQ
recall Brett must rebuild (dual telos). **Removal test / reconsider:** at < ~20 companies with reliable
boards, collapse to Map direct-invoke if you accept losing the DLQ quarantine and the SQS drill.
**Re-add / keep if:** company count grows, boards get flaky/rate-limited, or the SQS+DLQ learning is
in scope (it is).

**Inline Map vs Distributed Map (kept inline Map).**
Distributed Map targets thousands of items / large S3 datasets. **Reconsider if:** company count
exceeds a few hundred, or the company list itself becomes a large S3 manifest to iterate.

**DynamoDB / any database now (rejected; S3-only).**
S3 current-state is correct while: one writer per company per run (no concurrent conditional updates),
whole-file read/write per company (small sets), and analytics are batch (Athena over Parquet, later).
**EXACT trigger to introduce DynamoDB:** (a) concurrent writers touch the same current-state item and
you need atomic/conditional updates (e.g., "seen this job_id before?" under concurrency), OR (b) the
historical-intelligence layer needs indexed low-latency point/range queries (first-seen per job,
repost counts, application-outcome status) where per-query Athena scan cost/latency is too high for
interactive use, OR (c) per-job mutable status tracking (applied/interviewing/outcome) needing
conditional writes. Until one of those is true, S3 is cheaper and simpler.

**API Gateway / web frontend (excluded).** Output is a push digest; no request/response surface.
**Reconsider if:** an interactive query UI over history is wanted (pairs with the DynamoDB/Athena trigger).

**SNS as event bus / custom EventBridge bus (excluded).** No multi-consumer fan-out beyond the one
digest. SNS is retained ONLY as an optional digest transport. **Reconsider if:** multiple downstream
consumers of change events appear.

**NAT Gateway / VPC, RDS, ECS/Fargate, OpenSearch, paid Glue job/crawler (excluded).** All violate
the no-always-on / <$5-month / thin-Lambda rules; Lambdas reach public ATS + AWS APIs with no private
networking. **Reconsider only** on explicit operator approval for a specific need.

**Bedrock in starter (excluded/off-by-default).** Kept OUT of the daily path to protect the cost floor
and the "LLM is never evidence" rule. **Add later** strictly to narrate stored change evidence in
plain language, every sentence pointing back to a stored evidence reference — never as the authority
that decides whether a posting changed. Reuse CFR's existing Bedrock client wrapper (dry-run stubs,
retry/throttle) — it is directly portable.

---

## 9. Starter vs Later service table

| Service | Starter? | Role in starter | Later role |
|---|---|---|---|
| EventBridge Scheduler | YES | Daily cron trigger (tz-aware) | Possibly a 2nd schedule for analytics rollups |
| Step Functions Standard | YES | Orchestration + barrier + audit | Add analytics/rollup branch |
| Lambda (enumerate/collector/differ/report) | YES | Thin handlers; core logic pure/testable | Add narrator (Bedrock) handler |
| SQS + DLQ | YES | Collection fan-out + quarantine + SQS/DLQ drill | Same; scales with company count |
| S3 (single bucket, no versioning, lifecycle) | YES | All six tiers | Add parquet/ + athena-results/ tiers |
| CloudWatch (logs/metrics/alarms) | YES | Source-silence + DLQ-depth detection | Dashboards |
| SES (or SNS) | YES | Daily digest delivery | Same |
| Bedrock | NO (off) | — | Explanation-only narration, evidence-linked |
| Athena / Parquet | NO | — | Historical-intelligence analytics layer |
| DynamoDB | NO | — | Only at the exact trigger in §8 |
| API Gateway / frontend | NO | — | Only if interactive history UI wanted |
| NAT/VPC/RDS/Fargate/OpenSearch/Glue | NO | — | Only on explicit approval |
| IaC (SAM/CDK) + CI/CD (GitHub Actions) | NO (manual console) | Manual build rebuilds recall | Codify the manually-built stack; CI runs unit tests + `sam validate`/`cdk synth` on PR, deploy on merge |

---

## 10. Local development, teardown, reproducibility

**Local dev + fixtures.** Every Lambda's core logic is a pure function (fetch-parse, diff,
report-assemble) importable and runnable locally against committed ATS JSON fixtures (real captured
Greenhouse/Lever/Ashby responses) with a temp dir standing in for S3. Reuse CFR's Bedrock dry-run
stub pattern. State machine validated with Step Functions Local (Docker) + ASL `MockConfig` for task
responses; SQS partial-batch behavior tested with moto or an in-process fake queue. AWS wiring is the
deliberately-manual console act — the pure functions are what CI later tests.

**Teardown.** No versioning ⇒ clean deletes. AI-authored resource inventory + create-order runbook
lets Brett tear down (schedule → ESM → queues → state machine → bucket-with-lifecycle) and rebuild.
`raw/` is the only irreplaceable tier — back it up before any bucket teardown; all other tiers are
regenerable from `raw` + a re-run.

**Reproducibility test.** Destroy all, rebuild from the runbook (starter) or `cdk synth`/`sam deploy`
(later), run one collection, confirm identical tier layout and a well-formed report.

---

## 11. Acceptance tests (component boundaries)

1. **Isolation:** kill one company's board (fixture 500) → run completes; that company = NOT COLLECTED;
   all others CHANGED/NO CHANGE; that company's current-state unchanged; no "removed" events for it.
2. **Mass-removal safety:** kill an entire provider → all its companies NOT COLLECTED, report says
   "<provider> collection did not run"; zero removal events emitted.
3. **Two silences:** (a) all boards return identical sets → report NO CHANGE, no alarm. (b) Scheduler
   disabled for a day → "no execution today" alarm fires; report absent — never silently "no change".
4. **DLQ + redrive drill:** force 3 failures for one company → message in collect-dlq, depth alarm
   fires; redrive-to-source → collector reprocesses → receipt ok → next report reflects real state.
5. **Idempotency:** deliver the same collection message twice → one extra harmless raw object; single
   normalized/current-state/receipt; identical diff.
6. **Immutability:** confirm S3 versioning OFF; two fetches same day → two distinct `raw` keys, neither
   overwritten.
7. **Barrier:** slow one collector past first drain check → DrainBarrier Wait-loops, then proceeds
   once receipt-or-DLQ covers all companies; no company diffed before its collection resolves.
8. **Cost:** modeled monthly cost at 3 providers × 20 companies × 1 run/day < $5 (cost seat owns the
   number; CloudWatch log retention is the main lever).
```
