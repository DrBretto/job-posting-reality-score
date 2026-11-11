# P06 return review — collection is deployed; discovery-to-report acceptance fails

Date: 2026-09-25. Action class: run-return, evidence, successor packet.

## Decision

Accept the bounded deployment and one-run transport observations in the returned evidence.
Do not accept the product as delivered. Stage P07 for local implementation and verification of
the missing producer-to-consumer integration. No additional broad committee, rollback, deployment,
git mutation or application submission is authorized by this review.

## What was checked

**Evidence from P06, not an independent AWS re-query:** `gate_decision.md`,
`evidence/p06_live_verification_summary.md`, and the operator return distinguish the successful
stack update and four successful keyless feed fetches (295 jobs, 218 employers) from zero discovery
candidates in the actual report. The original monitored-board report remains functional. There is
no evidence here requiring containment or rollback. Tomorrow's scheduled-round behavior is pending.

**Independently reproduced locally:** `evidence/p06_independent_producer_consumer_probe.py` runs
the real enumerate, discovery handler/persistence, and report handler against mocked external
AWS/HTTP services. It does not write a manifest, normalized jobs, current state, or report rows
itself. Its saved JSON records one discovered/normalized job and zero candidate rows. This isolates
the missing discovery-to-report edge; it does not simulate monitored-board collection or establish
the entire state machine, deployed IAM, or live HTTP behavior.

Reproduce from the JPRS repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/evidence/p06_independent_producer_consumer_probe.py
```

**Code confirms the cause:** enumerate writes `expected_discovery_sources`, discovery persists
normalized snapshots, but report candidate assembly loads jobs for `expected_sources` from
`current/`. The deployed assembly state machine invokes the differ for registry companies only.
Coverage reads discovery metadata; candidate assembly does not consume the discovered jobs.

## Correction to the earlier review

The P05 review accepted persisted target rows as evidence of an end-to-end connection without
checking who produced the intermediate objects. `_write_round` in
`tests/test_resumable_discovery_and_release_binding.py` writes both the manifest entries and
discovery `current/` objects that production never writes. Those tests support traversal/report
behavior GIVEN that connection, not existence of the connection. The review's broader inference
is withdrawn. Preserve its original text and test evidence as history; this qualification controls.

## What P07 must deliver

The existing product goal is unchanged: previously unnamed employers' useful jobs reach the same
screened, ranked, deduplicated morning output without registry admission first. Hundreds of raw
feed rows are not the desired result. Do not invent a new candidate policy or a daily quota.

Implementation must choose a small explicit ownership path for discovery candidates, preserve
identity across pages/days, and not equate absence from a churning feed with closure. Verify the
whole connection using real producers and consumers, including declared invocation paths and
permissions. Repair the bounded old-report history fallback against its actual empty-complete-list,
nonempty-top-matches shape. New-to-report is distinct from newly posted.

P07 is staged at
`project-factory/claude_handoff/packets/jprs/JPRS-L2-P07-discovery-to-report-integration-v01.md`.
It authorizes local repair only. Deployment of changed code requires fresh explicit approval.
