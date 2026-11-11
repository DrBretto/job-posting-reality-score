# Radar end-to-end repair — delivery, open discovery, duty-first screening

Governed by `PKT-CAREER-RADAR-END-TO-END-REPAIR-V1-20261111`; run of record
`../Infotropy Book/book-factory/runs/20261111_career-radar-end-to-end-repair-v1/`.
Branch `ai/radar-end-to-end-repair`; its first commit (`3712321`) records the deployed-but-uncommitted
baseline (working-tree `src/` byte-identical to the live package, CodeSha256 `WQyYJv…`).

## Context

- **No report since 2026-10-09.** All 33 scheduled assemble executions 2026-10-10 → 2026-11-11 FAILED:
  `BuildReport` timed out at 300 s four times (one try + three retries of a deterministic timeout),
  then `ReportIncomplete` ran the identical full assembly and timed out too. ~25 min per failed day.
- **Cause, measured:** report compute is roughly linear in the population (~80–100 s per 1,000
  postings on Lambda at 512 MB), and the population is now dominated by discovery's 21-day retention
  window: 1,526 (09-30) → 3,143 (10-09) → **4,671 (11-11)** = 592 monitored + 4,079 discovery-carried.
  Local replay of 11-11 on the deployed code: 51.3 s (S3 6.3 s). Top costs: `cold_start_sources`
  recomputed for every rendered row (15.5 s, 26M `set.add`), screening 18.5 s, ownership 9.0 s,
  scoring 6.1 s, render 10.7 s.
- **The degraded path cannot degrade.** `mode: incomplete` is ignored by the handler; it repeats the work
  that just timed out. The only failure alarm watches a metric nothing publishes.
- **Title veto.** `_NON_TARGET_TITLE_RE` matches `analyst`; with no technical word in the title it sets
  `blocked_role`, zeroing fit and barring ownership retention, whatever the duties say.
- **Policy drift.** Voice/telephony exclusion (10-17) and the human-first rule (10-12) post-date the
  screening code; `policy-check` reports four stale sources.
- **Discovery** is four remote-tech feeds; the 15-board Greenhouse registry is still the collection-health
  headline and the only per-employer route.

## Plan

1. [ ] Delivery: memoize per-report invariants; measure; profile the remaining hot path; resize the
   report function on measured evidence; no retry on deterministic timeout; real degraded mode that
   publishes without the full-stock work; failure alarm on a metric that is actually emitted.
2. [ ] Duty-first screening: soft non-target titles defer to established engineering duties; voice /
   telephony exclusion; human-first holds (pre-interview evaluations are held, not rejected);
   PQ-166 (TN, internal helpdesk) verified.
3. [ ] Open discovery: HN "Who is hiring" founder/direct connector (keyless, one request); company-first
   financing signals (SEC EDGAR Form D) as a research watchlist that never enters the shortlist.
4. [ ] Registry disconnected: discovery-only rounds publish and reach review; health no longer uses the
   fixed registry as a market proxy.
5. [ ] Tests, full suite, `sam validate`, clean build, release diff, rollback, live search sample.

## Execution Log

- 2026-11-11: baseline commit; production state and replay recorded in the run directory.

## Follow-ups

- Adzuna (general U.S. search) still needs a free developer credential; isolated to that source.
