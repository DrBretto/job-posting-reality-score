# Run Packet: JPRS-L2-P04-location-and-freshness-boundaries-v01

## Header

- project_slug: jprs
- phase_key: location-and-freshness-boundaries
- execution_profile: FULL_BUILD
- handoff_target: Claude Code
- run_id: 20260924_location_and_freshness_boundaries_v1
- run_root: project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/
- status: staged; not executed

## Objective and context

Make the existing open-market radar reliably surface strong, NH-eligible opportunities promptly for
Brett's morning application round. Preserve broad unknown-employer discovery and older strong leads.
This is three bounded release repairs, not a new committee, rebuild, ranking redesign or feature set.

P01–P03 executed locally; the independent P03 review reran 252 passing tests but reproduced failures
outside them. A local Belmont job is excluded while an Illinois namesake and mandatory Boston hybrid
attendance are allowed; production report timing is unwired; newest-page continuation is discarded
when an old backlog exists. The earlier Adzuna transport and screening-polarity repairs now pass the
reviewer's probes. Preserve them and the rehearsed rollback downgrade.

## Read first

1. Repository `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, factory bootstrap, shared contracts and
   `project-factory/claude_handoff/RUN_OUTPUT_CONTRACT.md`.
2. `docs/plans/2026-09-24-open-market-job-discovery.md`, `docs/PLAN.md`, current factory status.
3. P03 run `project-factory/outputs/open-market-discovery/runs/20260924_runtime_boundary_and_fresh_first_v1/`:
   `ORCHESTRATOR_REVIEW.md`, `evidence/p03_independent_review_probes.py`, its saved results,
   `VALIDATION.md`, `DEPLOYMENT_HANDOFF.md`, `run_manifest.json` and actual rehearsal artifacts.
4. The five central candidate/workflow sources named in the controlling plan, read-only. In
   particular read the current Location and Compensation policy. Do not read/copy the private
   demographic answer bank into JPRS; it is not a discovery or ranking input.
5. Relevant production paths and callers in `src/candidate/screening.py`, `src/common/normalize.py`,
   `src/discovery/`, `src/report/handler.py`, `src/differ/handler.py`, `src/common/rollback.py`,
   `src/enumerate/handler.py`, existing tests and deployment docs.

## Authority and scope

Use the file-based factory in `/Users/drbretto/Desktop/Projects/job-posting-reality-score`, not the
Infotropy MCP spine. Preserve the entire uncommitted implementation. Allowed: targeted local
code/config/tests/docs, mocked services, local builds and bounded public reads if actually needed.
Not allowed: deployment, AWS/SSM/registry changes, signup, paid calls, real-secret discovery,
schedule changes, email/application submission, candidate-source edits, AGENTS/shared-contract edits,
staging/reset/checkout/branch/commit/push. No application materials in Inbox.

Create run_root before writing outputs; resume an existing checkpoint rather than duplicating a run.

## Repairs and acceptance

### 1. Implement the meaning of the location policy

Reproduce every R1 pair before changing code. Normalize place/state and attendance requirements;
neither punctuation nor a shared town name makes a role local. A remote label cannot override
mandatory Boston attendance or an explicit state-residency restriction excluding NH. Preserve
genuinely remote Boston/Portsmouth employers. Plymouth remains an operator-review case.

The user specified a drive duration, not the executor's town list. Do not certify all worksites in
a broad town/region as within 30 minutes. Keep plausible but unverified local leads visible for
worksite/commute confirmation; do not replace uncertainty with automatic rejection. No new mapping
service is required. Include multiple locations, missing state, abbreviations, punctuation,
conflicting remote/hybrid fields, remote roles with NH excluded, and paired genuinely NH-eligible
remote roles. Preserve all existing non-location exclusions and the absence of a pay cutoff.

### 2. Connect freshness to the real report execution

Reproduce R2 through actual mocked S3 -> assembly -> report handler -> saved JSON/Markdown, without
substituting a timing-populated ReportInput. Inspect how actual manifests/checkpoints are created
and choose a durable, truthful current/previous observation boundary. Do not derive morning age from
the end of its calendar day or invent a previous successful run after failures.

Verify a 20-hour-old posting, an undated new-to-us arrival, a genuinely older lead, missed weekdays
and weekends, first source observation, a warm one-job source, duplicate observations, retries and
failed/partial observations. Newly discovered is not newly published: preserve the distinction and
label older catch-up accordingly. Verify persisted report output and the digest body boundary with
email mocked. Current timing must come through production wiring, not only renderer tests.

### 3. Preserve recent arrivals beyond the first feed page

Reproduce R3's new-page-two gap with the old backlog still present. Preserve bounded recent-arrival
continuation as well as historical catch-up, or an equivalent design justified against the provider's
actual cursor contract. A burst or weekend can put new jobs on several pages; do not discard the
head cursor after one request. Within-budget recent work must reach the current report; overflow
must remain visible and resumable with fair treatment of old catch-up.

Test multiple fresh pages inserted above an existing historical cursor, follow-up runs, exhausted
budgets, failed pages and retry, no new arrivals, reaching a previously observed frontier, repeated
cursor protection and first-seen/dedup preservation. Prove that jobs reach the persisted report,
not only that a URL was requested. No unbounded crawling or silently increased source limits.

### 4. Reconcile and verify once the boundaries hold

Run the independent probe before/after, focused regressions and the full suite; run policy-check,
SAM validation/build and a bounded end-to-end rehearsal. Do not modify the old review evidence to
make it pass. Tests must intercept the external boundary, not replace the broken internal function.
Keep the repaired HTTP credential path and downgrade/restart regressions passing.

Correct the next live deployment handoff's contradictory old-reader statement, verify referenced
evidence paths actually exist, and make rollback order/writer-quiescence explicit so new writers
cannot immediately recreate incompatible records during recovery. Do not perform any recovery.

Synchronize existing live START_HERE/bootstrap/plan/status/registry/phase/timeline surfaces with
execution versus acceptance versus deployment. Preserve historical returns, correcting through
review qualification rather than rewriting their evidence. Counts must identify their population:
216 was employers, not postings; 4 fresh + 12 older was not all 44 retained roles.

## Outputs and stop condition

Produce the normal run manifest, checkpoint, gate decision, operator return, validation, corrected
deployment handoff, executable regression evidence and persisted rehearsal report. Record what each
new check would have failed on before repair. If a requirement remains unpassed, say so explicitly.

Stop at locally verified repairs and a coherent release handoff. No deployment, real credentials,
cloud mutation or commit. The orchestrator reviews the actual repaired boundaries before asking
Brett for deployment approval. Authenticated Adzuna and real production transports remain separate
activation checks; do not call mocked success live success. Do not add another broad review cycle
or new features simply because the project has had multiple repairs.
