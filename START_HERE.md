# Start Here: Job Posting Reality Score

This is the operator entrypoint. Read it before changing AWS or resuming the project in a new task.

## Current Direction — November 11: no report since October 9; repair built, NOT deployed

**Every scheduled report from 2026-10-10 to 2026-11-11 failed (33 days).** BuildReport hit its 300 s
limit four times a day (three retries of a deterministic timeout), then ReportIncomplete re-ran the
same full assembly and timed out too. The population discovery carries for 21 days grew to 4,671
postings; at 512 MB the report needs ~330–470 s for that. The failure alarm fired daily into an SNS
topic with no subscriber.

Branch `ai/radar-end-to-end-repair` (pushed) carries the repair: budget-aware evaluation that always
publishes, a real degraded path, no retries of deterministic timeouts, ReportFunction 1,769 MB, the
HN "Who is hiring" founder route, an SEC Form D company-first watchlist (never candidates),
duty-first screening (analyst titles, founding titles), and the current operator rules (human-first
holds, voice/telephony, no-cash-pay, AI-training-only). Plan: `docs/plans/2026-11-11-radar-end-to-end-repair.md`.
Run of record and the exact release/rollback: `../Infotropy Book/book-factory/runs/20261111_career-radar-end-to-end-repair-v1/`
(`EXECUTION_RETURN.md`, then `RELEASE_HANDOFF.md`). **Deployment needs Brett's approval.**

## Current Direction — September 30 (later): the dedup quadratic is repaired and DEPLOYED

**Deployed 2026-09-30T14:16:48Z** on explicit approval; CodeSha256
`WQyYJv/lp1AJoS8hNz8C/HAzvasQIsWtrtC24pP9IOI=`, deployed source byte-identical to the tested tree.

**Production, same corpus, same day: 226.74s → 140.11s; headroom 24.0% → 53.1%;
seconds-per-1,000-postings 148.58 → 91.82.** The answers did not move — 13 of 13 report fields
identical, every job-id set identical, `top_matches` identical in order, 122 retained / 35 new
strong / 22 previously engaged before and after. Digest correctly returned `already-sent`, so no
duplicate was mailed.

**One source file changes: `src/common/dedup.py`.** Verified against the *live deployed package*
rather than git, because the working tree carries several earlier uncommitted releases. Processed
template vs live: **6 code keys, 0 non-code differences**; `Timeout` stays 300 and `MemorySize`
stays 512.

**Locally on the same corpus:** `deduplicate` **7.342s → 0.023s**, growth per doubling
**~4.1x → ~2.0x**. Whole-report assembly **24.907s → 17.023s**.

**Why it was urgent.** Yesterday 1,344 postings at 188.52s and 36.9% headroom; this morning 1,526 at
226.74s and 24.0%. The cleanup scan was performing 1,526² = 2,328,676 ordered pair comparisons to
police **four** links, because its removal only ever fires on a link that already exists.

**Two gates you should know about:**

1. **`policy-check` exits 1** — `changed since the projection was built: operating_plan`. Unrelated
   to this repair: `OPERATING_PLAN.md` was edited at 09:48 today with a new operator direction about
   delegated outreach sending, and the committed screening projection was built 09-28. Independently
   confirmed **digest-stale, not screening-stale**: that paragraph sits under Business Outreach and
   the three rules mapped to `operating_plan` (`sales-ownership`, `customer-service-queue`,
   `clearance-government`) trace to unchanged sections. **The hash was not refreshed.**
2. **The Lambda package ships `tests/`, `docs/`, `scripts/` and `project-factory/`.** Pre-existing
   and out of scope here, but it is why every deploy rewrites all six code keys and why editing a
   document alone produces a new artifact.

- **Run of record:** `../Infotropy Book/book-factory/runs/20260930_career-radar-dedup-scaling-repair-v1/`
  — `EXECUTION_RETURN.md`, then `RELEASE_HANDOFF.md`.
- **Plan:** `docs/plans/2026-09-30-dedup-scaling-repair.md`.
- **Checks:** 666 tests pass, 6/6 mutants caught, independent review APPROVE, `sam validate` valid.
- **What needs you:** rebuild the candidate-policy projection if you want `policy-check` green
  (digest-stale only); the dormant `jprs-A3` alarm; Adzuna's credential.

## Current Direction — September 30: the morning report runs again

**`ReportFunction`'s timeout is 300s (was 90s), deployed 2026-09-30T07:20:08Z, and the report
completed in production for the first time since 2026-09-26.** Stack `jprs-v1`, CodeSha256
`Q7azuKmLMnOyWhu8ySckvldqCjps6r4v5ZvbrkvDHh0=`, deployed package verified byte-identical to the
tested tree. The change set was compared property by property against live before executing:
**7 differing properties — 6 Lambda code keys and `ReportFunction.Timeout` — and nothing else.**
`MemorySize` is unchanged at 512.

**The live run: 188.52s of a 298.97s budget on 1,344 postings — 110.45s / 36.9% headroom**, peak
memory 209 MB of 512, `VERIFIED-QUIET`, 15/15 sources, 103 retained, 29 new strong, digest **sent**.
Report objects exist at `reports/dt=2026-09-29/`.

**The report now states its own runtime.** Every report and digest ends with a line like
`Runtime: ran in 188.52s, of a 298.97s budget (110.45s / 36.9% left), over 1344 postings.` That line
exists because an 80.08s run against a 90s budget was recorded as an unqualified success on
2026-09-26 and nothing anywhere read the margin; three days later there was no report at all.

**Two things you should know, and neither is comfortable:**

1. **300s is a corpus budget, not a time budget.** `deduplicate` is quadratic — measured constant at
   3.1e-6 × n² seconds across a 6.7x range of n — so at the real 8.9x laptop-to-Lambda factor this
   ceiling is exhausted near **~1,990 postings**. The corpus is 1,344 today and went 813 → 1,344 in
   three days. The durable repair is `src/common/dedup.py:256-260`, which calls `normalize_employer`
   on both operands of a nested loop over the kept set (3.6M calls at 1,344 jobs, uncached).
   Hoisting or memoizing that key very likely makes the original 90s sufficient.
2. **`jprs-A3-report-not-assembled` has never been able to fire.** It watches custom metric
   `JPRS/ReportComplete`, which has **zero datapoints, ever** — nothing publishes it. It latched
   into ALARM on 2026-07-31 (missing data treated as breaching) and CloudWatch only notifies on
   transitions, so it was silent through all four failed days. `jprs-A2-missed-run` is the same.
   `ReportFunction` already holds `cloudwatch:PutMetricData` for namespace `JPRS`, so the publisher
   needs no IAM change — but a custom metric is a small paid resource and was out of scope.

**Application history is reconciled through 2026-09-28**: 68 entries. Grafana Labs Staff AI Engineer
(the operator completed and submitted it; employer confirmed 09-27), AWeber Operations Engineer II,
BetterHelp Full Stack Software Engineer, the Catalyst·Wayfare Agent Builder email and BJAK all read
SUBMITTED. AWeber and BetterHelp were the live risk — both are **still open on their employers' own
boards** and today's feed carries both at aggregator URLs. Grafana's other two Staff AI Engineer
requisitions correctly still read NEW and appear in the live report.

- **Run of record:** `../Infotropy Book/book-factory/runs/20260928_career-report-runtime-and-confirmed-history-recovery-v1/`
  — `EXECUTION_RETURN.md`, then `RELEASE_PROPOSAL.md` and `ROLLBACK.md`.
- **Plan:** `docs/plans/2026-09-28-report-runtime-recovery.md`.
- **Checks:** 638 tests pass, `policy-check` exit 0, `sam validate --lint` valid.
- **What needs you:** the dedup repair before the corpus reaches ~1,990; a decision on the metric
  publisher; and Adzuna still needs a credential for ordinary-industry breadth.

## Current Direction — September 28 (evening): DEPLOYED, and the report cannot finish

**Superseded by the section above on the report's runtime. Everything else in it still stands.**

**The broad-ownership release and a repaired application-history projection are DEPLOYED.** Stack
`jprs-v1` updated 2026-09-28T19:40:54Z; all five functions run CodeSha256
`x+0H6neXeKEpOrtxMplCizjk8alGOY0dSLsD6YH/IpI=`, and the deployed package is byte-identical to the
tested tree (652 files). The change set was compared property by property against the live stack
before executing: **6 differing properties, all Lambda code keys, 0 non-code differences**, 42
resources both sides, parameters identical.

**And the morning report has not run since 2026-09-26.** The `jprs-report` Lambda times out at its
90-second limit — on 09-27, on 09-28's scheduled round, and on the verification round run after this
deployment. The failure predates this release: the last successful report used **80.08 seconds of
its 90-second budget** and the corpus has grown since. Nothing was watching that margin. Raising the
timeout is an infrastructure change, which the packet governing this release explicitly forbade, so
it is reported rather than patched:
`../Infotropy Book/book-factory/runs/20260928_career-radar-release-and-history-reconciliation-v1/findings/FINDING-01-report-lambda-exceeds-its-90s-timeout.md`.

Discovery is healthy and unaffected: 4 of 4 keyless feeds, 302 postings, 705 in the live views, 18s.

- **Your usable pool for today**, rendered locally from that production data through the deployed
  code path: `.../20260928_career-radar-release-and-history-reconciliation-v1/RADAR_POOL_2026-09-28.md`
  — 38 retained, 20 new, 11 reaching you only because of the ownership change, 7 correctly suppressed
  as already engaged.
- **What needs you:** raise `ReportFunction`'s `Timeout` (and probably `MemorySize`), and provision
  Adzuna if you want ordinary-industry breadth.

### The history repair, in one paragraph

`config/application_history.json` was built 2026-09-24 and seven submission rounds had run since, so
postings already submitted on the 26th and 27th were being announced as NEW. It now carries **64
entries with an evidence cutoff of 2026-09-28**, rebuilt from the runs' own append-only
`SUBMISSION_LOG.md` files where the employer's acceptance is quoted against a named requisition —
`history-refresh` does it, repeatably, dry by default. An entry can carry several URLs for one
requisition, because the feeds carry aggregator URLs and the applications were submitted on ATS URLs;
three real submissions are reachable by nothing else. The report now distinguishes **missing / stale
/ current / known-empty** and prints the cutoff, where before it announced a missing projection and
said nothing at all about a stale one. Five applications are recorded but **not settled** — blocked,
held, or drafted and not sent — and are neither suppressed nor treated as sent.

A folder scan is still capped at PREPARED and still cannot conclude a submission on its own; that cap
is now enforced when the projection is *read*, not only when it is built.

## Current Direction — September 28 (morning): the broad-ownership work, then local only

**This section described the state BEFORE the release above. It is kept as the record of what was
built; production is no longer unchanged.**

Your 2026-09-28 note — first or sole software-engineer roles at smaller businesses are especially
attractive, and broad-ownership roles must stay available for review "even when an AI-oriented
keyword score is low" — is now implemented. Before this, a plausible opening reached a readable
section of your report only at a fit score of 0.40 or better, and that score is AI-weighted by
construction: its title lane pays 0.30 for `agentic` and nothing at all for "Internal Applications
Developer". Everything below the line became an id in `below_fit_threshold_job_ids` — no title, no
employer, no link, no reason, on any page you read.

What changed: a posting that establishes broad or first/sole ownership **of software**, for the
person being hired, now reaches the **needs-a-check** section with its ownership evidence on the
row, whatever its fit score. Confirmed sole ownership, a stated small team and unknown structure
stay three separate answers, and none of them is ever inferred from a title — a Staff title says
nothing about team size, and a missing headcount produces no finding.

On 176 real postings pulled from the four keyless feeds on 2026-09-28: **your existing seven
candidates are unchanged, job id for job id**, seven more became readable, and the below-threshold
tail fell from 86 to 79. Zero confirmed sole-engineer openings appeared — these feeds are
remote-technology feeds, and Adzuna, the one configured source that spans ordinary industries, is
still credential-gated.

One exclusion was repaired along the way, found by reading an actual posting rather than by
reasoning about the code: **Benzinga's "applying to this role requires a Loom video walkthrough
under 5 minutes" was reaching your retained pool.** That is a recorded candidate video, which you
exclude; `loom` and `video walkthrough` were simply absent from the pattern. Screening ruleset
1.5.0 → 1.6.0. Live human video calls are unaffected and tested.

- **Run of record:** `../Infotropy Book/book-factory/runs/20260928_career-broad-ownership-discovery-v1/`
  — read `EXECUTION_RETURN.md` first, then `COVERAGE_CHECK.md`.
- **Plan:** `docs/plans/2026-09-28-broad-ownership-discovery.md`.
- **Checks:** 551 tests pass, `policy-check` exits 0, the SAM template validates.
- **Independent review:** returned `revise` with seven material findings, all real and all
  repaired. The largest: the first version of the ownership patterns lost 19 of 24 plain-English
  statements of sole ownership — an ordinary business writes "nobody here writes software today",
  not "sole engineer". Now 24 of 24, pinned as a regression corpus. See the run's
  `INDEPENDENT_REVIEW.md`.
- **What needed you then:** deployment authorization. That was given and executed — see the section
  above. Nothing was staged, committed or pushed in either run, and no application was submitted.

## Current Direction — September 26

**CURRENT STATE (2026-09-26 18:27Z) — supersedes everything below it that says P07–P10 are local.**
P10 was deployed at 14:22Z by the Career Factory release run and broke discovery in production
(first round could not read its own never-written state: no `s3:ListBucket`) while the report kept
failing on its vocabulary guard. The recovery release is now DEPLOYED and live-verified: one IAM
statement (discovery may list `discovery/*` only) plus discovery/report code. The ordinary round run
after deployment, under the deployed roles, succeeded end to end — discovery 4/4 keyless feeds and
297 jobs, assemble 15/15 boards, `daily_report` persisted for 2026-09-26 with 56 retained candidates
(15 from discovery), digest accepted by SES, and `scripts/inspect_discovery_integration.py` returned
`ACCEPTANCE_MET`. Still NOT verified: an unattended scheduled round (next 07:05 / 09:00), and digest
receipt. Adzuna remains credential-gated. Record, evidence, rollback: `../Infotropy Book/book-factory/runs/20260926_career-radar-production-recovery-v1/`
(`EXECUTION_RETURN.md`, `RELEASE_PROPOSAL.md`); plan: `docs/plans/2026-09-26-radar-production-recovery.md`.
The live baseline for the NEXT release is this build; see `infra/DEPLOY.md` § Release gate.

**DEPLOYED on 2026-09-25 (P06). Discovery is live and verified — but its jobs do not reach your
report yet.** Read those two sentences together; neither is the whole story.

**Latest (2026-09-26, P10, local only): the release is ready and one thing is missing — your
authorization.** The screening gate that was blocking the deploy is genuinely resolved: your
2026-09-26 note about not returning to customer service or call-center work is now implemented as a
screening rule, which nothing in the code had before. `policy-check` exits 0, 433 tests pass, the P06
baseline verifies 36/36, and the release preflight passes as code-only across all six functions.
Read `project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/OPERATOR_RETURN.md`.

What is live: the P01-P05 overhaul is deployed to `jprs-v1` in `us-east-1`. A new `jprs-discovery`
pass runs daily at **07:05 America/New_York**, between the unchanged 07:00 collect and 09:00 assemble.
All four keyless feeds were verified from the real production Lambda — 295 jobs across 218 employers,
nothing inaccessible, every source inside its request cap, Adzuna correctly reported as needing a
credential. That closes the live-transport gate every earlier round had to leave open.

What is NOT live: **none of those discovered jobs can become candidate rows in your morning report.**
The report builds rows only from the monitored-board list, and nothing carries discovery's stored jobs
into the differ-owned state the report reads. So the report tells you truthfully how wide the search
reached, and shows you none of what it found. This is an absent integration that predates the
deployment; it was surfaced rather than improvised over. P07 has since repaired the normal path
locally and P08 has closed both findings from P07's independent review — interrupted-publication loss
at the original live-write boundary and parts of the release handoff — also locally. P08's new
independent review nevertheless reproduced loss at the first pending-ledger write and false-green
verification helpers; P09 closed both. P10 then aligned screening with your current preferences and
re-verified the release. P07-P10 all remain UNDEPLOYED and production behavior above is unchanged.
Read this run's `gate_decision.md` for current release acceptance.

Earlier reviews and returns are preserved and remain the review record. P05's `DEPLOYMENT_HANDOFF.md`
was the release instruction this deployment followed.

- **Controlling plan:** `docs/plans/2026-09-24-open-market-job-discovery.md`.
- **Latest executed packet:** `JPRS-L2-P10-policy-alignment-and-controlled-release-v01` (local only).
- **Current return:** `project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/OPERATOR_RETURN.md`.
- **Controlling review:** `project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/INDEPENDENT_REVIEW.md` — `revise`, with all three material findings repaired, rechecked and pinned in the same run.
- **Handoff to run when authorized:** `project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/DEPLOYMENT_HANDOFF.md` §4 (deploy) and §4.1 (one controlled live round). Supersedes P09's on two points.
- **Next packet:** none staged. The next step is your deployment authorization, not more implementation.
- **Why P08 existed:** `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/ORCHESTRATOR_REVIEW.md`.
- **Deployment run of record:** `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/` — read its `OPERATOR_RETURN.md` first, then
  `evidence/p06_live_verification_summary.md`, which keeps the five claims separate: local repair
  accepted / stack deployed / sources live-verified / **jobs reaching the report NOT established** /
  cross-round freshness **pending**.
- **Handoff of record:** `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/DEPLOYMENT_HANDOFF.md` — supersedes P04's, whose §4 forward
  command could not select the build it had just verified. Its §4 is the executable release
  instruction; its §6 keeps the required rollback order and the data downgrade.
- **Latest return and review:** `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/OPERATOR_RETURN.md`
  and that run's `ORCHESTRATOR_REVIEW.md`. The independent producer/consumer probe reproduces one
  normalized discovery job and zero report candidates without fixture-created intermediate state.
- **Verified local result (P05, still true):** 316 tests pass; SAM template validates and builds; the
  policy projection matches all sources. Both P04-review defects are repaired, each reproduced first against the reviewer's own
  unmodified probe
  (`.../20260925_resumable_discovery_release_repair_v1/evidence/p05_before_repair_p04_probe.json`,
  then `p05_after_repair_p04_probe.json`). Its report tests supplied the missing connection themselves;
  they prove conditional behavior, not a production discovery-to-report path.
- **Regression strength, measured rather than asserted:** of the 20 new tests, 12 fail against a
  reconstructed copy of the P04 source — including both review scenarios and both persisted-report
  checks (`.../evidence/p05_new_tests_against_p04_source.txt`).
- **Counts, with their populations named.** These are not interchangeable:
  - the P03 live sweep considered **821 postings** and observed **216 employers absent from the
    monitored registry** — employers, not postings, and observed, not monitored;
  - of that sweep, **44 postings were retained** with links, reasons and honest ages;
  - the P04 rehearsal is a **smaller captured slice** (four Himalayas cursor pages plus three bulk
    feeds): 264 postings considered, 108 policy-excluded, 145 below the fit threshold, **11
    retained** (5 strong, 6 needing a check), 3 labelled newly arrived. Fewer retained rows than P03
    is a smaller input, not a regression.
- **Fresh-first priority:** genuinely recent credible openings first, ideally within 24 hours, while
  preserving missed-day catch-up, older strong fits and unknown dates. "New since the last round" now
  means a posting the previous report did not show — identity, not a timestamp comparison.
- **Location policy:** onsite/hybrid only when genuinely local. The system does not measure drive
  time and no longer pretends to: it resolves the state boundary and the cities you named, and routes
  every in-state worksite to a confirmation step rather than guessing. A New Hampshire onsite role
  arrives as "confirm the worksite", not as a yes or a no.
- **Deployment boundary:** unchanged. AWS, registry changes, credentials and any paid service still
  require explicit approval. P06 is deployed; P07, P08, P09 and P10 executed locally. No git staging,
  commit or push occurred in any of these runs, and no application has been submitted.

### Current next step — your deployment authorization

**P10 is executed locally:**
`project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/`.
Read `OPERATOR_RETURN.md` first.

In short: the radar now applies the rule you wrote on 2026-09-26. Before this, **nothing in the code
knew** that broadening for stable employment does not mean customer service or a call center — there
was no call-center, customer-service, phone-support or help-desk handling in it at all. The check that
went red was reporting stale hashes; the missing thing was the behavior. Refreshing the hashes would
have turned the light green and changed nothing you'd be shown.

On the 282 real postings captured on 2026-09-24, five roles that had been reaching your report as
"below the fit threshold" with no reason recorded are now excluded with the duty text that justifies
it — Resource Guru, Warehance, Unio Digital (an MSP phone helpdesk), CoinGecko (no support title; the
duties gave it away) and Integrated Language Solutions. **Your eleven retained candidates are
unchanged, job id for job id.** The rule subtracts phone-queue work; it does not shrink the good list.

Everything the clarification says the exclusion does NOT mean is preserved and tested: software built
for a support department, internal problem ownership, requirements conversations and delivery
meetings, employers that already have an engineering team, and postings with no AI wording. Where a
support title's duties are genuinely unclear you get "read this one" rather than a silent yes or an
invented no.

An independent reviewer then broke it twice in opposite directions, and both are fixed: an internal
IT/DevOps role managing an internal service desk queue was being **hard excluded** — the population
your note was written to open up — and a posting titled **Call Center Representative** answering
customer phone enquiries came back **eligible** because it mentioned building a report. Neither was
visible in the corpus audit. See `INDEPENDENT_REVIEW.md`.

**What needs you: explicit authorization to deploy this and run one ordinary round.** That is the only
remaining item. `policy-check` exits 0, 433 tests pass, the P06 baseline verifies 36/36, the preflight
passes as `CHANGE_SET_IS_CODE_ONLY` across all six functions, and the rollback drill leaves your
working tree byte-identical. The exact sequences are `DEPLOYMENT_HANDOFF.md` §4 and §4.1.

**Leave the stack deployed meanwhile.** Discovery physically cannot write `current/` or `events/`, the
monitored radar is healthy and unchanged, and nothing is corrupting. No rollback or data downgrade is
needed. No new committee and no new broad review by default.

**Still genuinely unchecked:** the unattended round on 2026-09-26 (discovery 07:05) was not inspected.
It runs P06's code, so it says nothing about this repair either way; exact evidence paths are in the
deployment run's `evidence/p06_live_verification_summary.md` §6. P06's approval is spent and does not
authorize shipping P07–P10. The August-era rollback still requires its documented job-data downgrade;
do not improvise a source-only rollback.

## Deployed Baseline — August 2

- **Live system:** `jprs-v1` is deployed and running in `us-east-1`.
- **Live registry:** 15 validated Greenhouse boards selected for Brett's strongest job lanes.
- **Deployed usefulness pass:** Brett-specific fit ranking, linked daily results, SES digest delivery,
  authoritative observation dates, and expanded tests.
- **Active branch:** `codex/real-job-radar`.
- **Verified production run:** 15/15 current targets collected; 519 postings scored; 41 useful
  matches surfaced; queues and DLQ empty.
- **Current checkpoint:** daily radar active. SES identity, first delivery, and duplicate-suppression
  marker are verified.
- **Completed baseline plan:** `docs/plans/2026-08-02-real-job-radar.md`.

As of August 2, all 15 selected public boards returned successfully. Their 519 current postings
produced 41 roles above the useful-fit threshold. The highest results included agentic-system roles
at Machinify, Legion Intelligence, ICON, Grafana Labs, Future, and Cargomatic.

## What The Live Pass Does

1. Replaces Stripe, Figma, and GitLab with 15 companies selected for agentic/applied AI,
   backend/platform, automation, and developer-tooling work.
2. Scores the authoritative `current_jobs.json` records instead of leaving scorecards empty.
3. Shows company, title, location, fit evidence, and a direct posting link.
4. Caps the human digest while retaining every event and scorecard in JSON.
5. Sends the deterministic Markdown digest through SES and records a delivery marker to prevent
   ordinary retries from sending it twice.
6. Preserves the first date JPRS observed a posting across future collections.

## Email Delivery

The configured SES identity was verified on August 2. The controlled report returned
`digest_delivery=sent`, wrote `digest_delivery.json`, and an immediate second invocation returned
`already-sent`. No manual email activation remains.

## Future Target Changes

Do not update `/jprs/companies` while collection or assembly is running. Change
`config/companies.yaml`, run the checks, deploy code first when needed, then change the registry and
run both legs against the same target set.

### 1. Confirm Local State

From the repository root:

```bash
git status
.venv/bin/pytest -q -p no:cacheprovider

# A fresh build directory, so no stale default build can be selected later.
export BUILD="$(mktemp -d /tmp/jprs-build-XXXXXX)"
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml --build-dir "$BUILD"
```

The working branch should be committed and pushed. Deployment and merge to `main` each require
Brett's explicit approval.

### 2. Deploy The Code And Permission Update

After approval for a future code change:

```bash
# Confirm the artifact is the one you are about to ship.
test -f "$BUILD/template.yaml" && grep -q DiscoveryFunction "$BUILD/template.yaml" \
  && echo "OK: built template contains DiscoveryFunction"

sam deploy \
  --template-file "$BUILD/template.yaml" \
  --config-file "$PWD/infra/samconfig.toml" \
  --config-env default
```

**Never omit `--template-file`, and keep `--config-file` absolute.** With the template omitted, SAM
searches the current directory and would select a nonexistent root template from the repository root,
or a stale `infra/.aws-sam/build/template.yaml` containing no discovery function if run from `infra/`.
With the template in a build directory, a relative config path resolves inside that build directory and
this repository's config is silently missed. Measured evidence and the local selection check:
`project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/evidence/p05_deploy_selection_results.json`.

Review the change set before confirming it. The report role gains read access to `current/*`, and the
updated Lambda package connects scoring and SES delivery. Do not accept unrelated infrastructure
changes.

### 3. Update The Production Registry

Generate the payload:

```bash
.venv/bin/python -m src.cli registry --compact
```

In the AWS console:

1. Open **Systems Manager -> Parameter Store** in `us-east-1`.
2. Open `/jprs/companies` and choose **Edit**.
3. Replace its value with the generated JSON exactly as printed.
4. Save it as a standard String parameter.
5. Reopen the parameter and confirm it contains 15 enabled entries.

Do not hand-edit board tokens in the console. Change `config/companies.yaml`, test it, and regenerate
the payload instead.

### 4. Run One Controlled Collection

1. Open **Lambda -> jprs-enumerate -> Test**.
2. Use `{}` as the test event.
3. Confirm the response reports 15 expected and enqueued tasks.
4. Open **SQS -> jprs-collect-queue -> Monitoring** and wait for visible/in-flight messages to reach
   zero.
5. Confirm `jprs-collect-dlq` remains empty.
6. In S3, confirm fresh status sentinels exist for the run date.

### 5. Run One Controlled Assembly

1. Open **Step Functions -> jprs-daily-assemble**.
2. Start an execution with `{}` as input.
3. Confirm every Map item completes and the report Lambda succeeds.
4. Open `reports/dt=YYYY-MM-DD/daily_report.md` in the project bucket.
5. Confirm the report names 15 expected sources and includes readable linked matches.
6. Confirm `daily_report.json` includes nonempty `scorecards` and `top_matches`.
7. Confirm the digest email arrives and `digest_delivery.json` exists beside the report.

If the same date is assembled again, the report updates but the delivery marker prevents an ordinary
duplicate email.

## Normal Daily Use

After deployment, the normal system requires no daily AWS work:

1. Collection starts at 07:00 America/New_York.
2. Assembly starts at 09:00 America/New_York.
3. Read the digest and complete result set; review every credible fit without a fixed quota.
4. Open the direct links, verify each role is still open, tailor the resume/message, and apply
   manually.
5. Use the JSON report when you want the complete score decomposition or suppressed events.

Until the overhaul is deployed, this is monitoring of the configured employers, not broad
market discovery. Supplement it with wider discovery rather than treating a quiet monitored
set as an exhausted market. Once deployed, the report says which of the two it is on its own:
run health is split into collection, discovery coverage, freshness and interpretation, and
collection health explicitly states that it is not a claim about the job market. The ranking is a triage aid, not a substitute for reading the posting. A high fit score means the
stored text aligns with Brett's demonstrated lane; it does not guarantee interest from the company.

## Troubleshooting

**Report says INCOMPLETE**

Read the named sources, inspect the collector logs and DLQ, and rerun only after the source succeeds.
The differ freezes missing source state; do not manufacture success sentinels.

**No matches appear**

Check `current_job_count` and `scorecards` in `daily_report.json`. An `AccessDenied` must fail the
report rather than silently becoming an empty result. If the current count is zero, verify the SSM
registry, current S3 keys, and report-role access to `current/*`.

**No email arrives**

Check the report Lambda result, SES identity status, CloudWatch logs, and `digest_delivery.json`. If a
marker exists, that date has already been delivered. Do not delete it merely to test retries.

**A board returns 404 or changes format**

Disable that entry in `config/companies.yaml`, regenerate SSM JSON, and update the parameter between
runs. Preserve the failure evidence; do not let it create disappearance events.

## Working Agreement

Brett approves and performs consequential AWS changes or explicitly delegates a deployment. The AI
may inspect state read-only, implement locally, write tests, prepare exact instructions, and diagnose
actual failures. It must not silently deploy, update SSM, merge to `main`, delete data, or expose
private account details.

## Resume In A New Task

Use:

```text
Resume Job Posting Reality Score from START_HERE.md. Read the current branch, active plan, and live
AWS state before acting. Tell me the exact current checkpoint.
```

When documents disagree, use this order: current operator instruction, `AGENTS.md`/`CLAUDE.md`,
verified AWS state, active plan, then historical roadmap material.
