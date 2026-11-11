# Report runtime recovery and confirmed-history reconciliation

Packet: `PKT-CAREER-REPORT-RUNTIME-AND-CONFIRMED-HISTORY-RECOVERY-V1-20260928`
Run: `20260928_career-report-runtime-and-confirmed-history-recovery-v1`
Started 2026-09-29, deployed 2026-09-30.

## Context

Two separate problems, neither caused by the other.

**1. The morning report has not finished since 2026-09-26.** `jprs-report` exhausts its 90-second
timeout. The scheduled 09:00 assembly failed on 09-27, 09-28 and 09-29, each time with
`Sandbox.Timedout` after five attempts at exactly 90.00s. There is no `daily_report` in S3 for any
of those days. The last success used **80.08s of its 90-second budget** on 813 postings — 89%
consumed on the run recorded as the recovery's success — and nothing read that number.

The prior run (`20260928_career-radar-release-and-history-reconciliation-v1`) found this and was
forbidden by its own packet from touching infrastructure, so it reported it:
`findings/FINDING-01-report-lambda-exceeds-its-90s-timeout.md`.

**2. Five confirmed applications were absent or wrong in the application-history projection.** The
projection was rebuilt on 2026-09-28 at 19:32; the run that made three more submissions closed at
20:35. Grafana Labs Staff AI Engineer was recorded as prepared-and-handed-over when the operator had
in fact completed and submitted it and the employer had confirmed on 09-27. AWeber and BetterHelp
were submitted and employer-confirmed on 09-28 and appear nowhere in the projection — and **both are
still open on their employers' own boards**, so the next report that ran would have announced roles
that already have applications in them.

Underneath (2) is a parser defect. The 2026-09-28 release predicted a fourth acceptance format and
promised a section it could not read would be "held and named rather than dropped". The format
arrived the same evening and **all four sections of that log were dropped in silence** — the guard
required either a `URL:` line or a heading ending in a bare `SUBMITTED`, and
`· **SUBMITTED, employer-confirmed**` is neither.

## Plan

- [x] Capture a recoverable production baseline: stack, function config, processed template, recent
      executions, report objects, schedules, artifact retention.
- [x] Establish whether the timeout is expensive work, a wait, or a hang — measured, not assumed.
- [x] Reconcile the confirmed applications through the existing `history-refresh` pathway, from an
      append-only confirmation record under the run's own application folder.
- [x] Repair the submission-log reader so an unreadable section is visible rather than dropped.
- [x] Regressions: held-then-confirmed on one requisition; another role at the same employer
      unaffected; the bold-decoration drop; the runtime readout.
- [x] Prepare the smallest capacity fix — `ReportFunction` Timeout only, ≤300s, memory unchanged.
- [x] Leave a runtime/headroom readout so the margin is visible before it is gone.
- [x] Independent review of the delta, then deploy on explicit operator approval and verify in
      production with real data.

## Execution Log

**Diagnosis — it is computation, and the logs could not have told anyone that.** The report Lambda
emits nothing between `START` and its timeout, so CloudWatch cannot separate work from waiting. A
read-only harness (`evidence/measure_report_stages.py`) ran the deployed code path against live
production S3 and timed each half:

| | seconds |
|---|---|
| `assemble_report_input` wall | 20.6 |
| — of which S3, across 55 calls | 4.2 |
| — of which computation | 16.4 |
| `render_report` | 0.7 |
| **total wall** | **21.3** |

Population 1,344 postings. `user 16.47s / 76% cpu` — single-threaded and CPU-bound. **Memory is not
the constraint**: peak use in production is 188–192 MB of 512.

**The mechanism is quadratic.** Profiling put `normalize_employer` at **3,613,995 calls** for 1,344
jobs — 2,689 per job. `src/common/dedup.py` runs `for job in kept: for other in kept:` and calls
`normalize_employer` on *both* operands inside the comparison. Measured at five population sizes,
`dedup / n²` is constant at ~3.1e-6 across a 6.7x range of n, while `screen_all` is linear at
~4.1 ms/job (`evidence/scaling_dedup_screen.json`). So the corpus grew ~65% in three days and the
dominant stage's cost grew ~2.7x. That is the whole failure, and it is not mysterious.

**Sizing.** The one production anchor at 512 MB is 80.08s for 813 postings on 09-26; the same-shape
laptop figure is ~12s, giving a laptop-to-Lambda factor of about 6.7. Today's 21.3s projects to
~150s, and 300s leaves roughly 50% headroom. **300s is headroom, not requirement**, and it runs out
near ~2,400 postings — days, not months, at the observed growth. Memory stayed 512 per the packet;
raising it would buy proportional vCPU and is a different change with its own cost shape.

**History.** A confirmation record was written under
`2026-09-28-history-confirmations/SUBMISSION_LOG.md` in the format the reader already understands,
carrying role, exact requisition URL, time, outcome and a source pointer — and nothing else, because
this file is parsed into an artifact that ships inside the Lambda package. Evidence strength is
labelled: *employer-confirmed* for four, *provider-send confirmed* for the Catalyst email, whose
route is a bare address with no acknowledgement channel. Requisitions were verified against the
employers' own board APIs: AWeber `8100185` and BetterHelp `5395576008` (board token `betterhelpcom`,
not `betterhelp`) are both live; Grafana's `6100672004` is closed, while **two other Staff AI
Engineer requisitions are live and must keep reaching the report**.

`history-refresh` then moved 64 → 68 entries: BJAK PREPARED → SUBMITTED, and four added. Idempotent
on a second run. Held-not-settled fell from 5 to 3 — Grafana and the Catalyst Agent Builder are
settled; Syllo, Zscaler and the Catalyst Lead seat are genuinely unsent and stay visible.

**Three repairs in `src/candidate/history.py`**, all narrow:

1. The three heading regexes tolerate bold decoration and `SENT`. This can only make a section
   *visible* — it is read under `if not marker`, so it adds to `unresolved` and can never promote.
2. The decoration stripper also tolerates bold, because an unstripped decoration corrupts the role
   title to `Operations Engineer II · **SUBMITTED, employer-confirmed**`, which matches no feed row
   and no other record of the same application.
3. `merge_entries` no longer copies a loser's `status_conflict` onto a `submission_log` winner at
   SUBMITTED. BJAK's reviewed row said "Needs operator confirmation" while Bjak's own ATS had
   acknowledged the application on 2026-07-22; carrying that flag forward keeps asking a question
   the employer answered.

**Readout.** `measure_runtime()` records elapsed seconds, the configured timeout read from the Lambda
context, remaining headroom, population and seconds-per-1,000-postings into `daily_report.json`, and
appends one line to the markdown and therefore to the digest. The per-1k rate is the one that rises
as the corpus grows, which a flat duration cannot show.

**A defect this run introduced and the suite caught.** The first version re-ran the *blanket*
vocabulary guard over the finished document. `render_report` guards its own output with a
sourced-vocabulary exemption that exists because an employer is called Ghost and a department is
called Fraud; the blanket guard ignores it and rejected a legitimately sourced title on the word
`Real`. Caught by `test_source_titles_with_guarded_words_and_escaped_characters_publish_intact`. The
guard now checks only the generated line, which carries no source text.

**Checks:** 638 tests pass (617 inherited + 21 added). `policy-check` exit 0. `sam validate --lint`
valid. Processed-template diff vs live production: 7 differing properties, 6 code keys and the one
timeout, 0 others, parameters identical, 42 resources both sides.

## Follow-ups

- **`deduplicate` is quadratic, and this is the real repair.** `src/common/dedup.py:256-260` calls
  `normalize_employer` on both operands inside a nested loop over `kept`, uncached — 3.6M calls at
  1,344 jobs. Hoisting the key per job, or memoizing `normalize_employer`, turns the dominant stage
  into roughly nothing and would have made this timeout raise unnecessary. Out of this packet's edit
  surface; it is the next thing to do, before the corpus reaches ~2,400.
- **`jprs-A3-report-not-assembled` cannot fire, and never could.** The alarm watches custom metric
  `JPRS/ReportComplete`, which **has never been published — zero datapoints, ever**. It latched into
  ALARM on 2026-07-31 (missing data treated as breaching) and has stayed there, and CloudWatch
  notifies on transitions, so it has been silent through every failure including these four days.
  `jprs-A2-missed-run` / `CollectRunSuccess` is in the same state. `ReportFunction` already holds
  `cloudwatch:PutMetricData` scoped to namespace `JPRS` (`ReportMetrics` sid), so the publisher is a
  few lines and needs no IAM change — but a custom metric is a small paid resource, which this
  packet's step 7 excludes, so it is reported rather than added.
- Aggregator title normalization remains a residual suppression risk: a feed that flattens
  "Staff AI Engineer | US | Remote" to "Staff AI Engineer" would collide with the confirmed row on
  employer+title. Distinct today, verified against Grafana's board. Already recorded as
  `PQ-CAREER_FACTORY-082`.
- Adzuna remains credential-gated, so ordinary-industry breadth is still missing from discovery.
