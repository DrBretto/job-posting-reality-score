# Committee Verdict — Job Posting Reality Score Roadmap

> Settled by `STABLE-001` (Analyst) from six specialist seats (architecture, security, reliability,
> data, cost, product-learning). Roadmap only — no AWS resources, no application code. This verdict
> **recommends** the downstream packet sequence below; it does **not** open any of them.

## 1. The one architecture

A single-account **us-east-1** serverless system. **EventBridge Scheduler (two schedules: collect,
then assemble-after-offset) → collection via SQS + DLQ fan-out to a thin Greenhouse collector Lambda
writing immutable S3 snapshots → Step Functions Standard assembler (Map + Retry + Catch) diffing
against the most-recent-SUCCESS snapshot and reporting what changed → SES digest.** Storage is
**S3-only, one bucket, versioning OFF, five tiers** (`current/ raw/ normalized/ events/ reports/`),
immutability by write-once keys + lifecycle. No DynamoDB, no always-on infra, Bedrock a separate
feature-flagged `llm-role` Lambda OFF in V1. Modeled **< $5/mo**. Full topology + rationale:
`REFERENCE_ARCHITECTURE.md`; full build: `JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md`.

## 2. Phase plan at a glance

P0 Guardrails → P1 S3 → P2 Collector Lambda → P3 SQS+DLQ (recall lab) → P4 Scheduler → P5 Step
Functions → **P6 Change Detection = V1 deliverable** → P7 Observability → P8 Bedrock (opt) → P9 IaC
reconstruction → P10 Athena (mature). Manual console P0–P8; IaC withheld to P9. V1 = P0–P7. Increments
gated on actual need. Backlog: `PHASED_IMPLEMENTATION_BACKLOG.tsv`.

## 3. Headline decisions (full register: `ARCHITECTURE_DECISION_REGISTER.tsv`)

- **Collection→assembly boundary (the load-bearing contradiction): TWO SCHEDULES** default — collect,
  then assemble at a fixed offset, completeness judged by manifest-expected vs SUCCESS sentinels.
  Single-execution Choice+Wait barrier is the named upgrade, not a rejection. Both keep SFN Standard
  so P5's execution-history recall value is preserved either way.
- **Bedrock = separate `llm-role` Lambda, OFF in starter** (blast-radius; can't write factual tiers).
- **Greenhouse first; Ashby gated** on URL-slug UUID permanence verification; Lever second.
- **Grace = 2 consecutive SUCCESS snapshots; mass-drop >60%/zero = SUSPECT** (removals suppressed);
  `disappeared` fires only from a SUCCESS snapshot — source failure never reads as mass disappearance.
- **S3-only, versioning OFF, immutability by unique key + lifecycle**; DynamoDB only at explicit triggers.
- **Deterministic scoring, 6 inspectable dimensions, UNKNOWN first-class, never fake/real**; LLM
  narrates-only with a post-check that rejects unsupported dates/numbers.
- **Manual console build is the recall telos; IaC at P9 only**; SSE-S3, SSM Parameter Store, Budgets
  $5/$10, 30-day log retention, permissions boundary on every exec role.
- Every P0 architecture/security/cost/data-integrity decision has a real default + owner + trigger —
  **none left "ask AI later."**

## 4. Acceptance-test status

All acceptance tests are **DEFINED, NOT YET RUN** (roadmap stage — no resources exist). They are
carried into implementation as gates. Coverage confirmed across seats:

- Architecture (`REFERENCE_ARCHITECTURE.md` §11): isolation, mass-removal safety, two-silences, DLQ+
  redrive, idempotency, versioning-off, barrier/offset, cost.
- Reliability (`TEST_FAILURE_INJECTION_AND_ACCEPTANCE_PLAN.md`): idempotency dup, invariant matrix,
  retry-ownership boundaries, each alarm A1–A7 individually drivable, byte-comparable replay from raw,
  teardown-zero.
- Data (`DATA_MODEL_AND_HISTORY_SPEC.md` §9): the invariant (T1), PARTIAL freeze (T2), grace (T3),
  outage-through-grace (T4), content-hash (T5), field events (T6), repost (T7), full-drop guard (T8),
  replay (T9), dates-are-ours (T10).
- Scoring (`SCORING_AND_EVIDENCE_SPEC.md` §7): decomposability, determinism, evidence-linkage,
  LLM-boundary, never-fake, UNKNOWN honesty, exclusion, versioned replay.
- Connector (`SOURCE_CONNECTOR_AND_COMPLIANCE_SPEC.md` §6): auth-none, id-mapping, failure-labeling,
  receipt-before-parse, no-removal-from-connector, field-completeness.
- Cost (`COST_MODEL_AND_GUARDRAILS.md`): AT1–AT8 (model reconciles, budget fires, versioning off,
  finite log retention, Athena cutoff, tag coverage, Bedrock off, tag-based teardown → ~$0).

Each phase in the master roadmap embeds its intentional failure + done-gate; these are the executable
acceptance surface for the downstream packets.

## 5. Recommended downstream packet sequence (FP-08 — named, NOT opened)

This verdict recommends the following executable packets to carry the roadmap into implementation. It
does **not** open them; sequencing and authoring are the OG's call.

1. `PKT-JPRS-CFR-REPO-MIGRATION` — stand up the NEW `job-posting-reality-score` repo; extract the CFR
   Bedrock wrapper (reuse-unchanged) + config pattern (adapt); rebuild domain models. (Prereq for all.)
2. `PKT-JPRS-P0-P1-FOUNDATION` — account guardrails + IAM identity/boundary + S3 record substrate.
3. `PKT-JPRS-P2-P4-COLLECTION-SPINE` — collector Lambda + SQS/DLQ recall lab + EventBridge Scheduler.
4. `PKT-JPRS-P5-ORCHESTRATION-SFN` — Step Functions assembler + the two-schedule boundary.
5. `PKT-JPRS-P6-CHANGE-DETECTION-V1` — differ + change-event model + honest report + scorecards (**V1**).
6. `PKT-JPRS-P7-OBSERVABILITY` — alarms A1–A7 + SNS + dashboard.
7. `PKT-JPRS-P8-BEDROCK-NARRATOR` — optional, gated on a trusted V1 report.
8. `PKT-JPRS-P9-IAC-RECONSTRUCTION` — SAM/CDK round-trip + CI.
9. `PKT-JPRS-P10-ATHENA-HISTORICAL-INTELLIGENCE` — mature analytics, gated on accumulated history.

Each packet inherits the honesty boundary, the guardrail set, and the manual-first (BRETT_MANUAL_AWS /
AI_IMPLEMENTATION / SHARED_VERIFY) division of labor.

## 6. Ledger classes affected (recommendation only)

- **Decision ledger** — the 26 ADR rows (`ARCHITECTURE_DECISION_REGISTER.tsv`), especially the P0
  defaults and the two-schedule vs barrier resolution + its switch trigger.
- **Learning-capture ledger** — the per-phase recall lessons; in particular the SQS/DLQ interview-gap
  closure (P3), the "function's role not my creds" AccessDenied reflex (P2), and the two-silences
  honesty test (P6).
- **Candidate portfolio / deliverable ledger** — this roadmap package as the career-factory candidate
  artifact for Brett Westerlund; the eventual V1 stack + IaC template as interview-defensible outputs.

This committee recommends but does not open downstream packets or write ledger entries.
