> **SUPERSEDED — do not follow this document.** A second orchestrator review found three remaining
> blockers in the P02 return (`ORCHESTRATOR_REVIEW.md` in this directory), and
> `JPRS-L2-P03-runtime-boundary-and-fresh-first-v01` repaired them. The handoff of record is
> `../20260924_runtime_boundary_and_fresh_first_v1/DEPLOYMENT_HANDOFF.md`.
>
> Known wrong below: §3.2 implies the Adzuna credential would work (the live fetcher still discarded
> the authenticated URL); §6 omits the state downgrade, so following it would leave the reverted
> release unable to read its own data; §7's GB-second arithmetic is wrong by ~20x.
>
> Left unedited apart from this banner — it is the historical executor record, not a current result.

# DEPLOYMENT_HANDOFF — open-market discovery, after the P02 release repair

> NOT RELEASE-CLEARED: independent return review reproduced remaining Adzuna HTTP credential,
> screening and rollback data-compatibility defects. Read `ORCHESTRATOR_REVIEW.md` in this directory.
> Historical instructions below are preserved, not approved. Continue through P03 before deployment.

Packet: `JPRS-L2-P02-discovery-release-repair-v01` · Run: `20260924_open_market_release_repair_v1`

This supersedes the P01 handoff, which the orchestrator review correctly marked not cleared for use.
Every command below was validated locally, with no AWS operation performed.

**Nothing in this run touched AWS.** No deploy, no SSM write, no IAM change, no spend, no email, no
commit, no branch, no push.

---

## 1. Approval boundary

| Action | Authorized by this packet? |
|---|---|
| Local code, tests, docs, config | yes — done |
| Public read-only source verification | yes — done |
| Local CLI syntax validation (`--generate-cli-skeleton`) | yes — done, no AWS call |
| `sam deploy` | **no — needs your explicit approval** |
| SSM parameter creation or edit | **no — needs your explicit approval** |
| Creating an Adzuna account | **no — needs you** |
| Enabling careers-URL resolution | **no — needs your explicit approval** |
| git commit / branch / push | **no — needs your explicit approval** |

Branch `codex/real-job-radar` carries an **uncommitted working tree** holding both the P01
implementation and this repair. Nothing was staged. §6 is written so that no rollback step destroys
it.

---

## 2. What changes in AWS

Unchanged from the P01 proposal in shape; listed again because this is the handoff of record.

### New

| Resource | Purpose |
|---|---|
| `jprs-discovery` Lambda | the discovery pass; 120s timeout, 512MB |
| `/aws/lambda/jprs-discovery` log group | 30-day retention |
| `jprs-discovery-daily` EventBridge schedule | `cron(5 7 * * ? *)` America/New_York |
| `jprs-scheduler-discovery-role` | invoke-only role for that schedule |
| `jprs-A8-discovery-errors` alarm | a silent discovery failure would reduce the system to a fixed watchlist while every other signal still looked healthy |

### Changed

| Resource | Change |
|---|---|
| `jprs-report` | code update; IAM gains `s3:GetObject` on `discovery/*` and `s3:ListBucket` on that prefix |
| `jprs-collector`, `jprs-differ`, `jprs-enumerate` | code update only; no IAM change |

### Preserved — reject the change set if any of these move

- `jprs-collect-daily` stays `cron(0 7 * * ? *)`.
- `jprs-assemble-daily` stays `cron(0 9 * * ? *)`.
- Bucket (versioning off), SQS queues, DLQ, alarms A1–A7, permissions boundary: untouched.

Discovery gets no `current/*` or `events/*` grant. Those stay differ-owned.

---

## 3. Prerequisites

### 3.1 Required before deploy — none

The four keyless sources need no credentials.

### 3.2 The Adzuna credential — and what it does and does not close

`/jprs/secrets/ADZUNA_APP_ID` and `/jprs/secrets/ADZUNA_APP_KEY`, both SSM **SecureString**. Not
CloudFormation parameters: a secret passed through CloudFormation persists in change sets and console
history. The Lambda reads the path with decryption at invoke time, so **no redeploy is needed**.

What P02 fixed so that the credential can actually work:

- the default provider list now includes Adzuna, so the gate is reached and reported;
- the connector reads the **injected** credential mapping instead of `os.environ`, so an SSM value
  reaches the outbound request;
- requests now carry `where`, covering nationwide/remote **plus** New Hampshire and Boston;
- receipts and every stored artifact redact credential parameters.

**The credential alone does not close the general-industry coverage gate.** Providing it enables the
first *attempt*. The gate closes only when a real authenticated search returns results in production
and the coverage receipt shows Adzuna under `discovery_succeeded`. Until then, coverage remains four
remote-job boards plus whatever Adzuna returns, and the report says so.

### 3.3 Careers-URL resolution — proposes rows, does not monitor

`ResolveCareersUrls=true` at deploy time lets discovery follow an aggregator apply link to find the
employer's own board. Every redirect hop is re-validated against the SSRF address rules.

Three distinct things, deliberately not conflated:

1. **resolver success** — a careers URL was resolved to a supported board;
2. **a proposed registry entry** — written to `discovery/run=<date>/proposed_registry.json`;
3. **actual monitoring** — only after *you* apply that row to `config/companies.yaml` and the SSM
   registry.

Enabling the resolver achieves (1) and (2). It never achieves (3). No registry mutation happens in
this packet or in any scheduled run.

Its live path remains **unverified**: this machine's egress proxy blocks the DNS resolution the guard
performs, so the first production run is the verification.

---

## 4. Deploy

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

git status                                        # expect an uncommitted tree; do not reset it
.venv/bin/pytest -q -p no:cacheprovider           # expect 204 passed, 5 skipped
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml     # see the note below

sam deploy --config-file infra/samconfig.toml     # review the change set before confirming
```

`sam build` note: if it fails with `Operation not permitted: .aws-sam/build/*/.claude/commands`,
that is a stale build directory, not a template problem. Use `--build-dir <clean dir>`.

---

## 5. Post-deploy acceptance checks

1. **Discovery runs, and the transport gate closes.** Lambda → `jprs-discovery` → Test `{}`.
   Expect `discovery_succeeded` listing the four keyless providers. *This is the check that closes
   the production-transport gap*: locally only Remotive was exercised through `fetch_raw`, because
   this machine's proxy truncated the others.
2. **Pagination actually paginates.** In `discovery/run=<date>/coverage.json`, confirm Himalayas
   contributed more than 20 postings across pages, and that `backlog_items` plus
   `query_families_saturated` reflect whatever remains. A live `nextCursor` with an empty backlog
   would mean the R2 repair regressed.
3. **Cursor resumption.** After a second run, confirm `discovery/_discovery_state.json`
   `source_cursors.himalayas` advanced rather than resetting to page one.
4. **Adzuna, if the credential exists.** Confirm Adzuna under `discovery_succeeded`, that requests
   include both unscoped and `where`-scoped searches, and that **no** stored object contains the
   credential value. If the credential is absent, confirm Adzuna appears under `credential_gated`.
5. **Report surfaces.** `reports/dt=<date>/daily_report.md`: four health axes, "Coverage and
   backlog", a "Complete candidate list" whose count matches `matching_job_count`, and the
   attribution block required by Remotive / Remote OK / Jobicy terms.
6. **The existing path is unharmed.** 15/15 boards collected, digest delivered,
   `digest_delivery.json` present.
7. **Nothing auto-admitted.** `discovery/run=<date>/proposed_registry.json` is `[]` unless
   resolution is enabled — and even then it is a proposal, never a monitored source.

---

## 6. Rollback — validated locally, and non-destructive

Full transcript: `evidence/rollback_validation.txt`.

### 6.1 Partial disable — stops discovery only

**`UpdateSchedule` is a full replace, not a patch.** The P01 handoff's
`aws scheduler update-schedule --name jprs-discovery-daily --state DISABLED` is **rejected**:

```
aws: error: the following arguments are required: --flexible-time-window, --schedule-expression, --target
```

Use the round-trip, which preserves every field by construction (validated with
`--generate-cli-skeleton output`, exit 0, no AWS call):

```bash
aws scheduler get-schedule --name jprs-discovery-daily > /tmp/sched.json
# edit: set .State to "DISABLED"; remove read-only Arn, CreationDate, LastModificationDate
aws scheduler update-schedule --cli-input-json file:///tmp/sched.json
```

Or disable via CloudFormation instead, which avoids drift entirely:

```bash
sam deploy --config-file infra/samconfig.toml \
  --parameter-overrides DiscoveryCron='cron(5 7 * * ? *)' ResolveCareersUrls=false
# plus set DiscoverySchedule State to DISABLED in the template if a standing disable is wanted
```

**This is a PARTIAL disable.** It stops the discovery pass. It **does not revert** the modified
screening, scoring, dedup or report code, which the collector/differ/report Lambdas would still be
running. If the problem is a screening or report behavior, this is not the fix.

### 6.2 Full rollback — without destroying the working tree

**Do not run** `git checkout e549a73 -- src/ infra/ config/`. The P01 handoff proposed it; it would
overwrite the uncommitted P01 + P02 implementation with no copy anywhere.

Build the old revision in a separate worktree, leaving your tree untouched:

```bash
# exact revision currently deployed (the P01/P02 work is NOT in any commit)
git rev-parse e549a73        # -> e549a73... "fix: complete real job radar deployment"

git worktree add /tmp/jprs-rollback e549a73
cd /tmp/jprs-rollback
sam build --template-file infra/template.yaml --build-dir /tmp/jprs-rollback-build
sam deploy --config-file infra/samconfig.toml --template-file /tmp/jprs-rollback-build/template.yaml

# afterwards
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
git worktree remove /tmp/jprs-rollback
```

Your working tree is never checked out, reset, stashed or staged by any of this.

CloudFormation removes `jprs-discovery`, its schedule, role, log group and alarm A8, and reverts the
report role's `discovery/*` grants.

**Data left behind is inert.** The pre-change report never reads `discovery/`, and the additive
`CanonicalJob` / `DiffState` fields are ignored by the old code. Nothing needs deleting, and a
rollback cannot emit a removal event.

---

## 7. Cost — bounded, with sources and assumptions

Sourced from AWS's primary Price List API on 2026-09-24 for `us-east-1`
(`pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/us-east-1/index.json`)
and the public pricing pages.

**Assumptions, all stated:**

- one discovery invocation per day (~30/month), 512MB, 10–30s → ~0.25 GB-s/invocation, ~7.5 GB-s/mo
- ~19 new S3 PUTs per run → ~570 PUTs/month; stored objects well under 1 GB
- one new standard-resolution CloudWatch alarm (A8)
- 30 additional EventBridge Scheduler invocations per month
- `us-east-1`; **no free-tier credit assumed** (see below)

| New cost item | Unit price (source) | Monthly estimate |
|---|---|---|
| CloudWatch alarm A8 | **$0.10 / standard-resolution alarm-metric / month** — Price List API, `CW:AlarmMonitorUsage` | **$0.10** |
| Lambda compute | $0.0000166667 / GB-s — Lambda pricing page | ~$0.0001 |
| Lambda requests | $0.20 / 1M requests — Lambda pricing page | <$0.0001 |
| EventBridge Scheduler | $1.00 / million scheduled invocations — EventBridge pricing page | <$0.0001 |
| S3 PUT + storage | standard S3 request/storage rates (**not sourced from the primary API in this run**; S3's region index was too large to fetch here) | <$0.02, assumption |
| **Total new** | | **≈ $0.10–$0.15 / month, dominated by the alarm** |

**What this is not.** This is a *bounded estimate from unit prices and stated assumptions*, not an
account-verified bill and not a free-tier entitlement claim. The P01 handoff's "$0 additional in
practice" asserted free-tier eligibility that was never checked; that claim is withdrawn. If the
account is still inside the Lambda and Scheduler free tiers the compute lines round to zero, but the
$0.10 alarm is a real recurring charge regardless, and only the Billing console can confirm any of it.

The existing under-$5/month target is preserved with substantial headroom on these figures. Adzuna's
developer tier is free of charge; Brave was researched and declined because signup requires a payment
instrument.

---

## 8. Existing-data reconciliation

- `SCHEMA_VERSION` 1.0.0 → **1.1.0, additive only**. Same major, same `schema_v=1` prefix, **no
  replay required**. Older records load with new fields at defaults.
- `DiffState` gains `segment_absence_streak`, `suspect_streak`, `suspect_kind`, `suspect_since`,
  `suppressed_count_history` — all defaulted.
- `DiscoveryState` gains `source_cursors`, and backlog entries changed from positional tuples to
  `BacklogItem` records. **No `discovery/_discovery_state.json` exists in production yet**, so there
  is nothing to migrate; if one somehow exists, delete it and the next run rebuilds from page one.
- `scoring_profile_version` 1.1.0 → **1.2.0** and `SCREENING_RULESET_VERSION` 1.0.0 → **1.1.0**.
  Scores and screening verdicts are not comparable across those boundaries; both versions are stamped
  on every record so a later comparison can tell.
- First run after deploy: sources currently latched by the silent-subset guard restart their
  corroboration count and need two further healthy snapshots to release. Intended, not a stall.

---

## 9. Remaining gates — none of these is closed by one switch

| Gate | Status | What would close it |
|---|---|---|
| Adzuna general-industry coverage | **unpassed** | credential in SSM **and** a real authenticated search returning results in production (§3.2) |
| Production fetch transport for 3 of 4 feeds | **unpassed locally** | post-deploy check 1 |
| Careers-URL resolution live path | **unpassed** | enable it; first production run verifies |
| Discovery → monitoring loop | **not implemented, by design** | it proposes registry rows; you apply them (§3.3) |
| Independent review of screening | **not obtained** | a reviewer context that did not write the rules (see `VALIDATION.md`) |
| Lambda packaging ships the whole repo | **open, pre-existing** | a build-method change affecting all five functions; no security or runtime defect was demonstrated, so it is not a prerequisite |

---

## 10. What needs you

1. **Deploy or not.**
2. Optional, highest value: the free Adzuna developer credential in SSM (§3.2).
3. Optional: enable careers-URL resolution (§3.3), understanding it proposes rather than monitors.
