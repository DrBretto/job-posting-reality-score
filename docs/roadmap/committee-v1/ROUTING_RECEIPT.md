# Routing Receipt — Job Posting Reality Score Roadmap Committee

- **Run:** `20260727_job-posting-reality-score-roadmap-committee-v1`
- **Packet:** `PKT-CAREER-JOB-POSTING-REALITY-SCORE-ROADMAP-COMMITTEE-V1-20260727` (committee)
- **Governing sprint:** `SPR-OG-HYGIENE-NORMALIZATION` (career-factory work under recorded sprint exception)
- **Kind:** committee · **Panel:** 8 real subagents (no inline simulation)
- **Closed:** 2026-07-28

## Committee verdict

**PASS WITH CONDITIONS.** Acceptance scorecard (reconstructed from `_SHARED_CONTEXT.md` + charter):
**8 PASS / 7 PARTIAL / 0 FAIL.** P0–P3 are startable immediately; no blockers. Every PARTIAL traces
to one of five MAJOR conditions, each pinned to the phase gate where it comes due (master roadmap §8;
full audit in `PANEL_DISSENT.md`):

- **M1** — build the enumerate Lambda + `RUN_OPEN` manifest (completeness backbone) → **before P5**
- **M2** — close the semantic-bypass in "never fake/real" (slot-filled template) → **before P8 enable**
- **M3** — cumulative/trend + per-segment mass-drop guard → **before P6 done**
- **M4** — split the `current/` prefix (ADR-24 IAM collision) + replay-audit → **P2 IAM / P6 audit**
- **M5** — make the cost fence enforce (Budget Action disables scheduler) → **P0 + every Lambda phase**

None changes the settled architecture; each hardens it.

## Panel (8 seats, all real subagents)

| Seat | Role | Artifacts produced |
|---|---|---|
| STABLE-001 (Analyst) | synthesis | MASTER_ROADMAP, COMMITTEE_VERDICT, PROJECT_CHARTER, REPO_REUSE, PHASED_BACKLOG.tsv, ADR.tsv |
| STABLE-002 (Skeptic) | adversarial audit | PANEL_DISSENT.md |
| ADHOC-AWS-SERVERLESS-ARCHITECT | architecture | REFERENCE_ARCHITECTURE.md |
| ADHOC-CLOUD-SECURITY-IAM-ARCHITECT | security/IAM | SECURITY_AND_THREAT_MODEL.md |
| ADHOC-RELIABILITY-OBSERVABILITY-ENGINEER | reliability | RELIABILITY…RUNBOOK.md, TEST_FAILURE_INJECTION…PLAN.md |
| ADHOC-DATA-ANALYTICS-ARCHITECT | data/analytics | DATA_MODEL…, SCORING…, SOURCE_CONNECTOR… |
| ADHOC-FINOPS-COST-ENGINEER | cost | COST_MODEL_AND_GUARDRAILS.md, SOURCE_REGISTER_PRICING.md |
| ADHOC-PRODUCT-LEARNING-JOURNEY-DESIGNER | learning path | AWS_MANUAL_BUILD_WORKBOOK.md, MANUAL_VS_AUTOMATED_WORK_MATRIX.tsv, EXPANSION… |

Executor-assembled: SOURCE_REGISTER.md, WRITING_TOOL_SELECTION_LEDGER.md, this receipt; and the §8
conditions integration + cross-links in the master roadmap.

## Settled architecture (one line)

EventBridge Scheduler (×2, two-schedule completeness) → SQS collect-queue + DLQ → thin Greenhouse
collector Lambda → immutable S3 (5 tiers, versioning OFF) → Step Functions Standard assemble
(Map/Retry/Catch) → differ (disappearance invariant) → deterministic 6-dimension scoring →
SES digest; CloudWatch A1–A7 → SNS; Bedrock narrator OFF in V1. Modeled **< $5/mo (PASS)**.
Manual console build P0–P8 (the recall telos); IaC deferred to P9; Athena gated to P10.

## Writing-tool discovery (reader-facing standard, LIGHT tier)

`WRITING_TOOL_SELECTION_LEDGER.md`: 1 activated (WT-0015 AI-Cadence Detection, body-read + applied,
no rewrite required), 2 rejected-with-reason after body-read (WT-0023 false-match; WT-0050 Corniness
Boundary — `binding` gate explicitly excludes methods_documents, activation would raise a CAB-005
scope-violation), literary/book-lifecycle sets deferred/rejected on scope.

## FP-08 — downstream packet sequence (recommended, NOT opened)

`PKT-JPRS-CFR-REPO-MIGRATION` → `PKT-JPRS-P0-P1-FOUNDATION` → `PKT-JPRS-P2-P4-COLLECTION-SPINE`
→ `PKT-JPRS-P5-ORCHESTRATION-SFN` → `PKT-JPRS-P6-CHANGE-DETECTION-V1` (V1) → `PKT-JPRS-P7-OBSERVABILITY`
→ `PKT-JPRS-P8-BEDROCK-NARRATOR` → `PKT-JPRS-P9-IAC-RECONSTRUCTION` → `PKT-JPRS-P10-ATHENA-HISTORICAL-INTELLIGENCE`.
Ledger classes affected: `decide` (26 ADRs), `discover` (per-phase recall lessons + the interview-gap
closure), candidate portfolio/deliverable. The verdict RECOMMENDS but does not open these.

## Discovery-carry + capture

- Recognition-retrieval scan run + logged via `record_tool_carry` (`TOOL-IMAGINATION-LAYER-CONSULTING-ENGINE`).
- Surfaced primitive intaked + parked: **CL-997107** — "positive-success-sentinel" (record-of-absence
  vs absence-of-record), with named asymmetry-falsifier (dissolves in a lossless/reversible regime where
  collection cannot fail). Parked (provisional, recovery triggers review/consumption/promotion; holding 2188).
- Capture receipt: **CR-84ab28098392** (`discovery_bearing` / `provisional_parked`).

## Hard-requirement status

- Roadmap-only, no AWS resources created / no application code / no downstream packets opened — **satisfied**.
- 21 required return artifacts present in the write surface — **satisfied**.
- Manual-first preserved (starter pass has no bulk IaC/CLI deploy) — **satisfied**.
- Honesty boundary (behavior+confidence, never fake/real; LLM narrates-never-decides; source-failure ≠
  mass-disappearance) enforced structurally across artifacts — **satisfied** (M2/M3 harden two residual holes).
- No P0 decision left as "ask AI later" (26 ADRs each carry default/owner/trigger) — **satisfied**.

## Executor concern

The packet's declared write surface (`career-factory/outputs/.../runs/…`) is not one of the three
runs-roots that `open_run` scans (`book-factory/runs`, `research-lab/runs`, `discovery-engine/runs`), so
a governance run-marker directory was created under `book-factory/runs/<run_id>/` to satisfy `open_run`
while all deliverables were written to the packet's declared career-factory surface. Not a packet
revision — a spine-satisfaction step. Recommend future career-factory committee packets either target a
runs-root write surface or that `open_run`'s root list include the career-factory outputs tree.

---

JOB_POSTING_REALITY_SCORE_ROADMAP_READY_FOR_OPERATOR_REVIEW
