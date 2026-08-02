# Start Here: Job Posting Reality Score

This is the operator entrypoint. Read it before changing AWS or resuming the project in a new task.

## Current Position

- **Live system:** `jprs-v1` is deployed and running in `us-east-1`.
- **Live registry:** 15 validated Greenhouse boards selected for Brett's strongest job lanes.
- **Deployed usefulness pass:** Brett-specific fit ranking, linked daily results, SES digest delivery,
  authoritative observation dates, and expanded tests.
- **Active branch:** `codex/real-job-radar`.
- **Verified production run:** 15/15 current targets collected; 519 postings scored; 41 useful
  matches surfaced; queues and DLQ empty.
- **Current checkpoint:** daily radar active. SES identity, first delivery, and duplicate-suppression
  marker are verified.
- **Active plan:** `docs/plans/2026-08-02-real-job-radar.md`.

As of August 2, all 15 selected public boards returned successfully. Their 519 current postings
produced 41 roles above the useful-fit threshold. The highest results included agentic-system roles
at Machinify, Legion Intelligence, ICON, Grafana Labs, Future, and Cargomatic.

## What The Live Pass Does

1. Replaces Stripe, Figma, and GitLab with 15 companies selected for agentic/applied AI,
   backend/platform, automation, and developer-tooling work.
2. Scores the authoritative `current_jobs.json` records instead of leaving scorecards empty.
3. Shows company, title, location, fit evidence, and a direct posting link.
4. Caps the human digest while retaining every event and scorecard in JSON.
5. Sends the deterministic Markdown digest through SES and records a delivery marker to prevent
   ordinary retries from sending it twice.
6. Preserves the first date JPRS observed a posting across future collections.

## Email Delivery

The configured SES identity was verified on August 2. The controlled report returned
`digest_delivery=sent`, wrote `digest_delivery.json`, and an immediate second invocation returned
`already-sent`. No manual email activation remains.

## Future Target Changes

Do not update `/jprs/companies` while collection or assembly is running. Change
`config/companies.yaml`, run the checks, deploy code first when needed, then change the registry and
run both legs against the same target set.

### 1. Confirm Local State

From the repository root:

```bash
git status
.venv/bin/pytest -q -p no:cacheprovider
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml
```

The working branch should be committed and pushed. Deployment and merge to `main` each require
Brett's explicit approval.

### 2. Deploy The Code And Permission Update

After approval for a future code change:

```bash
sam deploy --config-file infra/samconfig.toml
```

Review the change set before confirming it. The report role gains read access to `current/*`, and the
updated Lambda package connects scoring and SES delivery. Do not accept unrelated infrastructure
changes.

### 3. Update The Production Registry

Generate the payload:

```bash
.venv/bin/python -m src.cli registry --compact
```

In the AWS console:

1. Open **Systems Manager -> Parameter Store** in `us-east-1`.
2. Open `/jprs/companies` and choose **Edit**.
3. Replace its value with the generated JSON exactly as printed.
4. Save it as a standard String parameter.
5. Reopen the parameter and confirm it contains 15 enabled entries.

Do not hand-edit board tokens in the console. Change `config/companies.yaml`, test it, and regenerate
the payload instead.

### 4. Run One Controlled Collection

1. Open **Lambda -> jprs-enumerate -> Test**.
2. Use `{}` as the test event.
3. Confirm the response reports 15 expected and enqueued tasks.
4. Open **SQS -> jprs-collect-queue -> Monitoring** and wait for visible/in-flight messages to reach
   zero.
5. Confirm `jprs-collect-dlq` remains empty.
6. In S3, confirm fresh status sentinels exist for the run date.

### 5. Run One Controlled Assembly

1. Open **Step Functions -> jprs-daily-assemble**.
2. Start an execution with `{}` as input.
3. Confirm every Map item completes and the report Lambda succeeds.
4. Open `reports/dt=YYYY-MM-DD/daily_report.md` in the project bucket.
5. Confirm the report names 15 expected sources and includes readable linked matches.
6. Confirm `daily_report.json` includes nonempty `scorecards` and `top_matches`.
7. Confirm the digest email arrives and `digest_delivery.json` exists beside the report.

If the same date is assembled again, the report updates but the delivery marker prevents an ordinary
duplicate email.

## Normal Daily Use

After deployment, the normal system requires no daily AWS work:

1. Collection starts at 07:00 America/New_York.
2. Assembly starts at 09:00 America/New_York.
3. Read the digest and choose the strongest one to three roles.
4. Open the direct links, verify each role is still open, tailor the resume/message, and apply
   manually.
5. Use the JSON report when you want the complete score decomposition or suppressed events.

The ranking is a triage aid, not a substitute for reading the posting. A high fit score means the
stored text aligns with Brett's demonstrated lane; it does not guarantee interest from the company.

## Troubleshooting

**Report says INCOMPLETE**

Read the named sources, inspect the collector logs and DLQ, and rerun only after the source succeeds.
The differ freezes missing source state; do not manufacture success sentinels.

**No matches appear**

Check `current_job_count` and `scorecards` in `daily_report.json`. An `AccessDenied` must fail the
report rather than silently becoming an empty result. If the current count is zero, verify the SSM
registry, current S3 keys, and report-role access to `current/*`.

**No email arrives**

Check the report Lambda result, SES identity status, CloudWatch logs, and `digest_delivery.json`. If a
marker exists, that date has already been delivered. Do not delete it merely to test retries.

**A board returns 404 or changes format**

Disable that entry in `config/companies.yaml`, regenerate SSM JSON, and update the parameter between
runs. Preserve the failure evidence; do not let it create disappearance events.

## Working Agreement

Brett approves and performs consequential AWS changes or explicitly delegates a deployment. The AI
may inspect state read-only, implement locally, write tests, prepare exact instructions, and diagnose
actual failures. It must not silently deploy, update SSM, merge to `main`, delete data, or expose
private account details.

## Resume In A New Task

Use:

```text
Resume Job Posting Reality Score from START_HERE.md. Read the current branch, active plan, and live
AWS state before acting. Tell me the exact current checkpoint.
```

When documents disagree, use this order: current operator instruction, `AGENTS.md`/`CLAUDE.md`,
verified AWS state, active plan, then historical roadmap material.
