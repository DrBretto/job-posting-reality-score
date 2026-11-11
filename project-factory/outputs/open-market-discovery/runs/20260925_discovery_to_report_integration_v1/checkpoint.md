# checkpoint — P07 discovery-to-report integration

Run: `20260925_discovery_to_report_integration_v1` · Packet:
`JPRS-L2-P07-discovery-to-report-integration-v01` · Status: `stage_complete`
Date: 2026-09-25.

---

## What moved

The missing producer-to-consumer edge P06 measured is closed **locally**.

1. **Reproduced the defect first**, with the P06 reviewer's own unmodified probe: one discovered and
   normalized job, zero candidate rows (`evidence/p07_before_repair_p06_probe.json`).
2. **Implemented the integration.** Discovery now writes a durable, feed-keyed live view at
   `discovery/live/provider={p}/live_jobs.json`; `assemble_report_input` reads the manifest's
   `expected_discovery_sources` and merges those postings into the job population **before** dedup,
   so screening, ranking, history, freshness and the complete candidate list all run over both
   populations unchanged.
3. **Re-ran the same probe, unedited**: one candidate row, from an employer absent from the registry
   (`evidence/p07_after_repair_p06_probe.json`).
4. **Repaired two defects found while tracing the path:**
   - discovery job identity was bound to the pagination cursor, so one posting became a different
     job on every page and every day;
   - `resolve_run_timing` recovered previously-reported ids only from `complete_candidate_list`, so
     the already-delivered 2026-09-25 report — which carries its rows in `top_matches` with that key
     empty — read as a round that showed nothing.
5. **Built the acceptance harness**: 23 cases driving the real enumerate, collector, discovery,
   differ and report stages with only HTTP/AWS/SES mocked.
6. **Withdrew P05's false claim.** Its two persisted-report tests were re-scoped onto the real
   producers; the "real internal wiring" header is gone. P05's own run evidence is untouched.

Infrastructure, IAM, schedules and the state machine are **byte-unchanged**, and that is asserted by
tests against the real files rather than claimed in prose.

---

## What is blocked or uncertain

- **Live acceptance is unproven and must stay that way until a deploy.** No registry-absent job has
  reached a real delivered report. The check is prepared in `DEPLOYMENT_HANDOFF.md` §5.1, including
  how to tell a legitimately thin day from a broken integration.
- **Deployment needs fresh approval.** P06's approval is spent on P06.
- The 21-day live-view retention bound is stated and bounded but not calibrated against a measured
  feed churn rate.
- The report Lambda now imports `src.discovery.live` and reaches it only because packaging ships the
  whole repository. A future packaging fix must carry that dependency explicitly.
- Adzuna remains credential-gated; its live query path is still unexercised.

---

## What is next

**One next unlocked task:** the orchestrator inspects the integration evidence in this run directory
and returns with a deployment decision. Not another broad review, not another committee.

---

## Artifacts emitted, with status

| Path (relative to this run root) | Status |
|---|---|
| `run_manifest.json` | complete |
| `checkpoint.md` | this file |
| `gate_decision.md` | complete — `unlock` for controlled deployment review only |
| `VALIDATION.md` | complete — design choice, boundary trace, results, limits |
| `DEPLOYMENT_HANDOFF.md` | complete — approval-gated, build-bound, rollback stated |
| `OPERATOR_RETURN.md` | complete |
| `evidence/p07_baseline_working_tree.txt` | evidence — pre-existing dirt, captured before any edit |
| `evidence/p07_before_repair_p06_probe.json` | evidence — 0 candidate rows |
| `evidence/p07_after_repair_p06_probe.json` | evidence — 1 candidate row |
| `evidence/p07_stage_trace_probe.py` | reusable — regenerates the trace below |
| `evidence/p07_stage_trace.json` | evidence — per-stage identities and counts, reconciled |
| `evidence/p07_sample_report.md` | evidence — the rendered morning report |
| `evidence/p07_test_results.txt` | evidence — 339 passed |
| `evidence/p07_policy_check.txt` | evidence — projection matches all policy sources |
| `evidence/p07_sam_validate.txt` | evidence — valid template |
| `evidence/p07_sam_build.txt` | evidence — build succeeded |
| `evidence/p07_owned_changes.txt` | evidence — owned changes separated from baseline dirt |

Code changes are listed in `evidence/p07_owned_changes.txt` and summarized in
`DEPLOYMENT_HANDOFF.md` §3. Nothing was committed, staged, branched or pushed.

---

## Resume steps

From the repository root:

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

# 1. the defect and its repair, using the P06 reviewer's own probe
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python \
  project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/evidence/p06_independent_producer_consumer_probe.py
# expect: "candidate_rows": 1 and a himalayas id in discovery_candidate_ids

# 2. the acceptance suite
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_discovery_to_report_integration.py
# expect 23 passed

# 3. the whole suite
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q          # expect 339 passed

# 4. the stage trace
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python \
  project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/evidence/p07_stage_trace_probe.py

# 5. policy + build
.venv/bin/python -m src.cli policy-check                          # expect: matches all sources
sam validate --lint --template-file infra/template.yaml
```

**Do not** `git checkout`, `reset`, `stash` or `clean`. The working tree is uncommitted and holds the
whole P01–P07 overhaul; there is no commit to return to.
