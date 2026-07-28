# Panel Dissent & Adversarial Audit — Job Posting Reality Score Roadmap

> Seat: `STABLE-002` (the Skeptic). Adversarial audit of the SYNTHESIZED package (the Analyst's one
> architecture + phased roadmap + 26 ADRs), not the initial idea. Roadmap-only committee — this is an
> audit + preserved dissent, not code. Reads: `JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md`,
> `ARCHITECTURE_DECISION_REGISTER.tsv`, `COMMITTEE_VERDICT.md`, `PROJECT_CHARTER_AND_SUCCESS_CRITERIA.md`,
> `_SHARED_CONTEXT.md`, `REPO_REUSE_AND_MIGRATION_DECISION.md`, and the load-bearing appendices
> (`SECURITY_AND_THREAT_MODEL.md`, `DATA_MODEL_AND_HISTORY_SPEC.md`, `RELIABILITY_...RUNBOOK.md`,
> `COST_MODEL_AND_GUARDRAILS.md`, `TEST_FAILURE_INJECTION_AND_ACCEPTANCE_PLAN.md`,
> `SCORING_AND_EVIDENCE_SPEC.md`), plus `SEAT_RETURNS.md` to catch anything the synthesis softened.

---

## (a) Audit verdict

**PASS WITH CONDITIONS.**

The synthesized package is fundamentally sound and internally coherent. One architecture, 26 ADRs each
with a real default + owner + trigger, a genuinely well-designed honesty invariant, and a manual-first
build order that honors the recall telos. **P0–P3 can begin immediately with zero re-architecture.**
There are **no BLOCKERS** to starting.

But seven of the fifteen acceptance points score PARTIAL, and five MAJOR findings must be cleared at the
phase that depends on each before that phase can be called done. The most important: one backbone
component (the enumerate/manifest writer) is unbuilt and unphased; the "never fake/real" guarantee has a
semantic bypass the two guards don't catch; the mass-drop guard is single-step and misses a real
degrading-source pattern; ADR-24's collector-normalize override collides with a shared S3 prefix in a way
that can defeat the least-privilege claim; and the cost fence notifies rather than enforces.

None of these is fatal. All are fixable inside the existing architecture without returning to a model for
a re-decision. Hence pass-with-conditions, not pass, and not no.

---

## (b) Preserved dissent & unresolved decisions (each with DEFAULT + OWNER + DEADLINE/TRIGGER)

No P0 architecture/security/cost/data-integrity decision is left without a default. The items below are
the ones I am **dissenting on or sharpening** past the Analyst's synthesis — each carries the resolution
I want and the gate at which it must be settled.

### MAJOR findings (numbered — risk → where → mitigation/default/owner/gate)

**M1 — The completeness backbone (enumerate Lambda + RUN_OPEN manifest) has no build phase or done-gate.**
- *Risk:* The whole two-schedule completeness model — "manifest-expected sources vs SUCCESS sentinels,
  never wall-clock" (ADR-06) — and the two-silences guarantee (A2/A3 read the manifest) depend on a
  `jprs-enumerate` Lambda that writes the RUN_OPEN manifest and fans out to SQS. It appears in the daily
  flow (roadmap §1), P4 ("target = enumerate Lambda / SQS fan-out"), and P5, but **no phase builds, tests,
  or done-gates it.** P2 builds the collector, P3 the queues, P4 the schedule — all assuming enumerate
  already exists. A fresh executor hits P4/P5 and must design the manifest schema + enumerate handler +
  its failure test from scratch mid-build (a partial violation of acceptance-test #1).
- *Where:* Roadmap §1 daily flow, P4, P5; ADR-06; RELIABILITY §1 ("Dispatcher (Lambda or SFN)").
- *DEFAULT / mitigation:* Add an explicit build unit — either a P4a "Enumerate + RUN_OPEN manifest" step
  or a hard prerequisite inside the P2–P4 collection-spine packet — that stands up the enumerate Lambda,
  the manifest schema (`run_id`, expected `[provider, company]` task set), the SQS fan-out (one msg/company),
  and a test: a source in the manifest that never produces a SUCCESS sentinel reads INCOMPLETE (not quiet),
  and a missing manifest fires A2. Also resolve the open architecture question the reliability seat left
  ("is the Dispatcher a Lambda or an SFN state?") — DEFAULT: a thin Lambda on schedule #1.
- *OWNER:* AI_IMPLEMENTATION (schema + handler) / BRETT_MANUAL_AWS (creates) / architecture seat (Dispatcher form).
- *GATE / DEADLINE:* Must be built and done-gated **before P5** (assembler completeness depends on it).

**M2 — "Never fake/real" has a semantic bypass: the guards are lexical + numeric, not semantic.**
- *Risk:* The narrator is contained on facts (llm-role can't write factual tiers; deterministic post-check
  rejects any date/number not in evidence; feature-flagged OFF in V1). But the post-check only catches
  *unsupported numbers/dates*, and the never-fake guard only catches *banned tokens* (`fake, real, ghost,
  scam, ...`). An LLM narration can emit an **accusatory qualitative claim that contains no banned token
  and no new number** — e.g. "this role appears to be an evergreen listing that may not reflect a genuine
  vacancy," or "unlikely to be actively hiring." That passes BOTH guards and becomes exactly the fake/real
  implication the whole product forbids. SECURITY §6 says "strict JSON schema output"; SCORING §4 allows a
  free-prose "plain-English summary" — the two specs are in tension, and the looser one loses.
- *Where:* SCORING §4–5 vs SECURITY §6; ADR-13; roadmap §4 honesty boundary; P8.
- *DEFAULT / mitigation:* Constrain LLM output to **slot-filling a fixed template of pre-approved
  behavioral sentence frames** (the LLM selects/orders evidence refs; it does not emit free narrative).
  Reconcile SCORING §4 to the SECURITY §6 strict-schema stance. Add a permanent red-team fixture: a
  narration containing a **no-banned-token accusatory paraphrase** must be rejected/fallback-to-template.
- *OWNER:* AI_IMPLEMENTATION (template + post-check) / data+security seats (reconcile the two specs).
- *GATE / DEADLINE:* Before P8 is enabled. (P8 is optional/gated — so this blocks the P8 enable, not V1.)

**M3 — Mass-drop guard is single-step relative; a cumulative bleed or silent-subset SUCCESS produces
real-looking `disappeared`.**
- *Risk:* The guard trips on "drop to zero or >60% vs the prior SUCCESS" (ADR-10, DATA §5/F2, RELIABILITY
  §5.2) — a **single-step** comparison. Two failure shapes slip through: (1) a **cumulative sub-threshold
  bleed** — a source drops ~50% one day (under 60%, not SUSPECT, becomes the new SUCCESS baseline), then
  ~50% again the next day; each step is legitimate-looking, grace N=2 is satisfied, and a large fraction is
  declared `disappeared` over two days without ever tripping SUSPECT; (2) a **silent-subset SUCCESS** — the
  ATS returns a well-formed 200 that silently omits one department's jobs (parse succeeds → status SUCCESS,
  not PARTIAL), a <60% drop → real `disappeared` events for jobs that never actually closed.
- *Where:* DATA §5.4/§9-F2, RELIABILITY §5.2, ADR-10.
- *DEFAULT / mitigation:* Add a **cumulative/trend check** alongside the single-step one — e.g. SUSPECT if
  cumulative shrink exceeds threshold over a rolling window, or on a sustained multi-day monotonic decline —
  and, where the ATS exposes department/team segmentation, a per-segment completeness check. Add an
  acceptance test for the two-day 50%+50% bleed and the silent-subset case.
- *OWNER:* AI_IMPLEMENTATION (differ gates) / data+reliability seats (threshold shape).
- *GATE / DEADLINE:* Before P6 done (the invariant is P6's central honesty test).

**M4 — ADR-24 collector-normalize override + the shared `current/` prefix can defeat least-privilege.**
- *Risk:* ADR-24 overrode the security seat's cleaner 3-role split (collector → raw-only) in favor of a
  collector that also writes `normalized/` + `current/_source_status.json`. On its own that is defensible
  (see the explicit ADR-24 ruling in section (c)). The sharper problem the synthesis did not surface: the
  **differ** writes `current/current_jobs.json` (the authoritative live-job set the diff trusts) and the
  **collector** writes `current/_source_status.json` — **both under the same `current/` prefix.** S3 IAM
  scopes by prefix, not by filename/suffix, so a `current/*` grant to the collector also grants it write to
  `current_jobs.json`. A compromised or buggy collector could then rewrite the authoritative live set
  directly — the exact blast radius the one-directional flow exists to prevent.
- *Where:* ADR-24, DATA §7 (S3 layout), SECURITY §2 (the overridden 3-role table), roadmap §5.
- *DEFAULT / mitigation:* (a) **Split `current/` into two prefixes** — `status/` (collector-only) and
  `current/` (differ-only) — so prefix-scoped IAM actually enforces the boundary; (b) add a **replay-audit
  control** (CI or periodic assert that `normalized/` == `normalizer(raw/)`) as the compensating control
  for the widened write scope; (c) keep ADR-24's split-to-dedicated-processor trigger AND add: **any
  normalizer parse-exploit finding, OR any observed divergence of `normalized/` from `raw/`, forces the split.**
- *OWNER:* AI_IMPLEMENTATION (policy shapes + audit) / security seat (boundary) / BRETT_MANUAL_AWS (attaches).
- *GATE / DEADLINE:* Prefix split + IAM shape before **P2** (collector role) and **P6** (differ role);
  replay-audit control before P6 done.

**M5 — Cost guardrails notify rather than enforce, and log-retention discipline is drift-prone.**
- *Risk:* The <$5 verdict is honest at V1/Useful (genuinely pennies) and holds at Expansion *only with
  G4/G5/G6/G8 active* — but two of those are notify-not-enforce or manual-and-drifting: (1) the "$10 ceiling
  Budget **action**" is "SNS notify; **optional** stop-scheduler" (COST G1) — i.e. it emails, it does not
  stop spend; Budgets is daily-granularity + lag, so a runaway (recursive fan-out, misconfigured
  minute-cron) can overspend before a human reacts; (2) G4's 30-day log retention is **manual per log
  group**, and every NEW Lambda a phase adds gets a log group that defaults to **Never-Expire** — so
  retention drifts open as the build grows; (3) custom-metric/alarm cost is UNVERIFIED (see U3).
- *Where:* COST G1/G4, ADR-16/17, roadmap §7.
- *DEFAULT / mitigation:* Wire the $10 Budget **Action to actually disable the EventBridge scheduler**
  (Budgets Action → SSM automation / IAM policy) rather than "optional"; make "**set finite (30-day) log
  retention on this function's log group**" an explicit line in **every** Lambda phase's manual steps +
  done-gate (P2, P5, P6, P7, P8); verify custom-metric cost (U3) before Expansion. State plainly that the
  real cost *enforcement* is G8 (excluded-service ban) + reserved concurrency + no always-on — Budgets is a
  reactive backstop, not a cap.
- *OWNER:* BRETT_MANUAL_AWS (Budget action + retention) / AI_IMPLEMENTATION (SSM automation, config).
- *GATE / DEADLINE:* Budget action + P0 retention baseline at P0; per-Lambda retention at each Lambda phase;
  custom-metric verify before Expansion.

### MINOR findings (recorded, low urgency)

- **m1 — Cold-start / first-run diff behavior is unspecified.** No prior SUCCESS snapshot exists on a
  source's first run. The correct behavior (all jobs `first-seen`, zero removals, grace clocks initialized,
  mass-drop guard has no baseline so is inert) is implied but never stated or tested. *Default:* add an
  explicit first-run rule + acceptance test. *Owner:* data seat. *Trigger:* P6.
- **m2 — De-configuring a company leaves stale `current/` state silently.** Remove a company from SSM
  config → enumerate stops emitting its task → it drops out of the manifest → never INCOMPLETE, never
  `disappeared`, but its last-known jobs linger in `current/` and could be miscounted by a later historical
  query. No false disappearance (correct), but a silent-staleness path. *Default:* make company removal an
  explicit **archive** action that retires the source's `current/` state. *Owner:* operator + data seat.
  *Trigger:* first time a company is removed / at P10 history design.
- **m3 — SES sandbox not called out.** SES starts in sandbox (send only to verified addresses). For a
  single self-recipient this is fine and needs no production-access request — but the roadmap never says so,
  and an executor may burn time requesting production access. *Default:* verify Brett's own recipient
  identity in sandbox; no production-access request in V1. *Owner:* BRETT_MANUAL_AWS. *Trigger:* P6/P7.
- **m4 — PII redaction is a manual pre-publish pass, not pipeline-enforced.** Fine for V1 (single private
  email recipient, no public artifact). Becomes load-bearing at first public/portfolio artifact. *Default:*
  redaction pass before any public artifact (ADR-19 already says this). *Owner:* AI_IMPLEMENTATION + operator.
  *Trigger:* first public artifact.

---

## (c) ADR-24 override assessment (explicit)

**Decision under review:** ADR-24 overrode the security seat's stricter 3-role split — collector writes
`raw/*` ONLY, a separate processor-role reads raw and writes normalized/processed, reporter reads processed
and writes reports (SECURITY §2, "Collection can write raw and enqueue, nothing else") — in favor of a
**collector that also normalizes**, writing `raw/ + normalized/ + receipt + current/_source_status.json`.

**Ruling: the override is ACCEPTABLE for V1, conditioned on M4's mitigations. It is a real
least-privilege regression versus the security seat's design, and it must be recorded as such — not
papered over.**

Why acceptable:
- The one-directional flow is **preserved in the load-bearing direction**: the collector still writes only
  *forward* tiers (raw → normalized) and still **reads nothing derived** (no read on events/reports/current
  job set). It cannot exfiltrate or act on downstream product state. "No component both writes raw and reads
  reports" still holds.
- `normalized/` is **regenerable from immutable `raw/`** by replay (DATA §6). A corrupted normalized write
  is recoverable and auditable — it is not the court-of-record. `raw/` stays write-once (no DeleteObject),
  so the irreplaceable tier's immutability is untouched by the override.
- The threat surface is small and trusted: a thin collector, inputs only from sanctioned public read-only
  ATS GET APIs behind an SSRF host-allowlist (T9), single account, single operator.
- ADR-24 already carries the correct escape hatch: "Normalize logic grows heavy or needs separate IAM
  blast-radius → split into a dedicated processor Lambda (security seat's tighter boundary)."

Why it must carry conditions (M4):
- It **widens the collector's S3 write scope** and, worse, the synthesis did not notice that the collector's
  status object and the differ's authoritative `current_jobs.json` **share the `current/` prefix** — which
  prefix-scoped S3 IAM cannot cleanly separate. Absent the M4 prefix split, the collector effectively gains
  write to the live-job set, which is the specific escalation the security seat's split was designed to
  prevent. The prefix split + the `normalized == normalizer(raw)` replay-audit are the compensating controls
  that make the override safe; **the override is conditionally approved only with them.**
- Add to ADR-24's trigger: *any normalizer parse-exploit finding, OR any observed divergence of
  `normalized/` from `raw/`, forces the split to the dedicated processor.*

---

## (d) Carried UNVERIFIED items as named risks (with the resolving gate)

These were flagged UNVERIFIED by the seats and carried into the synthesis. None is a <$5 breaker or an
invariant breaker at V1 scale, but each must be resolved at the named gate before it becomes load-bearing.

| # | UNVERIFIED item | Source | Load-bearing? | Resolve at gate |
|---|---|---|---|---|
| U1 | SQS visibility timeout ≥ 6× function timeout "best practice" | ADR-25, RELIABILITY §3 | Only sets a number | Confirm vs Lambda ESM docs at **P3** build |
| U2 | EventBridge Scheduler native missed-run metric + Scheduler DLQ/retry (A8) | RELIABILITY §0/§6 | No — A2 custom heartbeat is provider-agnostic | Confirm before relying on A8, at **P4** |
| U3 | Custom CloudWatch metric/alarm cost under free tier | COST §7, RELIABILITY OQ | Could add a few $ at Expansion | Verify before **Expansion** / at **P7** |
| U4 | Ashby URL-slug UUID permanence | DATA §9-A4/D3, SECURITY §0 | Yes for Ashby identity | Verify **before Ashby onboarding** (Ashby already GATED) |
| U5 | Lever `createdAt` reliability (undocumented) | DATA §9, connector spec | No — dates-are-ours makes it evidence-only | Confirm at **Lever onboarding** |
| U6 | Greenhouse/Lever/Ashby GET rate limits + ToS | SECURITY §0, connector spec | ToS risk if a low limit exists | Self-throttle + UA + 429 now; re-verify per provider **before scaling fan-out** |
| U7 | Bedrock Haiku/Sonnet token pricing + "Sonnet-5 promo $2/$10 thru 2026-08-31" | COST, SOURCE_REGISTER_PRICING | Yes for Bedrock cost | Re-pull **before enabling/scaling Bedrock (P8)** |
| U8 | SQS $0.40/1M, SNS email $2/100k, S3 secondary rates | COST | Immaterial at V1 | Re-verify **before Expansion** |
| U9 | Athena `injected` vs `enum` board partition projection | DATA §8 | Only at analytics | Confirm at **P10** table creation |

---

## (e) Conditions to clear before implementation

**Before starting (P0):** none. P0–P3 are fully decided and safe to begin.

**Before P2 done:** M4 — split `current/` into `status/` (collector) + `current/` (differ) so IAM prefix
scoping enforces the collector boundary; scope the collector role accordingly.

**Before P5:** M1 — build + done-gate the enumerate Lambda + RUN_OPEN manifest (+ resolve Dispatcher form).

**Before P6 done:** M3 — add cumulative/trend mass-drop check + silent-subset test; M4 — replay-audit
(`normalized == normalizer(raw)`) control; m1 — cold-start first-run rule + test.

**Before P7 done:** M5 — per-Lambda finite log retention as a done-gate line; wire the $10 Budget action to
disable the scheduler.

**Before P8 is enabled (optional):** M2 — template-constrained LLM output + no-banned-token accusatory-
paraphrase red-team fixture; reconcile SCORING §4 to SECURITY §6.

**Before Expansion:** U3, U6, U7, U8 re-verification.

---

## 15-point acceptance-test scorecard

> **Note on provenance:** the packet's literal 15-point acceptance list is **not present in this run dir**
> (searched — only the per-seat acceptance tests, the charter's 5 usefulness criteria + 6 minimum-report
> points, and the verdict's coverage map are here). I reconstruct the 15-point test from the **binding hard
> constraints in `_SHARED_CONTEXT.md`** + the charter + acceptance-test #1 as given in my brief, and score
> each against the actual artifacts. If the canonical 15 differ, re-map — the evidence per row stands.

| # | Acceptance point (reconstructed from binding constraints) | Score | Evidence / gap |
|---|---|---|---|
| 1 | Fresh executor can begin P0 without re-deciding architecture | **PARTIAL** | P0/P1 fully decided; but M1 (enumerate/manifest unbuilt) + M4 (current/ IAM) force mid-build design at P4–P6 |
| 2 | Every P0 decision has real default + owner + trigger (no "ask AI later") | **PASS** | 26 ADRs spot-checked; all P0 rows carry default/owner/trigger |
| 3 | Collection→assembly contradiction resolved with default + upgrade + trigger | **PASS** | ADR-06: two-schedule default, Choice+Wait barrier as named upgrade, explicit switch triggers |
| 4 | Source failure never masquerades as mass disappearance | **PARTIAL** | Strong SUCCESS-precondition + grace + guard; but M3 (single-step guard) misses cumulative bleed / silent-subset SUCCESS |
| 5 | "Nothing changed" ≠ "collectors didn't run" (two silences) | **PARTIAL** | Design airtight (sentinel tier + A2 + manifest); but the enforcing component (M1 manifest writer) is unbuilt/unphased |
| 6 | LLM never becomes the silent factual authority | **PARTIAL** | Factual-tier lockout is airtight; M2 semantic accusatory-narrative path bypasses lexical+numeric guards |
| 7 | Never claims fake/real | **PARTIAL** | Banned-token guard real but defeatable by paraphrase (same root as M2) |
| 8 | Cost < $5/mo with guardrails wired to enforce | **PARTIAL** | Verdict honest; but M5 (budget notifies-not-enforces, retention drift) + U3/U7 unverified |
| 9 | Manual-first integrity — no IaC/CLI bulk deploy in starter | **PASS** | ADR-18 firm; IaC gated to P9; console-by-hand P0–P8; no CLI bulk-deploy sneaks in |
| 10 | Least-privilege IAM, one-directional flow, no public exposure | **PARTIAL** | BPA/TLS/boundary/no-Resource:* solid; but M4 widens collector write + current/ prefix collision |
| 11 | Sanctioned public ATS APIs only; no scraping/harvesting/auto-apply | **PASS** | Charter §3, SECURITY §8, connector spec; forbidden list explicit and enforced |
| 12 | S3 immutability without versioning (write-once keys + lifecycle) | **PASS** | ADR-23; versioning OFF, no DeleteObject on raw/, lifecycle expiry; overwrite-failure exercised at P1 |
| 13 | SQS/DLQ recall lab present, targets the interview gap | **PASS** | P3 + TEST_PLAN §2 fully specified end-to-end (poison→DLQ→redrive + low-VT dup) |
| 14 | Each phase has a checkable done-gate + intentional failure | **PASS** | All 11 phases (P0–P10) carry observable done-gates + an induced failure |
| 15 | Dual telos honored — value + no-notes recall per phase | **PASS** | Every phase pairs a deliverable with a "no-notes explanation"; charter §1 both-telos-equal |

**Tally: 8 PASS · 7 PARTIAL · 0 FAIL → PASS WITH CONDITIONS.**

---

## Disagreement preserved (not papered over)

I am recording, against the Analyst's "all P0 decisions settled, none left to AI" framing, that:
- The synthesis **dropped** the security seat's cleanest artifact (the 3-role collector→raw-only split) via
  ADR-24 without surfacing the shared-`current/`-prefix consequence that partially re-opens the exact
  escalation the split prevented (M4).
- The synthesis **softened** the "never fake/real" guarantee to lexical + numeric checks that a semantic
  paraphrase defeats (M2) — SCORING §4 and SECURITY §6 disagree with each other and the looser wins.
- The synthesis **assumed** a backbone component (enumerate/manifest) into existence without a phase to
  build it (M1).
These are conditions, not blockers. The package is worth building — with the section (e) conditions cleared
at their gates.
