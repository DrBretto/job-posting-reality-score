# Current candidate policy alignment and controlled radar release (P10)

Packet: `project-factory/claude_handoff/packets/jprs/JPRS-L2-P10-policy-alignment-and-controlled-release-v01.md`
Run: `project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/`

## Context

`policy-check` is RED. Two central sources changed after the committed projection was built:

| source | recorded bytes | current bytes | changed |
| --- | --- | --- | --- |
| `APPLICATION_WORKFLOW.md` | 15,659 | 21,249 | yes |
| `OPERATING_PLAN.md` | 5,359 | 5,757 | yes |
| `SEARCH_PREFERENCES.md` | 4,108 | 4,108 | no |
| `CANDIDATE_FACTS.md` | 1,462 | 1,462 | no |
| `MASTER_RESUME.latest.md` | 13,484 | 13,484 | no |

Reading the current sources, the September 26 additions are three, and only one of them is a
**screening** change:

1. **Screening (in scope):** `APPLICATION_WORKFLOW.md` → *Adjacent roles: software problem-solving,
   not customer service*, plus the `Screen Before Preparing` line "Reject call-center and external
   customer-service/phone-support jobs". There is **no** call-center/customer-service rule anywhere
   in `src/` today (verified by search), so this is genuinely absent behavior, not a stale hash.
2. **Application process (out of scope for screening):** the *Tailoring* core-resume reuse
   allowance. A permission about how materials are produced, not a new job exclusion.
3. **Application process (out of scope for screening):** *Backlog Catch-up and Automated Submission
   Pilot*. Queued follow-up work; explicitly not permission to submit anything in this packet.
   `OPERATING_PLAN.md`'s delta is its pointers to (2) and (3).

So refreshing the projection alone would record the new hashes while screening kept behaving as if
the clarification had not been written. The projection stores hashes and a static rule→source map;
it implements nothing.

## Plan

1. [x] Reproduce `policy-check` RED; record per-source hash delta as evidence.
2. [x] Capture the **before** per-posting disposition audit over the captured posting corpus
       (2026-09-24 slice: 4 Himalayas cursor pages + Jobicy + RemoteOK + Remotive) through the real
       `run_discovery` → `_assemble_local_report` path.
3. [x] Implement the smallest tested screening change: a `customer-service-queue` rule in
       `src/candidate/screening.py` that reads duty evidence, with guards for internal software
       ownership, software built FOR a support org, and ordinary meetings/stakeholder work.
       Ambiguous support titles route to PENDING_CHECK, never to an invented exclusion.
4. [x] Bump `SCREENING_RULESET_VERSION`, add the rule to `RULE_SOURCE_MAP`, refresh the projection
       from current sources (`policy-refresh`).
5. [x] Add regressions (new file `tests/test_adjacent_roles_and_customer_service.py`); demonstrate the new ones fail against pre-P10
       behavior.
6. [x] Capture the **after** audit; diff dispositions by job id; inspect every change; fix
       unsupported losses.
7. [x] Bounded fresh reviewer on the policy meaning + the actual caller path; resolve findings.
8. [x] Full suite, `policy-check`, SAM validate/build, P06 baseline reconstruction, change-set gate,
       release preflight.
9. [x] Run outputs: `OPERATOR_RETURN.md`, `DEPLOYMENT_HANDOFF.md`, `VALIDATION.md`,
       `run_manifest.json`, `checkpoint.md`, `gate_decision.md`, machine-readable evidence.
10. [ ] Deployment + one controlled live round — **requires fresh explicit operator authorization**.
        Absent it, stop release-ready.

## Execution Log

- Read the native rules, factory bootstrap, shared contracts, the P09 run (return, validation,
  failure matrix, gate, handoff) and the four current central sources before editing anything.
- `policy-check` exit 1, `changed since the projection was built: operating_plan, workflow` —
  reproduced before any edit (`evidence/p10_policy_check_before.txt`). Confirmed by search that no
  call-center / customer-service / phone-support / help-desk handling existed anywhere in `src/`.
- Before audit: 282 postings considered, 11 retained, 112 policy-excluded, 159 below fit
  (`evidence/p10_dispositions_before.json`). The corpus holds twelve support-shaped titles; three
  were reaching the report with no customer-service reason recorded (Resource Guru, Warehance, Unio
  Digital) and one is a genuine look-alike that must stay unexcluded (Wing's flight-operations
  support manager, whose duties contain no support queue).
- Implemented `customer-service-queue` (ruleset 1.4.0 → 1.5.0) with its guards; added regressions;
  refreshed the projection; ran the after audit.
- **The audit found three misfires in my own first implementation**, all repaired and pinned: an AI
  engineering role read as working a help desk (the software noun sat behind adjectives, defeating
  the guard); "translating and creating Help Desk content" read as answering the help desk; and a
  consultant posting's "every phone call you answer" motivational prose read as a queue. A fourth
  case had the right verdict but cited the documentation sentence instead of the real queue duty.
- **Bounded independent review (fresh context, read-only) returned `revise` with three material
  findings**, two in opposite directions. All reproduced locally before repair:
  - **M1** — `help desk` / `service desk` / `support tickets` were treated as self-evidently
    EXTERNAL channels, so internal IT/DevOps roles managing an internal service desk queue were
    **hard excluded** — in some cases with evidence text containing the word "internal" under a
    reason asserting "external". That is the population the clarification was written to open up.
    Repaired: those channels are queue-*shaped* only, the internal-audience pattern is broad, and it
    is still checked first.
  - **M2** — a call-center or customer-service TITLE was cleared to `ELIGIBLE` by any software verb
    anywhere in the description (description scope, the exact mistake the sales rule had already
    learned). A posting titled "Call Center Representative" answering customer phone enquiries came
    back eligible. Repaired: no title branch returns ELIGIBLE on keyword evidence; a call-centre
    title is unconditional; otherwise PENDING_CHECK.
  - **M3** — missing channel phrasings (`telephone enquiries`, `first-line assistance`, `questions
    from customers by phone`, …) plus audience lost across an `and` coordinator, producing one
    silent full pass. Repaired: channel coverage extended, and **audience is now read at clause
    scope while guards stay duty-span scoped** — an asymmetry that is itself tested.
  - Also repaired: `location-residency` was missing from `RULE_SOURCE_MAP` (pre-existing).
  - Accepted as limitations rather than repaired, and recorded: PENDING_CHECK is invisible in the
    readable report for below-fit postings; the captured corpus exercises none of the rule's third
    state; one theoretical render path was never reproduced.
- All build, baseline and release checks re-run AFTER those repairs: 433 tests pass, 22 of the 40 new
  tests fail against the reversed-edit pre-P10 tree, `sam validate`/`sam build` clean,
  `BASELINE_VERIFIED` 36/36, preflight PASSED `CHANGE_SET_IS_CODE_ONLY` 6/6, rollback preflight exit
  0 with the working tree's `src/` fingerprint byte-identical.
- Final corpus delta: 5 newly excluded, 6 reasons/states changed, retained set identical by job id.
- Stopped at local release readiness. No deployment authorization was given, so nothing was deployed.

## Follow-ups

- Deployment and the controlled live round remain unauthorized as of this run.
- The batch bound (5) and retention horizon (21 days) carried forward from P08/P09 are still not
  calibrated against measured data.
- `src/.DS_Store` is packaged into the Lambda artifacts (packaging hygiene, noted by P09, still
  true, out of scope here).
