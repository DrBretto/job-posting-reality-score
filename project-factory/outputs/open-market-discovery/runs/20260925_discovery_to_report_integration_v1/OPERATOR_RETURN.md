# P07 — the radar now reaches your morning report

Run: `20260925_discovery_to_report_integration_v1`. 2026-09-25.
**Local only. Nothing deployed, nothing committed, no AWS touched, no email sent.**

---

## What is different in the thing you use

Yesterday's report could only ever show you the 15 employers you had already named. Discovery found
295 jobs across 218 employers and none of them could reach you — the postings were being saved to a
place the report never looked.

They reach you now. This is the top of the report the repaired code renders:

> ## New strong candidates
>
> - **Senior Software Engineer, Internal Tools and Automation** — Granite State Mutual Insurance |
>   United States | fit HIGH 0.95 | priority MEDIUM 0.46 | matches on automation, internal-tools,
>   software-engineering, apis-backend, aws-serverless, llms; remote compatible
> - **Senior Backend Engineer** — machinify | Remote - US | fit MEDIUM 0.44 | …

The first row is an insurance carrier. Not a software company, not on your list, and nothing had to
admit it or add it to the registry for it to show up — it just came through the same screening,
ranking, dedup and history everything else goes through, with a link you can click and a reason you
can judge. That is the thing the packet was for.

The full rendered report is at `evidence/p07_sample_report.md`.

Two more things you will notice in the report:

- **It says what it did not see.** Feeds that were configured but produced nothing yet, and feeds
  whose postings were carried over from an earlier round rather than re-checked today, are each named
  with the reason. A posting that has not been re-observed carries its last-verification age on the
  row and says, in those words, that a feed window is not a signal the opening ended.
- **"New since the last round" will be right tomorrow.** It would not have been. See below.

---

## Two things I found while tracing the path, both fixed

**A posting kept changing its identity.** Discovery ids were built from the pagination cursor, so the
same job was a different job every time it moved to another page or the feed rotated. That quietly
defeated deduplication, "have I seen this before", and first-observation tracking all at once. Jobs
now carry a stable feed identity.

**Tomorrow's report would have re-announced everything you already read.** The report you were
actually sent on 2026-09-25 stores its rows under `top_matches` and leaves `complete_candidate_list`
empty. The code only looked at the second one, so it read your delivered report as a round that had
shown you nothing, and would have declared every posting new the next morning. It now recovers what
that report actually showed you, and records that the list was capped at 20 so nothing treats it as a
complete census.

---

## What now needs you

**One decision: approve deploying this, or not.** That is the only thing blocking. P06's approval was
spent on P06, and this packet explicitly did not carry authority to ship. The exact commands, the
change-set you should expect, and the rollback are in `DEPLOYMENT_HANDOFF.md`.

Worth knowing before you decide: **there is no infrastructure change.** No new function, schedule,
role, alarm or permission — the new data lives in a prefix discovery already owned and the report
already read. The change set should show `jprs-discovery` and `jprs-report` only. If it shows
anything else, stop.

---

## What I have NOT shown you

I want to be exact about this, because the last run's failure was a test that proved something it
had quietly arranged itself.

**No registry-absent job has appeared in a report you actually received.** Everything above is the
local code running against captured and synthetic provider payloads with AWS mocked. It is a strong
demonstration that the machinery works; it is not an observation of production.

When it is deployed, that check is written out in the handoff — including how to tell a genuinely
thin day apart from a broken integration, because some days the feeds legitimately hold nothing that
passes your policy, and I would rather record a zero than re-run until the answer looks good.

Also still open, unchanged by this run: Adzuna credentials (still the only configured source with
general all-industry breadth), the careers-URL resolver switch, and Lambda packaging.

---

## Checks

| | |
|---|---|
| The P06 reviewer's own probe, unmodified | 0 candidate rows before → **1 after** |
| Test suite | 316 before → **339 passed** (23 new acceptance cases) |
| Candidate policy projection | matches all policy sources |
| `sam validate` / `sam build` | valid / succeeded |
| Git | untouched — no commit, branch, stage, push, reset or stash |

The two tests from P05 that claimed "real internal wiring" have been re-scoped to actually use it,
and that claim is withdrawn in the file. P05's own run evidence is left exactly as it was.
