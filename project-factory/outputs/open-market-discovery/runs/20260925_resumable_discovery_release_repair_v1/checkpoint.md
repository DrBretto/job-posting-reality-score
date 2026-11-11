# checkpoint — P05 resumable discovery and release binding

Run: `20260925_resumable_discovery_release_repair_v1` · Packet:
`JPRS-L2-P05-resumable-discovery-release-repair-v01` · Status: `completed` · Date: 2026-09-25

## What moved

1. **Recent-range traversal is now resumable across runs.** Discovery state records what it still
   *owes* (`DiscoveryState.head_pending`, an ordered list of untraversed recent cursor ranges) as a
   separate fact from what it has *observed* (`head_frontier_at`). A recent page that fails, comes back
   partial, or is never reached stays owed and is retried; a newly published continuation no longer
   overwrites a saved one, because one slot no longer has to hold both.
2. **Every outbound attempt is charged against the source budget**, including one that raises, and each
   walk is additionally bounded by the budget's remaining allowance. The review's 4-requests-under-3
   measurement is closed.
3. **Deployment and rollback select the build that was verified.** Both commands now pass
   `--template-file` pointing at the built artifact and an absolute `--config-file`, verified through
   SAM's own resolution functions with no AWS call.
4. **20 new regression tests**, 12 of which fail against a reconstructed P04 source.
5. **Corrected deployment documentation** in three places: this run's `DEPLOYMENT_HANDOFF.md`,
   `infra/DEPLOY.md`, and `START_HERE.md` — all three carried the same unbound command.

Full suite: **296 → 316 passed.**

## What is blocked or uncertain

Nothing blocks the next step. Open items, each honestly open rather than parked:

- **Production HTTP transport, all four keyless feeds** — unverified. P04 measured non-deterministic
  truncation from this machine. Only the first scheduled Lambda run closes it.
- **A real interrupted production day** — the repair's behaviour is verified over persisted-state
  reproductions, not observed in production.
- **Authenticated Adzuna, general-industry coverage, the careers-URL resolver live path, source-growth
  admission** — separate activation gates, none a prerequisite for deploying the keyless paths.
- **Rollback data downgrade against real state** — rehearsed only.
- **The drive-time interpretation** — deliberately unresolved in state; still needs the operator.

## What is next

One unlocked task: **operator-approved controlled deployment with live HTTP checks**, following this
run's `DEPLOYMENT_HANDOFF.md` §4 verbatim and then its §5 acceptance checks. No further speculative
polishing, and no new broad review by default.

## Artifacts emitted or updated

Run root: `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/`

| path | status |
|---|---|
| `run_manifest.json` | complete |
| `checkpoint.md` | complete (this file) |
| `gate_decision.md` | complete — outcome `unlock` |
| `OPERATOR_RETURN.md` | complete |
| `VALIDATION.md` | complete |
| `DEPLOYMENT_HANDOFF.md` | complete — **handoff of record**, supersedes P04's |
| `evidence/p05_before_repair_p04_probe.json` | evidence — both defects reproduced before any edit |
| `evidence/p05_after_repair_p04_probe.json` | evidence — both closed, budget honoured |
| `evidence/p05_persisted_scenario_driver.py` / `_results.json` | evidence — exit 0, five assertions true |
| `evidence/p05_deploy_selection_probe.py` / `_results.json` | evidence — exit 0, five assertions true |
| `evidence/p05_new_tests_against_p04_source.txt` | evidence — 12 of 20 new tests fail on P04 |
| `evidence/p05_p04_reconstruction_method.py` | method — the ten asserted reverts |
| `evidence/p05_test_transcript.txt` | evidence — 316 passed, plus focused suites |
| `evidence/p05_sam_validate_build.txt` | evidence — template valid, build succeeded |
| `evidence/p05_policy_check.txt` | evidence — projection matches all policy sources |
| `reports/failed_recent_page/run1..run3/` | evidence — persisted daily reports + state |
| `reports/new_burst_above_saved_continuation/run1..run5/` | evidence — persisted daily reports + state |

Repository files changed by this run:

| path | change |
|---|---|
| `src/discovery/budget.py` | `head_pending`, `pending_head`, `set_pending_head`, `HEAD_PENDING_MAX`; `head_cursors` becomes a derived mirror |
| `src/discovery/handler.py` | worklist-driven walk returning traversal debt; attempts charged before the fetch; frontier stop restricted to the contiguous chain; owed ranges reported |
| `tests/test_resumable_discovery_and_release_binding.py` | new, 20 tests |
| `docs/plans/2026-09-25-resumable-discovery-release-repair.md` | new plan doc |
| `infra/DEPLOY.md` | deploy/build commands bound; the selection trap documented |
| `START_HERE.md` | same command correction; current direction updated to P05 |
| `docs/PLAN.md`, `project-factory/meta/*`, `project-factory/ORCHESTRATOR_BOOTSTRAP.md`, `project-factory/claude_handoff/PACKET_REGISTRY.tsv` | reconciled to this run |

Nothing was deployed, committed, staged, branched, reset or pushed. No AWS call, no credential, no
network request, no email.

## Resume steps

If this run had to be resumed, it is already complete; re-verify rather than re-execute:

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

# 1. the repair holds
.venv/bin/python -m pytest -q -p no:cacheprovider            # expect 316 passed

# 2. the review's own probe, unmodified
.venv/bin/python project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/evidence/p04_independent_continuation_probe.py
# expect missing_fresh_job false twice, attempts_exceed_budget false

# 3. the two scenarios reach a persisted report
.venv/bin/python project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/evidence/p05_persisted_scenario_driver.py
# expect exit 0

# 4. deployment selects the verified build (needs SAM's own interpreter)
/opt/homebrew/Cellar/aws-sam-cli/1.137.1/libexec/bin/python \
  project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/evidence/p05_deploy_selection_probe.py
# expect exit 0
```

Step 4 uses SAM's bundled interpreter deliberately: under the repository venv the import of SAM's
`botocore`/`pyOpenSSL` stack fails with `module 'lib' has no attribute 'GEN_EMAIL'`, a library clash in
this environment and not a result about the selection logic.
