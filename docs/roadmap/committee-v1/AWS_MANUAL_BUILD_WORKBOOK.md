# AWS Manual Build Workbook — Job Posting Reality Score

> Seat: `ADHOC-PRODUCT-LEARNING-JOURNEY-DESIGNER`.
> Packet: `PKT-CAREER-JOB-POSTING-REALITY-SCORE-ROADMAP-COMMITTEE-V1-20260727`.
> This is a ROADMAP artifact. It does not create resources. Brett works through it later,
> by hand, in the console. AI has prepared code/policies/schemas in advance; **Brett performs
> every console create/wire/deploy/verify action himself** — that manual act is the point.

## How to use this workbook

Each phase has three fixed blocks:

- **STABLE CONCEPT** — the AWS idea that does not change when Amazon reskins the console. This
  is what Brett must be able to explain without notes. Learn this, not the button path.
- **CURRENT-UI PATH (drift-prone)** — today's menu wording, with a `source/date-checked` field.
  Console labels move; whenever a path is wrong, Brett updates it and dates it. Never trust a
  UI path in this doc as gospel — trust the STABLE CONCEPT and re-find the button.
- **DO / OBSERVE / RECALL** — the checkbox worklist, the fill-in evidence fields, the intentional
  failure, the teardown line, and the no-notes recall prompt.

**Ownership tags** (used throughout, and in `MANUAL_VS_AUTOMATED_WORK_MATRIX.tsv`):
`BRETT_MANUAL_AWS` = Brett does it in the console by hand ·
`AI_IMPLEMENTATION` = AI hands Brett a prepared artifact (code / policy JSON / ASL / SQL / test) ·
`SHARED_VERIFY` = both confirm the same evidence before the phase is "done".

**Golden rule of this workbook:** AI never pastes into the console for Brett, and Brett never
blind-pastes an AI artifact he cannot read back. Every prepared artifact has an **INSPECT-FIRST**
line: what Brett must be able to point at and explain before it goes in.

---

## Global fill-in header (fill once, before Phase 0)

| Field | Value |
|---|---|
| Region (stable choice) | `______________` (baseline: `us-east-1` per CFR env) |
| AWS account alias (NOT the numeric ID — never write the ID here) | `______________` |
| Monthly budget ceiling set in Budgets | `$________` (starter target < $5/mo) |
| Billing/cost alarm threshold | `$________` |
| Naming convention prefix for all resources | `jprs-` (Job Posting Reality Score) |
| IAM principal Brett operates as (user/role name, not ARN with account id) | `______________` |
| Evidence folder on laptop for screenshots/receipts | `______________` |
| Start date | `__________`  ·  Target V1-working date | `__________` |

> **Do not paste account IDs, access keys, or full ARNs containing the account number into this
> workbook.** Record resource *names* and *console URLs*; redact the numeric account segment of any
> ARN as `arn:aws:...:REDACTED:...`.

---

# PHASE 0 — Account Guardrails & Region Baseline

**Why first:** you never start spend-capable work without the cost fence up. This also re-seats the
muscle memory for Budgets/billing that decayed. No product value yet — this is the safety floor.

### STABLE CONCEPT
- A **region** is a geographic isolation boundary; every resource lives in exactly one. Pick one and
  stay in it — cross-region confusion is the #1 "where did my resource go" failure.
- **AWS Budgets** = proactive spend ceiling with notification; **CloudWatch billing alarm** = reactive
  threshold on the billing metric. They are different mechanisms; you want both.
- **Least-privilege IAM**: the principal you operate as should not be the account root.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- Budgets: `Billing and Cost Management → Budgets → Create budget → Cost budget`.
- Billing alarm: `CloudWatch → Alarms → All alarms → Create alarm → EstimatedCharges metric`
  (must be created in `us-east-1` — billing metrics only publish there).
- Region picker: top-right region menu.

### DO
- [ ] Confirm/lock region in the global header. Region chosen: `__________`
- [ ] Create a Cost budget at ceiling `$______`; email target set to `______________`
- [ ] Create billing alarm at `$______` threshold. Alarm name: `jprs-billing-________`
- [ ] Confirm you are NOT operating as root; principal in use: `______________`

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- A budget/alarm threshold recommendation memo and the exact numbers to type.
- A one-paragraph "what each guardrail catches" explainer.
- **INSPECT-FIRST:** Brett reads the thresholds and confirms they match his own risk tolerance
  before entering them — no blind acceptance of a number.

### INTENTIONAL FAILURE TO INDUCE
- Create the billing alarm in a **non-`us-east-1`** region first and watch the `EstimatedCharges`
  metric be unavailable/empty. Observation: `________________________________`
- Lesson logged: billing metrics are global-but-published-in-`us-east-1`.

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- Budget visible in console (screenshot: `__________`), alarm in `OK`/`INSUFFICIENT_DATA` state
  (screenshot: `__________`), test notification email received: [ ] yes.

### RECOVER / ROLLBACK
- Delete budget + alarm; no ongoing cost. Teardown confirmed: [ ] (date `______`)

### TIME / COST
- Hands-on: ~30–45 min. · Cost added: **$0** (Budgets free; alarm within free alarm allotment).

### RECALL PROMPT (answer without notes before leaving Phase 0)
> "Why must the billing alarm live in us-east-1, and what's the difference between a Budget and a
> billing alarm?"  Brett's answer: `________________________________`

---

# PHASE 1 — S3 Immutable Snapshot Store (the record substrate)

**Product value:** the place every daily posting snapshot is written and never mutated. This is the
"record" the whole product's honesty rests on — you can only tell Brett what changed if yesterday's
snapshot is preserved exactly.

### STABLE CONCEPT
- **S3 bucket** = flat object store; structure is a **key/prefix** convention, not real folders.
- **Immutability by convention:** write each snapshot under a timestamped, content-addressed key and
  never overwrite. **Operator hard rule: NEVER enable S3 versioning** — use a **lifecycle policy** for
  retention instead. (Versioning is the tempting-but-banned shortcut here; know why you're not using it.)
- **Block Public Access** on by default; this bucket is private.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- `S3 → Create bucket` → name, region, keep Block Public Access ON.
- Lifecycle: `Bucket → Management → Lifecycle rules → Create rule`.

### DO
- [ ] Create bucket. Name: `jprs-snapshots-________`  ·  Region matches header: [ ]
- [ ] Confirm Block Public Access = ON (screenshot: `__________`)
- [ ] Decide + write the key convention in your own words:
      `snapshots/<provider>/<company>/<date>/<run-id>.json` → your version: `______________`
- [ ] Create a lifecycle rule (retention `____ days` → expire or transition). Rule name: `__________`
- [ ] Confirm versioning is **disabled**: [ ] (state WHY in your words: `______________`)

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- The lifecycle-rule JSON and the key-naming scheme.
- A bucket policy (private, least-privilege) draft.
- **INSPECT-FIRST:** Brett reads the lifecycle JSON and can state what it deletes and when, and can
  point to the line that would break immutability if it were an overwrite/versioning rule.

### INTENTIONAL FAILURE TO INDUCE
- Write two objects to the **same key** and observe the second silently replaces the first (no
  version history, because versioning is off). This proves *why the key must be unique per snapshot*.
  Observation: `________________________________`

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- Bucket exists, private, lifecycle rule active, versioning off. Console URL: `__________`
- A hand-uploaded test object appears at the expected key. Screenshot: `__________`

### RECOVER / ROLLBACK
- Empty + delete bucket (must empty first). Teardown confirmed: [ ] (date `______`)

### TIME / COST
- Hands-on: ~30 min. · Cost: **≈$0** at learning scale (storage of KB-sized JSON; requests trivial).

### RECALL PROMPT
> "Why are we forbidden from S3 versioning here, and how do we get immutability without it?"
> Brett's answer: `________________________________`

---

# PHASE 2 — First Collector Lambda + Execution Role

**Product value:** fetch ONE company's live postings from a sanctioned public ATS API
(Greenhouse/Lever/Ashby) and write one immutable snapshot to the Phase-1 bucket. First end-to-end
"data actually landed" moment.

### STABLE CONCEPT
- **Lambda** = event-driven function; you own the code, AWS owns the runtime/scaling.
- **Execution role** = the IAM role the *function assumes* to touch other services (this is the
  thing people forget — the function's permissions are the role's, not yours).
- **Least-privilege policy**: grant exactly `s3:PutObject` on the one bucket prefix, nothing more.
- **CloudWatch Logs**: the function's stdout/errors land in a log group — your primary debug surface.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- `Lambda → Create function → Author from scratch` (runtime: Python 3.x).
- Role: `Configuration → Permissions → Execution role`.
- Test: `Test` tab → configure a test event.
- Logs: `Monitor → View CloudWatch logs`.

### DO
- [ ] Create function. Name: `jprs-collector-________`  ·  Runtime: `__________`
- [ ] Paste the AI-prepared handler (see INSPECT-FIRST). Handler entrypoint: `__________`
- [ ] Attach an execution role with a **hand-scoped** S3 PutObject policy. Role name: `__________`
- [ ] Set env vars (bucket name, provider, company slug). Values: `______________`
- [ ] Run a test event; confirm a snapshot object appears in S3. Object key created: `__________`
- [ ] Open the log group and read one successful invocation. Log group: `__________`

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- The collector handler (thin — HTTP GET to the ATS public API, normalize, `put_object`; **no
  pandas/numpy**, per operator rule) and a mock/fixture ATS response for offline testing.
- The least-privilege execution-role policy JSON.
- **INSPECT-FIRST:** Brett must (a) name which ATS endpoint is being called and confirm it's a
  sanctioned public API, (b) read the IAM policy aloud and confirm it grants ONLY PutObject on the
  one prefix, (c) find the line that writes the S3 key.

### INTENTIONAL FAILURE TO INDUCE  (the IAM-recall failure)
- Deploy first with the execution role **missing `s3:PutObject`**. Invoke → get `AccessDenied` →
  read it in CloudWatch Logs → add the permission → re-invoke → success.
  Error text observed: `________________________________`
- This rebuilds the "the function's role, not my creds" reflex.

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- Snapshot object present in S3 with expected schema; log shows a clean run; IAM policy is minimal
  (no `s3:*`). Screenshots: `__________`

### RECOVER / ROLLBACK
- Delete function + execution role; delete test objects. Teardown confirmed: [ ] (date `______`)

### TIME / COST
- Hands-on: ~60–90 min. · Cost: **≈$0** (Lambda free-tier requests; a few KB to S3).

### RECALL PROMPT
> "When the function got AccessDenied, whose permissions were wrong — mine or the function's — and
> where exactly did I fix it?"  Brett's answer: `________________________________`

---

# PHASE 3 — SQS + Dead-Letter Queue  (the recall lab)

**Product value:** decouple "list the companies to collect" from "collect each one" so one bad
company/provider can't sink the whole run — failed messages land in a DLQ instead of vanishing.
**This is the phase that directly rebuilds the SQS/DLQ path Brett blanked on in the interview.**

> **Coordination:** the **reliability seat owns the detailed first SQS/DLQ lab spec** (visibility
> timeout, `maxReceiveCount`, redrive mechanics). This workbook block frames the *manual recall
> exercise*; adopt the reliability seat's numbers where they differ.

### STABLE CONCEPT
- **SQS** = durable message buffer; a producer enqueues, a consumer polls.
- **Visibility timeout** = how long a picked-up message is hidden from other consumers; too short and
  a slow consumer causes duplicate processing.
- **Dead-Letter Queue** = where a message goes after `maxReceiveCount` failed processing attempts,
  via a **redrive policy** — so a poison message is quarantined, not lost, and not retried forever.
- **Redrive** = deliberately moving DLQ messages back to the main queue after you fix the cause.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- `SQS → Create queue` (Standard) — create the **DLQ first**, then the main queue.
- Main queue: `Dead-letter queue` section → enable → point at DLQ → set `Maximum receives`.
- Redrive: DLQ → `Start DLQ redrive`.

### DO
- [ ] Create DLQ. Name: `jprs-collect-dlq-________`
- [ ] Create main queue. Name: `jprs-collect-________`  ·  Visibility timeout: `____ s`
- [ ] Wire redrive policy: main → DLQ, `Maximum receives` = `____`
- [ ] Grant the collector/worker role `sqs:SendMessage` / `sqs:ReceiveMessage` as appropriate
      (least privilege). Policy scoped to these queue ARNs only: [ ]
- [ ] Send a test message by hand; poll and receive it. Message id: `__________`

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- A worker Lambda that consumes a queue message (one company), calls the collector logic, and on
  error raises so SQS retries.
- The SQS access policy JSON; recommended visibility timeout and `maxReceiveCount` (reconcile with
  reliability seat).
- **INSPECT-FIRST:** Brett must state, in his own words, the message lifecycle: enqueue → receive
  (hidden for visibility-timeout) → success deletes it / failure returns it → after N failures →
  DLQ. He points at the `maxReceiveCount` and the visibility-timeout values and says what each does.

### INTENTIONAL FAILURE TO INDUCE  (the core lab)
- Give the worker a message it will always fail on (e.g., an unreachable/garbage company slug).
  Watch it be received, retried `maxReceiveCount` times, and **land in the DLQ**. Inspect the DLQ
  message. Then fix the cause and **redrive** it back to success.
  Retry count observed: `____`  ·  DLQ arrival confirmed: [ ]  ·  Redrive succeeded: [ ]
- Second failure: set visibility timeout **too low** and observe duplicate processing. Observation:
  `________________________________`

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- A poison message demonstrably in the DLQ, then successfully redriven and processed. Queue-depth
  screenshots before/after: `__________`

### RECOVER / ROLLBACK
- Purge + delete both queues. Teardown confirmed: [ ] (date `______`)

### TIME / COST
- Hands-on: ~90 min. · Cost: **≈$0** (SQS free-tier request allotment covers learning volume).

### RECALL PROMPT (the interview question that broke)
> "Walk me through what happens to a message that keeps failing — where does it go, what controls
> that, and how do I get it back?"  Brett's answer: `________________________________`

---

# PHASE 4 — EventBridge Scheduler (daily trigger)

**Product value:** the collection now runs itself once a day. This is what makes it a *radar* instead
of a script Brett remembers to run.

### STABLE CONCEPT
- **EventBridge Scheduler** = managed cron-as-a-service; a **schedule** invokes a **target** (Lambda,
  Step Functions, SQS) on a rate/cron expression, in a stated **timezone**.
- The scheduler needs its **own IAM role** with permission to invoke the target — another
  "permissions live on the caller" moment.
- Free tier: 14,000,000 invocations/month (verified 2026-07-28) — Brett's 1/day is free forever.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- `EventBridge → Scheduler → Schedules → Create schedule` → recurring, cron/rate, timezone → target.

### DO
- [ ] Create schedule. Name: `jprs-daily-________`  ·  Expression: `__________`  ·  TZ: `__________`
- [ ] Target = (collector Lambda OR Step Functions state machine from Phase 5). Target: `__________`
- [ ] Create/attach the scheduler's invoke role. Role name: `__________`
- [ ] Confirm one successful scheduled fire (check target's logs/executions). First fire at: `______`

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- The cron/rate expression + timezone rationale; the scheduler invoke-role policy JSON.
- **INSPECT-FIRST:** Brett reads the cron expression and states the exact local time it fires, and
  confirms the invoke role points at the right target ARN.

### INTENTIONAL FAILURE TO INDUCE
- Deploy the schedule with the **invoke role missing the target permission** (or a UTC/local
  timezone mistake). Observe it not firing / firing at the wrong hour; find the cause in the
  scheduler's error metrics + target logs. Observation: `________________________________`

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- A scheduled (not manual) invocation visible in the target's execution history at the expected
  time. Screenshot: `__________`

### RECOVER / ROLLBACK
- Disable then delete schedule. Teardown confirmed: [ ] (date `______`)

### TIME / COST
- Hands-on: ~30–45 min. · Cost: **$0** (within 14M free invocations/mo).

### RECALL PROMPT
> "My daily job fired at the wrong time / didn't fire — what are the two most likely causes and
> where do I check each?"  Brett's answer: `________________________________`

---

# PHASE 5 — Step Functions Orchestration (fan-out over companies)

**Product value:** one daily run cleanly fans out over N companies, isolates per-company failure,
retries transient errors, and gives a visual execution history — the operational backbone.

> **Coordination:** the **architecture seat owns the service topology**; confirm SFN (vs. plain
> SQS fan-out) earns its place before building. Included here because its execution-history +
> retry/catch semantics are high-value recall AND real reliability.

### STABLE CONCEPT
- **State machine (ASL)** = a JSON-defined workflow of states with explicit transitions.
- **Map state** = fan-out over a list (the companies) with bounded concurrency.
- **Retry / Catch** = declarative transient-retry and error-routing at the state level.
- **Execution history** = per-run, per-state visual record — the best "what happened" surface AWS
  gives you. Free tier: 4,000 state transitions/month (verified 2026-07-28) — ample for daily fan-out.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- `Step Functions → State machines → Create → Standard` → paste ASL → assign role.
- Run: `Start execution`; inspect: `Executions → <id> → Graph/Table view`.

### DO
- [ ] Create state machine (Standard). Name: `jprs-daily-collect-________`
- [ ] Paste AI-prepared ASL (see INSPECT-FIRST). Uses a Map state over companies: [ ]
- [ ] Assign an execution role scoped to invoke the worker Lambda + read config only. Role: `______`
- [ ] Start one execution by hand; read the Graph view. Execution id: `__________`
- [ ] Confirm one company's failure does NOT fail the whole run (isolation). Observed: [ ]

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- The ASL definition (Map + Retry + Catch), the state-machine execution-role policy.
- **INSPECT-FIRST:** Brett must trace the ASL by eye: entry state → Map → per-item Lambda → Catch
  path on failure. He states what `Retry` backoff and `Catch` do without running it.

### INTENTIONAL FAILURE TO INDUCE
- Make one company in the list deterministically fail. Confirm the **Catch** routes it to a
  failure/record state while the other companies succeed — then read exactly which state failed in
  the execution history. Failed state name: `__________`

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- Green execution with one company isolated to a caught-failure branch; the run still produced the
  other snapshots. Execution-graph screenshot: `__________`

### RECOVER / ROLLBACK
- Delete state machine + role. Teardown confirmed: [ ] (date `______`)

### TIME / COST
- Hands-on: ~90 min. · Cost: **≈$0** (well under 4,000 free transitions/mo at daily × ~20 companies).

### RECALL PROMPT
> "How does my daily run keep one broken company from killing the whole batch, and where do I see
> which state failed?"  Brett's answer: `________________________________`

---

# PHASE 6 — Change Detection & Daily "What Changed" Report  (V1 DELIVERABLE)

**Product value:** THE V1 promise — "save postings every day and tell me what changed." Compares
today's snapshots against the prior stored snapshots and emits: new postings, disappeared postings,
and materially-changed postings, with first-seen dates. **This is the first day the tool earns its
keep in Brett's actual job search.**

> **Coordination:** the **data seat owns posting identity + change-event modeling** (what counts as
> "the same posting", what fields make a change "material"). This block owns the *learning framing +
> the honesty guardrail*, not the diff schema.

### STABLE CONCEPT
- **Idempotent, evidence-anchored comparison:** every claim in the report ("this posting
  disappeared") must point at two stored snapshots (present yesterday, absent today) — never at a
  model's opinion.
- **"Nothing changed" ≠ "the collector didn't run":** the report must state which. A run that
  produced zero snapshots is a *failure signal*, not a *quiet day*. (Guardrail from shared context.)
- **Behavior ≠ accusation:** the report describes observable posting behavior; it must NOT claim a
  job is fake/fraudulent. LLM text is never the evidence.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- This phase is mostly the worker/report Lambda + reading S3; UI touch is S3 object inspection and
  the report Lambda logs. (Same Lambda/S3 paths as Phases 1–2.)

### DO
- [ ] Deploy the AI-prepared change-detection worker. Function: `jprs-diff-________`
- [ ] Run it against two consecutive real snapshot days. Report object written to: `__________`
- [ ] Confirm the report distinguishes new / disappeared / changed, each with snapshot references.
- [ ] Confirm the report's header states run-health: `RAN_OK` vs `NO_SNAPSHOTS` (didn't run). [ ]
- [ ] Read one real day's report and use it in the job search. First real use date: `__________`

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- The diff logic (per data seat's identity/change model), the report schema, test fixtures with a
  known new/disappeared/changed case.
- **INSPECT-FIRST:** Brett must confirm (a) each reported change cites specific snapshot keys, (b)
  there is a distinct code path for "no snapshots produced" vs "no changes", (c) no line asserts
  fake/real — only observed behavior.

### INTENTIONAL FAILURE TO INDUCE
- Feed the diff a day where the **collector produced zero snapshots** (simulate a total source
  outage) and confirm the report says `COLLECTORS DID NOT RUN` — NOT "all jobs disappeared."
  Output observed: `________________________________`
- This is the single most important honesty test in the whole build.

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- A real multi-day report with correct new/disappeared/changed classification, every item
  traceable to snapshots, and a correct run-health header. Report sample path: `__________`

### RECOVER / ROLLBACK
- Delete diff function; snapshots and reports in S3 are safe to keep. Teardown: [ ] (date `______`)

### TIME / COST
- Hands-on: ~90–120 min. · Cost: **≈$0** (Lambda + S3 reads at KB scale).

### RECALL PROMPT
> "If tomorrow's report says nothing changed, how do I know the collectors actually ran — and why is
> that distinction the whole point?"  Brett's answer: `________________________________`

---

# PHASE 7 — CloudWatch Alarms & Observability

**Product value:** Brett gets told when the *system* is broken (collector didn't run, DLQ filling up)
instead of silently trusting a quiet report. Closes the "source failure must never masquerade as mass
job disappearance" guarantee at the ops layer.

### STABLE CONCEPT
- **Metric → Alarm → Notification (SNS):** an alarm watches a metric against a threshold and fires an
  action (email via SNS) on breach.
- Two alarms that matter here: **collector-didn't-run** (no successful execution in the expected
  window) and **DLQ-not-empty** (poison messages accumulating).
- A **dashboard** is a read surface; the **alarm** is the actor. Don't confuse a pretty dashboard for
  actual alerting.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- `CloudWatch → Alarms → Create alarm → select metric → threshold → SNS action`.
- SNS: `SNS → Topics → Create topic → create subscription (email) → confirm`.

### DO
- [ ] Create SNS topic + confirm an email subscription. Topic: `jprs-alerts-________`
- [ ] Alarm 1: DLQ `ApproximateNumberOfMessagesVisible` > 0. Alarm name: `__________`
- [ ] Alarm 2: collector success count < 1 in the daily window. Alarm name: `__________`
- [ ] (Optional) A small dashboard with run count, snapshots written, DLQ depth. URL: `__________`

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- Alarm threshold/period recommendations; the metric-math for "didn't run in window"; SNS wiring notes.
- **INSPECT-FIRST:** Brett states what each alarm watches and what a breach *means operationally*
  ("DLQ > 0 means a company failed all retries", "0 successes means the daily radar is blind today").

### INTENTIONAL FAILURE TO INDUCE
- **Suppress a scheduled run** (disable the Phase-4 schedule for a day) and confirm the
  collector-didn't-run alarm fires and the email arrives. Alarm-fired timestamp: `__________`
- Optionally push a poison message to trip the DLQ alarm too.

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- Both alarms transition to `ALARM` on the induced failures and email is received; return to `OK`
  after recovery. Screenshots + email receipts: `__________`

### RECOVER / ROLLBACK
- Delete alarms + SNS topic. Re-enable the daily schedule. Teardown: [ ] (date `______`)

### TIME / COST
- Hands-on: ~60 min. · Cost: **≈$0** (a few alarms within free allotment; SNS email pennies).

### RECALL PROMPT
> "Which alarm tells me the radar went blind, and how is that different from the alarm that tells me
> one company is failing?"  Brett's answer: `________________________________`

---

# PHASE 8 — Bedrock Change Summaries (OPTIONAL, evidence-pointing only)

**Product value:** a plain-English daily digest ("3 new Applied-AI roles at X; the Zapier role's
description changed") layered ON TOP of the deterministic diff. Reuses the CFR `bedrock_client.py`
wrapper. **Gate: only build this once the deterministic report is trusted** — the LLM decorates, it
never decides.

### STABLE CONCEPT
- **Bedrock `invoke_model`** = call a hosted model; you pay per token; cost control is on you.
- **LLM as narrator, not authority:** the summary must be generated *from* the deterministic diff
  output and must cite the same snapshot evidence. It is NEVER the source of a fact and NEVER decides
  whether a posting disappeared / is real / is fake. (Hard constraint from shared context.)

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- Mostly code (reuse CFR Bedrock wrapper); console touch = model access in `Bedrock → Model access`
  and cost inspection in Billing. Baseline models: Haiku (cheap), 3.5 Sonnet (strong) per CFR env.

### DO
- [ ] Confirm Bedrock model access enabled for the chosen model(s). Model id: `__________`
- [ ] Deploy the summary step; it consumes the diff output only. Function/step: `__________`
- [ ] Verify every sentence in a sample summary maps to a diff item + snapshot. Sample: `__________`
- [ ] Set a token/cost ceiling and confirm one day's summary cost. Observed cost: `$______`

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- A prompt that takes the structured diff and produces a grounded summary; the reused Bedrock client
  config; a token-budget guard.
- **INSPECT-FIRST:** Brett confirms the prompt is fed ONLY the deterministic diff (not raw web/LLM
  guessing) and that the output template forbids fake/real language.

### INTENTIONAL FAILURE TO INDUCE
- Feed the summarizer a diff with an ambiguous case and confirm it describes *behavior* ("posting no
  longer appears in the feed") and does NOT assert "this was a fake job." If it overclaims, tighten
  the prompt. Observation: `________________________________`

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- A grounded daily summary, every claim traceable to the diff, no fake/real assertions, cost within
  ceiling. Sample + cost screenshot: `__________`

### RECOVER / ROLLBACK
- Remove the summary step; deterministic report still stands alone. Teardown: [ ] (date `______`)

### TIME / COST
- Hands-on: ~90 min. · Cost: **cents/day** at Haiku for one short daily digest; set a hard ceiling.

### RECALL PROMPT
> "Where do the facts in the summary come from, and what is the LLM specifically NOT allowed to
> decide?"  Brett's answer: `________________________________`

---

# PHASE 9 — Infrastructure-as-Code Reconstruction  (manual → code)

**Why this is LATE, not early:** the manual console work in Phases 0–8 is what rebuilds recall. IaC is
only introduced AFTER Brett has created, wired, observed, broken, and explained the resources by hand.
Now he proves mastery by **expressing the same stack as code**, tearing the manual stack down, and
redeploying from the template. This is the reconstruction test, not a shortcut he skipped the console with.

### STABLE CONCEPT
- **IaC (SAM or CDK)** = declarative/programmatic description of the whole stack; `deploy` creates it,
  `delete` removes it, and the template is the reproducible source of truth.
- The learning value is **round-tripping**: can Brett map every hand-built resource to a template
  block? Gaps reveal what he only half-understood in the console.
- **Drift** = difference between deployed reality and template; understanding drift is the point.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- Mostly CLI/local (`sam deploy` / `cdk deploy`) + `CloudFormation → Stacks` to watch events and
  confirm the stack. Console role here is *observation of the CFN stack*, not clicking resources.

### DO
- [ ] For EACH manually-built resource, write/verify its template block. Resource→block checklist:
      S3 [ ] · collector Lambda+role [ ] · SQS+DLQ [ ] · Scheduler [ ] · Step Functions [ ] ·
      diff Lambda [ ] · alarms+SNS [ ] · (Bedrock step [ ])
- [ ] Deploy the stack into a **fresh prefix/name** alongside the manual one. Stack name: `__________`
- [ ] Diff behavior: does the IaC stack produce identical snapshots/reports? Observed: `__________`
- [ ] Tear down the MANUAL resources; keep the IaC stack as the going-forward system. Confirmed: [ ]

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- A draft SAM/CDK template mirroring the hand-built stack.
- **INSPECT-FIRST (highest bar in the workbook):** Brett must be able to point at each template block
  and name the console screen where he built its equivalent by hand. If he can't, that block goes
  back to a console refresher before he accepts it. **AI must not let IaC paper over a gap in recall.**

### INTENTIONAL FAILURE TO INDUCE
- Deliberately omit one IAM permission (or one env var) from the template, deploy, watch it fail the
  same way it failed in the manual phase — proving he understands the dependency, not just the syntax.
  Observation: `________________________________`

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- A CloudFormation stack that reproduces the working V1 end-to-end, with Brett able to narrate every
  block from his own manual experience. Stack + narration notes: `__________`

### RECOVER / ROLLBACK
- `sam delete` / `cdk destroy` removes everything cleanly (the payoff of IaC). Teardown: [ ] (`______`)

### TIME / COST
- Hands-on: ~2–3 hrs. · Cost: **≈$0** additional (same resources, now templated).

### RECALL PROMPT
> "Point at any resource in my stack and tell me both: the console screen I built it on, and the
> template block that now defines it."  Brett's answer: `________________________________`

---

# PHASE 10 — Parquet + Athena Historical Intelligence  (MATURE, gated)

**Product value:** the mature promise — turn accumulated first-seen dates, repost patterns, and
change history into an *expected-return* read on where Brett's effort likely pays off. **Gate: only
build once there is enough accumulated history to query (weeks–months) AND a real analytical question
Brett actually wants answered.** Do not build the warehouse before there's data to warehouse.

### STABLE CONCEPT
- **Columnar Parquet in S3, partitioned** (e.g., by date/provider) = cheap, scan-efficient storage.
- **Athena** = serverless SQL over S3; you pay per TB scanned ($5/TB verified 2026-07-28), so
  **partitioning + Parquet compression is the cost lever** (Parquet ~10× cheaper than raw JSON scan).
- **No paid Glue crawler / no always-on infra** (shared-context cost rule) — define the table by hand
  or with a cheap manual DDL, not a paid crawler.

### CURRENT-UI PATH (drift-prone)  ·  source: `__________`  ·  date-checked: `__________`
- `Athena → Query editor` → set a query-results S3 location → run DDL to define the external table →
  query. Watch **Data scanned** per query as the cost meter.

### DO
- [ ] Add a step that writes/rolls snapshots into partitioned Parquet. Parquet prefix: `__________`
- [ ] Define the Athena external table by hand (DDL from AI). Table: `__________`
- [ ] Run 2–3 real analytical queries (hiring momentum, repost frequency, first-seen age).
- [ ] Record `Data scanned` per query and confirm partitioning kept it tiny. Scanned: `______ MB`

### AI MAY PREPARE IN ADVANCE  (`AI_IMPLEMENTATION`)
- The Parquet-writing step, the table DDL, and the analytical SQL — clearly labeled as *evidence
  summaries, not truth claims about a job being fake/real*.
- **INSPECT-FIRST:** Brett reads each query and states what observable pattern it measures and what
  it does NOT prove (momentum ≠ "this company will hire me"; repost ≠ "fake job").

### INTENTIONAL FAILURE TO INDUCE
- Run a query **without the partition filter** and watch `Data scanned` (and cost) jump; then add the
  partition predicate and watch it collapse. Before/after scanned: `______ / ______`

### EVIDENCE OF SUCCESS (`SHARED_VERIFY`)
- Real queries returning momentum/first-seen/repost signals from actual accumulated history, each
  framed as observed behavior, with per-query scan cost negligible. Query samples: `__________`

### RECOVER / ROLLBACK
- Drop the table (metadata only); Parquet in S3 is safe to keep or lifecycle out. Teardown: [ ] (`__`)

### TIME / COST
- Hands-on: ~2–3 hrs. · Cost: **cents** at this scale if partitioned; can spike if you scan raw —
  which is exactly the induced-failure lesson.

### RECALL PROMPT
> "Why does partitioning my Athena table change the *cost* of the same question, and what's the
> honest limit of what a hiring-momentum number tells me?"  Brett's answer: `________________`

---

## Cross-phase teardown ledger (fill as you go — nothing left running)

| Phase | Resource(s) | Torn down? | Date | Residual monthly cost |
|---|---|---|---|---|
| 0 | Budget, billing alarm | [ ] | `____` | $0 |
| 1 | S3 bucket | [ ] | `____` | storage only |
| 2 | Collector Lambda + role | [ ] | `____` | $0 |
| 3 | SQS + DLQ | [ ] | `____` | $0 |
| 4 | EventBridge schedule | [ ] | `____` | $0 |
| 5 | Step Functions + role | [ ] | `____` | $0 |
| 6 | Diff Lambda | [ ] | `____` | $0 |
| 7 | Alarms + SNS | [ ] | `____` | ~$0 |
| 8 | Bedrock summary step | [ ] | `____` | usage only |
| 9 | IaC stack (replaces manual) | [ ] | `____` | same as V1 |
| 10 | Parquet + Athena table | [ ] | `____` | storage + per-query |

> **Standing rule (shared context):** never leave persistent always-on infra (RDS/NAT/EC2) — none of
> the above is always-on. If any phase ever tempts one, STOP and surface to the operator.
