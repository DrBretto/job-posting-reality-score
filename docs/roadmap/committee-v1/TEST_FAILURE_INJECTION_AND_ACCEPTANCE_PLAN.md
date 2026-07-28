# Test, Failure-Injection & Acceptance Plan — Job Posting Reality Score

> Seat: `ADHOC-RELIABILITY-OBSERVABILITY-ENGINEER`. Roadmap only. Companion:
> `RELIABILITY_OBSERVABILITY_AND_OPERATIONS_RUNBOOK.md`.
>
> **Division of labor is fixed:** all **fixtures, corrected payloads, handler versions, IAM
> policies, and expected-evidence checklists are AI-prepared IN ADVANCE** (`AI_IMPLEMENTATION`).
> **Every console action — sending messages, watching metrics, redriving — is Brett-manual**
> (`BRETT_MANUAL_AWS`); that manual act is the recall-rebuilding telos. Verification is
> `SHARED_VERIFY` against concrete evidence, never a reported "pass."
>
> AWS mechanics verified 2026-07-28 against primary docs (URLs in the runbook, §0).

---

## 1. Fixture & acceptance approach

- **Fixtures live in the repo, not in prod paths.** Each fixture is a small JSON file plus a
  one-line description of the failure it induces and the exact evidence that proves each stage.
- **Acceptance is evidence-based.** A step passes only when the named CloudWatch metric,
  log line, queue depth, or S3 object is *observed* — the memory-of-what-AWS-does note in
  `MEMORY.md` ("verify by OPENING the rendered artifact, never a reported PASS") applies here.
- **Deliberate-failure exercises are the point**, not incidental QA — the recall telos "lives
  largely here." Every phase ships with at least one injection whose observation refreshes a
  specific AWS concept.
- **Fixtures never touch immutable raw.** Failure labs write to a `test/` prefix or a throwaway
  queue pair so no lab pollutes production `raw/` history.

---

## 2. THE FIRST SQS/DLQ LAB — send a malformed job event, watch retry → DLQ → fix → redrive

This is the crown-jewel exercise and the exact capability Brett blanked on in interview. It is
specified end-to-end. Everything Brett types/clicks is manual; AI supplies the two fixtures and
the two handler versions in advance.

### 2.0 Pre-staged by AI (`AI_IMPLEMENTATION`)
- **Collector v1** handler that, on a record missing the required `company` field (or otherwise
  malformed), **throws / returns it in `batchItemFailures`** — i.e. treats it as poison.
- **Collector v2** hardened handler that validates the record, logs a structured
  `invalid_task` record, and **returns success** (drains the message) instead of choking — so a
  redrive of the original message genuinely succeeds.
- **Malformed fixture** `poison_missing_company.json` — a CollectTask body missing `company`.
- Expected-evidence checklist (below), and the least-privilege redrive IAM policy.

### 2.1 Environment Brett builds by hand first (`BRETT_MANUAL_AWS`)
CollectQueue (standard) + CollectDLQ (standard); DLQ wired via **Edit → Dead-letter queue →
Enabled**, **Maximum receives = 2** (lab uses 2 for speed; prod uses 3); CollectQueue
**visibility timeout = 6× the Collector timeout**; Collector deployed as **v1**; event source
mapping enabled with **`ReportBatchItemFailures`** function response type.

### 2.2 The lab, step by step

**Step 0 — Baseline the wiring.**
- *Brett does:* On CollectQueue, open **Dead-letter queue** section; confirm DLQ ARN + **Maximum
  receives = 2**; confirm visibility timeout ≈ 6× function timeout; confirm the ESM is Enabled
  with ReportBatchItemFailures.
- *Observes:* the redrive policy settings on the queue.
- *CloudWatch evidence:* n/a (config screen); note both queues show depth 0.
- *Concept refreshed:* **redrive policy / `maxReceiveCount`**, and why visibility timeout must be
  ≥ 6× function timeout (premature redelivery vs slow retry loop).

**Step 1 — Send the malformed message.**
- *Brett does:* CollectQueue → **Send and receive messages** → paste `poison_missing_company.json`
  into the body → **Send message**.
- *Observes:* CollectQueue "Messages available" blips 1, then the ESM poller picks it up.
- *CloudWatch evidence:* CollectQueue **`NumberOfMessagesSent` +1**; a brief
  **`ApproximateNumberOfMessagesVisible`** bump.
- *Concept refreshed:* producing to a queue; the **event source mapping poller** invoking Lambda
  synchronously with a batch.

**Step 2 — Watch the retry behavior.**
- *Brett does:* open the Collector **CloudWatch Logs** log group; watch for repeated invocations.
- *Observes:* the same `task_id`/`correlation_id` logged failing to parse ~3 times (initial +
  redeliveries), each spaced by roughly the visibility timeout; `attributes.ApproximateReceiveCount`
  climbs 1 → 2.
- *CloudWatch evidence:* Collector **`Errors`** increments per failed receive; log events show
  rising **`ApproximateReceiveCount`**; because v1 returns the item in `batchItemFailures`, only
  that message redelivers (not a whole-batch replay).
- *Concept refreshed:* **at-least-once delivery**, `ApproximateReceiveCount`, **visibility
  timeout controls redelivery spacing**, and **`ReportBatchItemFailures`** isolating the one bad
  record (verified: `batchItemFailures[].itemIdentifier` = `messageId`).

**Step 3 — Verify arrival in the DLQ.**
- *Brett does:* after receive count exceeds Maximum receives (2), open **CollectDLQ** → **Poll
  for messages** → open the message.
- *Observes:* CollectQueue depth → 0; CollectDLQ depth → 1; the DLQ message shows the malformed
  body and its attributes.
- *CloudWatch evidence:* CollectDLQ **`ApproximateNumberOfMessagesVisible` = 1**; **Alarm A1
  (DLQ not empty) transitions to ALARM → SNS email**.
- *Concept refreshed:* the **DLQ as poison isolation**; the **DLQ-not-empty alarm is how you
  learn about it** (you don't discover poison by luck).

**Step 4 — Correct the failure (root-cause, not paper over).**
- *Brett does:* diagnose from the DLQ body + logs (missing `company`). Then **deploy Collector
  v2** (the hardened handler). *(This is the canonical flavor: the message itself can't be
  edited in place, so the fix is code that now processes it cleanly. See §2.3 for the alt
  IAM-permission flavor.)*
- *Observes:* new Collector version published; queues still idle.
- *CloudWatch evidence:* Lambda console shows v2 as the ESM target; no new errors yet.
- *Concept refreshed:* **root-cause from DLQ contents + logs**; the DLQ is a debugging tool
  ("examine logs / analyze contents / determine whether the consumer had enough time" —
  verified DLQ purpose).

**Step 5 — Redrive the message.**
- *Brett does:* CollectDLQ → **Start DLQ redrive** → **Redrive to source queue(s)** → **Velocity:
  System optimized** → **Redrive messages**.
- *Observes:* CollectDLQ depth → 0; message re-enters CollectQueue (new `messageID`/`enqueueTime`,
  retention reset — verified); v2 Collector processes it and **deletes** it.
- *CloudWatch evidence:* CollectDLQ depth → 0; CollectQueue **`NumberOfMessagesSent` +1** then
  **`NumberOfMessagesDeleted` +1**; Collector log shows a successful invocation for that
  `task_id`; **Alarm A1 returns to OK**.
- *Concept refreshed:* **DLQ redrive** (`StartMessageMoveTask` under the hood), **redrive to
  source vs custom destination**, **velocity control** (System optimized / Custom max ≤ 500
  msg/s), and **messageID/retention reset** on redrive.

### 2.3 Alternate flavor (run after §2.2, or instead, for IAM recall)
Poison induced by an **IAM misconfig**: Collector v1 lacks `s3:PutObject` on the raw bucket →
throws `AccessDenied` on every receive → DLQ. Fix = attach the least-privilege `s3:PutObject`
statement (`AI_IMPLEMENTATION` supplies it) → redrive the *original* message → it now writes the
snapshot and drains. Refreshes **least-privilege IAM** alongside the DLQ path. Both flavors end
with the same redrive muscle-memory.

### 2.4 Lab acceptance (all must be observed)
- [ ] CollectDLQ depth went 0 → 1 → 0.
- [ ] Alarm A1 fired then cleared.
- [ ] `ApproximateReceiveCount` was observed climbing across redeliveries.
- [ ] After redrive, a success log line + (flavor-dependent) a `test/` snapshot exists for the
      `task_id`.
- [ ] Brett can **explain aloud**, unprompted: `maxReceiveCount`, visibility timeout's role,
      `ReportBatchItemFailures`, and the redrive path — the interview gap, closed.

---

## 3. Per-phase deliberate-failure exercises

Phases are the reliability-relevant reconstruction order; the architecture seat owns final phase
boundaries. Each exercise: injection → observation → concept.

| Phase | Build milestone | Deliberate-failure exercise | Observe / evidence | Concept refreshed |
|---|---|---|---|---|
| **P0 — Foundations** | S3 raw bucket + Collector Lambda + IAM, invoked manually | Invoke Collector with an IAM role missing `s3:PutObject` | `AccessDenied` in logs; no object written | Least-privilege IAM; reading a permission error |
| **P1 — SQS collection** | CollectQueue + DLQ + ESM | **The full §2 SQS/DLQ poison lab** | DLQ 0→1→0; A1 fires/clears | `maxReceiveCount`, visibility timeout, `ReportBatchItemFailures`, redrive |
| **P2 — Scheduling** | EventBridge Scheduler → Dispatcher | (a) Disable the schedule for a day; (b) point the target at a failing Dispatcher | (a) **A2 missed-run alarm** fires (no `CollectRunSuccess`); (b) Scheduler retry + Scheduler DLQ (UNVERIFIED — confirm) | Custom success-heartbeat as missed-run detector; NO-RUN ≠ quiet |
| **P3 — Orchestration** | ReportAssembler Step Functions | Force one assembly task to fail (bad input / throw) | SFN console shows **Retry** attempts then **Catch → `report_incomplete`**; report labels that source degraded; A7 fires | SFN `Retry`/`Catch`, `States.TaskFailed`, partial-run reporting |
| **P4 — Change detection & THE INVARIANT** | Diff vs last successful snapshot | (a) Source returns `200 OK` empty/short body; (b) one genuine posting removed; (c) one source fails entirely | (a) source marked **SUSPECT**, **A6** fires, **zero** removal events; (b) `candidate-removed` → `removed` only after N=2 successful snapshots; (c) report **INCOMPLETE**, source named, jobs carried `stale` not `removed` | Successful-snapshot precondition, disappearance grace, mass-drop guard — **source failure never = mass disappearance** |
| **P5 — Historical / analytics** *(later)* | Parquet + Athena over raw | Delete/corrupt a derived table, rebuild from immutable raw | Rebuilt table matches; raw untouched | Raw is source of truth; **replay from immutable raw**; derived is disposable |
| **P6 — Ops hardening / game day** | Full system | Simultaneous: fill the DLQ, kill a source, skip a schedule | A1, A6, A2 each fire **independently**; report correctly labeled INCOMPLETE; no false mass-removal | Alarms are orthogonal; the whole invariant holds under compound failure |

---

## 4. Standing acceptance tests (checkable, beyond the per-phase injections)

**Idempotency & duplicates**
- [ ] Send the *same* valid CollectTask twice → exactly one `raw/.../{run_id}/snapshot.json`,
      identical content; no duplicate change events.
- [ ] Redeliver a message mid-processing (force a timeout once) → no double-counted postings.

**The critical invariant**
- [ ] A day where all sources succeed and nothing changed → report reads **VERIFIED QUIET**.
- [ ] A day where the scheduler is disabled → **no** "quiet" report is produced; **A2** fires
      (NO-RUN detected).
- [ ] A day where 1 of 3 sources fails → report **INCOMPLETE**, names the failed source,
      reports changes only for the 2 that succeeded, emits **zero** removals for the failed one.
- [ ] A source returning empty `200` → **SUSPECT**, A6 fires, no mass-removal events.

**Retry ownership**
- [ ] Transient ATS 503 within one fetch → connector retries in-handler and succeeds without a
      second SQS receive (`ApproximateReceiveCount` stays 1).
- [ ] Unrecoverable handler error → SQS redelivers to `maxReceiveCount` then DLQ (SQS owns it),
      and Step Functions does **not** re-invoke the collector.
- [ ] Assembly transient failure → Step Functions `Retry` resolves it without operator action.

**Alarms & observability**
- [ ] Each alarm A1–A7 can be individually driven to ALARM by its matching injection and returns
      to OK after remediation.
- [ ] Dashboard shows last-run heartbeat, DLQ depth, per-source status, and MTD cost.

**Replay & retention**
- [ ] Any derived report regenerates byte-comparable from `raw/` alone.
- [ ] Lifecycle expiry is configured (versioning OFF, per operator rule); DLQ retention > source
      retention.

**Teardown**
- [ ] Full teardown checklist (runbook §8.3) leaves zero billable resources and no
      `INSUFFICIENT_DATA` orphan alarms.

---

## 5. Assumptions & open items
- Lab uses `maxReceiveCount = 2` for speed; production uses 3. Visibility timeout must track
  6× the (possibly-changed) function timeout — recompute if the Collector timeout moves.
- P2 Scheduler retry/DLQ specifics and any native missed-invocation metric are **UNVERIFIED** —
  A2's custom-heartbeat approach does not depend on them, but confirm before relying on Scheduler
  DLQ (A8).
- Fixtures are AI-prepared; the data seat must confirm its differ honors the §5-runbook gates so
  P4's tests exercise the real code path, not a parallel reimplementation.
