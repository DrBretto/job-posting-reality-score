# VALIDATION — durable discovery publication and release repair (P08)

Packet: `JPRS-L2-P08-durable-discovery-publication-and-release-repair-v01`
Run: `20260925_durable_discovery_publication_release_repair_v1` · Date: 2026-09-25

**Nothing in this run touched AWS.** No deploy, invoke, SSM read or write, IAM change, spend, email,
application, employer contact, registry edit, commit, branch, staging, push, reset, stash or
checkout. `sam validate` and `sam build` ran locally. The bounded read-only AWS retrieval the packet
permitted for the rollback baseline **was not needed and was not performed** — an intact local P06
build was found and verified instead, which is the packet's stated preference.

**The deployed stack is still the P06 build.** Everything below is a claim about the local working
tree. P07's integration is preserved unchanged in behavior; nothing in it was undone or re-planned.

---

## 1. R1 — the interruption is repaired, measured by the reviewer's own probe

The reviewer's independent probe was copied **byte-identical** into this run
(`evidence/p08_interrupted_publish_probe_unmodified.py`; `diff` against P07's copy reported no
difference) and run before and after the repair. It compares identical external inputs with and
without one storage failure immediately before the live-view write, and both arms then meet a
changed/empty feed window on a same-run retry and on the following round.

| Probe result | Control (no interruption) | Interrupted — BEFORE | Interrupted — AFTER |
|---|---|---|---|
| job durably normalized | yes | yes | yes |
| coverage/progress already persisted | yes | yes | yes |
| candidate survives the same-run retry | yes | **no** | **yes** |
| candidate reaches the following report | yes | **no** | **yes** |
| original raw observation retained | yes | yes | yes |

`evidence/p08_before_repair_interrupted_publish.json` and
`evidence/p08_after_repair_interrupted_publish.json`. After the repair the interrupted arm is
identical to the control in every field. The recovery happens with the feed returning **nothing** on
both later fetches, so it is replay of the captured observation and not a re-fetch.

### What changed in the code

`persist()` in `src/discovery/handler.py` had one ordering defect with a large consequence: it
committed `raw/`, `normalized/`, `status/`, the SUCCESS sentinel, coverage, traversal state and
growth, and only then wrote the live view the report reads. The observations were durable and
unreachable at the same time, and the retry destroyed the last trace of them by overwriting
`normalized/` for the same `dt`.

The write order is now: snapshots → **owe** → progress → **drain** → residual receipt.

| Piece | Where | What it does |
|---|---|---|
| `PendingPublication` | `src/discovery/live.py` | the owed-observation ledger, one object at one known key |
| `owe_publication` | `src/discovery/handler.py` | records each touched provider's observations as owed, before any progress record can claim them published |
| `drain_publication` | `src/discovery/handler.py` | publishes one feed at a time, clearing that feed's debt only after its view has committed |
| `publish_live_view` | `src/discovery/live.py` | applies owed batches oldest-observation-first onto the stored view |
| `observed_run_ids` (per posting) | `src/discovery/live.py` | makes replay exactly idempotent instead of merely convergent |
| `pending_publication` | coverage receipt + `src/report/handler.py` | makes an outstanding debt visible in the morning report |

Two design constraints are load-bearing and are recorded because a later change could silently break
them:

- **One known key, never a prefix scan.** The discovery role grants `GetObject`/`PutObject` on
  `discovery/*` and **neither `ListBucket` nor `DeleteObject`**. A ledger found by listing, or cleared
  by deleting, would have required widening this function's IAM — which R2.1 forbids and which the
  package-scope rule classifies as a prohibited change. Clearing a debt is rewriting the object
  without it.
- **No new concurrency hazard.** The ledger is read-modify-written by one scheduled stage, exactly as
  `discovery/_discovery_state.json` and `discovery/_source_growth.json` already are.

### Invariants, and where each is established

| Packet invariant | Established by |
|---|---|
| already-durable observations recoverable without the provider returning the job | probe after-state; `test_the_same_run_retry_publishes_the_owed_job_from_an_empty_feed`; `…_the_following_run_publishes_it_and_keeps_the_original_observation_timing` |
| progress/coverage cannot quietly erase unmaterialized observations; pending is visible | `test_an_interrupted_publication_owes_the_captured_job_instead_of_losing_it`; `…_report_says_the_posting_is_captured_but_unpublished`; `evidence/p08_sample_report_interrupted_round.md` |
| a repeated attempt neither duplicates jobs nor inflates observation history for the same run | `test_a_batch_owed_after_its_view_committed_replays_without_duplicating_or_inflating` |
| recovery retains original observation timing/provenance | `…_keeps_the_original_observation_timing` (the posting is republished as the earlier run's observation, and the view's own last-look advances separately) |
| cannot roll back newer observations or erase another provider's successful work | `test_a_replayed_batch_cannot_roll_back_a_newer_observation`; `test_the_next_round_recovers_the_owed_feed_without_disturbing_the_committed_one` |
| partial failure leaves a committed view or explicit replayable work | `test_a_partial_multi_provider_write_commits_one_feed_and_leaves_the_other_owed` |
| request caps, traversal debt, candidate policy, feed-vs-ATS lifecycle preserved | `test_an_interrupted_publication_does_not_spend_extra_requests_or_erase_traversal_debt`; the 339 pre-existing tests, which include P05's budget and owed-range cases and P07's closure-semantics cases |
| older useful candidates are not silently dropped as a recovery mechanism | `test_the_owed_ledger_is_bounded_and_says_so_when_it_drops_a_batch` — the bound exists and is reported with the job ids it cost |

### The new regressions, and what they do NOT establish

`tests/test_durable_discovery_publication.py`, 11 cases. Each injects the failure by refusing one
`PutObject` inside the mocked AWS client, so the failing call is the one production code makes. Every
intermediate record is written by a real producer; `test_no_intermediate_record_in_these_cases_is_
written_by_this_test` asserts that structurally, both by a textual check that the module contains no
S3 write call and by a prefix census of the bucket.

They do **not** establish: anything about real S3 or real IAM (moto grants everything); anything about
the live market (every payload is synthetic, and the insurance-company role is a test control, never
a vacancy); anything about two concurrent discovery invocations; or that a batch dropped by the
ledger bound is actually recoverable from `raw/` by hand — that path is stated in the receipt and
deliberately not automated.

**No real cloud failure was injected**, as the packet requires.

---

## 2. R2.1 — the actual package scope, measured rather than asserted

P07's handoff said a deploy could change only the discovery and report function code. That is wrong,
and the corrected stop rule matters: the old one would have **rejected a legitimate code-only update**.

`evidence/p08_package_scope.py` diffs the verified P06 package against a fresh P08 build, file by
file, by content hash. `evidence/p08_package_scope.txt`:

- **6 of 6 function artifacts change** — Collector, Differ, Discovery, Enumerate, Narrator, Report.
  All functions inherit `Globals.Function.CodeUri: ../`, so each package contains the whole
  repository and every shared-module edit reaches all of them.
- The application-code differences are exactly six paths, identical in every function:
  `src/common/connectors.py`, `src/common/s3layout.py`, `src/discovery/connectors.py`,
  `src/discovery/handler.py`, `src/discovery/live.py` (added), `src/report/handler.py`. Four are
  P07's; two are P08's, plus `live.py` which both touched.
- 59 further differing paths are **repository payload** — docs, packets and run outputs that
  packaging ships into every function. Inert at runtime, and the reason open item 4 exists.
- **The built templates are byte-identical**, and `infra/template.yaml`, `infra/samconfig.toml` and
  `config/discovery_sources.yaml` all match P06's recorded SHA-256 exactly
  (`evidence/p08_rollback_baseline_verification.txt`). Content hashes, not modification times.

Verdict: `CHANGE_SET_IS_CODE_ONLY`. No IAM, schedule, parameter, state-machine or retention change.

`git status` shows `infra/template.yaml` as modified — that modification is P01–P05's and is
**already deployed**; its content is identical to what P06 shipped. Nothing here changes it.

---

## 3. R2.2 — a real, hash-verified rollback baseline exists

P07's handoff proposed copying the current working files aside before a rollback. Those files are the
overhaul being rolled back, so that is not a baseline. This run found a genuine one.

`evidence/p08_verify_rollback_baseline.py` compares a candidate build against P06's **own recorded
per-file SHA-256 list** (`…/20260925_controlled_discovery_deployment_v1/evidence/p06_build_identity.txt`),
a record made before any of this work existed. Result: the local build at
`/private/tmp/claude-501/jprs-build-p06-9H8jKS` matches on **36 of 36 recorded source files in all
six packaged functions** — `BASELINE_VERIFIED`.

Because that path is a temporary directory that a reboot can clear, the verified tree is archived in
the repository at `evidence/p06_baseline_src.tar.gz` (36 files, 145 KB). The rollback no longer
depends on anything outside the repo.

`evidence/p08_rollback_drill.sh` then **tested recovery locally**, in a scratch directory so the
uncommitted overhaul is never at risk (`evidence/p08_rollback_drill.txt`, `DRILL_PASSED`):

1. preserve the current overhaul — aggregate digest recorded
2. restore the baseline over it — 36 files, and `src/discovery/live.py` correctly absent, so the
   result is P06 and not a P06/P08 hybrid
3. verify every restored file against P06's recorded hash — matched 36, differing 0, missing 0
4. return to the overhaul — byte-identical to its pre-drill state, so the rollback is reversible

No git reset, checkout, stash or guessed reverse patch is used anywhere in the procedure, and no
rollback defaults to the August code.

---

## 4. R2.3 — the live check distinguishes an empty day from a missing integration

`scripts/inspect_discovery_integration.py` takes discovery's stored postings as the input set and
reconciles **every identity** to a disposition in the actual report schema: retained, excluded (with
the rule that fired), absorbed as a duplicate (traced through the survivor's provenance),
consumed-unlisted (below fit), pending publication, or NOT CONSUMED.

It was exercised on reports produced by the **real** enumerate, collector, discovery, differ and
report stages (`evidence/p08_exercise_live_check.py`, `evidence/p08_live_check_exercise.txt`, with
each case's full output and fixtures under `evidence/live_check_fixtures/`):

| Control | Situation | Verdict |
|---|---|---|
| A | a registry-absent employer's fitting role is retained | `ACCEPTANCE_MET` |
| B | a genuine zero-fit discovery day (posting consumed, policy-excluded) | `INTEGRATION_OK` |
| C | the consumer connection removed, on inputs identical to A | `MISSING_INGESTION` |
| D | an interrupted publication, nothing published yet | `PENDING_PUBLICATION` |
| E | a retained posting whose employer **is** in the registry | `INTEGRATION_OK`, open-market condition not met |

B and C are the pair that matters: both produce a morning report with no discovered candidate, and
P07's proposed check could not tell them apart. E is the control for the other defect the review
named — a discovery source id differs from every ATS source id by construction, so the check
reconciles **employer identity** against `config/companies.yaml` instead. An employer whose identity
cannot be established is labelled `UNKNOWN-REVIEW-NEEDED` and never counted toward acceptance.

The script reads local files only and makes no AWS call; fetching its inputs is a separate explicitly
read-only step in the handoff.

---

## 5. Full local verification

| Check | Result | Evidence |
|---|---|---|
| full test suite | **350 passed** (339 pre-existing + 11 new) | `evidence/p08_test_results.txt` |
| unmodified reviewer probe, before repair | interruption reproduced | `evidence/p08_before_repair_interrupted_publish.json` |
| unmodified reviewer probe, after repair | interrupted arm matches the control exactly | `evidence/p08_after_repair_interrupted_publish.json` |
| candidate policy projection | matches all policy sources | `evidence/p08_policy_check.txt` |
| `sam validate --lint` | valid SAM template | `evidence/p08_sam_validate.txt` |
| `sam build` with explicit template | all six functions built | `evidence/p08_sam_build.txt` |
| package change set | `CHANGE_SET_IS_CODE_ONLY` | `evidence/p08_package_scope.txt` |
| rollback baseline | `BASELINE_VERIFIED`, 36/36 in 6/6 functions | `evidence/p08_rollback_baseline_verification.txt` |
| rollback recovery drill | `DRILL_PASSED`, reversible | `evidence/p08_rollback_drill.txt` |
| live acceptance check | `LIVE_CHECK_DISCRIMINATES`, 5/5 controls | `evidence/p08_live_check_exercise.txt` |

The `sam validate`/`sam build` logs each contain a `PermissionError` writing
`~/.aws-sam/metadata.json`. That is SAM's own telemetry file, blocked by the local sandbox; both
commands exited 0 and P07's evidence shows the same line.

---

## 6. Limits of this run

- **Everything is local and mocked.** Mocked S3 grants all access, so IAM is established only as
  *declared* grants read from the real template, never as a runtime policy evaluation.
- **No live feed was contacted** and no production object was read or written.
- **The live acceptance condition is not met by this run and must not be reported as met.** It
  requires a real registry-absent posting in a delivered report after an approved deployment.
- **The retention bound (21 days) and the owed-batch bound (5) are stated, not calibrated.** Neither
  has been measured against real feed churn or real failure frequency.
- **A dropped owed batch is not automatically recoverable.** The receipt points at `raw/` and a
  manual replay; that path is not exercised.
- **The unattended round on 2026-09-26 remains unverified** and is unaffected by this run, which
  deployed nothing.
