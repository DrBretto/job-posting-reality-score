# P03 independent return review

Date: 2026-09-24. Action: local run-return review, not implementation or deployment.
Recommendation: **revise_release**. P03 executed; its release-unlock recommendation is not adopted.
Preserve the original return and evidence. This is the sibling JPRS repository's file-based factory,
not an Infotropy governance record: its `AGENTS.md` delegates to
`project-factory/ORCHESTRATOR_BOOTSTRAP.md`, whose Operating Mode explicitly forbids using the
Infotropy spine for ordinary work here. No file in the Infotropy repository is changed by this review.

## Verified repairs

Evidence: independently reran the full suite: **252 passed in 3.10 seconds**. The unmodified P02
review probe confirms Adzuna credentials now reach the actual mocked HTTP boundary, all four prior
screening examples are corrected, and the newest feed page is revisited. Baseline data compatibility
depends on the new downgrade step; its forward/downgrade/read/restart tests pass locally. No live
recovery was attempted.

## R1 — Location filtering contradicts the commute policy

Evidence: `src/candidate/screening.py:509` uses unqualified town names and inconsistent state suffixes;
line 817 lets a remote token bypass required attendance and residence constraints. Independent
fixtures using the production remote-mode detector reproduce:

| Posting | Observed verdict |
| --- | --- |
| Belmont, NH; onsite | EXCLUDED |
| Belmont NH; otherwise identical | ELIGIBLE |
| Alton, IL; onsite | ELIGIBLE |
| Remote / Boston, MA; mandatory Boston attendance three days weekly | ELIGIBLE |
| Remote, US; employment limited to California or New York residents | ELIGIBLE |

Operator preference remains approximately 30 minutes from Laconia, Plymouth discussable, no Boston
or Portsmouth commuting, genuinely NH-eligible remote work allowed. A guessed town list is not a
drive-time measurement. Normalize place/state and resolve attendance/residence constraints; preserve
uncertain local leads for review rather than inventing a new exhaustive whitelist. No paid routing
service or broader location-feature project is required.

## R2 — The production report never receives its freshness timing

Evidence: `assemble_report_input` in `src/report/handler.py:1195` never supplies `run_started_at` or
`previous_run_at`. The renderer instead uses the end of the UTC calendar day and cannot exercise
the since-previous-run branch. Focused tests supply those fields manually, bypassing this boundary.

At 2026-09-24 12:00 UTC, a mocked-S3 reproduction contains an established-source control, an undated
job newly observed an hour ago, and a job published 20 hours ago. The actual handler writes a report
with **0 fresh**; supplying the actual current/previous timing to the same assembled input yields
**2 fresh**. All jobs remain in the complete list: prioritization/labels are wrong, not deletion.

Carry real durable timing through the handler, stored report and retry path. Test missed days,
weekends, cold starts and undated arrivals at that boundary. Keep new-to-us distinct from newly
published. Also test a warm one-job source: `cold_start_sources` currently infers initialization
from timestamp cardinality instead of actual source history.

## R3 — New arrivals on page two still wait behind the historical backlog

Evidence: `src/discovery/handler.py:307` fetches one head page, discards its continuation cursor,
then resumes the old historical cursor. With a five-request budget the independent probe requests:

`HEAD -> OLDER_CURSOR -> OLDER_AGAIN -> EVEN_OLDER -> STILL_OLDER`

The head points to `NEW_PAGE_TWO`, containing a job published two hours ago. That page is never
requested and its job never reaches this run; the persisted backlog advances to `DEEPER_BACKLOG`.
The gap can persist until an old traversal wraps, especially after a busy day or missed weekend.

Preserve bounded, resumable recent-arrival work as well as historical catch-up. Test multiple new
pages above an outstanding backlog, repeated runs, partial failures and insufficient budgets.
Checking only page one is not sufficient; neither is replacing bounded discovery with a full crawl.

## Continuity and handoff defects

Evidence: START_HERE, bootstrap, session status, packet registry and the active plan still call P03
staged. The phase ledger contains both a staged P03 phase and an added completed phase. Execution
happened, but synchronization did not pass.

The deployment handoff retains the old false statement that additive fields are ignored by the
baseline, alongside its new section correctly stating the opposite. Correct the next live handoff;
preserve this historical return. The measurement is 216 registry-absent **employers**, not postings.
Four fresh plus twelve older describes the sixteen new-application-history candidates, not all
forty-four retained roles.

## Next action

A focused executor continuation should repair R1–R3 and reconcile the live handoff/status surfaces.
No new committee or rebuild is needed. Preserve working P01–P03 transport, polarity and downgrade
repairs. Local review must pass before requesting deployment approval. Real authenticated Adzuna,
three keyless feeds' production transport, and live rollback remain separately unverified.

Independent probe: `evidence/p03_independent_review_probes.py`. Results:
`evidence/p03_independent_review_results.json`. The probe uses synthetic jobs, mocked S3 and the
actual report handler; it sends no email and makes no real network/AWS call.

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python \
  project-factory/outputs/open-market-discovery/runs/20260924_runtime_boundary_and_fresh_first_v1/evidence/p03_independent_review_probes.py
```

No runtime source changes, AWS changes, deployment, submissions, commits or pushes were made by
this review. Live-cloud state was not queried.
