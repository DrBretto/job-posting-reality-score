# Resumable discovery + release-binding repair (P05)

Packet: `project-factory/claude_handoff/packets/jprs/JPRS-L2-P05-resumable-discovery-release-repair-v01.md`
Run root: `project-factory/outputs/open-market-discovery/runs/20260925_resumable_discovery_release_repair_v1/`

## Context

P01–P04 built the open-market discovery overhaul. Nothing is committed or deployed. The independent
P04 review confirmed 296 passing tests and the location/timing repairs, and reproduced three
remaining defects, all of which this plan addresses and nothing else:

1. **A pending recent range can be discarded.** A failed recent page returns its cursor, but the
   caller saves a head continuation only when the walk stopped for *budget*; a failure (or a stop at
   the observed frontier) throws the pending range away. The frontier then advances from the
   timestamps of the pages that *were* read, so the next run treats the untraversed range as
   covered. The job on that page is never collected.
2. **A new burst above a saved continuation is skipped.** `head_cursors` is one slot per source. When
   the provider publishes new pages above a saved continuation, the saved cursor *overrides* the
   provider's new continuation link, so the newly published range is never requested and the
   advancing frontier subsequently hides it.
3. **Failed attempts escape the request budget.** `requests_spent` is incremented only after a fetch
   returns, so a raised fetch is free: 4 attempts occur under a budget of 3.
4. **Deployment does not select the build it verified.** The P04 handoff builds into
   `/tmp/jprs-build` and then runs `sam deploy` with no `--template-file`. SAM 1.137.1 resolves the
   template from `.aws-sam/build/template.yaml` then `template.yaml`/`template.yml` relative to the
   working directory — never the custom build dir. Here that resolves to a nonexistent root
   `template.yml`; in a tree with a stale default build it would silently deploy that stale build.

Reproduced before any edit: `evidence/p05_before_repair_p04_probe.json`.

## Plan

- [x] Read-first: `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, factory bootstrap + shared contracts,
      `RUN_OUTPUT_CONTRACT.md`, the controlling plan, the whole P04 run, the discovery state/callers,
      the pagination fixtures, and `infra/` + the installed SAM template-selection code.
- [x] Reproduce both review scenarios with the P04 probe unchanged; save the output as evidence.
- [x] **State model.** Replace the single head slot with an ordered list of *untraversed* recent
      ranges (`DiscoveryState.head_pending`), keeping `head_cursors` as a derived compatibility
      mirror so a rollback to the single-slot reader still resumes the newest owed range.
      Observation (`head_frontier_at`) and traversal debt (`head_pending`) become separate facts.
- [x] **Walk model.** One worklist-driven walk: page one always first, then each page's own
      continuation, then previously owed ranges. A range that fails, returns a non-success snapshot,
      or is cut by budget stays owed. The already-observed-frontier stop applies **only** to the
      contiguous chain from page one — for a resumed range it would drop a continuation nothing else
      records. Resumed chains still end at the recent-time horizon, the backfill's position, the feed
      end, or a repeated cursor, so they stay bounded.
- [x] **Budget.** Charge every outbound attempt, including one that raises, and bound every walk by
      the source budget's remaining allowance rather than by the per-phase slice alone.
- [x] Bound persisted state: cap the owed list and report anything dropped.
- [x] Regressions that fail on P04: both review scenarios, serialized state round trips, repeated
      invocations over a long backlog, failed/partial middle pages, saved continuation + new burst,
      unchanged head, repeated cursors, budget exhaustion, the attempted-request budget, the
      timestamp cursor contract, and first-seen/dedup preservation.
- [x] Both review scenarios must reach a **persisted candidate report** through mocked transport with
      production internal wiring intact.
- [x] **Deployment binding.** Correct the forward and rollback command selections so template and
      config paths are unambiguous, and verify the selection locally through SAM's own resolution
      code without invoking AWS.
- [x] Validate: focused regressions, full suite, policy projection check, `sam validate`, `sam build`,
      persisted-report scenarios. Record before/after.
- [x] Reconcile factory continuity surfaces; emit the run outputs the contract requires.

## Execution Log

- 2026-09-25 — Read-first complete. P04 probe rerun unchanged: both scenarios reproduce
  (`missing_fresh_job: true` twice, `attempts_exceed_budget: true`). Baseline suite 296 passed.
- 2026-09-25 — Confirmed the SAM defect is live: no root `template.yaml`/`template.yml` exists, root
  `.aws-sam/build/` holds five function directories and **no** `template.yaml` (and no
  `DiscoveryFunction`), while `infra/.aws-sam/build/template.yaml` is a stale 2026-08-01 build. So
  the unbound deploy command fails from the repo root and would select a stale build from `infra/`.
- 2026-09-25 — Implemented the state/walk/budget repair in `src/discovery/budget.py` and
  `src/discovery/handler.py`; added `tests/test_resumable_discovery_and_release_binding.py`.
- 2026-09-25 — Deployment binding corrected in the new `DEPLOYMENT_HANDOFF.md` and `infra/DEPLOY.md`;
  selection verified through SAM's own resolver locally.
- 2026-09-25 — Validation complete; run outputs written. No deploy, no commit.

## Follow-ups

- Controlled deployment with live HTTP checks remains operator-approved work, not part of this run.
- Authenticated Adzuna, general-industry coverage and source admission remain separate activation
  checks.
</content>
</invoke>
