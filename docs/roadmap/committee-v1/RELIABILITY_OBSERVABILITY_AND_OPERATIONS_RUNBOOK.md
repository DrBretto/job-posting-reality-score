# Reliability, Observability & Operations Runbook — Job Posting Reality Score

> Seat: `ADHOC-RELIABILITY-OBSERVABILITY-ENGINEER`. Roadmap document only — no AWS
> resources are created or code deployed here. Companion file:
> `TEST_FAILURE_INJECTION_AND_ACCEPTANCE_PLAN.md`.
>
> Ownership vocabulary (from `_SHARED_CONTEXT.md`): `BRETT_MANUAL_AWS` (Brett does it by
> hand in the console — this is what rebuilds recall) / `AI_IMPLEMENTATION` (AI prepares
> code/policy/schema/fixtures in advance) / `SHARED_VERIFY` (both confirm against evidence).

---

## 0. Verified-fact provenance

All AWS mechanics below were checked against primary AWS documentation on **2026-07-28**,
region assumption **us-east-1**. Source URLs:

- SQS DLQ / `maxReceiveCount` / redrive policy: `docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html`
- Configure DLQ (console, Maximum receives 1–1000): `.../sqs-configure-dead-letter-queue.html`
- DLQ redrive (Start DLQ redrive, velocity, `StartMessageMoveTask`, IAM): `.../sqs-configure-dead-letter-queue-redrive.html`
- Lambda + SQS event source mapping (visibility timeout, at-least-once, batching): `docs.aws.amazon.com/lambda/latest/dg/with-sqs.html`
- Lambda SQS error handling / `ReportBatchItemFailures` / `batchItemFailures`: `.../services-sqs-errorhandling.html`
- Step Functions error handling (Retry/Catch, `States.*`): `docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html`

**UNVERIFIED (must confirm before build):**
- EventBridge Scheduler native "missed invocation" metric/alarm. Primary docs for Scheduler
  missed-run detection were **not** fetched this pass. Design below does NOT rely on a native
  metric — it uses a **custom success-heartbeat alarm** (§6.2) which is provider-agnostic.
- Scheduler target-delivery retry policy + Scheduler DLQ specifics (`MaximumRetryAttempts`,
  `MaximumEventAgeInSeconds`, dead-letter config) — treat as UNVERIFIED until confirmed.
- Exact CloudWatch cost of custom metrics/alarms under free tier — confirm against Billing.

---

## 1. Reference architecture (reliability view)

The data/architecture seats own the canonical topology; this is the reliability-relevant
skeleton the runbook assumes. Flag any divergence back to those seats.

```
EventBridge Scheduler (daily, UTC)                 EventBridge Scheduler (daily + offset)
        │ input = { run_id }                                │ input = { run_id }
        ▼                                                    ▼
  Dispatcher (Lambda or SFN)                           ReportAssembler (Step Functions, Standard)
   - writes RUN_OPEN manifest (run_id,                  - reads manifest + SUCCESS sentinels
     expected [provider,company] tasks)                 - Map over companies: diff vs last
   - enqueues 1 CollectTask msg / task                    SUCCESSFUL snapshot
        │                                                - Retry/Catch → report_incomplete
        ▼                                                - emits daily report + ReportComplete=1
  CollectQueue (SQS standard) ── redrive policy ──► CollectDLQ (SQS standard)
        │  event source mapping (ReportBatchItemFailures)        │ alarm: depth ≥ 1
        ▼                                                        ▼
  Collector (Lambda, thin)                                 (operator inspects + redrives)
   - fetch sanctioned ATS API (Greenhouse/Lever/Ashby)
   - connector-level bounded retry (transient only)
   - write IMMUTABLE raw snapshot to S3 (key per run_id)
   - write per-task SUCCESS sentinel + CollectRunSuccess=1 metric
```

Why each moving part earns its place:
- **SQS + DLQ** — genuine work distribution + poison isolation; also the primary recall target
  (Brett blanked on the DLQ path). Not bolted on: it is the collection fan-out.
- **Step Functions (Standard)** — owns *report-assembly* orchestration only: Map over
  companies, Retry transient task failures, Catch → degraded-report path, partial-run reporting.
- **EventBridge Scheduler** — the only always-on trigger; two schedules (collect, then assemble
  after an offset) so completeness is evaluated against a settled queue.
- **S3** — immutable raw snapshots (the source of truth + the backup) + derived reports.
- **CloudWatch + SNS** — alarms and the one operator dashboard.

---

## 2. Correlation, run IDs, idempotency, duplicate suppression

| Decision | DEFAULT | OWNER | TRIGGER (revisit when…) |
|---|---|---|---|
| Run identity | `run_id` = scheduled UTC date, `YYYY-MM-DD`. One run per day, deterministic from the schedule. Passed as Scheduler target input. | AI_IMPLEMENTATION (schema) / SHARED_VERIFY | Move to sub-daily cadence → switch to `YYYY-MM-DDThh` or a ULID minted by the Scheduler input transformer. |
| Correlation ID | `correlation_id` = `run_id`; stamped into every SQS message (`MessageAttributes.correlation_id`), every structured log line, and S3 object metadata. SFN execution name = `run_id`. | AI_IMPLEMENTATION | Fan-out beyond one run/day, or need per-task tracing → add `task_id` as the span-level correlator. |
| Task identity | `task_id` = `{run_id}:{provider}:{company_slug}`. | AI_IMPLEMENTATION | New source dimensions (e.g. per-department) → extend the tuple. |
| Idempotency key | Collector idempotency key = `task_id`. Raw snapshot written to **deterministic key** `raw/{provider}/{company}/{run_id}/snapshot.json`. Re-delivery re-writes the same key with the same content → no double-count. | AI_IMPLEMENTATION / SHARED_VERIFY | If snapshots ever become append-style, add an explicit idempotency ledger (e.g. conditional PutObject / a processed-`task_id` marker). |
| Duplicate suppression | Correctness comes from deterministic S3 keys (last-writer-wins, identical payload). Optimization: Collector checks for a fresh SUCCESS sentinel for `task_id` and skips re-fetch. | AI_IMPLEMENTATION | If ATS calls become expensive/rate-limited, make the skip mandatory (dedupe before fetch). |

Rationale: Lambda SQS event source mappings are **at-least-once** and "duplicate processing of
records can occur" (verified) — AWS "strongly recommend that you make your function code
idempotent." Deterministic keys make duplicate delivery a no-op instead of a data bug.

---

## 3. Timeouts, retry OWNERSHIP, concurrency, throttling

**The retry-ownership model — each layer owns exactly one kind of retry (no overlap):**

| Failure class | Who retries | Mechanism | Ceiling |
|---|---|---|---|
| Transient source blip (HTTP 429/5xx, socket reset) *within one fetch* | **The connector (inside the Collector Lambda)** | Bounded exponential backoff + jitter in the handler; reuse the CFR Bedrock-wrapper's retry/throttle shape | ~3 in-handler attempts, must return within Lambda timeout |
| Connector exhausted / unexpected error on a message | **SQS (event source mapping)** | Message returned via `ReportBatchItemFailures` → visible again after visibility timeout → redelivered until `maxReceiveCount` → CollectDLQ | `maxReceiveCount` (default **3**) |
| Poison message (never processable) | **SQS → DLQ** | Isolated in CollectDLQ; operator redrives after fix | terminal until human acts |
| Report-assembly task failure (transient) | **Step Functions** | `Retry` on `Lambda.ServiceException`, `Lambda.SdkClientException`, `States.TaskFailed` with backoff | `MaxAttempts` 2–3, then Catch |
| Report-assembly unrecoverable | **Step Functions Catch** | `Catch` `States.ALL` → `report_incomplete` state | terminal → degraded report |
| Scheduler target delivery failure | **EventBridge Scheduler** | Scheduler retry policy + (optional) Scheduler DLQ — **UNVERIFIED**, confirm | per Scheduler config |

**Rule of thumb the model enforces:** *SQS never retries what Step Functions is retrying, and
Step Functions never retries the collectors.* Collectors live behind SQS; assembly lives behind
Step Functions. Crossing them (e.g. an SFN Map that also invokes collectors with its own retry
on top of SQS redelivery) is a design smell to reject.

| Decision | DEFAULT | OWNER | TRIGGER |
|---|---|---|---|
| Lambda function timeout (Collector) | 30 s (thin fetch + PutObject; heavy work banned per operator rule) | AI_IMPLEMENTATION | ATS pagination pushes p99 near ceiling → raise, or split fetch/persist. |
| Queue visibility timeout | **≥ 6× function timeout** (AWS best practice) → 180 s for a 30 s function | BRETT_MANUAL_AWS (sets it) / SHARED_VERIFY | Function timeout changes → recompute 6×. Too low = premature redelivery + false DLQ; too high = slow retry loop in the lab. |
| `maxReceiveCount` | **3** in production; **2** for the SQS/DLQ lab (faster failure) | BRETT_MANUAL_AWS | Flaky-but-recoverable source inflates DLQ → raise; genuinely-poison inputs → keep low. |
| Partial batch response | `ReportBatchItemFailures` ON so one bad message can't force the whole batch to redeliver | AI_IMPLEMENTATION (handler) / BRETT_MANUAL_AWS (ESM flag) | — |
| Max concurrency / source throttling | Reserved concurrency on Collector = small (e.g. 2–5) to protect ATS APIs and cost; batch size default 10; at learning scale (3 companies) this is trivially bounded | BRETT_MANUAL_AWS | Company count grows → raise reserved concurrency deliberately, watch ATS rate limits. |
| DLQ retention | **Longer** than source-queue retention (AWS best practice; DLQ `ApproximateAgeOfOldestMessage` reflects move-time, not original enqueue) — e.g. source 4 days, DLQ 14 days | BRETT_MANUAL_AWS | — |

---

## 4. Poison messages, Catch paths, partial-run reporting

- **Poison behavior:** a message that fails `maxReceiveCount` receives lands in CollectDLQ,
  isolated, alarmed (§6.1), and never silently dropped. The Collector must be idempotent so
  redelivery during retries is safe.
- **Handler contract:** the Collector catches all exceptions per record and returns failed
  records in `batchItemFailures` as `itemIdentifier` = the SQS `messageId` (verified shape). A
  thrown exception = whole batch fails (verified) — so the handler must not let one bad record
  throw out of the loop unless we intend the whole batch to redeliver.
- **Step Functions Catch (assembly):** every `Task`/`Map` state carries
  `Retry` (transient) then `Catch [States.ALL] → report_incomplete`. `States.Runtime` is
  **not** catchable by `States.ALL` (verified) — assembly code must avoid null-path errors.
- **Partial-run reporting:** ReportAssembler's Map over companies uses per-item tolerance: a
  single company's assembly failure marks that company `degraded` in the report and continues;
  it does not fail the whole run. The report explicitly lists degraded sources by name.

---

## 5. THE CRITICAL INVARIANT — quiet report vs. no-run, and source-failure ≠ mass disappearance

This is the load-bearing reliability requirement. Two distinct guarantees:

### 5.1 A quiet report must distinguish "nothing changed" from "collectors did not run"

Three mutually-exclusive daily outcomes, never collapsed:

1. **VERIFIED QUIET** — *every* expected source in the RUN_OPEN manifest produced a **successful
   snapshot** for `run_id`, and no material changes were found. Only this state is allowed to
   render as "all quiet."
2. **INCOMPLETE / DEGRADED** — the run happened but ≥ 1 expected source lacks a successful
   snapshot. The report is labeled INCOMPLETE and **names the failed sources**. Changes are
   reported only for sources that succeeded.
3. **NO-RUN** — no manifest exists for the expected `run_id` (the scheduler didn't fire, or the
   dispatcher died before writing the manifest). Caught by the **missed-run watchdog** (§6.2),
   not by the report — the report can't report on a run that never opened.

**Successful-snapshot precondition (the enforcer):** ReportAssembler MUST NOT emit "verified
quiet" for a source unless a fresh SUCCESS sentinel exists for `{run_id, source}`. The sentinel
is written by the Collector *only after* the raw snapshot is durably in S3. Absence of sentinel
→ that source is INCOMPLETE, full stop. No LLM, and no "probably fine" heuristic, may substitute
for the sentinel (canon: LLM output is never evidence).

### 5.2 Source failure must NEVER masquerade as mass job disappearance

- **Disappearance precondition:** a job may be counted "disappeared" for a source **only when
  that source produced a successful snapshot this run** and the job was present in that source's
  most-recent-*successful* prior snapshot but absent from the new successful snapshot. A source
  with no successful snapshot this run contributes **zero** disappearance events — its jobs are
  carried forward as `stale/unknown`, never `removed`.
- **Disappearance grace rule:** a job first seen absent is marked `candidate-removed / pending`
  and is promoted to `removed` only after absence in **N consecutive successful snapshots**
  (DEFAULT N=2). Absorbs a single flaky-but-200 truncated response.
- **Mass-drop guard:** if a successful snapshot's posting count drops beyond a threshold vs the
  prior successful snapshot (DEFAULT: to zero, or a > 60% drop), the source is marked `SUSPECT`
  for that run — **no** removal events are emitted, and a source-health alarm fires. This blocks
  a `200 OK` + empty/short body from reading as mass deletion.
- **Coordination with the data seat:** the data seat owns the change-event schema and diff
  algorithm. This seat owns the *gates*: (a) successful-snapshot precondition, (b)
  consecutive-absence grace N, (c) mass-drop SUSPECT threshold. These must be inputs the data
  seat's differ honors, not reimplemented separately.

| Decision | DEFAULT | OWNER | TRIGGER |
|---|---|---|---|
| Successful-snapshot precondition | sentinel required per source before any "quiet"/removal claim | AI_IMPLEMENTATION / SHARED_VERIFY | never relax |
| Grace N (consecutive-absence) | 2 | AI_IMPLEMENTATION | tune after observing real ATS flakiness rates |
| Mass-drop SUSPECT threshold | zero or > 60% drop | AI_IMPLEMENTATION | per-source volatility differs → per-source thresholds |

---

## 6. Alarm set (alarm → condition → action)

SNS topic `jprs-ops-alerts` → email to operator. All alarms `BRETT_MANUAL_AWS` to create,
`AI_IMPLEMENTATION` supplies exact thresholds/metric math.

| # | Alarm | Condition | Action / meaning |
|---|---|---|---|
| A1 | **DLQ not empty** | `ApproximateNumberOfMessagesVisible` (CollectDLQ) ≥ 1 for 1 datapoint | Email. A message is poison — inspect + redrive (§8 procedure). |
| A2 | **Missed run / stale data** | Custom metric `CollectRunSuccess` **missing or 0** over the daily window; alarm `treatMissingData = breaching` | Email "collectors did not run." This is the NO-RUN detector (does not depend on a native Scheduler metric). |
| A3 | **Report not assembled** | Custom metric `ReportComplete` missing/0 over the assemble window; `treatMissingData = breaching` | Email "no report today." Distinguishes assembly failure from quiet day. |
| A4 | **Queue backing up** | `ApproximateAgeOfOldestMessage` (CollectQueue) > 3× visibility timeout | Email. Collectors stuck/throttled. |
| A5 | **Collector errors** | Lambda `Errors` (Collector) ≥ 1 sustained, or `Throttles` ≥ 1 | Email. Code/permission/ATS problem before it reaches the DLQ. |
| A6 | **Source degraded / mass-drop** | Custom metric `SourceSuspect` ≥ 1 (emitted by §5.2 guard) | Email. A source returned suspiciously few postings — removals suppressed. |
| A7 | **Assembly execution failed** | Step Functions `ExecutionsFailed` ≥ 1 | Email. Assembler hit Catch/unhandled error. |
| A8 | **Scheduler delivery failed** *(if Scheduler DLQ configured — UNVERIFIED)** | Scheduler DLQ depth ≥ 1 | Email. Trigger never reached its target. |

`NumberOfMessagesSent/Received/Deleted` (verified metric names) power the dashboard trends; a
drop in `NumberOfMessagesDeleted` to 0 signals the handler isn't returning failures correctly.

---

## 7. Dashboards, report-completeness, replay, retention

**Operator dashboard** (one CloudWatch dashboard, `AI_IMPLEMENTATION` supplies JSON,
`BRETT_MANUAL_AWS` creates):
- Last successful-run heartbeat (time since `CollectRunSuccess=1`).
- CollectQueue depth + `ApproximateAgeOfOldestMessage`.
- **CollectDLQ depth** (the number that should always be 0).
- Collector `Errors` / `Throttles` / `Invocations`.
- Per-source successful-snapshot status (today).
- `ReportComplete` status; SFN `ExecutionsFailed`.
- Month-to-date estimated charges widget (cost guard, < $5/mo target).

**Report-completeness check:** ReportAssembler computes `expected_sources` (from manifest) vs
`succeeded_sources` (from sentinels); emits `ReportComplete=1` only when a report was produced
for a fully-accounted run, and always records the completeness ratio in the report header.

**Replay from immutable raw:** raw snapshots are **write-once** — deterministic key per
`run_id`, never re-PUT. Per operator hard rule, **S3 versioning stays OFF**; immutability is
enforced by (a) key-per-run convention, (b) a bucket policy denying overwrite/delete of
`raw/*` to the app roles, (c) lifecycle for expiry (not versioning). All derived artifacts
(diffs, reports, later Parquet/Athena tables) are **rebuildable** by re-running the assembler
over raw. Raw is the source of truth *and* the backup; derived data is disposable.

**Retention (lifecycle, not versioning):**

| Data | DEFAULT retention | OWNER | TRIGGER |
|---|---|---|---|
| `raw/` snapshots | 400 days → expire (or Glacier transition) | BRETT_MANUAL_AWS | analytics needs deeper history → extend before first expiry |
| `derived/` reports | 90 days (regenerable) | BRETT_MANUAL_AWS | — |
| CollectQueue msgs | 4 days | BRETT_MANUAL_AWS | — |
| CollectDLQ msgs | 14 days (> source) | BRETT_MANUAL_AWS | — |
| CloudWatch Logs | 30 days | BRETT_MANUAL_AWS | cost/debug tradeoff |

---

## 8. Operational flows

### 8.1 Daily operator flow (~2 min)
1. Read the daily report. Confirm its label: **VERIFIED QUIET** / **changes listed** /
   **INCOMPLETE(sources named)**.
2. Glance at the dashboard: last-run heartbeat is today; **CollectDLQ depth = 0**; no alarm in
   ALARM.
3. If INCOMPLETE → note which source failed; if it's a transient ATS outage, no action (grace
   rule protects the data). If persistent, open the source-health item.
4. If A1 (DLQ) fired → run the redrive procedure (§8.4).

### 8.2 Weekly maintenance flow (~15 min)
1. CollectDLQ empty? If not, drain via redrive after root-cause.
2. Billing → month-to-date vs < $5 target; investigate any anomaly.
3. Source-health trend: any source repeatedly INCOMPLETE/SUSPECT → check ATS API schema drift
   (Greenhouse/Lever/Ashby response shape) against the parser.
4. Confirm all alarms are in OK and none are `INSUFFICIENT_DATA` unexpectedly.
5. Spot-check one raw snapshot opens and one report regenerates from raw (replay sanity).

### 8.3 Full teardown checklist (leave zero cost)
1. **Disable both EventBridge Scheduler schedules** → confirm no further invocations next window.
2. Delete the Collector **event source mapping**.
3. **Empty then delete** CollectQueue and CollectDLQ.
4. Delete Step Functions state machine(s).
5. Delete Collector + Dispatcher Lambdas and their log groups.
6. Delete CloudWatch **alarms + dashboard**; delete SNS topic + subscriptions.
7. **Empty then delete** S3 buckets (export `raw/` first if keeping history; respect lifecycle).
8. Delete IAM roles/policies created for the system (least-privilege ones only).
9. Confirm **$0** on next Billing cycle; confirm no lingering `INSUFFICIENT_DATA` alarms.

### 8.4 DLQ inspect + redrive procedure (verified console path)
1. SQS console → **Queues** → open **CollectDLQ**.
2. **Poll for messages** → read the poison body + `ApproximateReceiveCount` + attributes;
   cross-reference `correlation_id`/`task_id` in the Collector log group to root-cause.
3. Fix root cause (deploy hardened handler, fix IAM/env, or correct upstream data — see the
   lab flavors in the companion file).
4. On CollectDLQ → **Start DLQ redrive** → **Message destination: Redrive to source queue(s)**
   → **Velocity: System optimized** (or Custom max velocity for large batches; max 500 msg/s) →
   **Redrive messages**.
5. Watch CollectDLQ depth → 0, CollectQueue receives the message (new `messageID`/`enqueueTime`
   — retention resets), Collector processes it successfully, A1 returns to OK.
6. IAM note: the redrive principal needs `sqs:StartMessageMoveTask`, `sqs:CancelMessageMoveTask`,
   `sqs:ListMessageMoveTasks`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`,
   `sqs:GetQueueAttributes`, `sqs:ListDeadLetterSourceQueues` on the DLQ and `sqs:SendMessage`
   on the destination (verified). `AI_IMPLEMENTATION` supplies this least-privilege policy.

---

## 9. Assumptions & open coordination

**Assumptions:** single AWS account, us-east-1; learning scale 1 provider × 3 companies × 1
daily run (trivially within free-tier concurrency); sanctioned ATS public APIs only; two
schedules (collect + assemble-after-offset) rather than event-driven completion, chosen for
simplicity and deterministic completeness evaluation at tiny scale.

**Open questions for other seats:** see the return summary — the data seat owns the diff/event
schema that must honor §5's gates; the architecture seat owns whether Dispatcher is a Lambda or
a Step Functions state; the security/IAM seat owns the exact least-privilege policies referenced
here; the cost seat owns confirming custom-metric/alarm charges stay within < $5/mo.
