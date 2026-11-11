# DEPLOYMENT_HANDOFF — publication commit boundary and corrected release (P09)

Supersedes the P08 handoff on the four points its review named. Everything P08 recorded that is
still true is carried forward, and its evidence files are unchanged.

**Nothing in this run was deployed.** P06 is the running build and its approval is spent. This
document describes what a deploy would do and how to verify it; performing one needs fresh
approval.

---

## 1. Approval boundary

| allowed in this run | not done, and not authorized by it |
| --- | --- |
| local code, tests, verification scripts, docs | any deploy, `sam deploy`, change-set execution |
| local `sam validate` and `sam build` | any AWS call, invocation or cloud mutation |
| reading persisted local evidence | SSM, registry, credentials, email, applications |
| — | any git branch, stage, commit, push, reset, stash or checkout |

The uncommitted P01–P09 overhaul is preserved. There is no commit to return to, which is why no
step anywhere in this document uses git to move code.

---

## 2. What changes in AWS

**Six function artifacts, application code only.** Measured, not asserted:
`evidence/p09_change_set_check.txt`, exit 0, `CHANGE_SET_IS_CODE_ONLY`, against a P06 baseline
build reconstructed from the verified archive.

P07's claim that only two functions change was already refuted by P08: every function inherits
`Globals.Function.CodeUri: ../`, so a shared-module edit changes all six artifacts. A stop rule of
"reject anything but two functions" would reject a correct deploy. That correction stands.

### The stop rule

Do not deploy unless `scripts/release_preflight.sh` exits 0. It fails closed at the first failing
check and never reaches the deploy step — drilled across seven cases in
`evidence/p09_preflight_drill.txt`. In particular the change-set gate now **fails** for:

- any resource or property difference between the two built templates once `CodeUri` and absolute
  build paths are normalized (IAM, schedules, parameters, state machine, retention)
- a function added to or removed from the build
- a difference between the current `infra/template.yaml`, `infra/samconfig.toml` or
  `config/discovery_sources.yaml` and the hashes P06 recorded
- an unavailable baseline build or an unavailable recorded P06 identity — an unknown baseline is
  not a clean one, and the verdict is `COMPARISON_INCOMPLETE`

It passes for genuine code-only differences and for `CodeUri` differences that are only SAM's
per-build-directory rewrite.

**This is a local comparison of two built packages. It is not an AWS change set.** The script says
so on every run. Inspecting the real change set that CloudFormation reports remains a separate,
required step before you confirm: a parameter's previous value, a drifted resource or a transform's
own output can change resources for reasons no local diff can see.

---

## 3. What changed in the code

| area | change |
| --- | --- |
| `src/common/s3layout.py` | new `discovery_owed_publication_key(provider)`; `discovery_pending_publication_key` is now a whole-system receipt, still written and still read |
| `src/discovery/handler.py` | `persist` accepts a feed's observations into that feed's own owed record as the FIRST durable write of its round, then writes `raw/`/`normalized/`/`status/`, then the SUCCESS sentinels; recovery loads every feed's record plus the aggregate |
| `src/discovery/live.py` | the owed-debt bound COMPACTS instead of dropping; only the live view's own retention horizon removes anything, and both are reported |
| `src/report/handler.py` | the report states `consumed_job_ids` and `below_fit_threshold_job_ids`; the below-fit count is that list's length |

No IAM change is needed or made: `discovery/owed/*` is already covered by the existing
`arn:aws:s3:::${BucketName}/discovery/*` grants on both sides.

### New stored shape, and compatibility

- `discovery/owed/provider=<p>/owed_publication.json` — new, one per feed. Inert to P06, which has
  no code that reads it.
- `discovery/_pending_publication.json` — unchanged key. On the first run of this code, any debt
  the currently deployed version left there is read, unioned in and settled rather than orphaned.
- No field is added to `CanonicalJob` or `DiffState`, so no data downgrade is required for
  P07–P09. The P05 assessment of an August-era rollback is unchanged; see §5.3.

---

## 4. Deploy

Two steps, deliberately separate. The first verifies and deploys nothing; the second is yours.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

# The baseline is RECONSTRUCTED from the verified persisted archive, so it does not depend on a
# temporary directory from an earlier session surviving. P08's handoff named one; it is gone.
BASELINE="$(mktemp -d "${TMPDIR:-/tmp}/jprs-p06-baseline-XXXXXX")"
BUILD="$(mktemp -d "${TMPDIR:-/tmp}/jprs-build-XXXXXX")"

scripts/reconstruct_p06_baseline_build.sh "$BASELINE"
scripts/release_preflight.sh "$BUILD" "$BASELINE/build"
```

`release_preflight.sh` runs, in order and fail-fast: `git status` (read-only), the full test suite,
`policy-check`, `sam validate --lint`, `sam build` into `$BUILD`, an assertion that
`src/discovery/live.py` is present in BOTH the Discovery and Report artifacts (the report imports it
at invoke time, so a package missing it builds cleanly and fails in production), and the change-set
gate. On success it PRINTS the deploy command and stops.

```bash
sam deploy \
  --template-file "$BUILD/template.yaml" \
  --config-file "/Users/drbretto/Desktop/Projects/job-posting-reality-score/infra/samconfig.toml" \
  --config-env default
```

The explicit template is the one just verified, and the config path is absolute — the P04 failure
was SAM resolving a stale `.aws-sam/build/` template with no `DiscoveryFunction`.

The three email/notification parameters are **not** in `samconfig.toml` and must be carried forward
by CloudFormation as previous values, as P06 recorded. Do not retype them and do not print them.

> **Today the preflight will stop at `policy-check`.** Two operator-owned policy sources outside
> this repository were edited on 2026-09-26 and the committed projection no longer matches them.
> P09 changed no policy source; refreshing the projection is a candidate-policy decision and was
> deliberately not made here. See `VALIDATION.md` §9. Resolve that before deploying — that is the
> gate doing its job, not an obstacle to route around.

### 4.1 Post-approval live acceptance — prepared, and deliberately UNPROVEN

The condition: **one registry-absent employer's posting reaches the actual delivered report.**

Fetch the inputs read-only, then run the shipped check. Two steps on purpose: the check makes no
AWS call, so it cannot invoke, mutate or write anything.

```bash
#!/usr/bin/env bash
set -euo pipefail
DT="<YYYY-MM-DD>"; BUCKET="<bucket>"
OUT="$(mktemp -d "${TMPDIR:-/tmp}/jprs-live-XXXXXX")"
LIVE=()                      # initialized before use; P08's loop built its arguments in an unset var

aws s3 cp "s3://$BUCKET/reports/dt=$DT/daily_report.json" "$OUT/daily_report.json"
aws s3 cp "s3://$BUCKET/discovery/run=$DT/coverage.json"  "$OUT/coverage.json"
for P in himalayas remotive remoteok jobicy adzuna; do
  if aws s3 cp "s3://$BUCKET/discovery/live/provider=$P/live_jobs.json" "$OUT/$P.json"; then
    LIVE+=(--live "$OUT/$P.json")
  fi
done
if [[ ${#LIVE[@]} -eq 0 ]]; then
  echo "no live view was retrievable for any feed — that is a MISSING INPUT, not an empty feed" >&2
  exit 1
fi

.venv/bin/python scripts/inspect_discovery_integration.py \
  --report "$OUT/daily_report.json" --coverage "$OUT/coverage.json" "${LIVE[@]}"
```

Fetch the report and the views for the SAME run. The check enforces it: a view holding postings
first observed after the report's run returns `INPUTS_NOT_COHERENT` rather than reading them as
missing inputs.

| verdict | meaning | exit |
| --- | --- | --- |
| `ACCEPTANCE_MET` | every stored posting reconciled, and a registry-absent employer's posting is retained in the human report — **the live positive condition** | 0 |
| `INTEGRATION_OK` | every stored posting reconciled; none qualified today, or every retained one names an already-monitored employer | 0 |
| `RECONCILIATION_INCOMPLETE` | some postings were consumed and at least one reached no disposition. A positive witness may still be printed and is still true; the integration is partial | 1 |
| `MISSING_INGESTION` | stored postings reached no disposition and nothing evidences a consumed one — the consumer connection | 1 |
| `PENDING_PUBLICATION` | the only observations on record are owed; re-check after the next round | 2 |
| `INPUTS_NOT_COHERENT` | the live view is newer than the report; re-pair the inputs | 2 |
| `EVIDENCE_UNAVAILABLE` | the report predates `consumed_job_ids`; absent evidence, not a zero | 2 |
| `NO_INPUT` | discovery stored nothing; cannot conclude either way | 2 |

Every disposition is backed by something the report itself states — `complete_candidate_list`,
`policy_exclusions`, a row's provenance, `below_fit_threshold_job_ids`, `consumed_job_ids`, or the
coverage receipt's `pending_publication`. An employer-name match is no longer treated as evidence
that a posting was consumed; that inference is what let P08's check pass a missing job.

**Record the outcome honestly, including a zero.** A zero is legitimate: the feeds are a moving
window and the screener is a policy gate, not a quota. Do not re-run until a favorable sample
appears, and do not insert a fixture into production. Code deployment, live ingestion, actual
delivery and unattended next-day behavior remain four separate claims.

**This acceptance condition is not met by this run and must not be reported as met.**

---

## 5. Rollback

### 5.1 What the baseline is

`…/20260925_durable_discovery_publication_release_repair_v1/evidence/p06_baseline_src.tar.gz` — the
36 `src/` files P06 deployed, verified file by file against P06's own recorded SHA-256 list. It is
persisted in the repository, so nothing depends on a temporary build directory surviving.

Verification now **fails closed**. P08's verifier printed `MISMATCH` and exited 0; this one refuses
a corrupt archive, a modified recorded module, an archive carrying executable source P06 never
recorded, and a missing archive — each before anything is written anywhere. Identified macOS
AppleDouble metadata members are listed and ignored; nothing else is ignored.

### 5.2 Reverting P07–P09 to the deployed P06 source

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

WORK="$(mktemp -d "${TMPDIR:-/tmp}/jprs-rollback-XXXXXX")"
scripts/rollback_preflight.sh "$WORK"
```

That sequence verifies the archive, reconstructs the P06 build in `$WORK`, asserts the restored
tree is P06 and not a P06/P09 hybrid — by requiring `src/discovery/live.py` to be **absent**, since
that module is P07's — and asserts the working checkout still holds the overhaul. It deploys
nothing and it never touches the checkout's `src/`, so there is no "return" step to remember: the
overhaul was never a participant. Drilled end to end in scratch:
`evidence/p09_rollback_drill.txt`, `evidence/p09_rollback_preflight.txt`.

Before deploying the rollback, read the latest coverage receipt's `pending_publication`. If it is
non-empty, P06 will never drain those observations — it has no live view and no owed record — and
the postings named there leave the automatic path. Let one more discovery round publish them first
if they matter.

```bash
sam deploy \
  --template-file "$WORK/build/template.yaml" \
  --config-file "/Users/drbretto/Desktop/Projects/job-posting-reality-score/infra/samconfig.toml" \
  --config-env default
```

### 5.3 Durable state: leave it alone

All three discovery objects are inert to P06, which has no `src/discovery/live.py` and reads none
of them.

- **Leave `discovery/live/*` in place.** Deleting it discards observation history
  (`first_seen_at`, `observed_run_ids`) a later re-deploy would have to rebuild from the feed.
- **Leave `discovery/owed/*` and `discovery/_pending_publication.json` in place.** Inert to P06,
  and read again if this release returns.
- **No data downgrade is required for P07–P09.** An August-era rollback is a different and larger
  operation: the P05 handoff §6 still controls, in its stated order, including its required
  `downgrade-state` step.
- **Paused, not lost.** A debt outstanding at the moment of rollback is *paused*: the records stay
  on S3 and this release drains them if it returns. It is not deletion, and it is not irrecoverable
  loss. What it is not is automatic while P06 is running.

### 5.4 Bounded verification after any rollback

```bash
aws s3 cp "s3://$BUCKET/reports/dt=$DT/daily_report.json" - | head -c 2000
```

Expect a report that renders, with monitored candidates present and no discovery rows. A report
that fails to render is the signal that the revert was partial.

---

## 6. Open items that still need Brett

Carried forward; none is created or resolved by this run except as noted.

1. **Fresh approval to deploy this repair.** P06's approval is spent.
2. **New:** two operator-owned policy sources changed on 2026-09-26 and the committed projection no
   longer matches them. The projection is a candidate-policy artifact and was deliberately not
   refreshed here. `policy-check` is RED until you decide.
3. Adzuna developer credentials in SSM (`/jprs/secrets/ADZUNA_APP_ID`, `…_APP_KEY`). Still the only
   configured source with general all-industry breadth and a location filter; still gated and
   still named in the coverage receipt.
4. Whether to enable bounded careers-URL resolution (`ResolveCareersUrls`), currently `false`.
5. Whether to fix Lambda packaging, which ships the whole repository in every function. Two further
   signs this run: `src/.DS_Store` is packaged into the artifacts, and a stale `.aws-sam/build`
   contained a copied `.claude/commands` path. The report function's dependency on
   `src/discovery/live` survives only because of the whole-repo behavior, so a packaging fix must
   carry it explicitly.
6. Whether 21 days is the right live-view retention bound and 5 the right owed-batch compaction
   bound. Both are stated and reported when reached; neither is calibrated against measured data.
7. **The unattended round on 2026-09-26** (discovery 07:05) remains pending and unverified. This run
   deployed nothing, so it is still a P06 observation when it happens, with the exact evidence paths
   in the P06 run's `evidence/p06_live_verification_summary.md` §6.
