# gate_decision — P08 durable publication and release repair

Stage: `implementation_and_local_verification`
Packet: `JPRS-L2-P08-durable-discovery-publication-and-release-repair-v01`
Run: `20260925_durable_discovery_publication_release_repair_v1` · Date: 2026-09-25

## Outcome

**`unlock` — for deployment REVIEW only.**

This unlocks the orchestrator's inspection of the repair evidence and a fresh deployment decision. It
does **not** record deployed functionality, does **not** authorize a deploy, and does **not** claim
the live acceptance condition. P06's approval is spent on P06.

## Outputs reviewed

- `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`, `checkpoint.md`, `run_manifest.json`
- `evidence/p08_interrupted_publish_probe_unmodified.py` and its before/after JSON
- `evidence/p08_package_scope.{py,txt}`, `evidence/p08_verify_rollback_baseline.{py,txt}`
- `evidence/p08_rollback_drill.{sh,txt}`, `evidence/p06_baseline_src.tar.gz`
- `evidence/p08_exercise_live_check.py`, `evidence/p08_live_check_exercise.txt`,
  `evidence/live_check_fixtures/`
- `evidence/p08_test_results.txt`, `p08_policy_check.txt`, `p08_sam_validate.txt`,
  `p08_sam_build.txt`, `p08_owned_changes.txt`
- `evidence/p08_sample_report_{interrupted,recovered}_round.md`
- `src/discovery/live.py`, `src/discovery/handler.py`, `src/common/s3layout.py`,
  `src/report/handler.py`, `tests/test_durable_discovery_publication.py`,
  `scripts/inspect_discovery_integration.py`

## Acceptance criteria, item by item

| Packet acceptance requirement | Met | Evidence |
|---|---|---|
| the interruption reproduction is repaired | yes | the reviewer's unmodified probe: interrupted arm goes from 0 candidates on both the retry and the following report to matching the control exactly, with the feed returning nothing on both later fetches |
| through actual producer/consumer code, without test-authored wiring | yes | the repair is in `persist`/`merge_live_view`; `test_no_intermediate_record_in_these_cases_is_written_by_this_test` asserts it textually and by prefix census |
| focused retry regressions pass | yes | same-run retry and following-run cases, both with the job absent from the feed |
| focused partial-write regressions pass | yes | two-feed partial write: one committed and settled, the other untouched and owed; and the recovery round |
| the existing suite passes | yes | 350 passed — all 339 pre-existing, plus 11 new |
| actual package scope demonstrated | yes | `CHANGE_SET_IS_CODE_ONLY`; 6 of 6 artifacts change, 6 application-code paths, no IAM/schedule/parameter/state-machine/retention change, built templates byte-identical |
| a recoverable baseline demonstrated | yes | `BASELINE_VERIFIED` 36/36 in 6/6 functions against P06's own recorded hashes; archived in-repo; `DRILL_PASSED` both directions |
| the live inspection distinguishes empty eligibility from missing ingestion | yes | controls B and C give `INTEGRATION_OK` and `MISSING_INGESTION` on identical inputs |
| pending publication is visible to the operator | yes | coverage receipt, report JSON, discovery health axis `PARTIAL`, and a named line in `p08_sample_report_interrupted_round.md` |
| P07's working integration preserved | yes | P07's 339 tests unchanged and passing; `p08_sample_report_recovered_round.md` shows the registry-absent role leading the report |
| no deployment, cloud write, invocation or git mutation | yes | `run_manifest.json` budget caps all zero; branch and HEAD unchanged |

## Scoring (QUALITY_GATES rubric, 0–5)

| Dimension | Score | Note |
|---|---|---|
| `coherence` | 4.5 | one idea — observations are owed until published — carried through the ledger, the merge, the receipt and the report, with the ordering stated in `persist`'s own docstring |
| `force_impact` | 4.5 | the defect that silently deleted a real opportunity is closed, and two release claims that would have misled the operator at the worst moment are corrected with measurements |
| `readability_usability` | 4.5 | the corrected stop rule, the drilled rollback and the live check are executable as written; the rollback verification snippet was run to confirm it discriminates |
| `support_provenance` | 4.5 | before/after on the reviewer's own unmodified script; every release claim derived by a committed, re-runnable script rather than asserted; limits enumerated per artifact |
| `gimmick_overfit_risk` (reverse) | 1 | one new object at one known key, no new abstraction layer, no transaction framework, no infrastructure change; the IAM grants deliberately constrained the design |

Weighted average ≈ **4.4**, no critical failure → `unlock` under the default guidance.

## Key evidence and support quality

**Strongest.** The R1 before/after uses the reviewer's script byte-identically — `diff` reported no
difference before it was run — so the repair is measured by the instrument that found the defect,
not by a test written to pass. And the R2 claims are *derived* rather than asserted: the change set
comes from hashing two real builds, and the baseline from comparing a real build against a hash list
P06 recorded before any of this work existed. P07's handoff failed exactly by asserting both.

**Second strongest.** The live check was shown to give *different* answers to two situations that
produce identical-looking morning reports. A check that cannot fail on a broken system is not a check,
and this one was demonstrated failing on one.

**Weakest, and named.** Everything is local and mocked. Moto grants all access, so runtime IAM is
established only as declared grants in the real template. The design needs no new grant — which is
itself the mitigation — but no deployed policy evaluation was performed and no live feed was
contacted. The two bounds (5 owed batches, 21 days retention) are stated and reported, not calibrated.

## Top risks

1. **Live acceptance is still unproven.** No registry-absent job has appeared in a real delivered
   report. `scripts/inspect_discovery_integration.py` is the check to run after an approved deploy; a
   zero is legitimate and must be recorded with its evidence rather than re-run away.
2. **A rollback while a batch is owed loses those observations,** because P06 never drains the ledger.
   Bounded and stated: the receipt names the job ids, and `DEPLOYMENT_HANDOFF.md` §6.3 says to check
   it before rolling back.
3. **Packaging still ships the whole repository in every function.** That is why all six artifacts
   change and why the report Lambda can import `src.discovery.live` at all. Quantified here so a
   future packaging fix cannot break that dependency silently.

## Recommended next action

Orchestrator inspects this run's repairs and returns with a deployment decision. Do not open another
committee, deploy, wait for tomorrow, or commit as part of this gate.
