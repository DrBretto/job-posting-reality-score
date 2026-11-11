# DECISION_LOG

## D-029 - A support queue is defined by WHOSE contacts it handles, not by the word "support"

- Date: 2026-09-26
- Status: executed locally; gate `unlock` for the local stage only. No deployment authorization sought,
  granted or implied.
- Evidence: `project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/`
  — a per-identity disposition audit over 282 real postings captured 2026-09-24 through the real
  caller path (`evidence/p10_dispositions_{before,after}.json`, `p10_disposition_delta.json`), a
  bounded independent review that returned `revise` (`INDEPENDENT_REVIEW.md`), 433 passing tests with
  22 of 40 new ones failing against a reversed-edit pre-change tree, and the full release sequence
  re-run after the review repairs.
- Decision: implement the 2026-09-26 clarification as a rule whose hinge is the AUDIENCE of a contact
  duty, not the presence of support vocabulary. `support` is one of the most common words in a job
  description, so the rule requires a channel, a handling verb and an audience inside a duty span, and
  then: an external audience excludes with its duty quoted; an internal audience routes to review,
  because internal users are explicitly welcome; an unnamed audience on a queue-shaped channel routes
  to review; and a bare channel noun is not evidence of anything. A call-centre title is
  unconditional, because the policy names it without qualification. No title is ever cleared to
  ELIGIBLE on keyword evidence. Guards map one-to-one onto the clarification's own sentences.
- Consequences: the clause that earned this entry is the one the review forced. AUDIENCE is a property
  of the sentence and is read at clause scope; a GUARD is a property of the duty and stays duty-span
  scoped. Collapsing the two in either direction produced a real defect in this run — reading the
  audience too narrowly hard-excluded internal IT roles managing an internal service desk queue (the
  population the clarification exists to open up, with evidence text that said "internal" under a
  reason asserting "external"), and reading a guard too widely cleared a Call Center Representative
  answering customer phone enquiries because one software verb appeared elsewhere in the description.
  Neither was visible in the 282-posting corpus audit, which contains none of those phrasings and
  produces ZERO pending checks for the new rule: **a corpus audit measures what a rule does to the
  data it happens to hold, and is not a substitute for adversarial review.** Standing consequence for
  future screening rules in this repository: a projection refresh is bookkeeping, never an
  implementation, and a new exclusion is not accepted until its consequences are named by job id AND
  an independent context has tried to make it fire on work the operator wants.
- Carried as accepted limitations rather than repaired: a PENDING_CHECK posting that also scores below
  the fit band reaches no readable report section (pre-existing ranking architecture, outside this
  packet's write surface); the rule's third state has no real-data evidence yet; one theoretical
  report-render path was reasoned from code and never reproduced.
- Run: `project-factory/outputs/open-market-discovery/runs/20260926_policy_alignment_and_controlled_release_v1/`.

## D-028 - Align policy behavior before refreshing its fingerprints

- Date: 2026-09-26
- Status: superseded in execution by D-029 — the decision held. P10 executed locally; the projection
  was refreshed only AFTER the behavior it certifies was implemented. Deployment remains unauthorized.
- Evidence: current central APPLICATION_WORKFLOW.md adjacent-role clarification; rerun policy-check
  fails for workflow/operating_plan; src/candidate/policy.py refreshes hashes/static mappings and
  contains no call-center rule mapping. Refresh alone would not implement the new preference.
- Decision: bounded implementation and consequence audit, preserving internal software roles and
  current flexible calibration; no new committee. Optional code-only deployment and one live round
  require fresh explicit approval. Backlog applications remain a separate approved-batch workflow.
- Packet: `project-factory/claude_handoff/packets/jprs/JPRS-L2-P10-policy-alignment-and-controlled-release-v01.md`.

## D-027 - Make the durable acceptance point the first write, and make the release checks refuse

- Date: 2026-09-26
- Status: executed locally; `unlock`, review-only. No deployment authorization sought or implied.
- Evidence: `project-factory/outputs/open-market-discovery/runs/20260925_publication_commit_boundary_and_verification_v1/`
  — the P08 reviewer's own two probes run unchanged before and after, a sixteen-boundary fault
  matrix, nineteen release-gate controls, a seven-case preflight drill, and 393 passing tests.
- Decision A, the boundary rather than the key. P08 recorded the debt once, at an aggregate key,
  after every forward-tier write had committed; refusing that single write stranded a posting that
  was already durably normalized. Retrying that key would have repaired the probe and nothing else.
  A feed's owed publication is now its OWN object and the FIRST durable write of that feed's round,
  ahead of `raw/`, `normalized/`, `status/` and the SUCCESS sentinels. Putting it first is what
  makes the acceptance statement decidable rather than a label: nothing durable precedes it, so the
  state "captured but unrecoverable" does not exist. The stated cost is the reverse gap — a failure
  at the snapshot writes can leave a published posting whose raw snapshot is missing for that date,
  which is preferred to an intact audit trail for a posting the report can never show.
- Decision B, per feed rather than per run. One refused write now costs that feed's new batch and
  nothing else. The key is derived from the provider, and the provider list comes from the
  connector registry, so recovery still needs neither `ListBucket` nor `DeleteObject` and no IAM
  change is implied. The aggregate object is retained: it is what the coverage receipt and the
  report read, and it is still read on load so a debt the DEPLOYED code wrote is settled rather
  than orphaned.
- Decision C, compaction rather than eviction. P08's bound dropped the oldest batch above five and
  its own regression required the drop. An accepted observation is owed to the morning report and a
  count of rounds is not a reason to stop owing it — worst of all, the bound ran on `owe`, before
  the drain, so the first healthy round after a backlog evicted the oldest job merely by enqueuing
  its own empty batch. The oldest rounds are now folded into one carry-forward batch with every
  posting preserved; the only bound that removes anything is the live view's own retention horizon,
  and both are reported in the coverage receipt and in `inaccessible`.
- Decision D, evidence at the consumer rather than inference at the checker. The report now states
  `consumed_job_ids` and `below_fit_threshold_job_ids`. P08's live check had read an employer's
  presence in `previously_unseen_employers` as proof that each posting from that employer was
  consumed, and labelled a missing job "below the fit threshold" in a report with zero below-fit
  jobs. An employer-name match is not evidence about a posting.
- Decision E, gates that fail closed. `scripts/check_release_change_set.py` records each check as
  performed-and-passed, performed-and-failed, or NOT PERFORMED, and the third fails like the
  second: an unavailable baseline is an unknown baseline, not a clean one. Rollback verification
  validates the archive before writing anything and refuses to restore over the working tree. The
  forward and rollback sequences are fail-fast scripts rather than command lists, because a list
  cannot fail closed — drilled 7/7 with stubbed tools, never reaching the deploy step.
- Boundary: local only. No deployment, AWS call, invocation, cloud mutation or git mutation. The
  uncommitted overhaul is preserved and P06 remains the running build with its approval spent. The
  local package comparison is named as such and is not an AWS change set. No policy source,
  screening rule or projection was changed.
- Surfaced, not resolved: `policy-check` is RED. Two operator-owned documents outside this
  repository (`APPLICATION_WORKFLOW.md`, `OPERATING_PLAN.md`) were edited on 2026-09-26 and the
  committed projection no longer matches them. Refreshing it is a candidate-policy decision that
  this packet excludes, so the release preflight halts there by design and the choice is the
  operator's.

## D-026 - Preserve P08 gains; finish durable acceptance and discriminating release checks

- Date: 2026-09-25
- Status: accepted for bounded local follow-up; no deployment authorization
- Evidence: P08/ORCHESTRATOR_REVIEW.md and two independent executable probe/result pairs. Original
  live-write control passes and all 350 tests pass, but the first pending-ledger write loses the
  stored role from both later reports. Package and per-job inspector negative controls return false
  clean outcomes. Archived P06 source verifies 36/36.
- Decision: stage P09 under standing obvious-follow-up authority. Complete the finite publication
  failure matrix, prevent owed-job eviction, repair verifier false greens and executable handoff.
  No new committee, policy/provider expansion or packaging redesign.
- Boundary: P08 execution stands; its overall release unlock is not adopted. P06 remains deployed.
  No runtime implementation, cloud actions or git mutation by this review. Seek deployment approval
  only after targeted repair evidence holds.

## D-025 - Owe discovery's observations before publishing them; correct the release claims by measurement

- Date: 2026-09-25
- Status: executed locally; gate `unlock` REVIEW-ONLY; no deployment authorization
- Evidence: P08 run `20260925_durable_discovery_publication_release_repair_v1`. The P07 reviewer's own
  unmodified probe (diff-verified byte-identical) went from losing the captured job on both the same-run
  retry and the following report to matching the uninterrupted control in every field, with the feed
  returning nothing on both later fetches. 350 tests pass (339 before, plus 11 fault-injection cases at
  the real storage boundary). `CHANGE_SET_IS_CODE_ONLY`, `BASELINE_VERIFIED` 36/36 in 6/6 functions,
  `DRILL_PASSED`, `LIVE_CHECK_DISCRIMINATES` 5/5.
- Decision, R1: discovery OWES each touched provider's observations to `discovery/_pending_publication.json`
  before any progress record may claim them published, and DRAINS that ledger one feed at a time, clearing
  a feed's debt only after its view has committed. Replay is exactly idempotent via a per-posting
  `observed_run_ids` ledger, and monotonic in time, so an owed batch cannot duplicate a row, inflate
  observation history, roll back a newer observation or disturb another feed's committed work. Owed
  publication is visible in the coverage receipt, the report JSON, the discovery health axis and the
  rendered report.
- Constraint that shaped the design: the discovery role holds `GetObject`/`PutObject` on `discovery/*`
  and neither `ListBucket` nor `DeleteObject`. So the ledger is ONE object at ONE KNOWN key and clearing
  is a rewrite, not a delete. A prefix-scanning or deleting design would have required an IAM change,
  which R2.1 forbids and which the package-scope stop rule classifies as prohibited.
- Decision, R2: release claims are DERIVED by committed, re-runnable scripts rather than asserted.
  P07's "only two Lambdas change" is replaced — all six artifacts change because every function
  inherits `CodeUri: ../`, and P07's stop rule would have rejected a correct deploy. P07's "copy the
  current files aside" is replaced by a hash-verified P06 baseline archived in-repo, with the restore
  and return drilled. P07's three-step thin-day check is replaced by per-identity disposition
  reconciliation that verifies EMPLOYER identity against the registry.
- Boundaries honored: no deployment, cloud write, invocation, email, application, employer contact,
  SSM or registry edit, new provider, credential, paid call, schedule change, source admission or
  packaging redesign; no git branch, stage, commit, push, reset, stash or checkout. AWS was not
  contacted at all — the permitted bounded read-only baseline retrieval was not needed.
- Qualification: everything is local and mocked. Mocked S3 grants all access, so IAM is established
  only as declared grants read from the real template. Live acceptance is NOT met and must not be
  reported as met. The owed-batch bound (5) and retention bound (21 days) are stated and reported when
  reached, not calibrated. A rollback while a batch is owed abandons those observations, because P06
  never drains the ledger; the receipt names the job ids. Synthetic sample employers are test controls,
  never vacancies.

## D-024 - Retain P07 integration; repair interrupted publication and the release handoff

- Date: 2026-09-25
- Status: accepted for local follow-up; no deployment authorization
- Evidence: P07 ORCHESTRATOR_REVIEW.md. Full suite 339 passes independently; original probe reaches
  a candidate. Controlled external-storage failure before live-view commit leaves a stored observation
  absent from same-run retry and next-day report, while identical uninterrupted inputs retain it.
- Decision: stage P08 under standing follow-up authority for durable/replayable observation publication
  and corrected package-scope, baseline-rollback and discovery-specific live acceptance checks.
- Boundaries: preserve live-view ownership and candidate pipeline; no new committee, provider,
  candidate-policy change, packaging redesign, deployment, invocation or git mutation. Only bounded
  read-only baseline retrieval is permitted if needed. P06 remains the running version.
- Qualification: P07's ordinary path is useful and verified locally; its release gate is not adopted
  until these findings are repaired. Synthetic sample employers are not vacancies or evidence of hiring.

## D-021 - Give discovery its own live view; do not route it through the differ

- Date: 2026-09-25
- Status: accepted; execution complete; **no deployment authorization**
- Context: P07 had to choose who owns a discovered posting's durable candidate representation. Two
  paths were available: extend the differ to diff discovery sources into `current/`, or give
  discovery its own materialized view that report assembly ingests explicitly.
- Decision: **discovery owns a feed-keyed live view** at `discovery/live/provider={p}/live_jobs.json`,
  and `assemble_report_input` merges it into the job population before dedup.
- Rationale: the differ's semantics are built on a property discovery feeds do not have. An ATS board
  returns the employer's ENTIRE open list, so a posting's absence from a healthy snapshot is evidence
  about the posting - that is what the grace clock, mass-drop guard and silent-subset latch rest on.
  A discovery feed returns a moving WINDOW bounded by a page budget, so absence from it is evidence
  about the window. Routing discovery through the differ would have read ordinary feed churn as
  closure. `current/` is additionally differ-owned by the M4 prefix rule, so writing there would have
  widened the differ's blast radius. The chosen path also required no new function, task, schedule or
  IAM grant, because the new object sits in a prefix whose existing ownership already matches exactly
  the one writer and one reader involved.
- Consequences: the discovery lifecycle is explicit and bounded - positive observations only, absence
  never treated as closure, a round whose feed could not be read ages nothing and advances no success
  history, and one stated 21-day retention limit reported as retention. Report assembly gains a second
  population source and states, per feed, whether its postings were observed this round or carried
  from an earlier one. The deployed P06 code neither reads nor writes the new key, so a mixed deploy
  degrades to today's behavior instead of failing.
- Evidence: `project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/VALIDATION.md`
  and its `evidence/` (the P06 reviewer's own probe before and after, the reconciled stage trace, the
  rendered report, 339 passing tests including 23 acceptance cases).

## D-022 - A fetch coordinate is not an identity

- Date: 2026-09-25
- Status: accepted; execution complete; **no deployment authorization**
- Evidence: discovery `source_id` was `provider:{board_token}`, and for a paginated feed the board
  token IS the pagination cursor. The same posting was therefore `himalayas:NEW_TWO#slug` on one run
  and `himalayas:all#slug` on the next. Two P05 tests asserted the cursor-bound form directly.
- Decision: jobs carry the stable FEED id (`provider:all`, the same id `config/discovery_sources.yaml`
  declares and enumerate records in `expected_discovery_sources`). Snapshots keep the coordinate,
  because two pages of one feed are two distinct downloads that must not overwrite each other.
- Consequences: deduplication, first-observation tracking and the previously-reported comparison all
  become correct across pages and days. The two P05 assertions were re-scoped onto real producers and
  their "real internal wiring" section claim withdrawn; P05's own run evidence is left untouched.
  Existing `normalized/` objects keep their old ids and are read by nothing, and no `current/` or
  `events/` record has ever carried a discovery id, so the change has no downstream data migration.

## D-023 - Recover the old report's boundary from what it actually showed

- Date: 2026-09-25
- Status: accepted; execution complete; **no deployment authorization**
- Evidence: the report delivered on 2026-09-25 carries an EMPTY `complete_candidate_list` and its 20
  rows in `top_matches`, with no timing block and no `report_generated_at`. `resolve_run_timing` read
  only the first key, found nothing, discarded the boundary and declared a cold start - so the next
  morning would have re-announced every posting the operator had already read.
- Decision: fall back to `top_matches`, and record BOTH which key the identities came from and that
  the key is capped (`previously_reported_source`, `previously_reported_truncated`).
- Rationale: the recovered set is what that report EVIDENCES - the rows it listed. Recording the cap
  is what stops anything downstream reading it as a complete census of that round's candidates. A
  posting missing from a capped list was not shown to the operator either, which is exactly what "new
  since the last report" asks, so those postings are correctly still new. "New since the last report"
  remains distinct from "posted within 24 hours".
- Consequences: genuine cold start is still distinguished from a recovered boundary, and both are
  asserted. The transition from the old format to the new one is covered end to end.

## D-020 - Repair the producer-to-report connection, not another review cycle

- Date: 2026-09-25
- Status: accepted for local continuation; no deployment authorization
- Evidence: P06 return separates deployed/live collection from zero discovery report candidates.
  Its ORCHESTRATOR_REVIEW.md adds an independent real-handler reproduction: one normalized
  registry-absent job, zero candidate rows, no test-created intermediate state.
- Correction: the earlier orchestrator accepted P05 saved report rows without checking who wrote
  their inputs. Its harness supplied manifest/current objects that production never writes. Those
  conditional tests remain useful; their production-integration inference is withdrawn.
- Decision: stage P07 under the operator's standing obvious-follow-up instruction. Implement a
  minimal candidate ingestion path, preserving existing screening/ranking/history/dedup, stable
  identity, honest feed lifecycle and freshness. Fix the actual old-report fallback alongside it.
  Registry admission is not required; neither raw-feed dumping nor an arbitrary match cap is intended.
- Acceptance: real production producers must create the intermediates consumed by the real saved
  report path. Validate invocation routing and least-privilege reads/writes as well as data flow.
- Consequences: leave P06 running; no rollback or broad committee. P07 stops after local verification
  and a safe deployment handoff. P06's prior deployment approval does not authorize P07 deployment.

## D-019 - P06 deployed under approval; discovery is live but its jobs have no path to the report

- Date: 2026-09-25
- Context: the operator explicitly authorized the controlled deployment of the accepted overhaul to the
  existing jprs-v1 stack, within the P06 packet's scope. Approval was recorded before any cloud mutation.
- Decision (deployment): deploy the reviewed change set only, after reading it. Executed with 6 adds,
  9 non-destructive modifies, 0 removals and 0 replacements. Existing schedules, timezone, registry,
  retained storage and every existing parameter value were preserved; the three email parameters have no
  template default, so they were verified present in the change set before execution rather than assumed.
- Decision (verification): establish live access only through the production Lambda, never a local curl
  surrogate; invoke each provider once rather than retrying for a greener sample; inject no failure into
  production to manufacture resumability evidence; honor existing same-date digest suppression.
- Outcome, kept deliberately separate because no one status implies the rest:
  local repair accepted (P05, prior) / stack DEPLOYED / four keyless sources LIVE-VERIFIED /
  discovered jobs reaching the report NOT ESTABLISHED / cross-round freshness PENDING for 2026-09-26.
- Decision (the finding): STOP rather than wire discovery into the report. The gap is that enumerate
  files discovery ids under `expected_discovery_sources` while the report loads candidate jobs only from
  `expected_sources`, and `current/` is differ-owned with the differ invoked once per `/jprs/companies`
  entry, so no discovery provider has any `current/` state. Closing it means deciding how feed jobs enter
  differ-owned state, what a disappearance event means for a feed that churns daily, how to dedup against
  the monitored boards, and whether hundreds of unscreened postings a day belong in candidate rows. That
  is a design decision, not the "trivial, clearly evidenced launch correction" the packet allows, so it
  is surfaced for a bounded P07 instead of improvised in a deployment run.
- Decision (no rollback): leave the stack deployed. Discovery cannot write `current/` or `events/`, the
  monitored radar is healthy and unchanged, nothing is corrupting, and a rollback would require the P05
  handoff section 6.2 data downgrade for no benefit. Containment was considered and is not warranted.
- Correction to the record: P05's two persisted-report regressions are NOT evidence that discovery
  reaches the report. Their harness wrote `expected_sources` and `current/` for discovery sources, which
  production never does. They remain valid evidence that the traversal repair delivers a recovered job
  into a report GIVEN that wiring. A P07 regression must fail on the production manifest shape instead.
- Second finding: the first post-deploy report read `timing.boundary: cold-start` because the real
  old-format reports carry an empty `complete_candidate_list` (their rows are in `top_matches`) and no
  `timing` block, so the earlier-release id fallback found nothing usable. `cold-start` is an honest
  label rather than a false freshness claim, and it self-corrects from the next round, but P05 handoff
  section 8 overstated that fallback for this system's actual history.
- Status: accepted; deployment complete; gate `revise_implementation` for the product goal
- Evidence: `project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/`
  — `evidence/p06_live_verification_summary.md` (separated claims and the pending check),
  `evidence/p06_live_discovery_coverage.json` (the real coverage receipt),
  `evidence/p06_post_deploy_resources.txt`, `evidence/p06_post_deploy_report_2026-09-25.md`, and
  `evidence/pre_discovery_report_2026-09-25/` (the already-delivered report, preserved before the re-run).
- Consequences: Brett's morning report now carries a truthful discovery COVERAGE line and none of the
  discovered JOBS. Adzuna, general-industry coverage, employer admission and the careers-URL resolver
  remain separate untouched gates. For dt=2026-09-25 only, the stored report is the new-code version
  while the emailed digest was the old code's; they agree from the next round.

## D-018 - Accept P05 local gate and prepare approval-gated deployment

- Date: 2026-09-25
- Status: local repair accepted; P06 staged, deployment approval outstanding
- Evidence: P05 `ORCHESTRATOR_REVIEW.md`; independent 316-test run, unchanged continuation probe,
  target IDs in persisted reports and SAM runtime selection check. No remaining blocker found
  in this bounded verification. Production access remains unobserved.
- Decision: move to controlled deployment, not another generic review. Preparing the follow-up is
  authorized; mutating AWS still requires the operator's explicit deployment approval.
- Qualification: the August baseline ignores discovery state, not all new job data. Its previously
  required data downgrade remains mandatory. Avoid the return's unbounded interruption guarantee.
- Next: use `JPRS-L2-P06-controlled-discovery-deployment-v01` once approval is supplied; preserve
  separate live-source, later scheduled report, Adzuna and source-admission gates.

## D-017 - P05 executed; traversal debt is a first-class fact and deployment is bound to its build

- Date: 2026-09-25
- Context: the independent P04 review reran 296 passing tests, confirmed the location and production
  timing repairs, and reproduced two defects outside the suite plus a budget overrun: a recent range
  went missing after a failed middle page, a newly published range went missing while an older
  continuation was saved, failed attempts did not spend their request, and the forward deploy command
  selected a template that was not the build it had just verified.
- Decision: treat the two traversal findings as ONE defect in the state model rather than two branches
  to patch. An observed timestamp had been read as proof that the intervening range was traversed, so
  separate the two facts: record the recent ranges still OWED (`DiscoveryState.head_pending`, an ordered
  list) as the only thing permitted to say a range was covered, and keep `head_frontier_at` as what it
  honestly is — the newest posting observed on the contiguous chain from page one. Scope the
  already-observed stop to that contiguous chain alone, because it is the only walk whose coverage runs
  unbroken from the newest posting downward; applying it to a resumed chain would discard a continuation
  nothing else records, which is the same silent loss in a new place.
- Deliberately NOT done: no cross-run memory of visited cursors. It would have saved one request at the
  boundary between the recent region and the historical backfill, but it would introduce a new way to
  skip a page silently — the exact defect class under repair. The cost is instead bounded by the head
  budget, drains on its own, and is visible in the saved scenario tables. Also not done: any queue
  framework, any unbounded recrawl, any change to the approved candidate policy, screening or source set.
- Status: accepted; execution complete; gate decision `unlock`; no deployment authorization
- Evidence: `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/VALIDATION.md` and that run's `evidence/` — the reviewer's own probe run unmodified
  before and after, a persisted-scenario driver that serializes state at every run boundary against a
  24-page backlog and drives both scenarios to a persisted candidate report, a deploy-selection probe
  calling the installed SAM CLI's own resolution functions, and a transcript of the new tests run against
  a reconstructed P04 source where 12 of 20 fail. 316 passing tests.
- Consequences: `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/DEPLOYMENT_HANDOFF.md` becomes the handoff of record and the executable
  release instruction; P04's is superseded. A deploy must name `--template-file` and pass an ABSOLUTE
  `--config-file`, because omitting the template selects a nonexistent root template or a stale build
  containing no discovery function, and a relative config path resolves inside the build directory; the
  same correction was applied to `infra/DEPLOY.md` and `START_HERE.md`, which carried the same command.
  The coverage receipt can now report untraversed recent ranges, which means a clean receipt says more
  than it used to. A day with failures will show per-source spend closer to its cap, because a failed
  attempt is no longer free; the cap itself is unchanged. Rolling the discovery source back to P04 while
  keeping its state requires deleting the `head_pending` key, since that model forbids extra fields; the
  `head_cursors` mirror exists so a stripped document still resumes the newest owed range. Production
  transport, authenticated Adzuna, general-industry coverage, the careers-URL resolver live path,
  source-growth admission and the rollback downgrade against real state remain separate, named, unpassed
  gates, and none of them blocks deploying the working keyless paths.

## D-016 - P04 reviewed; stage only the remaining traversal and release-command repair

- Date: 2026-09-25
- Status: repair staged; no deployment authorization
- Evidence: P04 `ORCHESTRATOR_REVIEW.md` and executable independent continuation results.
  296 tests pass; location/report timing now hold. Recent ranges remain silently unvisited after
  a failed middle page or new arrivals during saved continuation. Failed attempts exceed the
  source budget. Installed SAM selects a nonexistent template rather than the stated build.
- Decision: preserve P01–P04 and stage P05 for these specific defects. No runtime changes by the
  reviewer, no screening redesign and no new general review committee.
- Next: after persisted-state/report checks and artifact-selection verification pass, seek
  controlled deployment approval. Live transport, Adzuna and source admission remain distinct.

Record process and path decisions with enough detail to resume without chat history.

## D-007 - Make discovery open-market, not employer-whitelisted

- Date: 2026-09-24
- Status: accepted objective; implementation staged
- Context: The operator rejected treating 15 selected employers as the available job market.
- Decision: Adopt `docs/plans/2026-09-24-open-market-job-discovery.md` as the controlling plan.
  Discover unknown employers across sectors, then monitor validated sources. Preserve central
  candidate policy, retain every credible fit, and report actual coverage limits.
- Consequences: Claude receives one implementation packet. Existing production remains live;
  deployment, registry changes, paid services and credentials require explicit approval.
  This supersedes the fixed one-to-three daily selection instruction, not historical records.

## D-001 - Adopt `project-factory/` as default factory root

- Date: 2026-02-26
- Status: accepted
- Context: Generic orchestrator factory bootstrap requested for the template repo.
- Decision: Use `project-factory/` as the default root with `meta/`, `claude_handoff/`, and `outputs/` subdirectories.
- Consequences: New repos can start with zero-decision defaults and rename later if needed.

## D-002 - Seed template-specific optional lane `template-ops`

- Date: 2026-02-26
- Status: accepted
- Context: This repo is a reusable template with scripts and bootstrap assets beyond pure documents.
- Decision: Add optional lane `template-ops` to the standard lane set in addition to `discovery`, `production`, and `shared-contracts`.
- Consequences: Template maintenance work can remain explicit without overloading `production`.

## D-003 - Seed two canonical artifact roots in outputs registry

- Date: 2026-02-26
- Status: accepted
- Context: The factory scaffold should demonstrate output architecture, status docs, and run directories immediately.
- Decision: Seed `factory-system-bootstrap` and `template-ops-playbook` roots under `project-factory/outputs/` with starter run folders.
- Consequences: Downstream projects get a concrete pattern to copy and adapt.

## D-004 - Default the factory role to Orchestrator / control plane

- Date: 2026-03-14
- Status: accepted
- Context: The template needs a clearer default that preserves sequencing, delegation, and recovery.
- Decision: Treat the Orchestrator as the default control plane rather than the default primary implementer. Direct coding is an explicit exception, not the silent default.
- Consequences: Meaningful implementation work should usually move through bounded packets instead of vague continuation.

## D-005 - Adopt explicit state resolution and continuity surfaces

- Date: 2026-03-14
- Status: accepted
- Context: Recovery after context loss needs a clear answer for what to trust first.
- Decision: Resolve conflicting files in this order: completed artifacts/run results, current status trackers, roadmap/timeline, then bootstrap/summary docs. Maintain `SESSION_STATUS.md`, `PHASE_LEDGER.md`, `EXECUTION_TIMELINE.md`, and this decision log as the minimum control-plane recovery surfaces.
- Consequences: Lower-priority summaries must be updated when higher-priority state changes.

## D-006 - Standardize task states and packet fields

- Date: 2026-03-14
- Status: accepted
- Context: Work drift and ambiguous "continue later" states make delegation and recovery harder than necessary.
- Decision: Use the standard task states `planned`, `staged`, `in_progress`, `blocked`, `completed`, `parked`, and `closed`. Require packets to include objective, scope, expected outputs, acceptance condition, stop condition, and exact target surfaces/files.
- Consequences: Status trackers and handoff packets become more legible and easier to resume.

## D-012 - Qualify P01 readiness after independent return review

- Date: 2026-09-24
- Status: accepted as orchestrator review; not a deployment authorization
- Evidence: P01 `ORCHESTRATOR_REVIEW.md`, 168 independently rerun passing tests, and isolated
  runtime/screening/CLI probes reproducing four untested defects.
- Decision: preserve the implementation and stage P02 for Adzuna wiring, pagination, exclusion
  semantics and deployment/rollback repair. Do not adopt the earlier deploy-only next step.
- Consequence: research and qualitative company assessment remain downstream in Career Factory;
  no new candidate vetoes, architecture committee, or AWS writes are authorized.

## D-007 - Employer is a property of the job, not of the source

- Date: 2026-09-24
- Status: accepted
- Context: `source_id` was `provider:board_token` and the employer was implied by the source, with a hardcoded 15-entry company-label table in the report. A source keyed by an employer can only ever answer "what is open at THIS employer", so a posting from a company nobody had named could not arrive — not because the roster was small, but by construction.
- Decision: Move `employer_name` onto `CanonicalJob` and delete the label table. Split sources into `ATS_BOARD` (monitoring, one known employer) and `DISCOVERY_FEED` (employer-independent, many unknown employers), carried through the manifest as `source_kinds`.
- Consequences: Discovery and monitoring share one pipeline, one manifest, one freeze invariant and one IAM prefix split. Measured the same day, employers reaching the system that are absent from the registry went from 0 to 161.

## D-008 - Discovery queries may never name an employer, enforced in code

- Date: 2026-09-24
- Status: accepted
- Context: The moment a company name enters a query, the result can only confirm a company somebody already thought of. That is the failure being removed, and a comment would not prevent its return.
- Decision: `assert_company_independent` refuses any query phrase containing a known employer, checked against normalized forms so casing, punctuation and legal suffixes cannot smuggle one through. The held-out acceptance test asserts the property over the whole query plan.
- Consequences: A future edit that turns discovery back into a lookup fails the test suite rather than quietly shipping.

## D-009 - The silent-subset guard is corroboration-bounded, not latching

- Date: 2026-09-24
- Status: accepted
- Context: A vanished department and a silently truncated feed produce a byte-identical signature. Suppressing removals forever froze a real closure's postings ACTIVE indefinitely and reprinted a warning that said "low count" when the actual condition was "missing segment".
- Decision: Keep indefinite suppression for mass-drop and cumulative-bleed, which genuinely cannot be distinguished from truncation. For the segment guard, hold removals while ambiguous, track a per-segment absence streak, and reclassify to confirmed closure after N independent healthy SUCCESS snapshots. Warnings state the observed condition and the streak.
- Consequences: Real closures recover on their own; truncation protection is unchanged. Tests cover both directions.

## D-010 - Only reviewed application-history entries may suppress a posting

- Date: 2026-09-24
- Status: accepted
- Context: The history lives in three successive markdown formats of freeform prose. A regex scanner was built and compared against a careful independent read; it mis-assigned statuses in both directions. A false SUBMITTED hides a live opportunity, while a false PREPARED only files a row in the wrong section — the harm is asymmetric.
- Decision: The committed projection holds `reviewed` entries, each with a quoted line of evidence, and only those may carry SUBMITTED/REJECTED/SKIPPED. Scanner output is capped at PREPARED by `enforce_confidence_cap`. Contradictory records keep the weaker status and surface the conflict rather than being resolved.
- Consequences: The scanner's job becomes drift detection. A parser error can no longer hide an opening.

## D-011 - Runtime-learned URLs go through a fetch guard, not the build-time allowlist

- Date: 2026-09-24
- Status: accepted
- Context: Monitoring only ever touched four vetted ATS hosts, so a static allowlist was a complete defense. Discovery learns URLs at runtime from untrusted feeds, which breaks that assumption.
- Decision: Keep the allowlist for build-time-vetted provider hosts. Route every runtime-learned URL through `fetch_guard`, which validates scheme, credentials, port and every RESOLVED address against private/loopback/link-local/CGNAT/reserved ranges, refuses cross-host and scheme-downgrading redirects, and caps response size on bytes actually transferred. Job text is data and is never interpreted as instructions.
- Consequences: Source growth and unsupported careers pages are reachable without opening an SSRF path. Sixteen tests cover the refusals, including cloud metadata and DNS-rebinding shapes.

## D-013 - Qualify P02 release readiness and retain fresh-first intent

- Date: 2026-09-24
- Status: accepted for local continuation; no deployment authorization
- Evidence: P02 run `ORCHESTRATOR_REVIEW.md` and its executable offline probes. Independent suite
  rerun: 209 pass, but actual HTTP drops injected credentials, mixed/optional screening fails and
  the baseline reader rejects current records. Historical executor unlock is not adopted.
- Operator preference: morning rounds prioritize genuinely fresh credible openings, ideally within
  24 hours. This is not a rejection cutoff. Preserve catch-up, older strong fits, date provenance,
  unknown ages and source lag. A pagination backlog must not prevent prompt new-head checks.
- Decision: retain the useful implementation and stage one bounded P03 continuation. No new
  committee, rebuild, candidate-policy edits, schedule changes, AWS actions or paid access.
- Consequences: P02 execution is complete but acceptance needs repair. Re-review after P03 before
  deployment. Real authenticated Adzuna and production transport remain distinct later gates.

## D-014 - P03 executed; release remains review-qualified

- Date: 2026-09-24
- Status: local repair staged; no deployment authorization
- Evidence: P03 `ORCHESTRATOR_REVIEW.md` and its independent mocked-boundary reproductions.
  Full suite independently passes 252 tests; earlier HTTP/polarity repairs hold. Three new defects
  still undermine candidate eligibility and timely discovery/reporting.
- Decision: preserve P01–P03 and stage P04 for location semantics, production report timing,
  recent-page continuation and live handoff/status reconciliation. No new committee or rebuild.
- Consequences: actual worksite/residence and the central commute policy control, not a guessed
  town list. Production-wired reports and multi-page new arrivals must pass before a deployment
  recommendation. Real-provider and deployment gates remain separate. No runtime changes by review.

## D-015 - P04 executed; the three open boundaries are repaired and deployment is the operator's call

- Date: 2026-09-24
- Context: the independent P03 review reran 252 passing tests, confirmed the earlier transport and
  screening-polarity repairs, and reproduced three defects outside the suite: location filtering
  contradicting the commute policy, the production report never receiving its freshness timing, and
  new arrivals on page two waiting behind the historical backlog.
- Decision: repair all three at the boundaries where they actually failed, reproducing each against
  the reviewer's own unmodified probe first. Answer the location policy by its MEANING rather than by
  a hand-written town list: resolve the state boundary (a verifiable fact — no out-of-state worksite
  is a 30-minute drive from Laconia), honor the cities the operator named, and leave every in-state
  distance question unresolved and visible for confirmation instead of certifying a drive time the
  system cannot measure. Decide freshness by IDENTITY — which postings the previous report showed —
  rather than by comparing timestamps across stages that do not share a clock.
- Status: accepted; execution complete; no deployment authorization
- Evidence: `project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/VALIDATION.md`, `project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/evidence/` (pre- and post-repair runs of the reviewer's
  probe, a production-shaped report-boundary probe, and a two-round rehearsal over real captured
  provider payloads), 296 passing tests.
- Consequences: `project-factory/outputs/open-market-discovery/runs/20260924_location_and_freshness_boundaries_v1/DEPLOYMENT_HANDOFF.md` becomes the handoff of record and corrects P03's
  self-contradiction about rollback data compatibility — the baseline rejects 18 fields, so the data
  downgrade is REQUIRED, not optional — and makes the rollback order and writer quiescence explicit.
  A New Hampshire onsite posting now reaches the operator as a worksite question rather than a
  verdict; that is the deliberate cost of not inventing a measurement. Production transport,
  authenticated Adzuna, the careers-URL resolver live path and the rollback downgrade against real
  state remain separate, named, unpassed gates.
