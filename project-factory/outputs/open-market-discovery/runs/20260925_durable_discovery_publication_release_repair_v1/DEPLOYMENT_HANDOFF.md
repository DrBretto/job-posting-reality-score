# DEPLOYMENT_HANDOFF — durable publication and corrected release (P08)

Packet: `JPRS-L2-P08-durable-discovery-publication-and-release-repair-v01`
Run: `20260925_durable_discovery_publication_release_repair_v1`

This handoff **supersedes P07's** on the three points its review found wrong: the expected change
set, the rollback baseline, and the thin-day check. Everything else in P07's handoff still holds, and
the P05 handoff remains the record of the release P06 actually performed.

**Nothing in this run touched AWS.** No deploy, invoke, SSM read or write, IAM change, spend, email,
application, employer contact, registry edit, commit, branch, staging, push, reset, stash or checkout.
The bounded read-only AWS retrieval the packet permitted for the baseline **was not needed**: an
intact local P06 build was found and hash-verified instead.

**The deployed stack is still the P06 build and contains none of P07 or P08.**

---

## 1. Approval boundary

| Action | Authorized? |
|---|---|
| Local code, tests, docs, local verification | yes — done |
| `sam validate` / `sam build` | yes — done, no AWS call |
| `sam deploy` | **no — needs fresh explicit approval** |
| Any AWS mutation, invoke, SSM or IAM change | **no** |
| git commit / branch / stage / push | **no** |

P06's approval is spent on P06. `unlock` on this run means ready for deployment **review**, not
permission to deploy.

---

## 2. What changes in AWS — corrected

**No infrastructure change.** `infra/template.yaml`, `infra/samconfig.toml` and
`config/discovery_sources.yaml` are byte-identical to the versions P06 deployed, verified against
P06's own recorded SHA-256 (`evidence/p08_rollback_baseline_verification.txt`). The two built
templates — P06's and a fresh P08 build's — are byte-identical as well.

`git status` lists `infra/template.yaml` as modified. That modification belongs to P01–P05 and is
**already deployed**. It is not a pending change.

### The correction to P07's claim

P07's handoff said "the changed Lambdas are `jprs-discovery` and `jprs-report`", and told you to stop
if the change set showed anything else. That stop rule would have **rejected a correct deploy**. Every
function inherits `Globals.Function.CodeUri: ../`, so every function's package contains the whole
repository, and a shared-module edit changes all six artifacts.

Measured, not asserted (`evidence/p08_package_scope.py`, `evidence/p08_package_scope.txt`):

| What changes | Detail |
|---|---|
| **6 of 6 function code artifacts** | Collector, Differ, Discovery, Enumerate, Narrator, Report |
| application code, identical in each | `src/common/connectors.py`, `src/common/s3layout.py`, `src/discovery/connectors.py`, `src/discovery/handler.py`, `src/discovery/live.py` (new), `src/report/handler.py` |
| repository payload, inert at runtime | 59 doc/packet/run-output paths that packaging ships into every function |
| **nothing else** | no IAM statement, schedule, parameter, state machine, log retention, queue, alarm or new resource |

### The corrected stop rule

> Expect a change set containing **code-only updates to up to six Lambda functions and nothing else.**
> Stop if it contains any IAM, schedule, parameter, state-machine, retention or resource change, or if
> it proposes creating or deleting a resource. Six function updates is correct and expected; it is not
> a sign that something extra is in the tree.

Permissions the new code needs, all already granted by the deployed template and machine-checked by
`test_the_live_view_key_is_covered_by_the_declared_iam_on_both_sides`:

| Need | Grant |
|---|---|
| discovery writes `discovery/live/…` and `discovery/_pending_publication.json` | `DiscoveryOwnsDiscoveryPrefix` — `PutObject` on `discovery/*` |
| discovery reads both back | `DiscoveryReadOwnStateAndManifest` — `GetObject` on `discovery/*` |
| report reads them | `ReportReadProcessed` — `GetObject` on `discovery/*` |
| report must not write them | report's `PutObject` is `reports/*` only — asserted negatively |

The owed-publication ledger was deliberately designed as **one object at one known key** precisely so
that no `ListBucket` or `DeleteObject` grant is needed. If a future change makes it scan a prefix or
delete an object, that becomes an IAM change and this stop rule will correctly refuse it.

---

## 3. Owned changes in this run

Full inventory in `evidence/p08_owned_changes.txt`. P08's own slice:

**Created**
- `tests/test_durable_discovery_publication.py` — 11 fault-injection regressions
- `scripts/inspect_discovery_integration.py` — the live acceptance check

**Edited**
- `src/discovery/live.py` — `PendingPublication`, `PendingPublicationBatch`, `publish_live_view`;
  per-posting `observed_run_ids`; replay-safe `merge_live_view` (`observed_at`, monotonic timing)
- `src/discovery/handler.py` — `owe_publication`, `drain_publication`, `_usable_by_provider`,
  `_coverage_body`; `persist()` reordered; `persist_live_views` replaced by the owe/drain pair
- `src/common/s3layout.py` — `discovery_pending_publication_key()`
- `src/report/handler.py` — `CoverageInput.pending_publication`, its effect on the discovery health
  axis, and its lines in the rendered report and the report JSON
- `docs/plans/2026-09-24-open-market-job-discovery.md` — P08 implementation plan and execution log

`src/candidate/*`, `src/scoring/*`, `src/differ/*`, `src/collector/*`, `src/enumerate/*`, `config/*`
and `infra/*` are untouched by this run.

---

## 4. New stored shape, and compatibility

One new object, discovery-owned, at a fixed key:

```
discovery/_pending_publication.json
```

```jsonc
{
  "batches": {                     // provider -> batches owed, oldest observation first
    "himalayas": [
      {
        "run_id": "2026-09-25",
        "observed_at": "2026-09-25T11:05:02+00:00",
        "feed_produced_usable_page": true,
        "jobs": [ /* full CanonicalJob records */ ]
      }
    ]
  },
  "schema_version": "1.1.0"
}
```

At rest this object is normally `{"batches": {}}`: a batch is owed and cleared inside the same
invocation. It holds real content only between a capture and its publication — which is exactly the
window that used to lose data.

`discovery/live/provider={p}/live_jobs.json` keeps P07's shape and gains one field per posting:

```jsonc
"observed_run_ids": ["2026-09-25", "2026-09-26"]   // observation_count is this list's length
```

| Direction | Behavior | Why |
|---|---|---|
| **New code, no existing object** | reads as absent, nothing owed | `_load_optional`; the default is an empty ledger |
| **New code, P07-shaped live view** | accepted; `observed_run_ids` defaults to empty and is seeded from `last_seen_run_id` the first time the posting is touched | `runs_observed()` |
| **Deployed P06 code, both objects present** | **ignored** | P06 has no `src/discovery/live.py` at all and never reads either key |
| **Mixed deploy** | degrades to P06 behavior — objects written and not read, or not written and read as absent | no stage fails |

`inference` — a forward-compatible addition. No existing object's shape changes destructively and no
existing reader reads the new one, so there is no migration and no writer-quiescence requirement.

---

## 5. Deploy, using the P05 verified template/config selection pattern

Do **not** use an implicit SAM template. The P04 failure — SAM resolving a stale `.aws-sam/build/`
template with no `DiscoveryFunction` — is still the hazard.

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

git status                                        # expect an uncommitted tree; do NOT reset it
.venv/bin/python -m pytest -q -p no:cacheprovider # expect 350 passed
.venv/bin/python -m src.cli policy-check          # expect: projection matches all policy sources

export BUILD="$(mktemp -d "${TMPDIR:-/tmp}/jprs-build-XXXXXX")"

sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml --build-dir "$BUILD"

# Confirm the artifact is the one you are about to ship, before shipping it. The report function
# imports src.discovery.live, so a package missing it would fail at INVOKE time, not build time.
test -f "$BUILD/DiscoveryFunction/src/discovery/live.py" \
  && test -f "$BUILD/ReportFunction/src/discovery/live.py" \
  && echo "OK: the live-view module is present in BOTH function artifacts"

# Confirm the change set is code-only BEFORE deploying, against the verified P06 baseline.
.venv/bin/python \
  project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/evidence/p08_package_scope.py \
  /private/tmp/claude-501/jprs-build-p06-9H8jKS "$BUILD" .
# expect the final line: CHANGE_SET_IS_CODE_ONLY

sam deploy \
  --template-file "$BUILD/template.yaml" \
  --config-file "$PWD/infra/samconfig.toml" \
  --config-env default        # review the change set against §2's stop rule before confirming
```

The three email/notification parameters are **not** in `samconfig.toml` and must be carried forward by
CloudFormation as previous values, as P06 recorded. Do not retype them and do not print them.

### 5.1 Post-approval live acceptance — prepared, and deliberately UNPROVEN

The condition: **one registry-absent employer's posting reaches the actual delivered report.**

Fetch the inputs read-only, then run the shipped check. Two separate steps on purpose: the script
makes no AWS call, so it cannot invoke, mutate or write anything.

```bash
DT=<YYYY-MM-DD>; BUCKET=<bucket>; OUT="$(mktemp -d)"

aws s3 cp "s3://$BUCKET/reports/dt=$DT/daily_report.json" "$OUT/daily_report.json"
aws s3 cp "s3://$BUCKET/discovery/run=$DT/coverage.json"  "$OUT/coverage.json"
for P in himalayas remotive remoteok jobicy adzuna; do
  aws s3 cp "s3://$BUCKET/discovery/live/provider=$P/live_jobs.json" "$OUT/$P.json" 2>/dev/null \
    && LIVE="$LIVE --live $OUT/$P.json"
done

.venv/bin/python scripts/inspect_discovery_integration.py \
  --report "$OUT/daily_report.json" --coverage "$OUT/coverage.json" $LIVE
```

It reconciles every stored discovery identity to a disposition and returns one of:

| Verdict | Meaning | Exit |
|---|---|---|
| `ACCEPTANCE_MET` | a registry-absent employer's posting is retained in the human report — **the live positive condition** | 0 |
| `INTEGRATION_OK` | discovery postings were consumed and reconciled; none qualified today, or every retained one names an already-monitored employer | 0 |
| `MISSING_INGESTION` | stored postings reached no disposition — the consumer connection is broken | 1 |
| `PENDING_PUBLICATION` | the only observations on record are owed; re-check after the next round | 2 |
| `NO_INPUT` | discovery stored nothing; the check cannot conclude either way | 2 |

Its five controls were exercised locally against reports the real stages produced
(`evidence/p08_live_check_exercise.txt`), including the two that look identical from the outside — a
genuine zero-fit day and a removed consumer connection.

**Record the outcome honestly, including a zero.** A zero is legitimate: the feeds are a moving window
and the screener is a policy gate, not a quota. Do not re-run until a favorable sample appears and do
not insert a fixture into production. Code deployment, live ingestion, actual delivery and unattended
next-day behavior remain four separate claims.

**This acceptance condition is not met by this run and must not be reported as met.**

---

## 6. Rollback — now against a verified baseline

### 6.1 What the baseline is

`evidence/p06_baseline_src.tar.gz` — the 36 `src/` files P06 deployed, extracted from the local P06
build and verified file-by-file against P06's own recorded SHA-256 list (`BASELINE_VERIFIED`, 36/36 in
all six packaged functions). It is committed to this run root so the rollback does not depend on a
temporary directory surviving.

The whole procedure below was **drilled** in a scratch directory and passed both directions
(`evidence/p08_rollback_drill.sh`, `evidence/p08_rollback_drill.txt`). No step uses
`git reset`, `checkout`, `stash` or a guessed reverse patch, because the P01–P08 overhaul is
uncommitted and a git restore would destroy it.

### 6.2 Reverting P07 + P08 to the deployed P06 source

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
RUN=project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1

# R-1. Preserve the overhaul. There is no commit to return to.
export KEEP="$(mktemp -d "${TMPDIR:-/tmp}/jprs-overhaul-XXXXXX")"
find src -name '__pycache__' -prune -o -type f -print | sort | tar -cf - -T - \
  | ( cd "$KEEP" && tar -xf - )

# R-2. Verify the baseline before trusting it.
.venv/bin/python "$RUN/evidence/p08_verify_rollback_baseline.py" \
  /private/tmp/claude-501/jprs-build-p06-9H8jKS .   # expect BASELINE_VERIFIED
# If that path is gone, the archive is the baseline; extract it in R-3 and skip this step.

# R-3. Replace src/ wholly — a merge would leave a P06/P08 hybrid that was never deployed.
rm -rf src && tar -xzf "$RUN/evidence/p06_baseline_src.tar.gz"
test ! -e src/discovery/live.py && echo "OK: restored tree is P06, not a hybrid"

# R-4. Confirm every restored file against P06's record.
.venv/bin/python - <<'PY'
import hashlib, pathlib, re
rec = pathlib.Path("project-factory/outputs/open-market-discovery/runs/"
                   "20260925_controlled_discovery_deployment_v1/evidence/p06_build_identity.txt")
want = dict((m[2], m[1]) for m in
            (re.match(r"^([0-9a-f]{64})\s+(src/\S+)$", l.strip()) for l in rec.read_text().splitlines())
            if m)
bad = [r for r, h in want.items()
       if not pathlib.Path(r).exists()
       or hashlib.sha256(pathlib.Path(r).read_bytes()).hexdigest() != h]
print("ROLLBACK_SOURCE_VERIFIED" if not bad else f"MISMATCH: {bad}")
PY

# R-5. Rebuild and redeploy with the §5 command shape.

# R-6. To return to the overhaul afterwards:  rm -rf src && cp -R "$KEEP/src" src
```

### 6.3 Durable state: leave it alone

Both new objects are inert to P06's code, which has no `src/discovery/live.py` and never reads either
key. So:

- **Leave `discovery/live/*` in place.** Deleting it would discard observation history
  (`first_seen_at`, `observed_run_ids`) that a later re-deploy would have to rebuild from the feed.
- **Leave `discovery/_pending_publication.json` in place.** Inert to P06; read again if P08 returns.
- **No data downgrade is required for P07 or P08.** Neither adds a field to `CanonicalJob` or
  `DiffState`; P08's per-posting `observed_run_ids` is a new field on a P07-only model that P06 does
  not read. This does **not** weaken the P05 §6 assessment — see 6.4.
- **One honest cost.** If a batch is owed at the moment of rollback, P06 will never drain it and those
  observations are lost. The coverage receipt names the job ids, so check
  `pending_publication` in the latest receipt first and, if it is non-empty and the postings matter,
  let one more discovery round publish them before rolling back.

### 6.4 If the whole discovery release must come out

The P05 handoff §6 applies unchanged, in its stated order (quiesce → downgrade data → revert source →
re-enable), **including its required `downgrade-state` step**. An August rollback still requires that
job-data downgrade. P08 does not change or weaken that assessment.

### 6.5 Bounded verification after any rollback

```bash
aws s3 cp "s3://$BUCKET/reports/dt=$DT/daily_report.json" - | head -c 2000
```

Expect a report that renders, with monitored candidates present and no discovery rows. A report that
fails to render is the signal that the revert was partial.

---

## 7. Open items that still need Brett

Carried forward; none is created or resolved by this run except as noted.

1. **Fresh approval to deploy this repair.** P06's approval is spent.
2. Adzuna developer credentials in SSM (`/jprs/secrets/ADZUNA_APP_ID`, `…_APP_KEY`). Still the only
   configured source with general all-industry breadth and a location filter; still gated and still
   named in the coverage receipt.
3. Whether to enable bounded careers-URL resolution (`ResolveCareersUrls`), currently `false`.
4. Whether to fix Lambda packaging, which ships the whole repository in every function. **This run
   quantified it**: all six artifacts change on any shared-module edit, and 59 differing paths are
   documentation rather than code. The report function's dependency on `src/discovery/live` survives
   only because of that behavior, so a future packaging fix must carry it explicitly.
5. Whether 21 days is the right live-view retention bound, and whether 5 is the right owed-batch
   bound. Both are stated and reported when reached; neither is calibrated against measured data.
6. **The unattended round on 2026-09-26** (discovery 07:05) is still pending and unverified. This run
   deployed nothing, so it remains a P06 observation when it happens.
