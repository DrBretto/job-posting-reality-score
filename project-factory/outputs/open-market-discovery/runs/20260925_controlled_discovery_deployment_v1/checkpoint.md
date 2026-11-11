# checkpoint — P06 controlled discovery deployment

Run: `20260925_controlled_discovery_deployment_v1` · Packet:
`JPRS-L2-P06-controlled-discovery-deployment-v01` · Status: `completed` · Date: 2026-09-25

Operator approval for this deployment was given in-session and is quoted in `run_manifest.json`. It
was recorded before any cloud mutation.

## What moved

**The overhaul is deployed and running in `jprs-v1` (`us-east-1`).** Stack `UPDATE_COMPLETE` at
13:07:45Z from a change set inspected first: 6 adds (the declared discovery function, its role, log
group, scheduler role, schedule and the A8 alarm), 9 non-destructive modifies, **0 removals and 0
replacements**. Existing collect (07:00) and assemble (09:00) schedules, their `America/New_York`
timezone, the 15-board registry, retained storage and all existing parameter values are unchanged.

**The live-transport gate is closed for the four keyless feeds.** One production invocation of
`jprs-discovery`: all four attempted and all four succeeded, `inaccessible: 0`, **295 jobs from 218
employers**, Adzuna correctly reported as credential-gated. Real pagination exercised (himalayas
`board=all` plus four descending-timestamp cursor pages). Every source stayed inside its configured
request cap. Full `raw/`, `normalized/`, `status/` evidence and per-run SUCCESS sentinels retained.

**The P05 resumability invariant held on real data, observed rather than injected:** `head_pending` is
empty and the receipt's `inaccessible` is empty — the two agree, so there is no claim of clean recent
coverage while ranges remain owed. The historical backfill saved its position and the receipt says so
(`backlog_items: 1`, "position saved and resumable").

**Report timing is wired in production:** `basis: manifest.opened_at`, matching the real `RUN_OPEN.json`
(the old code wrote `timing: null`). The monitored radar is intact: 15/15 collected,
`run_health VERIFIED-QUIET`, 511 current jobs, 35 candidate rows. `digest_delivery: already-sent` —
existing suppression honored, **zero emails sent by this run**.

## What is blocked or uncertain

**Finding B — the product goal is not delivered yet, and this is the headline.** Discovery's 295 jobs
cannot become candidate rows. The report's 35 rows are all `greenhouse` / `ATS_BOARD`; **zero** come
from the four discovery providers. The jobs are not missing — they are in
`normalized/schema_v=1/provider={himalayas,jobicy,remoteok,remotive}/` — there is simply no path to the
report:

1. `enumerate.build_manifest` records discovery ids in `expected_discovery_sources`, and only monitored
   ATS boards in `expected_sources`.
2. `report.assemble_report_input` loads candidate jobs by iterating `expected_sources` →
   `current_jobs_key(...)`. It never reads `expected_discovery_sources` (0 occurrences in the file).
3. `current/` is differ-owned and the differ is invoked once per `/jprs/companies` entry by the assemble
   Map. Discovery providers are not in that registry, so `current/` holds only `provider=greenhouse/`.

This is an **absent integration, not an empty valid result**, and it predates this run. Left unrepaired
deliberately: it is a design decision, well outside "a trivial, clearly evidenced launch correction".

**Finding B also corrects the record on P05.** Its two persisted-report regressions passed because the
test harness itself wrote `expected_sources` and `current/` for discovery sources — the wiring
production lacks. They prove the traversal repair delivers recovered jobs into a report *given* that
wiring; they never proved the wiring exists.

**Finding A — the first post-deploy report read `timing.boundary: cold-start`.** Real old-format
reports carry `complete_candidate_list: []` (their rows live in `top_matches`) and no `timing` block, so
the earlier-release id fallback found nothing. Verified against `reports/dt=2026-09-24/daily_report.json`.
Bounded and self-correcting from tomorrow; the label is honest, but P05 handoff §8's claim that an
earlier release still supplies its id list is not true of this system's real history.

Also true, and not a defect: one production run is not a durability claim for the transport, and for
`dt=2026-09-25` only, the stored report is the new-code version while the emailed digest was the old
code's (prior object preserved in evidence; they agree from tomorrow).

Untouched, still separate: Adzuna credentials, general-industry coverage, employer admission, the
careers-URL resolver's live path.

## What is next

One unlocked task, and it is an operator decision, not an automatic continuation:

**Author a bounded P07 packet for discovery-to-report wiring.** Treat it as a design decision — how
discovery sources enter differ-owned `current/` (or whether the report should read `normalized/`
instead), disappearance semantics for a high-churn feed, dedup against monitored boards, and whether
unscreened feed volume belongs in candidate rows. It must include a regression that fails on the
**production** manifest shape rather than on a harness-supplied one.

**Leave the stack deployed meanwhile.** Discovery cannot write `current/` or `events/`, the monitored
radar is healthy, nothing is corrupting, and tomorrow's unattended round produces the pending evidence.
No rollback, no containment, no data downgrade is needed or recommended.

## PENDING — not run, not waited for

The first unattended round on the new code fires **2026-09-26**: collect 07:00, discovery 07:05,
assemble 09:00 `America/New_York`. Exact evidence paths are in
`evidence/p06_live_verification_summary.md` §6. The cross-round freshness check (`timing.boundary`
should read `reported-ids` with `previous_run_id: 2026-09-25`) is the real retest of Finding A and
**has not happened**. Nothing here may be read as having checked it. No automation was created to wait
for it.

## Artifacts emitted

Run root: `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/`

| path | status |
|---|---|
| `run_manifest.json` | complete — records the approval quote and the five separated claims |
| `checkpoint.md` | complete (this file) |
| `gate_decision.md` | complete — `revise_implementation` for the product goal; deployment `unlock` and safe to leave running |
| `OPERATOR_RETURN.md` | complete |
| `evidence/p06_live_verification_summary.md` | the full separated-claims account with the pending check |
| `evidence/p06_build_identity.txt` | source/template/config hashes, baseline and dirty-state boundary |
| `evidence/p06_post_deploy_resources.txt` | sanitized post-deploy stack, function, schedule and alarm state |
| `evidence/p06_live_discovery_coverage.json` | the real production coverage receipt |
| `evidence/p06_post_deploy_report_2026-09-25.md` | the persisted new-code report |
| `evidence/pre_discovery_report_2026-09-25/` | the already-delivered report, preserved before the re-run |

Repository files changed by this run: continuity surfaces only (`START_HERE.md`, `docs/PLAN.md`,
`project-factory/ORCHESTRATOR_BOOTSTRAP.md`, `project-factory/meta/*`,
`project-factory/claude_handoff/PACKET_REGISTRY.tsv`, and the controlling plan's log). **No runtime
source file was changed by this run.** Nothing was committed, staged, branched, reset or pushed; the
uncommitted P01–P05 tree is intact.

## Resume steps

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

# deployed state is healthy (read-only)
aws cloudformation describe-stacks --stack-name jprs-v1 --region us-east-1 \
  --query 'Stacks[0].StackStatus' --output text          # expect UPDATE_COMPLETE
aws lambda get-function-configuration --function-name jprs-discovery --region us-east-1 \
  --query '[State,LastUpdateStatus]' --output text        # expect Active Successful

# tomorrow's pending round (do NOT record as passed before it runs)
aws s3 cp s3://jprs-prod-bw-20260731/discovery/run=2026-09-26/coverage.json - --region us-east-1
aws s3 cp s3://jprs-prod-bw-20260731/reports/dt=2026-09-26/daily_report.json - --region us-east-1 \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["timing"])'
# expect timing.boundary == "reported-ids" and previous_run_id == "2026-09-25"

# Finding B, reproducible in seconds without AWS
grep -c expected_discovery_sources src/report/handler.py   # expect 0
```
