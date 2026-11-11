# Open-market job discovery overhaul

## Context

Status: P06 remains the DEPLOYED version; P07/P08 are local only. Independent P08 review confirms
350 passing tests, the original live-write repair, and 36/36 archived P06 source hashes. It also
reproduces lost report candidates when the FIRST pending-ledger write fails, and false-green release
helpers. P08 execution is complete, but release acceptance is `revise_implementation`, not waiting
only on deployment approval. Bounded P09 repairs these same publication/release boundaries; no new
committee, provider, candidate policy or infrastructure redesign. See the P08 run's
`ORCHESTRATOR_REVIEW.md` and `JPRS-L2-P09-publication-commit-boundary-and-verification-v01`.

The operator's September 24 direction is to find useful openings wherever the work exists,
including an unknown small business that needs an engineer to integrate AI or improve its
internal systems. A fixed company roster, even a much larger one, cannot satisfy this goal.
The product is a job-search aid for near-term employment and income, not a prestigious-employer
watchlist, an AI-research job board, or an AWS exercise with incidental employment benefits.

JPRS currently monitors 15 Greenhouse boards selected August 2. The live September 24 report
contains 526 postings and 33 ranked matches. This establishes coverage of those boards, not
coverage of the market. The current collector, differ, storage, and reporting are useful
infrastructure to extend; rebuilding them without a demonstrated need would delay the outcome.

This document controls the overhaul. The execution packet supplies sequencing and tests, not
a competing product vision. Older instructions to select one to three jobs are superseded.

### What success means

A morning round discovers previously unknown employers and openings, verifies what it can,
and presents every credible opportunity with an application link and a useful reason to pursue
or skip it. A useful opening at an employer absent from yesterday's registry must be able to
arrive without Brett or an agent first naming that employer. Newly discovered sources can then
be monitored so future postings are cheaper and quicker to find.

The worked acceptance scenario is an unseeded, non-software business hiring someone to build
AI-enabled internal tools, integrations, or operational automation. This is a positive example,
not a required industry, title, company size, or daily hit quota. Larger employers, software
companies, full-time employment, and credible paid contracts remain eligible.

No finite search can promise every job on the internet. The system must actively expand its
search horizon and show what it actually covered, what remains queued, and what it could not
access. It must not quietly redefine broad discovery as checking a fixed roster successfully.

### Candidate policy: one authority, not new scattered rules

Read the current sources in the sibling Infotropy repository:

- `../Infotropy Book/INBOX/Employment Search/APPLICATION_WORKFLOW.md`
- `../Infotropy Book/INBOX/Employment Search/SEARCH_PREFERENCES.md`
- `../Infotropy Book/INBOX/Employment Search/OPERATING_PLAN.md`
- `../Infotropy Book/INBOX/Employment Search/CANDIDATE_FACTS.md`
- `../Infotropy Book/career-factory/outputs/candidates/brett-westerlund/master-resume/MASTER_RESUME.latest.md`

The workflow is authoritative for candidate screening. Do not edit those sources in this run,
put hiring preferences in AGENTS.md, or create another prose policy that can drift from them.
If production requires a machine-readable profile, keep one versioned projection with source
paths, hashes, and reviewed policy mappings; detect divergence rather than silently guessing.
Only job-related criteria go to cloud search/ranking. Do not upload the master resume, contact
details, personal circumstances, or sensitive explanations behind preferences to providers.

Calibration to preserve: practical senior software engineering, roughly five to seven years
of competitive experience, with applied AI as an advantage. Around $150K is an orientation,
not a salary gate. Evaluate actual scope and employer context, not prestige or title. A small
company's hands-on architect can fit; a large company's specialist role may not. Learnable
framework gaps do not equal deep-specialization gaps. Strong conventional engineering matches
are eligible. Do not translate the operator's urgency into fabricated experience or weak filler.

Preserve the explicit exclusions, including sales responsibilities, government/clearance
paths, frontend specialization, AI-conducted interviews, and required recorded candidate video.
Apply them to the actual role/process, not incidental text: benefits boilerplate mentioning
commission is not proof an engineering role has a quota; a live human video call is not a
recorded-video application; building sales tools is not doing sales. Unknown is not confirmed
eligible and is not automatically excluded. Location eligibility must work from New Hampshire;
do not invent relocation, travel, or commuting commitments.

## Required product behavior

### 1. Discovery and monitoring are different capabilities

- Add recurring employer-independent discovery using practical public search/job-data sources.
  Search across work performed, title variants, and sectors; include broad queries that do not
  restrict company, ATS, industry, or an exact AI title. Industry-specific queries supplement
  that breadth rather than becoming another whitelist.
- Include internal tools, workplace/business applications, workflow automation, integrations,
  document/data extraction, AI implementation, and applied backend/cloud work. Explore ordinary
  businesses as well as software vendors: examples include logistics, hospitality, manufacturing,
  insurance, healthcare, retail, professional services, and construction. These are examples,
  not quotas or an exhaustive taxonomy. Existing exclusions still apply.
- Distinguish job openings from course pages, talent directories, staffing lead capture,
  speculative business needs, and closed listings. Local-business website-repair outreach is
  a separate Career Factory method, not a job invented by this system.
- Treat Greenhouse/Lever/Ashby board monitoring as follow-up collection, not open-market search.
  Validate and use the existing adapters where they work. Resolve the Ashby identity concern
  with tests and evidence; merely leaving the adapter disabled is not completion.
- Find company-native careers pages and ATS families beyond those three. Provide a safe,
  bounded public-page/JobPosting-data path or an explicit verification queue for unsupported
  pages. Do not require implementation of every ATS before shipping useful broad discovery,
  and do not discard a lead just because its ATS lacks a connector.
- Source registration must be able to grow through validated discoveries under a documented
  admission policy, without editing a 15-company YAML list by hand every morning. Separate
  observation from permission to collect; validate public scope, host, provenance, cadence,
  terms, and resource limits before admission. Preserve operator disables and source provenance.

### 2. Practical, durable source access

- Investigate current official access, terms, coverage, pagination, freshness, rate limits,
  credentials, and cost. Search snippets and aggregators are leads, not final job descriptions.
  Verify against the employer or authorized posting where possible; keep uncertainty visible.
- There must be at least one working employer-independent discovery path. A manual URL importer,
  hard-coded demonstration list, or provider interface without a working implementation does
  not pass as discovery. Retain a simple operator-assisted import path as a supplement.
- A Codex/Claude interactive web-search tool is not a deployable Lambda search API. State the
  real recurring dependency and credential setup rather than pretending the chat tool will be
  available in the scheduled job.
- Candidate sources include Brave's web-search API, Adzuna's job-search API, and permitted
  public job feeds. They are research candidates, not a mandate to integrate all of them.
  Choose the smallest practical combination that demonstrates broad employer discovery and
  non-tech coverage. Avoid an abstraction framework larger than the useful implementation.
- Missing credentials or approval are explicit deployment blockers. Complete independent local
  work and a bounded interactive live discovery rehearsal where possible, but do not mark
  unattended discovery verified if only fixtures or an interactive surrogate ran.
- Search/query limits are operational budgets, not an application quota. Show saturation,
  pagination limits, skipped query families, source limits, and resumable backlog. Rotate and
  revisit under-covered searches; never silently erase good candidates beyond a display cap.

#### Fresh-first clarification — September 24, while P02 ran

Prioritize genuinely recent credible openings for the morning round, ideally allowing Brett to
apply within 24 hours of posting. This is not an age-based exclusion or a guarantee of universal
coverage. New head arrivals must be checked promptly even with an unfinished older browse/query
backlog. Preserve bounded fair catch-up, missed-day/weekend coverage and older exceptional fits.

Display posting age and its provenance when known; first-discovered today, an updated description
and no application history do not prove newly posted. Preserve unknown age and provider delays
explicitly. The report must make the fresh priority usable without hiding older good opportunities.
Current schedules remain unchanged unless Brett approves a change. P03 must demonstrate multi-run
fresh-head arrival and actual persisted-report behavior, not only successful page traversal.

### 3. Normalize, verify, and deduplicate without losing opportunities

- Keep source URL, employer/application URL, provider identity where available, title, employer,
  location/work mode, employment type, salary when actually published, description, timestamps,
  discovery query/source, verification time, and uncertainty. Preserve native text alongside
  safely normalized text. Dates mean different things: published, updated, first observed, and
  last verified are not interchangeable; do not label old imported jobs newly posted.
- Use stable identifiers/canonical URLs and cautious cross-source matching. Keep provenance
  and aliases. Do not merge different requisitions or location eligibility variants simply
  because employer/title are similar. Ambiguous staffing duplicates need review, not deletion.
- Read existing application history without writing to it. Submitted, rejected, skipped,
  prepared-but-not-confirmed-submitted, and new are distinct. A resume file is not submission
  evidence. Surface useful queued work separately rather than repeatedly calling it new.
- Inspect the description and accessible application requirements before labeling a candidate
  a strong recommendation. An inaccessible or dynamic form gets an explicit pending-process
  check, not a claim that no video/AI interview is required. JPRS does not replace the complete
  live-form inspection required when Career Factory builds a bespoke application.

### 4. Rank for this candidate without brittle gates

- The discovery stage should favor recall; verified exclusions and scope-aware screening improve
  precision later. Do not drop a promising role for a novel title, missing salary, or one
  framework keyword. Do not elevate a role solely because the description repeats AI terms.
- Separate role/work match, actual seniority/depth, location, process friction, freshness,
  verification, and history. Give concise human reasons and unresolved questions. Scores are
  triage aids, not empirically calibrated probabilities of an offer.
- Test title variants such as FullStack/full-stack/full stack and ambiguous titles such as
  application engineer, business systems engineer, integration developer, automation engineer,
  and hands-on AI architect. A title-only empty-match gate cannot silently remove them.
- Include false-positive tests: industrial PLC-only automation, primarily frontend polish,
  AI research requiring a specialist track record, pre-sales, and clearance work. Include
  positive counterexamples with the same ambiguous words in ordinary engineering contexts.
- Do not make an LLM the sole authority for exclusions or invent facts. Existing deterministic
  scoring can improve without a new model service. If semantic review is proposed, justify
  incremental value, cost, reproducibility, and conservative abstention before enabling it.

### 5. Repair health and history as part of the same useful system

- Resolve the demonstrated silent-subset latch without removing protection against genuinely
  truncated feeds. Add a justified reconciliation/recovery path, preserve raw history, and
  distinguish confirmed closure, possible feed loss, stale baseline, and fetch failure.
- State what a warning actually means. Do not label every missing department as a low-count
  download. Split collection health, discovery coverage, freshness, and interpretation health.
  Fifteen successful configured fetches cannot yield an all-market or all-clear claim.
- Handle source failure, rate limiting, replay, identity changes, and concurrent runs safely.
  Discovery, collection, and assembly must use compatible immutable run/source manifests.
  Do not mutate the active production registry midway through a run.

### 6. A morning output that is useful without another investigation

Retain the concise digest, but offer a complete readable candidate list with every retained
credible role and direct links. An explicit paginated/linked full list is fine; hidden JSON-only
overflow is not the human handoff. Show new strong candidates, review-needed leads, useful
previously prepared items, exclusions with reasons, and coverage/backlog separately. Do not
present hundreds of raw hits as hundreds of suitable jobs.

Each recommended row needs employer/title, direct application link, location, compensation
when known, why Brett fits, important gaps/process checks, discovery/verification timestamps,
and history status. Clearly label discovery incomplete versus a completed search with zero
strong matches. No forced daily count and no top-three rule.

JPRS hands opportunities to Career Factory. It does not produce default resumes, change the
master resume, submit applications, contact employers, or schedule new reminders in this work.

## Evidence already established on September 24

These are verified observations, not implementation instructions to reproduce blindly:

- Live `/jprs/companies` exactly matches the 15-entry local Greenhouse registry. Local HEAD
  is `e549a73`; the collector's reported deployment modification date is August 2.
- Today's report has 11 SOURCE_SUSPECT events. Every reason is missing department segments,
  not a failed download. Present observations are still written to current_jobs.json; it is
  historical absence tracking that freezes. Do not falsely describe all current jobs as stale.
- Future's missing People Team job `greenhouse:future#4722812005` remains ACTIVE with zero
  absences despite last_seen_at August 20. Three in-memory replays of the unchanged current
  snapshot repeat the warning and preserve that state. No live state was mutated.
- The Grafana job `6130907004` scores 0.0 with its actual `FullStack` title; changing only that
  spelling to `Full Stack` yields 0.38 in an in-memory test. This proves a filtering defect,
  not that the specific role is a strong recommendation.
- Direct live ID comparisons matched 12 boards exactly to the morning snapshot. Three had
  changes; the four additional IDs carried update times after morning collection and were
  sales/support roles. No additional strong role was established by that check.
- Code pointers: `src/differ/handler.py` silent-subset/removal/history logic;
  `src/report/handler.py` compute_run_health, warning labels and display caps;
  `src/scoring/scoring.py` title signals, blocked_title_lane and scope adjustments;
  `src/common/connectors.py` Ashby flag and supported connectors.
- Optional ephemeral reproductions are in `/tmp/jprs-2026-09-24.json`,
  `/tmp/jprs-current-20260924/`, and `/tmp/jprs-coverage-audit-20260924/`. Re-fetch if absent;
  the packet does not depend on temporary files surviving.

### Source research starting points, checked September 24

- https://docs.greenhouse.io/job-board.html
- https://developers.ashbyhq.com/docs/public-job-posting-api
- https://brave.com/search/api/
- https://api-dashboard.search.brave.com/documentation/resources/help-feedback
- https://developer.adzuna.com/overview
- https://github.com/remotive-io/remote-jobs-api
- https://developers.smartrecruiters.com/docs/endpoints

Brave currently documents $5/1,000 searches and $5 monthly credits, but signup requires a card;
Adzuna needs an app ID/key. Remotive documents a 24-hour delay and attribution/rate conditions.
These are not purchased services or proven fits. Recheck current terms, especially storage
rights and API access; do not commit raw provider output if redistribution is not permitted.

## Plan

- [x] Validate the source approach and write one implementable architecture with explicit costs.
- [x] Build employer-independent discovery and safe continuing source growth.
      *Discovery works. Source GROWTH is built but cannot admit anything from the keyless feeds —
      see the Execution Log; the bounded careers-URL resolver is off by default.*
- [x] Integrate discovery with monitoring, normalization, verification, history, and candidate screening.
      *P07 repaired it locally: discovery owns a durable live view under `discovery/`, and report
      assembly merges it into the same population before dedup/screen/rank/history. Undeployed.*
- [x] Repair warning recovery, title misses, and misleading health/overflow behavior.
- [x] Test source failures and recall/precision; run a live unseeded-employer rehearsal.
- [ ] Deliver a release-cleared integrated candidate report and deployment/rollback package.
      *P07's acceptance harness runs the real enumerate, collector, discovery, differ and report
      stages; P05's two conditional tests were re-scoped onto those producers and their
      "real internal wiring" claim withdrawn.*
      *P07 review: the ordinary path works, but interrupted publication and the release handoff need P08.*
- [x] Finish bounded multi-run continuation and verified build selection through P05.
- [x] Deploy P01–P05 under separate authorization and verify four live keyless feeds (P06).
- [x] Execute P07 discovery-to-report integration and verify the full local path.
- [x] Execute P08 durable-publication repair and correct/verify the release handoff.
      *Executed locally. Captured observations are owed before they can be called published and
      replayed idempotently; the change set, rollback baseline and live check are now derived from
      measurements rather than asserted. 350 tests pass. Undeployed.*
- [x] Execute bounded P09: close the first durable-publication boundary and prevent debt eviction;
      make release/live-inspection checks fail on the reproduced negative controls.
- [ ] Execute staged P10: align actual screening with current central preferences, audit changed
      dispositions and run bounded review plus the full release checks. No fingerprint-only acceptance.
- [ ] After fresh approval, deploy that repair and verify live report delivery and the scheduled path.

### P07 implementation plan — the chosen integration (2026-09-25)

Named before coding, so the ownership question the P06 review asked has one written answer:

| Question | Answer |
| --- | --- |
| Producer | the discovery Lambda, already scheduled at 07:05 |
| Durable candidate representation | `discovery/live/provider={p}/live_jobs.json` — a feed-keyed live view holding each posting plus its observation record |
| Owner of that write | discovery, solely. Report is not granted `PutObject` on it |
| Consumer | `assemble_report_input`, which reads the manifest's `expected_discovery_sources` and merges those postings into `jobs` **before** dedup |
| Invocation path | unchanged: DiscoverySchedule 07:05 → discovery; AssembleSchedule 09:00 → state machine → report |
| Permissions | unchanged: discovery already owns `discovery/*` for read and write, and report already reads it |

Why not the differ, and why not `current/`: an ATS board returns an employer's whole open list, so a
posting's absence from a healthy snapshot is evidence about the posting, which is what the grace
clock and the mass-drop guard are built on. A discovery feed returns a moving window under a page
budget, so absence from it is evidence about the window. Routing discovery through the differ would
read ordinary feed churn as closure. The live view therefore records positive observations only and
carries one bounded retention limit, stated as retention and never as closure.

Two defects were found while tracing the path and are repaired with it:

1. **Discovery job identity was bound to the pagination cursor.** `source_id` was
   `provider:{board_token}`, and for a paginated feed the board token *is* the cursor, so the same
   posting became `himalayas:NEW_TWO#slug` one run and `himalayas:all#slug` the next. Jobs now carry
   the stable feed id; snapshots keep the coordinate, since two pages are two distinct downloads.
2. **The old-report history boundary was discarded.** `resolve_run_timing` recovered previously
   reported ids only from `complete_candidate_list`. The report already delivered on 2026-09-25 has
   that key empty and its rows in `top_matches`, so it read as a round that showed nothing and the
   next morning would have re-announced everything. The fallback now recovers the identities that
   report evidences and records that the list was capped.

### P08 implementation plan — durable publication and a trustworthy release (2026-09-25)

P07's review reproduced the remaining code defect: `persist` writes `raw/`, `normalized/`, `status/`,
the SUCCESS sentinel, coverage, traversal state and growth, and only THEN merges the live view. A
storage failure at that last write strands observations that are already durable. The next fetch sees
a different feed window, `normalized/` for the same `dt` is overwritten by the retry, and the posting
never reaches the candidate representation — in that run or any later one.

Named before coding, as P07's table was:

| Question | Answer |
| --- | --- |
| What is owed | the observations of one run for one provider, as canonical jobs, until they have been folded into that feed's live view |
| Where the debt lives | `discovery/_pending_publication.json` — one discovery-owned object, read and written at a **known key** |
| Why a known key and not a prefix scan | the discovery role grants `GetObject`/`PutObject` on `discovery/*` and **no** `ListBucket` or `DeleteObject`. A design needing either would be an IAM change, which R2.1 forbids and the package-scope rule treats as prohibited |
| How a batch is cleared | by rewriting that object without it, after the live view it belongs to has committed |
| Replay ordering | owed batches are applied oldest-run-first, then the current run's, onto the view loaded from S3 |
| Timing attribution | each batch carries its own `observed_at` and `run_id`; replay never claims an old posting was just fetched |
| Concurrency profile | identical to the existing `discovery/_discovery_state.json` and `_source_growth.json` — one scheduled single-writer stage doing read-modify-write. No new hazard class |

Write order inside `persist`, which is the whole repair:

1. snapshots (`raw/`, `normalized/`, `status/`, sentinel) — unchanged, the court of record.
2. **owe** every touched provider's observations into the pending object. Nothing downstream can yet
   claim them published.
3. coverage, traversal state, growth, proposed registry — coverage now carries
   `pending_publication`, so progress can no longer read as complete while observations are owed.
4. **drain**: per provider, merge its owed batches into the live view, commit the view, then clear
   just that provider from the pending object.
5. rewrite coverage with the residual, which is reached only if the drain completed.

Failure at any of those boundaries leaves a committed view or explicit replayable work, never
silence. A failure between (4)'s view commit and its clear leaves the batch owed a second time, which
is why replay has to be exactly idempotent rather than merely convergent:

- `DiscoveryLiveJob.observed_run_ids` records which runs actually observed a posting, and the
  observation count is that list's length. Re-applying a batch cannot inflate it, in any order.
- Replay is monotonic in time: `last_seen_at`, `last_seen_run_id` and the view's own
  `last_observed_*` never move backwards, so an old batch arriving after a newer run cannot roll back
  the newer observation or erase another provider's committed work.
- The owed-batch count per provider is bounded, and exceeding it is reported in the coverage receipt
  and in `inaccessible` — the same treatment `set_pending_head` already gives a dropped page range.

R2 is verification, not redesign: derive the allowed code-only change set from a fresh build's
packaged contents rather than asserting two functions; recover and hash-verify a real P06 baseline
before recommending deployment, or leave that condition unmet; and make the live check reconcile
discovery-origin identities to dispositions, with controls that separate a genuine zero-fit day from a
missing consumer connection, and an employer-identity check rather than a source-id comparison.

### P09 implementation plan — the commit boundary and verifiers that reject (2026-09-25)

P08's independent review reproduced two things its own work did not close. Both are finished here,
locally; nothing is deployed and P06 remains the running build.

**A. The acceptance point was after the first durable capture, not at it.**

P08 wrote `raw/`, `normalized/`, `status/` and the SUCCESS sentinel and only then recorded the debt,
at one aggregate key. Refusing that FIRST `PutObject` therefore strands a posting that is already
durably normalized: the ledger holds nothing, the same-day retry meets an empty window and overwrites
`normalized/` for that `dt`, and no later run has any automatically reachable record of the job.
Retrying that one key would repair the probe and nothing else, so the boundary is what moves.

| Question | P08 | P09 |
| --- | --- | --- |
| Durable acceptance point | the aggregate ledger write, after every forward-tier write | the **per-provider owed record**, written between that provider's `normalized/` writes and its SUCCESS sentinels |
| Where the debt lives | one object, `discovery/_pending_publication.json` | one object **per provider**, `discovery/owed/provider=<p>/owed_publication.json`; the aggregate object is still written as a receipt, and is still read on load so a debt written by the deployed code is not orphaned |
| How recovery finds it | read the one aggregate key | read each enabled provider's own key — derivable from the connector registry, so still **no `ListBucket` and no `DeleteObject`**, which is what keeps this inside the granted IAM |
| Blast radius of one refused write | the whole run's debt | that one provider's new batch; every peer's record and that provider's earlier batches are untouched |
| Bound on stored debt | drop the oldest batch above five | **compact** the oldest batches into one carry-forward batch (union by job id, earliest observation kept) and expire only what the live view's own retention horizon would discard anyway. Both are reported |

Order inside `persist`, per provider, in provider order:

1. `raw/`, `normalized/`, `status/` for each of that provider's snapshots.
2. **ACCEPT** — read that provider's owed record, union this run's batch into it, write it back.
   Nothing before this point is claimed as accepted; nothing after it can make the jobs unreachable.
3. its SUCCESS sentinels, so no success marker ever precedes the record that makes the work
   recoverable.

Then once, for the run: the aggregate receipt, coverage, traversal state, growth, proposed registry;
the **drain** (per provider: commit the view, settle that provider's record, refresh the receipt);
and the residual coverage receipt. A failure at any one of those leaves either a committed view or
explicit, replayable, automatically reachable work.

What is deliberately NOT promised: a failure before step 2 leaves the round incomplete and the
observations unaccepted, and nothing here makes two simultaneous discovery invocations safe. The
concurrency profile is unchanged — one scheduled writer doing read-modify-write on its own objects.

**B. Verifiers that reject the conditions they name.**

- The package checker compares the candidate build against a recorded P06 **baseline** of
  infrastructure source, built-template resource definitions and the function set. A changed IAM or
  resource property, an added or removed function, an unavailable baseline and an unperformed
  comparison each fail. Only genuine code-only differences and explicitly normalized `CodeUri`
  build-path differences pass. It is a local package comparison and never describes itself as an
  executed AWS change set.
- The report now states, per identity, which postings it **consumed** (`consumed_job_ids`) and which
  of those reached no readable section (`below_fit_threshold_job_ids`). The inspector reconciles
  against that evidence instead of inferring a below-fit disposition from an employer-name match, and
  it binds the live view to the report's own run so a newer view is not read as a missing input.
- Rollback verification fails closed before restoring, rehearses restore-and-return and a corrupt
  archive in scratch directories, and never touches the working tree's `src/`.

## Execution Log

- 2026-09-26 — Orchestrator inspected P09 and reproduced RED policy-check. Staged P10 for policy
  behavior alignment and controlled release readiness; current policy already states the intended
  adjacent-role exclusions and preserved internal software work. No code edited, test suite rerun,
  deployment, applications or git actions. Deployment approval requested, not yet recorded. The
  native packet carries an optional release branch that requires fresh explicit authorization.

- 2026-09-26 — P09 executed locally. Ran the reviewer's pending-write probe unchanged BEFORE
  repairing and captured the loss, then moved the acceptance point instead of fixing its key. A
  feed's owed publication is now its own object (`discovery/owed/provider=<p>/owed_publication.json`)
  and the FIRST durable write of that feed's round, ahead of `raw/`, `normalized/`, `status/` and
  the SUCCESS sentinels — so nothing durable precedes acceptance and there is no state in which a
  posting is captured but unrecoverable. Recovery reads each enabled provider's own key (derived,
  not scanned: still no `ListBucket`, still no `DeleteObject`) and also the old aggregate object, so
  a debt the deployed code wrote is settled rather than orphaned. The unchanged probe's interrupted
  arm now matches its control in every field, and P07's unmodified live-write probe still passes.
  Enumerated the finite write sequence and refused each of its SIXTEEN boundaries in turn, including
  a write that lands and then times out before the caller hears: every boundary either accepts
  nothing — one row, the acceptance write itself, where the round is honestly incomplete and nothing
  at all was written — or accepts and recovers on both the same-run retry and the following round,
  with the feed returning nothing on every later attempt and no inflation of observation history.
  The owed-debt bound no longer discards: beyond five batches the oldest rounds are COMPACTED into
  one carry-forward batch with every posting preserved, and the only bound that removes anything is
  the live view's own retention horizon. P08's dropping test encoded a defect and was replaced,
  including the case that mattered most — the first healthy round after a backlog, which previously
  evicted the oldest job merely by enqueuing its own empty batch. Release side: the change-set gate
  now FAILS a changed built-template resource property, an added or removed function, an unavailable
  baseline and an unperformed comparison, and passes only genuine code-only and normalized-`CodeUri`
  differences; rollback verification fails closed before restoring and refuses to restore over the
  working tree; the report states `consumed_job_ids` and `below_fit_threshold_job_ids` so the
  inspector reconciles against consumer evidence instead of inferring below-fit status from an
  employer-name match. The P06 baseline build is reconstructed from the verified archive rather than
  a temporary directory, and the forward and rollback sequences are fail-fast scripts drilled 7/7
  against stubbed tools. 393 tests pass; `sam validate` and `sam build` exit 0; the change set
  against the reconstructed baseline is code-only across all six functions. **`policy-check` is
  RED** — two operator-owned documents outside this repository were edited on 2026-09-26 and the
  committed projection no longer matches them. P09 changed no policy source; refreshing the
  projection is a candidate-policy decision and was deliberately left to the operator. Nothing
  deployed, committed or staged; AWS was not contacted.
  Run: `project-factory/outputs/open-market-discovery/runs/20260925_publication_commit_boundary_and_verification_v1/`.
- 2026-09-25 — P08 independent review: 350 tests pass; unchanged P07 live-write probe repaired;
  policy projection matches; archive contains all 36 exact P06 source files (plus 36 AppleDouble
  metadata members); current template/config match recorded P06 hashes. A single failed FIRST
  pending-ledger write strands an already-normalized job: control reaches both reports, fault arm
  reaches neither. Local negative controls also show the package checker accepting changed IAM
  template semantics and the live inspector inventing a below-fit disposition for a missing job
  merely because another job shares its employer. The five-batch eviction policy is not adopted
  as durable recovery. Stage bounded P09; preserve P08 evidence and the genuine P06 baseline. No
  runtime repair, AWS call or git mutation by the orchestrator. P08/ORCHESTRATOR_REVIEW.md controls
  release status over the earlier executor unlock.

- 2026-09-25 — P08 executed locally. Reproduced the interrupted-publication loss with the reviewer's
  own probe copied byte-identical (diff-verified), then repaired it: `persist` now OWES each touched
  provider's observations to `discovery/_pending_publication.json` before any progress record can claim
  them published, and DRAINS that ledger one feed at a time, clearing a feed's debt only after its view
  commits. Replay is exactly idempotent (per-posting `observed_run_ids`) and monotonic in time, so an
  owed batch cannot duplicate a row, inflate observation history, roll back a newer observation or
  disturb another feed's committed work. The ledger is one object at one KNOWN key because the discovery
  role has no `ListBucket` or `DeleteObject` — a scanning or deleting design would have been an IAM
  change. Owed publication is visible in the coverage receipt, the report JSON, a `PARTIAL` discovery
  health axis and a named line in the rendered report. Re-ran the same unmodified probe: the interrupted
  arm now matches the uninterrupted control in every field, with the feed returning nothing on both
  later fetches. 350 tests pass (339 before, plus 11 fault-injection regressions); policy projection
  matches; SAM validates and builds. Release side, all three P07-review defects corrected by
  measurement rather than assertion: the change set is SIX code-only function artifacts, not two
  (P07's stop rule would have rejected a correct deploy); a hash-verified P06 baseline was found,
  archived in-repo and its restore/return drilled; and `scripts/inspect_discovery_integration.py`
  reconciles every stored discovery identity to a disposition and checks employer identity against the
  registry, discriminating across five controls including the zero-fit vs missing-consumer pair.
  Nothing deployed, committed or staged; AWS was not contacted.
  Run: `project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/`.
- 2026-09-25 — Independently reviewed P07: 339 tests and the original P06 probe pass; policy matches.
  Storage-failure control reproduces an already-normalized job missing from retry and next report,
  while the uninterrupted control retains it. Verified unchanged infrastructure by P06 content hashes,
  but every built function contains shared new code, contradicting the two-function deploy expectation.
  Rollback lacks an identified P06 artifact; thin-day checks need discovery-specific dispositions.
  Staged bounded P08. No runtime implementation, deployment or git mutation by the review.
- 2026-09-25 — P07 executed locally. Reproduced P06's missing edge with the reviewer's own probe
  (1 normalized job, 0 candidate rows), implemented the discovery live view + report ingestion, and
  re-ran the same unmodified probe to 1 candidate row. Repaired cursor-bound discovery identity and
  the old-report history boundary. 339 tests pass (316 before, plus 23 new acceptance cases); policy
  projection matches all sources; SAM validates and builds. Nothing deployed, committed or staged.
  Run: `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/`.
- 2026-09-25 — Processed P06 return: deployment/feed access accepted at their stated scope, product
  acceptance refused. Independent real-handler probe creates one normalized job and no candidate,
  confirming the absent integration. Qualified P05's fixture-created report evidence and corrected
  stale current-state pointers. Staged JPRS-L2-P07-discovery-to-report-integration-v01 under the
  operator's standing follow-up instruction. No runtime source, cloud, registry or git mutation.
- 2026-09-25 — Independent P05 review accepts the bounded local repair: 316 tests pass, formerly
  lost jobs now arrive with bounded requests, actual saved reports contain both targets on run two,
  and SAM selection passes with its own interpreter. Prepared approval-gated P06 deployment packet;
  no runtime/cloud/git mutations. August rollback still requires the existing job-data downgrade;
  only the new discovery-state field adds no August-specific downgrade work.

- 2026-09-25 — Independent P04 review: 296 tests pass; original location and page-two probes and
  the production-shaped report probe hold. New long-backlog reproductions lose a failed recent
  page and a new burst during saved continuation; a failed fetch permits four attempts under a
  budget of three. Local SAM template selection proves the forward deploy command ignores its
  temporary build. Added executable evidence and review; staged bounded P05, not executed. Runtime,
  AWS and git unchanged. Once repaired, request controlled deployment rather than another broad review.

- 2026-09-24 — Independent P03 return review: 252 tests pass, but location fixtures reject Belmont
  with a comma and admit an Illinois namesake and required Boston hybrid attendance. The actual
  report handler writes zero fresh where actual run timing yields two. New-page-two arrivals are
  skipped when the old backlog resumes. Preserved the completed transport/polarity/downgrade work;
  staged P04, with executable evidence in the P03 run. Runtime untouched by the reviewer. No AWS,
  deployment, git commit or push. Current status surfaces reconciled; historical evidence preserved.

- 2026-09-24, P02 return review: independently reran 209 passing tests; local probes kept the real
  fetcher and found blank outgoing Adzuna credentials, four mixed/optional screening misfires, and
  strict baseline-reader rejection of new records. A two-run cursor probe never refreshed the head
  on its second day. Recorded the fresh-first clarification separately from P02's original scope.
  See P02 `ORCHESTRATOR_REVIEW.md` and runnable evidence. Staged P03; no runtime changes or deployment.

- 2026-09-24, orchestrator return review: independently reran 168 passing tests and reproduced
  Adzuna credential/default-path defects, silent first-page truncation, false screening exclusions
  and an invalid rollback command. Findings are in the P01 run's `ORCHESTRATOR_REVIEW.md`.
  Staged `JPRS-L2-P02-discovery-release-repair-v01`; implementation preserved, no deployment.

- 2026-09-24: Operator approved the broad-discovery objective, explicitly including unknown
  small/non-software businesses. Inspection and read-only reproductions identified the coverage,
  warning, and title-filter defects above. This plan and the Claude implementation packet were
  staged. No implementation, paid signup, registry change, AWS deployment, or submission occurred.

- 2026-09-24: Packet `JPRS-L2-P01-open-market-discovery-v01` executed. **Implemented and tested
  locally; not deployed.** Outputs in
  `project-factory/outputs/open-market-discovery/runs/20260924_open_market_discovery_v1/`.

  **Central change:** employer moved from being a property of the SOURCE to a property of the JOB.
  The hardcoded 15-entry company-label table in the report is gone. Monitoring can only answer "what
  is open at this employer", so it structurally could not surface an unnamed one; discovery answers
  "who is hiring for this work" and can.

  **Sources chosen** (live-probed, read-only): Remotive, Remote OK, Jobicy and Himalayas work with
  no credentials and are integrated. Adzuna is implemented and fixture-tested but credential-gated —
  it is the only configured source with general industry breadth and a New Hampshire filter, so its
  absence is a real coverage limit, stated in the report itself. Arbeitnow was declined (a location
  census of its first 800 records was overwhelmingly London/Berlin/Paris). Brave was declined
  (signup requires a payment instrument, which this packet does not authorize).

  **Ashby identity concern closed with evidence:** 1,083 postings across Ramp, OpenAI, Ashby and
  Linear, every record carrying a stable top-level UUID; a Linear posting published 2021-04-27 is
  still listed under its original id. `ASHBY_ENABLED` is now true.

  **Four named defects repaired**, each with a regression test that fails against the old code:
  the `FullStack` spelling (0.00 vs 0.38 for the same role); the title-only hard zero that erased
  ordinary and novel titles; the frozen-department latch (now corroboration-bounded, releasing after
  two independent healthy snapshots while genuine truncation still freezes indefinitely); and the
  report's dead health branch plus the 20-row JSON overflow.

  **Measured result, same evaluation day:** employers reaching the system that are absent from the
  registry went from 0 — structurally, not by tuning — to **161**. 43 credible roles retained, 14
  new strong, 364 excluded with quoted reasons, 2 distinct-requisition pairs protected from a merge
  that would have deleted a live opening. Raw postings moved 521 to 747, which is explicitly not the
  success criterion. 168 tests pass; `sam validate --lint` and `sam build` clean. $0 spent, no AWS
  mutation, no commit.

  **Honestly unpassed:** Adzuna live discovery (needs a free key); source-growth admission (measured:
  none of the four feeds publish the employer's own board URL, so every discovered employer stays a
  visible `QUEUED_UNSUPPORTED` lead); and `fetch_raw` for three of four feeds, which this machine's
  egress proxy truncates — the connector degraded correctly to PARTIAL and a post-deploy check
  closes it.

  **Ten findings** surfaced during implementation; nine repaired in-run, one reported: `.samignore`
  is not honored by SAM's Python builder, so every Lambda ships the whole repository. Pre-existing,
  affects all five functions, left for a separate decision.

## Follow-ups

### P06 — controlled deployment and live source verification (2026-09-25, executed)

Run: `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/`.
Deployed under explicit operator approval, recorded before any cloud mutation. Gate:
`revise_implementation` for the product goal, with the deployment itself complete and safe to leave
running. Five claims are kept deliberately separate, because no one of them implies the rest.

**Deployed (established).** Stack `jprs-v1` in `us-east-1`, `UPDATE_COMPLETE`. The change set was read
before executing: 6 adds (discovery function, its role, log group, scheduler role, schedule, A8 alarm),
9 non-destructive modifies, **0 removals and 0 replacements**, every detail `RequiresRecreation: Never`.
Collect 07:00 and assemble 09:00 `America/New_York`, the 15-board registry, retained storage and every
existing parameter value were preserved — including the three email parameters, which have no template
default and were verified present in the change set rather than assumed. The new `jprs-discovery-daily`
schedule is the reviewed `cron(5 7 * * ? *)` in the same timezone. The only substantive permission
change is the report role gaining **read-only** `discovery/*`. Deployed into a quiet window: today's
collect and assemble had finished, zero executions running, both queues empty.

**Sources live-verified (established) — the gate every earlier round had to leave open.** One production
`jprs-discovery` invocation reached all four keyless feeds: attempted and succeeded on all four,
`inaccessible: 0`, **295 jobs across 218 employers**, real descending-cursor pagination (five himalayas
pages, not just a first page), every source inside its configured request cap, Adzuna named as
credential-gated rather than silently skipped. Full `raw/`, `normalized/`, `status/` evidence and per-run
SUCCESS sentinels retained. P04's non-deterministic truncation did not occur from Lambda; one run is not
a durability claim. The P05 resumability invariant held on real data **without injecting any failure**:
`head_pending` empty and the receipt's `inaccessible` empty, agreeing — no claim of clean recent coverage
while ranges remain owed. Report timing reads `basis: manifest.opened_at` in production, where the old
code wrote `timing: null`. Same-date digest suppression was honored (`already-sent`), so zero emails were
sent.

**Discovered jobs reaching the report (NOT established).** This is the finding that matters. The report's
35 candidate rows are all `greenhouse` / `ATS_BOARD`; **zero** come from the four discovery providers,
even though the 295 jobs are fetched, normalized and stored. It is an **absent integration, not an empty
valid result**:

1. `enumerate.build_manifest` records discovery ids in `expected_discovery_sources` and only monitored
   ATS boards in `expected_sources`.
2. `report.assemble_report_input` builds candidate rows by iterating `expected_sources` →
   `current_jobs_key(...)`. It never reads `expected_discovery_sources` (0 occurrences in the file).
3. `current/` is differ-owned, and the differ is invoked once per `/jprs/companies` entry by the assemble
   Map. Discovery providers are not in that registry, so `current/` holds only `provider=greenhouse/`.

So discovery currently contributes a truthful **coverage line** to the report — "4/4 discovery sources
returned results; 14/14 query families covered; 1 query item queued and resumable; not runnable without
a credential: adzuna" — and none of the jobs behind it. Left unrepaired deliberately: closing it means
deciding how feed jobs enter differ-owned state, what a disappearance event means for a feed that churns
daily, how to dedup against the monitored boards, and whether hundreds of unscreened postings a day
belong in candidate rows. That is a design decision, not the "trivial, clearly evidenced launch
correction" the packet allowed.

**Correction to the P05 record.** P05's `test_the_recovered_failed_page_reaches_the_persisted_report` and
its burst counterpart are **not** evidence that discovery reaches the report. Their harness wrote
`expected_sources` and `current/` for discovery sources itself — the wiring production does not create.
They remain valid evidence that the traversal repair delivers a recovered job into a report **given**
that wiring. A P07 regression must fail on the **production** manifest shape instead.

**Second finding.** The first post-deploy report read `timing.boundary: cold-start` rather than reading
the previous round. Cause, measured against `reports/dt=2026-09-24/daily_report.json`: the real
old-format reports carry `complete_candidate_list: []` with their rows in `top_matches`, and no `timing`
block, so the earlier-release id fallback found nothing usable. `cold-start` is an honest label rather
than a false freshness claim and it self-corrects from the next round, but P05 handoff §8 overstated that
fallback for this system's actual history.

Also, for `dt=2026-09-25` only, the stored report is the new-code version while the digest emailed at
09:01 was the old code's. The original object was preserved first under
`evidence/pre_discovery_report_2026-09-25/`. They agree from the next round.

**P06 follow-ups (current status amended after return review):**

1. **Execute the staged P07 discovery-to-report integration packet.** Authoring is covered by Brett's
   standing follow-up instruction; no repeat decision is needed. It must produce screened, ranked
   candidates, not a raw feed dump. Leave P06 deployed; shipping P07 requires fresh approval.
2. **Check the pending 2026-09-26 unattended round** against `evidence/p06_live_verification_summary.md`
   §6 — in particular whether `timing.boundary` reads `reported-ids` with `previous_run_id: 2026-09-25`.
   Not run, not waited for, and not to be recorded as passed before it happens.
3. The working tree is still **uncommitted** while now being the deployed code. Tree and stack must not
   diverge unnoticed.
4. Adzuna credentials, general-industry coverage, employer admission and the careers-URL resolver's live
   path remain separate, untouched gates.
5. Lambda packaging still ships the whole repository in every function. Pre-existing, unchanged.

### P05 — resumable discovery and release binding (2026-09-25, executed)

Run: `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/`.
Gate decision `unlock`. **316 tests pass.** The two blockers the P04 review reproduced are closed, each
reproduced first against the reviewer's own unmodified probe before any runtime edit
(`evidence/p05_before_repair_p04_probe.json`, then `p05_after_repair_p04_probe.json`).

Both findings were one confusion in the traversal state model, which is why they were repaired together
rather than as two branch patches: **an observed timestamp was being read as proof that the intervening
range had been traversed.** The model recorded what it had seen and where it had stopped, and had no
place to record what it still owed.

- **Recent ranges are no longer lost.** `DiscoveryState.head_pending` is an ordered list of recent
  cursor ranges known to be untraversed — the traversal debt — and it is now the only thing that may say
  a range was covered. A recent page that raises, returns a truncated body, or is cut off by the budget
  stays owed and is retried. A newly published continuation no longer overwrites a saved one, because a
  single slot no longer has to hold both. `head_frontier_at` remains what it honestly is: the newest
  posting observed on the contiguous chain from page one.
- **The already-observed stop is scoped to the walk that earns it.** Only the contiguous chain from page
  one may stop at the frontier, because it is the one walk whose coverage runs unbroken from the newest
  posting downward. A chain resumed from an owed range has no such guarantee, and stopping it there
  would discard a continuation nothing else records — the same silent loss in a new place. Resumed
  chains still end at the recent-time horizon, the backfill's position, the feed end, or a repeated
  cursor, so nothing became a recrawl and persisted state stays bounded (24 owed ranges per source, with
  any drop reported as partial coverage).
- **Failed attempts are charged.** Every outbound attempt spends its request before it is made, closing
  the four-requests-under-a-budget-of-three overrun. The per-source cap is asserted at budgets 1, 2, 3, 5
  and 8, with failures in the mix, across repeated runs.
- **Verified the way the defect actually occurs.** Every run boundary serializes and reloads
  `DiscoveryState`, because production stores it in S3 between invocations. Every multi-run test keeps a
  24-page historical backlog open, because the P04 suite's three-page backlog let the feed reach its end,
  restart at page one and re-collect the "lost" job by accident — which is how a broken walk looked
  correct. Both scenarios are driven through to a **persisted candidate report** written by the real
  report handler: the formerly lost posting arrives on run two in both, the historical backfill advances
  monotonically and never rewinds, and owed ranges drain to empty.
- **Deployment is bound to the build it verified.** The P04 command built into a temporary directory and
  deployed without naming the template. SAM never consults `--build-dir`: from the repository root that
  resolves to a nonexistent `template.yml`, and from `infra/` to a stale 2026-08-01 build containing **no
  discovery function at all**. Behind that sat a second trap — SAM sets its samconfig directory to the
  given template's directory, so a relative `--config-file` resolves inside the build directory. Forward
  and rollback commands now name the template and an absolute config path, verified through SAM's own
  resolution functions with no AWS call, and corrected in `infra/DEPLOY.md` and `START_HERE.md` as well
  as the new handoff. A test parses the handoff's own commands so the binding cannot rot back out of the
  prose.

Regression strength was measured, not asserted: the repository was copied to a scratch directory, the
P05 source changes reverted there with every revert asserted, and the new tests run against that
reconstruction. **12 of the 20 fail on the P04 source**, including both review scenarios and both
persisted-report checks. The other 8 guard behaviour P04 already had right.

The quiesce → data downgrade → source rollback → resume ordering and the non-destructive `git worktree`
method are preserved unchanged. One new data note: a rollback of the discovery source to P04 that keeps
its state must delete the `head_pending` key, because P04's model forbids extra fields; `head_cursors`
is written as a mirror of the newest owed range so a stripped document still resumes the most important
one. A rollback to the `e549a73` baseline is unaffected — that code never reads `discovery/`.

Nothing was deployed, committed, staged or pushed; no AWS call, credential, network request or email.
`project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/DEPLOYMENT_HANDOFF.md`
is the handoff of record and the executable release instruction.

**Open items that need Brett, after P05:**

1. **The deployment decision.** The recommendation is deploy, following the P05 handoff's §4 verbatim
   and then its §5 acceptance checks — §5.6 is new and is where this repair would visibly fail in
   production. Everything local is verified; nothing is deployed.
2. One interpretation to confirm, carried forward unchanged: a New Hampshire onsite role arrives as
   "confirm the worksite" rather than a yes or a no, because the system will not certify a drive time it
   cannot measure.
3. Adzuna developer credentials in SSM, if and when general-industry breadth is wanted. A credential
   enables the first attempt; it does not close the coverage gate.
4. Whether to enable bounded careers-URL resolution so a discovered employer can become a monitored
   source. Every redirect hop is re-validated against the SSRF address rules.
5. Whether to fix Lambda packaging, which still ships the whole repository in every function.
   Pre-existing, unchanged by P05.

What P05 does **not** establish: production HTTP transport remains unverified for all four keyless
feeds, and the repair's behaviour under a real interrupted production day is inferred from
persisted-state reproductions rather than observed. The first scheduled Lambda run is that evidence.

### P04 — location and freshness boundaries (2026-09-24, executed)

Review qualification, September 25: the following is the executor's repair account, not current
release clearance. `ORCHESTRATOR_REVIEW.md` in the P04 run confirms location/timing and reopens
recent traversal under failure/new arrivals. P05 also corrects build-to-deploy selection.

P01–P04 are executed. Run: `project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/`. The three blockers the P03 review left open are repaired at the
boundaries where they actually failed, each reproduced first against the reviewer's own unmodified
probe (`evidence/p04_before_repair_probe.json`, then `p04_after_repair_probe.json`):

- **R1, location.** `src/candidate/location.py` is new and replaces three regexes of hand-written town
  names. It resolves place and state (so punctuation and a shared town name stop deciding locality),
  mandatory attendance requirements with polarity (so a remote label cannot override required Boston
  attendance, while "no in-office requirement" and a reporting line are not read as one), and
  residency limits that exclude New Hampshire. The single hard distance rule is the state boundary,
  which is verifiable: Laconia is in central New Hampshire, so no out-of-state worksite is a
  thirty-minute drive from it. Every in-state distance question is left deliberately unresolved and
  surfaced for worksite confirmation — the policy states a drive time, this system cannot measure one,
  and certifying towns was the original defect. Plymouth routes to operator review. Screening ruleset
  1.3.0 → 1.4.0.
- **R2, report timing.** `resolve_run_timing` reads this round's start from the RUN_OPEN manifest's
  `opened_at` and the previous boundary from the most recent earlier persisted report. "New since the
  last round" is decided by which postings that report showed, not by comparing timestamps across
  stages that do not share a clock — so a weekend gap, a failed round, a retry and a replay all give
  the same answer. Ages are measured from the run start instead of the end of the UTC calendar day.
  The local CLI path had the same unwired boundary and was fixed with it (`--previous-report`).
- **R3, recent-page continuation.** The feed-head walk continues while pages still hold recent
  arrivals, hands over when it meets the historical backfill, and saves any unreachable remainder in
  `head_cursors` to resume next run. At least one page is always reserved for the catch-up, and the
  per-source budget is asserted at 1, 2, 3 and 5.

Two further defects surfaced during the repair, neither in the review: the local CLI report path
shared R2's unwired boundary, and cold-start detection inferred a first observation from timestamp
cardinality, so a warm source holding one posting suppressed its genuinely new arrival — it now uses
the source's recorded success history.

296 tests pass; SAM validates and builds; the policy projection matches all five sources; the
rehearsal replays real captured provider payloads across two consecutive rounds. Nothing was deployed,
committed, staged or pushed. `project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/DEPLOYMENT_HANDOFF.md` is the handoff of record and corrects P03's
contradiction about rollback data compatibility.

Open items that need Brett:

1. Superseded by the P05 section above: P05 is executed and its handoff is the release instruction.
   Retained because the rollback detail still applies. Disabling discovery alone does not restore the prior
   screening/report code, and a source-only revert is **not** sufficient: the baseline rejects 18
   added fields, so the data downgrade in that handoff's §6.2 is required, in the order given there.
2. One interpretation to confirm: a New Hampshire onsite role now arrives as "confirm the worksite"
   rather than as a yes or a no, because the system will not certify a drive time it cannot measure.
3. Adzuna developer credentials in SSM as `/jprs/secrets/ADZUNA_APP_ID` and
   `/jprs/secrets/ADZUNA_APP_KEY`, after the locally testable runtime path is repaired and terms
   checked. Credential provisioning and live coverage remain separate gates.
4. Whether to enable bounded careers-URL resolution so a discovered employer can become a monitored
   source. Every redirect hop is re-validated against the SSRF address rules.
5. Whether to fix Lambda packaging, which currently ships the whole repository in every function.

Keep the existing AWS cost target below $5/month unless Brett approves a change. Report search
API costs separately and combined. No paid subscription, unapproved model spend, or unattended
cloud changes are authorized by this plan. No search system may promise literal total coverage.
