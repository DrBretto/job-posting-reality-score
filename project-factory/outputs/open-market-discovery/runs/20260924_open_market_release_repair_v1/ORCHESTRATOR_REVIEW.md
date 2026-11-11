# P02 return review — September 24, 2026

Action class: run-return / evidence. Verdict: **revise_release**. P02 ran and reached its stop;
its claim that R1–R4 are all closed locally is not accepted. No implementation was changed by this
review. No AWS mutation, deployment, real credential use, commit, or application occurred.

## Verified progress

- Independently reran `.venv/bin/pytest -q -p no:cacheprovider`: **209 passed in 2.57s**.
- Read the P02 packet, return, validation, gate, manifest, handoff, affected runtime and tests.
- The connector now supports injected credentials, default selection reaches gated providers,
  Himalayas walks/resumes pages, and the original screening examples have regressions.
- The worktree rollback protects the uncommitted source tree, unlike the previous checkout.
- The saved combined report has 821 jobs: 44 retained, 374 policy-excluded, 403 below fit threshold.
  Retained partitions are 16 new-to-application-history, 21 needs-check, and 7 previously engaged.
  These are neither 821 previously unknown employers nor 16 proven newly posted strong fits.
- Build/CLI validation and live pagination evidence were inspected, not independently rerun here.

## Reproducible evidence

From the repository root, with the existing virtual environment:

```sh
PYTHONPATH=. .venv/bin/python project-factory/outputs/open-market-discovery/runs/20260924_open_market_release_repair_v1/evidence/orchestrator_review_probes.py
```

The probe uses fake credentials, intercepts HTTP locally, and reads the named historical revision
without checkout. It does not use AWS. Its output describes observed behavior, not a PASS request.

## R1 remains blocked: the real HTTP boundary loses credentials

`run_discovery` binds a connector to the SSM-derived mapping and supplies its authenticated URL.
`_live_fetcher(provider, board_token, url)` discards that URL, obtains the unbound registry connector,
and calls `fetch_raw(board_token)`. That method rebuilds the endpoint from process environment.

Observed at mocked `urllib.request.urlopen`, leaving `_live_fetcher` intact: one request with
`app_id=[""]` and `app_key=[""]`, despite nonempty injected fake credentials. Location serialization
is not the failure demonstrated by this probe; the initial unscoped request intentionally has none.

P02's `_capture_transport` replaces `_live_fetcher` itself. Its assertions prove the URL passed INTO
the faulty function, not the request sent OUT. Require the default handler with mocked SSM and
HTTP at the actual transport boundary, preserving the connector/fetcher wiring under test.

## R3 remains blocked: first-match suppression and optionality

Observed synthetic regression cases, using the normal `screen_job` entrypoint:

| Posting text | Current result | Required meaning |
|---|---|---|
| Recorded introduction optional; live human call available instead | EXCLUDED: recorded-video | Do not hard-exclude for an optional step; retain with a process check if needed |
| No recorded introduction required; final round requires one-way video | ELIGIBLE | The later mandatory step must still exclude |
| No security clearance required; pre-start drug screening mandatory | PENDING_CHECK; clearance rule suppressed | The separate mandatory drug screening must still exclude |
| Build sales tools AND carry a sales quota | PENDING_CHECK; sales rule suppressed | Software duties do not cancel an explicit quota |

`_find` examines only the first match, so a negative statement can suppress later positive
requirements. The software-artifact guard also blankets distinct duties in a shared clause.
Video/AI-interview branches treat `optional` as required. Fix evidence aggregation and attribution,
not four string exceptions. Ambiguity remains reviewable; candidate policy is not to be rewritten.

## R4 remains blocked: source-safe rollback is not data-compatible rollback

The handoff says additive fields are ignored by the previous reader. In revision `e549a73`,
`CanonicalJob` uses `extra="forbid"`. Reading a minimal current-version monitored-job record through
that exact historical model fails on 18 added fields, including `employer_name`, `source_kind`,
`verification_state` and `provenance`. This is not confined to ignored `discovery/` data: the new
collector/differ also writes shared monitored-job records. The differ's state is strict too.

Prove rollback against records and state actually written by the candidate release, with AWS mocked
or an isolated local replay. Preserve both source work and data. No production deletion, in-place
downgrade, or blanket state reset is authorized here. CLI syntax checks alone do not establish it.

## F1: newly clarified fresh-first objective is not implemented

This is the operator's clarification while P02 ran, not a retroactive claim that P02 omitted an
explicit first-24-hours requirement. The morning round should prioritize genuinely fresh credible
openings, ideally within 24 hours, while retaining older exceptional fits and missed-day catch-up.

Observed two-run probe: day one saves `OLDER_PAGE_2`; day two requests only that cursor, not the head.
The production five-page budget changes the amount traversed, not that scheduling rule. New head
arrivals wait until the historical walk finishes. Adzuna also allocates old query backlog first.
Report `NEW` means no application history, not recent publication; Adzuna uses a 30-day lookback.

Protect fresh-head checks alongside fair bounded catch-up. Keep published/updated/first-seen and
last-verified dates distinct, preserve source lag/unknown age, and do not turn 24 hours into an
exclusion cutoff. A job posted since the prior check must be surfaced despite a nonempty backfill.
No promise of universal sub-24-hour capture is justified by delayed sources or a daily schedule.

## Supporting corrections, not separate projects

- Bootstrap, session, phase ledger and plan disagree about whether P02 is staged or executed.
  Historical executor verdicts stay intact; live routing must point to this review and its successor.
- Cost arithmetic: 512 MB for 10–30 seconds is 5–15 GB-seconds, not 0.25; 30 runs gives 150–450,
  not 7.5. At the handoff's stated unit price that is $0.0025–$0.0075/month compute. This alone need
  not break the broad estimate, but recompute request/storage assumptions with actual pagination.
- Coverage JSON reports 220 observed employers while the validation prose says 221; reconcile
  cohort and counting method rather than treating both as the same measurement.

## Next action

One bounded executor continuation: `JPRS-L2-P03-runtime-boundary-and-fresh-first-v01`.
Keep working discovery code and all P01/P02 historical evidence. Fix R1/R3/R4, implement the fresh-first
priority within existing discovery/reporting, then re-review. Deployment and credentials remain
separate explicit operator approvals. No new committee or architecture rebuild is needed.
