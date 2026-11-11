# gate_decision — P05 resumable discovery and release binding

Stage: implementation and local validation · Packet:
`JPRS-L2-P05-resumable-discovery-release-repair-v01` · Run:
`20260925_resumable_discovery_release_repair_v1` · Date: 2026-09-25

## Outcome

**`unlock`** — for the one thing this gate governs: the bounded local repairs are complete, the two
review scenarios are closed under persisted multi-run state, and deployment is bound to the artifact
that was actually verified. The recommended next action is **operator-approved controlled deployment
with live HTTP checks.**

What `unlock` does *not* mean here, stated because the packet's acceptance clause is explicit that
passing tests are not sufficient: it does not mean production-ready in the sense of verified in
production. Production transport, authenticated Adzuna, general-industry coverage, the careers-URL
resolver's live path and the rollback downgrade against real state remain open and separately named.
This gate unlocks the deployment *decision*, not the gates that only a real run can close.

## Outputs reviewed

- `VALIDATION.md` — before/after evidence, the transition-model reasoning, the full check table
- `DEPLOYMENT_HANDOFF.md` — corrected forward and rollback command binding
- `checkpoint.md`, `run_manifest.json`
- `evidence/` — nine artifacts: the before and after P04 probes, the persisted-scenario driver and
  results, the deploy-selection probe and results, the P04-source regression transcript with its
  reconstruction method, the test transcript, the SAM validate/build transcript, the policy check
- `reports/` — eight persisted daily reports across the two scenarios, with per-run state
- `src/discovery/budget.py`, `src/discovery/handler.py`,
  `tests/test_resumable_discovery_and_release_binding.py`, `infra/DEPLOY.md`, `START_HERE.md`,
  `docs/plans/2026-09-25-resumable-discovery-release-repair.md`

## Evidence and support quality

Rationale rather than a numeric score, per `QUALITY_GATES.md`: this is a defect-closure gate with
binary acceptance conditions, not a creative output needing a weighted rubric.

| Acceptance condition from the packet | Result | Support |
|---|---|---|
| Both formerly missed jobs accounted for under **persisted multi-run** state | met | `evidence/p05_after_repair_p04_probe.json`; `evidence/p05_persisted_scenario_results.json` (state serialized and reloaded at every run boundary) |
| Both reach a **persisted candidate report** through mocked services, production internal wiring real | met | `reports/**/daily_report.json` written by the real report handler; asserted by job id, not by employer string |
| A pending recent range survives a failure, a later head read, and replacement by another range | met | `test_a_failed_recent_page_is_owed_not_erased_by_the_frontier_it_advanced`, `test_newly_published_pages_are_not_overridden_by_a_saved_continuation` |
| New pages ahead of a saved continuation remain reachable | met | scenario two reaches the new range on run two; both ranges stay owed |
| **All** outbound attempts charged, including exceptions and partial responses | met | `test_a_fetch_that_raises_still_spends_its_request`; `test_a_partially_downloaded_recent_page_is_owed_like_a_failed_one`; budget bound asserted at 1/2/3/5/8 across repeated runs |
| First-page priority and bounded historical progress preserved | met | page one leads every run; the backfill advances monotonically and never rewinds in either scenario |
| Remaining work shown and resumable when capacity is exceeded | met | `himalayas recent arrivals` reported with a count on every incomplete run |
| Serialized round trips, repeated invocations, backlog long enough to prevent accidental restart | met | 24-page backlog throughout; every run boundary round-trips state |
| Eventual collection proven within finite capacity; honest pending coverage while incomplete | met | owed list drains to empty in both scenarios; incomplete runs report incompleteness |
| Dedup / first-seen history and old-state readability preserved | met | `test_first_seen_history_survives_the_head_re_reading_page_one`; `test_a_p04_state_document_resumes_its_saved_range` |
| Regression tests that **fail on P04**, including the budget failure | met | 12 of 20 fail against a reconstructed P04 source; `evidence/p05_new_tests_against_p04_source.txt` |
| Template and config paths unambiguously select the verified build, independent of stale defaults | met | `evidence/p05_deploy_selection_results.json`, exit 0, five assertions true, checked against the real built template |
| Forward **and rollback** selections checked, not just prose | met | both commands resolved through SAM's own functions; the handoff's own commands are parsed by a test |
| Quiesce → downgrade → rollback → resume ordering and non-destructive worktree preserved | met | `DEPLOYMENT_HANDOFF.md` §6.0–§6.3 unchanged in ordering; rollback gained the same explicit binding |
| No network, AWS, credential, deploy, commit or staging | met | `git status` untouched; no AWS call in any artifact |
| One coherent repair, not implement-then-review-as-a-second-pass | met | reproduce → design the transition model → repair → validate, in one pass; the P04-source comparison is a measurement of the delivered tests, not a second review round |

## Top risks

1. **Production transport is still unverified.** P04 measured non-deterministic truncation from this
   machine, so no local run exercises the real wire. P05 makes that failure resumable as well as
   visible, but the first scheduled Lambda run is the only evidence. Watch `discovery_succeeded` and
   `inaccessible` on day one.
2. **Backward state compatibility is deliberately one-directional.** A rollback of the discovery source
   to P04 that keeps its state must delete the `head_pending` key, because P04's model forbids extra
   fields. Documented in `DEPLOYMENT_HANDOFF.md` §6.2 with a regression; a rollback to the `e549a73`
   baseline is unaffected.
3. **Recovery can spend one extra request at the recent/historical boundary.** Bounded by the head
   budget and self-draining, but a day with failures will show spend closer to the per-source cap. The
   cap itself is asserted and unchanged.

## Recommended next action

Request operator approval for a controlled deployment following this run's `DEPLOYMENT_HANDOFF.md` §4
verbatim, then run the §5 post-deploy acceptance checks — including the new check 6, that owed recent
ranges are reported rather than hidden. Do **not** open another broad review by default; the two
scenarios this gate governs are closed with executable evidence, and the remaining gates are the kind
only a live run can close.
