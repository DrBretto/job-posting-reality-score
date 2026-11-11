# gate_decision — P10 current candidate policy and controlled release

Stage: implementation, independent review and local release verification.
Packet: `JPRS-L2-P10-policy-alignment-and-controlled-release-v01`.
Run: `20260926_policy_alignment_and_controlled_release_v1`, executed 2026-09-26.

**Recommended outcome: `unlock`** — for the LOCAL stage only. It is a release-readiness statement and
**confers no deployment authorization**. Deployment acceptance is a separate condition that this run
did not meet and did not seek.

## Outputs reviewed

`OPERATOR_RETURN.md`, `VALIDATION.md`, `INDEPENDENT_REVIEW.md`, `DEPLOYMENT_HANDOFF.md`,
`checkpoint.md`, the 16 files in `evidence/`, the three scripts in `scripts/`, and the source and test
changes they measure.

## The packet's local acceptance conditions

| # | condition | result |
| --- | --- | --- |
| 1 | policy meaning implemented, not only rehashed | **met** — the delta's one screening addition is a new `customer-service-queue` rule reading duty evidence; there was NO call-center/customer-service/help-desk handling anywhere in `src/` beforehand, independently confirmed against a reconstructed pre-change tree. Screening changes are separated from the two application-process additions, which are named and deliberately not implemented (`evidence/p10_policy_source_delta.json`) |
| 2 | current projection | **met** — `policy-check` exit 0; projection rebuilt to `1.1.0` from all five current sources with 9 mapped rules, and hashed inside all six function artifacts (`evidence/p10_policy_check_after.txt`, `p10_release_identity.json`) |
| 3 | disposition-delta audit over the same captured postings, before and after, with every changed disposition named | **met** — 282 postings through the real caller path; 11 changed verdicts by job id with reasons; retained set byte-identical; every new exclusion inspected and three misfires found and repaired in-run (`evidence/p10_dispositions_{before,after}.json`, `p10_disposition_delta.json`) |
| 4 | bounded fresh reviewer on the policy meaning and the actual caller path, material findings resolved and rechecked | **met, and it mattered** — verdict `revise` with three material findings, two in opposite directions: internal help-desk ownership hard-excluded, and a call-center title cleared to ELIGIBLE. All repaired, rechecked against the reviewer's own 19 cases, and pinned by 9 added regressions (`INDEPENDENT_REVIEW.md`) |
| 5 | passing regressions, full suite, build and release preflight; verified baseline | **met** — 433 passed; 22 of 40 new tests fail against the reversed-edit scratch tree; `sam validate`/`sam build` exit 0; `BASELINE_VERIFIED` 36/36 then `BASELINE_BUILD_READY`; preflight PASSED with `CHANGE_SET_IS_CODE_ONLY` across 6/6 artifacts; rollback preflight exit 0 leaving the working tree byte-identical. **All re-run after the review repairs** |
| 6 | preserved P09 coverage; no gate lowered or bypassed | **met** — publication boundary matrix (18), owed-debt compaction (13), negative release controls (23), integration (23), original screening (24), recall/coverage incl. salary flexibility and Staff-title handling (24), location/freshness (44), all passing (`evidence/p10_preserved_coverage.txt`) |
| 7 | self-contained release handoff | **met** — `DEPLOYMENT_HANDOFF.md`, with fresh reconstruction paths, the code-only evidence, the projection-shipping claim labeled separately, and the live-round sequence |

## Deployment acceptance

**NOT MET, and not sought.** No fresh authorization existed at any point in this run. No deploy, AWS
call, change-set execution, invocation, email, application or git mutation occurred. The positive live
condition — a real registry-absent employer's qualified role in a report actually delivered — is
unmet and unclaimed. Local completion does not imply live acceptance.

## Scoring

| dimension | score | note |
| --- | --- | --- |
| coherence | 4.5 | one rule, one hinge (whose contacts these are), three outcomes used deliberately; the audience/guard scope asymmetry is stated and tested |
| force_impact | 4.5 | the change removes phone-queue work from the report without touching a single retained candidate, and the review caught the inverse defect that would have cost the adjacent roles the clarification exists to open up |
| readability_usability | 4 | every guard is traceable to a sentence in the policy document; the operator-facing exclusion reason carries its duty text |
| support_provenance | 4.5 | before/after by job id on real captured postings, pre-change discrimination measured rather than asserted, and the review's own cases preserved as regressions |
| gimmick_overfit_risk (reverse) | 1.5 | the rule is a sizeable regex family and three of its patterns were tuned in response to specific corpus misfires; each tuning is pinned by a test, but the family is large and the corpus never exercised its third state |

Weighted average ≈ 4.4.

## Top risks

1. **The third state is unexercised by real data.** The captured corpus yields 0 pending checks for
   the new rule and contains none of the phrasings behind the review's largest finding. That half of
   the rule rests on the regression suite and the reviewer's probes, not on observed postings. The
   first live rounds are where it gets tested.
2. **PENDING_CHECK plus a below-fit score is invisible in the readable report.** Pre-existing report
   architecture, but the new rule's population skews low-fit. Accepted as a limitation and recorded
   rather than repaired; fixing it needs report ranking changes outside this write surface.
3. **Nothing was deployed or inspected in AWS.** No change set, invocation, transport check or
   delivery. The 2026-09-26 unattended round remains a P06 observation and was not checked.
4. **The reconstructed baseline is not byte-identical to the deployed P06 artifact outside `src/`**,
   so the projection's shipping is evidenced by artifact hashes rather than by the package diff. A
   reviewer should confirm that classification rather than take it.
5. One theoretical report-render path (entity-encoded title carrying a banned token) was reasoned
   from code and never reproduced; recorded as unverified.

## Recommended next action

Seek **fresh explicit operator authorization** for this repaired radar's deployment and one controlled
ordinary live round. Not another committee, and not another broad review by default. If authorization
is withheld, the work is complete and stops here at release readiness.
