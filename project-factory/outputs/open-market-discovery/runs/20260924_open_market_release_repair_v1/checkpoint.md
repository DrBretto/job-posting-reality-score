# CHECKPOINT — 20260924_open_market_release_repair_v1

Status: **stage_complete (local repair readiness)**. R1–R4 closed locally. No deployment occurred.

## What moved

1. Reproduced R1–R4 independently before any repair (`evidence/defect_reproduction_before_repair.txt`).
2. Added 41 regression tests; confirmed **23 failing** before repair (`evidence/tests_before_repair.txt`).
3. **R1** — default provider list now reaches credential-gated sources so their gate is reported;
   `AdzunaConnector.with_env()` binds resolved credentials without mutating the shared instance;
   location scopes wired (nationwide + remote + NH + Boston); credential redaction in every receipt.
4. **R2** — new `PaginatedFeedConnector`; Himalayas walks its documented 20-per-page cursor with a
   persisted, resumable position; failed/rate-limited pages keep their cursor; repeated cursors stop
   without claiming the feed is exhausted; the same loss mode checked on the Adzuna query feed.
5. **R3** — clause-scoped `polarity` (required / negated / optional) consulted by every rule branch;
   software-artifact versus own-duty detection; bare `prospects` removed from the sales pattern;
   ambiguity routes to PENDING_CHECK; `norm_text` now decodes HTML entities first.
6. **R4** — rollback validated against the AWS CLI (no AWS call); non-destructive worktree method;
   partial disable distinguished from full rollback; cost bounded from AWS's Price List API.
7. Audited all 364 P01 exclusions on identical bytes: 34 changed, of which only 2 reach the
   candidate list after scoring.
8. Policy sources compared semantically before refreshing the projection: no exclusion changed. The
   comparison exposed a real gap — below-threshold postings were invisible — now stated in the report.

## Verification (`evidence/after_repair_verification.txt`)

```
pytest                     209 passed        (168 before P02; 41 added)
tests/test_release_repair   41 passed
sam validate --lint        valid SAM Template
sam build                  Build Succeeded
policy-check               projection matches all policy sources
```

Repaired rehearsal: `rehearsal/combined_repaired/`. Himalayas 20 -> **96 postings / 74 employers**;
821 postings considered; 221 discovery employers, none in the registry; 44 retained credible.

## Artifacts emitted

`run_manifest.json`, `checkpoint.md`, `gate_decision.md`, `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`,
`OPERATOR_RETURN.md`, `evidence/` (7 files), `rehearsal/combined_repaired/` (3 files).

P01 evidence left intact; its handoff carries the review's qualifying banner rather than being edited
to hide the original verdict.

## Repository changes (uncommitted, branch `codex/real-job-radar`)

Modified: `src/common/{normalize,connectors}.py`, `src/candidate/screening.py`,
`src/discovery/{handler,connectors,budget}.py`, `src/report/handler.py`, `tests/test_discovery.py`.
Added: `tests/test_release_repair.py`.
Refreshed: `config/candidate_policy.json`.

## What is blocked or uncertain

1. **Adzuna live gate** — no credential; the path works but has never run authenticated.
2. **Production fetch transport, 3 of 4 feeds** — local egress proxy truncates them; verified on real
   bytes, not through `fetch_raw`. Post-deploy check 1.
3. **Careers-URL resolution** — off by default; its DNS-dependent guard cannot run in this sandbox.
4. **Discovery -> monitoring** — proposes registry rows only, by design.
5. **Independent review of the repaired screening** — not obtained; disclosed in VALIDATION §7.
6. **Lambda packaging ships the whole repository** — pre-existing; no security or runtime defect
   demonstrated, so not treated as a prerequisite.

## What is next

Operator decision: deploy, or route the repaired screening rules through an independent review first.

## Resume steps

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
git status                                     # uncommitted by design; do not reset
.venv/bin/pytest -q -p no:cacheprovider        # expect 209 passed
.venv/bin/python -m src.cli policy-check       # expect: projection matches all policy sources
```

Read `OPERATOR_RETURN.md`, then `DEPLOYMENT_HANDOFF.md`. `VALIDATION.md` carries the per-finding
evidence and the acceptance verdicts.
