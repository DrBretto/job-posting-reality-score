# JPRS V1 — Deploy Guide (`infra/`)

This directory is the infrastructure-as-code (AWS SAM) for the **Job Posting Reality Score**
V1 stack. One `sam deploy` stands up everything phases P2–P7 built by hand: the S3 bucket,
SQS collect-queue + DLQ, two EventBridge Scheduler schedules, the four Lambdas
(enumerate / collector / differ / report) plus the optional narrator, the Standard Step
Functions assembler, the A1–A7 CloudWatch alarms → SNS, and the M5 cost fence
(AWS Budgets + a Budget Action).

> **This replaces every resource Brett hand-built in P0–P5.** After the stack is deployed and
> the first daily run is verified (below), the hand-built console resources can be deleted —
> the stack owns them now. Do that only after verification, and export any `raw/` you want to
> keep first (`raw/` is the one irreplaceable tier).

---

## 1. Prerequisites

- **AWS SAM CLI** ≥ 1.137 (`sam --version`). Install: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
- **AWS credentials** for the target account (single account, `us-east-1`). Prefer IAM
  Identity Center short-lived creds: `aws sso login` then confirm `aws sts get-caller-identity`.
- **Python 3.13** available for `sam build` (Lambdas are `python3.13`, `arm64`).
- The **application code** in the repo-root `src/` tree exposing these handlers (built in
  parallel; `sam build` packages `src/` for every function):
  - `enumerate/handler.py` → `handler`
  - `collector/handler.py` → `handler`
  - `differ/handler.py` → `handler`
  - `report/handler.py` → `handler`
  - `llm/narrator.py` → `handler` (only if `EnableNarrator=true`)
  - a `requirements.txt` at the `src/` root (thin deps only — no pandas/numpy/torch).

The template `sam validate --lint` passes as-is; the app code is only needed for `sam build`/deploy.

---

## 2. Build and deploy

From `infra/`:

```bash
sam build
sam deploy --guided        # first time; writes/updates samconfig.toml
```

On later deploys just `sam build && sam deploy` (config is already in `samconfig.toml`).

### Parameter walkthrough (`--guided` prompts)

| Parameter | Default | What it is |
|---|---|---|
| `BucketName` | `jprs-prod-bw-20260731` | The single data bucket (globally unique; keep or change). |
| `AlertEmail` | `drbretto82@gmail.com` | Receives ops alarms A1–A7 and AWS Budgets alerts. **You must confirm the SNS subscription email** (step 5). |
| `DigestRecipient` | `drbretto82@gmail.com` | Where the daily digest is sent (SES). Must be a **verified SES identity** while SES is in sandbox. |
| `SesSender` | `drbretto82@gmail.com` | Verified SES **From** identity for the digest. |
| `CollectCron` | `cron(0 7 * * ? *)` | Collect run — 07:00 daily in `TimeZone`. |
| `AssembleCron` | `cron(0 9 * * ? *)` | Assemble run — 09:00 daily (collect + a 2h offset so the queue has settled). |
| `TimeZone` | `America/New_York` | IANA timezone applied to both schedules. |
| `EnableNarrator` | `false` | Feature flag for the optional Bedrock narrator. Leave `false` for V1. |

Answer **yes** to `Allow SAM CLI IAM role creation` and to
`Save arguments to configuration file`. Capabilities needed: `CAPABILITY_NAMED_IAM`
(already set in `samconfig.toml`; the stack creates named IAM roles + two named managed
policies).

Non-interactive equivalent:

```bash
sam deploy \
  --stack-name jprs-v1 --region us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM --resolve-s3 \
  --parameter-overrides AlertEmail=you@example.com DigestRecipient=you@example.com SesSender=you@example.com
```

Stack outputs (`sam list stack-outputs --stack-name jprs-v1`): data bucket name,
collect-queue URL, collect-DLQ URL, assembler state machine ARN, SNS topic ARN.

---

## 3. Seed the company registry into SSM (**required before the first run**)

`enumerate` reads `/jprs/companies` (a JSON array of `{provider, board_token, company_id}`)
and fans one SQS message out per company. Seed it once:

```bash
aws ssm put-parameter --region us-east-1 \
  --name /jprs/companies --type String \
  --value '[
    {"provider":"greenhouse","board_token":"example","company_id":"example-co"},
    {"provider":"lever","board_token":"another","company_id":"another-co"}
  ]'
```

Update it later with `--overwrite`. The parameter is intentionally **not** managed by the
template so redeploys never clobber your edits. The assembler state machine reads the same
`/jprs/companies` value to know which companies to diff.

---

## 4. Verify SES (one-time, sandbox is fine for V1)

SES starts in **sandbox** — that is fine for a single self-recipient; **no production-access
request is needed for V1.** Verify the identity you used for `SesSender` / `DigestRecipient`:

```bash
aws ses verify-email-identity --region us-east-1 --email-address drbretto82@gmail.com
```

Click the confirmation link SES emails you. (If `SesSender` and `DigestRecipient` differ,
verify both while in sandbox.)

---

## 5. Confirm the alarm/SNS email subscription

Deploy creates an `email` subscription on the `jprs-ops-alerts` SNS topic for `AlertEmail`.
AWS sends a **"Subscription Confirmation"** email — **click Confirm subscription** or no alarm
will ever reach you. Verify:

```bash
aws sns list-subscriptions-by-topic --region us-east-1 \
  --topic-arn "$(sam list stack-outputs --stack-name jprs-v1 --output json \
     | python3 -c 'import sys,json;print([o["OutputValue"] for o in json.load(sys.stdin) if o["OutputKey"]=="OpsAlertTopicArn"][0])')"
```

`SubscriptionArn` should not be `PendingConfirmation`.

> **First-deploy note:** alarms **A2** (missed run) and **A3** (report not assembled) use
> `treatMissingData=breaching`, so they sit in **ALARM until the first successful run** emits
> the `CollectRunSuccess` / `ReportComplete` custom metrics. That is expected — they are the
> NO-RUN / no-report detectors. They clear after the first good day.

---

## 6. Confirm the first daily run

You can wait for the scheduled times or force a run now.

**Force the collect leg** (invokes `enumerate`, which writes the RUN_OPEN manifest and fans out):

```bash
aws lambda invoke --region us-east-1 --function-name jprs-enumerate \
  --payload '{"trigger":"manual"}' --cli-binary-format raw-in-base64-out /dev/stdout
```

Then watch the pipeline:

```bash
# collectors drained, DLQ stays empty
aws sqs get-queue-attributes --region us-east-1 \
  --queue-url "$(aws sqs get-queue-url --region us-east-1 --queue-name jprs-collect-dlq --query QueueUrl --output text)" \
  --attribute-names ApproximateNumberOfMessages

# S3 tiers populated
aws s3 ls s3://jprs-prod-bw-20260731/ --recursive | grep -E 'manifest/|raw/|normalized/|status/'
```

**Force the assemble leg** (StartExecution on the assembler; use the ARN from stack outputs):

```bash
aws stepfunctions start-execution --region us-east-1 \
  --state-machine-arn <DailyAssembleStateMachineArn> --input '{"trigger":"manual"}'
```

A successful run leaves: a report under `reports/`, a digest email in `DigestRecipient`'s inbox,
DLQ depth 0, and alarms A1–A7 all in `OK`/`INSUFFICIENT_DATA` (A2/A3 flip to OK after the metrics land).

---

## 7. How M4 and M5 are enforced (read before trusting the boundary)

- **M4 — the `current/` prefix IAM split.** IAM scopes S3 by prefix, so the write scopes are
  split so no role can cross the one-directional flow:
  - `collector` → `PutObject` on `raw/*`, `normalized/*`, `status/*` **only** (it writes the
    SUCCESS sentinel to `status/`, **never** `current/`).
  - `differ` → owns `PutObject` on `current/*` + `events/*` (the authoritative live-job set).
  - `report` → `PutObject` on `reports/*` only; reads processed tiers.
  - No role has `Resource: "*"` on S3, and no role has `s3:DeleteObject` on `raw/`.
  Because collector and differ now write to **different prefixes**, a buggy/compromised collector
  cannot rewrite `current/current_jobs.json`.
- **M5 — the enforcing cost fence.** `AWS::Budgets::Budget jprs-monthly-5` emails at 80%/100%
  actual + 80% forecast. `jprs-ceiling-10` ($10) carries an `AWS::Budgets::BudgetsAction`
  (`APPLY_IAM_POLICY`) that, at 100% of $10, **attaches the `jprs-budget-lockdown-deny` managed
  policy to both scheduler roles** — denying `lambda:InvokeFunction`, `states:StartExecution`,
  and `sqs:SendMessage` on `jprs-*`, which halts all *new* scheduled work. This is the
  ADR-0001 mechanism: AWS Budget Actions cannot disable a schedule directly, so the supported
  path is an IAM lockdown. **It is a reactive backstop, not an instantaneous circuit breaker**
  (Budgets cost data lags). The real cost *prevention* is: no always-on infra, reserved
  concurrency on the collector, and **30-day log retention on every function log group**
  (explicit `AWS::Logs::LogGroup` resources — no never-expire default drift).

The whole thing is expressed cleanly in CFN/SAM — including the Budget Action — so there is **no
manual step required for the cost fence.** (Contrast: the earlier hand-built plan had to wire the
Budget Action by hand at P4 because the target role didn't exist yet; here it and the roles are
created together.)

To lift a lockdown after a cost incident: fix the cause, then detach the policy —
`aws iam detach-role-policy --role-name jprs-scheduler-collect-role --policy-arn <BudgetLockdownPolicyArn>`
(and the assemble role) — or delete + recreate the budget action.

---

## 8. Teardown

```bash
# 1. Stop all runs first (disables both schedules without deleting anything else)
aws scheduler update-schedule --region us-east-1 --name jprs-collect-daily  --state DISABLED \
  --schedule-expression "cron(0 7 * * ? *)" --flexible-time-window Mode=OFF
aws scheduler update-schedule --region us-east-1 --name jprs-assemble-daily --state DISABLED \
  --schedule-expression "cron(0 9 * * ? *)" --flexible-time-window Mode=OFF

# 2. Export raw/ if you want to keep history (raw/ is the only irreplaceable tier)
aws s3 sync s3://jprs-prod-bw-20260731/raw/ ./jprs-raw-backup/

# 3. Empty the bucket (it is RETAINed on stack delete, so empty it by hand)
aws s3 rm s3://jprs-prod-bw-20260731/ --recursive

# 4. Delete the stack (removes Lambdas, queues, state machine, alarms, SNS, budgets, roles)
sam delete --stack-name jprs-v1 --region us-east-1

# 5. The bucket has DeletionPolicy: Retain — delete it explicitly once emptied
aws s3 rb s3://jprs-prod-bw-20260731

# 6. Confirm $0 on the next billing cycle; no lingering INSUFFICIENT_DATA alarms
```

`sam delete` leaves the `raw/` bucket (Retain) and the `/jprs/companies` SSM parameter (not
stack-managed) — remove those two by hand if you want a truly zero-footprint teardown.

---

## Design notes (why the assembler looks the way it does)

- **Two schedules, not one** (ADR-06 / reliability runbook): schedule #1 → `enumerate` Lambda
  (writes RUN_OPEN manifest, fans out to SQS); schedule #2 → Step Functions `jprs-daily-assemble`
  after an offset, so completeness is judged against a settled queue.
- The assembler reads the company set from **SSM `/jprs/companies`** via the native Step Functions
  AWS SDK integration (no extra Lambda), then **Maps** over companies with per-branch Retry +
  Catch (Map isolation). `differ` itself skips any company lacking a fresh SUCCESS sentinel, so an
  uncollected source is never diffed to "all removed." **`report` is the completeness judge** — it
  compares the manifest's expected sources against SUCCESS sentinels (manifest-vs-sentinel, **never
  wall-clock**) and is invoked both on the happy path (`mode:assemble`) and via the top-level
  Catch (`mode:incomplete`) so a degraded report is always produced.
