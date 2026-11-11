# VALIDATION — JPRS-L2-P04-location-and-freshness-boundaries-v01

Run: `20260924_location_and_freshness_boundaries_v1` · Date: 2026-09-24

Three repairs, each reproduced before any code changed, plus reconciliation. 296 tests pass. Nothing
deployed, committed, staged or pushed; `git status` shows an uncommitted tree with 0 staged files.

Labels used below: **measured** — I ran it and saved the output. **inference** — my reasoning, flagged
as such. **unverified** — stated as an open gate rather than a result.

---

## 1. Reproduction before repair — measured

Ran the P03 review's own probe, unmodified, before touching anything:
`evidence/p04_before_repair_probe.json`.

| Review row | Observed before repair | Expected by policy |
|---|---|---|
| `Belmont, NH`, onsite | EXCLUDED | not excluded — plausibly local |
| `Belmont NH`, onsite | ELIGIBLE | same answer as the line above |
| `Alton, IL`, onsite | ELIGIBLE | excluded — different state |
| `Remote / Boston, MA` + "must attend the Boston office three days per week" | ELIGIBLE | excluded — Boston commuting |
| `Remote, US` + "may only employ residents of California or New York" | ELIGIBLE | excluded — NH not included |
| Himalayas head gap, 5-page budget | requested `None → OLDER_CURSOR → OLDER_AGAIN → EVEN_OLDER → STILL_OLDER`; page two never fetched | page two fetched |
| Production report timing | `run_started_at: null`, `previous_run_at: null`, persisted `fresh_arrival_count: 0` | real timing, fresh arrivals labelled |

All seven reproduced exactly as the review described. The probe was never edited.

---

## 2. R1 — the location policy, implemented by its meaning

### 2.1 What was wrong, precisely

`src/candidate/screening.py` held three regexes of hand-written town names. Three separate failures
followed from that one choice:

- the list contained the literal string `belmont nh`, so `Belmont, NH` (with a comma) missed it and
  fell through to "not commutable" → EXCLUDED, while `Belmont NH` matched → ELIGIBLE. **A comma
  decided a verdict, in both directions at once.**
- the list contained a bare `alton`, and New Hampshire has an Alton. So did Illinois. `Alton, IL`
  read as local.
- a remote token anywhere in the location field set `remote_ok`, which **skipped every worksite rule
  below it**. That is why mandatory Boston attendance and a California/New York residency restriction
  both passed.

And underneath all three: the policy states a **drive duration** ("no more than approximately a
30-minute one-way drive from Laconia"), and the previous implementation answered it with a list of
towns nobody had measured. It certified places it could not verify *and* rejected a genuinely local
job over punctuation.

### 2.2 What replaced it

`src/candidate/location.py` (new). It asks three questions instead of matching names:

1. **Does the posting restrict residency in a way that excludes New Hampshire?** `may only employ
   residents of X`, `hiring only in X`, `must be located in X`. A country-level statement ("must
   reside in the United States", "authorized to work in the US") restricts nobody in New Hampshire and
   is not an exclusion. An unparsable one returns nothing rather than a guess.
2. **Is attendance at a worksite actually mandatory?** Matched with the existing polarity machinery, so
   "there is no in-office requirement" is not a requirement, and "you will report to the VP of
   Engineering in our Boston office" is a reporting line rather than an attendance rule. A mandatory
   attendance requirement **outranks a remote label**, which is the R1 Boston case.
3. **Only then, where is that worksite?** Places are parsed with state resolution, so `Belmont, NH`,
   `Belmont NH`, `Belmont, New Hampshire`, `belmont,nh`, `Belmont, N.H.` and `BELMONT NH` all resolve
   to the same place, and `Alton, IL` does not resolve to New Hampshire.

The classification is deliberately partial:

| Worksite | Verdict | Basis |
|---|---|---|
| Portsmouth, or the Boston area | EXCLUDED for commuting | the operator named them |
| outside New Hampshire | EXCLUDED when attendance is required | Laconia is in central New Hampshire, so no out-of-state worksite is a ~30-minute drive from it. A geographic fact, not an estimate — the only hard distance rule used |
| Plymouth | operator review | "a possible exception to discuss with Brett, not blanket approval" |
| Lakes Region town | **review: plausibly local, confirm the worksite** | plausible, unmeasured. Not certified |
| elsewhere in New Hampshire | **review: probably beyond 30 minutes, confirm** | in state; "probably" is a review, not an exclusion |
| no parsable worksite | review | unknown is not a verdict |
| genuinely remote, NH not excluded | eligible regardless of employer city | "An employer headquartered in either city remains eligible when the role is genuinely remote" |

**This is the design decision worth disputing, so it is stated plainly.** A New Hampshire onsite role
now reaches the operator as a worksite question rather than a yes or a no. The packet asked for exactly
this — "do not certify all worksites in a broad town/region as within 30 minutes... keep plausible but
unverified local leads visible... do not replace uncertainty with automatic rejection" — and it is the
honest answer for a system with no drive-time measurement. It does mean more review rows for local
postings. A named auto-approve list would remove them, and would be me certifying a distance I have
not measured.

### 2.3 Two bugs found while building it — measured

- **`or` parsed as Oregon.** A case-insensitive two-letter state pattern read "California or New York"
  as `['CA', 'OR', 'NY']`. Half the state codes are ordinary English words — `or`, `in`, `me`, `ok`,
  `hi`, `de`, `la`, `pa`, `ma`, `co`, `id`. Codes are now matched case-sensitively, uppercase only.
  Regression: `test_or_is_not_parsed_as_oregon`.
- **A worksite named only in the body was invisible.** "Remote" in the location field plus "four days
  per week in the office in Cambridge, MA" in the description yielded no parsable worksite, so it
  became a review item instead of an excluded Boston-area commute. When attendance is mandatory and the
  location field yields nothing, the attendance sentence is now parsed for the worksite. Found by
  `test_conflicting_remote_and_hybrid_fields_resolve_to_the_stated_requirement` failing.

### 2.4 After repair — measured

`evidence/p04_after_repair_probe.json`, same unmodified probe:

| Review row | After |
|---|---|
| `Belmont, NH` / `Belmont NH`, onsite | **PENDING_CHECK, identical reasons** — "plausibly local to Laconia, but the actual worksite address and attendance requirement decide" |
| `Alton, IL`, onsite | **EXCLUDED** — "outside New Hampshire" |
| `Remote / Boston, MA` + mandatory attendance | **EXCLUDED** — "a location the operator excluded for commuting" |
| `Remote, US` + CA/NY residency | **EXCLUDED** — rule `location-residency`, "does not include New Hampshire" |

The dead town-list regexes were deleted rather than left in place, so nothing can reuse them.

### 2.5 What each new R1 test would have failed on before repair

| Test | Pre-repair behavior |
|---|---|
| `test_punctuation_does_not_decide_locality` | `Belmont, NH` EXCLUDED, `Belmont NH` ELIGIBLE — two verdicts for one place |
| `test_a_shared_town_name_in_another_state_is_not_local` | `Alton, IL` ELIGIBLE via the bare `alton` entry |
| `test_a_remote_label_does_not_override_mandatory_office_attendance` | ELIGIBLE — `remote_ok` skipped the worksite branch |
| `test_a_remote_role_whose_residency_list_excludes_new_hampshire_is_excluded` | ELIGIBLE — no residency rule existed |
| `test_country_level_work_authorization_is_not_a_residency_exclusion` | passed before (no rule existed) — it guards the *new* rule from over-reaching |
| `test_genuinely_remote_role_at_an_excluded_city_employer_stays_eligible` | passed before, for the wrong reason: any remote token short-circuited the check. Now it passes because the role is genuinely remote and attendance is not required |
| `test_a_reporting_line_is_not_an_attendance_requirement` | passed before; guards the new attendance rule |
| `test_a_negated_office_requirement_is_not_read_as_a_requirement` | passed before; guards the new attendance rule |
| `test_plymouth_is_an_operator_review_case_not_a_verdict` | passed for `Plymouth` only via a bare regex; now resolves state too |
| `test_a_plausibly_local_lead_stays_visible_and_is_not_certified` | ELIGIBLE — certified as commutable. The verdict itself was the defect |
| `test_a_new_hampshire_worksite_beyond_the_lakes_region_is_flagged_not_rejected` | Manchester/Nashua/Keene onsite were EXCLUDED as "not commutable" |
| `test_a_missing_state_keeps_a_matching_town_name_unresolved` | bare `Belmont` matched the town list → ELIGIBLE |
| `test_multiple_worksites_are_judged_on_the_best_option` | order-dependent: whichever name the regex hit first |
| `test_conflicting_remote_and_hybrid_fields_resolve_to_the_stated_requirement` | ELIGIBLE — remote label won |
| `test_non_us_worksite_without_us_remote_is_still_excluded` | passed before; guards the rewrite |
| `test_state_abbreviations_and_full_names_agree` | `Portsmouth, NH` and `Portsmouth, New Hampshire` could differ, since the list matched raw substrings |
| `test_or_is_not_parsed_as_oregon` | n/a — the residency parser did not exist; it failed during development |
| `test_worksite_classification_table` | n/a — no classification existed |
| `test_no_pay_rule_was_introduced_with_the_location_rules` | passed before; guards against adding a pay cutoff, which the policy forbids |
| `test_existing_non_location_exclusions_survive_the_rewrite` | passed before; guards the rewrite |

**Honest scope note (inference):** the five reviewer rows were reproduced against the actual pre-repair
code and saved. The other pre-repair behaviors in that table are derived from the removed regexes,
which are quoted in this document and in the replacement module's comments — they were not each
separately executed against the old code, because the old code existed only in the working tree that
this run modified. Where a test passed before, the table says so rather than claiming a fix.

---

## 3. R2 — freshness timing through production wiring

### 3.1 What was wrong

`assemble_report_input` built its `ReportInput` without `run_started_at` or `previous_run_at`. The
renderer's fallback was `datetime.fromisoformat(f"{dt}T23:59:59+00:00")` — **the end of the UTC
calendar day.** For a 07:05 run that is seventeen hours in the future, and the "since the previous
round" branch could never execute because there was no previous boundary at all. Every persisted
production report would have said zero fresh arrivals.

The renderer tests passed throughout, because they handed `render_report` a ReportInput with the timing
fields already filled in — the same shape of mistake as P02's R1 test, in a new place.

### 3.2 What replaced it

`resolve_run_timing(s3, bucket, run_id, dt)`:

- **`run_started_at`** = the RUN_OPEN manifest's `opened_at`, written by ENUMERATE before any
  collection. Used for age labels too, so ages are measured from when the round started looking. If no
  manifest exists, the report's own invocation time is used and `basis` says so — a labelled fallback,
  not a silent guess.
- **the previous boundary** = the most recent **earlier** persisted report. A persisted report is
  itself the evidence that the round reported, so a failed round leaves none and is skipped rather
  than credited with an observation it never made. Candidate reports are ordered by the `dt=` partition
  they belong to, not by a stored wall-clock stamp, so a replay of an earlier day cannot misorder them.

**And the decision is by identity, not arithmetic.** "New since the last round" means *the previous
report did not show this posting* — `previously_reported_ids`. This came out of a test failure: the
timestamp comparison was correct in production but wrong under a replay, and more importantly it
re-announced a posting first seen partway through the previous round, which that round had already
shown. Identity needs no clock, so a weekend gap, a failed round, a retry and a replay all give the
same answer. `timing.boundary` in the report JSON names which mechanism decided.

The report now persists `report_generated_at` and a `timing` block so the next round has a durable
boundary to read.

### 3.3 The same defect in a second place — found, not reported

`src/cli.py`'s `_assemble_local_report` built its ReportInput with no timing either. Every local
`discover` report had the same end-of-calendar-day ages and could never label a new arrival. Fixed
with a `--previous-report` flag that defaults to the output directory, so a local round reads the
previous round's report exactly as the Lambda path does. Without this fix the rehearsal in this run
would have reproduced R2.

### 3.4 One more, from the review's footnote

`cold_start_sources` inferred "first observation" from **timestamp cardinality**: if every posting from
a source shared one `first_seen_at`, it was treated as a cold start. A warm source holding a *single*
posting also has one distinct stamp, so its genuinely new arrival was suppressed. It now uses the
source's recorded `success_count_history` from `current/state`, falling back to cardinality only when
no history exists. Regression:
`test_a_warm_source_with_one_posting_is_not_mistaken_for_a_cold_start`.

### 3.5 After repair — measured, through the real handler

`evidence/p04_report_boundary_probe.py` → `evidence/p04_report_boundary_results.json`. Production
manifest shape, mocked S3, the real `handler()`, reading the **persisted** report:

| | round one (cold start) | round two |
|---|---|---|
| `timing.basis` | `manifest.opened_at` | `manifest.opened_at` |
| `run_started_at` | `2026-09-23T07:05:00+00:00` | `2026-09-24T07:05:00+00:00` |
| `previous_run_id` | none | `2026-09-23` |
| `timing.boundary` | `cold-start` | `reported-ids` |
| fresh arrivals | 0 | **2** |
| retained rows | 2 | 4 — nothing dropped |

Round two's fresh pair is the 20-hour-old posting and the undated new-to-us arrival. The posting first
seen *partway through round one* is correctly **not** fresh. A retry of round two reports the same 2
and still names `2026-09-23` as previous, rather than reading its own first attempt.

Age labels are measured from the run start: the posting published 20 hours before noon reads
"published 15h ago" against the 07:05 start, where the old end-of-day fallback would have said 32h.

**Why the review's own probe still shows 0 fresh after repair (measured, and not a defect).** That
probe writes its manifest with `created_at` / `run_started_at` keys; the manifest ENUMERATE actually
writes is a `RunManifest` whose start field is **`opened_at`**. So after the repair that fixture
exercises the manifest-absent fallback — `run_started_at` is now populated where it was `null`, with
`basis` reading "report_invocation_time (RUN_OPEN manifest absent)" — and its mocked bucket contains no
previous report either, so `cold-start` is the correct answer for what that fixture contains. The probe
was left untouched, as the packet requires. The production-shaped reproduction above is the evidence.

### 3.6 Forward compatibility with the currently deployed release

A report written by an earlier release has no `report_generated_at` and no `timing` block. The first
draft of the reader skipped such a report entirely, which would have announced **every already-seen
posting as new on the first morning after every deploy**. The reader now takes the previous report's
candidate id list even when no timestamp can be read, because identity needs no clock. Regression:
`test_a_previous_report_from_an_earlier_release_still_supplies_its_identity_list`.

### 3.7 What each new R2 test would have failed on before repair

| Test | Pre-repair behavior |
|---|---|
| `test_production_report_receives_real_run_timing` | `timing` key absent; `fresh_arrival_count: 0` |
| `test_morning_age_is_not_measured_from_the_end_of_the_calendar_day` | age computed against 23:59:59 |
| `test_previous_boundary_comes_from_the_previous_reported_round` | no previous boundary existed |
| `test_a_failed_round_does_not_become_a_previous_successful_observation` | n/a — no previous-round logic to get wrong |
| `test_a_weekend_gap_treats_the_whole_gap_as_new` | 0 fresh |
| `test_an_undated_arrival_is_new_to_us_without_claiming_it_is_newly_published` | 0 fresh; the age label was already correct |
| `test_first_observation_of_a_source_is_not_a_wave_of_fresh_arrivals` | passed via cardinality, for a reason that broke the next test |
| `test_a_warm_source_with_one_posting_is_not_mistaken_for_a_cold_start` | suppressed as a cold start |
| `test_a_retry_of_the_same_round_does_not_compare_against_its_own_first_attempt` | n/a |
| `test_duplicate_observations_of_one_posting_do_not_multiply_it` | dedup already correct; this guards it at the report boundary |
| `test_a_partial_round_still_reports_and_says_so` | reported, but with no timing |
| `test_the_digest_body_boundary_gets_the_same_timing` | the emailed body carried the same 0-fresh report |
| `test_a_previous_report_from_an_earlier_release_still_supplies_its_identity_list` | n/a — failed during development, see §3.6 |

---

## 4. R3 — recent arrivals beyond the first feed page

### 4.1 What was wrong

The head walk was literally `_walk(None, 1, phase="head")`: fetch one page, **discard the continuation
cursor**, then resume the historical backfill. With new postings on page two, page two was never
requested. The review measured it and so did this run:
`None → OLDER_CURSOR → OLDER_AGAIN → EVEN_OLDER → STILL_OLDER`.

### 4.2 What replaced it

The head walk continues while pages still hold recent arrivals, and stops on the first of:

- its page budget is spent — the remainder is **saved to `head_cursors` and resumed next run**, and
  reported as a visible, resumable overflow;
- the feed ends;
- its next cursor equals the backfill's saved cursor — the two walks have met, so it hands over rather
  than spending a request on the page catch-up is about to fetch;
- the page just fetched held nothing published inside `HEAD_RECENT_HOURS` (72h — wide enough for a
  missed weekend);
- the page held nothing newer than `head_frontier_at`, the newest publication already observed.

Bounded two ways so the old catch-up cannot be starved: **at least one page is always reserved for the
backfill**, and the budget is never exceeded. An undated posting counts as recent, so a provider that
publishes no dates never causes a new arrival to be walked past; the page budget, not the date, is what
bounds the walk.

### 4.3 A design bug the tests caught

The frontier and recency stops fired *before* a saved head continuation could resume. On the run after
an overflow, page one is previously observed ground **by definition**, so the walk stopped there and
abandoned the very pages the previous run had saved — silently dropping the arrivals it saved them for.
Those two stops are now skipped while a resume is pending. Found by
`test_an_overflowing_head_walk_is_saved_and_resumed_not_discarded` failing.

### 4.4 After repair — measured

Same unmodified probe, 5-page budget: `None → NEW_PAGE_TWO → OLDER_CURSOR → OLDER_AGAIN → EVEN_OLDER`.
`new_page_two_requested: true`, `Employer new-page-two` reaches the run, the backfill still advances
(to `STILL_OLDER`), and the budget of 5 is respected exactly.

### 4.5 What each new R3 test would have failed on before repair

| Test | Pre-repair behavior |
|---|---|
| `test_new_pages_above_an_outstanding_backlog_are_fetched` | `NEW_2` never requested; its posting never reached the run |
| `test_the_head_walk_hands_over_when_it_meets_the_backlog` | n/a — the head never continued far enough to meet it |
| `test_the_head_walk_stops_at_previously_observed_ground` | n/a — no frontier was recorded |
| `test_an_overflowing_head_walk_is_saved_and_resumed_not_discarded` | the continuation was discarded every run |
| `test_a_failed_head_page_is_retried_rather_than_skipped` | the single head page was retried; a *continuation* page could not be, as none existed |
| `test_no_new_arrivals_spends_nothing_extra_on_the_head` | passed trivially — the head was always exactly one page |
| `test_a_repeated_cursor_still_stops_the_walk` | passed; guards the rewrite |
| `test_first_seen_is_preserved_when_the_head_re_reads_a_posting` | passed; guards the rewrite |
| `test_the_budget_is_never_exceeded_by_the_head_continuation` | passed trivially; now guards a walk that can continue |
| `test_a_single_page_budget_still_favors_the_head_and_says_so` | passed (P03 behavior, preserved) |

---

## 5. Verification — measured

| Check | Result |
|---|---|
| Full suite | **296 passed** (252 inherited + 44 new) |
| P02/P03 regressions — transport, polarity, rollback | 84 passed |
| Downgrade / rollback / restart / credential / Adzuna subset | 22 passed |
| New P04 regressions | 44 passed |
| `sam validate --lint` | valid SAM template |
| `sam build` | Build Succeeded |
| `policy-check` | "projection matches all policy sources" |
| Review probe, unmodified, before → after | `evidence/p04_before_repair_probe.json` → `p04_after_repair_probe.json` |
| Report boundary through the real handler | `evidence/p04_report_boundary_results.json` |
| Two-round rehearsal, real payloads | `evidence/p04_rehearsal_results.json`, reports in `rehearsal/round1` and `rehearsal/round2` |
| Git | branch `codex/real-job-radar`, commit `e549a73`, **0 staged files** |

Two environment notes, neither a code or template problem:

- `sam validate` failed with `PermissionError: /Users/drbretto/.aws-sam/metadata.json` under the
  sandbox. Re-run with an isolated `HOME` plus explicit `AWS_CONFIG_FILE` /
  `AWS_SHARED_CREDENTIALS_FILE`; it then validates. Recorded in the handoff so a future run does not
  read it as a broken template.
- **Live transport truncates from this machine.** `curl` returned the full 80,693-byte Himalayas
  payload; `urllib` returned 18,586 / 0 / 5,996 / 18,600 bytes on four consecutive attempts to the same
  URL. The connector handles it correctly — `IncompleteRead` keeps the partial body and the JSON parse
  lands the snapshot `PARTIAL`, which suppresses removals rather than inventing a clean read — but it
  makes a live end-to-end rehearsal unreproducible. I changed no transport code in this run.

---

## 6. Rehearsal — real data, mocked transport, stated as such

`evidence/p04_rehearsal_driver.py`. Payloads in `rehearsal/fixtures/` were captured from the providers'
public endpoints on 2026-09-24: four consecutive Himalayas cursor pages plus the three bulk feeds,
seven GETs total. The cursors independently re-confirm P03's measured contract — successive pages
descend in time (10:26 → 09:34 → 08:57).

| | round one | round two |
|---|---|---|
| Himalayas pages requested | page1, page2 | page1, **page2**, page3 |
| requests (budget) | 2 (2) | 3 (3) |
| postings considered | 245 | 264 |
| policy-excluded | 100 | 108 |
| below fit threshold | 135 | 145 |
| retained | 10 | 11 (5 strong, 6 needing a check) |
| labelled newly arrived | 2 | 3 |
| freshness boundary | `cold-start` | `reported-ids`, previous `rehearsal-r1` |
| backfill position saved | page3 | page4 |
| head remainder saved | none | none |

Round two is the R3 case: a backfill was outstanding, and the head still reached page two *and* the
backfill still advanced, inside a 3-page budget. All five driver assertions hold, including that the
postings reached the **persisted** report rather than only being requested.

**This is not evidence that the production transport works.** Real data, mocked transport. The first
scheduled Lambda run is that evidence.

A reporting bug in my own driver, fixed: a saved-cursor label mapped `None` to "page1", because page
one's cursor *is* null — so an empty slot read as a saved position. It now reports `None`.

---

## 7. Counts, with their populations named

The review's counting objection, answered directly. These are four different populations and must not
be compared as though they were one:

| Number | What it counts | What it is not |
|---|---|---|
| 821 | postings in the P03 live sweep | not employers, not retained roles |
| 216 | employers in that sweep **absent from the monitored registry** | **not postings**, and observed — not admitted, not monitored |
| 161 | the same measure in the earlier P01 sweep | a smaller sweep, not a regression |
| 44 | postings retained in the P03 sweep | not "44 suitable roles" and not employers |
| 16 | of those 44, the ones with no application history | this is the cohort the "4 fresh + 12 older" split described — **not all 44** |
| 264 | postings in the P04 rehearsal | a **smaller captured slice**: four Himalayas pages plus three bulk feeds. Fewer retained rows than P03 is a smaller input, not a regression |
| 11 | retained in the P04 rehearsal (5 strong, 6 needing a check) | not comparable to 44 |
| 296 | tests passing now | the P03 row in `EXECUTION_TIMELINE.md` read "247", which was P02's figure; corrected in place with the correction noted |

---

## 8. Reconciliation — measured

- **The handoff contradiction is corrected.** P03's handoff said in §6 that the additive
  `CanonicalJob` / `DiffState` fields "are ignored by the old code" while its own §8 correctly said the
  opposite. The baseline uses `ConfigDict(extra="forbid")` and **rejects** 18 job fields and 5 diff
  state fields; the unmodified P02 probe re-confirms `accepts_current_record: false` this run. The new
  handoff states once that the data downgrade is **required**, and the earlier claim is withdrawn
  rather than deleted.
- **Rollback order and writer quiescence are now explicit** (handoff §6.0): quiesce the writers and
  wait for in-flight executions, then downgrade the data, then revert the source, then re-enable.
  Re-enabling early puts old code and new-format data in the same window, which is the one combination
  that fails.
- **A broken evidence path was found and corrected.** P03's handoff cited
  `evidence/rollback_validation.txt` relative to its own directory; that file lives in the **P02** run
  root. The new handoff gives full run-root-qualified paths, and every path it cites was verified to
  exist.
- **Continuity surfaces synchronized:** `START_HERE.md`, `project-factory/ORCHESTRATOR_BOOTSTRAP.md`,
  `meta/SESSION_STATUS.md`, `meta/PHASE_LEDGER.md`, `meta/EXECUTION_TIMELINE.md`,
  `meta/DECISION_LOG.md` (D-015), `claude_handoff/PACKET_REGISTRY.tsv`, `docs/PLAN.md` and the
  controlling plan's execution log. Execution, acceptance and deployment are kept distinct everywhere:
  P04 execution is complete, local acceptance is met, **deployment is not authorized**.
- **Historical returns preserved.** No earlier run's evidence, review or return was edited. The one
  correction inside a historical row is the stale test count in the timeline, and it says it was
  corrected.

---

## 9. Gates still open — unverified, and not closed by this run

| Gate | Status |
|---|---|
| Discovery running in AWS | not verified — first scheduled run |
| Production HTTP transport, four keyless feeds | **not verified**, and §5 gives a fresh reason to doubt this machine's path |
| Authenticated Adzuna | not verified — needs the credential *and* a real search returning results |
| General-industry coverage | open — depends on Adzuna succeeding in production |
| Careers-URL resolver live path | not verified |
| Rollback downgrade against real state | rehearsed only |
| Freshness across two real production rounds | rehearsed on real payloads; day two in production is the check |
| Whether a plausibly-local worksite should auto-approve | **deliberately unresolved** — needs the operator's reading, §2.2 |

No requirement in the packet is left unpassed. Two are passed with their limits stated rather than
silently: the rehearsal is real-data-with-mocked-transport (§6), and the per-test pre-repair table
distinguishes what was executed against the old code from what is derived from the removed regexes
(§2.5).
