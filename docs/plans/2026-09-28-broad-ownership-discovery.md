# Broad-ownership and first/sole-engineer discovery

## Context

`APPLICATION_WORKFLOW.md` gained a section on 2026-09-28: **Broad ownership and first/sole-engineer
preference**. It is a settled operator preference, not a proposal, and it says three things this
repository does not yet do:

1. *"Carry this preference through source discovery, candidate retention, employer research and
   application emphasis."*
2. *"Keep eligible broad-ownership roles available for human/LLM review even when an AI-oriented
   keyword score is low; scoring may prioritize effort, not silently erase plausible openings."*
3. *"Distinguish confirmed sole ownership, a small team with broad ownership, and unknown team
   structure. Do not infer headcount or sole-engineer status from company size, a title, or a lack
   of public engineering material."*

`policy-check` reports `changed since the projection was built: operating_plan, workflow`. The
workflow change is (1)–(3) above. The `OPERATING_PLAN.md` change of the same date extends local
business outreach to software and automation work and states explicitly that *"the first/sole-engineer
employment preference is maintained only in `APPLICATION_WORKFLOW.md`"* — no JPRS behavior follows
from it. Refreshing the hashes before implementing (2) would turn the check green and change nothing
Brett is shown, which is the exact failure the 2026-09-26 run recorded.

### Where the preference is already effective, and where it is not

Traced through the real path: `discovery/handler` → `discovery/queries` → `discovery/admission` →
`candidate/screening` → `scoring/scoring` → `report/handler`.

| Requirement | State before this run |
|---|---|
| Employer-independent work queries reaching ordinary businesses | **Effective.** `queries.py` already has `internal-tools`, `automation-integration`, the no-AI-vocabulary `ordinary-software` recall floor, and eight sector families. No first/sole/founding/generalist phrasings, which are the clues the new section names. |
| Ordinary business, no AI wording, survives screening | **Effective.** `screening.py` excludes on duties, not on an absent AI keyword. |
| Staff title does not imply sole ownership | **Effective, by absence.** Nothing reads a title for team size; `scoring` treats Staff as a −0.08 stretch label. Must stay that way. |
| Low AI-keyword score still reaches a readable review surface | **NOT effective. This is the defect.** |
| Confirmed sole / small team / unknown held apart | **NOT effective.** No such concept exists anywhere in the codebase. |

### The defect, precisely

`report/handler._ranked()` admits a scorecard only when
`card.brett_fit.band in (Band.HIGH, Band.MEDIUM)` — i.e. `brett_fit.score >= 0.40`. Everything below
that lands in `below_fit_threshold_job_ids`: a bare identity in JSON, with no title, no employer, no
link and no reason in any readable section.

`brett_fit` is AI-weighted by construction. Its title lane pays `agentic-ai` 0.30 and `applied-ai`
0.28; a plain internal-applications title matches **no** title signal at all (`internal-tools` covers
`internal tools|internal systems|business systems|business applications` — not `internal
applications`), so such a posting runs the `work-evidence` recall path, whose credit is capped at
0.20. A remote internal-applications role at an ordinary employer with Python/API/reporting duties
and no AI vocabulary scores near 0.32: above the 0.25 exclusion floor, below the 0.40 band gate,
therefore retained in JSON and invisible on the page Brett reads.

That is "silently erasing a plausible opening on an AI-oriented keyword score", stated in the
workflow as the thing not to do.

## Plan

- [x] 1. Record the worktree and trace the real path (above).
- [x] 2. `src/candidate/ownership.py` — a new assessment, deliberately separate from title,
      seniority, industry and fit score. Three-valued team structure (`CONFIRMED_SOLE` /
      `SMALL_TEAM` / `UNKNOWN`), three-valued breadth (`BROAD` / `STATED_NARROW` / `UNSTATED`), each
      carrying the matched text and its section. Reuses `screening.py`'s segmentation, polarity and
      duty-span helpers so there is one vocabulary, not two. No inference from title, company size
      or missing material: unstated is `UNKNOWN` and `UNKNOWN` is never a finding.
- [x] 3. `src/discovery/queries.py` — one new work family, `broad-ownership`, with the clues the
      section names (first/sole/founding engineer, generalist, applications engineer, business
      systems engineer) and match terms for bulk-feed recall. Priority 10, `rotates=False`: it is a
      floor family like `ordinary-software`, not a rotating supplement.
- [x] 4. `src/report/handler.py` — the retention repair. A second admission path into `_ranked`:
      a card below the band gate is retained when it is not policy-excluded, not below the
      `brett_fit` exclusion floor by scoring's own judgment, and carries **real** ownership evidence
      (`is_broad_ownership_candidate`). Such a card lands in the **needs-a-check** section with its
      reason, never in "strong", and ranks last. Ownership scope is rendered on every retained row
      and carried in `_match_json`.
- [x] 5. `config/candidate_policy.json` — refresh the projection **after** 2–4 land, and add
      `broad-ownership-retention` to `RULE_SOURCE_MAP` so the new behavior records its derivation.
- [x] 6. `tests/test_broad_ownership.py` — the acceptance controls, exercising the real production
      functions end to end to a persisted report.
- [x] 7. Independent review by a fresh reviewer; repair in scope; rerun.
- [x] 8. Bounded live public pass; honest disposition for what it finds.

## Execution Log

- **Trace complete.** `_ranked`'s band gate is the single point where a plausible low-score opening
  stops being readable. Everything else on the path already behaves.
- **`ownership.py` added.** Detection is evidence-first: every verdict carries the matched phrase,
  the section it came from, and the polarity check that let it stand. `founding engineer` is
  deliberately a breadth clue and NOT confirmed-sole evidence — the workflow lists it as a search
  clue, and a founding engineer is commonly one of several.
- **Retention path added.** Admission requires ownership evidence, so it is not an unconditional
  promotion: a posting with no ownership signal and a low score is still below the threshold and
  still counted there.
- **Projection refreshed** after the behavior landed, not before.
- **Independent review** returned two material findings; both repaired in scope and re-checked.
  See `INDEPENDENT_REVIEW.md` in the governed run directory.

## Follow-ups

- Adzuna remains credential-gated, and it is the only configured source that spans ordinary
  industries with a location filter. The keyless feeds are remote-job feeds, so the ordinary-business
  reach of the live radar is narrower than the query plan implies. This is a coverage limit to state,
  not a code defect to fix here.
- Production still runs the 2026-09-26 recovery build. Everything in this plan is local.
