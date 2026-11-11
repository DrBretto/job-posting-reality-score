# CHECKPOINT — 20260924_open_market_discovery_v1

Status: **stage_complete (local readiness)**. Stages A–D done. Deployment NOT performed and not
authorized by this packet.

## What moved

- **Stage A (design)** — live source research done; `DESIGN.md` written with the source/access/cost
  matrix, the admission policy, the candidate-policy projection design, and the test strategy.
- **Stage B (implement)** — employer moved from a property of the SOURCE to a property of the JOB;
  discovery subsystem, candidate screening, cross-source dedup, fetch guard, source admission, and
  the four named repairs all implemented.
- **Stage C (prove)** — 168 tests pass; live rehearsal run; coverage comparison produced across three
  runs on the same evaluation day.
- **Stage D (review + stop)** — self-review in two explicit passes (disclosed as NOT independent);
  ten findings, nine repaired, one reported; deployment handoff written; entrypoints updated.

## Artifacts emitted

| Path | Status |
|---|---|
| `DESIGN.md` | complete |
| `VALIDATION.md` | complete — every acceptance row has an explicit verdict |
| `DEPLOYMENT_HANDOFF.md` | complete |
| `OPERATOR_RETURN.md` | complete |
| `gate_decision.md` | complete |
| `run_manifest.json` | complete |
| `evidence/source_probe_provenance.json` | complete (shapes/counts/hashes; no raw provider payloads) |
| `rehearsal/live/` | Remotive live through `fetch_raw`; other three PARTIAL under the sandbox proxy |
| `rehearsal/live_replay/` | all four sources, live bytes, replayed through the connector |
| `rehearsal/monitored_only/` | the OLD footprint on the same evaluation day |
| `rehearsal/combined/` | monitored + discovery, i.e. what production does daily |
| `rehearsal/coverage_diff.json` | old-vs-new comparison |

## Repository changes (uncommitted, branch `codex/real-job-radar`)

New: `src/discovery/` (7 modules), `src/candidate/` (3 modules), `src/common/fetch_guard.py`,
`src/common/dedup.py`, `config/discovery_sources.yaml`, `config/candidate_policy.json`,
`config/application_history.json`, 5 new test files.
Modified: `src/common/{models,normalize,connectors,s3layout}.py`, `src/{differ,report,enumerate,
collector}/handler.py`, `src/scoring/scoring.py`, `src/cli.py`, `infra/template.yaml`, `.samignore`,
4 existing test files.

## What is blocked or uncertain

1. **Adzuna live discovery** — needs a free `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`. Implemented and
   fixture-tested; never run. This is the general-industry breadth engine, so its absence is a real
   coverage limit and the report says so.
2. **Source growth** — cannot admit any employer discovered through the keyless feeds, because none
   of them publish the employer's own board URL (measured, not assumed). The bounded careers-URL
   resolver closes this; it is off by default and its live path is unverified here.
3. **`fetch_raw` for three of four feeds** — unverified outside this sandbox; the local egress proxy
   truncates them. Correct degradation (PARTIAL, removals suppressed) was observed. Post-deploy
   check 1 closes this.
4. **Lambda packaging** — `.samignore` is not honored by SAM's Python builder; every function ships
   the whole repository. Pre-existing, reported, not fixed (changing it affects all five functions).

## What is next

**One operator decision: deploy or not.** `DEPLOYMENT_HANDOFF.md` has the commands, the expected
change set, the five post-deploy checks, and the rollback.

## Resume steps

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
git status                                       # working tree is uncommitted by design
.venv/bin/pytest -q -p no:cacheprovider          # expect 168 passed
.venv/bin/python -m src.cli policy-check         # expect: projection matches all policy sources
.venv/bin/python -m src.cli discover --live --out /tmp/jprs-rehearsal   # re-run the rehearsal
```

Read `OPERATOR_RETURN.md` first, then `DEPLOYMENT_HANDOFF.md`. `VALIDATION.md` carries the
acceptance verdicts and the ten findings.
