# CHECKPOINT — 20260924_runtime_boundary_and_fresh_first_v1

Status: **stage_complete (local repair + fresh-first readiness)**. No deployment occurred.

## What moved

1. Ran the review's own probe unmodified and reproduced all six observations
   (`evidence/review_probe_reproduction.txt`), then wrote 38 regression tests; **22 failed** before
   any repair (`evidence/tests_before_repair.txt`).
2. **R1** — `_live_fetcher` discarded the authenticated URL and let the unbound connector rebuild it
   from `os.environ`. `fetch_raw` now accepts the caller's URL; host validation and credential
   redaction preserved. Seven tests intercept at `urllib.request.urlopen` with the real wiring intact,
   including a handler-boundary test with mocked SSM. P02's test had replaced the broken function.
3. **R3** — `_find` returned only the first match, so a negation ended the search before a later
   mandatory requirement. Replaced with `collect_findings` + `mandatory()` aggregation,
   `duty_span_around` for per-duty artifact attribution, and per-family `artifact_excuses`.
   Optionality is now its own outcome. Ruleset 1.1.0 -> 1.2.0.
4. **R4** — the baseline rejects 18 job fields and 5 diff-state fields (`extra="forbid"`), so source
   rollback alone breaks the previous release. Added `src/common/rollback.py` plus
   `python -m src.cli downgrade-state` (dry run by default). Rehearsed end to end on mocked AWS:
   forward run -> baseline read fails -> backup + downgrade -> baseline reads -> restart with
   DISAPPEARED=0, including a job absent on the following run
   (`evidence/rollback_data_rehearsal.txt`).
5. **F1 fresh-first** — measured the Himalayas cursor as a descending timestamp
   (`evidence/himalayas_cursor_ordering.txt`), so a saved cursor walks away from new arrivals. Each
   run now checks the head first, then continues the backfill; at a 1-page budget the head wins and
   the starvation is reported. Added `age_label`, source lag/lookback tables, a "New since the last
   round" report section, and `cold_start_sources` after the first rehearsal wrongly called 44 of 44
   roles fresh. `_iso` now returns timezone-aware datetimes.
6. Reconciled counts and cohorts; corrected the cost arithmetic (off by ~20x); synchronized the live
   plan/bootstrap/status/registries.
7. **A late policy change that did affect screening.** `policy-check` fired again and the semantic
   comparison found a new operator-confirmed "Location and Compensation" section (2026-09-24) that my
   screener contradicted: it treated Portsmouth, Boston and all of MA/ME/VT as commutable, and spent
   Adzuna budget on a Boston scope, while the policy excludes Portsmouth and Boston commuting.
   Aligned minimally (Plymouth NH -> review; excluded metros -> excluded only for onsite/hybrid;
   Boston scope dropped; NO compensation gate added, since the targets are explicitly not gates).
   Ruleset 1.2.0 -> 1.3.0. This is beyond the packet's four rows and is flagged for the reviewer —
   the 30-minute town list is an interpretation of a stated drive time.

## Verification (`evidence/after_repair_verification.txt`)

```
pytest                                    252 passed   (209 before P03; 43 added)
tests/test_runtime_boundary_and_fresh_first  43 passed
sam validate --lint                       valid SAM Template
sam build                                 Build Succeeded
policy-check                              projection matches all policy sources
review probe, unmodified                  all six observations now show repaired behavior
```

Rehearsal `rehearsal/combined_fresh_first/`: 821 postings considered; Himalayas 96 postings / 74
employers; 216 discovery employers, none in the registry; 44 retained (4 fresh, 12 older-strong;
history 16 new / 21 needs-check / 7 previously engaged); 383 policy exclusions; 394 below threshold.

## Artifacts emitted

`run_manifest.json`, `checkpoint.md`, `gate_decision.md`, `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`,
`OPERATOR_RETURN.md`, `evidence/` (7 files), `rehearsal/combined_fresh_first/` (3 files).

P01 and P02 evidence left intact; both carry review banners rather than edited verdicts.

## Repository changes (uncommitted, branch `codex/real-job-radar`)

Modified: `src/common/connectors.py`, `src/common/normalize.py` (P02), `src/candidate/screening.py`,
`src/discovery/{handler,budget}.py`, `src/report/handler.py`, `src/cli.py`,
`tests/test_release_repair.py`, `tests/test_discovery.py`.
Added: `src/common/rollback.py`, `tests/test_runtime_boundary_and_fresh_first.py`.
Refreshed: `config/candidate_policy.json`.

## What is blocked or uncertain

1. **Adzuna live authenticated search** — no credential exists; the boundary is proven, the search is not.
2. **Production fetch transport for 3 of 4 keyless feeds** — local egress proxy truncates them.
3. **Rollback downgrade against real state** — rehearsed on mocked AWS only; needs deployment-time approval.
4. **Sub-24-hour capture** — not achievable on one daily run with delayed providers; achievable
   latency stated, optional second pass written up, no schedule changed.
5. **Careers-URL resolution live path** — off by default.
6. **Discovery -> monitoring** — proposes registry rows only, by design.
7. **Independent review** — not obtained. The review's own probe was re-run as the fresh boundary
   check, which is the closest available substitute and is disclosed as such.

## What is next

Operator decision: deploy, or route this through a third review first.

## Resume steps

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
git status                                  # uncommitted by design; do not reset
.venv/bin/pytest -q -p no:cacheprovider     # expect 252 passed
.venv/bin/python -m src.cli policy-check    # expect: projection matches all policy sources
PYTHONPATH=. .venv/bin/python project-factory/outputs/open-market-discovery/runs/20260924_open_market_release_repair_v1/evidence/orchestrator_review_probes.py
```
