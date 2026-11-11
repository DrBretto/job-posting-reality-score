# checkpoint — P08 durable publication and release repair

Packet: `JPRS-L2-P08-durable-discovery-publication-and-release-repair-v01`
Run: `20260925_durable_discovery_publication_release_repair_v1` · Date: 2026-09-25
Stage: `implementation_and_local_verification` — **complete**

## What moved

**R1 — the interruption is repaired.** A storage failure immediately before the live-view write no
longer loses an already-captured posting. `persist()` now owes its observations to a durable ledger
before any progress record can claim them published, and drains that ledger one feed at a time,
clearing each feed's debt only after its view has committed. The reviewer's own probe, copied
byte-identical, went from losing the job on both the same-run retry and the following report to
matching the uninterrupted control in every field — with the feed returning nothing on both later
fetches, so this is replay of the capture and not a re-fetch.

**R2.1 — the expected change set is corrected and measured.** P07's handoff said only two Lambdas
could change and told the operator to stop otherwise; that rule would have rejected a correct deploy.
All six function artifacts change on any shared-module edit, because every function inherits
`CodeUri: ../`. Six application-code paths differ; no IAM, schedule, parameter, state-machine or
retention change does. The built templates are byte-identical and the three infrastructure source
files match P06's recorded hashes exactly.

**R2.2 — a real rollback baseline exists and the recovery was drilled.** An intact local P06 build
matches P06's own recorded per-file hashes on 36 of 36 source files in all six packaged functions. It
is archived in this run root so the procedure no longer depends on a temporary directory, and the
whole restore-and-return cycle was tested in a scratch directory without risking the uncommitted
overhaul. The permitted bounded read-only AWS retrieval was therefore not needed.

**R2.3 — the live check now discriminates.** `scripts/inspect_discovery_integration.py` reconciles
every stored discovery identity to a disposition in the real report schema and was exercised against
reports the real stages produced. It tells apart a genuine zero-fit day from a removed consumer
connection — the pair P07's proposed check could not — and it verifies employer identity against the
registry rather than comparing source ids.

**Preserved.** P07's integration is behaviorally unchanged: all 339 of its tests still pass, and the
ownership decision, closure semantics, stable identities and old-report fallback are untouched.

## What is blocked / uncertain

- **Nothing is blocked.** Every clause of the packet's acceptance condition is met locally.
- **The live acceptance condition is not met and must not be reported as met.** It requires a real
  registry-absent posting in a delivered report after an approved deployment.
- Runtime IAM is established only as *declared* grants read from the real template. Mocked S3 grants
  everything. The design deliberately needs no new grant, which is what keeps this bounded.
- The owed-batch bound (5 per provider) and the live-view retention bound (21 days) are stated and
  reported when reached, but neither is calibrated against measured data.
- A rollback performed while a batch is owed loses those observations, because P06 never drains the
  ledger. The receipt names the job ids and the handoff says to check it first.

## Artifacts emitted or updated

| Path | Status |
|---|---|
| `run_manifest.json`, `checkpoint.md`, `gate_decision.md` | new |
| `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`, `OPERATOR_RETURN.md` | new |
| `evidence/p08_interrupted_publish_probe_unmodified.py` + before/after JSON | new — the reviewer's script, unmodified |
| `evidence/p08_package_scope.py` + `.txt` | new — reusable change-set derivation |
| `evidence/p08_verify_rollback_baseline.py` + `.txt` | new — reusable baseline verification |
| `evidence/p06_baseline_src.tar.gz` | new — the hash-verified P06 source, 36 files |
| `evidence/p08_rollback_drill.sh` + `.txt` | new — recovery tested locally, both directions |
| `evidence/p08_exercise_live_check.py` + `.txt` + `live_check_fixtures/` | new — 5 controls on real reports |
| `evidence/p08_sample_report_{interrupted,recovered}_round.md` | new — the operator-visible surface |
| `evidence/p08_test_results.txt`, `p08_policy_check.txt`, `p08_sam_validate.txt`, `p08_sam_build.txt`, `p08_owned_changes.txt` | new |
| `src/discovery/live.py`, `src/discovery/handler.py`, `src/common/s3layout.py`, `src/report/handler.py` | edited |
| `tests/test_durable_discovery_publication.py`, `scripts/inspect_discovery_integration.py` | created |
| `docs/plans/2026-09-24-open-market-job-discovery.md` | P08 plan section and execution log |
| `project-factory/meta/*`, `ORCHESTRATOR_BOOTSTRAP.md`, `PACKET_REGISTRY.tsv` | synchronized |
| `infra/*`, `config/*`, `src/{candidate,scoring,differ,collector,enumerate}/` | untouched |

## One next unlocked task

**Orchestrator inspects this run's targeted repairs and returns a fresh deployment decision.** Read,
in order: `OPERATOR_RETURN.md`, `VALIDATION.md` §1–§4, then `DEPLOYMENT_HANDOFF.md` §2 for the
corrected stop rule and §6 for the drilled rollback. Do not open another committee, deploy, or wait
for tomorrow as part of that inspection.

## Resume steps

Nothing to resume; the stage is complete. To re-verify independently from a clean session:

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score
R=project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1

.venv/bin/python -m pytest -q                       # expect 350 passed
.venv/bin/python -m src.cli policy-check            # expect: projection matches all policy sources
.venv/bin/python $R/evidence/p08_interrupted_publish_probe_unmodified.py   # both arms identical
.venv/bin/python $R/evidence/p08_verify_rollback_baseline.py \
  /private/tmp/claude-501/jprs-build-p06-9H8jKS .   # expect BASELINE_VERIFIED
bash $R/evidence/p08_rollback_drill.sh "$PWD"       # expect DRILL_PASSED
.venv/bin/python $R/evidence/p08_exercise_live_check.py "$(mktemp -d)"     # expect 5/5
```

The rollback baseline lives in a temporary directory that a reboot can clear. If that path is gone,
`evidence/p06_baseline_src.tar.gz` is the baseline and the drill still passes against it; only the
`p08_verify_rollback_baseline.py` step needs the build tree.
