# GATE DECISION — 20260924_runtime_boundary_and_fresh_first_v1

**Outcome: `unlock`** — R1, R3, R4 and the fresh-first item are closed locally. Next step is an
operator decision: deploy, or obtain the independent review that two consecutive review rounds now
argue for.

## Evidence

- The review's own probe, run unmodified before and after, shows all six observations moving from
  defective to repaired except the rollback reader, which measures raw record compatibility that no
  repair can change (the downgrade step is proven separately).
- 22 of 38 new tests failed before repair; **252 pass** after (43 added in total). SAM validates and builds; policy
  projection matches all five sources.
- R1 is verified at `urllib.request.urlopen` with `_live_fetcher` and the connector wiring intact —
  the specific failure mode of the P02 test is designed out.
- R4 is verified by a full forward-run -> downgrade -> baseline-read -> restart cycle on mocked AWS,
  with DISAPPEARED=0 and a preserved backup, including a job absent on the following run.
- F1 rests on a measured source contract (descending cursor), not an assumption, and the cold-start
  correction was made because the first rehearsal produced an obviously false 44-of-44 freshness
  claim.

## Risks carried forward

| Risk | Severity | Mitigation |
|---|---|---|
| Adzuna has still never run authenticated | high for the objective | boundary proven; named as an open gate in the handoff and the report |
| No independent review of this repair | high | disclosed; the review's own probe re-run as a fresh boundary check; a third review is the recommended next step |
| `fetch_raw` unverified outside the sandbox for 3 of 4 feeds | medium | post-deploy check |
| Rollback downgrade unexercised against real state | medium | dry run by default, double confirmation to apply, backup taken first |
| Sub-24h capture not achievable | low, stated | achievable latency documented; optional second pass offered, not taken |

## Why not `stop`

Every blocker was reproduced independently, repaired at the root, and re-verified with the
reviewer's own instrument rather than only with tests I wrote.

## Why not `revise_stage`

No acceptance row failed. Three defects found during the work — the cold-start freshness inflation, my
own mis-specified exclusion-delta comparison, and a test helper that hardcoded a remote location so
location fixtures passed for the wrong reason — were corrected in-run and documented as corrections
rather than quietly fixed.

## One item beyond the packet's rows, flagged rather than buried

A new operator-confirmed "Location and Compensation" section appeared mid-run and my screener
contradicted it (Portsmouth and Boston were treated as commutable). I aligned it, added five tests,
and added no compensation gate. The town list implementing "approximately a 30-minute drive from
Laconia" is my interpretation and wants a reviewer's confirmation; see VALIDATION §7a.

## Stop condition honored

`stage_complete` for local repair and fresh-first readiness. No deployment, no AWS mutation, no
credential provisioning, no commit. Unpassed gates are named, not marked passed to obtain closure.
