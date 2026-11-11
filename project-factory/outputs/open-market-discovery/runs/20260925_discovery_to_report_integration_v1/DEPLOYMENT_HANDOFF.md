# DEPLOYMENT_HANDOFF — discovery-to-report integration (P07)

Packet: `JPRS-L2-P07-discovery-to-report-integration-v01` · Run: `20260925_discovery_to_report_integration_v1`

This handoff covers **only** the P07 repair. The P05 handoff remains the handoff of record for the
P01–P05 release that is already deployed; this document adds to it and does not replace it. Where
they differ, the difference is named in §6.

**Nothing in this run touched AWS.** No deploy, no invoke, no SSM read or write, no IAM change, no
spend, no email, no application submitted, no employer contacted, no commit, branch, staging, push,
reset, stash or checkout. `sam validate` and `sam build` ran entirely locally.

**The currently deployed stack is the P06 build and contains none of this.** Every claim about P07
behavior in any current summary is a claim about the local working tree.

---

## 1. Approval boundary

| Action | Authorized by the P07 packet? |
|---|---|
| Local code, tests, docs | yes — done |
| Local mocked-service verification | yes — done |
| `sam validate` / `sam build` | yes — done, no AWS call |
| `sam deploy` | **no — needs fresh explicit approval** |
| Any AWS mutation, invoke, SSM or IAM change | **no** |
| git commit / branch / stage / push | **no** |

P06's approval is spent on P06. It does not carry to this repair.

---

## 2. What changes in AWS

**No infrastructure change at all.** No new function, schedule, role, parameter, alarm, queue, state
or IAM grant. `infra/template.yaml` and `infra/statemachine/jprs-daily-assemble.asl.json` are
**byte-unchanged by this run**.

This is a deliberate property of the design rather than luck, and it is machine-checked
(`tests/test_discovery_to_report_integration.py`, three deployment-surface tests):

| Need | Already granted by the deployed template |
|---|---|
| discovery writes `discovery/live/provider={p}/live_jobs.json` | `DiscoveryOwnsDiscoveryPrefix` — `PutObject` on `discovery/*` |
| discovery reads the prior round's copy back | `DiscoveryReadOwnStateAndManifest` — `GetObject` on `discovery/*` |
| report reads it | `ReportReadProcessed` — `GetObject` on `discovery/*` |
| report must **not** write it | report's `PutObject` is `reports/*` only — asserted negatively |

Invocation order is likewise unchanged and asserted against the real files: `DiscoveryCron`
`cron(5 7 * * ? *)` precedes `AssembleCron` `cron(0 9 * * ? *)` in `America/New_York`; the assemble
state machine still has exactly `LoadCompanies → DiffAllCompanies → BuildReport` plus
`ReportIncomplete`, with no discovery task added.

**So this deploy is a code-only stack update.** The changed Lambdas are `jprs-discovery` and
`jprs-report`.

---

## 3. Exact owned changes

Full list, separated from the pre-existing uncommitted overhaul, in
`evidence/p07_owned_changes.txt`. Summary:

**Created**
- `src/discovery/live.py` — the live-view model and its pure merge function
- `tests/test_discovery_to_report_integration.py` — 23-case acceptance harness

**Edited**
- `src/common/connectors.py` — `job_source_id()` hook; `build_snapshot` maps jobs through it
- `src/common/s3layout.py` — `discovery_live_key()`
- `src/discovery/connectors.py` — `DiscoveryConnector.FEED_SLICE` + `job_source_id` override
- `src/discovery/handler.py` — `persist_live_views()`; `persist()` accepts `now`
- `src/report/handler.py` — discovery merge in `assemble_report_input`; carried-over / awaiting
  coverage statements; `RunTiming` boundary-provenance fields; `top_matches` history fallback
- `tests/test_resumable_discovery_and_release_binding.py` — two tests re-scoped onto real producers
- `docs/plans/2026-09-24-open-market-job-discovery.md` — implementation plan and execution log

`src/candidate/*`, `src/scoring/*`, `src/differ/*`, `src/collector/*`, `src/enumerate/*`,
`config/*` and `infra/*` are untouched.

---

## 4. New stored shape, and compatibility with the running P06 deployment

One new object per discovery feed:

```
discovery/live/provider={provider}/live_jobs.json
```

```jsonc
{
  "source_id": "himalayas:all",
  "jobs": {                       // job_id -> record
    "himalayas:all#internal-tools": {
      "job": { /* a full CanonicalJob, schema 1.1.0 */ },
      "first_seen_run_id": "2026-09-25",
      "last_seen_run_id":  "2026-09-26",
      "observation_count": 2,
      "alias_job_ids": []
    }
  },
  "observed_run_ids": ["2026-09-25", "2026-09-26"],
  "last_observed_run_id": "2026-09-26",
  "last_observed_at": "2026-09-26T11:05:00+00:00",
  "retired_for_retention": [],
  "schema_version": "1.1.0"
}
```

### Reader/writer compatibility with what is deployed now

| Direction | Behavior | Why |
|---|---|---|
| **New code, no existing object** | reads as absent; report states the feed has no stored postings yet and shows none from it | `_load_json(..., default=None)`; asserted by `test_a_late_arriving_discovery_round_reaches_the_following_report` |
| **New code, objects written by P06** | none exist — P06 never wrote this key | new key, not a reshape of an existing one |
| **Deployed P06 code, object present** | **ignored** | P06's report reads `expected_sources` + `current/` only, and never lists or fetches this key |
| **Mixed deploy** (discovery new, report old, or the reverse) | degrades to P06 behavior: the object is written and not read, or not written and read as absent | no stage fails; the report simply shows no discovery candidates, which is exactly today's behavior |

`inference` — this is a forward-compatible addition, not a migration. There is no data conversion
step and no writer quiescence requirement for the new object, because **no existing object's shape
changes and no existing reader reads the new one.**

### The one behavioral change to an existing stored value

Discovery `CanonicalJob.source_id` and `job_id` now use the stable feed slice (`himalayas:all#slug`)
instead of the pagination cursor (`himalayas:NEW_TWO#slug`). Effect on already-stored data:

- `normalized/` objects written by the deployed P06 build keep their old cursor-bound ids. They are
  **not read by report assembly** before or after this change, so nothing re-reads them.
- No `current/` or `events/` record has ever carried a discovery id, because discovery never reached
  the differ. So the monitored lifecycle is untouched.
- The first post-deploy discovery run rebuilds the live view from the feed under the new ids.
  `first_seen_at` for those postings will be that run, which is honest: the live view did not exist
  before, so that genuinely is our first observation *in this store*. It is not presented as the
  employer's publication date — those remain separate fields, and the report keeps saying so.

---

## 5. Deploy, using the P05 verified template/config selection pattern

Do **not** use an implicit SAM template. The P04 failure — SAM resolving a stale `.aws-sam/build/`
template that contained no `DiscoveryFunction` — is still the hazard, and `test_the_documented_
deploy_commands_bind_template_and_config_explicitly` in the P05 suite enforces the shape below.

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

git status                                        # expect an uncommitted tree; do NOT reset it
.venv/bin/python -m pytest -q -p no:cacheprovider # expect 339 passed
.venv/bin/python -m src.cli policy-check          # expect: projection matches all policy sources

export BUILD="$(mktemp -d /tmp/jprs-build-XXXXXX)"

sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml --build-dir "$BUILD"

# Confirm the artifact is the one you are about to ship, before shipping it.
test -f "$BUILD/DiscoveryFunction/src/discovery/live.py" \
  && test -f "$BUILD/ReportFunction/src/discovery/live.py" \
  && echo "OK: the live-view module is present in BOTH function artifacts"

sam deploy \
  --template-file "$BUILD/template.yaml" \
  --config-file "$PWD/infra/samconfig.toml" \
  --config-env default        # review the change set before confirming
```

The `ReportFunction` check is not ceremony: `src/report/handler.py` imports `src.discovery.live`, so
a package missing it would fail at invoke time rather than at build time. `.samignore` prunes no part
of `src/`, and the built artifacts were confirmed to contain it (`evidence/p07_sam_build.txt`).

Expect the change set to show updates to `jprs-discovery` and `jprs-report` only, and **no** IAM,
schedule, state-machine or parameter diff. If it shows any of those, stop: something other than this
repair is in the tree.

### 5.1 Post-approval live acceptance — prepared, and deliberately UNPROVEN

The condition: **one registry-absent employer's posting reaches the actual delivered report.**

```bash
# after the deploy, on the next scheduled round (or a manual discovery invoke if approved separately)
aws s3 cp "s3://<bucket>/reports/dt=<YYYY-MM-DD>/daily_report.json" - \
  | .venv/bin/python -c '
import json,sys
r=json.load(sys.stdin)
mon=set(r["expected_sources"])
rows=[x for x in r["complete_candidate_list"] if x["source_kind"]=="DISCOVERY_FEED"]
print("discovery candidates:",len(rows))
for x in rows[:10]:
    print(" ",x["job_id"],"|",x["employer"],"|",x["screen_outcome"],"|",x["apply_url"])
print("any from a source outside the monitored registry:",
      any(x["source_id"] not in mon for x in rows))
'
```

**Record the outcome honestly, including a zero.** The pipeline may legitimately retain zero
discovery candidates on a given day: the feeds are a moving window and the screener is a policy gate,
not a quota. A zero must be distinguished from a missing integration by checking, in order:

1. `discovery/live/provider=*/live_jobs.json` exists and is non-empty → the producer ran
2. `coverage.inaccessible` in the report names each feed's state → the consumer saw it
3. `policy_excluded_count` and `below_fit_threshold_count` → postings arrived and were judged

If all three hold and the count is still zero, the integration is working and the day was thin.
**Do not re-run until a favorable sample appears, and do not manufacture a production candidate.**

This acceptance condition is **not met by this run and must not be reported as met.** Deployment,
live integration and unattended next-day behavior remain three separate claims.

---

## 6. Rollback

**The August rollback is not the default for this repair**, and the P05 §6 data downgrade is **not
required** for it. Those procedures exist because the P01–P05 release changed `CanonicalJob` and
`DiffState` in ways the baseline `extra="forbid"` models reject. P07 adds **no field to any existing
model** — it adds one new object under a new key. So reverting P07 alone is a source-only revert.

### 6.1 Reverting P07 only

1. Restore the seven edited files and remove the two created ones (§3). The working tree is
   uncommitted, so **take a copy of the files before touching them** — there is no commit to return
   to, and `git checkout`/`reset`/`stash` would destroy the surrounding overhaul. This is the
   uncommitted-tree hazard, and it is the reason no step here uses a git restore command.
2. Rebuild and redeploy with the §5 command shape.
3. **Leave `discovery/live/*` in place.** It is inert to the reverted code — nothing reads it — and
   deleting it would discard the observation history (`first_seen_at`, observation counts) that a
   later re-deploy would otherwise have to rebuild from scratch. Discovery state is preserved by
   doing nothing, which is the safest available option.
4. No writer quiescence is needed, because no existing object's shape is being rewritten.

### 6.2 If the whole discovery release must come out

Then the P05 handoff §6 applies unchanged, in its stated order (quiesce → downgrade data → revert
source → re-enable), including its **required** `downgrade-state` step. P07 does not change that
assessment and does not weaken it.

### 6.3 Bounded verification after any rollback

```bash
aws s3 cp "s3://<bucket>/reports/dt=<YYYY-MM-DD>/daily_report.json" - | head -c 2000
```

Expect a report that renders, with monitored candidates present and no discovery rows. A report that
fails to render is the signal that the revert was partial.

---

## 7. Open items that still need Brett

Carried forward; none is created or resolved by this run.

1. **Fresh approval to deploy this repair.** P06's approval is spent.
2. Adzuna developer credentials in SSM (`/jprs/secrets/ADZUNA_APP_ID`, `…_APP_KEY`). Still the only
   configured source with general all-industry breadth and a location filter; still gated and still
   named in the coverage receipt rather than hidden.
3. Whether to enable bounded careers-URL resolution (`ResolveCareersUrls`), currently `false`.
4. Whether to fix Lambda packaging, which still ships the whole repository in every function. This
   run depends on that behavior (it is how `src/discovery/live.py` reaches `jprs-report`), so if
   packaging is ever narrowed, the report function's dependency on `src/discovery/live` must be
   carried explicitly. Noted so a future packaging change cannot break this silently.
5. Whether 21 days is the right retention bound for the discovery live view. It is stated and
   bounded; the number has not been calibrated against a measured feed churn rate.
