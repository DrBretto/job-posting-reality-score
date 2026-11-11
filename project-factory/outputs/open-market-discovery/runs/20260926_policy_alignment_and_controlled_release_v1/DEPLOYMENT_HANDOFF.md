# DEPLOYMENT_HANDOFF — current candidate policy and controlled release (P10)

Supersedes P09's handoff on two points, and carries everything else forward unchanged:

1. **`policy-check` is now GREEN.** The divergence P09 stopped at is resolved — not by refreshing a
   hash, but by implementing the screening behavior the changed source actually asks for. The
   refreshed projection is `1.1.0` and ships inside every function artifact.
2. **The release is verified against a freshly reconstructed P06 baseline built in this run**, not
   against P09's build directory. Both baseline and candidate build directories from this run are
   scratch paths and will not survive; §4 reconstructs them.

**Nothing in this run was deployed.** P06 is the running build, its approval is spent, and no fresh
authorization existed at the time of writing. No AWS call, invocation, change-set execution, email,
application or git mutation occurred.

---

## 1. Approval boundary

| done in this run | not done, and not authorized by this file |
| --- | --- |
| local source change, tests, audits, verification scripts, docs | any deploy, `sam deploy`, change-set execution |
| local `sam validate`, `sam build`, baseline reconstruction | any AWS call, invocation, or cloud mutation |
| reading persisted local evidence and the captured posting corpus | SSM, registry, credentials, email routing, applications |
| refreshing `config/candidate_policy.json` from current sources | any git branch, stage, commit, push, reset, stash, checkout |

The uncommitted P01–P10 overhaul is preserved. Nothing here uses git to move code, because there is
no commit to return to.

A fresh authorization, if given, covers **this stack's code-only release and one ordinary round,
including its existing digest to the existing recipient**. It does not cover IAM, schedules,
parameters, credentials, paid services, new sources, limits, retention, or notification routing.

---

## 2. What changes in AWS

**Six function artifacts, application code only.** Measured this run, not asserted:
`evidence/p10_release_preflight.txt` — final verdict `CHANGE_SET_IS_CODE_ONLY`, every check
performed, against a P06 baseline reconstructed and verified here
(`evidence/p10_reconstruct_p06_baseline.txt`, `BASELINE_VERIFIED`, 36/36 recorded files).

Six is the correct expectation, not a number to pattern-match: every function inherits
`Globals.Function.CodeUri: ../`, so any shared-module edit changes all six artifacts. P07's
"halt if not two" rule would reject a correct deploy. **The count alone is not the evidence** — the
per-file classification in the preflight output is.

The changed files appearing in all six artifacts are `src/candidate/screening.py` and
`src/candidate/policy.py`, both classified `[application code]`, plus the P07–P09 changes already
described in P09's handoff §3.

### One limitation of the local comparison, stated rather than buried

The reconstructed baseline carries the **current** tree outside `src/`. So
`config/candidate_policy.json` is byte-identical on both sides *by construction*, and the local
comparison **cannot** evidence that the refreshed projection ships. That is evidenced separately, by
hashing the file inside each built artifact: `evidence/p10_release_identity.json` →
`projection.packaged_into_artifacts_sha256`, identical across all six functions and equal to the
working-tree file (`projection_version 1.1.0`, 9 mapped rules, new workflow hash).

**This is a local comparison of two built packages. It is not an AWS change set.** The script says
so on every run. Inspecting the change set CloudFormation actually reports remains a separate,
required step before confirming: a parameter's previous value, a drifted resource, or the transform's
own output can change resources for reasons no local diff can see.

### The stop rule

Do not deploy unless `scripts/release_preflight.sh` exits 0. It fails closed at the first failing
check and never reaches the deploy step (drilled 7/7 in P09's `evidence/p09_preflight_drill.txt`;
not re-drilled here, and the script is unchanged by this run). Stop on any added or removed resource,
permission, schedule, parameter, retention or other non-code difference.

---

## 3. What changed in the code

| area | change |
| --- | --- |
| `src/candidate/screening.py` | new rule `customer-service-queue`; `SCREENING_RULESET_VERSION` 1.4.0 → 1.5.0 |
| `src/candidate/policy.py` | `customer-service-queue` mapped to `workflow` + `operating_plan`; `PROJECTION_VERSION` 1.0.0 → 1.1.0 |
| `config/candidate_policy.json` | refreshed from the five current sources; carries the new rule mapping |
| `tests/test_adjacent_roles_and_customer_service.py` | new; 40 regressions |

No IAM, template, schedule or parameter change. No new stored object, no new S3 prefix, no schema
change, and nothing added to `CanonicalJob`. The rule reads text already stored and writes its
verdict into the screening result that already existed.

### Compatibility, both directions

- **Forward.** The report groups policy exclusions by `rule_id` generically, so a new rule id needs
  no report change and appears in `## Excluded by candidate policy` with its duty evidence. Verified
  by rendering a real report over the captured corpus — see `VALIDATION.md` §5.
- **Backward.** A P06 rollback screens with ruleset 1.4.0 and the older projection *if* the archive's
  files are restored; the rule simply does not exist there. No data written by this release needs
  downgrading, because it writes none.

---

## 4. Deploy

Two steps, deliberately separate. The first verifies and deploys nothing; the second is yours.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

# Fresh paths. This run's directories were scratch and are gone.
BASELINE="$(mktemp -d "${TMPDIR:-/tmp}/jprs-p06-baseline-XXXXXX")"
BUILD="$(mktemp -d "${TMPDIR:-/tmp}/jprs-build-XXXXXX")"

scripts/reconstruct_p06_baseline_build.sh "$BASELINE"
scripts/release_preflight.sh "$BUILD" "$BASELINE/build"
```

`release_preflight.sh` runs, in order and fail-fast: read-only `git status`, the full test suite,
`policy-check`, `sam validate --lint`, `sam build` into `$BUILD`, an assertion that
`src/discovery/live.py` is present in BOTH the Discovery and Report artifacts, and the change-set
gate. On success it prints the deploy command and stops.

```bash
sam deploy \
  --template-file "$BUILD/template.yaml" \
  --config-file "/Users/drbretto/Desktop/Projects/job-posting-reality-score/infra/samconfig.toml" \
  --config-env default
```

Never omit `--template-file`; keep `--config-file` absolute. The three email/notification parameters
are **not** in `samconfig.toml` and must be carried forward by CloudFormation as previous values. Do
not retype them, do not reconstruct them, and do not print them.

Before confirming: verify the account and stack are the intended ones, and read the change set AWS
reports against the local verdict.

### 4.1 One controlled ordinary round, after approval

Do not overlap an active round. An already-running ordinary round can supply the evidence if its
deployed code and run artifacts are coherent with each other.

Fetch inputs read-only, then run the shipped check — two steps on purpose, because the check makes no
AWS call and so cannot invoke, mutate or write anything.

```bash
#!/usr/bin/env bash
set -euo pipefail
DT="<YYYY-MM-DD>"; BUCKET="<bucket>"
OUT="$(mktemp -d "${TMPDIR:-/tmp}/jprs-live-XXXXXX")"
LIVE=()

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

Pair the report and views from the SAME run; the check enforces it. Verdicts, unchanged from P09:

| verdict | meaning | exit |
| --- | --- | --- |
| `ACCEPTANCE_MET` | every stored posting reconciled, and a registry-absent employer's posting is retained in the human report — the live positive condition | 0 |
| `INTEGRATION_OK` | every stored posting reconciled; none qualified today, or every retained one names an already-monitored employer | 0 |
| `RECONCILIATION_INCOMPLETE` | some postings consumed, at least one reached no disposition | 1 |
| `MISSING_INGESTION` | stored postings reached no disposition and nothing evidences a consumed one | 1 |
| `PENDING_PUBLICATION` | the only observations on record are owed; re-check next round | 2 |
| `INPUTS_NOT_COHERENT` | the live view is newer than the report; re-pair the inputs | 2 |
| `EVIDENCE_UNAVAILABLE` | the report predates `consumed_job_ids`; absent evidence, not a zero | 2 |
| `NO_INPUT` | discovery stored nothing; cannot conclude either way | 2 |

`INTEGRATION_OK` on a legitimately thin day **is not** `ACCEPTANCE_MET`. Record a zero as a zero.
Do not seed production, relax fit, or re-run until a desirable role appears. Partial, missing or
incoherent evidence stays named as such, never reported as a quiet day.

Keep these four claims separate and do not let one stand for another: **report persisted**,
**delivery attempted**, **SES accepted the message**, **Brett actually received the digest**. SES
acceptance is not receipt. Respect delivery deduplication — do not delete a marker to force a
duplicate digest and do not widen recipient settings.

**Scheduled/unattended behavior is a separate claim** and stays unverified unless an actual
unattended execution is observed.

### 4.2 What this release does NOT do for the search

It changes which roles are screened out and why. It does not submit applications, generate resumes,
contact employers, or implement any part of the submission pilot. Nothing in this run touched those.

---

## 5. Rollback

Unchanged from P09 §5 and still controlling; summarized, not replaced.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
WORK="$(mktemp -d "${TMPDIR:-/tmp}/jprs-rollback-XXXXXX")"
scripts/rollback_preflight.sh "$WORK"
```

Re-verified in this run: exit 0, and the working checkout's `src/` fingerprint is byte-identical
before and after (`356c0ad140beae546c297081c529a1e7`) — `evidence/p10_rollback_preflight.txt`,
`evidence/p10_release_identity.json`. The sequence never touches the checkout's `src/`, so there is
no "return" step to remember.

Execute a rollback only under authorization that explicitly covers it. Before deploying one, read
the latest coverage receipt's `pending_publication`: if it is non-empty, **P06 will not drain those
observations** — it has no live view and no owed record — and the postings named there leave the
automatic path. They are paused on S3, not deleted. Leave `discovery/live/*`, `discovery/owed/*` and
`discovery/_pending_publication.json` in place; all three are inert to P06.

An August-era rollback is a different and larger operation: P05's handoff §6 still controls,
including its required `downgrade-state` step. Do not improvise a source-only rollback for it.

If a release needs rollback, stop mutating and state the problem first. Never restore baseline files
over the working tree, and do not reset or discard the uncommitted work.

---

## 6. Open items that still need Brett

1. **Fresh authorization to deploy this repair and run one controlled round.** P06's approval is
   spent and this file confers nothing. This is the only item blocking the release.
2. Adzuna developer credentials in SSM — still the only configured source with general
   all-industry breadth and a location filter; still gated, still named in the coverage receipt.
3. Whether to enable bounded careers-URL resolution (`ResolveCareersUrls`), currently `false`.
4. Whether to fix Lambda packaging, which ships the whole repository in every function.
   `src/.DS_Store` is still packaged. A packaging fix must carry the report function's invoke-time
   dependency on `src/discovery/live` explicitly.
5. Whether 21 days is the right live-view retention bound and 5 the right owed-batch compaction
   bound. Both are reported when reached; neither is calibrated against measured data.
6. **The unattended round on 2026-09-26** (discovery 07:05) was not checked by this run and is still
   a P06 observation. Exact evidence paths: the P06 run's
   `evidence/p06_live_verification_summary.md` §6.

---

## 7. After the live path is verified — the existing downstream sequence

Not this packet's work, and not a second plan. `APPLICATION_WORKFLOW.md` →
**Backlog Catch-up and Automated Submission Pilot** already controls it, in this order: reconcile
older still-open jobs against actual submission/skip/rejection history, deduplicate and re-check
current openings and fit; research the promising companies; obtain an operator-approved batch;
verify one real supported-form pilot end to end including attachments, answers and confirmations;
then expand as observed results justify. Preserve fresh arrivals throughout — catch-up must not
stall the current-day round.

No part of that is implemented or started here.
