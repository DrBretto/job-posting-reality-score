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

# A fresh build directory per attempt, so no stale build can be selected (see the warning below).
export BUILD="$(mktemp -d /tmp/jprs-build-XXXXXX)"

sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml --build-dir "$BUILD"
```

`AlertEmail`, `DigestRecipient`, and `SesSender` intentionally have no values committed to the
template. Existing stack updates retain their current parameter values. A first deployment must
supply them through `sam deploy --guided` or private command-line parameters.

## Name The Template And The Config — Never Let SAM Guess

**Every deploy command below passes `--template-file` and an ABSOLUTE `--config-file`.** This is not
style. SAM 1.137.1 resolves an omitted deploy template by searching, relative to the current
directory, `.aws-sam/build/template.yaml`, then `template.yaml`, `template.yml`, `template.json`. A
`--build-dir` is never consulted. Measured in this repository:

- from the repository root, an omitted `--template-file` resolves to `<repo>/template.yml`, which does
  not exist;
- from `infra/`, it resolves to `infra/.aws-sam/build/template.yaml` — a stale build that contains no
  `DiscoveryFunction`, so it would silently deploy the pre-discovery stack;
- in any checkout carrying a default `.aws-sam/build/`, it selects that build rather than the new one.

And SAM sets its samconfig search directory to the directory of the template you give it, so once the
template lives in a build directory, a relative `--config-file infra/samconfig.toml` resolves to
`<build-dir>/infra/samconfig.toml` and this repository's config is silently missed.

Evidence and the local selection check, no AWS call:
`project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/evidence/p05_deploy_selection_probe.py`

## Deploy An Existing Stack Update

```bash
# Confirm the artifact is the one you are about to ship, before shipping it.
test -f "$BUILD/template.yaml" && grep -q DiscoveryFunction "$BUILD/template.yaml" \
  && echo "OK: built template contains DiscoveryFunction"

sam deploy \
  --template-file "$BUILD/template.yaml" \
  --config-file "$PWD/infra/samconfig.toml" \
  --config-env default
```

Review the generated change set before confirming it. For the August 2 radar pass, expected changes
are Lambda package updates and report-role read access to `current/*`. Stop if unrelated services or
destructive S3 changes appear.

For a first deployment:

```bash
sam deploy --guided \
  --template-file "$BUILD/template.yaml" \
  --config-file "$PWD/infra/samconfig.toml"
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
- Report reads `runs/*`, `status/*`, `events/*`, `current/*` and `discovery/*`; it writes `reports/*`
  only, and may list `status/`, `reports/` and `discovery/`.
- Discovery writes `discovery/*` and the `raw/`, `normalized/`, `status/` forward tiers, reads
  `discovery/*`, `runs/*`, `status/*`, and may list `discovery/` only (`DiscoveryListOwnPrefix`,
  added 2026-09-26). Every optional discovery read lists its exact key first: without that grant a
  never-written key answers 403, not 404, and the first round deadlocked on its own state.
- No execution role has `s3:DeleteObject` on raw evidence.
- The shared boundary denies IAM mutation, out-of-scope infrastructure, and public S3 changes.

The report's `current/*` read permission is required for ranking. AccessDenied is deliberately not
treated as a missing object; the run must fail loudly instead of emailing an empty shortlist.

## Runtime settings that are load-bearing

| function | Timeout | MemorySize | why it is that number |
|---|---|---|---|
| `jprs-report` | **300** (was 90 until 2026-09-30) | **1769** (was 512 until the 2026-11-11 release) — see the template comment: one full vCPU for single-threaded work, measured on the real 4,671-posting corpus | The assembly is CPU-bound and **quadratic in corpus size**. Measured in production on 2026-09-30: 188.52s over 1,344 postings, 36.9% headroom, peak 209 MB of 512. |
| `jprs-discovery` | 120 | 512 | network-bound; 18s typical |
| `jprs-differ`, `jprs-enumerate` | 30 | 256 | per-board work, unchanged |

**Before raising `jprs-report`'s timeout again, read this first.** Raising it is the wrong repair
the second time, and as of 2026-09-30 the right one is prepared: the `deduplicate` cleanup pass no
longer scans every ordered pair of survivors. Locally it goes 7.342s → 0.023s on a 1,526-posting
corpus and its growth per doubling drops from ~4.1x to ~2.0x.

*History, kept because the numbers were quoted and were wrong.* The stage used to call
`normalize_employer` on both operands of a nested loop over the kept set — 3.6M calls at 1,344 jobs,
measured constant at 3.1e-6 × n² seconds. Capacity ceilings of ~2,400 and then ~1,990 postings were
both published; the two real production points (1,344 at 188.52s, 1,526 at 226.74s) give ~1,835 by
an exact two-point fit, which is not independent evidence either. **Treat all three as
extrapolations, not limits.**

**A cache is not the fix.** Memoizing `normalize_employer` makes each of the ~2.3M comparisons
cheaper and leaves every one of them in place; measured, a cache-only variant reads exactly as many
employer names as the naive scan (459,840 at n=480, versus 960 for the repaired pass).

**Memory is not the lever it looks like.** Peak use is ~209 MB of 512. More memory buys
proportional vCPU and would genuinely reduce wall time, but it changes the cost shape and has never
been the constraint; do not raise it as a reflex when the timeout is tight.

**How to know the margin before it is gone.** Every report and digest ends with its own runtime
line — `Runtime: ran in 188.52s, of a 298.97s budget (110.45s / 36.9% left), over 1344 postings.` —
and `daily_report.json` carries the same figures plus `per_1k_population_seconds`, which is the one
that rises as the corpus grows. **Watch that rate, not the elapsed seconds.** This exists because an
80.08s run against a 90s budget was recorded as an unqualified success on 2026-09-26 and nothing
read the margin; the next three scheduled rounds produced no report at all.

**Since the 2026-11-11 release the report cannot simply time out.** It evaluates newest-first and
stops before the reserve it needs to publish; a short round publishes a `partial` report naming every
posting it did not evaluate, and a crashed round publishes a `degraded` fresh-cohort report via
`ReportIncomplete`. The digest subject says `[partial]` / `[degraded]`. Watch `delivery_mode` and
`evaluation` in `daily_report.json`.

**`jprs-ops-alerts` had NO subscription on 2026-11-11**, so A7 (which did fire every failed day) reached
nobody. Re-subscribing sends a confirmation email that must be clicked.

**Do not rely on `jprs-A3-report-not-assembled` to tell you the report failed.** It watches custom
metric `JPRS/ReportComplete`, which has never been published — zero datapoints since the alarm was
created. It latched into ALARM on 2026-07-31 because missing data is treated as breaching, and
CloudWatch notifies only on state transitions, so it has never sent anything and did not fire
through four consecutive failed days. `jprs-A2-missed-run` / `CollectRunSuccess` is in the same
state. `ReportFunction` already holds `cloudwatch:PutMetricData` scoped to namespace `JPRS`, so a
publisher needs no IAM change — note that a custom metric costs about $0.30/month, and that the
`TreatMissingData: breaching` + `EvaluationPeriods: 1` configuration is what latched it.

## Release gate — compare against what is live, declare any infrastructure change

`scripts/release_preflight.sh <build> <baseline-build> [<recorded-identity> <declared-delta.json>]`
fails closed. The baseline build must be the version LIVE NOW, rebuilt from a verified archive:

```bash
scripts/reconstruct_p06_baseline_build.sh "$BASELINE" <archive.tar.gz> <manifest.json>
```

(With no archive named it rebuilds P06, which has not been live since 2026-09-25.) A release that
changes infrastructure passes only with a declaration that names every template difference exactly;
the verdict is then `CHANGE_SET_IS_CODE_PLUS_DECLARED_INFRASTRUCTURE`, never "code-only". The
recorded identity must cover the state-machine definition file, which no function package carries.
After `sam deploy --no-execute-changeset`, diff the live and change-set PROCESSED templates property
by property before executing; CloudFormation lists every resource that references a function ARN as
"Modify" even when nothing about it changes. The 2026-09-26 recovery run's
`RELEASE_PROPOSAL.md` holds the worked commands, the live P10 archive and the rollback template.

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
