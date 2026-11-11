# checkpoint — JPRS-L2-P04-location-and-freshness-boundaries-v01

Run: `20260924_location_and_freshness_boundaries_v1` · 2026-09-24 · status: **complete**

Each item was reproduced before it was repaired. The reviewer's probe was never edited.

1. **Reproduced all three blockers** against the P03 review's unmodified probe and saved the output
   (`evidence/p04_before_repair_probe.json`). All seven rows failed exactly as the review described.

2. **R1 — location.** New `src/candidate/location.py` replaces three regexes of hand-written town
   names. Resolves place/state (a comma no longer flips a verdict; an Illinois namesake is no longer
   local), mandatory attendance with polarity (a remote label no longer overrides required Boston
   attendance; a reporting line and a negated requirement are not attendance rules), and residency
   limits that exclude New Hampshire. The one hard distance rule is the state boundary, which is a
   fact. Every in-state distance question is surfaced for worksite confirmation rather than certified.
   Screening ruleset 1.3.0 → 1.4.0. Two bugs found while building it: `or` parsed as Oregon, and a
   worksite named only in the description was invisible.

3. **R2 — report timing.** `resolve_run_timing` reads the run start from the RUN_OPEN manifest's
   `opened_at` and the previous boundary from the most recent earlier persisted report, ordered by the
   `dt=` partition rather than a stored clock. "New since the last round" is decided by which postings
   that report showed — identity, not arithmetic. Ages now measure from the run start, not the end of
   the calendar day. The report persists `report_generated_at` and a `timing` block for the next round.

4. **Two defects found while repairing R2, neither in the review.** The local CLI report path had the
   same unwired boundary (fixed, with `--previous-report`), and cold-start detection inferred a first
   observation from timestamp cardinality, so a warm source holding one posting suppressed its
   genuinely new arrival (now uses the source's recorded success history).

5. **R3 — recent-page continuation.** The feed-head walk continues while pages hold recent arrivals,
   hands over when it meets the backfill, and saves any remainder to `head_cursors` to resume next run.
   One page is always reserved for the historical catch-up and the budget is never exceeded (asserted
   at 1, 2, 3, 5). A design bug the tests caught: the frontier stop fired before a saved continuation
   could resume, which would have abandoned exactly the pages the previous run saved.

6. **Forward compatibility with the deployed release.** A report written by an earlier release carries
   no timing fields; the reader takes its candidate id list anyway, so the first morning after a deploy
   does not announce every already-seen posting as new.

7. **Verified.** 296 tests pass (252 inherited + 44 new); the P02/P03 transport, polarity and
   rollback-downgrade regressions still pass; SAM validates and builds; `policy-check` clean.

8. **Rehearsed** two consecutive rounds over real captured provider payloads. Round two reached page
   two *and* advanced the backfill within a 3-page budget, and read round one as its boundary. Real
   data, mocked transport — stated as such, because live `urlopen` truncated responses
   non-deterministically from this machine.

9. **Reconciled.** New DEPLOYMENT_HANDOFF corrects P03's self-contradiction about rollback data
   compatibility (the downgrade is required, not optional), makes rollback order and writer quiescence
   explicit, and fixes a cited evidence path that pointed at the wrong run root. Continuity surfaces
   synchronized; counts restated with their populations named. Historical returns preserved.

Not done, by instruction: no deployment, no AWS or SSM mutation, no credential, no email, no
application, no commit, branch, staging, reset or push.
