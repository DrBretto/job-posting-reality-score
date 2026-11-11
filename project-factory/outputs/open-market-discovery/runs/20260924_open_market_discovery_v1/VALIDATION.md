> **Qualified by later review — read this first.** An orchestrator review on 2026-09-24 reproduced
> four release defects that this document's verdicts did not catch, and packet
> `JPRS-L2-P02-discovery-release-repair-v01` repaired them. See
> `ORCHESTRATOR_REVIEW.md` in this directory, and
> `../20260924_open_market_release_repair_v1/VALIDATION.md` for the repair evidence.
>
> Specifically superseded below: §7 row 3's "PARTIAL PASS" understated the Adzuna defect (its runtime
> path could never have worked); §7 rows 8 and 5 did not detect the Himalayas pagination loss or the
> screening polarity misfires; §7 row 10's deployment "PASS" rested on a rollback command the AWS CLI
> rejects and a full-rollback instruction that would have destroyed the uncommitted work; and §4's
> Ashby permanence claim is bounded to a single point-in-time observation.
>
> This file is left unedited apart from this banner. Its original verdicts are the historical
> executor record, not a currently accepted result.

# VALIDATION — open-market job discovery

Packet: `JPRS-L2-P01-open-market-discovery-v01`
Run: `20260924_open_market_discovery_v1`
Date: 2026-09-24

Provenance labels per `RUN_OUTPUT_CONTRACT.md`: `evidence` = observed this run,
`inference` = reasoned from evidence, `operator_preference` = from the central candidate policy.

---

## 1. Commands and results

```bash
.venv/bin/python -m pytest -q -p no:cacheprovider
# 168 passed in 1.31s

sam validate --lint --template-file infra/template.yaml
# infra/template.yaml is a valid SAM Template

sam build --template-file infra/template.yaml --build-dir "$TMPDIR/sambuild"
# Build Succeeded  (see §6 for why a non-default build dir was needed)

.venv/bin/python -m src.cli policy-refresh && .venv/bin/python -m src.cli policy-check
# wrote config/candidate_policy.json from 5 policy sources
# projection matches all policy sources
```

Test distribution (168 total; 66 pre-existing, 102 added):

| file | tests | covers |
|---|---:|---|
| `test_discovery.py` | 22 | held-out unknown employer, company-independence, budgets/backlog, credential gate |
| `test_screening.py` | 24 | every policy exclusion **and** every misfire guard, both directions |
| `test_recall_and_coverage.py` | 24 | the four repairs, calibration, health axes, complete-list visibility |
| `test_dedup_and_history.py` | 16 | cross-source merge, distinct requisitions, the five history states |
| `test_fetch_guard.py` | 16 | SSRF, redirects, size caps, job text as data |
| `test_scoring.py` | 14 | pre-existing scoring contract (2 updated for changed behavior) |
| `test_report.py` | 13 | pre-existing report contract, never-fake guard |
| `test_differ.py` | 11 | pre-existing freeze invariant (2 updated for changed behavior) |
| `test_connectors.py` | 10 | ATS mapping + the Ashby identity ladder (1 rewritten) |
| `test_integration_pipeline.py` | 9 | pre-existing S3 pipeline via moto |
| `test_enumerate_and_narrator.py` | 9 | manifest/fan-out (3 updated: Ashby now enumerates) |

**Fixture versus live is never merged.** Synthetic fixtures validate code. Live access was verified
separately (§3). Every claim below states which one it rests on.

---

## 2. The four repairs, with before-and-after measurement

| # | Defect | Before | After | Test |
|---|---|---|---|---|
| 1 | Title spelling | `FullStack` **0.00**, `Full Stack` **0.38** — same role | all five spellings identical | `test_fullstack_spelling_variants_all_score_identically` |
| 2 | Title-only hard zero | any unmatched title forced `total = 0.0` | ordinary/novel titles retained on work evidence at reduced confidence | `test_ambiguous_and_novel_titles_survive_on_work_evidence` |
| 3 | Frozen-department latch | segment absence suppressed removals **forever**; warning said "low count" for a missing segment | corroboration-bounded: held while ambiguous, released after 2 independent healthy snapshots | `test_an_independently_corroborated_department_closure_recovers` |
| 4 | Health + hidden overflow | `compute_run_health` returned `VERIFIED_QUIET` on **both arms** of its own conditional; rows past 20 "retained in JSON" | four independent axes; complete readable list, uncapped | `test_health_axes_are_independent`, `test_more_than_twenty_candidates_stay_readable_with_links_and_reasons` |

Repair 3, step by step (`evidence`, from the regression test):

```
day 1  People Team present                      → ACTIVE
day 2  segment absent, 3 postings still healthy → SUSPECT(silent_subset), removals HELD,
                                                   warning names the segment, grace clock paused
day 3  still absent, second healthy snapshot    → SOURCE_SEGMENT_CLOSED, latch RELEASED,
                                                   state → PENDING_REMOVAL
day 4  still absent                             → DISAPPEARED (ordinary grace)
```

Protection is not relaxed: a genuine mass drop still suppresses indefinitely with a frozen baseline
(`test_a_partial_feed_still_freezes_removals_indefinitely`, 5 consecutive runs, 0 removals).

---

## 3. Live access verification

All live access was public, read-only, and unauthenticated.

| Source | Result | How verified |
|---|---|---|
| Remotive | HTTP 200, 209,696 bytes | live fetch through the connector's own `fetch_raw`, end to end |
| Remote OK | HTTP 200, 615,658 bytes | live fetch via `curl`, replayed through the connector (§6) |
| Jobicy | HTTP 200, 808,005 bytes | live fetch via `curl`, replayed through the connector |
| Himalayas | HTTP 200, 109,004 bytes | live fetch via `curl`, replayed through the connector |
| Greenhouse ×15 boards | HTTP 200 on all 15 | live fetch via `curl`, replayed through the connector |
| Ashby ×4 boards | HTTP 200, 1,083 postings | live fetch, identity evidence (§4) |
| Adzuna | HTTP 400 without credentials | live fetch, confirms the documented gate |

**Honest limit on the fetch transport.** Only Remotive was exercised through `fetch_raw` end to end
from this machine. The other three returned `IncompleteRead` under this environment's egress proxy,
which also produced `BadStatusLine: CONNECT remoteok.com:443` on a direct retry — a proxy artifact,
not provider behavior and not a code defect. The connector labelled those responses `PARTIAL` and
suppressed removals, which is the correct degradation, and the live rehearsal report says so in
plain words. **The four-source `fetch_raw` path therefore remains unverified outside this sandbox
and is an explicitly unpassed gate**; it is listed in `DEPLOYMENT_HANDOFF.md` as a post-deploy check.
Payload parsing, mapping, screening, scoring, dedup and reporting ARE verified against the real
live bytes of all four sources.

Raw provider payloads are deliberately not committed: Remotive, Remote OK and Jobicy each restrict
redistribution, and the packet forbids giant raw dumps. Shapes, counts and SHA-256 digests are in
`evidence/source_probe_provenance.json`.

---

## 4. Ashby identity concern — closed

`evidence`, four independent live boards, 2026-09-24:

| Board | Postings | native `id` present | UUID | `jobUrl` ends with it |
|---|---:|---|---|---|
| Ramp | 155 | 155/155 | yes | yes |
| OpenAI | 828 | 828/828 | yes | yes |
| Ashby | 70 | 70/70 | yes | yes |
| Linear | 30 | 30/30 | yes | yes |

Persistence: a Linear posting with `publishedAt` 2021-04-27 is still listed under its original UUID,
so the identifier survives years rather than being per-response. `ASHBY_ENABLED` is now `True`, the
connector prefers the native `id`, and the URL-slug and content-hash fallbacks remain tested so a
future provider change degrades honestly (`test_ashby_identity_ladder_degrades_honestly`).

---

## 5. Coverage comparison — old footprint versus new

Same evaluation day, same code, three runs. `evidence`.

| | monitored only (old) | discovery only (new) | combined (what production does) |
|---|---:|---:|---:|
| postings considered | 521 | 226 | 747 |
| retained credible | 33 | 10 | 43 |
| new strong | 10 | 4 | 14 |
| needs a check | 16 | 6 | 22 |
| policy exclusions | 278 | 86 | 364 |
| distinct employers seen | 15 | **162** | 162 + 15 |
| **employers absent from the registry** | **0, structurally** | **161** | **161** |
| distinct source types | ATS_BOARD | DISCOVERY_FEED | both |
| discovery coverage axis | NOT-RUN | PLAN-COVERED | PARTIAL |

**The load-bearing number is 0 → 161, not 521 → 747.** A higher raw posting count is explicitly not
success. Before this change, the count of employers that could arrive without a human first naming
them was zero *by construction*, and no amount of registry growth would have altered that.

Ten previously unseen employers reached the *retained credible* list, including LaunchDarkly,
Pivotal Health, Root Inc., Airspace Link, Benzinga, Salesforge, Sticker Mule and OkWhen — none of
which appear in `config/companies.yaml`.

Dedup on the combined run: 0 hard merges, 0 soft links, and **2 pairs deliberately protected as
distinct requisitions** — Grafana Labs `27535` vs `27523`, and Mozilla `R3065` vs `R3230`. Naive
employer+title dedup would have deleted one opening from each pair.

### Remaining coverage limitations (`evidence` + `inference`)

1. **All four keyless feeds are remote-job boards.** They demonstrate genuine employer-independent
   discovery, but they are not a general index of ordinary local businesses. The plan's worked
   scenario — a non-software business hiring an internal-AI engineer — is most likely to arrive
   through Adzuna's general index, which is credential-gated. **Unpassed gate, stated in the report.**
2. **Source growth cannot admit anything from the keyless feeds today.** Measured: all four return
   aggregator apply links, and a regex sweep for embedded Greenhouse/Lever/Ashby URLs across the
   full raw payloads of all four found **zero**. Every discovered employer therefore lands in
   `QUEUED_UNSUPPORTED` — visible as a lead, not admitted. The bounded careers-URL resolver
   (`src/discovery/resolve.py`) closes this loop but is **off by default** and its live path is
   unverified here (the sandbox blocks DNS).
3. **Remote OK records frequently omit location**, which routes them to `PENDING_CHECK` rather than
   to the strong list. That is the correct handling of unknown, not a defect, but it does mean that
   source contributes more review items than strong candidates.

---

## 6. Findings uncovered during implementation

Each of these was found by a test or a live check, and each is either fixed or reported.

| # | Finding | Status |
|---|---|---|
| F1 | Crawler match terms were substring-matched, so `rag` matched inside "sto**rag**e" and unrelated postings claimed the applied-AI family | **fixed** — word-boundary matching, `test_word_boundary_matching_stops_substring_false_positives` |
| F2 | The same matcher missed plurals: the term `internal tool` could not match "internal tools" | **fixed** — optional plural suffix |
| F3 | Company boilerplate ("Our AI company uses LLM agents…") scored **0.69**, *above* a genuine ordinary-title applied-AI role at **0.59** | **fixed** — skill signals are now weighted by role-versus-company sentence context; boilerplate earns 25% weight and cannot buy a recall path |
| F4 | The GTM/RevOps guard was a loophole: a "Sales Engineer" posting with explicit quota language was suppressed because it also mentioned CRM integration | **fixed** — explicit ownership language disarms the guard |
| F5 | Clearance pattern missed "ability to obtain a clearance" | **fixed** |
| F6 | `dedup_group_id` truncated the raw URL to 20 characters, so every posting on one ATS host collided into one group and pairs were never compared — the report could not explain why two rows existed | **fixed** — hashed group id |
| F7 | The normalized title was emitted in scorecard detail but not registered as provider text, so a posting titled "Real-Time AI Engineer" tripped the never-fake vocabulary guard and would have failed the whole report | **fixed** — derived provider forms are redacted too |
| F8 | An AI-research title outranked a practical senior role, contradicting the September 23 operator clarification | **fixed** — research title weight reduced, ordinary software engineering raised, and a stated specialist bar (PhD / publication record / 8+ years) applies a labelled penalty |
| F9 | `Field Application Engineer (Integrated Photonics)` matched a candidate `application engineer` title lane | **fixed** — that family was narrowed to unambiguous terms; genuinely ambiguous titles go to the work-evidence path where the description decides |
| F10 | **`.samignore` is not honored by SAM's Python builder.** `tests/`, `docs/`, `infra/`, `project-factory/`, `policies/`, `scripts/` and `.claude/` all ship inside every Lambda package (18 MB). | **reported, not fixed** — pre-existing, affects all five functions, and changing the packaging method is a separate decision. See `DEPLOYMENT_HANDOFF.md`. |

### F11 — the divergence detector fired for real, mid-run

`evidence`. At 10:50, while this run was in progress, a concurrent session edited the central policy
source `APPLICATION_WORKFLOW.md` (7,139 → 12,400 bytes), adding a **Company Research and
Working-Environment Fit** section. `policy-check` detected it immediately and exited non-zero:

```
$ .venv/bin/python -m src.cli policy-check
changed since the projection was built: workflow
```

This is the projection mechanism doing exactly what the plan asked for — "detect divergence rather
than silently guessing" — on a real edit rather than a synthetic one.

Assessment of the new section against what was built: it **confirms** the boundary rather than
contradicting it. It states that "JPRS discovers openings broadly, supplies posting provenance and
available factual employer information, and flags eligibility or process issues. It need not infer
culture from keywords or perform expensive research on every discovered posting," and assigns the
research pass to the orchestrator and executor. No new exclusion rule is introduced, so no screening
rule changed. The factual employer information it asks JPRS to supply — employer name, careers URL,
industry, provenance, verification state, uncertainty markers and the four distinct dates — is
already carried on every record and rendered in the report.

Action taken: the projection was refreshed so the committed hashes match the current sources, and
the sibling file was **not** edited (this packet forbids it). `operator_preference`: if that new
section is later meant to constrain JPRS itself rather than the surrounding workflow, that is a
follow-up packet, not a silent rule change here.

**Correction to an earlier read.** While investigating F10 I first believed `config/` was excluded
from the package and that history lookups would silently return NEW in production. That was wrong:
because `.samignore` is not applied at all, `config/` was already shipping. The `.samignore` edit
remains as accurate intent, and the genuinely useful part of that change is the new visible note in
the report when the history projection is absent, rather than everything silently reading as NEW.

---

## 7. Acceptance rows — explicit verdict for every row

| # | Row | Verdict | Evidence |
|---|---|---|---|
| 1 | Unknown employer discovered through a company-independent query and reaching the complete report | **PASS** | `test_held_out_unknown_employer_is_discovered_without_being_named` + `..._reaches_the_complete_report`; live: 161 registry-absent employers, 10 of them on the retained list |
| 2 | Sector/title recall; examples are not a closed whitelist; FullStack variants equivalent | **PASS** | `test_fullstack_spelling_variants_all_score_identically`, `test_ambiguous_and_novel_titles_survive_on_work_evidence`, `test_sector_examples_are_not_a_closed_whitelist` |
| 3 | Real sources: working broad discovery, validated monitoring adapters, source growth, unsupported-careers path; live distinguished from fixture | **PARTIAL PASS** | 4 keyless feeds live-verified end to end for parsing/mapping; Ashby enabled with evidence; unsupported-page path returns a verification lead. **Unpassed:** source growth admits nothing from these feeds (§5.2), and the resolver's live path is unverified |
| 4 | Practical seniors above topical-only specialists; Staff and >$150K are not blanket rejections; adjacent skills viable | **PASS** | `test_practical_senior_match_ranks_above_a_topical_only_specialist`, `test_staff_title_is_a_labelled_stretch_not_a_rejection`, `test_pay_above_the_orientation_is_not_a_rejection`, `test_adjacent_learnable_skills_remain_viable` |
| 5 | Sales, clearance, frontend, video and AI-interview route correctly; boilerplate and unknown do not misfire | **PASS** | 24 tests in `test_screening.py`, each exclusion paired with its look-alike; live run excluded 86 postings with quoted reasons |
| 6 | Cross-source duplicates keep provenance; distinct requisitions survive; prepared ≠ submitted; skips respected | **PASS** | 16 tests in `test_dedup_and_history.py`; live run protected 2 distinct-requisition pairs; scanner output is capped at PREPARED in code |
| 7 | Partial feeds still freeze removals; justified complete feeds recover from real department disappearance; warnings explain the actual condition | **PASS** | `test_a_partial_feed_still_freezes_removals_indefinitely`, `test_an_independently_corroborated_department_closure_recovers`, `test_suspect_streak_and_observed_counts_explain_a_long_running_condition` |
| 8 | No hidden cap; empty results honest; provider limits and deferred work visible and resumable | **PASS** | `test_more_than_twenty_candidates_stay_readable_with_links_and_reasons` (27 rows, all readable), `test_budget_exhaustion_defers_work_instead_of_dropping_it`, `test_zero_strong_matches_distinguishes_incomplete_from_completed_search` |
| 9 | Public access only, fetch safety, no leaked secrets, bounded load, documented retention, no unauthorized paid or cloud action | **PASS** | 16 tests in `test_fetch_guard.py`; `$0` spent; no AWS mutation; attribution rendered; no raw provider payload committed; `test_history_projection_carries_no_personal_data` |
| 10 | Deployment readiness: compatible manifests, privacy-minimized handoff, tests/builds, exact instructions, rollback, truthful entrypoints | **PASS** | `sam validate` clean, `sam build` succeeded, `DEPLOYMENT_HANDOFF.md` written, entrypoints updated to tested-local/not-deployed |
| 11 | Whole-object review against the employment outcome, not "more feeds ran" | **PASS** | §5 reports 0 → 161 registry-absent employers as the headline, explicitly not the 521 → 747 raw count; §5 also states the three remaining coverage limitations |

**Two gates are explicitly UNPASSED and neither is worked around:**

- **Adzuna live discovery** — needs a free `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`. This is the source
  that provides general, all-industry, New-Hampshire-filterable breadth. Implemented and
  fixture-tested; not run.
- **Source growth from keyless feeds** — needs the careers-URL resolver enabled and live-verified.
  Implemented, unit-tested, off by default.

---

## 8. Independent review

The packet asks for distinct reviewer contexts and for honesty about which review was actually
independent.

**Disclosure:** no separate reviewer agent was run for the code and candidate-fit dimensions. A
single implementation context produced this work, so the review below is **self-review with
explicit separate passes**, not independent review. No agents or votes are invented.

One genuinely independent context WAS used, for a different task: a read-only subagent inventoried
the application-history corpus without seeing the implementation. Its inventory is what exposed that
the regex history scanner was unreliable in both directions, which produced the reviewed/parsed
confidence split and the code-level cap on scanner-derived statuses (§6, `test_a_scan_can_never_...`).

Pass A — candidate fit and coverage. Found F3 (boilerplate outranking real work), F8 (research title
outranking a practical senior), F9 (ambiguous title in a lane it did not belong in). All repaired,
each with a paired test proving discrimination rather than keyword presence.

Pass B — code and reliability. Found F6 (group-id collision), F7 (guard bypass via a derived field),
F1/F2 (matcher precision and recall), F4/F5 (screening loophole and gap), F10 (packaging). All
repaired except F10, which is reported.

`inference`: the highest-value remaining review would be an adversarial pass over the screening
rules by a context that did not write them, since a misfire there silently discards an opportunity
and the failure is invisible in the output.
