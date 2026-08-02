# JPRS Deployment Guide

This guide covers the deployed `jprs-v1` SAM stack and the manual registry stored in SSM. AWS changes
require an explicit operator checkpoint. Never deploy while a collect or assemble run is in flight.

## Stack Contents

- One private, prefix-partitioned S3 bucket with versioning off.
- SQS collection queue and DLQ.
- Enumerate, collector, differ, and report Lambdas.
- Two EventBridge Scheduler schedules.
- One Standard Step Functions assembly workflow.
- CloudWatch log groups, metrics, alarms, and SNS notifications.
- SES digest delivery.
- Optional Bedrock narrator behind `EnableNarrator=false`.

The production company registry is intentionally outside CloudFormation at `/jprs/companies`, so a
stack deployment cannot silently replace operator-selected targets.

## Prerequisites

- AWS SAM CLI with Python 3.13 support.
- Authenticated AWS credentials for `us-east-1`.
- Sender, digest recipient, and alert notification addresses chosen privately.
- SES sender and recipient identities verified when the account is in the SES sandbox.
- No collection or assembly currently running.

Confirm identity without copying private output into Git or chat:

```bash
aws sts get-caller-identity
sam --version
```

## Validate And Build

From the repository root:

```bash
.venv/bin/pytest -q -p no:cacheprovider
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml
```

`AlertEmail`, `DigestRecipient`, and `SesSender` intentionally have no values committed to the
template. Existing stack updates retain their current parameter values. A first deployment must
supply them through `sam deploy --guided` or private command-line parameters.

## Deploy An Existing Stack Update

```bash
sam deploy --config-file infra/samconfig.toml
```

Review the generated change set before confirming it. For the August 2 radar pass, expected changes
are Lambda package updates and report-role read access to `current/*`. Stop if unrelated services or
destructive S3 changes appear.

For a first deployment:

```bash
sam deploy --guided --template-file .aws-sam/build/template.yaml
```

Use stack name `jprs-v1`, region `us-east-1`, `CAPABILITY_NAMED_IAM`, and keep
`EnableNarrator=false`.

## Production Registry

`config/companies.yaml` is the reviewed local registry. Render its exact production JSON with:

```bash
.venv/bin/python -m src.cli registry --compact
```

The output shape is:

```json
{"companies":[{"provider":"greenhouse","board_token":"...","company_slug":"...","enabled":true}]}
```

Update it in **Systems Manager -> Parameter Store -> `/jprs/companies` -> Edit**. Store it as a
standard String. Do not use the obsolete `company_id` field, and do not paste the YAML itself.

Sequence matters:

1. Deploy code and IAM changes.
2. Wait until no collect or assemble execution is active.
3. Update `/jprs/companies` from the generated JSON.
4. Force one enumerate collection.
5. Wait for the collection queue to drain and confirm the DLQ is empty.
6. Force one Step Functions assembly.

If collection and assembly read different registries, the manifest and Map inputs can disagree.

## Controlled Verification

### Collect

In the console, invoke `jprs-enumerate` with `{}`. Confirm the response count matches the enabled
registry and wait for `jprs-collect-queue` visible/in-flight messages to reach zero.

Verify the run produced:

- `runs/run=YYYY-MM-DD/RUN_OPEN.json`
- one `status/run=YYYY-MM-DD/.../SUCCESS.json` per successful source
- fresh immutable `raw/` snapshots
- fresh `normalized/` records

### Assemble

Start `jprs-daily-assemble` with `{}`. Confirm all Map items and the report task complete.

Verify:

- `current/provider=.../board=.../current_jobs.json`
- `events/schema_v=1/.../dt=YYYY-MM-DD/events.json`
- `reports/dt=YYYY-MM-DD/daily_report.md`
- `reports/dt=YYYY-MM-DD/daily_report.json`
- `reports/dt=YYYY-MM-DD/digest_delivery.json`
- a digest email containing readable titles, locations, companies, and direct links

`daily_report.json` must contain nonempty `scorecards` and `top_matches` when relevant roles exist.
The report Lambda returns `digest_delivery=sent` on first delivery and `already-sent` on an ordinary
same-date retry.

## IAM Ownership

- Collector writes `raw/*`, `normalized/*`, and `status/*` only.
- Differ reads collection inputs and owns `current/*` plus `events/*`.
- Report reads `runs/*`, `status/*`, `events/*`, and `current/*`; it writes `reports/*` only.
- No execution role has `s3:DeleteObject` on raw evidence.
- The shared boundary denies IAM mutation, out-of-scope infrastructure, and public S3 changes.

The report's `current/*` read permission is required for ranking. AccessDenied is deliberately not
treated as a missing object; the run must fail loudly instead of emailing an empty shortlist.

## SES

SES sandbox mode is sufficient for a self-recipient digest, but both sender and recipient must be
verified. The report is sent as deterministic plain text. A successful delivery writes a per-date
marker after SES returns a message ID.

If email is missing, check in this order:

1. Report Lambda result and CloudWatch logs.
2. SES identity status and sandbox recipient verification.
3. `digest_delivery.json` for that date.
4. SES sending metrics.

## Rollback

Do not delete evidence or reset the stack as a first response.

1. Disable both schedules if continuing runs could make the incident worse.
2. Restore the prior `/jprs/companies` value between runs.
3. Redeploy the prior known-good application commit.
4. Re-enable schedules only after one controlled collect and assemble passes.

Stack deletion and bucket emptying are destructive and require a separate explicit approval. The S3
bucket is retained by CloudFormation, and `/jprs/companies` is not stack-managed.
