# Job Posting Reality Score — Master Roadmap

> **This is the primary operator document.** Work phase-by-phase from this file. It summarizes the
> committee's settled architecture and every phase's build; dip into the specialist appendices only
> for depth. Roadmap only — no AWS resources are created by this document. Brett performs every
> console create/wire/deploy/verify by hand; AI hands him prepared code/policy/schema/SQL in advance.
>
> Synthesized by `STABLE-001` (Analyst) from six specialist seats. Companion files:
> `ARCHITECTURE_DECISION_REGISTER.tsv`, `PHASED_IMPLEMENTATION_BACKLOG.tsv`, `COMMITTEE_VERDICT.md`,
> `PROJECT_CHARTER_AND_SUCCESS_CRITERIA.md`, `REPO_REUSE_AND_MIGRATION_DECISION.md`.
> Appendices by seat: `REFERENCE_ARCHITECTURE.md`, `SECURITY_AND_THREAT_MODEL.md`,
> `RELIABILITY_OBSERVABILITY_AND_OPERATIONS_RUNBOOK.md`, `TEST_FAILURE_INJECTION_AND_ACCEPTANCE_PLAN.md`,
> `DATA_MODEL_AND_HISTORY_SPEC.md`, `SCORING_AND_EVIDENCE_SPEC.md`,
> `SOURCE_CONNECTOR_AND_COMPLIANCE_SPEC.md`, `COST_MODEL_AND_GUARDRAILS.md`,
> `AWS_MANUAL_BUILD_WORKBOOK.md`, `EXPANSION_AND_PRODUCT_EVOLUTION.md`.
> Audit & governance companions: `PANEL_DISSENT.md` (Skeptic audit — **read before building**;
> the committee verdict is PASS WITH CONDITIONS, five must-clear conditions in §8 below),
> `SOURCE_REGISTER.md` (every external fact + verification status), `WRITING_TOOL_SELECTION_LEDGER.md`,
> `ROUTING_RECEIPT.md`.

---

## Table of contents

1. Decision summary — the settled architecture in one page
2. Where am I? — status table (phase | goal | status | done-gate)
3. First five sessions — launch sequence
4. The honesty boundary (read before building anything)
5. Settled internals (the concrete decisions the phases assume)
6. The phases, P0 → P10 (full build spec each)
7. Cost, teardown, and the two silences
8. Committee conditions to clear (PASS WITH CONDITIONS)

---

## 1. Decision summary — the settled architecture

A low-cost, serverless, single-account **us-east-1** system that collects selected company job boards
once a day from **sanctioned public ATS APIs**, preserves **immutable posting snapshots** in S3, and
reports **what materially changed** — with a hard line between observable posting *behavior* and any
accusation that a job is fake/real.

**The daily flow (two schedules — see ADR-06):**

```
EventBridge Scheduler #1 (collect, daily, tz America/New_York)
   -> jprs-enumerate Lambda: reads company/board config (SSM), writes RUN_OPEN manifest, SQS fan-out
        (one message per company: {run_id, provider, board_token, company_id})
   -> SQS jprs-collect-queue --(event-source-mapping, ReportBatchItemFailures)--> jprs-collector Lambda
        fetch ONE board -> write immutable raw + receipt BEFORE parse -> map canonical -> write
        normalized + update current/_source_status; emit CollectRunSuccess metric
        on failure: redeliver until maxReceiveCount=3 -> jprs-collect-dlq (A1 alarm)

EventBridge Scheduler #2 (assemble, daily + fixed offset)
   -> Step Functions STANDARD jprs-daily-assemble (Map over companies + Retry + Catch)
        completeness judged by manifest-expected vs SUCCESS sentinels (NEVER wall-clock)
        -> jprs-differ: diff today vs most-recent-SUCCESS snapshot, emit change events, advance current
        -> jprs-report: assemble daily report (CHANGED / NO-CHANGE / NOT-COLLECTED per company) + scorecards
        -> SES digest (report persisted to S3 regardless of send)
   Catch States.ALL -> report_incomplete

CloudWatch alarms A1-A7 -> SNS jprs-ops-alerts -> email.  Bedrock narrator = separate llm-role Lambda, OFF in V1.
```

**Storage = S3-only, one bucket, versioning OFF, five tiers** (immutability by write-once keys +
lifecycle, never versioning): `current/`, `raw/`, `normalized/`, `events/`, `reports/` (+ later
`parquet/`, `athena-results/`). No DynamoDB, no NAT/VPC/RDS/Fargate/OpenSearch/paid-Glue. Modeled
cost **< $5/mo** with wide margin at V1/Useful scale.

**Why each service earns its place:** Scheduler = the only always-on trigger (two schedules for
deterministic completeness). SFN Standard = report-assembly orchestration + Retry/Catch isolation +
90-day queryable execution history (recall + audit). SQS + DLQ = collection fan-out, poison
isolation, and the physical embodiment of "failed fetch != mass removal" (the exact interview gap
Brett must rebuild). S3 = immutable system-of-record + backup. CloudWatch = how source-silence is
detected. SES = the one daily digest. Bedrock = optional narration, never authority.

The full architecture, the seven ADR contradiction resolutions, and every P0 default live in
`ARCHITECTURE_DECISION_REGISTER.tsv`.

---

## 2. Where am I? — status table

All phases start **NOT-STARTED**. A phase is done only when its done-gate is met AND its intentional
failure has been exercised AND Brett can give the phase's no-notes explanation.

| Phase | Goal | Status | Done-gate |
|---|---|---|---|
| **P0** Guardrails | Cost fence + region + identity before any spend-capable work | NOT-STARTED | $5 Budget + billing alarm live in us-east-1; non-root identity; Access Analyzer clean; billing-alarm-in-wrong-region failure observed |
| **P1** S3 record substrate | The immutable place every snapshot is written and never mutated | NOT-STARTED | Private bucket, 4 BPA flags true, versioning OFF, lifecycle active; same-key overwrite observed (proves unique-key immutability) |
| **P2** Collector Lambda | Fetch one Greenhouse board, write one immutable snapshot | NOT-STARTED | Snapshot object in S3; least-priv role (no s3:*); AccessDenied-then-fix exercised |
| **P3** SQS + DLQ (recall lab) | Decouple list-from-collect; poison isolation | NOT-STARTED | Poison message reaches DLQ then successfully redriven; too-low-VT duplicate observed (**the interview question**) |
| **P4** Scheduler | Collection runs itself daily | NOT-STARTED | A scheduled (not manual) fire in target history at the expected local time; misfire root-caused |
| **P5** Step Functions | Fan-out over companies, per-company isolation, audit history | NOT-STARTED | Green execution with one company isolated by Catch; assemble schedule (schedule #2) fires after collect offset |
| **P6** Change detection V1 | **The V1 deliverable** — daily new/disappeared/changed, honest | NOT-STARTED | Multi-day report, every change traces to snapshot keys; zero-snapshot day reads COLLECTORS DID NOT RUN; source-fail -> zero disappeared |
| **P7** Observability | Told when the *system* is broken, not just a quiet report | NOT-STARTED | A2 (radar-blind) + A1 (DLQ) fire on induced failures with email; return to OK on recovery |
| **P8** Bedrock digest (opt) | Plain-English daily summary layered on the diff | NOT-STARTED | Every summary sentence maps to a diff item + snapshot; no fake/real language; cost within ceiling |
| **P9** IaC reconstruction | Prove mastery by expressing the hand-built stack as code | NOT-STARTED | CFN stack reproduces V1 end-to-end; Brett names the console screen for every template block; omitted-permission fails the same way |
| **P10** Athena (mature, gated) | Historical intelligence: where effort likely pays off | NOT-STARTED | Real momentum/repost/first-seen queries over accumulated history; unpartitioned-scan cost jump observed then collapsed by partition predicate |

Product increments (from the product seat): **V1** = P0–P7 (Job Radar). **V1.5** = P8 (Bedrock
digest, optional). **V1.75** = P9 (IaC). **Mature** = P10 + analytics. Each increment is gated on an
**actual need**, never on "the diagram looks unfinished." Count is an output, not a target.

---

## 3. First five sessions — launch sequence

These five sessions stand up the autonomous collection spine. P5–P7 then complete V1.

1. **Session 1 — P0 guardrails.** Lock us-east-1; set the $5 Budget + billing alarm; confirm non-root
   identity + permissions boundary. Failure to feel: create the billing alarm in the wrong region and
   watch `EstimatedCharges` be empty.
2. **Session 2 — P1 S3 store.** Create the private, versioning-OFF bucket + lifecycle; write the
   key convention. Failure to feel: overwrite the same key and watch the first object silently vanish.
3. **Session 3 — P2 collector Lambda.** Deploy the thin Greenhouse collector + hand-scoped exec role;
   land the first real snapshot. Failure to feel: **AccessDenied** with the role missing `s3:PutObject`
   — the "it's the function's role, not my creds" reflex.
4. **Session 4 — P3 SQS + DLQ lab.** The anchor recall exercise. Poison message → retries → DLQ →
   inspect → fix → **redrive**. This is the exact path Brett blanked on in interview.
5. **Session 5 — P4 EventBridge Scheduler.** Wire the daily collect schedule; confirm one scheduled
   fire. Failure to feel: wrong timezone / missing invoke permission.

---

## 4. The honesty boundary (read before building anything)

This binds every phase and is the product's spine. It is enforced structurally, not by hope.

- **Observable behavior + confidence, NEVER fake/real.** The system says "reposted 4× in 90 days;
  live 210 days without edits (confidence 0.8)" — never "this job is fake." Banned vocabulary
  (`fake, real, ghost, fraudulent, scam, lying`) is rejected by the report renderer (SCORING spec §5).
- **Three daily outcomes never collapse:** VERIFIED-QUIET (every expected source produced a SUCCESS
  snapshot, no material change) / INCOMPLETE (a source lacks a SUCCESS snapshot — named) / NO-RUN
  (no manifest — caught by alarm A2, not the report). "Nothing changed" ≠ "collectors didn't run."
- **Source failure NEVER masquerades as mass disappearance.** `disappeared` fires ONLY against a
  SUCCESS snapshot; a failed/partial fetch freezes all job states and emits a source-scoped event
  only (DATA spec §0, RELIABILITY §5). A drop to zero or >60% vs the prior SUCCESS = SUSPECT, all
  removals suppressed, A6 fires.
- **The LLM narrates, it never decides.** It may not invent a date, decide disappearance/repost/
  real-fake, or compute a score. A deterministic post-check rejects any date/number in LLM output
  not present in the supplied evidence → template fallback. Every generated sentence cites a stored
  evidence id (SCORING §3–4).
- **Dates are ours.** `first_seen_at` = our earliest SUCCESS observation, never a provider timestamp.

---

## 5. Settled internals (the concrete decisions the phases assume)

**S3 five-tier layout** (single bucket, Hive-partitioned, versioning OFF; DATA spec §7):

| Tier | Prefix | Writer | Purpose |
|---|---|---|---|
| current | `current/provider=<p>/board=<b>/current_jobs.json` + `_source_status.json` | differ / collector | latest live set + last snapshot status (drives "did collectors run") |
| raw | `raw/provider=<p>/board=<b>/dt=<d>/snapshot=<ulid>.json.gz` + `receipt=<ulid>.json` | collector | immutable court-of-record (WORM by unique key) + SourceReceipt |
| normalized | `normalized/schema_v=<v>/provider=/board=/dt=/jobs.json` | collector | canonical jobs, replayable from raw |
| events | `events/schema_v=<v>/provider=/board=/dt=/events.json` | differ | append-only change-event log — the product's memory |
| reports | `reports/dt=<d>/daily_report.json` + `.md` | report | daily digest of record |
| (later) | `parquet/`, `athena-results/` | P10 worker | mature analytics only |

**Job identity** (DATA §1): `job_id = "{provider}:{board_token}#{provider_key}"`. Greenhouse =
native `id` (+ `internal_job_id`, `requisition_id`, `updated_at`); Lever = native UUID; Ashby = URL-slug
UUID else content-hash (flag `IDENTITY_LOW_CONFIDENCE`). `content_hash` over the canonical field set
drives change detection where no provider `updated_at` exists (Lever/Ashby). `id_kind` stored on every
record.

**Change-event taxonomy** (DATA §5): job-scoped — `first-seen`, `no-material-change`,
`materially-changed`, `location-changed`, `salary-changed`, `remote-hybrid-language-changed`,
`disappeared`, `returned`, `probable-repost`; source-scoped — `source-fetch-failed`,
`source-response-partial`. Job state machine: `ACTIVE → PENDING_REMOVAL → DISAPPEARED ⇄ returned`.
**Disappearance invariant:** `disappeared` requires `current.status == SUCCESS`; grace = **2
consecutive SUCCESS snapshots** (not days). "Prior snapshot" = most recent SUCCESS, skipping outages.

**Retry-ownership model** (RELIABILITY §3 — each layer owns exactly one retry, no overlap):
transient-within-fetch → the connector (in-handler backoff+jitter, ~3, within timeout);
connector-exhausted → SQS (ReportBatchItemFailures → visibility → redeliver to maxReceiveCount → DLQ);
poison → DLQ (terminal until human redrive); assembly-transient → SFN Retry; assembly-unrecoverable →
SFN Catch States.ALL → report_incomplete. **Rule: SQS never retries what SFN retries; SFN never
retries collectors.**

**Alarm set** (RELIABILITY §6 → SNS `jprs-ops-alerts` → email): A1 DLQ depth≥1; A2 missed-run
(custom `CollectRunSuccess` missing/0, `treatMissingData=breaching` — the NO-RUN detector); A3
ReportComplete missing/0; A4 queue age > 3× visibility; A5 collector Errors/Throttles≥1; A6
SourceSuspect≥1 (mass-drop); A7 SFN ExecutionsFailed≥1; (A8 Scheduler DLQ — UNVERIFIED).

**Scoring dimensions** (SCORING §1–2): six deterministic, individually-inspectable — `brett_fit`,
`freshness`, `hiring_activity_evidence`, `repost_churn_pattern`, `source_data_confidence`,
`application_priority` (composite); `observed_application_outcome` later. Each emits
`{score, band HIGH/MED/LOW/UNKNOWN, confidence, evidence_refs[], version}`. UNKNOWN is first-class;
composite confidence = weakest-link (min). No opaque single number; the composite is titled
"application priority," never "reality verdict."

**Guardrail set** (COST §G1–G8): G1 Budgets $5 (50/80/100+forecast), $10 ceiling; G2 cost tags
Project/Env/ManagedBy; G3 lifecycle (versioning OFF, raw 400d, IA 90d, abort-MPU 7d); G4 explicit 30d
log retention on **every** group (default is Never-Expire — the real cost lever); G5 Athena
BytesScannedCutoffPerQuery=1GB + Parquet+snappy+partitioned; G6 Bedrock OFF/Haiku-default/Sonnet-
on-demand/max_tokens-cap; G7 tag-based teardown (disabling Scheduler halts all); G8 excluded-service
ban (NAT/EC2/RDS/OpenSearch/K8s/paid-Glue/Provisioned-Concurrency). **Verdict: PASS < $5/mo.**

**Security spine** (SECURITY §1–2): root prohibited; IAM Identity Center + MFA; a shared
permissions boundary on every exec role denying `iam:*`/`ec2:*`/make-public; per-prefix + per-ARN
IAM (no `Resource:"*"`); one-directional flow — collector writes evidence tiers, differ writes derived
tiers, report reads+writes reports, **llm-role writes no factual data**; SSE-S3; SSM Parameter Store
(no Secrets Manager V1); CloudTrail management events + Access Analyzer (both free).

---

## 6. The phases, P0 → P10

Each phase gives the twelve fields the packet requires. Owner tags: `BRETT_MANUAL_AWS` (console by
hand — the recall act) / `AI_IMPLEMENTATION` (prepared artifact, always with an INSPECT-FIRST gate) /
`SHARED_VERIFY` (both confirm the same evidence). Exact task rows + dependencies + rollback are in
`PHASED_IMPLEMENTATION_BACKLOG.tsv`; the fill-in worklists are in `AWS_MANUAL_BUILD_WORKBOOK.md`.

---

### PHASE 0 — Account Guardrails & Region Baseline

- **Objective & user value:** No product value yet — this is the safety floor. Never start
  spend-capable work without the cost fence up; re-seat the Budgets/billing muscle memory.
- **AWS concept refreshed:** Region as an isolation boundary; Budgets (proactive ceiling) vs
  CloudWatch billing alarm (reactive threshold on `EstimatedCharges`, publishes only in us-east-1);
  least-privilege identity (not root).
- **Prerequisites:** An AWS account exists (S3 12-mo free tier may be expired — modeled at pennies).
- **BRETT_MANUAL_AWS:** lock region us-east-1; create the $5 cost Budget (alerts 50/80/100% + forecast)
  + $10 ceiling; create the billing alarm (in us-east-1); confirm operating as a non-root principal;
  set up IAM Identity Center (or fallback MFA'd IAM user); enable IAM Access Analyzer.
- **AI_IMPLEMENTATION:** budget/alarm threshold memo + "what each guardrail catches" explainer; the
  shared permissions-boundary policy JSON. INSPECT-FIRST: Brett confirms thresholds match his risk
  tolerance and can state what the boundary denies.
- **SHARED_VERIFY:** Budget + alarm visible in console; test alert email received; Access Analyzer
  reports no external access.
- **Resource names + deps:** `jprs-billing-*` alarm, the $5/$10 Budget, the boundary policy. No deps.
- **Intentional failure:** create the billing alarm in a non-us-east-1 region → `EstimatedCharges` is
  unavailable/empty. Lesson: billing metrics are global-but-published-in-us-east-1.
- **Expected observations:** empty metric in the wrong region; test email arrives from the correct one.
- **Security checkpoint:** root has no access keys, MFA on root; you are not operating as root.
- **Cost checkpoint:** $0 (Budgets free; alarm within free allotment).
- **Rollback/cleanup:** delete budget + alarm; no ongoing cost.
- **Completion evidence:** budget + alarm screenshots; wrong-region observation logged.
- **Done gate:** guardrails live in us-east-1; non-root identity; wrong-region failure observed.
- **No-notes explanation:** "Why must the billing alarm live in us-east-1, and what's the difference
  between a Budget and a billing alarm?"

### PHASE 1 — S3 Immutable Snapshot Store

- **Objective & user value:** The record substrate the whole product's honesty rests on — you can only
  tell Brett what changed if yesterday's snapshot is preserved exactly.
- **AWS concept refreshed:** S3 as a flat object store with key/prefix conventions (not folders);
  **immutability by unique write-once key, NOT versioning** (operator hard rule — versioning is the
  tempting-but-banned shortcut; know why); Block Public Access.
- **Prerequisites:** P0 (region, boundary policy).
- **BRETT_MANUAL_AWS:** create `jprs-<stage>-<alias>` bucket; BPA ON (4 flags); SSE-S3 + Bucket Key;
  ACLs disabled (bucket-owner-enforced); versioning OFF; write the key convention; create lifecycle
  rules per tier (raw 400d, normalized/reports 90d, abort-MPU 7d).
- **AI_IMPLEMENTATION:** lifecycle-rule JSON, key-naming scheme, private least-priv bucket policy
  (deny non-TLS). INSPECT-FIRST: Brett states what the lifecycle deletes and when, and points at the
  line that would break immutability if it were an overwrite/versioning rule.
- **SHARED_VERIFY:** bucket private, lifecycle active, versioning off; a hand-uploaded test object
  appears at the expected key; anonymous curl → 403.
- **Resource names + deps:** bucket `jprs-<stage>-<alias>`, five prefixes. Depends on P0.
- **Intentional failure:** write two objects to the **same key** → second silently replaces the first
  (no version history). Proves why the key must be unique per snapshot.
- **Expected observations:** overwrite is silent and total; 403 on anonymous access.
- **Security checkpoint:** all 4 BPA flags true; ACLs disabled; SSE-S3 on; no DeleteObject on raw/.
- **Cost checkpoint:** ≈$0 (KB-sized JSON).
- **Rollback/cleanup:** empty + delete bucket.
- **Completion evidence:** console URL, versioning-off screenshot, overwrite observation.
- **Done gate:** private bucket, 4 BPA flags, versioning OFF, lifecycle active, overwrite observed.
- **No-notes explanation:** "Why are we forbidden from S3 versioning here, and how do we get
  immutability without it?"

### PHASE 2 — First Collector Lambda + Execution Role

- **Objective & user value:** Fetch ONE company's live postings from Greenhouse's public API and write
  one immutable snapshot. First "data actually landed" moment.
- **AWS concept refreshed:** Lambda as event-driven function; the **execution role** (the function's
  permissions are the role's, not yours — the thing people forget); least-privilege
  (`s3:PutObject` on one prefix, nothing more); CloudWatch Logs as the debug surface.
- **Prerequisites:** P1 (bucket).
- **BRETT_MANUAL_AWS:** create `jprs-collector` Lambda (Python 3.x); attach `collector-role` (PutObject
  on raw/normalized/receipt for jprs-* only; GetParameter `/jprs/collector/*`; own log group); set env
  vars (bucket, provider=greenhouse, company slug); run a test event; read one successful log.
- **AI_IMPLEMENTATION:** the thin collector handler (HTTP GET `boards-api.greenhouse.io/v1/boards/
  {token}/jobs?content=true`, write raw + receipt BEFORE parse, map canonical, **no pandas/numpy**);
  an ATS fixture; the least-priv exec-role policy JSON; the host-allowlist guard + truthful User-Agent
  + 429/503 backoff. INSPECT-FIRST: Brett (a) names the endpoint and confirms it's a sanctioned public
  API, (b) reads the IAM policy aloud and confirms PutObject-only, (c) finds the S3-key line.
- **SHARED_VERIFY:** snapshot object present with expected schema; clean log; policy minimal (no `s3:*`).
- **Resource names + deps:** `jprs-collector`, `collector-role`. Depends on P1.
- **Intentional failure (the IAM-recall failure):** deploy with the role **missing `s3:PutObject`** →
  invoke → `AccessDenied` → read it in CloudWatch → add the permission → re-invoke → success.
- **Expected observations:** the `AccessDenied` text; the fix is in the role, not your credentials.
- **Security checkpoint:** connector calls only allowlisted ATS hosts; no `Resource:"*"`; User-Agent set.
- **Cost checkpoint:** ≈$0 (Lambda free-tier requests; KB to S3).
- **Rollback/cleanup:** delete function + role + test objects.
- **Completion evidence:** snapshot object, clean log, minimal-policy screenshot.
- **Done gate:** snapshot in S3; least-priv role; AccessDenied-then-fix exercised.
- **No-notes explanation:** "When the function got AccessDenied, whose permissions were wrong — mine or
  the function's — and where exactly did I fix it?"

### PHASE 3 — SQS + Dead-Letter Queue (the recall lab)

- **Objective & user value:** Decouple "list the companies" from "collect each one" so one bad
  company/provider can't sink the run — failed messages land in a DLQ instead of vanishing.
  **This directly rebuilds the SQS/DLQ path Brett blanked on in the interview.**
- **AWS concept refreshed:** SQS as a durable buffer; **visibility timeout** (too short → duplicate
  processing); **DLQ** via redrive policy after `maxReceiveCount` (poison quarantined, not lost, not
  retried forever); **redrive** (moving DLQ messages back after a fix).
- **Prerequisites:** P2 (collector).
- **BRETT_MANUAL_AWS:** create `jprs-collect-dlq` FIRST, then `jprs-collect-queue`; wire redrive policy
  (`maxReceiveCount`=3, or 2 for the lab); VT = 180s (≥6× the 30s fn); DLQ retention 14d > source 4d;
  scope the collector role's `sqs:SendMessage`/`ReceiveMessage` to these ARNs only; send + poll a test
  message.
- **AI_IMPLEMENTATION:** the worker/consumer contract (one company/msg; per-record failure via
  `ReportBatchItemFailures`, `itemIdentifier`=messageId); SQS access-policy JSON; the VT/maxReceiveCount
  numbers (reconciled with the reliability seat). INSPECT-FIRST: Brett states the message lifecycle in
  his own words and points at what VT and `maxReceiveCount` each do.
- **SHARED_VERIFY:** a poison message demonstrably in the DLQ, then successfully redriven and processed.
- **Resource names + deps:** `jprs-collect-queue`, `jprs-collect-dlq`. Depends on P2.
- **Intentional failure (the core lab):** feed a message that always fails (garbage slug) → received,
  retried `maxReceiveCount` times (`ApproximateReceiveCount` climbs), lands in DLQ (A1) → fix root
  cause (collector v2) → **Start DLQ redrive → source** → drains to success, A1 → OK. Second failure:
  set VT too low → observe duplicate processing.
- **Expected observations:** the retry count; DLQ arrival; a new `messageID`/`enqueueTime` after
  redrive; duplicate processing at low VT.
- **Security checkpoint:** queue policies scoped to the collector role principal only.
- **Cost checkpoint:** ≈$0 (SQS free-tier allotment).
- **Rollback/cleanup:** purge + delete both queues.
- **Completion evidence:** before/after queue-depth screenshots; redrive confirmed.
- **Done gate:** poison → DLQ → redriven → processed; low-VT duplicate observed.
- **No-notes explanation (the interview question that broke):** "Walk me through what happens to a
  message that keeps failing — where does it go, what controls that, and how do I get it back?"

### PHASE 4 — EventBridge Scheduler (daily trigger)

- **Objective & user value:** Collection now runs itself once a day — a *radar*, not a script Brett
  remembers to run.
- **AWS concept refreshed:** managed cron-as-a-service; a schedule invokes a target in a stated
  timezone; the scheduler needs its **own IAM role** to invoke the target (another "permissions live on
  the caller" moment); 14M free invocations/mo.
- **Prerequisites:** P2 (a target to invoke); P3 (the SQS fan-out target).
- **BRETT_MANUAL_AWS:** create `jprs-daily-collect` schedule (cron, tz America/New_York); target =
  enumerate Lambda / SQS fan-out; create/attach the scheduler invoke role scoped to the one target;
  confirm one successful scheduled fire.
- **AI_IMPLEMENTATION:** the cron/rate expression + timezone rationale; the scheduler invoke-role policy.
  INSPECT-FIRST: Brett reads the cron and states the exact local fire time, confirms the role points at
  the right target ARN.
- **SHARED_VERIFY:** a scheduled (not manual) invocation in the target's execution history at the
  expected time.
- **Resource names + deps:** `jprs-daily-collect`, `scheduler-role`. Depends on P2/P3.
- **Intentional failure:** deploy with the invoke role missing the target permission (or a
  UTC/local-tz mistake) → observe non-fire / wrong-hour fire; find the cause in Scheduler error metrics
  + target logs.
- **Expected observations:** the misfire and its root cause.
- **Security checkpoint:** scheduler-role scoped to StartExecution/Invoke on the single target ARN.
- **Cost checkpoint:** $0 (within 14M free/mo).
- **Rollback/cleanup:** disable then delete schedule.
- **Completion evidence:** scheduled-fire screenshot.
- **Done gate:** a scheduled fire at the expected local time; misfire root-caused.
- **No-notes explanation:** "My daily job fired at the wrong time / didn't fire — what are the two most
  likely causes and where do I check each?"

### PHASE 5 — Step Functions Orchestration

- **Objective & user value:** One daily run cleanly fans out over N companies, isolates per-company
  failure, retries transient errors, and gives a visual execution history — the operational backbone
  and the **assemble** side of the two-schedule boundary (ADR-06).
- **AWS concept refreshed:** ASL state machine; **Map** state (bounded fan-out over companies);
  **Retry/Catch** (declarative transient-retry + error routing); **execution history** (per-run,
  per-state visual record — the best "what happened" surface); 4,000 free transitions/mo.
- **Prerequisites:** P3 (queue settled), P4 (a schedule exists).
- **BRETT_MANUAL_AWS:** create `jprs-daily-assemble` state machine (Standard); assign an exec role
  scoped to invoke differ/report + read config; create schedule #2 (assemble-after-offset) targeting
  it; start one execution by hand; read the Graph view; confirm one company's failure doesn't fail the
  run.
- **AI_IMPLEMENTATION:** the ASL (Map + Retry + Catch States.ALL → report_incomplete); the exec-role
  policy; the completeness check (manifest-expected vs SUCCESS sentinels — **never wall-clock**).
  INSPECT-FIRST: Brett traces entry → Map → per-item Lambda → Catch and states what Retry/Catch do.
- **SHARED_VERIFY:** green execution with one company isolated to a caught-failure branch; other
  snapshots still produced.
- **Resource names + deps:** `jprs-daily-assemble`, its role, schedule #2. Depends on P3/P4.
- **Intentional failure:** make one company deterministically fail → confirm Catch routes it while
  others succeed → read exactly which state failed in the execution history.
- **Expected observations:** the failed state name; isolation held.
- **Security checkpoint:** exec role invokes only the named functions (not `*`).
- **Cost checkpoint:** ≈$0 (well under 4,000 free transitions/mo).
- **Rollback/cleanup:** delete state machine + role + schedule #2.
- **Completion evidence:** execution-graph screenshot.
- **Done gate:** one company isolated by Catch; assemble schedule fires after the collect offset.
- **No-notes explanation:** "How does my daily run keep one broken company from killing the whole
  batch, and where do I see which state failed?"
- **Boundary note (ADR-06):** V1 default is two schedules. The named upgrade — folding collection into
  a single SFN execution with a Choice+Wait DrainBarrier — is triggered only if the fixed offset
  becomes unreliable, cadence goes sub-daily, or a single-execution audit unit is wanted.

### PHASE 6 — Change Detection & Daily "What Changed" Report (V1 DELIVERABLE)

- **Objective & user value:** THE V1 promise — "save postings every day and tell me what changed":
  new (with first-seen), disappeared, materially-changed, each traceable to stored snapshots. The
  first day the tool earns its keep in Brett's actual search (feeds the "apply within 72h of posting"
  target).
- **AWS concept refreshed:** none new — this is the differ/report Lambda + S3 reads. The concepts are
  **idempotent evidence-anchored comparison** and the honesty gates.
- **Prerequisites:** P1 (bucket with ≥2 days of snapshots); the data-seat models.
- **BRETT_MANUAL_AWS:** deploy `jprs-differ` (differ-role: read normalized+current, write
  events+current); run against two consecutive real snapshot days; read one real day's report and use
  it in the search.
- **AI_IMPLEMENTATION:** Pydantic models (SourceSnapshot, SourceReceipt, CanonicalJob, ChangeEvent),
  the versioned deterministic normalizer, the diff engine honoring the reliability gates (SUCCESS
  precondition, grace N=2, mass-drop SUSPECT), the report renderer with the run-health header
  (VERIFIED-QUIET / INCOMPLETE(sources named) / RAN_OK vs NO_SNAPSHOTS) + the never-fake vocabulary
  guard, the deterministic scorecard scorer (6 dimensions, profile v1.0.0, UNKNOWN first-class,
  evidence_refs), and golden fixtures. INSPECT-FIRST: Brett confirms (a) each change cites specific
  snapshot keys, (b) a distinct code path for "no snapshots produced" vs "no changes", (c) no line
  asserts fake/real.
- **SHARED_VERIFY:** a real multi-day report with correct new/disappeared/changed classification, every
  item traceable to snapshots, correct run-health header.
- **Resource names + deps:** `jprs-differ`, events/ + reports/ tiers. Depends on P1.
- **Intentional failure (the single most important honesty test):** feed a day where the collector
  produced **zero snapshots** (total outage) → report says `COLLECTORS DID NOT RUN`, NOT "all jobs
  disappeared." Also feed prev=SUCCESS(10) + current=FETCH_FAILED → zero disappeared, states frozen,
  one source-fetch-failed.
- **Expected observations:** the NO_SNAPSHOTS header; zero false removals under source failure.
- **Security checkpoint:** differ reads normalized/current, writes events/current only; no raw delete.
- **Cost checkpoint:** ≈$0 (Lambda + S3 reads at KB scale).
- **Rollback/cleanup:** delete differ; snapshots + reports in S3 are safe to keep.
- **Completion evidence:** a real multi-day report sample path.
- **Done gate:** every change traces to snapshot keys; zero-snapshot day reads COLLECTORS DID NOT RUN;
  source-fail → zero disappeared.
- **No-notes explanation:** "If tomorrow's report says nothing changed, how do I know the collectors
  actually ran — and why is that distinction the whole point?"

### PHASE 7 — CloudWatch Alarms & Observability

- **Objective & user value:** Brett is told when the *system* is broken (collector didn't run, DLQ
  filling) instead of silently trusting a quiet report. Closes "source failure must never masquerade as
  mass disappearance" at the ops layer. Completes V1.
- **AWS concept refreshed:** metric → alarm → SNS notification; the two that matter here —
  **collector-didn't-run** (A2, custom heartbeat, `treatMissingData=breaching`) and **DLQ-not-empty**
  (A1). A dashboard is a read surface; the alarm is the actor.
- **Prerequisites:** P3 (DLQ), P6 (report completeness metric).
- **BRETT_MANUAL_AWS:** create SNS `jprs-ops-alerts` + confirmed email sub; create A1 (DLQ≥1), A2
  (missed-run heartbeat), A3 (ReportComplete), A5 (collector Errors), A6 (SourceSuspect), A7 (SFN
  ExecutionsFailed); optional dashboard.
- **AI_IMPLEMENTATION:** alarm thresholds + metric-math (esp. "didn't run in window"); dashboard JSON;
  SNS wiring. INSPECT-FIRST: Brett states what each alarm watches and what a breach *means* ("DLQ>0 =
  a company failed all retries"; "0 successes = the radar is blind today").
- **SHARED_VERIFY:** both alarms transition to ALARM on induced failures with email; return to OK after
  recovery.
- **Resource names + deps:** `jprs-ops-alerts`, alarms A1–A7. Depends on P3/P6.
- **Intentional failure:** disable the collect schedule for a day → A2 fires + email arrives; push a
  poison message → A1 fires.
- **Expected observations:** the radar-blind alarm distinct from the one-company-failing alarm.
- **Security checkpoint:** SNS topic policy restricted to the account; email sub confirmed.
- **Cost checkpoint:** ≈$0 (alarms within free allotment; SNS email pennies).
- **Rollback/cleanup:** delete alarms + SNS topic; re-enable the daily schedule.
- **Completion evidence:** ALARM-state screenshots + email receipts.
- **Done gate:** A2 + A1 fire on induced failures with email; return to OK on recovery.
- **No-notes explanation:** "Which alarm tells me the radar went blind, and how is that different from
  the alarm that tells me one company is failing?"

### PHASE 8 — Bedrock Change Summaries (OPTIONAL, evidence-pointing only)

- **Objective & user value:** A 30-second plain-English daily digest layered ON TOP of the
  deterministic diff, so the radar actually gets read. The LLM decorates; it never decides.
- **AWS concept refreshed:** Bedrock `invoke_model` (pay per token, cost control on you); **LLM as
  narrator, not authority** — generated *from* the diff, cites the same snapshot evidence, never the
  source of a fact.
- **Prerequisites:** P6 (trusted deterministic report) + P7. **Gate: only build once the deterministic
  report is trusted and Brett finds the raw report high-friction.** If he reads V1 happily, skip P8.
- **BRETT_MANUAL_AWS:** enable Bedrock model access (Haiku); create `jprs-llm` Lambda + `llm-role`
  (`InvokeModel` on exactly the two model ARNs, **no** factual-tier write); feature-flag OFF by
  default; set a token/cost ceiling.
- **AI_IMPLEMENTATION:** a prompt fed ONLY the structured diff (delimited hostile-data block, strict
  JSON out); reuse of the CFR `bedrock_client.py` wrapper; the deterministic post-check (reject
  dates/numbers not in evidence → template); a red-team injection fixture. INSPECT-FIRST: Brett
  confirms the prompt is fed only the diff and the output template forbids fake/real language.
- **SHARED_VERIFY:** every summary sentence maps to a diff item + snapshot; no fake/real; cost in ceiling.
- **Resource names + deps:** `jprs-llm`, `llm-role`. Depends on P6/P7.
- **Intentional failure:** feed an ambiguous diff → confirm the summary says "posting no longer appears
  in the feed," NOT "this was a fake job." Tighten the prompt if it overclaims.
- **Expected observations:** behavior-only language; the injection fixture leaves factual fields intact.
- **Security checkpoint:** `llm-role` is InvokeModel-only on two ARNs, no writes — a successful
  injection can only produce a discardable, schema-bounded string.
- **Cost checkpoint:** cents/day at Haiku; Sonnet-daily needs approval (would threaten $5 at scale).
- **Rollback/cleanup:** remove the summary step; the deterministic report stands alone.
- **Completion evidence:** grounded summary sample + cost screenshot.
- **Done gate:** every claim traceable to the diff; no fake/real; cost within ceiling.
- **No-notes explanation:** "Where do the facts in the summary come from, and what is the LLM
  specifically NOT allowed to decide?"

### PHASE 9 — Infrastructure-as-Code Reconstruction

- **Objective & user value:** Prove mastery by expressing the same hand-built stack as code, tearing
  down the manual stack, and redeploying from the template — an interview-defensible artifact. **Late,
  not early:** the console work IS the recall; IaC before it inverts the telos.
- **AWS concept refreshed:** IaC (SAM/CDK) as the reproducible source of truth; **round-tripping**
  (mapping every hand-built resource to a template block — gaps reveal what was only half-understood);
  **drift**.
- **Prerequisites:** P6 + P7 running reliably by hand long enough that each resource has been broken.
- **BRETT_MANUAL_AWS:** for EACH manual resource, verify its template block; deploy the stack into a
  fresh prefix alongside the manual one; diff behavior; tear down the manual resources, keep the IaC
  stack.
- **AI_IMPLEMENTATION:** a draft SAM/CDK template mirroring the hand-built stack; unit tests +
  `sam validate`/`cdk synth` in CI. **INSPECT-FIRST (highest bar):** Brett points at each template
  block and names the console screen where he built its equivalent; any block he can't trace goes back
  to a console refresher. AI must not let IaC paper over a recall gap.
- **SHARED_VERIFY:** a CFN stack reproducing working V1 end-to-end, with Brett narrating every block.
- **Resource names + deps:** the templated stack (fresh prefix). Depends on P6/P7.
- **Intentional failure:** deliberately omit one IAM permission (or env var) from the template →
  deploy → watch it fail the same way it failed in the manual phase.
- **Expected observations:** the same failure, now from a template omission (dependency understood).
- **Security checkpoint:** template IAM matches the hand-built least-privilege; no broadening.
- **Cost checkpoint:** ≈$0 additional (same resources, briefly duplicated).
- **Rollback/cleanup:** `sam delete` / `cdk destroy` (the payoff of IaC).
- **Completion evidence:** the CFN stack + narration notes.
- **Done gate:** stack reproduces V1; Brett names the console screen for every block; omitted-permission
  fails the same way.
- **No-notes explanation:** "Point at any resource and tell me both: the console screen I built it on,
  and the template block that now defines it."

### PHASE 10 — Parquet + Athena Historical Intelligence (MATURE, gated)

- **Objective & user value:** Turn accumulated first-seen dates, repost patterns, and change history
  into an expected-return read on where effort likely pays off. **Gate: only once there is enough
  accumulated history (weeks–months) AND a real analytical question V1 can't answer.** Don't warehouse
  data you haven't collected.
- **AWS concept refreshed:** columnar Parquet in S3, **partitioned** (the cost lever); Athena as
  serverless SQL over S3 ($5/TB scanned — Parquet+partition ~10× cheaper than raw JSON); **no paid Glue
  crawler** — define the table by hand with partition projection.
- **Prerequisites:** all three DATA-spec §8 conditions: routine cross-day questions; ≥~20 companies /
  ≥2 providers / ≥60 days history; a query a single Lambda can't answer cheaply.
- **BRETT_MANUAL_AWS:** add a step that rolls snapshots into partitioned Parquet (`parquet/` tier, a
  **separate worker, not a fat Lambda**); define the Athena external table by hand (DDL); set the
  workgroup `BytesScannedCutoffPerQuery`=1GB + a query-results location; run 2–3 real analytical
  queries; record Data-scanned.
- **AI_IMPLEMENTATION:** the Parquet-writing step, the table DDL (`CREATE EXTERNAL TABLE` +
  `projection.enabled=true`, no crawler), the analytical SQL labeled *evidence summaries, not truth
  claims*. INSPECT-FIRST: Brett states what each query measures and what it does NOT prove (momentum ≠
  "this company will hire me"; repost ≠ "fake job").
- **SHARED_VERIFY:** real queries returning momentum/first-seen/repost signals from actual history,
  each framed as observed behavior, per-query scan cost negligible.
- **Resource names + deps:** `parquet/` tier, Athena table + workgroup. Depends on P9 + accumulated
  history.
- **Intentional failure:** run a query **without** the partition filter → watch Data-scanned + cost
  jump → add the partition predicate → watch it collapse.
- **Expected observations:** the before/after scan (partitioning changes the cost of the same question).
- **Security checkpoint:** `analytics-role` read-only on normalized/events + a dedicated
  `athena-results/` write; excluded from starter scope (no paid Glue).
- **Cost checkpoint:** cents at this scale if partitioned; spikes if you scan raw (the induced-failure
  lesson). G5 cutoff caps runaway queries.
- **Rollback/cleanup:** drop the table (metadata only); Parquet in S3 is safe to keep or lifecycle out.
- **Completion evidence:** query samples with per-query scan cost.
- **Done gate:** real historical queries return signal; unpartitioned-vs-partitioned scan jump observed.
- **No-notes explanation:** "Why does partitioning my Athena table change the *cost* of the same
  question, and what's the honest limit of what a hiring-momentum number tells me?"

---

## 7. Cost, teardown, and the two silences

**Under-$5 verdict (COST seat): PASS.** Core (Haiku/no-Bedrock) monthly: V1 ~$0–0.05, Useful
~$0.10–0.30, Expansion ~$1.00–2.50. Expansion stays <$5 only with G4 (log retention) + G5 (Athena
partitioning) + G6 (Bedrock off/Haiku) + G8 (no always-on) active. Breakers to watch: banned always-on
infra (NAT ~$32, RDS ~$12+, OpenSearch ~$25+ — all excluded), unpartitioned Athena (~$2.50+),
Sonnet-daily at 100 companies (~$3.15), unbounded CloudWatch retention. Budgets is the backstop.

**Teardown (leave zero cost):** disable both schedules → delete ESMs → empty+delete queues → delete
state machine(s) → delete Lambdas + log groups → delete alarms + dashboard + SNS → **export raw/ first
if keeping history**, then empty+delete bucket → delete IAM roles/policies → confirm $0 next cycle, no
orphan `INSUFFICIENT_DATA` alarms. Nothing is always-on; if any phase ever tempts RDS/NAT/EC2, STOP and
surface. `raw/` is the only irreplaceable tier — everything else is regenerable from raw + a re-run.

**The two silences (the guarantee that survives every phase):** "nothing changed" (collector ran,
receipt=ok, diff empty → VERIFIED-QUIET) is a *different state* from "collectors didn't run" (missing
receipt / DLQ depth / no execution → INCOMPLETE or NO-RUN + alarm). They must never collapse. This is
enforced by the receipt/sentinel tier, the SUCCESS-precondition on disappearance, the grace clock
counted in SUCCESS snapshots, the mass-drop SUSPECT guard, and alarm A2. Every increment inherits it.

---

## 8. Committee conditions to clear (PASS WITH CONDITIONS)

The Skeptic seat (`STABLE-002`) audited the synthesized package: **verdict PASS WITH CONDITIONS —
8/15 acceptance points PASS, 7 PARTIAL, 0 FAIL. P0–P3 start immediately; there are no blockers.**
Every PARTIAL traces to one of the five must-clear conditions below, each pinned to the phase gate
where it comes due. Full findings + the ADR-24 ruling + the UNVERIFIED-risk register are in
`PANEL_DISSENT.md`. Do not treat a phase as done until its condition here is met.

| # | Condition (what the synthesis under-built) | Fix | Clear-by gate |
|---|---|---|---|
| **M1** | The enumerate Lambda + `RUN_OPEN` manifest that the two-schedule completeness model and the two-silences guarantee depend on (ADR-06, alarms A2/A3) are referenced in P4/P5 but **no phase actually builds/tests/gates them**. | Add a **P4a collection-spine build unit**: enumerate Lambda + manifest schema + SQS fan-out + an INCOMPLETE-detection test; settle Dispatcher = Lambda vs SFN state. | **before P5** |
| **M2** | "Never fake/real" is guarded only lexically (banned tokens) + numerically (unsupported dates). A narration like *"evergreen listing that may not reflect a genuine vacancy"* has no banned token and no new number → passes both guards. SCORING §4 (free prose) contradicts SECURITY §6 (strict schema). | Constrain the LLM to a **slot-filled fixed template** (adopt SECURITY §6 as authoritative over free prose); add a no-banned-token accusatory-paraphrase red-team fixture. | **before P8 enable** (P8 is optional) |
| **M3** | The mass-drop guard (">60%/zero vs prior SUCCESS") is single-step: it misses (a) a cumulative 50%+50% two-day bleed (each step under threshold, grace N=2 satisfied → real `disappeared`), and (b) a silent-subset SUCCESS (HTTP 200, well-formed, one department omitted → labeled SUCCESS not PARTIAL). | Add a **cumulative/trend check** across the grace window + a **per-segment completeness** check; add both as fixtures. | **before P6 done** |
| **M4** | ADR-24 (collector normalizes) is acceptable for V1 BUT the collector's `current/_source_status.json` and the differ's authoritative `current/current_jobs.json` share the `current/` prefix — S3 IAM scopes by prefix, so a `current/*` grant lets a compromised collector rewrite the live-job set (the escalation the security split prevented). | **Split the prefix:** collector writes `status/`, differ owns `current/`. Add a `normalized == normalizer(raw)` replay-audit. Add "normalizer parse-exploit OR normalized-diverges-from-raw → force the processor split" to the ADR-24 trigger. | **IAM at P2, audit at P6** |
| **M5** | The cost fence notifies but doesn't enforce: the $10 "ceiling action" only emails (stop-scheduler is "optional"); per-log-group 30-day retention is manual and new Lambda log groups default **Never-Expire** (drifts as phases add functions); custom-metric cost is UNVERIFIED. | Wire the **$10 Budget Action to disable the scheduler**; make finite log retention a **line in every Lambda phase's done-gate**; verify custom-metric cost before Expansion. | **P0 + every Lambda phase + P7** |

Minor items (also in `PANEL_DISSENT.md`): cold-start/first-ever-run diff behavior; a de-configured
company leaving a silent stale `current/`; SES sandbox mode on first send; PII redaction being manual
rather than pipelined. None block V1; each is noted at its phase.

**Bottom line for the executor:** begin at P0 today. Carry M4 into P2's IAM, M1 into the P4→P5
boundary, M3 into P6's done-gate, M5 into every phase that adds a Lambda, and M2 only if/when P8 is
enabled. None of them changes the settled architecture — they harden it.
