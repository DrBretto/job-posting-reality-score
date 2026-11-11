# Orchestrator review — September 24

Action class: run-return / evidence. Status: **revise_release_readiness**.
This review qualifies the executor's earlier deployment recommendation; it does not erase the
run or its useful implementation. No product code, AWS resources, registry, or git history changed
during this review. The original return remains the historical executor report.

## What holds

- Independently reran `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider`:
  **168 passed in 1.05s**.
- Inspected the stored monitored-only, discovery-only and combined reports: 33 / 10 / 43 retained
  roles and 10 / 4 / 14 new-strong classifications. The discovery-only report contains ten distinct
  employers. These are machine-ranked leads, not ten researched employers or fourteen approved
  applications. The comparison isolates source footprint under the new code, not all effects of
  old versus new scoring.
- Employer-independent arrival is implemented; the old fixed-employer boundary is genuinely gone.
- FullStack normalization, complete readable candidate output, and explicit uncertainty are useful
  improvements. SAM validation/build are executor-reported here; this review reran pytest, not SAM.

## Blocking findings reproduced locally

### R1 — Adzuna setup instructions do not match the runtime

`src/discovery/handler.py:124` defaults to `keyless_discovery_providers()`. Supplying credentials
does not add Adzuna and does not even name it in the missing-credential list on that default path.
Separately, the Lambda resolves SSM values into a dictionary passed as `env`, but
`src/discovery/connectors.py:380` builds the URL from `os.environ` instead. Explicitly selecting
Adzuna therefore still sends blank credentials when the credentials exist only in SSM.

Read-only injected-fetch reproduction, with `os.environ` cleared and fake credentials passed as
`env`: default attempted only Himalayas, Jobicy, Remote OK and Remotive; explicit Adzuna made 20
requests with empty credential query parameters. No real secret or network request was used.
All generated Adzuna requests also lacked `where`; the promised NH-targeted search is not wired.

Acceptance: exercise the actual handler configuration with mocked SSM/S3 and captured HTTP
requests; absent credentials produce a visible gate, present credentials reach requests securely,
and US-remote plus appropriate location-scoped work are both represented. Do not solve this by
limiting all searches to NH. Secrets must not enter receipts, raw request metadata or logs.

### R2 — A paginated feed is treated as a complete bulk feed

`HimalayasConnector` inherits `BulkFeedConnector` and requests `?limit=100`. The bulk branch in
`run_discovery` makes one request, ignores continuation metadata and records no backlog. A
synthetic response announcing further results still produces one request and an empty backlog.

The provider's current documentation says the browse endpoint returns at most 20 jobs and uses
`nextCursor`; it also supplies a keyword/country search endpoint. Source checked September 24:
https://himalayas.app/api

Acceptance: a relevant job beyond page one must reach the candidate report. Bounded work may
defer remaining pages but must persist and resume their cursor, label coverage partial, and avoid
repeating page one forever. Include timeout/rate-limit and retry/resume tests for query sources,
not only the happy path. An operational request budget is not complete-market coverage.

### R3 — Screening still removes look-alikes rather than actual exclusions

Independent synthetic tests of `screen_job` returned EXCLUDED for all three:

| Input | Incorrect reason |
|---|---|
| `No security clearance is required.` | clearance-government |
| `We do not require a recorded video.` | recorded-video |
| `Build tools for the sales team to research prospects.` | sales-ownership |

The stored combined report also excludes Future's Full-Stack Growth Engineer for a phrase about
output reaching `members or prospects`. This demonstrates the vocabulary misfire on an actual
captured posting, not that this role is otherwise a confirmed fit.

Relevant code: `_SALES_OWNERSHIP_RE`, `screen_job`, the clearance and interview branches in
`src/candidate/screening.py`. Positive responsibilities and negated requirements need different
outcomes. Unclear scope should be review-needed, not confidently excluded. Check normalized and
HTML-encoded source text as well as clean prose. Preserve genuine sales/clearance/video exclusions.

Acceptance: paired tests covering required versus explicitly not required, product/tooling use
versus the candidate's own duties, and mixed clauses. Re-evaluate captured engineering-role
exclusions and report changed dispositions, without converting them straight into approved apps.
Keep quoted reasons and uncertain candidates available for the downstream research executor.

### R4 — Deployment/rollback readiness was passed too early

The supplied fast rollback command is rejected by the local AWS CLI even with
`--generate-cli-skeleton output` (validation only, no AWS operation): missing
`--flexible-time-window`, `--schedule-expression`, and `--target`.
Official contract: https://docs.aws.amazon.com/cli/latest/reference/scheduler/update-schedule.html

The full rollback also checks old files over an uncommitted implementation. Replace it with a
recoverable method that preserves the working tree and specifies the exact built revision.
Disabling discovery is only a partial disable; it does not revert modified screening/report code.

The proposed `$0 additional in practice` is not an account-verified cost result; no free-tier
eligibility was checked. Separate the zero-cost local run from a sourced deployment estimate,
including the new alarm and storage. Preserve the existing under-$5 target without inventing an
account entitlement. No need for a billing project or unnecessary packaging rewrite.

## Remaining limitations, not newly discovered blockers

- General-industry coverage through Adzuna still needs an operator-provisioned credential and a
  real successful search. A credential alone cannot close R1.
- Careers resolution remains off. Even enabled, the current code emits proposed registry rows;
  it does not itself establish an automatic discovery-to-monitoring loop. Keep that distinction
  explicit and stage any registry mutation for approval.
- Three feeds were parsed from curl-fetched bytes, not verified through the production transport.
  A controlled live runtime check remains necessary after separate approval.
- `policy-check` currently detects a newer central workflow edit. Refresh the projection after
  reading its meaning; do not infer a new exclusion from new research instructions. Company/vibe
  research belongs to Career Factory execution with orchestrator review, not new JRPS hard gates.
- The one-time observation of a UUID with a 2021 publication date does not demonstrate that its
  identifier has remained unchanged since 2021. Likewise, repeat successful downloads do not prove
  every possible partial-feed failure is excluded. Bound those historical/robustness claims.

## Next

One focused repair, not a new architecture committee:
`project-factory/claude_handoff/packets/jprs/JPRS-L2-P02-discovery-release-repair-v01.md`.
Re-review its code, regression tests and repaired rehearsal before requesting deployment.
