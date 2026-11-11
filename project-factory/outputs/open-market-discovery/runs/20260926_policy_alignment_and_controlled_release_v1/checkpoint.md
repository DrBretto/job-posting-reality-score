# checkpoint — P10 current candidate policy and controlled release

Run: `20260926_policy_alignment_and_controlled_release_v1`
Packet: `JPRS-L2-P10-policy-alignment-and-controlled-release-v01`
Status: `completed` locally. **Local only** — nothing deployed, invoked, committed, staged or pushed,
and AWS was not contacted.

## What moved

- The RED `policy-check` that halted P09's release sequence is resolved by implementing behavior, not
  by refreshing a hash. The source delta's one screening addition — the 2026-09-26 *Adjacent roles:
  software problem-solving, not customer service* clarification — is now a screening rule
  (`customer-service-queue`, ruleset 1.4.0 → 1.5.0). There was no call-center, customer-service,
  phone-support or help-desk handling anywhere in `src/` before this run.
- The two other 2026-09-26 additions (core-resume reuse; the backlog/submission-pilot direction) are
  application-process permissions, named and deliberately NOT implemented as screening or as
  submission authority.
- `config/candidate_policy.json` rebuilt from the five current sources: `1.1.0`, 9 mapped rules,
  packaged identically into all six function artifacts.
- Over the 282-posting captured corpus, through the real caller path: 5 roles newly excluded with duty
  evidence, 6 reasons made more honest, and the 11 retained candidates unchanged job id for job id.
- A bounded independent reviewer returned `revise` with three material findings — internal help-desk
  ownership hard-excluded, a call-center title cleared to ELIGIBLE, and missed external-support
  phrasings including one silent pass. All repaired, rechecked against the reviewer's own cases, and
  pinned by 9 added regressions. One pre-existing gap (`location-residency` missing from the rule map)
  also repaired.
- Every build, baseline and release check was re-run **after** those repairs: 433 tests, `sam validate`
  and `sam build` clean, `BASELINE_VERIFIED` 36/36, preflight PASSED with `CHANGE_SET_IS_CODE_ONLY`
  across 6/6 artifacts, rollback preflight exit 0 with the working tree byte-identical.

## What is blocked or uncertain

- **Blocked on one thing: a fresh explicit operator authorization** covering this repaired radar's
  deployment and one controlled ordinary live round. P06's approval is spent and no file in this run
  grants a new one. This is the entire remaining boundary.
- Uncertain, and stated rather than papered over: the captured corpus produced **0 pending checks**
  for the new rule and contains none of the phrasings behind the review's largest finding, so the
  rule's third state has no real-data evidence yet.
- Accepted limitation, not repaired: a posting that is PENDING_CHECK **and** below the fit band
  reaches no readable report section — only an id in `below_fit_threshold_job_ids`. Repairing it needs
  report-ranking changes outside this packet's write surface.
- Unverified and not dismissed: one theoretical report-render path flagged in review (entity-encoded
  title carrying a banned token), reasoned from code, never reproduced.
- Carried forward unchanged: the live positive product condition is unmet; the 2026-09-26 unattended
  round (07:05) was not checked and remains a P06 observation; Adzuna credentials, the careers-URL
  resolver, Lambda packaging, and the retention/compaction bounds are still open operator items.

## What is next

**One next unlocked task:** obtain fresh explicit authorization, then perform the verified code-only
release and one ordinary live round exactly as `DEPLOYMENT_HANDOFF.md` §4 and §4.1 describe. Without
that authorization the work is complete and stops here.

After the ordinary live path is verified, the next work is the operator's existing queued sequence in
`APPLICATION_WORKFLOW.md` → **Backlog Catch-up and Automated Submission Pilot**. No part of it is
implemented here.

## Artifacts emitted or updated

| path | status |
| --- | --- |
| `src/candidate/screening.py` | modified — new rule, ruleset 1.5.0 |
| `src/candidate/policy.py` | modified — rule map + `location-residency`, projection 1.1.0 |
| `config/candidate_policy.json` | regenerated from current sources |
| `tests/test_adjacent_roles_and_customer_service.py` | new, 40 regressions |
| `…/20260926_policy_alignment_and_controlled_release_v1/OPERATOR_RETURN.md` | complete |
| `…/VALIDATION.md` | complete |
| `…/INDEPENDENT_REVIEW.md` | complete |
| `…/DEPLOYMENT_HANDOFF.md` | complete, self-contained |
| `…/gate_decision.md` | `unlock`, local stage only |
| `…/run_manifest.json` | complete |
| `…/checkpoint.md` | this file |
| `…/scripts/p10_disposition_audit.py` | reusable |
| `…/scripts/p10_disposition_delta.py` | reusable |
| `…/scripts/p10_reverse_edits_to_scratch.py` | reusable |
| `…/evidence/` | 16 files |
| `docs/plans/2026-09-26-policy-alignment-and-controlled-release.md` | plan doc, execution log current |
| `START_HERE.md`, `project-factory/ORCHESTRATOR_BOOTSTRAP.md`, `project-factory/meta/*`, `PACKET_REGISTRY.tsv` | pointers updated to this run |

All historical runs, packets and evidence are intact. No central Infotropy file, `AGENTS.md`,
`CLAUDE.md`, shared contract, resume or personal-answer profile was written.

## Resume steps

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
git status                      # read-only; expect the uncommitted P01–P10 overhaul
.venv/bin/python -m src.cli policy-check          # expect exit 0
.venv/bin/pytest -q -p no:cacheprovider           # expect 433 passed
```

Then read this run's `OPERATOR_RETURN.md`, and `DEPLOYMENT_HANDOFF.md` §4 if authorization has since
been given. To re-derive the policy consequences from scratch:

```bash
RUN=project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1
.venv/bin/python "$RUN/scripts/p10_disposition_audit.py" --out "$TMPDIR/after.json"
.venv/bin/python "$RUN/scripts/p10_disposition_delta.py" \
  --before "$RUN/evidence/p10_dispositions_before.json" --after "$TMPDIR/after.json" \
  --out "$TMPDIR/delta.json"
```
