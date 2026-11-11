# DEPLOYMENT_HANDOFF — open-market discovery, after the P05 resumability and release-binding repairs

Packet: `JPRS-L2-P05-resumable-discovery-release-repair-v01` · Run: `20260925_resumable_discovery_release_repair_v1`

This is the handoff of record. It supersedes the P04 handoff, whose §4 forward command could not
select the build it had just verified. Earlier handoffs and their evidence are preserved unchanged in
their own run directories; where this document disagrees with one of them, **this one is correct and
the disagreement is named explicitly below.**

**Nothing in this run touched AWS.** No deploy, no SSM write, no IAM change, no spend, no email, no
commit, no branch, no staging, no push, no reset. `sam validate` and `sam build` run entirely locally;
the template-selection evidence calls SAM's own resolution functions and never a cloud endpoint.

---

## 1. Approval boundary

| Action | Authorized by this packet? |
|---|---|
| Local code, tests, docs | yes — done |
| Local mocked-service verification | yes — done |
| `sam validate` / `sam build` | yes — done, no AWS call |
| Local template/config **selection** checks | yes — done, no AWS call |
| `sam deploy` | **no — needs your explicit approval** |
| SSM parameter creation or edit | **no — needs your explicit approval** |
| Creating an Adzuna account | **no — needs you** |
| Enabling careers-URL resolution | **no — needs your explicit approval** |
| git commit / branch / push | **no — needs your explicit approval** |

Branch `codex/real-job-radar` carries an **uncommitted working tree** holding the P01 implementation
and the P02–P05 repairs. Nothing is staged. §6 is written so that no rollback step destroys it.

---

## 2. What changes in AWS

**No infrastructure change from the P03/P04 proposal.** P05 is source-and-docs only: no new function,
schedule, role, parameter, alarm or IAM grant. `infra/template.yaml` is unchanged by this run and was
re-validated here.

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

Unchanged by P05, and its regression still passes. **The credential alone does not close the
general-industry coverage gate:** it enables the first *attempt*. The gate closes when a real
authenticated search returns results in production and the coverage receipt lists Adzuna under
`discovery_succeeded`.

### 3.3 Careers-URL resolution — proposes rows, does not monitor

Unchanged from P03/P04. `ResolveCareersUrls=true` lets discovery follow an aggregator apply link to
find an employer's own board, re-validating every redirect hop against the SSRF address rules. It
writes a *proposed* registry row; it never monitors anything. Actual monitoring needs you to apply the
row to `config/companies.yaml` and the SSM registry. Its live path remains **unverified**.

### 3.4 Live transport is still unverified

Unchanged and still true. P04 measured live `urlopen` returning **truncated bodies
non-deterministically** from this machine (80,693 bytes via `curl` versus 18,586 / 5,996 / 0 bytes via
`urllib` on consecutive attempts to the same URL). The connector handles that correctly — it keeps the
partial body and the JSON parse lands the snapshot `PARTIAL`.

P05 makes that safe failure *resumable* as well as visible: a `PARTIAL` page no longer hands its
continuation token forward as though the page had been read. The range stays owed and is retried
(§8, and `test_a_partially_downloaded_recent_page_is_owed_like_a_failed_one`).

**No local run has exercised the production transport end to end.** Everything verified in P04 and P05
replays payloads through the real pipeline with the transport mocked. Real or provider-shaped data,
mocked transport: that is not evidence the production transport works. The first scheduled run in
Lambda is that evidence. Watch `discovery_succeeded` and the `inaccessible` list on day one.

---

## 4. Deploy — bound to the build that was verified

**This is the section P04 got wrong.** It built into `/tmp/jprs-build` and then ran `sam deploy` with
no `--template-file`. SAM 1.137.1 resolves a deploy template by searching, relative to the **current
directory**, `.aws-sam/build/template.yaml`, then `template.yaml`, `template.yml`, `template.json`. A
`--build-dir` is never consulted. Measured in this tree (`evidence/p05_deploy_selection_results.json`):

- from the repository root the P04 command resolves to `<repo>/template.yml`, **which does not exist**;
- from `infra/` it resolves to `infra/.aws-sam/build/template.yaml`, a **stale 2026-08-01 build that
  contains no `DiscoveryFunction` at all** — it would silently deploy the pre-discovery stack;
- in any checkout carrying a default `.aws-sam/build/`, it selects that build instead of the new one.

There is a second trap behind the first. SAM sets its samconfig search directory to the **directory of
the template you give it**, so once the template lives in a temporary build directory, a relative
`--config-file infra/samconfig.toml` resolves to `<build-dir>/infra/samconfig.toml` and the
repository's config is silently missed. `infra/samconfig.toml` also provides no deploy template
override, so nothing else rescues the selection. **Both paths must be explicit, and the config path
must be absolute.**

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

git status                                        # expect an uncommitted tree; do NOT reset it
.venv/bin/python -m pytest -q -p no:cacheprovider # expect 316 passed

# A fresh build directory per attempt, so no earlier or stale build can be selected.
export BUILD="$(mktemp -d /tmp/jprs-build-XXXXXX)"

sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml --build-dir "$BUILD"

# Confirm the artifact is the one you are about to ship, before shipping it.
test -f "$BUILD/template.yaml" && grep -q DiscoveryFunction "$BUILD/template.yaml" \
  && echo "OK: built template contains DiscoveryFunction"

sam deploy \
  --template-file "$BUILD/template.yaml" \
  --config-file "$PWD/infra/samconfig.toml" \
  --config-env default        # review the change set before confirming
```

Verified locally, without invoking deploy or AWS: with `--template-file "$BUILD/template.yaml"`, SAM's
own `get_or_default_template_file_name` returns exactly that path, and the absolute `--config-file`
resolves to the repository's `infra/samconfig.toml`, while the relative form does not exist. Evidence:
`evidence/p05_deploy_selection_probe.py` and `evidence/p05_deploy_selection_results.json`, all five
assertions true. `tests/test_resumable_discovery_and_release_binding.py` asserts the commands **in
this document** carry both flags, so the binding cannot silently rot back out of the prose.

Two environment notes, neither a template problem:

- `sam build` can fail with `Operation not permitted: .aws-sam/build/*/.claude/commands` from a stale
  build directory. The `mktemp -d` build directory above avoids it.
- `sam validate` can fail with `PermissionError: /Users/drbretto/.aws-sam/metadata.json` when the
  sandbox denies that write. Run it with an isolated `HOME` and your real AWS config paths:
  `HOME=/tmp/samhome AWS_CONFIG_FILE=~/.aws/config AWS_SHARED_CREDENTIALS_FILE=~/.aws/credentials sam validate --lint --template-file infra/template.yaml`.
  Redirecting `HOME` also hides `~/.aws`, so if you redirect it you must pass both AWS paths or SAM
  reports `The config profile (...) could not be found` — that error is the redirect, not your profile.

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
   `reported-ids` and `previous_run_id` should name day one.
4. **Location verdicts.** Spot-check a New Hampshire onsite posting: it should land in the
   needs-a-check section with a worksite-confirmation reason, not in the strong list and not excluded.
   An out-of-state onsite posting should be excluded with "outside New Hampshire" in its reason.
5. **Nothing was silently widened.** Per-source request budgets in the coverage receipt must not
   exceed their configured `max_requests_per_run`. P05 made this stricter: failed and partial attempts
   now spend their request too, so a day with failures will show spend closer to the cap than before.
   That is the budget working, not a widening.
6. **Owed recent ranges are reported, not hidden.** New in P05. If a recent page fails or the budget
   runs out mid-burst, `inaccessible` says so with `<provider> recent arrivals` and a count of
   untraversed ranges, and `discovery/state.json` carries them under `head_pending`. On a later run
   that list should shrink to empty. A run reporting clean coverage while `head_pending` is non-empty
   would be a regression of exactly the defect this release repaired.

---

## 6. Rollback — validated locally, non-destructive, and ORDERED

Rollback has a required order. Doing it in the wrong order lets a running writer recreate exactly the
records the downgrade just removed, which is why this section is explicit about quiescence.

Evidence, with run roots named so the paths actually resolve:

- `project-factory/outputs/open-market-discovery/runs/20260924_open_market_release_repair_v1/evidence/rollback_validation.txt`
  — the P02 transcript. The P03 handoff cited this relative to its own directory, where **no such file
  exists**. Corrected in P04 and still correct here.
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

At baseline `e549a73`, `CanonicalJob` and `DiffState` both use `ConfigDict(extra="forbid")`. Measured:
the baseline **rejects** a current monitored-job record on **18** fields and a current diff state on
**5**, and two new `ChangeEventType` values fail its enum. Pydantic raises rather than ignoring. So a
source-only rollback leaves the reverted code unable to read the state this release wrote. **You must
run the downgrade.** (P03's §6 claim that the additive fields "are ignored by the old code" was false
and was withdrawn in P04. It stays withdrawn.)

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

**P05's own new state field does not change the downgrade set, and it degrades on purpose.** P05 adds
`head_pending` to `DiscoveryState`, alongside P04's `head_cursors` and `head_frontier_at`. All three
live under `discovery/`, a prefix the baseline never reads and which did not exist before this
release, so the downgrade set is unchanged from P03's.

Within the release lineage the degradation is deliberate and one-directional:

- **Forward** (P04 state read by P05 code): `head_pending` is absent, so the single `head_cursors`
  value is read as the one range still owed. Nothing is lost.
  Regression: `test_a_p04_state_document_resumes_its_saved_range`.
- **Backward** (P05 state read by P04 code): P04's `DiscoveryState` uses `extra="forbid"` and would
  **reject** a document containing `head_pending`. If you ever roll the discovery source back to P04
  while keeping its state, delete the `head_pending` key from `discovery/state.json`. `head_cursors`
  is written as a mirror of the newest owed range precisely so that a stripped document still resumes
  the most important one instead of none.
  Regression: `test_the_compatibility_mirror_tracks_the_newest_owed_range`.

Rolling back to the `e549a73` baseline needs neither step: that code never reads `discovery/` at all.

### 6.3 Full source rollback — without destroying the working tree

The rollback deploy needs the same explicit binding as the forward one (§4), and for the same reason:
`/tmp/jprs-rollback-build` is not a location SAM searches, and a relative config path would resolve
inside it.

```bash
git worktree add /tmp/jprs-rollback e549a73
export ROLLBACK_BUILD="$(mktemp -d /tmp/jprs-rollback-build-XXXXXX)"
cd /tmp/jprs-rollback
sam build --template-file infra/template.yaml --build-dir "$ROLLBACK_BUILD"
sam deploy \
  --template-file "$ROLLBACK_BUILD/template.yaml" \
  --config-file /Users/drbretto/Desktop/Projects/job-posting-reality-score/infra/samconfig.toml \
  --config-env default
# afterwards
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
git worktree remove /tmp/jprs-rollback
```

The config path is absolute and points at the **main** working tree's config on purpose: that is the
file carrying the stack name, region, bucket and parameter overrides, and a relative path would be
resolved against the rollback build directory instead. Verified by the same selection probe
(`p05_rollback_command` in the results file).

Your working tree is never checked out, reset, stashed or staged by any of this.

CloudFormation removes `jprs-discovery`, its schedule, role, log group and alarm A8, and reverts the
report role's `discovery/*` grants.

### 6.4 What is left behind, stated correctly

Data under `discovery/` is inert to the baseline, which never reads that prefix, and a rollback cannot
emit a removal event. But the additive fields on `current/` records are **not** inert — see §6.2.
Nothing needs deleting; the downgrade is what makes the remaining data readable.

---

## 7. Cost

Unchanged by P05, which adds no infrastructure and no scheduled invocation. Roughly **$0.11–0.13 per
month** for the discovery function at 512 MB and 10–30 s per daily run, plus negligible S3 and
CloudWatch. (The P02 figures were wrong by roughly 20× and were withdrawn in P03.)

P05 does not raise the request ceiling — it lowers effective spend if anything, because a failed or
partial attempt now consumes its request instead of being retried for free within the same run. The
per-source `max_requests_per_run` cap is asserted at budgets 1, 2, 3, 5 and 8, with failures in the
mix and across repeated runs, so the cost ceiling does not move.

---

## 8. Existing-data reconciliation

- `SCHEMA_VERSION` stays **1.1.0, additive only**: same major, same `schema_v=1` prefix, **no replay
  required**. P05 added no model field to `CanonicalJob`.
- `DiscoveryState` gains `head_pending` (a per-source list of untraversed recent cursor ranges).
  It defaults to empty, so an existing `discovery/state.json` loads unchanged, and a P04 document's
  `head_cursors` value is read as its one owed range. See §6.2 for the backward direction.
- The report JSON is unchanged by P05.
- Behavioural change worth knowing before you read day-one output: the coverage receipt can now report
  `<provider> recent arrivals` with a count of untraversed ranges. That line is the system telling the
  truth about incomplete coverage; before this release the same situation produced a clean-looking
  receipt and a lost posting.

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
| Recent-range resumability across real interruptions | **verified locally over persisted state** | a production day that actually fails a page (§5.6) |
| Location verdicts against the drive-time policy | **implemented, deliberately unresolved in state** | your confirmation of a worksite when one is flagged |

---

## 10. What needs you

1. **Decide on deployment.** Everything local is verified; nothing is deployed.
2. **One interpretation to confirm, carried forward from P04 and still open.** The policy states a
   drive duration ("approximately 30 minutes from Laconia"). This system does not measure drive time
   and no longer pretends to. It resolves only what it can check — the state boundary, and the cities
   you named — and routes every in-state worksite to a confirmation step instead of guessing.
3. **The Adzuna credential**, if and when you want general-industry breadth.
4. Nothing else. No commit, branch, push or deploy was performed.
