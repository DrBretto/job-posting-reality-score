# VALIDATION — publication commit boundary and verification (P09)

Run: `20260925_publication_commit_boundary_and_verification_v1`
Packet: `JPRS-L2-P09-publication-commit-boundary-and-verification-v01`
Executed: 2026-09-26. Local only. **No deployment, no AWS call, no invocation, no git mutation.**
P06 remains the running build and its approval is still spent.

Every claim below is labeled. `evidence` means a file in `evidence/` produced by running the thing.

---

## 1. The reviewer's own probes, before and after

`evidence` — both probes were run UNCHANGED, from the P08 run directory, before any repair and
again after.

| probe | arm | before repair | after repair |
| --- | --- | --- | --- |
| `p08_independent_pending_boundary_probe.py` | control | job in same-run retry and following report | unchanged |
| | first pending-ledger write refused | **job in neither report** | **job in both reports** |
| `p08_interrupted_publish_probe_unmodified.py` (P07's) | control | job in both | unchanged |
| | live-view write refused | job in both | unchanged |

Files: `evidence/p09_before_pending_boundary_probe.json`,
`evidence/p09_after_pending_boundary_probe.json`, `evidence/p09_after_p07_live_write_probe.json`.

The P08 repair is preserved: P07's live-write probe still passes, and the replay timing and
idempotence it established are unchanged.

## 2. The whole persistence sequence, not one key

`evidence` — `evidence/p09_publication_boundary_matrix.json`, 16 boundaries, each one refused
`PutObject` inside the real stage with the feed empty on every later attempt. Read
`FAILURE_MATRIX.md` for the table and the stated limits.

Result: every boundary either accepts nothing (one row: the acceptance write itself, where the
round is honestly incomplete and nothing durable was written at all) or accepts and recovers
without the provider returning the posting. No third outcome.

`inference` — the acceptance point is now decidable rather than asserted, because it is the first
durable write of a feed's round. P08's acceptance point sat after every forward-tier write, which
is why a single refused write could strand a posting that was already durably normalized.

## 3. The owed-debt bound no longer discards

`evidence` — `tests/test_durable_discovery_publication.py`:

- beyond the five-batch cap, every posting from every failed round is still owed; the oldest rounds
  are folded into one carry-forward batch and the compaction is named in the coverage receipt and
  in `inaccessible`
- the first healthy round after that backlog publishes **every** owed posting, from the debt alone,
  with each posting keeping the round that actually observed it. P08's bound ran on `owe`, before
  the drain, so that round evicted the oldest batch merely by enqueuing its own empty one
- the only bound that removes anything is the live view's own retention horizon, and it reports the
  job ids when it fires

`operator_preference` — the batch bound (5) and the retention bound (21 days) are still not
calibrated against measured data. Carried forward as an open item, unchanged from P08.

## 4. Release checkers now fail the conditions they name

`evidence` — `evidence/p09_release_gate_controls.json` (19 controls) and
`tests/test_release_gates_reject.py` (23 regressions). Before-repair behavior of the P08 helpers is
preserved in `evidence/p09_before_release_gate_probe.json`.

| condition | P08 helper | P09 entrypoint |
| --- | --- | --- |
| built template's IAM role property 3600 → 7200 | exit 0, `CHANGE_SET_IS_CODE_ONLY` | exit 1, `CHANGE_SET_INCLUDES_INFRASTRUCTURE` |
| a function added to the build | printed only | exit 1 |
| a function removed from the build | printed only | exit 1 |
| baseline build directory absent | not checked | exit 1, `COMPARISON_INCOMPLETE` |
| recorded P06 identity unavailable | not checked | exit 1, `COMPARISON_INCOMPLETE` |
| genuine code-only change | exit 0 | exit 0 |
| only `CodeUri` differs (SAM build path) | exit 0 | exit 0 |
| archive bytes corrupted | printed MISMATCH, exit 0 | exit 1, `BASELINE_NOT_VERIFIED` |
| a recorded module modified in the archive | printed MISMATCH, exit 0 | exit 1 |
| archive carries unrecorded executable source | not checked | exit 1 |
| restore aimed at the working tree's `src/` | would have replaced it | exit 1, `RESTORE_REFUSED` |
| second job from the SAME employer missing from the report | exit 0, `ACCEPTANCE_MET`, labelled "below the fit threshold" | exit 1, `RECONCILIATION_INCOMPLETE` |
| job from a different employer missing | exit 0 | exit 1 |
| a job the report NAMES as below fit | — | exit 0 |
| a legitimately deduplicated job | — | exit 0 |
| live view newer than the report | treated as missing input | exit 2, `INPUTS_NOT_COHERENT` |
| report predates per-identity evidence | treated as a zero | exit 2, `EVIDENCE_UNAVAILABLE` |

Maintained entrypoints, unambiguous: `scripts/check_release_change_set.py`,
`scripts/verify_rollback_baseline.py`, `scripts/inspect_discovery_integration.py`,
`scripts/reconstruct_p06_baseline_build.sh`, `scripts/release_preflight.sh`,
`scripts/rollback_preflight.sh`. The P08 originals in that run's `evidence/` are unchanged and are
superseded, not edited.

`evidence` — the per-identity dispositions are backed by evidence the CONSUMER states. The report
now writes `consumed_job_ids` and `below_fit_threshold_job_ids`, and
`below_fit_threshold_count` is the length of the second list, so the count and the identities
cannot disagree. Nothing is fabricated inside the inspector or the harness.

`evidence` — the local package comparison is named as what it is. It prints, every run, that it is
not an AWS change set and that inspecting the real change set is a separate later step.

## 5. Rollback works without the temporary P06 build directory

`evidence` — `evidence/p09_reconstruct_p06_baseline.txt`, `evidence/p09_rollback_drill.txt`,
`evidence/p09_rollback_preflight.txt`.

`/private/tmp/claude-501/jprs-build-p06-9H8jKS` is not used by anything in this run. The baseline is
reconstructed from the verified persisted archive by
`scripts/reconstruct_p06_baseline_build.sh`, which verifies before extracting, assembles a P06
source tree in scratch, and runs a local `sam build`. The forward change-set check in §6 was run
against that reconstruction.

Drill result, all in scratch: archive verified (36/36); restored into a scratch directory and
returned by discarding it; a restore aimed at the working tree refused; a corrupt archive refused
before any restore; a missing archive refused rather than treated as nothing to verify. The `src/`
fingerprint is identical before and after the drill
(`13c211976f2a417db8950751b7b5508656f8fe810e7f33582b25ed60fd4b23ef`).

`evidence` — the rollback shape check is appropriate to P06: it asserts that
`src/discovery/live.py` is **absent** from the restored tree, because that module is P07's and a
hybrid tree is the specific failure an in-place restore produces.

## 6. Build, template and change set

| check | result |
| --- | --- |
| `sam validate --lint --template-file infra/template.yaml` | exit 0 — `evidence/p09_sam_validate.txt` |
| `sam build --template-file infra/template.yaml --build-dir <scratch>` | exit 0, six functions — `evidence/p09_sam_build.txt` |
| reconstructed P06 baseline build | `BASELINE_BUILD_READY` — `evidence/p09_reconstruct_p06_baseline.txt` |
| change-set gate, baseline vs candidate | exit 0, `CHANGE_SET_IS_CODE_ONLY` — `evidence/p09_change_set_check.txt` |

All four checks in the gate were PERFORMED; none was skipped. Six function artifacts differ, all in
application code, which is the correct expectation for a shared-module change under
`Globals.Function.CodeUri: ../`.

Two honest notes about that comparison, both `evidence`:

- the reconstructed baseline carries the CURRENT tree outside `src/`, so repository payload
  (tests, docs) is not P06's. Those paths classify as payload, not infrastructure.
- `src/.DS_Store` appears as "added" for the same reason — the archive restore skips identified
  metadata. It is also genuinely packaged into the Lambda artifacts, which is packaging hygiene
  worth noting and out of scope here.

`sam build` had to be told an explicit `--build-dir` outside the repository: clearing the existing
`.aws-sam/build` was refused by this session's filesystem sandbox, because a stale build directory
contains a copied `.claude/commands` path the sandbox protects. That is an environment constraint,
not a build failure, and it is a second sign that the whole repository is being packaged.

## 7. Release command sequences fail closed

`evidence` — `evidence/p09_preflight_drill.txt`. `scripts/release_preflight.sh` was drilled against
a stubbed `sam` and a stubbed interpreter, breaking one step per case:

| broken step | exit | reached the deploy step |
| --- | --- | --- |
| nothing (all pass) | 0 | yes |
| test suite | 1 | no |
| policy projection | 1 | no |
| `sam validate` | 1 | no |
| `sam build` | 1 | no |
| report artifact missing `src/discovery/live.py` | 1 | no |
| change-set gate | 1 | no |

7 of 7 correct. The stub `sam deploy` exits 99 if it is ever called; it was never called.

The sequences use an explicitly selected shell (`#!/usr/bin/env bash`, `set -euo pipefail`), an
initialized argument array in the live-acceptance fetch loop, the verified build's explicit
template and an absolute SAM config path. Forward and rollback are separate scripts.

## 8. Test suite

`evidence` — `evidence/p09_test_results.txt`: **393 passed**, bytecode writes disabled. P08's run
had 350; the 43 new tests are the boundary matrix (18), the release gates (23), and the rewritten
and added owed-debt cases.

`evidence` — `evidence/p09_prerepair_regression_check.txt`: the new regressions were run against a
scratch copy of the tree with the P09 source edits reversed. `test_publication_commit_boundary.py`
cannot even be collected there (`s3layout` has no `discovery_owed_publication_key`); the three new
owed-debt cases and the consumer-evidence assertion fail. The actual working checkout was not
modified to produce that. Five unrelated `test_r4_*` failures in the scratch tree are an artifact of
the copy having no `.git` — those tests read a P06 file with `git show`.

## 9. One check is RED, and it is not this run's doing

`evidence` — `evidence/p09_policy_check.txt`. `policy-check` exits 1:

    changed since the projection was built: operating_plan, workflow

Both keys are operator-owned documents **outside this repository**
(`../Infotropy Book/INBOX/Employment Search/APPLICATION_WORKFLOW.md` and `OPERATING_PLAN.md`), and
both were edited on 2026-09-26 — after P08 ran, when this check passed. P09 changed no policy
source, no screening rule and no projection. Refreshing the projection is a candidate-policy edit,
which this packet excludes, so the divergence is reported and left to the operator.

`inference` — `scripts/release_preflight.sh` will therefore halt at step 2 today. That is the
correct behavior and it is why the preflight is a script rather than a list.

## What this run does NOT claim

- No live success, and no claim from a fixture. Every payload here is synthetic; the insurance and
  benefits companies are test controls and never vacancies.
- The positive product condition — a REAL job from a registry-absent employer in a report actually
  delivered — is **not met by this run and must not be reported as met**.
- Local tests, code deployment, real ingestion, delivery and unattended next-round behavior are
  five distinct claims. Only the first is addressed here.
- Nothing here makes two simultaneous discovery invocations safe. Discovery is one scheduled writer
  doing read-modify-write on its own objects; every fault case is serial and no exactly-once
  guarantee under concurrency is claimed.
- No fresh SAM deploy, change-set inspection, invocation or transport check was performed.
- The unattended round on 2026-09-26 (discovery 07:05) is a P06 observation and was not checked
  here. It must not be recorded as passed on this run's evidence.
