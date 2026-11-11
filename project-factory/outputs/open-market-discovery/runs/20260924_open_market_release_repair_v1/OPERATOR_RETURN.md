# OPERATOR RETURN — discovery release repair

2026-09-24 · packet `JPRS-L2-P02-discovery-release-repair-v01` · tested locally, **not deployed**

---

## The review was right, and two of the four were serious

The orchestrator review caught four defects in what I handed you yesterday. I reproduced all four
before touching anything. Two of them mattered a lot:

- **The Adzuna path could never have worked.** Three separate bugs: the default run never even
  reached Adzuna, the connector read the wrong place for credentials so every request would have gone
  out blank, and the New Hampshire search I described in the design was never wired at all. If you
  had gone and got that API key, nothing would have happened and the report would not have told you
  why. My own test missed it because it tested a path production never takes.
- **The rollback instructions would have destroyed this work.** `git checkout e549a73 -- src/` was in
  the handoff. None of this is committed, so that command would have wiped it with no copy anywhere.
  The disable command I gave you was also simply rejected by the AWS CLI.

The other two: Himalayas was being read as a single complete feed when it is actually paginated 20 at
a time, so roughly four fifths of it was unreachable. And screening was excluding postings for words
rather than meaning — "No security clearance is required" was thrown out for requiring a clearance.

---

## What is different now

**Discovery reaches much further.** Himalayas went from 20 postings to **96, across 74 employers**,
verified against the real provider. Across all sources the run now sees **821 postings from 221
employers, none of which are in your registry** — up from 162.

**Screening reads sentences instead of matching words.** It now tells apart "clearance required" from
"no clearance required", and "build tools for the sales team" from "carry a sales quota". I
re-screened all 364 postings the old code excluded: **34 were wrongly excluded.** Of those, only
**2 are real opportunities** — the rest were operations, legal and marketing roles that fit scoring
rejects anyway. One of the two is the Future Full-Stack Growth Engineer the review flagged, which had
been thrown out because the words "members or prospects" appeared in it.

**The Adzuna key will now actually do something** when you provide it, and if you do not, the report
names it as the reason coverage is partial.

**Nothing is silently dropped.** 403 postings scored below the fit threshold this run. That number
appeared nowhere before; it is now stated in the report, because your workflow says the JPRS score is
not a final rejection gate.

**Rollback is validated and non-destructive.** Both commands were tested locally against the AWS CLI
without touching AWS. The full rollback now builds from a separate worktree and never touches your
working tree.

---

## What it cost

**$0.** No signup, no AWS change, no commit. All source access was public and read-only.

The deployment cost estimate is now sourced rather than asserted: about **$0.10–0.15/month**, almost
entirely one CloudWatch alarm at $0.10, taken from AWS's price list API. I withdrew the earlier
"$0 additional" claim — it assumed free-tier eligibility nobody had checked.

---

## Still honestly open

- **Adzuna has never actually run.** The path works now; no key exists, so no authenticated search
  has returned anything. The key enables the attempt; it does not by itself prove coverage.
- **Three of the four feeds still have not been fetched through the production code path** from this
  machine — the local network proxy truncates them. Their bytes are real and everything downstream is
  verified on them; the fetch itself gets verified on the first production run.
- **Discovered employers still cannot become monitored sources.** The system writes *proposed*
  registry rows. Applying them is your action, and I did not blur those two things.
- **Nobody independent reviewed the repaired screening rules.** I wrote them and I checked them. The
  review that found yesterday's four defects is the reason I would not call that sufficient.

---

## Next action

Tell me whether to deploy, or send this for another review first. `DEPLOYMENT_HANDOFF.md` has the
validated commands, the change set to expect, seven post-deploy checks and the rollback.
