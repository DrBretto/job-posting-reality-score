# DEPLOYMENT_HANDOFF — open-market discovery, after the P04 boundary repairs

Packet: `JPRS-L2-P04-location-and-freshness-boundaries-v01` · Run: `20260924_location_and_freshness_boundaries_v1`

This is the handoff of record. It supersedes the P03 handoff, which the independent P03 review found
carried three open blockers plus a self-contradiction about rollback data compatibility. The earlier
handoffs and their evidence are preserved unchanged in their own run directories; where this document
disagrees with one of them, **this one is correct and the disagreement is named explicitly below.**

**Nothing in this run touched AWS.** No deploy, no SSM write, no IAM change, no spend, no email, no
commit, no branch, no staging, no push, no reset.

---

## 1. Approval boundary

| Action | Authorized by this packet? |
|---|---|
| Local code, tests, docs, config | yes — done |
| Public read-only payload capture for the rehearsal | yes — done (7 GETs) |
| `sam validate` / `sam build` | yes — done, no AWS call |
| `sam deploy` | **no — needs your explicit approval** |
| SSM parameter creation or edit | **no — needs your explicit approval** |
| Creating an Adzuna account | **no — needs you** |
| Enabling careers-URL resolution | **no — needs your explicit approval** |
| git commit / branch / push | **no — needs your explicit approval** |

Branch `codex/real-job-radar` carries an **uncommitted working tree** holding the P01 implementation
and the P02, P03 and P04 repairs. Nothing is staged. §6 is written so that no rollback step destroys
it.

---

## 2. What changes in AWS

**No infrastructure change from the P03 proposal.** P04 is source-only: no new function, schedule,
role, parameter, alarm or IAM grant. `infra/template.yaml` is byte-identical to the version P03
validated, re-validated here.

For completeness, the stack additions still pending first deploy (introduced in P01):

- `DiscoveryFunction` (`jprs-discovery`) + `DiscoveryLogGroup`
- `DiscoverySchedule` — EventBridge Scheduler, `cron(5 7 * * ? *)` — and `DiscoverySchedulerRole`
- alarm `A8DiscoveryErrors`
- parameters `DiscoveryCron`, `DiscoveryProviders`, `SecretsSsmPrefix`, `ResolveCareersUrls`
- the report role gains read on `discovery/*`

---

## 3. Prerequisites

### 3.1 Required before deploy — none

The four keyless sources need no credentials.

### 3.2 The Adzuna credential

`/jprs/secrets/ADZUNA_APP_ID` and `/jprs/secrets/ADZUNA_APP_KEY`, both SSM **SecureString**. Not
CloudFormation parameters: a secret passed through CloudFormation persists in change sets and console
history. The Lambda reads the path with decryption at invoke time, so **no redeploy is needed** after
you set them.

The credential path is repaired and verified at `urllib.request.urlopen` with the real fetcher and
connector wiring left intact — P03/R1. P04 changed nothing in that path and its regression still
passes. **The credential alone does not close the general-industry coverage gate:** it enables the
first *attempt*. The gate closes when a real authenticated search returns results in production and
the coverage receipt lists Adzuna under `discovery_succeeded`.

### 3.3 Careers-URL resolution — proposes rows, does not monitor

Unchanged from P03. `ResolveCareersUrls=true` lets discovery follow an aggregator apply link to find
an employer's own board, re-validating every redirect hop against the SSRF address rules. It writes a
*proposed* registry row; it never monitors anything. Actual monitoring needs you to apply the row to
`config/companies.yaml` and the SSM registry. Its live path remains **unverified**.

### 3.4 Live transport is still unverified, and this run has a fresh reason to say so

While rehearsing, live `urlopen` against the public feeds returned **truncated bodies
non-deterministically** from this machine: 80,693 bytes via `curl` versus 18,586 / 5,996 / 0 bytes via
`urllib` on consecutive attempts to the same URL. The connector handles that correctly — it keeps the
partial body and the JSON parse lands the snapshot `PARTIAL`, which suppresses removals rather than
inventing a clean read — so the failure mode is safe and visible.

But it means **no local run has exercised the production transport end to end.** The rehearsal in this
run therefore replays *real captured payloads* through the real pipeline with the transport mocked.
Real data, mocked transport: that is not evidence the production transport works. The first scheduled
run in Lambda is that evidence. Watch `discovery_succeeded` and the `inaccessible` list on day one.

---

## 4. Deploy

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

git status                                        # expect an uncommitted tree; do NOT reset it
.venv/bin/python -m pytest -q -p no:cacheprovider # expect 296 passed
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml --build-dir /tmp/jprs-build
sam deploy --config-file infra/samconfig.toml     # review the change set before confirming
```

Two environment notes, neither a template problem:

- `sam build` can fail with `Operation not permitted: .aws-sam/build/*/.claude/commands` from a stale
  build directory. Use a clean `--build-dir`, as above.
- `sam validate` can fail with `PermissionError: /Users/drbretto/.aws-sam/metadata.json` when the
  sandbox denies that write. Run it with an isolated `HOME` and explicit AWS config paths:
  `HOME=/tmp/samhome AWS_CONFIG_FILE=~/.aws/config AWS_SHARED_CREDENTIALS_FILE=~/.aws/credentials sam validate --lint --template-file infra/template.yaml`

---

## 5. Post-deploy acceptance checks

1. **Discovery runs and the transport holds.** Lambda → `jprs-discovery` → Test `{}`. Expect a
   coverage receipt; check `discovery_succeeded` against `discovery_attempted`, and read
   `inaccessible` for truncated or `PARTIAL` downloads (see §3.4).
2. **The report carries real timing.** Open `reports/dt=<date>/daily_report.json` and check the
   `timing` block: `basis` should read `manifest.opened_at`, and `run_started_at` should match the
   RUN_OPEN manifest — not the end of the calendar day. On the very first run `boundary` will read
   `cold-start`, which is correct: there is no previous report yet.
3. **The second run is the freshness check.** On day two, `timing.boundary` should read
   `reported-ids` and `previous_run_id` should name day one. "New since the last round" then means
   what it says. If day two still reads `cold-start`, the report is not finding the previous day's
   object — check the `reports/` prefix and the report role's read grant.
4. **Location verdicts.** Spot-check a New Hampshire onsite posting: it should land in the
   needs-a-check section with a worksite-confirmation reason, not in the strong list and not excluded.
   An out-of-state onsite posting should be excluded with "outside New Hampshire" in its reason.
5. **Nothing was silently widened.** Per-source request budgets in the coverage receipt must not
   exceed their configured `max_requests_per_run`.

---

## 6. Rollback — validated locally, non-destructive, and ORDERED

Rollback has a required order. Doing it in the wrong order lets a running writer recreate exactly the
records the downgrade just removed, which is why this section is explicit about quiescence.

Evidence, with run roots named so the paths actually resolve:

- `project-factory/outputs/open-market-discovery/runs/20260924_open_market_release_repair_v1/evidence/rollback_validation.txt`
  — the P02 transcript. The P03 handoff cited this as `evidence/rollback_validation.txt` relative to
  its own directory, where **no such file exists**. Corrected here.
- `project-factory/outputs/open-market-discovery/runs/20260924_runtime_boundary_and_fresh_first_v1/evidence/rollback_data_rehearsal.txt`
  — the P03 end-to-end downgrade rehearsal (forward run → baseline read fails → backup + downgrade →
  baseline reads → baseline restarts with `DISAPPEARED=0`).

### 6.0 Order of operations — do these in sequence

1. **Quiesce the writers first.** Disable the schedules so nothing writes while you are rewriting
   state (§6.1). Confirm no execution is in flight before continuing: a Step Functions execution or a
   Lambda already running will finish its write *after* your downgrade and reintroduce new-format
   records. Wait for in-flight executions to finish rather than assuming the disable was instant.
2. **Downgrade the data** (§6.2) — dry run, read the plan, then apply.
3. **Roll the source back** (§6.3).
4. **Re-enable the schedules** only once the reverted code is deployed.

Re-enabling before step 3 completes puts the old code and new-format data in the same window, which
is the one combination that fails.

### 6.1 Partial disable — stops discovery only

**`UpdateSchedule` is a full replace, not a patch.** The P01 handoff's
`aws scheduler update-schedule --name jprs-discovery-daily --state DISABLED` is **rejected**:

```
aws: error: the following arguments are required: --flexible-time-window, --schedule-expression, --target
```

Pass every required argument, or set `DiscoveryCron` to a far-future expression and redeploy.

### 6.2 Data downgrade — REQUIRED, not optional

**This is the statement the P03 handoff contradicted itself about, and it is the one that matters.**

That document said, in §6, that *"the additive `CanonicalJob` / `DiffState` fields are ignored by the
old code"* — while its own §8, a few pages later, correctly reported the opposite. The earlier claim
is **false and withdrawn.**

At baseline `e549a73`, `CanonicalJob` and `DiffState` both use `ConfigDict(extra="forbid")`. Measured:
the baseline **rejects** a current monitored-job record on **18** fields and a current diff state on
**5**, and two new `ChangeEventType` values fail its enum. Pydantic raises rather than ignoring.

So a source-only rollback leaves the reverted code unable to read the state this release wrote. **You
must run the downgrade.** Re-verified in this run by the unmodified P02 review probe, whose
`rollback_reader` result reports `accepts_current_record: false` and names all 18 fields.

```bash
# dry run first — prints the plan, writes nothing
.venv/bin/python -m src.cli downgrade-state --bucket <bucket> --dt <YYYY-MM-DD>

# apply
.venv/bin/python -m src.cli downgrade-state --bucket <bucket> --dt <YYYY-MM-DD> \
    --apply --i-have-a-backup-plan
```

It backs every object up under `rollback-backup/<timestamp>/` **before** rewriting, drops only keys
the baseline rejects, and asserts that no job id and no grace clock is lost. Run it while the writers
are quiesced (§6.0).

**P04's own new state fields do not change this.** P04 added `head_cursors` and `head_frontier_at` to
`DiscoveryState` (in `discovery/`) and `report_generated_at` plus `timing` to the report JSON. The
baseline reads neither: `discovery/` did not exist before this release, and reports are outputs. So
the downgrade set is unchanged from P03's.

### 6.3 Full source rollback — without destroying the working tree

```bash
git worktree add /tmp/jprs-rollback e549a73
cd /tmp/jprs-rollback
sam build --template-file infra/template.yaml --build-dir /tmp/jprs-rollback-build
sam deploy --config-file infra/samconfig.toml --template-file /tmp/jprs-rollback-build/template.yaml
# afterwards
git worktree remove /tmp/jprs-rollback
```

Your working tree is never checked out, reset, stashed or staged by any of this.

CloudFormation removes `jprs-discovery`, its schedule, role, log group and alarm A8, and reverts the
report role's `discovery/*` grants.

### 6.4 What is left behind, stated correctly

Data under `discovery/` is inert to the baseline, which never reads that prefix, and a rollback cannot
emit a removal event. But the additive fields on `current/` records are **not** inert — see §6.2.
Nothing needs deleting; the downgrade is what makes the remaining data readable.

---

## 7. Cost

Unchanged by P04, which adds no infrastructure and no scheduled invocation. The P03 figures stand:
roughly **$0.11–0.13 per month** for the discovery function at 512 MB and 10–30 s per daily run
(5–15 GB-seconds per invocation), plus negligible S3 and CloudWatch. The P02 figures were wrong by
roughly 20× and were withdrawn in P03.

P04 can *slightly* increase request volume within existing limits: the feed-head walk may now spend
more than one page on recent arrivals. It cannot exceed a source's configured
`max_requests_per_run` — asserted at budgets 1, 2, 3 and 5 — so the cost ceiling does not move.

---

## 8. Existing-data reconciliation

- `SCHEMA_VERSION` stays **1.1.0, additive only**: same major, same `schema_v=1` prefix, **no replay
  required**. P04 added no model field to `CanonicalJob`.
- `DiscoveryState` gains `head_cursors` and `head_frontier_at`. Both default to empty, so an existing
  `discovery/state.json` written by P03 loads unchanged and the first run simply has no saved head
  position — which is correct, not a loss.
- The report JSON gains `report_generated_at` and `timing`. A report written by an **earlier** release
  has neither; the reader handles that by taking the previous report's candidate id list, which needs
  no timestamp. That is why the first run after deploy does not announce every already-seen posting as
  new. Regression: `test_a_previous_report_from_an_earlier_release_still_supplies_its_identity_list`.

---

## 9. Remaining gates — none closed by one switch

| Gate | Status | Closed by |
|---|---|---|
| Discovery runs in AWS | **not verified** | first scheduled run |
| Production HTTP transport, all four keyless feeds | **not verified** (see §3.4) | first scheduled run |
| Authenticated Adzuna search | **not verified** | your credential + a real search returning results |
| General-industry coverage | **open** | Adzuna succeeding in production |
| Careers-URL resolver live path | **not verified** | first run with `ResolveCareersUrls=true` |
| Rollback data downgrade against real state | **rehearsed only** | §6.2 dry run, then your approval |
| Freshness boundary across two real rounds | **rehearsed on real payloads** | day two in production (§5.3) |
| Location verdicts against the drive-time policy | **implemented, deliberately unresolved in state** | your confirmation of a worksite when one is flagged |

---

## 10. What needs you

1. **Decide on deployment.** Everything local is verified; nothing is deployed.
2. **One interpretation to confirm.** The policy states a drive duration ("approximately 30 minutes
   from Laconia"). This system does not measure drive time and no longer pretends to. It resolves only
   what it can check — the state boundary, and the cities you named — and routes every in-state
   worksite to a confirmation step instead of guessing. That means a New Hampshire onsite role now
   arrives as "confirm the worksite" rather than as a yes or a no. If you would rather it auto-approve
   a named short list of towns, that is a one-line change, but it would be me certifying a drive time
   I have not measured.
3. **The Adzuna credential**, if and when you want general-industry breadth.
4. Nothing else. No commit, branch, push or deploy was performed.
