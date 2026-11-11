# VALIDATION — P05 resumable discovery and release binding

Run: `20260925_resumable_discovery_release_repair_v1` · Packet:
`JPRS-L2-P05-resumable-discovery-release-repair-v01`

Provenance labels are used throughout: `evidence` (something was executed and its output is saved
here), `inference` (a conclusion drawn from evidence), `speculation`, `operator_preference`.

**What was not done, and so is not claimed:** no deploy, no AWS call, no SSM read or write, no
credential, no network request, no email, no commit, branch, stage, reset or push. Every result below
comes from local execution against mocked transport and mocked S3, or from calling the installed SAM
CLI's own resolution functions. That is the boundary the packet set, and it is also the ceiling on what
these results can mean: **production transport remains unverified** (DEPLOYMENT_HANDOFF §3.4).

---

## 0. Reproduce first, then repair

`evidence` — The P04 independent probe was run **unmodified** before any runtime edit
(`evidence/p05_before_repair_p04_probe.json`). Both of the review's scenarios reproduced exactly as
`ORCHESTRATOR_REVIEW.md` described:

| | before repair | after repair |
|---|---|---|
| scenario one — failed recent page: fresh job missing | `true` | `false` |
| scenario one — attempts exceeded the budget of 3 | `true` (4 requests) | `false` (3 requests) |
| scenario two — new burst above a saved continuation: fresh job missing | `true` | `false` |

After: `evidence/p05_after_repair_p04_probe.json`. The requested-cursor logs show what changed:

```
scenario one   before   run 1 [null, NEW_TWO, OLD, OLD_1]   run 2 [null, OLD_2, OLD_3]
               after    run 1 [null, NEW_TWO, OLD]          run 2 [null, NEW_TWO, OLD_1]
scenario two   before   run 2 [null, B3, OLD_1]             (NEWER_TWO never requested)
               after    run 2 [null, NEWER_TWO, OLD_1]
```

`evidence` — Baseline before editing: 296 tests passed, matching the P04 review's independent count.

---

## 1. The defect, as a transition-model problem rather than two branches

`inference` — Both scenarios were one confusion in the state model: **an observed timestamp was being
read as proof that the intervening range had been traversed.** The model had a place to record what it
had *seen* (`head_frontier_at`) and one slot to record where it had *stopped* (`head_cursors`), and
nothing that recorded what it still *owed*.

Three consequences followed mechanically, and patching either branch alone would have left the third:

1. `_walk` returned one position plus a stop reason. The caller saved a continuation **only** for the
   reason `budget`. A page that raised returned `error`, and the range was dropped.
2. `head_frontier_at` advanced from whatever pages did load, including on the run where a page failed.
   The next run then stopped at page one, believing it had covered ground it had never walked.
3. One slot cannot hold two owed ranges. When the provider published new pages above a saved
   continuation, the saved cursor **overrode** the provider's new continuation link, so the newly
   published range was never requested — and then the advancing frontier hid it too.

### The repair

`evidence` (`src/discovery/budget.py`, `src/discovery/handler.py`)

- **Observation and traversal debt are now separate facts.** `head_pending[provider]` is an ordered
  list of recent cursor ranges known to be **untraversed**. `head_frontier_at` remains what it honestly
  is — the newest posting observed on the contiguous chain from page one — and no longer implies
  coverage of anything in `head_pending`.
- **One worklist-driven walk.** Page one always leads (first-page priority, unchanged). Each page's own
  continuation is followed before older owed ranges, which is newest-first because the feed is
  descending. Anything not traversed — a page that raised, a page that came back `PARTIAL`, or a range
  the budget never reached — is returned as debt and saved.
- **The frontier stop applies only to the contiguous chain from page one.** `inference`, and it is the
  subtlest part of the repair: that chain runs unbroken from the newest posting downward, so reaching
  already-observed ground really does mean the rest was read. A chain *resumed* from an owed range
  carries no such guarantee, and stopping it at the frontier would discard a continuation that nothing
  else records — the same silent loss in a new place. Resumed chains still end at the recent-time
  horizon, the backfill's position, the feed end, or a repeated cursor, so they stay bounded: no
  recrawl, no unlimited queue.
- **Every outbound attempt is charged before it is made**, and each walk is additionally bounded by the
  source budget's remaining allowance rather than by its own slice alone.
- **Persisted state is bounded.** `HEAD_PENDING_MAX = 24` owed ranges per source; anything dropped at
  the cap is reported as partial coverage rather than vanishing.
- **`head_cursors` is kept as a derived mirror** of the newest owed range, written in exactly one
  place. It is the only field an older reader understands (§5).

`inference` — What the repair deliberately does **not** claim: it does not promise every posting within
24 hours regardless of provider or budget. It promises prompt prioritized discovery with **no silent
loss** — if work exceeds capacity, what remains is shown and stays resumable.

`inference` — One honest cost, measured rather than hidden. When a recovered recent page's own
continuation turns out to be historical ground, learning that costs one request, once, and then the
range drains (a page holding nothing recent ends its chain). Visible in the scenario tables below as
the `owed: ['OLD']` step. Bounded, self-draining, and not a loss.

---

## 2. Regressions: written to fail on P04, measured to fail on P04

`evidence` — `tests/test_resumable_discovery_and_release_binding.py`, 20 tests, all passing on the
repaired tree. To make "these fail on P04" a measurement rather than a claim, the repository was copied
to a scratch directory, the P05 changes to the two source files were reverted there (each of the ten
reverts asserted), and module origin was verified to be the scratch copy. Method:
`evidence/p05_p04_reconstruction_method.py`. Result:
`evidence/p05_new_tests_against_p04_source.txt`.

- The unmodified P04 probe reproduces both defects against the reconstruction, so the reconstruction is
  faithful.
- The pre-existing suite passes against it (291), except five `test_r4_*` tests that shell out to
  `git show e549a73:...` and fail only because the scratch copy has no `.git`. A scratch artifact, not a
  code result; they pass in the working tree.
- **12 of the 20 new tests fail on the P04 source**, including every load-bearing one: both review
  scenarios, both persisted-report scenarios, the partial-download case, repeated resumptions, the
  attempted-request budget, and the budget bound at 3, 5 and 8.
- The remaining 8 pass on P04 because they guard behaviour P04 already had right — an unchanged head
  spending one page, a repeated cursor stopping the walk, a P04 state document resuming, the descending
  timestamp cursor contract, first-seen preservation, and the budget bound at 1 and 2. Stating that
  plainly matters: a file where every test failed on the old code would mean the preserved behaviour
  was not being guarded at all.

What the new tests cover, and why each is shaped that way:

| Concern the packet named | Test | Shape that makes it real |
|---|---|---|
| failed middle page | `test_a_failed_recent_page_is_owed_not_erased_by_the_frontier_it_advanced` | 24-page backlog, state round-tripped, asserts the backfill never rewinds |
| partial middle page | `test_a_partially_downloaded_recent_page_is_owed_like_a_failed_one` | truncated body, so the snapshot lands `PARTIAL` rather than raising |
| saved continuation + new multi-page burst | `test_newly_published_pages_are_not_overridden_by_a_saved_continuation` | asserts **both** ranges remain owed, so neither overwrote the other |
| multiple resumptions, eventual collection | `test_repeated_resumptions_eventually_collect_every_reachable_recent_posting` | five burst pages under a two-page head budget; asserts honest incomplete reporting on every incomplete run |
| unchanged head | `test_an_unchanged_head_owes_nothing_and_spends_one_page_on_it` | guards against the repair turning every run into a re-walk |
| attempted-request budget | `test_a_fetch_that_raises_still_spends_its_request` | the exact 4-under-3 measurement from the review |
| budget exhaustion | `test_the_source_budget_bounds_every_attempt_including_failures` | budgets 1/2/3/5/8 × 4 runs, failures in the mix |
| repeated cursors | `test_a_repeated_cursor_is_reported_and_does_not_become_an_owed_range` | also asserts a looping cursor cannot grow persisted state |
| old-state readability | `test_a_p04_state_document_resumes_its_saved_range` | a literal P04-shaped document |
| rollback readability | `test_the_compatibility_mirror_tracks_the_newest_owed_range` | drops the new key, as a downgrade would |
| bounded state | `test_owed_ranges_stay_bounded_and_say_what_was_dropped` | asserts the drop is returned for reporting |
| timestamp cursor contract | `test_the_cursor_contract_is_a_descending_timestamp_and_the_backfill_only_moves_older` | real base64 `<ISO>|<id>` cursor shape, decoded and ordered |
| dedup / first-seen history | `test_first_seen_history_survives_the_head_re_reading_page_one` | the head re-reads page one every run |
| reaching the operator | `test_the_recovered_*_page_reaches_the_persisted_report` | real report handler, mocked S3, asserts by job id |
| deploy binding | `test_the_documented_deploy_commands_bind_template_and_config_explicitly` | parses the handoff's own commands, continuations joined |

---

## 3. The two scenarios reach a persisted candidate report

`evidence` — `evidence/p05_persisted_scenario_driver.py`, results in
`evidence/p05_persisted_scenario_results.json`, persisted reports under `reports/`. Real discovery
walk, real state serialization at every run boundary, real screening, scoring, dedup and report
handler; mocked HTTP transport and mocked S3. Exit code 0, all five assertions true.

Scenario one — a recent page times out while a 24-page backlog stays open:

| run | cursors requested | requests / budget | owed after | backfill | target in persisted report |
|---|---|---|---|---|---|
| 1 | `page1, NEW_TWO, OLD` | 3 / 3 | `[NEW_TWO]` | `OLD_1` | no |
| 2 | `page1, NEW_TWO, OLD_1` | 3 / 3 | `[OLD]` | `OLD_2` | **yes** |
| 3 | `page1, OLD, OLD_2` | 3 / 3 | `[]` | `OLD_3` | yes |

Scenario two — two newer pages arrive above a saved continuation:

| run | cursors requested | requests / budget | owed after | backfill | target in persisted report |
|---|---|---|---|---|---|
| 1 | `page1, B2, OLD` | 3 / 3 | `[B3]` | `OLD_1` | no |
| 2 | `page1, NEWER_TWO, OLD_1` | 3 / 3 | `[B2, B3]` | `OLD_2` | **yes** |
| 3 | `page1, B2, OLD_2` | 3 / 3 | `[B3]` | `OLD_3` | yes |
| 4 | `page1, B3, OLD_3` | 3 / 3 | `[OLD]` | `OLD_4` | yes |
| 5 | `page1, OLD, OLD_4` | 3 / 3 | `[]` | `OLD_5` | yes |

`evidence` — In both scenarios the formerly-lost posting reaches the **persisted** report on run two;
every run stays within its source budget; the historical backfill advances monotonically and never
rewinds; and the owed list drains to empty. While incomplete, each run reports
`himalayas recent arrivals` with a count of untraversed ranges rather than reporting clean coverage.

`inference` — Scenario two's runs 3–5 are the honest cost of not keeping a cross-run memory of visited
cursors: the walk re-reads one junction page to discover where the recent region ends. It was a
deliberate choice — such a memory would introduce a new way to skip a page silently, which is the
defect class under repair — and the cost is bounded by the head budget and drains on its own.

---

## 4. Deployment now selects the build that was verified

`evidence` — `evidence/p05_deploy_selection_probe.py` /
`evidence/p05_deploy_selection_results.json`, exit code 0, all five assertions true. It calls the
installed SAM CLI's own `get_or_default_template_file_name` and mirrors its samconfig join. No deploy,
no AWS call, no credential; the stale-build case is simulated in a temporary directory so the hazard is
never created in the real tree.

| command | resolves to | verdict |
|---|---|---|
| P04's, from the repo root | `<repo>/template.yml` | **does not exist** |
| P04's, run from `infra/` | `infra/.aws-sam/build/template.yaml` | **a stale 2026-08-01 build with zero `DiscoveryFunction`** |
| P04's, in a tree with a default build | `.aws-sam/build/template.yaml` | silently selects the stale build |
| P05's, `--template-file "$BUILD/template.yaml"` | exactly that path | **selects the verified build** |

`evidence` — The second trap, behind the first: SAM sets its samconfig search directory to the
directory of the template it is given, so with the template in a build directory a relative
`--config-file infra/samconfig.toml` resolves to `<build-dir>/infra/samconfig.toml`, which does not
exist. The absolute form resolves to the repository's config. Both were checked against the **real**
built template, not only a stand-in.

`evidence` — `sam validate --lint` passes; `sam build` into a fresh build directory succeeds and its
template contains `DiscoveryFunction` (8 occurrences) while the stale `infra/.aws-sam` build contains
0 (`evidence/p05_sam_validate_build.txt`). That is the concrete difference the unbound command could
have shipped.

`evidence` — Corrected in three places so the fix cannot rot back out of prose: this run's
`DEPLOYMENT_HANDOFF.md` §4 and §6.3, `infra/DEPLOY.md` (the document `CLAUDE.md` requires reading
before any deploy, and which carried the same unbound `sam deploy --config-file infra/samconfig.toml`
and a `--template-file .aws-sam/build/template.yaml` that points at a stale path), and a test that
parses the handoff's own commands.

`evidence` — The quiesce → data downgrade → source rollback → resume ordering and the non-destructive
`git worktree` method are preserved unchanged; the rollback deploy gained the same explicit binding for
the same reason, verified by the same probe.

---

## 5. Existing-data reconciliation

`evidence` — `DiscoveryState` gains one field, `head_pending`, defaulting to empty.

- Forward (a P04 state document read by P05 code): `head_pending` is absent, so the single
  `head_cursors` value is read as the one range still owed. Nothing is lost. Test:
  `test_a_p04_state_document_resumes_its_saved_range`.
- Backward (a P05 document read by P04 code): P04's model uses `extra="forbid"` and would **reject** a
  document containing `head_pending`. A rollback that keeps discovery state must delete that key;
  `head_cursors` is written as a mirror of the newest owed range precisely so a stripped document still
  resumes the most important range instead of none. Test:
  `test_the_compatibility_mirror_tracks_the_newest_owed_range`. Documented in DEPLOYMENT_HANDOFF §6.2.
- Rolling back to the `e549a73` baseline needs neither step: that code never reads `discovery/`. The
  §6.2 downgrade set is therefore **unchanged** from P03's, and the P03 claim that the additive
  `current/` fields are "ignored by the old code" stays withdrawn.
- `SCHEMA_VERSION` stays 1.1.0, additive only. No `CanonicalJob` field was added. The report JSON is
  unchanged.

---

## 6. Full check results

`evidence`, transcript in `evidence/p05_test_transcript.txt`:

| check | before this run | after |
|---|---|---|
| full suite | 296 passed | **316 passed** |
| new P05 regressions | did not exist | 20 passed (12 fail on P04 source) |
| P04 location / freshness / pagination boundaries | 44 passed | 44 passed |
| runtime boundary, release repair, recall, discovery | 130 passed | 130 passed |
| policy projection check | — | `projection matches all policy sources` |
| `sam validate --lint` | valid | valid |
| `sam build` | succeeded | succeeded, `DiscoveryFunction` present |
| P04 independent continuation probe | 2 jobs lost, budget exceeded | 0 lost, budget honoured |
| deploy/rollback template + config selection | selects a nonexistent or stale template | selects the verified build |

`evidence` — Preserved regressions specifically re-confirmed: the Adzuna credential path, screening
polarity, the location rules including the Belmont punctuation and Alton IL cases, production report
timing from `manifest.opened_at`, and the rollback data-downgrade tests.

---

## 7. What this run does not establish

`evidence`/`inference` as marked:

- Production HTTP transport is still unverified, for the reason P04 measured (non-deterministic
  truncation from this machine). Everything here replays payloads through the real pipeline with the
  transport mocked. `evidence`
- The repair's behaviour under a *real* interrupted production day is inferred from persisted-state
  reproductions, not observed. The first production day that actually fails a page is that evidence.
  `inference`
- Authenticated Adzuna, general-industry coverage, the careers-URL resolver's live path, and source
  admission remain separate open gates. None is a prerequisite for truthfully deploying the working
  keyless discovery paths. `evidence`
- The drive-time interpretation remains deliberately unresolved in state and still needs the operator.
  `operator_preference`
