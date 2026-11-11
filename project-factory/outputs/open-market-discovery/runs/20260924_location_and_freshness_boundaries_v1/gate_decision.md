# gate_decision — JPRS-L2-P04-location-and-freshness-boundaries-v01

Run: `20260924_location_and_freshness_boundaries_v1` · 2026-09-24

## Decision

**Execution acceptance: MET.** All three of the P03 review's open blockers are repaired at the
boundaries where they actually failed, each reproduced against the reviewer's own unmodified probe
before any code changed. 296 tests pass, the SAM template validates and builds, the policy projection
matches all five sources, and a two-round rehearsal over real captured provider payloads shows the
repaired behavior reaching the persisted report.

**Release acceptance: not mine to give.** Deployment is an operator decision and nothing was deployed.

## Against the packet's four acceptance areas

| Area | Verdict | Evidence |
|---|---|---|
| 1. Implement the meaning of the location policy | met | `VALIDATION.md` §2; `evidence/p04_before_repair_probe.json` → `p04_after_repair_probe.json`; 20 regressions |
| 2. Connect freshness to the real report execution | met | §3; `evidence/p04_report_boundary_results.json` — real handler, persisted artifact, no test-supplied timing; 13 regressions |
| 3. Preserve recent arrivals beyond the first feed page | met | §4; same probe, page two now fetched with the backfill still advancing; 10 regressions |
| 4. Reconcile and verify | met | §5–§8; new handoff, corrected contradiction, verified evidence paths, synchronized surfaces, counts restated with populations |

## Two things carried beyond the rows, flagged rather than buried

1. **Two defects the review did not name, found while repairing R2.** The local CLI report path
   shared the unwired-timing defect, and cold-start detection misread a warm single-posting source.
   Both are fixed. I am naming them because "296 tests pass" would otherwise read as though the
   reviewed list was the whole list — for the fourth round running, it was not.

2. **One design decision that is genuinely arguable, and belongs to the operator.** The policy states
   a drive duration. This system cannot measure one, so it now resolves only what it can check and
   routes every in-state distance question to worksite confirmation. A New Hampshire onsite role
   therefore arrives as a question rather than a yes or a no. The packet asked for exactly this; it
   still means more review rows, and the alternative — a named auto-approve list — would be me
   certifying a distance I have not measured. Stated in the handoff §10 for a decision.

## My recommendation

Three consecutive reviews each found real defects the implementing context had missed, twice inside
its own tests. That pattern did not break this round: this run found two more defects of exactly that
shape on its own, and a third — the abandoned head continuation — only because a test it had just
written failed. **A fourth review is the cheaper error.** But the argument is weaker than last time:
the defects now being found are ones this context surfaced itself, and the remaining risk has shifted
from correctness to the two things no local run can settle — production transport and authenticated
Adzuna, both of which only deployment answers.

Either path is defensible. What is not defensible is deploying while treating the open gates in
`DEPLOYMENT_HANDOFF.md` §9 as closed.

## Stop condition

Reached. Stopped at locally verified repairs and a coherent release handoff. No deployment, real
credential, cloud mutation, email, application, commit, branch, staging, reset or push.
