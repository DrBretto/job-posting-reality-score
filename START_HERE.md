# Start Here: Job Posting Reality Score

This is Brett's single operator guide for the project. Start here every time. It tells you what phase
is active, what you must do manually, what the AI should do, and what proves the phase is finished.

You do not need to reread the committee packet to continue normal project work.

## Current Position

- **Active phase:** P0 — AWS account guardrails
- **Status:** Local instructions and policy files are ready; manual AWS work is not complete
- **Region:** `us-east-1`
- **Project AWS resources:** None as of the last verification
- **Next phase:** P1 — private S3 record substrate, currently locked
- **Current branch:** `codex/p0-foundation`

## What To Do Right Now

Complete these first three actions, then report the results using the template below:

1. Inspect the existing root-user access key without deleting it blindly.
2. Add MFA to the normal `drbretto-admin` IAM user.
3. Enable CloudWatch billing alerts in Billing preferences.

The complete P0 sequence appears below. You can stop after any numbered section and resume here later.

## Working Agreement

### Brett does manually

- Signs in to AWS and navigates the console.
- Creates and configures AWS resources through P8.
- Performs each intentional failure exercise.
- Reads every policy or script before using it.
- Records what happened and explains the AWS concept without notes.

### The AI does

- Creates application code, tests, fixtures, policies, and documentation locally.
- Gives exact console values and explains why they are used.
- Inspects AWS state read-only when verification is requested.
- Diagnoses failures from the actual error and logs.
- Updates this guide, the phase plan, and session status after verified progress.

### The AI does not

- Bulk-deploy P0-P8 or silently create AWS resources.
- Mark a phase complete because documentation or code exists.
- Delete keys, data, or resources for Brett.
- Move to the next phase before the current done gate and recall prompt pass.

## Safety Rules

1. Never put account numbers, private ARNs, access-key IDs, secret keys, MFA codes, or personal
   notification addresses in Git or chat.
2. Do not delete an access key until you know what depends on it.
3. Use `us-east-1` unless a worksheet intentionally tells you to visit another region.
4. Never enable S3 versioning for this project.
5. Do not add NAT Gateway, EC2, RDS, OpenSearch, EKS, Kinesis, paid Glue jobs/crawlers, provisioned
   Lambda concurrency, or other always-on infrastructure.
6. Stop and inspect any unexpected charge before continuing.
7. Do not automate job applications, harvest personal contact information, or scrape authenticated
   sources.

# P0: Account Guardrails

Expected hands-on time: approximately 45-60 minutes, plus possible waiting time for AWS billing
metrics to begin publishing. Expected project cost: `$0`.

## Step 1: Review Root Security

Use the root user only for this review.

1. Sign in to the AWS console as root.
2. Open **Security credentials**.
3. Confirm root MFA is enabled.
4. Find the existing root access key and inspect its last-used information.
5. Determine whether a known tool or workload depends on it.
6. If it is clearly unused, disable it first, verify nothing breaks, and then delete it.
7. If its use is unclear, leave it in place for now and record that investigation is required.
8. Sign out of root.

Record only one of these descriptions:

- `never used / safe to remove`
- `recently used / dependency identified`
- `usage unclear / investigation required`

Do not record the key ID.

## Step 2: Secure the Daily IAM User

Sign in as the normal `drbretto-admin` IAM user.

1. Open **IAM → Users → drbretto-admin → Security credentials**.
2. Add an MFA device.
3. Confirm the next sign-in requires MFA.
4. Note privately which local tools or deployed workloads use the user's existing long-lived access
   key.
5. Do not rotate or delete that key until its dependencies are known.

P0 needs MFA enabled now. Migrating human access to IAM Identity Center can happen later.

## Step 3: Enable CloudWatch Billing Alerts

1. Open **Billing and Cost Management → Billing preferences → Alert preferences**.
2. Enable **Receive CloudWatch billing alerts**.
3. Save the preference.
4. Note the time privately.

The existing account billing alarm has no data because `EstimatedCharges` is not currently
publishing. AWS may take time to publish the first metric after this setting is enabled.

## Step 4: Perform the Wrong-Region Exercise

This is intentional. It exists to rebuild the memory that AWS billing metrics are available through
CloudWatch only in `us-east-1`.

1. Switch the console to any region other than `us-east-1`.
2. Open **CloudWatch → Alarms → Create alarm → Select metric**.
3. Look for **Billing → Total Estimated Charge**.
4. Observe that `EstimatedCharges` is unavailable or empty.
5. Return the console to `us-east-1`.
6. Repeat the metric search after billing alerts have begun publishing.
7. Observe that the billing metric is available in `us-east-1`.

If the metric is still absent in `us-east-1`, stop here and allow more time. Do not create another
permanently empty alarm.

## Step 5: Create the Warning Budget

Path:

**Billing and Cost Management → Budgets → Create budget → Customize (advanced) → Cost budget**

Use these values:

| Field | Value |
|---|---|
| Name | `jprs-monthly-warning` |
| Period | Monthly |
| Budget type | Fixed |
| Amount | `$5.00` |
| Actual threshold 1 | 50% (`$2.50`) |
| Actual threshold 2 | 80% (`$4.00`) |
| Actual threshold 3 | 100% (`$5.00`) |
| Forecast threshold | 80% (`$4.00`) |

Use your preferred notification destination and confirm any required subscription message. Do not
record that address in the repository.

## Step 6: Create the Emergency Budget

Create a second fixed monthly cost budget:

| Field | Value |
|---|---|
| Name | `jprs-hard-stop` |
| Amount | `$10.00` |
| Actual notification | 100% |

Do not configure an automatic action yet. The target scheduler role does not exist until P4. At P4,
the Budget Action will attach `jprs-budget-lockdown-deny` to that role. AWS Budgets cannot directly
disable an EventBridge Scheduler schedule, and cost data is not instantaneous.

## Step 7: Create the CloudWatch Billing Alarm

Do this in `us-east-1`.

Path:

**CloudWatch → Alarms → Create alarm → Select metric → Billing → Total Estimated Charge → USD**

| Field | Value |
|---|---|
| Alarm name | `jprs-billing-5-usd` |
| Statistic | Maximum |
| Period | 6 hours |
| Condition | Greater than `$5.00` |
| Missing data | Treat as missing |

Connect the verified notification destination. The initial alarm state may be
`INSUFFICIENT_DATA`, but the underlying `EstimatedCharges` metric must exist.

## Step 8: Enable IAM Access Analyzer

Path:

**IAM → Access Analyzer → Create analyzer**

| Field | Value |
|---|---|
| Name | `jprs-account-analyzer` |
| Analysis type | External access |
| Zone of trust | Current AWS account |
| Region | `us-east-1` |

Review the findings. Record only the count and whether each finding is expected; do not put private
resource identifiers in the repository or chat.

## Step 9: Create the IAM Policies

These local files have already passed AWS Access Analyzer policy validation with zero findings:

- `policies/jprs-execution-boundary.json`
- `policies/jprs-budget-lockdown-deny.json`

For each policy:

1. Open the local file and read every statement.
2. Go to **IAM → Policies → Create policy → JSON**.
3. Paste the JSON and inspect the generated permissions summary.
4. Create it using the filename without `.json` as the policy name.

Rules:

- Do not attach either policy to the human administrator.
- `jprs-execution-boundary` becomes the permissions boundary for future JPRS execution roles.
- Leave `jprs-budget-lockdown-deny` unattached until P4.

## Step 10: Report Progress

Send this status to the AI without private identifiers:

```text
JPRS P0 progress

Root MFA: enabled / not enabled
Root access key: never used / recently used / unclear
Normal-user MFA: enabled / not enabled
Billing alerts: enabled / not enabled
Wrong-region exercise: observed / not yet
$5 warning budget: created / not yet
$10 emergency budget: created / not yet
$5 billing alarm: created / waiting for metric / not yet
Access Analyzer: active / not yet
Execution-boundary policy: created / not yet
Budget-lockdown policy: created / not yet
```

The AI should then perform read-only verification and update the repository's status files. It must
not infer completion from this message alone.

## P0 Done Gate

P0 is complete only when all of these are true:

- Root MFA remains enabled.
- The root access key is removed or has a documented dependency and removal plan.
- The normal human user has MFA.
- `EstimatedCharges` exists in CloudWatch in `us-east-1`.
- `jprs-monthly-warning` exists with the exact `$5` thresholds.
- `jprs-hard-stop` exists at `$10`.
- `jprs-billing-5-usd` watches the USD billing metric at `$5`.
- `jprs-account-analyzer` is active and findings were reviewed.
- Both IAM policies exist and match the local JSON.
- The wrong-region failure was observed.
- Read-only shared verification passes.
- Brett can answer this without notes:

> Why must the billing alarm live in us-east-1, and what is the difference between an AWS Budget and
> a CloudWatch billing alarm?

Do not start P1 until this gate passes.

# What Comes After P0

Only one phase is active at a time. At the start of each phase, the AI prepares its code, policy,
tests, exact console sequence, intentional failure, and completion checklist in this repository.
Brett then performs the AWS steps manually.

| Phase | What you will build and relearn |
|---|---|
| P1 | Private S3 substrate, Block Public Access, lifecycle, write-once keys, versioning off |
| P2 | First public ATS connector and collector Lambda, execution roles, logs, failure permissions |
| P3 | SQS, DLQ, retries, redrive, poison-message behavior |
| P4 | EventBridge Scheduler, scheduler execution role, explicit enumerate step, cost lockdown action |
| P5 | Multi-source fan-out, complete-run manifests, partial-run safety |
| P6 | Evidence-backed differ, repost/change history, cumulative and per-segment mass-drop guards |
| P7 | Daily report, SES delivery, CloudWatch alarms/dashboard, incident runbook |
| P8 | Optional evidence-constrained Bedrock narration; deterministic system remains authoritative |
| P9 | Rebuild the working manual stack as infrastructure as code |
| P10 | Parquet and Athena historical analysis after enough data accumulates |

V1 is P0-P7. P8 is optional. P9 proves that the manually understood stack can be expressed as code.
P10 becomes valuable only after the project has history to query.

# How To Resume Later

1. Open this file.
2. Find the first incomplete step in the active phase.
3. Tell the AI:

```text
Resume Job Posting Reality Score from START_HERE.md. Read the current repo state first. I am at:
[briefly state the last completed step]
```

4. The AI reads `project-factory/ORCHESTRATOR_BOOTSTRAP.md`,
   `project-factory/meta/SESSION_STATUS.md`, and the active plan before acting.
5. If the chat and repository disagree, verified AWS state and the repository status files win.

# Supporting References

You should not need these for ordinary continuation, but they preserve the detailed reasoning:

- `docs/operator/phase-0/P0_CONSOLE_WORKSHEET.md` — printable/checkable P0 worksheet
- `docs/operator/phase-0/P0_ACCOUNT_PREFLIGHT.md` — read-only account findings from 2026-07-28
- `docs/operator/phase-0/P0_GUARDRAIL_EXPLAINER.md` — what each safety control catches
- `docs/plans/2026-07-28-p0-account-guardrails.md` — active implementation record
- `docs/PLAN.md` — full phase status
- `docs/roadmap/committee-v1/JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md` — committee roadmap
- `docs/ADR/0001-supported-budget-enforcement.md` — corrected Budget Action design
