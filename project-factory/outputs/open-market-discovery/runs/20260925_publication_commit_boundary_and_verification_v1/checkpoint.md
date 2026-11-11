# checkpoint — 20260925_publication_commit_boundary_and_verification_v1

Status: `completed`. Executed 2026-09-26, locally. Nothing deployed, no AWS call, no git mutation.

## What moved

**A. The durable acceptance boundary.** A feed's owed-publication record is now its own object
(`discovery/owed/provider=<p>/owed_publication.json`) and the FIRST durable write of that feed's
round, ahead of `raw/`, `normalized/`, `status/` and the SUCCESS sentinels. P08 recorded the debt
once, at an aggregate key, after every forward-tier write, so refusing that one write stranded a
posting that was already durably normalized. The reviewer's unchanged probe now retains the job on
both the same-run retry and the following round; P07's live-write probe still passes.

**B. The whole persistence sequence is exercised, not one key.** Sixteen boundaries, one refused
`PutObject` each, feed empty afterwards — `FAILURE_MATRIX.md`. Every boundary either accepts
nothing (one row: the acceptance write itself, where nothing durable was written at all) or accepts
and recovers without the provider returning the posting.

**C. The owed-debt bound compacts instead of discarding.** Beyond five batches the oldest rounds
fold into one carry-forward batch, all postings preserved; only the live view's own retention
horizon removes anything, and both are reported. The first healthy round after a backlog now
publishes every owed posting instead of evicting the oldest by enqueuing its own empty batch.

**D. Release checkers reject what they name.** `scripts/check_release_change_set.py` fails a
changed built-template resource property, an added or removed function, an unavailable baseline and
an unperformed comparison, and passes genuine code-only and normalized-`CodeUri` differences.
`scripts/verify_rollback_baseline.py` fails closed before restoring and refuses to restore over the
working tree. `scripts/inspect_discovery_integration.py` reconciles against evidence the report now
states (`consumed_job_ids`, `below_fit_threshold_job_ids`) instead of inferring below-fit status
from an employer-name match.

**E. Release command sequences fail closed**, drilled 7/7 against stubbed tools, and the P06
baseline is reconstructed from the verified archive rather than from a temporary directory.

393 tests pass (P08: 350).

## What is blocked / uncertain

- `policy-check` exits 1: two operator-owned policy sources outside this repository
  (`../Infotropy Book/INBOX/Employment Search/{APPLICATION_WORKFLOW,OPERATING_PLAN}.md`) were
  edited on 2026-09-26. P09 changed no policy source. Refreshing the projection is a
  candidate-policy edit this packet excludes, so it is surfaced, not resolved.
  `scripts/release_preflight.sh` halts there by design.
- No AWS change set, deploy, invocation or transport check was performed. The positive product
  condition — a real job from a registry-absent employer in a delivered report — remains unmet and
  is not claimed.
- The unattended round on 2026-09-26 (discovery 07:05) is unverified and is a P06 observation.

## What is next

One next unlocked task: **orchestrator review of this run.** After that, fresh deployment
authorization — not another committee by default.

## Artifacts emitted or updated

| path | status |
| --- | --- |
| `VALIDATION.md` | new, complete |
| `DEPLOYMENT_HANDOFF.md` | new, supersedes P08's on four points; P08's file unchanged |
| `FAILURE_MATRIX.md` | new |
| `OPERATOR_RETURN.md` | new |
| `gate_decision.md`, `run_manifest.json`, `checkpoint.md` | new |
| `scripts/p09_publication_boundary_matrix.py` | new, reusable |
| `scripts/p09_release_gate_controls.py` | new, reusable (19 controls) |
| `scripts/p09_preflight_drill.sh` | new, reusable (7 cases) |
| `evidence/` (16 files) | new |
| `src/common/s3layout.py`, `src/discovery/live.py`, `src/discovery/handler.py`, `src/report/handler.py` | modified, uncommitted |
| `scripts/{check_release_change_set,verify_rollback_baseline}.py` | new maintained entrypoints |
| `scripts/{reconstruct_p06_baseline_build,release_preflight,rollback_preflight}.sh` | new maintained entrypoints |
| `scripts/inspect_discovery_integration.py` | repaired in place |
| `tests/test_publication_commit_boundary.py`, `tests/test_release_gates_reject.py` | new |
| `tests/test_durable_discovery_publication.py`, `tests/test_discovery_to_report_integration.py` | modified |
| `docs/plans/2026-09-24-open-market-job-discovery.md` | P09 plan section and execution log |
| P08 run directory | unchanged, preserved |

## Resume steps

Nothing to resume; the run is complete. To re-derive any claim from the repository root:

```bash
.venv/bin/python -m pytest -q -p no:cacheprovider                       # 393 passed
P08=project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1
.venv/bin/python "$P08/evidence/p08_independent_pending_boundary_probe.py"
.venv/bin/python "$P08/evidence/p08_interrupted_publish_probe_unmodified.py"
RR=project-factory/outputs/open-market-discovery/runs/20260925_publication_commit_boundary_and_verification_v1
.venv/bin/python "$RR/scripts/p09_publication_boundary_matrix.py"
.venv/bin/python "$RR/scripts/p09_release_gate_controls.py"
bash "$RR/scripts/p09_preflight_drill.sh"
```
