# P06 live verification summary — what the real production run established

All facts below come from the deployed `jprs-v1` stack in `us-east-1` on 2026-09-25, from production
Lambda invocations and the objects they actually wrote. No local surrogate (no `curl`, no mocked
transport) is used for any live-access claim. Private identifiers are not recorded here.

The five claims the packet requires be kept separate:

| # | Claim | Status |
|---|---|---|
| 1 | Local repair accepted (P05) | **established** before this run |
| 2 | Stack deployed | **established** — §1 |
| 3 | Individual sources live-verified | **established for all four keyless feeds** — §2 |
| 4 | Discovered jobs reach the user-facing report | **NOT established — integration gap, §4** |
| 5 | Later scheduled-round freshness verified | **PENDING — §6, not yet run** |

---

## 1. Stack deployment (claim 2)

- Change set inspected before execution: **6 adds, 9 modifies, 0 removals, 0 replacements.**
  - Adds, exactly the declared discovery resources: `DiscoveryFunction`, `DiscoveryFunctionRole`,
    `DiscoveryLogGroup`, `DiscoverySchedulerRole`, `DiscoverySchedule`, `A8DiscoveryErrors`.
  - Modifies: the five Lambdas' code, `ReportFunctionRole` (the one substantive permission change),
    and four resources whose only change is re-resolution of references to those functions
    (`CollectSchedule`/`CollectSchedulerRole` → `Target`/`Policies` only, `DailyAssembleStateMachine`
    → `DefinitionSubstitutions`, `SfnRole` → `Policies`). Every one `RequiresRecreation: Never`.
  - **No schedule expression or timezone was in any change scope.**
- Parameters carried forward by CloudFormation, verified in the change set before execution:
  `CollectCron cron(0 7 * * ? *)`, `AssembleCron cron(0 9 * * ? *)`, `TimeZone America/New_York`,
  `BucketName` unchanged, and the three email parameters present and unchanged (they have no template
  default, so a blank would have broken alerting and digest delivery). New parameters took their
  reviewed defaults: `DiscoveryCron cron(5 7 * * ? *)`, `DiscoveryProviders` empty (all keyless),
  `SecretsSsmPrefix /jprs/secrets`, `ResolveCareersUrls false`, `EnableNarrator false`.
- `ReportFunctionRole` change is **read-only**: `discovery/*` added to its existing `s3:GetObject`
  resource list and to the `ListBucket` prefix condition. Discovery's own writes are scoped to
  `discovery/*`, `raw/*`, `normalized/*`, `status/*` — it cannot write `current/*` or `events/*`.
- Executed 13:07:45Z → `UPDATE_COMPLETE`. Post-deploy: `jprs-discovery` `State: Active`,
  `LastUpdateStatus: Successful`, python3.13/arm64, 512 MB, 120 s timeout, resolver off.
- Schedules after deploy: collect `cron(0 7 * * ? *)` and assemble `cron(0 9 * * ? *)` **unchanged**,
  both `America/New_York`; new `jprs-discovery-daily` `cron(5 7 * * ? *)` `America/New_York`, ENABLED.
- Alarm `jprs-A8-discovery-errors` present, state `OK`. Narrator absent (condition off).
- Quiescence: deployment began after today's collect (07:00) and assemble (09:00:41→09:01:03 EDT,
  SUCCEEDED) had finished. Zero running executions, both queues empty (0 visible, 0 in flight).

A successful stack update is deployment evidence only. It says nothing about claims 3–5.

## 2. Live source verification (claim 3) — the gate P04/P05 could not close

One production invocation of `jprs-discovery` with the scheduler's own payload
`{"trigger":"discovery"}`; `run_id` defaulted to `2026-09-25`, matching today's real manifest.

- `StatusCode 200`, no `FunctionError`, 15.66 s, 133 MB peak of 512 MB.
- Response: `discovery_attempted` and `discovery_succeeded` both
  `[himalayas, jobicy, remoteok, remotive]` — **4/4 keyless feeds returned valid, parseable
  responses over real production HTTP.** `jobs_discovered: 295`, `employers_observed: 218`,
  `credential_gated: [adzuna]`, `snapshots_written: 8`.
- Coverage receipt (`discovery/run=2026-09-25/coverage.json`): **`inaccessible: 0`** — no truncated
  body, no `PARTIAL` snapshot, no failure this run. The non-deterministic truncation P04 measured from
  the operator's machine did **not** occur from Lambda on this run. One run is not a durability claim.
- Budgets, each within its configured cap and none exceeded: `himalayas 5/5`, `jobicy 1/1`,
  `remoteok 1/1`, `remotive 1/1`; `failures: 0`, `rate_limited: false` for all four.
- Retained evidence, all written at 09:12 EDT: 8 gzipped `raw/` snapshots, 8 `normalized/schema_v=1/`
  job files, 8 `status/.../_source_status.json`, and per-run `SUCCESS` sentinels. The five himalayas
  entries are `board=all` plus four real descending-timestamp cursor pages, so live pagination is
  exercised, not just a first page.
- Adzuna is named as credential-gated in the receipt rather than silently skipped, as designed.

### The P05 resumability invariant, observed rather than injected

No failure was injected into production to manufacture this.

- Persisted `discovery/_discovery_state.json`: `head_pending: {"himalayas": []}` — no owed recent
  ranges — and the receipt's `inaccessible` is likewise empty. **The two agree**: there is no claim of
  clean recent coverage while ranges remain owed.
- The historical backfill saved its position (`source_cursors.himalayas`, a descending base64
  timestamp cursor) and the receipt says so honestly: `backlog_items: 1`,
  `"himalayas feed has more pages; position saved and resumable"`.
- `head_frontier_at` is empty, which is correct for a first run: with no saved backfill position the
  walk from page one *is* the catch-up, so no recent-phase frontier is recorded.

## 3. Report timing and the monitored radar (partial, with one finding)

One bounded `jprs-report` invocation for `{"run_id":"2026-09-25","dt":"2026-09-25"}`.

- `StatusCode 200`, no error. `run_health: VERIFIED-QUIET`, 15/15 expected sources succeeded, 523
  events, 35 matches, 12 new-strong, 16 needing a check.
- **`digest_delivery: "already-sent"`** — existing same-date suppression honored. No second email was
  sent, no recipient changed, no forced resend.
- Timing comes from the manifest, which is the P04 repair working in production:
  `basis: "manifest.opened_at"`, `run_started_at: 2026-09-25T11:00:52.461982+00:00`, matching the real
  `RUN_OPEN.json`. The old code had written `timing: null`.
- The report renders the discovery coverage receipt verbatim as its own health axis:
  *"Discovery coverage (PARTIAL) — 4/4 discovery sources returned results; 14/14 query families
  covered; hit a result ceiling (more may exist): …; 1 query items queued and resumable; not runnable
  without a credential: adzuna."* It also lists the four sources queried.
- The fixed-board monitor is intact: 15/15 collected, `current_job_count: 511`, candidate rows present,
  ordinary report and digest behavior unchanged.

### Finding A — the freshness boundary reads `cold-start`, and the "earlier release" fallback does not work on this system's real history

Measured, not inferred:

- Today's report: `boundary: "cold-start"`, `previous_run_id: null`, `previously_reported_count: 0`,
  `cold_start_run: true` — even though reports exist for `dt=2026-09-21` … `2026-09-24`.
- Cause: the previous-round reader harvests ids from `complete_candidate_list` only. The real
  old-format reports have **`complete_candidate_list: []` and their 20 rows in `top_matches`**, and no
  `timing` block at all. Verified directly against `reports/dt=2026-09-24/daily_report.json`:
  0 usable ids in `complete_candidate_list`, 20 ids present in `top_matches`.
- So P05 handoff §8's claim that "a report written by an earlier release still supplies its candidate
  id list" is **not true for this system's actual historical artifacts**. The regression
  `test_a_previous_report_from_an_earlier_release_still_supplies_its_identity_list` passes against a
  fixture whose `complete_candidate_list` is populated, which the real old reports' is not.
- Consequence is bounded and self-correcting: `cold-start` is an honest label rather than a false
  freshness claim, and today's new-format report carries 35 `complete_candidate_list` rows, so
  tomorrow's scheduled report should read `reported-ids`. That is exactly the pending check in §6.
- Not repaired here: out of scope for this packet.

### Note on today's report object versus the email already sent

This morning's 09:01 digest was generated and emailed by the **old** code. The re-run replaced the
stored `reports/dt=2026-09-25/daily_report.{json,md}` with the new-code version, so for today only,
the stored report is richer than the email the operator received. The pre-existing object was
preserved first at `evidence/pre_discovery_report_2026-09-25/` (full markdown plus a summary of the
JSON with the large row arrays omitted). From tomorrow the two agree again.

## 4. Finding B — discovered jobs do not reach the candidate report (claim 4 NOT established)

**This is an absent integration, not an empty valid result.** The distinction matters and the evidence
separates them: the data arrived and is stored; there is simply no path from it to the report.

Evidence:

- The report's `complete_candidate_list` has **35 rows, all `source_id` prefix `greenhouse` and all
  `source_kind: ATS_BOARD`. Zero rows from `himalayas`, `jobicy`, `remoteok` or `remotive`.**
- Yet 295 jobs from 218 employers were fetched and are stored in
  `normalized/schema_v=1/provider={himalayas,jobicy,remoteok,remotive}/…`. The data is not missing.
- `s3://…/current/` contains only `provider=greenhouse/`. No discovery provider has any `current/`
  state at all.

Mechanism, read in the deployed code:

1. `enumerate.build_manifest` puts discovery source ids in **`expected_discovery_sources`**, and puts
   only monitored ATS boards in `expected_sources`.
2. `report.assemble_report_input` loads candidate jobs by iterating **`expected_sources`** and reading
   `current_jobs_key(provider, board)`. It never reads `expected_discovery_sources` — that field
   appears **0 times** in `src/report/handler.py`.
3. `current/` is differ-owned, and the differ is invoked once per entry of the `/jprs/companies` SSM
   registry by the assemble state machine's `DiffAllCompanies` Map. Discovery providers are not in
   that registry and are not ATS boards, so the differ is never invoked for them.

So discovery's contribution to the operator-facing report is currently the **coverage receipt only**:
the report truthfully says how wide the search reached, while none of the 295 postings it found can
appear as a candidate row.

### This also identifies a flaw in P05's own persisted-report regressions

`test_the_recovered_failed_page_reaches_the_persisted_report` and its burst counterpart pass because
the **test harness itself** wrote `expected_sources` from the discovery jobs and wrote
`current/provider=…` for them. Production's `enumerate` does neither. Those tests therefore supplied
the very wiring production lacks — the same class of mistake this repository's own test-writing notes
call out ("A test that supplies the very field production fails to supply is the same mistake in a new
place"). They are valid evidence that the *traversal repair* delivers recovered jobs into the report
**given** that wiring, and they are not evidence that the wiring exists.

Not repaired here: choosing how discovery jobs enter `current/` is a design decision with real
consequences (differ disappearance semantics for a high-churn feed, dedup against monitored boards,
whether 295 unscreened postings per day should flow into differ-owned state), well outside "a trivial,
clearly evidenced launch correction."

## 5. What was deliberately not done

No Adzuna signup or credential, no SSM or registry edit, no employer admitted (`admitted_this_pass: 0`;
proposed rows written to `discovery/run=2026-09-25/proposed_registry.json` and applied by nobody), no
resolver enabled, no paid model call, no application or employer contact, no forced email, no schedule
or cadence invented, no commit, branch, push, reset or staging. The uncommitted tree is intact. No
failure was injected into production. Providers were invoked once each, not retried for a better sample.

## 6. PENDING — the scheduled-round check (claim 5)

**Not run, not verified, and deliberately not waited for.** The first unattended round on the new code
fires tomorrow, 2026-09-26: collect 07:00, discovery 07:05, assemble 09:00 America/New_York.

What to check, and where the evidence will be:

| Check | Exact path / field |
|---|---|
| Unattended discovery ran and the transport held again | `s3://jprs-prod-bw-20260731/discovery/run=2026-09-26/coverage.json` → `discovery_succeeded` vs `discovery_attempted`, and `inaccessible` |
| Owed ranges agree with reported coverage | `s3://…/discovery/_discovery_state.json` → `head_pending` vs that receipt's `inaccessible` |
| Recent-phase frontier now recorded (a backfill position exists from today) | same object → `head_frontier_at` non-empty |
| Cross-round freshness, the real Finding A retest | `s3://…/reports/dt=2026-09-26/daily_report.json` → `timing.boundary` should read `reported-ids` with `previous_run_id: 2026-09-25`, **not** `cold-start` |
| A8 stayed quiet | alarm `jprs-A8-discovery-errors` state |

Until that round actually runs, cross-round freshness is unverified. Nothing in this run should be read
as having checked it.
