# OPERATOR RETURN — open-market job discovery

2026-09-24 · packet `JPRS-L2-P01-open-market-discovery-v01` · tested locally, **not deployed**

---

## What is different

JPRS could only ever tell you about the 15 companies you typed into a file. A job at a company you
had not heard of could not reach you — not because the search was too small, but because arrival
required you to name the employer first. That is fixed.

Running the new path against today's live data:

- **161 employers appeared that are not in your registry.** Yesterday that number was zero, and no
  amount of adding companies would have changed it.
- **10 of them reached the retained list** with a link, compensation, and a reason — LaunchDarkly,
  Pivotal Health, Root Inc., Airspace Link, Benzinga, Salesforge, Sticker Mule, Canonical, OkWhen
  and one more.
- The combined run surfaced **43 credible roles: 14 new, 22 needing one specific check, 364 excluded
  with the quoted line that excluded each one.**

Four defects you identified are repaired, each with a test that fails against the old code:

- The `FullStack` spelling bug is gone. All five spellings now score identically; that Grafana role
  scored 0.00 purely because of a missing space.
- An unfamiliar job title no longer erases a posting. "Business Systems Engineer" at a freight
  company doing internal AI work now survives on what the work actually is.
- The department-freeze latch releases. A department that genuinely closed used to freeze its jobs
  ACTIVE forever and reprint the same warning; it now confirms closure after two independent healthy
  downloads. Genuine truncation still freezes indefinitely — that protection was not relaxed.
- Candidates past row 20 are no longer hidden in JSON. The report carries the complete readable list.

The report also stopped overclaiming. Fifteen successful downloads used to read as an all-clear; run
health is now four separate axes, and collection health explicitly says it is not a statement about
the job market.

Ashby is enabled. The identity concern that kept it off was resolved with evidence: 1,083 postings
across four live boards, every one carrying a stable UUID, one of them unchanged since 2021.

---

## What this cost

**$0.** No signup, no paid service, no AWS change, no email sent, nothing committed. All source
access was public and read-only.

---

## What is honestly not done

Two gates are unpassed, and I did not paper over either:

1. **The four working discovery sources are all remote-job boards.** They genuinely find employers
   you have never seen, but they are not an index of ordinary local businesses. Your worked example —
   a small non-software company hiring someone to apply AI internally — is most likely to come
   through **Adzuna**, which needs a free API key. It is built and tested; it has never run.
2. **Newly discovered employers cannot yet become monitored sources.** I measured why: all four
   feeds hand out their own apply links, and none of their payloads contain the employer's real
   careers URL. Following that link to find it is built and bounded, but switched off and unverified.

One more thing worth knowing: only Remotive was exercised through the production fetch path from
this machine. The other three were verified on their real live bytes, but fetched with `curl`
because this sandbox's proxy truncated them. That specific code path gets verified on the first
production run, and it is written into the post-deploy checks.

---

## What needs you

**One decision: do you want this deployed?**

If yes, `DEPLOYMENT_HANDOFF.md` has the exact commands, the change set to expect, the five
post-deploy checks, and the rollback. The change is additive — disabling one schedule reverts to
today's behavior — and the collect and assemble schedules are unchanged.

The highest-value thing you could do alongside it takes about five minutes: register a free
developer key at `developer.adzuna.com` and put it in SSM as
`/jprs/secrets/ADZUNA_APP_ID` and `/jprs/secrets/ADZUNA_APP_KEY`. No redeploy needed, and it is what
turns four remote boards into a general search across every industry with a New Hampshire filter.

---

## Next action

Tell me whether to deploy. Nothing else is blocked.
