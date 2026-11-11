# DEPLOYMENT_HANDOFF — open-market discovery, after the P03 repair

> NOT RELEASE-CLEARED: independent return review reproduced remaining Adzuna HTTP credential,
> screening and rollback data-compatibility defects. Read `ORCHESTRATOR_REVIEW.md` in this directory.
> Historical instructions below are preserved, not approved. Continue through P03 before deployment.

Packet: `JPRS-L2-P03-runtime-boundary-and-fresh-first-v01` · Run: `20260924_runtime_boundary_and_fresh_first_v1`

This supersedes the P02 handoff, which a second orchestrator review found still carried three blockers. Every command below was validated locally with no AWS operation.

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

What is now in place so the credential can actually work:

- the default provider list includes Adzuna, so the gate is reached and reported (P02);
- the connector reads the **injected** credential mapping instead of `os.environ` (P02);
- **the live fetcher now sends the authenticated URL it was given** — P02 fixed the connector but
  `_live_fetcher` still discarded its URL and let the unbound connector rebuild it from an empty
  `os.environ`, so every request would have gone out unauthenticated (P03/R1);
- requests carry `where`, covering nationwide/remote **plus** New Hampshire and Boston;
- receipts and every stored artifact redact credential parameters, verified by scanning every object
  in a mock bucket for the fake credential.

This is verified at `urllib.request.urlopen` with the real fetcher and connector wiring intact. The
P02 test replaced the broken function with a stand-in and therefore could not see the defect.

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
.venv/bin/pytest -q -p no:cacheprovider           # expect 247 passed
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

### 6.2 Data compatibility — required, and previously missing

**Source rollback alone is not sufficient.** At `e549a73`, `CanonicalJob` and `DiffState` both use
`extra="forbid"`. Measured: the baseline rejects a current monitored-job record on **18** fields and a
current diff state on **5**, and two new event-type values fail its enum. The P02 claim that additive
fields "are ignored by the previous reader" was false. Reverting only the code leaves the previous
release unable to read the state the new code wrote.

Rehearsed end to end on mocked AWS (`evidence/rollback_data_rehearsal.txt`): forward run → baseline
read fails → backup + downgrade → baseline reads → baseline restarts with **DISAPPEARED=0**, including
a job absent on the following run, where the ordinary grace clock governs exactly as before.

```bash
# 1. DRY RUN first — writes nothing, prints what would change
.venv/bin/python -m src.cli downgrade-state --bucket <bucket> --dt <YYYY-MM-DD>

# 2. only after reviewing that output, and only with your approval
.venv/bin/python -m src.cli downgrade-state --bucket <bucket> --dt <YYYY-MM-DD> \
    --apply --i-have-a-backup-plan
```

It backs every object up under `rollback-backup/<timestamp>/` **before** rewriting, drops only keys
the baseline does not declare, and preserves **every job id and grace clock** — dropping a job would
make the old differ emit a disappearance for a posting that never closed. Two assertions inside the
tool enforce that.

Restore from the backup prefix to undo it. This is a deployment-time operator action; nothing runs it
automatically and this packet only rehearsed it.

### 6.3 Full source rollback — without destroying the working tree

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
report role's `discovery/*` grants. **Run §6.2 as well** — otherwise the reverted code cannot read the
state the new release wrote.

**Data left behind is inert.** The pre-change report never reads `discovery/`, and the additive
`CanonicalJob` / `DiffState` fields are ignored by the old code. Nothing needs deleting, and a
rollback cannot emit a removal event.

---

## 7. Cost — corrected arithmetic, sourced where possible

The P02 figures were wrong by roughly 20× and are withdrawn. 512 MB for 10–30 s is **5–15 GB-seconds**
per invocation, not 0.25.

**Assumptions, all stated:** one discovery invocation per day (~30/month) at 512 MB; runtime
**15–60 s**, recomputed for the actual work (up to 5 Himalayas pages, 3 bulk feeds, up to 20 Adzuna
queries ≈ 28 HTTP requests); ~30 new S3 PUTs per run; ~2 MB of raw payload per run; one new
standard-resolution CloudWatch alarm; `us-east-1`; **no free-tier credit assumed**.

| item | unit price (source) | monthly |
|---|---|---|
| CloudWatch alarm A8 | **$0.10 / standard-resolution alarm-metric / month** — AWS Price List API, `CW:AlarmMonitorUsage` | **$0.10** |
| Lambda compute | $0.0000166667 / GB-s — Lambda pricing page | 225–900 GB-s → **$0.004–0.015** |
| Lambda requests | $0.20 / 1M | <$0.0001 |
| EventBridge Scheduler | $1.00 / 1M | <$0.0001 |
| S3 PUTs (~900/mo) | standard rate, **not sourced from the primary API this run** | ~$0.005 |
| S3 storage (~60 MB/mo growth) | standard rate, same caveat | ~$0.001, grows |
| **total new** | | **≈ $0.11–0.13 / month, alarm-dominated** |

A *bounded estimate from unit prices and stated assumptions* — not an account-verified bill and not a
free-tier entitlement claim. The under-$5/month target keeps substantial headroom. Adzuna's developer
tier is free of charge; Brave was researched and declined because signup requires a payment
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
- `SCREENING_RULESET_VERSION` 1.1.0 → **1.2.0** (evidence aggregation). Screening verdicts are not
  comparable across that boundary; the version is stamped on every result.
- `DiscoveryState` gains `last_feed_phase`; `DiscoveryBacklog` entries are `BacklogItem` records.
  No `discovery/_discovery_state.json` exists in production yet, so there is nothing to migrate.
- **Rolling back requires §6.2 in addition to §6.3.** This is the item P02 got wrong.

---

## 9. Remaining gates — none closed by one switch

| Gate | Status | What would close it |
|---|---|---|
| Adzuna general-industry coverage | **unpassed** | the credential in SSM **and** an authenticated search returning results in production. The boundary is now proven to carry a credential; that is not the same as having run one. |
| Production fetch transport, 3 of 4 keyless feeds | **unpassed locally** | post-deploy check 1 |
| Rollback state downgrade against real state | **rehearsed only** | §6.2 dry run, then your approval |
| Sub-24-hour capture | **not achievable as configured** | discovery runs once daily at 07:05 and Remotive publishes on a documented 24 h delay, so a posting can be ~48 h old when first surfaced. A second afternoon discovery pass would narrow it; that is a schedule change and needs separate approval. **No schedule was changed.** |
| Careers-URL resolution live path | **unpassed** | enable it; first production run verifies |
| Discovery → monitoring | **not implemented, by design** | it proposes registry rows; you apply them |
| Independent review of this repair | **not obtained** | a reviewer context that did not write the code. Two consecutive reviews each found defects the implementing context missed, including in its own tests. |
| Lambda packaging ships the whole repo | **open, pre-existing** | a build-method change across all five functions; no security or runtime defect demonstrated |


---

## 10. What needs you

1. **Deploy, or send this for a third review first.** Given that two reviews each found defects I
   missed, the second option is the one I would pick.
2. Optional, highest value: the free Adzuna developer credential in SSM (§3.2).
3. Optional: enable careers-URL resolution (§3.3), understanding it proposes rather than monitors.
4. If discovery is deployed and later needs reverting, **both** §6.2 and §6.3 apply.
