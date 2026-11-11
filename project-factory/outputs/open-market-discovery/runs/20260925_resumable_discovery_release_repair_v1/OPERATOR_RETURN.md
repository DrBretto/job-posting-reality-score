# OPERATOR_RETURN — P05 resumable discovery and release binding

Run: `20260925_resumable_discovery_release_repair_v1` · 2026-09-25 · Nothing deployed, committed or
pushed. No AWS call, no credential, no network request.

## What is different in the thing you use

**Your morning radar can no longer lose a job by being interrupted.**

Before this run, two ordinary things silently dropped openings. If a page of recent postings timed out,
that page was forgotten — and worse, the system recorded the timestamps of the pages that *did* load
and treated the gap as already covered, so it never went back. And if a handful of new postings arrived
while it was still working through an earlier batch, the new ones were skipped, because there was
exactly one slot to remember "where I left off" and the old position won.

Both are closed. The system now keeps a separate list of the ranges it has **not** read, and that list
is the only thing allowed to say a range was covered. Seeing a timestamp is no longer treated as proof
of having read what came before it. A page that fails, comes back truncated, or is cut off by the
request budget stays on that list until it is actually read.

Two consequences you will see in the daily output:

- When coverage is incomplete, the report **says so** — "himalayas recent arrivals" with a count of
  ranges still owed. Previously that same situation produced a clean-looking report with a job missing
  from it. A clean report now means more than it used to.
- On a day with failures, the per-source request count will sit closer to its cap, because a failed
  attempt now spends its request instead of being free. That is the budget working correctly; the cap
  itself has not moved.

**The deploy command now ships the code it just tested.** The previous handoff told you to build into a
temporary directory and then deploy without naming the template. From the repository root that
command fails on a file that does not exist. From `infra/` it would have picked up a build from August
1st that contains **no discovery function at all** — you would have deployed the old pre-discovery
stack and it would have looked like it worked. Corrected in all three places that carried it: the new
handoff, `infra/DEPLOY.md`, and `START_HERE.md`.

## What now needs you

**One decision: deploy or not.** Everything local is verified and nothing is deployed.

The release recommendation is **deploy**. Follow §4 of this run's `DEPLOYMENT_HANDOFF.md` exactly — it
now names the template and the config explicitly, and includes a one-line check that the built template
really contains the discovery function before you ship it. Then work §5's acceptance checks; item 6 is
new and is where you would notice this repair failing in production.

Two things worth knowing before you decide, neither a blocker:

- **The first real run is still the first real test of the network.** Every check here replays
  provider-shaped payloads through the real pipeline with the transport mocked, because live requests
  from this machine truncate unpredictably. The code handles that safely — it marks the read partial
  rather than pretending it succeeded, and now retries it — but "handles it safely" is not the same as
  "we have watched it work in production."
- **If you ever roll the discovery code back one step while keeping its state**, delete the
  `head_pending` key from `discovery/state.json` first; the older code refuses unknown fields. Rolling
  all the way back to the August baseline needs nothing, because that code never reads discovery state
  at all. Spelled out in §6.2.

Still open and unchanged, none of them a reason to hold the deploy: authenticated Adzuna, general
industry breadth, the careers-URL resolver's live path, and your confirmation of a worksite when a New
Hampshire onsite role gets flagged for it.

## Receipts

- Full suite **296 → 316 passed**. Policy projection matches all sources. `sam validate --lint` passes;
  `sam build` succeeds and the built template contains the discovery function, where the stale build
  contains zero.
- The P04 reviewer's own probe, run unmodified: both lost jobs now arrive, and the request budget holds.
  Before and after saved side by side in `evidence/`.
- Both scenarios driven across multiple runs with state saved and reloaded each time, through to a
  **persisted daily report** — the actual artifact you read, not a log of requested URLs. The formerly
  lost posting appears on run two in both cases, and the historical catch-up never rewinds.
- The 20 new tests were checked against a reconstructed copy of the old code: **12 of them fail there**,
  including both scenarios and both report checks. The other 8 guard behaviour the old code already had
  right.
- Reasoning, per-check before/after detail and the full list of what this run does **not** establish:
  `VALIDATION.md`.
