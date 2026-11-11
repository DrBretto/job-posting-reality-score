# P07 VALIDATION — discovery-to-report integration

Run: `20260925_discovery_to_report_integration_v1`
Packet: `JPRS-L2-P07-discovery-to-report-integration-v01`
Date: 2026-09-25. Status: `stage_complete` — local implementation and verification only.

**Scope label that governs every claim below:** this is a LOCAL repair, verified against mocked
external services. Nothing was deployed. The still-running production stack is the P06 build and
does not contain any of this. No claim here is a claim about live behavior.

---

## 1. The defect, reproduced before it was touched

`evidence/p07_before_repair_p06_probe.json` — the P06 reviewer's own probe, run unmodified against
the working tree before any P07 edit:

```
"discovered": 1,
"normalized_job_ids": ["himalayas:all#applied-engineer"],
"candidate_rows": 0,
"discovery_candidate_ids": []
```

`evidence/p07_after_repair_p06_probe.json` — the same script, same external inputs, after the repair:

```
"discovered": 1,
"normalized_job_ids": ["himalayas:all#applied-engineer"],
"candidate_rows": 1,
"discovery_candidate_ids": ["himalayas:all#applied-engineer"]
```

`evidence` — the probe is not mine and was not edited. Its inputs did not change; the consumer did.

**Cause, confirmed in code.** `assemble_report_input` built its job population by iterating the
manifest's `expected_sources` and loading the differ-owned `current/` set for each. Discovery's
sources are recorded separately in `expected_discovery_sources` and its postings were written to
`normalized/`, which nothing downstream reads. Coverage metadata was consumed; the postings were not.

---

## 2. The chosen integration, and why this one

| Question the P06 review asked | Answer |
| --- | --- |
| Producer | the discovery Lambda, on its existing 07:05 schedule |
| Durable candidate representation | `discovery/live/provider={p}/live_jobs.json` |
| Owner of that write | discovery, solely — report holds no `PutObject` on the prefix |
| Consumer | `assemble_report_input`, merging into `jobs` **before** dedup |
| Invocation path | unchanged — DiscoverySchedule → discovery; AssembleSchedule → state machine → report |
| Permissions | unchanged — discovery already owns `discovery/*`; report already reads it |

`inference` — this is the smallest sound path. It needs no new Lambda, no new state-machine task, no
schedule change and no IAM change, because it places the new object inside a prefix whose ownership
and grants already match exactly the writer and reader involved.

**Why not the differ, and why not `current/`.** `evidence` (code + packet constraint): an ATS board
returns the employer's entire open list, so a posting's absence from a healthy snapshot is evidence
about the posting — the grace clock, mass-drop guard and silent-subset latch all rest on that. A
discovery feed returns a moving window bounded by a page budget, so absence from it is evidence
about the window. Routing discovery through the differ would read ordinary feed churn as closure,
which the packet forbids in those words. `current/` is additionally differ-owned by the M4 prefix
rule, so a discovery writer there would widen the differ's blast radius.

**The discovery lifecycle, stated explicitly** (`src/discovery/live.py`):

- observed this run → upsert; `first_seen_at` never moves, `last_seen_at` advances, count increments
- not observed, feed healthy → **retained unchanged**, with a stated last-verification age on the row
- feed produced no usable page → **nothing is said about any posting**; the view is returned untouched
  and its success history does not advance
- one bounded retention limit (21 days without re-observation), reported as retention, never closure

---

## 3. Production boundary trace

`tests/test_discovery_to_report_integration.py` runs the real stages in the order the deployment
invokes them. Only external HTTP, AWS and SES are mocked.

```
enumerate  (real handler)                  -> runs/  RUN_OPEN manifest + SQS fan-out
collector  (real collect_one, real queue)  -> raw/ normalized/ status/ + SUCCESS sentinels
discovery  (real handler)                  -> normalized/ + discovery/ live view
differ     (real handler, per company)     -> current/ events/
report     (real handler)                  -> reports/ + digest
```

The harness writes **no** manifest, `expected_sources`, normalized or current job set, screening
decision, scorecard or `ReportInput`. `evidence` — `test_the_stage_trace_reconciles_and_contains_no_
test_authored_intermediate` asserts structurally that every candidate id traces back to a normalized
record a producer wrote, that discovery rows trace to the producer-written live view, and that the
only S3 prefixes in existence are the eight the five stages own.

Pre-existing fixtures, identified as the packet requires: the committed
`config/application_history.json` projection and `config/candidate_policy.json` are used as history
and policy inputs and are not written by the harness.

### Stage trace (`evidence/p07_stage_trace.json`)

```
fetched/normalized : greenhouse:machinifyinc#900001, himalayas:all#enterprise-ae,
                     himalayas:all#internal-tools
discovery live view: himalayas:all#enterprise-ae, himalayas:all#internal-tools
considered         : 3    hard merges: 0
retained credible  : 2    excluded by policy: 1    below fit threshold: 0
report candidates  : himalayas:all#internal-tools (DISCOVERY_FEED),
                     greenhouse:machinifyinc#900001 (ATS_BOARD)
excluded with reason: himalayas:all#enterprise-ae — "sales-ownership: title is a sales role
                     (Account Executive)"
```

Population reconciles: 3 considered = 2 retained + 1 excluded + 0 below threshold. Both populations
are present, so this is not a discovery-only demonstration.

---

## 4. Required cases and their results

| Packet case | Result | Where |
| --- | --- | --- |
| Unregistered employer's fitting job reaches the saved shortlist with link and reason | pass | `test_unregistered_employer_reaches_the_saved_report_with_link_and_reason` |
| The regression fails on the pre-repair consumer without changing external inputs | pass | `test_the_same_inputs_produce_no_discovery_candidate_without_the_integration` + the two probe runs in §1 |
| Each enabled keyless provider's payload path feeds the common candidate path | pass (4/4) | `test_each_keyless_provider_capture_replays_onto_the_common_candidate_path` |
| Ineligible job excluded for the correct policy reason | pass | `test_ineligible_job_is_excluded_for_the_stated_policy_reason` |
| Already-submitted is not confused with prepared-but-unsubmitted | pass | `test_history_distinguishes_submitted_from_prepared_and_unknown` |
| All credible results available beyond the highlight limit | pass | `test_every_credible_result_survives_beyond_the_highlight_cap` |
| Duplicate across feeds appears once with provenance; distinct requisitions stay distinct | pass | `test_a_duplicate_across_two_feeds_appears_once_with_provenance` |
| Same job on a different page/day retains identity and freshness history | pass | `test_the_same_posting_on_a_new_page_and_a_new_day_keeps_one_identity` |
| Failed discovery loses no observation and fabricates no coverage | pass | `test_a_failed_discovery_round_loses_nothing_and_claims_no_coverage` |
| Feed absence is not closure | pass | `test_absence_from_a_later_feed_window_is_not_treated_as_closure` |
| Late-arriving discovery / report-before-discovery | pass | `test_a_late_arriving_discovery_round_reaches_the_following_report` |
| P05 owed-range and request-budget behavior preserved | pass | `test_the_request_budget_and_owed_ranges_still_hold_under_the_live_view` |
| Old-report fallback, and the new-format next round | pass | three `test_the_pre_discovery_report_shape…` / `…round_after_the_old_format_report…` / `…cold_start_is_still_distinguished…` |
| Same-date email suppression holds, with delivery mocked | pass | `test_same_date_digest_is_sent_once_and_never_actually_delivered` |
| Declared permissions and invocation routing | pass | three deployment-surface tests reading the real template and state machine |

**Provider replays are labeled.** The four keyless-provider cases replay payloads captured from the
live feeds on 2026-09-24 (`…/20260924_location_and_freshness_boundaries_v1/rehearsal/fixtures/`).
`evidence` about JPRS's handling of those bytes. **Not** a claim that any employer in them is hiring
today. The fit, exclusion, duplicate and staleness controls are synthetic and are labeled `SYNTHETIC`
in the file; they prove pipeline behavior and nothing about the market.

---

## 5. Permissions and invocation, checked against the real files

Mocked S3 grants everything, so the harness above cannot establish IAM. Three tests read
`infra/template.yaml` and `infra/statemachine/jprs-daily-assemble.asl.json` directly:

- `discovery/live/...` is covered by discovery's `PutObject` **and** `GetObject` on `discovery/*`
- it is covered by report's `GetObject` on `discovery/*`
- it is **not** covered by report's `PutObject` (which is `reports/*` only) — one writer by construction
- discovery still holds no write to `current/`
- DiscoveryCron 07:05 precedes AssembleCron 09:00 in `America/New_York`
- the assemble state machine still has exactly four states and no discovery task was added

`evidence` — `sam validate --lint` passes and `sam build --build-dir "$TMPDIR/jprs-p07-build"
--template-file infra/template.yaml` succeeds. The new module `src/discovery/live.py` is present in
**both** the built `DiscoveryFunction` and `ReportFunction` artifacts, which matters because the
report handler imports it; `.samignore` prunes no part of `src/`.

Note on the build transcripts: both SAM commands emit a `PermissionError` traceback writing
`~/.aws-sam/metadata.json`. That is this sandbox denying a write to SAM's own telemetry file, outside
the repository. Both commands exit 0 and produce their artifacts.

---

## 6. Test results

| Check | Result |
| --- | --- |
| Full suite before this run | 316 passed (`evidence` — recorded in the P05 run's checkpoint and handoff) |
| First run after the identity repair | 314 passed, 2 failed — both the P05 conditional report tests, both on the cursor-bound id |
| Full suite after re-scoping those two | 316 passed |
| Full suite with the 23 new acceptance cases | **339 passed** (`evidence/p07_test_results.txt`) |
| Policy projection check | `projection matches all policy sources` (`evidence/p07_policy_check.txt`) |
| `sam validate --lint` | valid (`evidence/p07_sam_validate.txt`) |
| `sam build` into a fresh build dir | succeeded (`evidence/p07_sam_build.txt`) |

**The two failures are preserved deliberately, not hidden.** They are the correct consequence of the
identity repair: those tests asserted `himalayas:NEW_TWO#fresh-two`, an id containing a pagination
cursor. Under the repair the same posting is `himalayas:all#fresh-two` on every page and every day.

**P05's tests were re-scoped, and their claim withdrawn.** `tests/test_resumable_discovery_and_
release_binding.py` previously carried a `_write_round` helper that hand-wrote the manifest, the
`current/` objects and the sentinels, under a section header claiming "real internal wiring". It was
not. Those two tests now drive the real enumerate handler, the real discovery `persist` and the real
report handler. The withdrawn claim is stated in the file. The P05 run's original evidence is
untouched.

---

## 7. Limits — what this run does NOT establish

1. **Nothing is deployed.** The running stack is the P06 build. Every claim here is local.
2. **No live feed was contacted.** All provider bytes are captured or synthetic.
3. **No live registry-absent candidate has been observed in a production report.** That acceptance
   condition is prepared in `DEPLOYMENT_HANDOFF.md` §5 and is explicitly **unproven**.
4. **Mocked storage does not prove IAM at runtime.** §5 checks the template's declared grants. A
   deployed policy evaluation is a separate observation.
5. **The retention bound (21 days) has not been exercised against a real feed's churn rate.** It is
   bounded and stated; whether three weeks is the right number is an operating question, not a
   correctness one.
6. **The unattended next-day scheduled path is a separate claim** and remains unverified.
7. **Adzuna remains credential-gated** and its live query path is still unexercised; the coverage
   receipt names it rather than hiding it.
