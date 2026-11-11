# OPERATOR RETURN — runtime boundary and fresh-first

2026-09-24 · packet `JPRS-L2-P03-runtime-boundary-and-fresh-first-v01` · tested locally, **not deployed**

---

## The review was right again, and one finding was about my testing

Three things were still broken after P02, and the worst one is embarrassing in a useful way:

**My Adzuna test was testing itself.** I had "fixed" the credential path and written a test that
passed. But the test replaced the very function that was broken with a stand-in, so it checked the
URL going *into* the broken code rather than the request going *out*. The real call still stripped
your credentials. If you had gone and got that API key, every request would still have gone out
empty. Fixed, and this time the test intercepts the actual network call with the real wiring in
place — and I re-ran the reviewer's own probe, which I did not write, before and after.

**Screening stopped reading after the first match.** "We do not require a recorded video. You must
complete a one-way video interview in the final round" came out ELIGIBLE, because the negation
ended the search before the real requirement. Same for a job that said no clearance was needed but
required a drug screening, and for one that said "build tools for the sales team **and** carry a
sales quota". All three now exclude correctly. And an *optional* video with a live alternative no
longer hard-excludes a good job.

**Rollback would have left the old code unable to read its own data.** I had claimed the new fields
were harmlessly ignored by the previous release. They are not — it rejects them outright, 18 fields
on a job record and 5 on the differ's state. So reverting the code alone would have broken
production. There is now a downgrade step, rehearsed end to end: back up, strip the new fields,
confirm the old code reads it, confirm it restarts without wrongly marking anything as disappeared.

---

## Fresh-first, which you asked for while P02 was running

You want strong fits promptly, ideally inside 24 hours. I measured the actual source behavior rather
than guessing: the Himalayas cursor is a **descending timestamp**, so resuming where the last run
stopped walks steadily *away* from new postings and never comes back. That is why new arrivals were
waiting behind a multi-day backfill.

Now every run checks the head of the feed first, then spends the rest of its budget continuing the
backfill. Both proceed; neither starves.

The report has a **"New since the last round"** section. It is a highlight, not a re-ranking — both
sections are ordered by fit, and nothing is dropped for being old. A fresh mediocre job cannot jump
ahead of a strong one.

One thing I caught and fixed before believing my own output: the first rehearsal said **44 of 44**
retained roles were "new since the last round". That was nonsense — on a first run every posting is
seen for the first time, which says when *we* started looking, not when it was posted. Now only a
real publication date counts on a source we have just started watching. The honest number was
**4 fresh**, plus 12 older-but-strong.

**What I cannot promise:** sub-24-hour capture. Discovery runs once a day at 07:05, and Remotive
publishes on a documented 24-hour delay, so a Remotive posting can be ~48 hours old when you first
see it. The report labels each row's age and says which date it rests on. A second afternoon pass
would help; it is written up for your approval and I did not change any schedule.

---

## One thing you changed while I was working, that I acted on

Your new **Location and Compensation** section landed partway through. My screener directly
contradicted it: it was treating Portsmouth, Boston, Cambridge, Waltham and effectively all of
Massachusetts, Maine and Vermont as commutable, and it was spending search budget on a Boston query.
You now say Portsmouth and Boston commuting are excluded.

So I aligned it:

- onsite or hybrid is only eligible in genuinely local Lakes Region towns;
- Portsmouth and the Boston area are excluded **for commuting only** — an employer there is still
  eligible when the role is genuinely remote, which your text says explicitly;
- **Plymouth goes to "ask Brett"**, not to a yes or a no, since you called it an exception to discuss;
- I dropped the Boston search scope, because it was mostly returning onsite Boston roles the screener
  now rejects. Remote roles at Boston employers still arrive through the nationwide and remote
  searches, so nothing is lost;
- **I added no pay rule at all.** You said the targets are not minimums or ceilings and not to turn
  them into exclusions, so nothing is excluded on compensation — there is a test asserting that at
  $110k, $130k and $340k.

One thing to check when you read this: the policy gives a *drive time* ("approximately 30 minutes from
Laconia"), and I had to turn that into a list of towns. That list is my interpretation, not yours.

## What it cost

**$0.** No signup, no AWS change, no commit, no real credential.

I also corrected my cost arithmetic, which the review caught: I was off by about 20×. 512MB for
10–30s is 5–15 GB-seconds per run, not 0.25. Recomputed for the real pagination it is
**≈$0.11–0.13/month**, still almost entirely the one CloudWatch alarm at $0.10.

---

## Still open

- **Adzuna has never actually run.** The boundary now provably carries a credential; there is no
  credential to carry.
- **Three of four feeds still have not been fetched through the production code path** from this
  machine — the local proxy truncates them.
- **The rollback downgrade is rehearsed, not performed.** Running it against production needs your
  approval, and it takes its own backup first.
- **No independent reviewer looked at this repair.** Two reviews in a row have each found defects I
  missed, including in my own tests. I would not treat my own sign-off as sufficient here.

---

## Next action

Tell me whether to deploy, or send this for a third review first. `DEPLOYMENT_HANDOFF.md` has the
validated commands, the change set, post-deploy checks, the two-part rollback and the corrected cost.
