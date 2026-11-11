# OPERATOR_RETURN — P04, location and freshness boundaries

Run: `20260924_location_and_freshness_boundaries_v1` · 2026-09-24 · nothing deployed, nothing committed

## What's different in the radar

**Location now works the way your policy reads, not the way a list of town names guessed.**

The screener had been answering your "approximately 30 minutes from Laconia" with a hand-written list
of towns. Three things were wrong with it at once, and all three are fixed:

- `Belmont, NH` was **excluded** while `Belmont NH` was **eligible**. A comma decided it.
- `Alton, IL` counted as local, because New Hampshire also has an Alton.
- A posting saying "Remote / Boston, MA" that required **three days a week in the Boston office**
  passed as eligible, because the word "remote" appearing anywhere skipped every location rule below
  it. So did a remote role that only employs California or New York residents.

It now reads place and state (so punctuation and a shared town name stop mattering), checks whether
attendance is actually mandatory before believing a "remote" label, and catches residency restrictions
that leave New Hampshire out. Genuinely remote roles at Boston or Portsmouth employers stay eligible,
exactly as you said.

**New postings will actually be marked new.** Every production report would have said zero new
arrivals — the code that builds the report never passed the timing through, so the renderer fell back
to the *end of the calendar day*. At a 07:05 run that is seventeen hours in the future. The tests
passed because they filled in the timing the real path was failing to supply. It now reads the run
start from the run manifest, and decides "new since the last round" by **which postings the last report
actually showed you** rather than by comparing clocks. A weekend gap, a failed morning, and a retry all
now give the right answer.

**A job posted overnight can no longer hide on page two.** The feed walk fetched exactly one page of
newest jobs, threw away the pointer to the next one, and went back to the old backlog. If a busy day
pushed new postings onto page two, they waited. It now keeps walking while pages still hold recent
jobs, stops when it reaches ground it already covered, and saves its place if it runs out of budget —
while always keeping one page for the backlog so catch-up never starves.

## One thing that got *less* decisive, on purpose

A New Hampshire onsite job now comes to you as **"confirm the worksite"** instead of a yes or a no.

Your policy states a drive time. This system has no way to measure a drive time, and the old town list
was me pretending otherwise — it certified towns nobody had measured while rejecting a genuinely local
job over a comma. So it now decides only what it can actually check: out of state is out (Laconia is
central enough that no out-of-state worksite is a 30-minute drive), Portsmouth and Boston commuting are
out because you said so, Plymouth comes to you because you said that too — and everything else inside
New Hampshire comes to you with the question named.

That means a few more rows to glance at. If you'd rather it auto-approve a specific list of towns,
say which towns and it's a one-line change. I didn't want to invent that list twice.

## What I found that the review didn't

Two more of the same defect, caught while fixing the others:

- The **local `discover` command** had the identical unwired-timing bug, so any report you ran by hand
  had the same end-of-day ages and never flagged a new arrival.
- A source with **exactly one posting** was misread as "we just started watching this source", which
  suppressed its genuinely new job.

And one in my own work: the first version of the page-two fix would have **abandoned the very pages it
saved** on the following run. A test I had just written caught it.

## What needs you

**Deploy, or send it for a fourth review.** Everything local is verified: 296 tests, clean SAM build,
policy projection matching all five of your source documents, and a two-round rehearsal over real
payloads captured from the four job feeds today.

The honest read on which to pick: three reviews in a row each found real defects, twice inside my own
tests. That pattern is the argument for a fourth. But it's weaker now than last time — the defects
being found this round are ones I surfaced myself, and what's left is mostly the two things no local
run can settle anyway: whether the production HTTP path works, and whether Adzuna returns anything once
it has a key. Only deployment answers those.

One caveat worth knowing before you decide: **the live fetches from this machine are unreliable right
now.** Pulling the same Himalayas URL four times returned 18KB, 0KB, 6KB and 18KB, where `curl` gets
the full 80KB. The code handles it correctly — it marks the download partial and refuses to treat it as
a clean read, so nothing gets falsely deleted — but it means the rehearsal used real captured data with
the transport mocked, and the first scheduled run in AWS is the real test of that path.

If you deploy: `DEPLOYMENT_HANDOFF.md` in this run folder is the one to follow. It replaces P03's,
which contradicted itself about rollback — P03 said the old code would ignore the new data fields, and
it won't; it rejects 18 of them. **A source-only rollback is not enough**; the data downgrade step is
required, and §6 now gives the order and says to stop the writers first.
