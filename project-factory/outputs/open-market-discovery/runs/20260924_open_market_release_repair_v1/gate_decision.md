# GATE DECISION — 20260924_open_market_release_repair_v1

**Outcome: `unlock`** — the four reproduced release defects are closed locally. The next step is an
operator decision: deploy, or obtain an independent review of the repaired screening first.

## Evidence

- All four findings reproduced independently before repair; 23 of 41 new tests failing at that point.
- After repair: **209 passed**, `sam validate` clean, `sam build` succeeded, policy projection matches
  all five sources.
- R2 verified against the live provider: Himalayas 20 -> **96 postings / 74 employers** across a real
  5-page cursor walk, with the remaining position saved and coverage honestly PARTIAL.
- R3 verified by a 364-posting audit on identical bytes: 34 dispositions changed, and only **2** of
  those reach the candidate list after scoring. The distinction between "wrong exclusion released"
  and "new opportunity" is measured, not asserted.
- R4 verified against the AWS CLI with no AWS operation, and the cost bounded from AWS's Price List
  API rather than a free-tier assumption.

## Risks carried forward

| Risk | Severity | Mitigation |
|---|---|---|
| Adzuna has never run authenticated, so general-industry coverage is still unproven | high for the objective | named in the report and the handoff; the credential enables the attempt, not the conclusion |
| Screening rules were repaired and self-reviewed by the same context | medium-high | disclosed; a misfire silently discards an opportunity, and the review that found yesterday's defects is the argument for getting one here |
| `fetch_raw` unverified for 3 of 4 feeds outside the sandbox | medium | post-deploy check 1 |
| Source growth proposes rows but does not monitor | low, by design | stated as three distinct things in the handoff |
| Lambda packaging ships the whole repository | low | pre-existing; no demonstrated security or runtime defect |

## Why not `stop`

Every defect the review demonstrated is closed with a failing-then-passing test and, where a provider
was involved, live evidence. Nothing was labelled passed to obtain closure.

## Why not `revise_stage`

No acceptance row failed. The one gap discovered during the work — invisible below-threshold
postings — was repaired in-run rather than deferred.

## Stop condition honored

`stage_complete` for local repair readiness with remaining activation requirements explicit. No
deployment, no AWS mutation, no commit. The Adzuna live gate is recorded as unpassed, not passed.
