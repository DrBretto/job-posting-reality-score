# P0 Account Guardrails

## Context

P0 establishes the safety floor before any spend-capable project service is built. The committee
requires a fixed region, non-root operating identity, cost visibility, Access Analyzer, and a shared
permissions boundary. Read-only account inspection on 2026-07-28 found useful existing controls, but
also found gaps that must be handled manually before P0 can pass.

This phase deliberately separates preparation from proof:

- AI prepares inspectable policy JSON, exact instructions, and read-only observations.
- Brett creates or changes AWS resources in the console.
- Shared verification confirms the resulting state.

## Plan

- [x] Create the standalone `job-posting-reality-score` repository.
- [x] Preserve the complete committee output under `docs/roadmap/committee-v1/`.
- [x] Record the read-only account preflight without private identifiers.
- [x] Write the P0 console worksheet and guardrail explainer.
- [x] Draft the shared execution-role permissions boundary.
- [x] Correct the committee's unsupported direct scheduler-disable mechanism.
- [x] Draft the P4 budget-lockdown policy.
- [x] Consolidate operator instructions, progress reporting, and restart guidance into `START_HERE.md`.
- [ ] Brett completes root-key review, human MFA, and access-key inventory.
- [ ] Brett enables billing alerts and observes the intentional wrong-region failure.
- [ ] Brett creates the `$5` warning budget, `$10` ceiling budget, and billing alarm.
- [ ] Brett enables IAM Access Analyzer.
- [ ] Brett creates and inspects both customer-managed IAM policies.
- [ ] Shared read-only verification passes.
- [ ] Brett answers the no-notes recall prompt.

## Execution Log

- 2026-07-28: Committee run verified complete through the governance spine with eight real seats and a
  `PASS WITH CONDITIONS` verdict.
- 2026-07-28: New repository created from the local solo template on branch
  `codex/p0-foundation`; no AWS resources created.
- 2026-07-28: Read-only AWS preflight completed. Root MFA exists; root access key, human-user MFA,
  billing telemetry, Access Analyzer, and project-specific budget controls need attention.
- 2026-07-28: Confirmed from AWS documentation that Budget Actions cannot directly disable an
  EventBridge Scheduler schedule. Chose a supported IAM-policy lockdown for P4.
- 2026-07-28: Both IAM policy files returned zero findings from AWS Access Analyzer policy validation.
- 2026-07-28: Repository fast checks passed; code-specific checks remain unavailable until application
  code and tests are added.
- 2026-07-29: Replaced the generic template entrypoint with a complete operator guide and synchronized
  the README, orchestrator bootstrap, and session status around it.

## Follow-ups

- P4 must create a dedicated scheduler invocation role and configure the `$10` Budget Action to attach
  `jprs-budget-lockdown-deny` automatically.
- Every Lambda phase must include pre-created CloudWatch log groups with 30-day retention in its done
  gate.
- Before P7, verify current CloudWatch custom-metric and alarm pricing against expected volume.
- Before P8, re-check Bedrock model availability and pricing; Bedrock remains off by default.
