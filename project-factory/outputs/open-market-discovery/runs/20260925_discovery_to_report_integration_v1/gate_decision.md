# gate_decision — P07 discovery-to-report integration

Stage: `implementation_and_local_verification`
Packet: `JPRS-L2-P07-discovery-to-report-integration-v01`
Run: `20260925_discovery_to_report_integration_v1` · Date: 2026-09-25

## Outcome

**`unlock` — for controlled deployment REVIEW only.**

This unlocks the orchestrator's inspection of the integration evidence and a deployment decision. It
does **not** record deployed functionality, does not authorize a deploy, and does not claim the live
acceptance condition. Deployment requires fresh explicit operator approval; P06's is spent on P06.

## Outputs reviewed

- `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`, `checkpoint.md`, `run_manifest.json`
- `evidence/p07_before_repair_p06_probe.json`, `evidence/p07_after_repair_p06_probe.json`
- `evidence/p07_stage_trace.json`, `evidence/p07_sample_report.md`
- `evidence/p07_test_results.txt`, `p07_policy_check.txt`, `p07_sam_validate.txt`, `p07_sam_build.txt`
- `evidence/p07_owned_changes.txt`, `evidence/p07_baseline_working_tree.txt`
- `src/discovery/live.py`, the `src/report/handler.py` merge, `tests/test_discovery_to_report_integration.py`

## Acceptance criteria, item by item

| Packet acceptance requirement | Met | Evidence |
|---|---|---|
| A registry-absent useful job in the saved ordinary report | yes | reviewer's own probe: 0 → 1 candidate row; `p07_sample_report.md` shows it leading the report |
| Produced by the real producers and consumers | yes | harness drives real enumerate/collector/discovery/differ/report; structural no-test-bridge assertion |
| Existing screening, ranking and history engaged | yes | row carries `screen ELIGIBLE`, fit/priority bands, `history NEW`; exclusion case attributes `sales-ownership` |
| Matching negative checks | yes | exclusion case, cold-start case, and the disabled-consumer regression |
| Multi-round checks | yes | identity-across-pages, failed round, churn absence, late discovery, old→new format transition |
| Declared invocation and permissions verified | yes | three tests read the real `template.yaml` and `.asl.json`; both positive and negative grants asserted |
| No test-only bridge | yes | harness writes no manifest/expected_sources/normalized/current/screening/scorecard/ReportInput; prefix census asserted |
| Monitored functionality intact | yes | monitored candidate present in every discovery assertion; 316 pre-existing tests still pass |
| Build-bound, data-compatible, approval-gated handoff | yes | `DEPLOYMENT_HANDOFF.md` §4–§6 |

## Scoring (QUALITY_GATES rubric, 0–5)

| Dimension | Score | Note |
|---|---|---|
| `coherence` | 4.5 | one ownership decision carried consistently through producer, store, consumer and tests |
| `force_impact` | 4.5 | the product goal is visibly met: an unregistered employer leads the morning report with a link and a reason |
| `readability_usability` | 4 | the rendered report is readable without chat context; the handoff is executable as written |
| `support_provenance` | 4.5 | before/after on the reviewer's own probe; captures vs synthetic controls labeled separately; limits enumerated |
| `gimmick_overfit_risk` (reverse) | 1 | no new infrastructure, no new abstraction layer; one new module and one merge point |

Weighted average ≈ **4.4**, no critical failure → `unlock` under the default guidance.

## Key evidence and support quality

**Strongest.** The before/after pair uses the P06 reviewer's script unmodified, with identical
external inputs. That removes the failure mode the review actually caught — a harness proving report
behavior given a connection that did not exist. The new harness additionally asserts *structurally*
that no intermediate artifact is test-authored, rather than relying on my word for it.

**Weakest, and named.** Everything is local and mocked. Mocked S3 grants all access, so IAM is
established only as *declared* grants in the template, not as a runtime policy evaluation. No live
feed was contacted. The retention bound is uncalibrated.

## Top risks

1. **Live acceptance is unproven.** A zero-discovery-candidate day is legitimate; the handoff gives
   the three checks that separate a thin day from a broken integration, and requires recording a
   zero honestly rather than re-running until a favorable sample appears.
2. **Discovery id shape changes.** Cursor-bound ids in existing `normalized/` objects are not read
   by anything, and no `current/`/`events/` record has ever held a discovery id, so the blast radius
   is the live view's own first-observation stamps on the first post-deploy run.
3. **The report Lambda's new import of `src.discovery.live` survives only because packaging ships
   the whole repository.** Recorded as open item 4 in the handoff so a packaging fix cannot break it
   silently.

## Recommended next action

Orchestrator inspects this run's integration evidence and returns with a deployment decision. Do not
open another committee, deploy, wait for tomorrow, or commit as part of this gate.
