# Expansion & Product Evolution — Job Posting Reality Score

> Seat: `ADHOC-PRODUCT-LEARNING-JOURNEY-DESIGNER`.
> How the product grows from "save postings, tell me what changed" to expected-return intelligence —
> **each increment gated on an ACTUAL NEED, never on "the diagram looks unfinished."** No overclaiming
> that posting behavior proves a job is fake or real, at any increment.

## Two things grow in lockstep

Every increment does double duty (the dual telos): it adds **daily job-search value** AND it is a
**self-guided AWS recall exercise**. The gate for building the next increment is always the same shape:
*is there a real need this increment serves that the current one does not?* If the answer is "not yet,"
Brett keeps using the current increment in his search and does not build ahead of need.

**Count is an output, not a target.** The increments below are the natural shape of the growth, not a
quota to fill. If Brett gets durable job-search value and enough recall from V1 + V1.5 and never needs
the mature tier, that is a success, not an unfinished project.

---

## V1 — Job Radar: "save postings daily, tell me what changed"

**Built by:** Phases 0–7 (guardrails → S3 → collector → SQS/DLQ → scheduler → orchestration → change
detection → observability).

**User value (what Brett gets in his daily search):**
- Every morning, a report of what materially changed across his selected companies: **new** postings
  (with first-seen date), **disappeared** postings, and **materially-changed** postings — each traceable
  to stored snapshots.
- A trustworthy negative: "nothing changed today" that he can rely on *because* the system separately
  tells him the collectors actually ran. No false "everything vanished" from a source outage.
- Concretely feeds the LinkedIn-first plan's "apply within 72 hours of posting" target: he sees new
  high-fit roles the day they appear, at the companies he cares about, without refreshing job boards.

**Recall value:** the whole serverless spine by hand — the exact SQS/DLQ path he blanked on, plus
Lambda execution roles, EventBridge scheduling, Step Functions error isolation, and CloudWatch alerting.

**Honesty boundary:** describes observable posting behavior only. Never asserts a job is fake, real,
active, or deceptive.

**Actual-need gate to START V1:** already met — the LinkedIn plan explicitly calls to rebuild the
job-searcher around *live openings* and Brett needs day-of-posting awareness at target companies.

---

## V1.5 — Bedrock Change Digest: "tell me what changed, in plain English"

**Built by:** Phase 8 (optional Bedrock summary layered on the deterministic diff).

**User value:**
- The same deterministic change report, narrated as a short daily digest he can read in 30 seconds
  ("2 new Applied-AI roles at X; the Zapier posting's requirements changed") — lower friction, so the
  radar actually gets read every day.
- Reuses the existing CFR Bedrock wrapper, so it's cheap incremental work.

**Recall value:** Bedrock `invoke_model`, model-access management, and token/cost ceilings — plus the
discipline of an LLM that narrates but never decides.

**Honesty boundary (tightened here because an LLM is involved):** the summary is generated *from* the
deterministic diff and cites the same snapshot evidence. The LLM is NEVER the source of a fact and
NEVER decides whether a posting disappeared or is real/fake. Behavior language only.

**Actual-need gate:** build ONLY if (a) the V1 deterministic report is trusted and in daily use, and
(b) Brett finds the raw structured report high-friction enough that he skips reading it. If he already
reads the V1 report happily, V1.5 is optional decoration — skip it. If skipped, nothing downstream breaks.

---

## V1.75 — IaC Reconstruction: "rebuild the whole stack from code"

**Built by:** Phase 9 (SAM/CDK reconstruction), positioned deliberately AFTER hands-on mastery.

**User value:**
- Reproducibility: the whole system becomes a template Brett can deploy/tear down in one command,
  and version in git — which is itself an interview-defensible artifact ("here's my serverless stack as
  code, and I can narrate every resource from having built it by hand first").
- Clean teardown/redeploy for cost hygiene and for demoing.

**Recall value (the reconstruction TEST):** this is where manual recall is *proven*. Brett maps every
hand-built resource to a template block; any block he can't trace back to a console screen exposes a gap
he only half-learned — that block goes back to a console refresher before he accepts the generated IaC.
**This is why IaC is late, not early: the console work must happen first, or there's no recall to prove.**

**Honesty boundary:** unchanged; IaC is structural, not analytical.

**Actual-need gate:** build ONLY after V1 has run reliably by hand for long enough that Brett has
observed and broken each resource. IaC before that inverts the telos (it would automate away the very
console work whose purpose is to rebuild recall) — explicitly forbidden by the manual-first constraint.

---

## MATURE — Historical Intelligence: "where is my effort most likely to pay off?"

**Built by:** Phase 10 (Parquet + Athena) plus the analytics layer on accumulated history.

**User value:**
- Uses accumulated first-seen dates, repost patterns, change frequency, hiring momentum, role-fit, and
  (eventually) his own application outcomes to surface **where hiring activity appears strongest and
  where effort is most likely to pay off** — an expected-return read to prioritize the finite weekly
  application budget from the LinkedIn plan.
- Turns the radar from "what changed today" into "where should I spend Tuesday."

**Recall value:** columnar Parquet, partitioning as the cost lever, serverless SQL over S3, and the
DDL-by-hand discipline (no paid Glue crawler).

**Honesty boundary (most important at this tier):** every output is framed as *observed behavior and
evidence summary*, never a truth claim. Hiring momentum is not a promise of a hire; a repost is not proof
of a fake job; a disappeared posting is not an accusation. The analytics rank *where the observable
evidence is strongest*, not *which jobs are real*. AI may summarize evidence but may not invent dates or
become the silent factual scoring authority — every number points back to stored snapshots.

**Actual-need gate:** build ONLY when BOTH are true: (a) enough history has accumulated to query
meaningfully (weeks-to-months of daily snapshots — you cannot warehouse data you haven't collected yet),
and (b) Brett has a real analytical question the V1 daily report can't answer ("which of my 15 companies
is actually accelerating hiring in my lane?"). Building the warehouse before there's data or a question
is the "add a service to make the diagram impressive" anti-pattern the shared context forbids.

---

## Scale gates (from the shared-context reference points)

| Increment | Scale | Trigger to expand scale |
|---|---|---|
| V1 learning | 1 ATS provider + 3 companies, 1 daily run | Start here; prove the spine end-to-end |
| V1 useful | 3 ATS providers (Greenhouse/Lever/Ashby) + 10–20 companies | Once the spine is trusted and Brett wants real coverage of his target list |
| Mature | ~100 companies + historical analytics | Only when Brett has a real prioritization problem across a large target set AND accumulated history to analyze |

Adding companies/providers is config, not new architecture — do it when his target list actually grows,
not to hit a number. Sourcing stays on **sanctioned public ATS APIs only** (Greenhouse/Lever/Ashby); no
authenticated/LinkedIn scraping, no contact harvesting, no auto-apply, at any increment.

---

## The one-way doors to avoid (so growth stays cheap and honest)

- **Never** flip to always-on infra (RDS/NAT/EC2/OpenSearch) for analytics — Athena-on-S3 stays
  serverless and pay-per-query. If an increment seems to *need* always-on infra, STOP and surface to the
  operator; it's a design smell, not a step.
- **Never** let the LLM layer (V1.5/mature) drift from narrator to authority. The deterministic diff is
  always the source of truth; the model always cites it.
- **Never** build the mature warehouse ahead of accumulated data — the history IS the moat, and it only
  exists after V1 has been running.
- **Never** collapse the "nothing changed" / "didn't run" distinction as the product grows — every tier
  inherits that guarantee.
