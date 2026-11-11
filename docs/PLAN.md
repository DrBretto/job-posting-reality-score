# Project Plan

## Goals

1. Discover useful openings across the market, including previously unknown and non-software
   employers, and provide all credible current roles for Brett without a fixed daily quota.
2. Preserve public posting history so changes, disappearances, and repost patterns are evidence-backed.
3. Rank attention transparently around Brett's demonstrated agentic AI, applied AI, backend/platform,
   AWS, automation, and developer-tooling experience.
4. Keep AWS architecture skills fresh through inspectable serverless components and explicit manual
   checkpoints.
5. Keep expected operating cost below `$5/month` without always-on infrastructure.

## Constraints

- One AWS account and one region: `us-east-1`.
- Public ATS/company-career sources only; no authenticated scraping.
- No automated applications or personal-contact harvesting.
- No NAT Gateway, EC2, RDS, OpenSearch, EKS, Kinesis, paid Glue, or provisioned concurrency.
- S3 is the evidence store and versioning remains off.
- Bedrock is optional and remains disabled; no LLM sets scores or authoritative facts.
- AWS deployment, SSM changes, destructive actions, and merges to `main` require operator approval.
- Private account identifiers, ARNs, access keys, emails, and secrets never enter Git.

## Architecture

Daily collection:

`EventBridge Scheduler -> enumerate Lambda -> RUN_OPEN manifest -> SQS/DLQ -> collector -> S3`

Daily discovery (added by P11, not yet deployed):

`EventBridge Scheduler -> discovery Lambda -> employer-independent sources -> raw/normalized/status
+ discovery/`

Daily interpretation:

`EventBridge Scheduler -> Step Functions -> differ -> current/events -> report -> S3 + SES`

The collector owns `raw/`, `normalized/`, and `status/`. The differ alone owns `current/` and
`events/`. Discovery owns `discovery/` and writes the same forward tiers as the collector; it never
writes `current/` or `events/`. Failed or partial fetches freeze source state and cannot emit
disappearance events.

Monitoring answers "what is open at THIS employer" and so cannot surface an employer nobody has
named. Discovery answers "who is hiring for THIS work" and can. Employer is therefore a property of
the job, not of the source.

## Milestones

| Phase | Outcome | Status |
|---|---|---|
| P0 | Region, identity, and account guardrails | COMPLETE |
| P1 | Private S3 evidence substrate | COMPLETE |
| P2 | Public ATS connector and collector Lambda | COMPLETE |
| P3 | SQS, DLQ, retries, and redrive lab | COMPLETE |
| P4 | Scheduled collection and enumerate step | COMPLETE |
| P5 | Multi-source fan-out and complete-run manifest | COMPLETE |
| P6 | Evidence-backed differ and mass-drop protection | COMPLETE |
| P7 | Daily report, SES path, monitoring, and runbook | DEPLOYED AND VERIFIED |
| P8 | Optional constrained Bedrock narration | DEFERRED / OFF |
| P9 | SAM infrastructure reconstruction | COMPLETE AND DEPLOYED |
| P10 | Parquet/Athena historical analysis | DEFERRED UNTIL HISTORY JUSTIFIES IT |
| P11 | Open-market discovery, candidate screening, health/overflow repairs | BUILT, THEN REVIEWED — release defects found |
| P12 | Release repair: Adzuna default path, feed pagination, screening polarity, rollback/cost | REVIEWED — three blockers remained |
| P13 | Runtime boundary, screening evidence aggregation, data-compatible rollback, fresh-first | EXECUTED AND REVIEWED — three release gaps remain |
| P14 | Location semantics, production report timing and recent-page continuation | EXECUTED AND REVIEWED — location/timing hold; continuation and deploy handoff still fail |
| P15 | Persist incomplete recent traversal and bind deploy to verified build | EXECUTED — release gate passed |
| P16 | Controlled deployment of the overhaul + live source verification | **DEPLOYED 2026-09-25** — four keyless feeds live-verified; discovery jobs do NOT reach the report yet |
| P17 | P07–P10 release (2026-09-26 14:22Z) and production recovery (discovery list grant, report guard) | **DEPLOYED AND LIVE-VERIFIED 2026-09-26 18:27Z** — one ordinary round `ACCEPTANCE_MET`; unattended round not yet observed |
| P18 | Broad-ownership / first-sole-engineer retention, ownership-scope assessment, recorded-video repair | **EXECUTED AND REVIEWED LOCALLY 2026-09-28** — reviewer returned `revise`, seven findings repaired; 551 tests pass; production unchanged |

## Current Work

**CURRENT STATE (2026-09-30, P21) — the dedup quadratic is repaired and DEPLOYED.** `src/common/dedup.py` only; the cleanup pass now walks each record's existing links
instead of every ordered pair of survivors. Locally, on the real 1,526-posting corpus, `deduplicate`
goes **7.342s → 0.023s** and its growth per doubling **~4.1x → ~2.0x**; whole-report assembly
**24.907s → 17.023s**. 666 tests pass, 6/6 mutants caught, independent review APPROVE, processed
template vs live showed **0 non-code differences** with `Timeout` 300 and `MemorySize` 512 preserved.

**Verified in production on the same corpus the same day: 226.74s → 140.11s, headroom 24.0% →
53.1%, seconds-per-1,000 148.58 → 91.82, with 13 of 13 report fields and every job-id set identical
before and after.** Goal 5 (operating cost under $5/month) improves rather than degrades: a shorter
report bills less at an unchanged ceiling.

Two carried conditions, neither caused by that repair:

- **`policy-check` exits 1** on operating-plan digest drift from a 09:48 edit about delegated
  outreach sending. Independently confirmed digest-stale, not screening-stale. The hash was not
  refreshed, and `config/candidate_policy.json` is outside that run's write surface.
- **The runtime artifact packages `tests/`, `docs/`, `scripts/` and `project-factory/`.** That is
  why every release rewrites all six Lambda code keys and why a doc edit alone yields a new
  artifact. Pre-existing; worth a dedicated cleanup someday.

`PQ-CAREER_FACTORY-087` is settled on that production evidence.

---

**PREVIOUS STATE (2026-09-30, P20) — the report runs again, on a timeout that buys a corpus and not
a calendar.** `ReportFunction.Timeout` 90 → 300, deployed 07:20:08Z; first production report since
2026-09-26 completed in **188.52s of a 298.97s budget (36.9% headroom)** over 1,344 postings, digest
sent. Only two properties classes changed in the stack: the six Lambda code keys and that one
timeout. `MemorySize` stayed 512 — peak use is 209 MB, so memory was never the constraint.

The diagnosis is the part worth keeping. The report Lambda emits nothing between `START` and its
timeout, so CloudWatch could not say whether the budget went to work or to waiting; a read-only
harness against live production S3 separated them (4.2s of S3 across 55 calls, 17.1s of
single-threaded CPU) and settled it as capacity. The mechanism is that **`deduplicate` is quadratic**
— `normalize_employer` called on both operands of a nested loop over the kept set, 3.6M calls at
1,344 jobs, measured constant at 3.1e-6 × n² across a 6.7x range of n. A corpus that grew 65% in
three days grew that stage's cost ~2.7x, which is why an 80.08s/90s near-miss became four straight
timeouts rather than a slowdown.

**Consequences for the roadmap, stated rather than left implicit:**

- **The 300s ceiling is exhausted near ~1,990 postings** at the measured 8.9x laptop-to-Lambda
  factor. Today's corpus is 1,344. Fixing `src/common/dedup.py:256-260` is now a scheduled item, not
  an optional cleanup, and it likely makes the original 90s sufficient again.
- **Goal 5 (operating cost below `$5/month`) is unaffected.** A successful report is ~$0.0016/day;
  the worst case of five 300s attempts is $0.0125/day. Worst-case annual increase is roughly $3.30,
  and only on days the report fails.
- **The report now measures itself.** Elapsed, budget, headroom, population and seconds-per-1,000
  postings land in `daily_report.json` and one line of the markdown and digest. The per-1k rate is
  the one that rises as the corpus grows; a flat duration cannot show that.
- **Alarm coverage is a fiction and should be treated as absent.** `jprs-A3-report-not-assembled`
  watches `JPRS/ReportComplete`, which has never been published — zero datapoints ever. It latched
  into ALARM on 2026-07-31 and CloudWatch notifies only on transitions, so it was silent through
  every failure. `jprs-A2-missed-run` is identical. The permission to publish already exists.

Run of record: `../Infotropy Book/book-factory/runs/20260928_career-report-runtime-and-confirmed-history-recovery-v1/`.
Plan: `docs/plans/2026-09-28-report-runtime-recovery.md`.

**Application history now carries 68 entries with an evidence cutoff of 2026-09-28** — superseding
the 62/2026-09-27 figures in the P19 section below. Grafana Labs Staff AI Engineer, AWeber, BetterHelp,
the Catalyst·Wayfare Agent Builder email and BJAK read SUBMITTED; AWeber and BetterHelp are still
open on their employers' boards, so those two were the live re-announcement risk.

---

**PREVIOUS STATE (2026-09-28, P19) — the broad-ownership release plus a repaired application-history
projection.** Two things shipped together because one without the other is worse than neither: the
ownership work widens what reaches the report, and the report was announcing already-submitted
postings as NEW, so widening it alone would have widened the noise.

- **History.** `config/application_history.json` was built 2026-09-24 and seven dated submission
  rounds had run since. It now carries **62 entries with an evidence cutoff of 2026-09-27**: 20
  existing rows upgraded PREPARED → SUBMITTED and 8 added, all from the runs' own append-only
  `SUBMISSION_LOG.md` files where the employer's acceptance text is quoted against a named
  requisition. A folder scan is still capped at PREPARED and still cannot conclude a submission —
  the scan's output is reported as drift, never merged.
- **Aliases.** An entry may now carry several URLs for one requisition. The feeds carry aggregator
  URLs and the applications were submitted on ATS URLs, so before this the two never met; three real
  submissions (Airspace Link, Hard Rock Digital, Prenosis) are reachable by nothing else, and each
  read NEW without it.
- **Cutoff, not completeness.** `built_at` says when the file was written; `cutoff` says how far its
  evidence reached. The report prints both and the gap, and states that anything submitted after the
  cutoff is not represented. It never claims the history is complete.
- **Four states, where there were two.** missing / stale / current / known-empty. The report always
  announced a MISSING projection and said nothing about a stale one — from inside the report those
  looked identical, which is exactly how postings submitted on the 26th were re-announced.
- **Held, not guessed.** Blocked, held and both-claims-present records land on `unresolved` and are
  counted on the page. They are neither suppressed nor recorded as sent.
- One inherited claim corrected: the aggregator's Evolve **Staff Software Engineer** row
  (remoteOK 1136447) was reported as "already submitted"; it is off Evolve's board and a *different*
  requisition was applied to. Two rows now, neither guessed into the other.

`history-refresh` rebuilds it, dry by default. Plan:
`docs/plans/2026-09-28-history-reconciliation-release.md`. Record:
`../Infotropy Book/book-factory/runs/20260928_career-radar-release-and-history-reconciliation-v1/`.

**CURRENT STATE (2026-09-28) — P18 is LOCAL; production still runs the 2026-09-26 recovery build.**
The 2026-09-28 broad-ownership preference is implemented through discovery, retention and report
output: `src/candidate/ownership.py` assesses ownership scope from posting evidence only, the report
retains a plausible software-ownership opening whatever its AI-weighted fit score, and the
`broad-ownership` query family widens what a bulk feed's payload is recognised for. Measured on 176
live postings: the existing candidate set is unchanged job-id for job-id, seven more became readable
and the below-threshold tail fell 86 → 79. A recorded-video gap (Loom / video walkthrough) was found
in a live posting and repaired; screening ruleset 1.5.0 → 1.6.0. Record:
`../Infotropy Book/book-factory/runs/20260928_career-broad-ownership-discovery-v1/`; plan:
`docs/plans/2026-09-28-broad-ownership-discovery.md`.

**CURRENT STATE (2026-09-26 18:27Z) — supersedes everything below it that says P07–P10 are local.**
P10 was deployed at 14:22Z by the Career Factory release run and broke discovery in production
(first round could not read its own never-written state: no `s3:ListBucket`) while the report kept
failing on its vocabulary guard. The recovery release is now DEPLOYED and live-verified: one IAM
statement (discovery may list `discovery/*` only) plus discovery/report code. The ordinary round run
after deployment, under the deployed roles, succeeded end to end — discovery 4/4 keyless feeds and
297 jobs, assemble 15/15 boards, `daily_report` persisted for 2026-09-26 with 56 retained candidates
(15 from discovery), digest accepted by SES, and `scripts/inspect_discovery_integration.py` returned
`ACCEPTANCE_MET`. Still NOT verified: an unattended scheduled round (next 07:05 / 09:00), and digest
receipt. Adzuna remains credential-gated. Record, evidence, rollback: `../Infotropy Book/book-factory/runs/20260926_career-radar-production-recovery-v1/`
(`EXECUTION_RETURN.md`, `RELEASE_PROPOSAL.md`); plan: `docs/plans/2026-09-26-radar-production-recovery.md`.
The live baseline for the NEXT release is this build; see `infra/DEPLOY.md` § Release gate.

**Deployment status, September 25:** **the overhaul is DEPLOYED to `jprs-v1` (`us-east-1`) and the four
keyless discovery feeds are live-verified from the production Lambda — 295 jobs, 218 employers, nothing
inaccessible, every source within its request cap, Adzuna named as credential-gated.** A `jprs-discovery`
pass now runs daily at 07:05 America/New_York, between the unchanged 07:00 collect and 09:00 assemble.
The change set was inspected before execution: 6 adds, 9 non-destructive modifies, 0 removals, 0
replacements; schedules, timezone, the 15-board registry, retained storage and every existing parameter
preserved.

**But the product goal is not yet delivered: none of the discovered jobs can become candidate rows.**
`enumerate` files discovery source ids under `expected_discovery_sources` while the report builds
candidate rows only from `expected_sources` and never reads that field, and `current/` is differ-owned
with the differ invoked once per `/jprs/companies` entry — so `current/` holds nothing but
`provider=greenhouse/`. The jobs are fetched, normalized and stored; there is simply no wire to the
report. An absent integration, not an empty valid result, and it predates the deployment. It also
corrects the record on P05: those two persisted-report regressions passed because the test harness
itself wrote `expected_sources` and `current/` for discovery sources, so they never proved the wiring
existed. Deployment run:
`project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/`.

Second finding: the first post-deploy report read `timing.boundary: cold-start` because the real
old-format reports carry an empty `complete_candidate_list`, so the earlier-release id fallback found
nothing usable. Next-round recovery is expected, not verified; P07 includes a bounded compatibility fix.

**Current handoff:** `project-factory/claude_handoff/packets/jprs/JPRS-L2-P09-publication-commit-boundary-and-verification-v01.md`
— staged local repair, not executed. P08's `ORCHESTRATOR_REVIEW.md` controls release acceptance:
350 tests and the original live-write repair pass independently, but the first pending-ledger write
still strands a stored job; debt eviction and false-green release/report helpers need correction.
The 36-file P06 archive is genuinely hash-verified; keep it. P08's deployment handoff is qualified,
not approved to run. **Production remains P06**, and fresh approval is required after bounded repairs.

**Prior release status (P05), preserved:** P05 executed. The two blockers the P04 review left open are
repaired and its gate decision is `unlock`. All **316** tests pass, the SAM template validates and
builds, and the candidate-policy projection matches all sources. Its local traversal/build acceptance
stands; its fixture-created report connection is not production integration evidence. P06 has since
deployed that code and verified one real fetch across all four keyless feeds. Authenticated Adzuna,
the careers-URL resolver live path, source-growth admission and rollback against real state remain
separate unpassed gates.

**The P05 repairs.** Both P04 findings were one confusion in the traversal state model: an observed
timestamp was being read as proof that the intervening range had been traversed.

- **Recent ranges are no longer lost.** State now records what it still *owes* — an ordered list of
  untraversed recent cursor ranges — separately from what it has *observed*. A recent page that fails,
  returns partial, or is cut off by the budget stays owed and is retried, and a newly published
  continuation no longer overwrites a saved one, because one slot no longer has to hold both. The
  already-observed stop applies only to the contiguous walk from page one, which is the only walk whose
  coverage runs unbroken from the newest posting downward. Verified over persisted multi-run state
  against a 24-page backlog, and driven through to a persisted candidate report.
- **Failed attempts are charged.** Every outbound attempt spends its request before it is made, so the
  review's four-requests-under-a-budget-of-three is closed. The per-source cap is asserted at budgets
  1, 2, 3, 5 and 8 with failures in the mix.
- **Deployment selects the build it verified.** The P04 command built into a temporary directory and
  deployed without naming the template; from the repository root that resolves to a nonexistent file,
  and from `infra/` to a stale August 1 build containing no discovery function. Both forward and
  rollback commands now name the template and an absolute config path, checked through SAM's own
  resolution code with no AWS call. Corrected in the new handoff, `infra/DEPLOY.md` and `START_HERE.md`.

Of the 20 new regression tests, 12 fail against a reconstructed copy of the P04 source, including both
review scenarios and both persisted-report checks. Latest run:
`project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/`;
its `DEPLOYMENT_HANDOFF.md` is the handoff of record and supersedes P04's.

**Prior state, preserved:** P01–P04 executed; 296 tests passed at P04. The three blockers the P03
review left open were repaired there, each reproduced against the reviewer's own unmodified probe
before any code changed:

- **Location semantics.** Screening had answered a drive-time policy with a hand-written town list, so
  "Belmont, NH" was excluded while "Belmont NH" was eligible, "Alton, IL" counted as local, a remote
  label overrode mandatory Boston attendance, and a remote role restricted to California or New York
  residents passed. It now resolves place and state, mandatory attendance and residency limits. The one
  hard distance rule is the state boundary, which is a fact rather than an estimate: no out-of-state
  worksite is a thirty-minute drive from Laconia. Every in-state distance question is left unresolved
  and visible for worksite confirmation, because the system cannot measure a drive time and should not
  certify one.
- **Production report timing.** `assemble_report_input` never set `run_started_at` or
  `previous_run_at`, so the renderer fell back to the end of the UTC calendar day and every persisted
  report said zero fresh arrivals while the renderer tests passed. The run start now comes from the
  RUN_OPEN manifest's `opened_at`, and "new since the last round" is decided by which postings the
  previous persisted report actually showed — identity, not clock arithmetic, so a weekend gap, a
  failed round, a retry and a replay all give the same answer.
- **Recent-page continuation.** The feed-head walk took one page and discarded its continuation
  cursor, so a two-hour-old posting on page two was never fetched. It now continues while pages still
  hold recent arrivals, hands over when it meets the backfill, saves and resumes anything it could not
  reach, and always reserves a page for the historical catch-up. Budgets are asserted at 1, 2, 3 and 5.

Two defects found while repairing those, neither in the review: the local CLI report path had the same
unwired timing boundary, and cold-start detection inferred a first observation from timestamp
cardinality, so a warm source holding a single posting suppressed its genuinely new arrival.

P04's run root is `project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/`. Its `DEPLOYMENT_HANDOFF.md` superseded P03's and corrected its
self-contradiction about rollback — the baseline rejects 18 added fields, so the data downgrade is
required, not optional — and made the rollback order and writer quiescence explicit. P05's handoff
keeps all of that and is now the handoff of record.

**Counts, with populations named, because they are not interchangeable.** The P03 live sweep considered
**821 postings** and observed **216 employers absent from the monitored registry** — employers, not
postings, and observed, not monitored — of which 44 postings were retained. The P04 rehearsal replays a
**smaller captured slice** (four Himalayas cursor pages plus three bulk feeds): 264 postings
considered, 108 policy-excluded, 145 below the fit threshold, 11 retained (5 strong, 6 needing a
check), 3 labelled newly arrived. Fewer retained rows than P03 is a smaller input, not a regression.
Raw count is not the success criterion.

The active plan is
[2026-09-24 open-market job discovery](plans/2026-09-24-open-market-job-discovery.md). Its
implementation packet `JPRS-L2-P01-open-market-discovery-v01` was executed on 2026-09-24; an
orchestrator review found four release defects; P02, P03 and P04 repaired successive rounds of
findings. Each of the four reviews found real defects the implementing context had missed, including
inside its own tests. **Locally verified; not deployed.**

The P02 repairs: the Adzuna default path never reached the provider; Himalayas was read as a complete
feed when it paginates 20 at a time (20 postings became 96 across 74 employers); screening excluded on
vocabulary rather than meaning; and the documented rollback would have destroyed the uncommitted
implementation.

The P03 repairs: the *real* Adzuna runtime still stripped credentials, because `_live_fetcher`
discarded the authenticated URL — and P02's test had replaced that very function, so it asserted the
URL passed in rather than the request sent out; screening examined only the first match, so a negation
cancelled a later mandatory duty; source rollback was not data-compatible; and fresh-first scheduling,
derived from the measured fact that the feed cursor is a descending timestamp.

Current unpassed gates: authenticated Adzuna (a credential enables an attempt, not a conclusion),
careers-URL resolution, source admission, actual discovery candidates in the report and unattended
cross-round verification. P06 established one successful production fetch across the four keyless
feeds; local transport truncation is not evidence that that production run failed. Rollback data
conversion has been rehearsed, not run against real state.

The August 2 usefulness pass is historical, superseded by the P06 deployment. Its controlled run completed 15/15 targets
and produced a ranked 519-job report with 41 useful matches. SES delivery and same-day duplicate
suppression are verified.

## Next Product Steps

1. Inspect executed P08 and decide on deployment. All four of its acceptance clauses are met locally:
   the interrupted-publication loss is repaired and measured with the P07 reviewer's own unmodified
   probe, the package scope and rollback baseline are demonstrated, and the live check distinguishes an
   empty eligibility day from a missing integration. Leave P06 running; fresh approval is required to
   deploy, and after deploying, run `scripts/inspect_discovery_integration.py` on the delivered report.
2. Check the pending first unattended round (2026-09-26, discovery 07:05) against the exact paths in
   `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/evidence/p06_live_verification_summary.md`
   §6 — in particular whether `timing.boundary` reads `reported-ids` instead of `cold-start`. Not yet
   run; do not record it as passed before it does.
3. Request credential and source-growth approvals separately. A key alone enables Adzuna's first
   attempt; it does not close the general-industry coverage gate.
4. Keep the existing radar and supplemental wider search available during the transition.
5. Consider Parquet/Athena only when accumulated history answers a concrete question better than the
   existing JSON records.
6. Run `history-refresh` as part of the application round that produces a submission log, rather than
   as a separate step somebody has to remember. The refresh is repeatable and it is not automatic: a
   submission made after the cutoff is not in the projection until it runs again, and the report now
   says so on its own rather than leaving the reader to discover it.

## Non-Goals

- Inferring deceptive intent from posting behavior.
- Broad prestige-company monitoring without current role relevance.
- A commercial dashboard before the personal digest proves useful.
- LLM-based scoring where deterministic evidence is sufficient.
- Replacing human review of a posting or automating submission.
