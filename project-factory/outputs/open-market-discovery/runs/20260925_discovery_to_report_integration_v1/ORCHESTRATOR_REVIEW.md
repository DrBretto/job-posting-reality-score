# P07 review — useful integration works; release needs bounded repair

Date: 2026-09-25. Action: run-return/evidence/packet. Decision: `revise_implementation` before deployment.

## Accepted evidence

Independently reran the full suite: **339 passed**. The unchanged P06 real-handler probe now produces
one discovery candidate from one normalized job, and the policy projection matches its sources.
The main missing connection is fixed locally. The live-view ownership choice, separation from ATS
closure semantics, stable cursor-independent identities and old-report fallback are retained.
The sample insurance-company role is a **synthetic test control**, not an actual vacancy to apply to.
P06 remains the deployed version; nothing in this review contacts or changes AWS.

Compared local `infra/template.yaml` and `infra/samconfig.toml` with P06's recorded SHA-256 hashes:
both match exactly. This is stronger than the return's modification-time comparison. No infrastructure
source change was found. Inspected P07's existing fresh-build output and its declared function artifacts.

## R1 — durable observations can still vanish from the candidate path

`src/discovery/handler.py::persist` writes snapshots, success/coverage and traversal state before
`persist_live_views`. No replay of the stored observations bridges a failure at that final write.

Executable independent evidence:
`evidence/p07_independent_interrupted_publish_probe.py` and its JSON result. The probe uses P07's
real enumerate, collector, discovery, differ and report harness with mocked external services. It
does not create intermediate objects. In one arm it injects one external storage failure immediately
before the live-view write. Both arms then receive the same changed/empty feed window on a same-run
retry and following round.

| Result | Uninterrupted control | Interrupted publication |
| --- | --- | --- |
| Qualifying discovery job durably normalized | yes | yes |
| Coverage/progress already persisted | yes | yes |
| Candidate survives the same-run retry | yes | no |
| Candidate reaches the following report | yes | no |
| Original raw observation still stored | yes | yes |

This is a recoverable observation stranded upstream, not an inability to recover bytes never saved.
A healthy new feed response does not substitute for replay of the already-captured job. Moving a
progress write alone is insufficient if the next retry overwrites/replaces the observations before
materialization. Require a small durable/replayable handoff and interruption tests at this boundary.
Do not rebuild discovery or introduce a general transaction framework.

## R2 — the deployment handoff is not yet executable safely as claimed

- **Expected change set:** the handoff says only discovery and report function code can change. All
  functions inherit `Globals.Function.CodeUri: ../`; P07's built Enumerate, Collector, Differ,
  Discovery, Report and optional Narrator artifacts all contain the new live module. A shared-package
  update can change the code artifact for other active functions without an infrastructure edit.
  The current stop rule would reject a legitimate code-only update. Do not confuse unchanged template
  source with exactly two CloudFormation resource changes.
- **Rollback baseline:** copying the already-modified working files before a future rollback does
  not restore P06. The handoff names no verified pre-P07 source/artifact to restore, while HEAD lacks
  the uncommitted P01–P06 overhaul. Establish a recoverable hash-verified P06 artifact before deployment;
  preserve both the deployed baseline and current work. Do not reconstruct it by guesswork or reset Git.
- **Thin-day check:** a nonempty live view, coverage metadata and report-wide exclusion/below-fit
  counts do not prove discovery jobs were consumed; those counts can come entirely from monitored
  jobs. Require discovery-specific input-to-disposition reconciliation. Its employer-absence check
  also compares source IDs rather than employers; every discovery provider differs from an ATS source
  even when both carry a known employer. Verify actual employer identity for that acceptance claim.

## Next and limits

Prepare P08 for R1 and R2 only, preserving P07's working path and prior repairs. No new committee,
provider, candidate-policy change, scheduling change, automatic source admission or packaging redesign.
Production has not been tested by this review. The original executor return/gate remain historical
evidence; this review qualifies release acceptance rather than silently editing them into a pass.

P08: `project-factory/claude_handoff/packets/jprs/JPRS-L2-P08-durable-discovery-publication-and-release-repair-v01.md`.
It stops after local verification and a corrected release handoff. No deployment is authorized.
