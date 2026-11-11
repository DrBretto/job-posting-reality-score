# gate_decision — P06 controlled discovery deployment

Stage: controlled deployment and immediate live verification · Packet:
`JPRS-L2-P06-controlled-discovery-deployment-v01` · Run:
`20260925_controlled_discovery_deployment_v1` · Date: 2026-09-25

## Outcome

**`revise_implementation`** — for the product goal, with the deployment itself complete and **safe to
leave running**. No rollback is recommended or required.

The deployment did what it was authorized to do and the four keyless feeds are now live-verified for
the first time. But the thing the packet says the work is actually for — "usable fresh job
opportunities" reaching Brett's morning report — does not happen yet, because nothing carries
discovery's stored jobs into the candidate report. That is an absent integration in code that predates
this run, not a deployment failure and not something this packet authorizes repairing.

The five claims stay separate, as the packet requires:

| Claim | Outcome |
|---|---|
| Local repair accepted (P05) | established before this run |
| **Stack deployed** | **`unlock` — complete and healthy** |
| **Individual sources live-verified** | **`unlock` — all four keyless feeds, one production run** |
| **Discovered jobs reach the user-facing report** | **`revise_implementation` — Finding B** |
| Later scheduled-round freshness | **pending**, fires 2026-09-26; not run, not waited for |

## Outputs reviewed

- `evidence/p06_live_verification_summary.md` — the full separated-claims account
- `evidence/p06_build_identity.txt`, `evidence/p06_post_deploy_resources.txt`
- `evidence/p06_live_discovery_coverage.json` — the real coverage receipt
- `evidence/p06_post_deploy_report_2026-09-25.md`, `evidence/pre_discovery_report_2026-09-25/`
- the executed change set, read in full before execution
- deployed code paths: `src/enumerate/handler.py`, `src/report/handler.py`, `src/differ/handler.py`,
  `infra/statemachine/jprs-daily-assemble.asl.json`

## Evidence and support quality

Rationale rather than a numeric rubric: this is a deployment-and-verification gate with separable
binary conditions.

| Packet condition | Result | Support |
|---|---|---|
| Explicit approval recorded before any cloud mutation | met | operator instruction quoted in `run_manifest.json`; first mutation was the post-approval artifact upload |
| Target confirmed from existing configuration, never guessed | met | stack, parameters, schedules and queues read before acting |
| No overlap with a running collection or assembly | met | today's assemble SUCCEEDED 09:00:41→09:01:03 EDT; zero running executions; both queues 0/0 |
| Fresh build, template and absolute config bound per P05 §4 | met | `mktemp` build dir; `--template-file "$BUILD/template.yaml" --config-file "$PWD/infra/samconfig.toml"` |
| Built artifact contains the discovery resources | met | 8 `DiscoveryFunction` refs, `jprs-discovery`, `jprs-discovery-daily`, `jprs-A8-discovery-errors` all present; hash recorded |
| Change set inspected before execution | met | 6 adds / 9 modifies / **0 removals / 0 replacements**, every detail `RequiresRecreation: Never` |
| Existing schedules, timezones and cadence preserved | met | collect `cron(0 7)` and assemble `cron(0 9)` unchanged, `America/New_York`; no schedule expression or timezone in any change scope |
| Discovery schedule matches the reviewed template, no invented cadence | met | `jprs-discovery-daily`, `cron(5 7 * * ? *)`, `America/New_York`, from the template default |
| Existing parameter values preserved | met | the three email parameters carried forward with values intact (no template default exists, so a blank would have broken alerting and delivery) |
| Bedrock off, resolver off, caps unchanged | met | `EnableNarrator false`, `ResolveCareersUrls false`, per-source caps unchanged and each respected |
| Retained storage, history and registry untouched | met | no `Remove`, no replacement; `/jprs/companies` never written; `admitted_this_pass: 0` |
| Production Lambda HTTP, not a local surrogate, establishes live access | met | one `jprs-discovery` invocation: 4/4 attempted and succeeded, `inaccessible: 0`, 295 jobs, 218 employers |
| Per-source attempted / succeeded / inaccessible / budget / retained evidence reported | met | coverage receipt plus 8 `raw/`, 8 `normalized/`, 8 `status/` objects and per-run SUCCESS sentinels |
| Partial success reported as partial coverage | met | `backlog_items: 1`, "himalayas feed has more pages; position saved and resumable"; report axis reads `PARTIAL` |
| Pending recent ranges and inaccessible coverage agree | met | `head_pending: {"himalayas": []}` and `inaccessible: []` — naturally observed, no injected failure |
| Report timing from the manifest | met | `basis: manifest.opened_at`, `run_started_at` matches the real `RUN_OPEN.json` |
| Prior-report boundary when one exists | **not met — Finding A** | `boundary: cold-start`; real old reports carry `complete_candidate_list: []`, so the earlier-release id fallback finds nothing |
| At least one registry-absent employer's job reaches the persisted report | **not met — Finding B** | 35 candidate rows, all `greenhouse` / `ATS_BOARD`; **zero** from the four discovery providers |
| Empty valid result distinguished from unverified integration | met | distinguished, and it is the latter: the jobs exist in `normalized/` but `current/` holds only `provider=greenhouse/` and the report never reads `expected_discovery_sources` |
| Fixed-board monitor and ordinary digest behavior intact | met | 15/15 collected, `current_job_count: 511`, `run_health VERIFIED-QUIET`, `digest_delivery: already-sent` |
| No forced resend, recipient change or suppression bypass | met | `already-sent`; zero emails sent by this run |
| No providers re-run until a green sample appeared | met | each source invoked once |
| Out-of-scope runtime repair avoided, surfaced instead | met | Findings A and B left unrepaired and reported |

## Top risks

1. **Finding B — the product goal is not yet delivered.** Discovery fetched 295 jobs from 218
   employers and stored them, but no path turns them into candidate rows: `enumerate` records discovery
   ids in `expected_discovery_sources` while the report loads jobs only from `expected_sources`, and
   the differ that owns `current/` is invoked only once per `/jprs/companies` entry. The operator sees
   a truthful discovery *coverage* line and none of the discovered *jobs*.
2. **Finding B also removes P05's persisted-report regressions as evidence of wiring.** Those two
   tests passed because the harness itself wrote `expected_sources` and `current/` for discovery
   sources. They still prove the traversal repair delivers recovered jobs into a report *given* that
   wiring; they never proved the wiring exists. That correction belongs on the record.
3. **Finding A — first-round freshness fell back to `cold-start`** because the real old-format reports
   carry an empty `complete_candidate_list`. Bounded and self-correcting from tomorrow, and the label
   is honest rather than a false claim, but P05 handoff §8's "earlier release still supplies its id
   list" is not true of this system's actual history.
4. **One run is not a durability claim.** The transport held with zero inaccessible entries this once;
   P04's non-deterministic truncation simply did not occur from Lambda here.

## Recommended next action

1. **Leave the stack deployed.** Discovery writes only `discovery/`, `raw/`, `normalized/` and
   `status/`; it cannot write `current/` or `events/`. The monitored radar is healthy and unchanged, so
   nothing is corrupting and nothing needs containment. Tomorrow's unattended round will also produce
   the pending cross-round evidence. A rollback would require the §6.2 data downgrade for no benefit.
2. **Author one bounded packet (P07) for the discovery-to-report wiring**, and treat it as a design
   decision rather than a patch: how discovery sources enter differ-owned `current/` (or whether the
   report should read them from `normalized/` instead), what disappearance semantics mean for a
   high-churn feed, dedup against monitored boards, and whether the report's candidate rows should
   carry unscreened feed volume. Include a regression that fails on the **production** manifest shape
   rather than on a harness-supplied one.
3. **Check the pending scheduled round** on 2026-09-26 against the exact paths in
   `evidence/p06_live_verification_summary.md` §6. Do not record it as passed before it runs.

No fresh broad audit is warranted. Adzuna credentials, general-industry coverage, employer admission
and longer-term completeness remain separate follow-ups, untouched by this run.
