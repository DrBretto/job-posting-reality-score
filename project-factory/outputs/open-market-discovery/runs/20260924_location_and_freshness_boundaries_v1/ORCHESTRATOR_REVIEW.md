# P04 independent return review

Date: 2026-09-25. Action: run-return / evidence / bounded handoff.

## Decision

**Execution completed; release acceptance not met.** Keep the implementation. The location and
production timing reproductions now pass. Recent-page continuation still loses work across runs,
and the forward deployment command is not bound to its stated build. Stage P05 for those repairs,
not a general fourth committee or a new discovery design. No runtime changes made in this review.
No deployment, cloud mutation, commit, branch, reset or staging.

This review qualifies, but does not overwrite, the executor's gate, manifest, return or evidence.

## Checks that hold

- Evidence: independently reran the full suite: **296 passed in 4.20s**.
- Evidence: reran the P03 independent probe unmodified. Belmont with/without punctuation is pending
  worksite confirmation; Alton IL, required Boston attendance and CA/NY-only residency are excluded.
  Its original fresh-page-two fixture now reaches page two and continues historical work.
- Evidence: reran P04's production-shaped two-round report probe. The real report handler persists
  `manifest.opened_at`, the prior report's IDs, two genuinely new-to-us rows and the same previous
  boundary on retry. The earlier P03 probe wrote `created_at`/`run_started_at` rather than the actual
  manifest's `opened_at`; its remaining zero result exercises the labelled fallback, not a remaining
  production-wiring defect. The review must not demand that production obey an invented fixture.
- Evidence: the revised rollback instructions recognize strict old readers, require data downgrade,
  quiesce writers first and preserve the uncommitted tree. This is a document/local-evidence check,
  not a production rollback rehearsal.

## R1 — incomplete recent ranges can become invisible

Evidence: `evidence/p04_independent_continuation_probe.py` runs the real connector and discovery
logic against synthetic provider-shaped payloads. Only the external fetch boundary is replaced.
Results are saved beside it as `p04_independent_continuation_results.json`.

### Failure while the historical backlog remains open

With budget 3, the first run requests `head, NEW_TWO, OLD, OLD_1`. `NEW_TWO` times out. The saved
recent cursor is null, but the head frontier advances to the first page's newest publication time.
The next successful run requests `head, OLD_2, OLD_3`. It neither retries nor collects the fresh job
on `NEW_TWO`. The historical walk moves farther away from that page.

Mechanism: the exception path returns a failed cursor, but the caller saves only budget exhaustion;
it then advances `head_frontier_at` from observed page timestamps despite the unresolved range.

The existing failed-page test has a short backlog: its unknown deep cursor becomes a fabricated
end-of-feed page. Backfill therefore exhausts on the first run, clearing the cursor and making the
next run restart a complete walk. That masks failure under the intended long-running backlog.

### New arrivals while an older recent continuation is pending

Run one requests `head, B2, OLD` and saves `B3`. Before run two, two newer pages arrive. Run two
requests `head, B3, OLD_1`, overriding the provider's new `NEWER_TWO` link with saved `B3`. Run three
requests `head, OLD_2, OLD_3`. The job on `NEWER_TWO` is missing in both runs.

Mechanism: one saved recent continuation replaces the newly returned head continuation; the new
frontier subsequently treats that unvisited range as covered. The current overflow test inserts no
new pages between runs, so it cannot detect this interaction.

Related budget defect in the same reproduction: 4 fetch attempts occur with budget 3 because a
raised fetch does not consume the attempt/page accounting. A bounded request budget must include
attempts that fail, not just completed downloads.

Inference: a successful latest-page read does not establish contiguous coverage. Preserve incomplete
ranges and represent observation separately from completed traversal. Choose a small repair, but
validate sequential state transitions, not only one-day examples. No unbounded crawl is requested.

## R2 — deployment instructions select the wrong template

Evidence: P04 `DEPLOYMENT_HANDOFF.md` section 4 builds with `--build-dir /tmp/jprs-build`, then
invokes deploy without `--template-file`. `infra/samconfig.toml` provides no deploy template override.
The installed SAM 1.137.1 deploy command uses `template_click_option(include_build=True)`; its
`get_or_default_template_file_name` searches the default build and root template locations, not
`/tmp/jprs-build`. Calling that selection function locally, without invoking deploy or AWS, returns
`/Users/drbretto/Desktop/Projects/job-posting-reality-score/template.yml`, which does not exist.

Inference: following the handoff fails locally; in a checkout with a stale default build it could
select that build instead. Bind forward deployment to the exact verified built template and use an
unambiguous config path. Validate selection locally, not by running a cloud command.

## Next bounded step

`project-factory/claude_handoff/packets/jprs/JPRS-L2-P05-resumable-discovery-release-repair-v01.md`
is staged, not executed. It repairs recent traversal under failure/new arrivals, counts failed
attempts, verifies persistence/report delivery and corrects build-to-deploy selection. It preserves
the location, timing, credential, screening and data-compatible rollback work.

Once these concrete checks hold, request a controlled deployment with real transport verification;
do not require another broad review solely because earlier rounds found defects. Authenticated
Adzuna, live source access and source-growth admission retain their separate, honestly open gates.
