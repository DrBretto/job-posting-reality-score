# gate_decision — P09 publication commit boundary and verification

Stage: implementation and adversarial local verification.
Packet: `JPRS-L2-P09-publication-commit-boundary-and-verification-v01`.
Run: `20260925_publication_commit_boundary_and_verification_v1`, executed 2026-09-26.

**Recommended outcome: `unlock`** — ready for orchestrator review only. It is not a deployment
recommendation and confers no deployment authorization.

## Outputs reviewed

`VALIDATION.md`, `FAILURE_MATRIX.md`, `DEPLOYMENT_HANDOFF.md`, `checkpoint.md`, the 16 files
in `evidence/`, the three reusable scripts in `scripts/`, and the source and test changes they
measure.

## The packet's five acceptance conditions

| # | condition | result |
| --- | --- | --- |
| 1 | the unchanged pending-boundary probe is repaired AND P07's live-write probe still passes; across the fault matrix, accepted jobs are published or replayably owed, including beyond the old batch cap; no test-authored intermediate wiring | **met** — `evidence/p09_{before,after}_pending_boundary_probe.json`, `evidence/p09_after_p07_live_write_probe.json`, `evidence/p09_publication_boundary_matrix.json` (16 boundaries), compaction cases in `tests/test_durable_discovery_publication.py`. `test_no_intermediate_record_in_these_cases_is_written_by_this_test` still holds |
| 2 | negative release controls fail for semantic infrastructure differences, unavailable baseline and corrupt restore input; legitimate code-only builds and scratch restore/return pass | **met** — 19 controls in `evidence/p09_release_gate_controls.json`, 23 regressions in `tests/test_release_gates_reject.py` |
| 3 | the mixed same-employer case is not invented as below-fit; dispositions are backed by real per-ID consumer evidence; honest empty, pending, partial and complete states remain distinct | **met** — the report states `consumed_job_ids` and `below_fit_threshold_job_ids`; the mixed case now returns `RECONCILIATION_INCOMPLETE` / exit 1, and `EVIDENCE_UNAVAILABLE`, `INPUTS_NOT_COHERENT`, `PENDING_PUBLICATION` and `NO_INPUT` are separate verdicts |
| 4 | targeted tests, full suite, candidate-policy check, SAM validation/build and packaged module/template selection pass; new regressions fail against preserved pre-repair code in scratch without changing the working checkout | **met except the policy check**, which is RED for a reason outside this run — see below. 393 passed; `sam validate` and `sam build` exit 0; the change-set gate exits 0 `CHANGE_SET_IS_CODE_ONLY`; `evidence/p09_prerepair_regression_check.txt` shows the new regressions failing against the reversed-edit scratch tree, with the real checkout untouched |
| 5 | release commands are executable, fail closed and use the preserved baseline; no scope violation | **met** — `evidence/p09_preflight_drill.txt`, 7/7; the baseline is reconstructed from the persisted archive; `/private/tmp/claude-501/jprs-build-p06-9H8jKS` is referenced nowhere |

## Scoring

| dimension | score | note |
| --- | --- | --- |
| coherence | 4.5 | one acceptance point, stated once, enforced by ordering rather than by convention |
| force_impact | 4.5 | the reproduced loss is closed at the boundary, not at the probe's key; the checkers now refuse |
| readability_usability | 4 | two preflight scripts replace two command lists; the handoff is shorter and the logic is testable |
| support_provenance | 4.5 | before/after from the reviewer's own unmodified probes; every verdict re-derivable from three scripts |
| gimmick_overfit_risk (reverse) | 1.5 | the aggregate receipt is retained alongside the per-feed records — justified by the report and receipt reading one place and by settling debt the deployed code wrote, but it is a second object |

Weighted average ≈ 4.4.

## Top risks

1. **`policy-check` is RED.** Two operator-owned documents outside this repository were edited on
   2026-09-26 and the committed projection no longer matches them. No policy source, screening rule
   or projection was touched by this run; refreshing the projection is a candidate-policy decision
   the packet excludes. The preflight halts there by design. **Operator decision required before
   any deploy.**
2. **The reconstructed P06 baseline is not byte-identical to the deployed P06 artifact** outside
   `src/`, because `CodeUri: ../` packages the whole repository and only `src/` is restored from the
   archive. Those differences classify as repository payload, not infrastructure, and the
   change-set output says so. A reviewer should confirm that classification rather than take it.
3. **Nothing was deployed or inspected in AWS.** No change set, no invocation, no transport check.
   The positive product condition is unmet and unclaimed, and the 2026-09-26 unattended round is
   still a P06 observation.

## Recommended next action

Orchestrator review of this run. If it holds, seek **fresh deployment authorization** — not another
committee by default — after the operator resolves the policy-projection divergence.
