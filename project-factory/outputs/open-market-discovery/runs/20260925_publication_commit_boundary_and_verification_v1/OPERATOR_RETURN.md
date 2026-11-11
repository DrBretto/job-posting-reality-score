# OPERATOR_RETURN — P09

## What is different in the thing you use

Nothing yet, in production. P06 is still what runs, and its discovery jobs still do not reach your
morning report. This run made the fix deployable; it did not deploy it.

What changed locally is that a discovered job can no longer vanish between being found and being
shown to you. Before this run there was a window: discovery wrote the posting to storage, then
wrote a separate record saying "this is owed to the report", and if that second write failed the
posting was already saved but nothing knew it was owed. The next morning's fetch met a different
slice of the feed, overwrote the day's file, and the job was gone from every report forever. The
P08 reviewer reproduced exactly that.

Now the "this is owed" record is the **first** thing written for each feed, before anything else.
So either the round never started — and the feed has to show the job again, which is honest — or
the job is recoverable no matter what fails afterwards. Sixteen distinct failure points were
tested one at a time, with the feed returning nothing on every later attempt, and the job comes
back in all fifteen that got past the first write.

A second thing changed that would have cost you jobs quietly. The old code held at most five
rounds' worth of undelivered work and **dropped the oldest** beyond that — and the first round that
finally succeeded would itself trigger the drop, because it added its own (empty) batch. So the
recovery round was the round that lost the oldest job. It now folds old rounds together instead of
discarding them, and nothing is dropped except postings so old the report would not carry them
anyway.

Third: the checks that were supposed to stop a bad deploy did not stop anything. A build whose IAM
settings had changed passed as "code only". A corrupted rollback archive printed MISMATCH and
returned success. A stored job missing from your report was labelled "below the fit threshold" on
no evidence — the check had inferred it from the employer's name appearing elsewhere. All three now
fail, and the report itself now states which job identities it actually consumed, so the check
reads evidence instead of guessing.

## What now needs you

**One thing, and it is a real decision.**

`policy-check` is now failing. Two of your own documents —
`Infotropy Book/INBOX/Employment Search/APPLICATION_WORKFLOW.md` and `OPERATING_PLAN.md` — were
edited this morning, and the screening projection committed in this repo was built from the older
versions. The projection is the thing that decides which roles get excluded and why, so refreshing
it changes candidate policy. This packet explicitly forbids candidate-policy edits, so I did not
touch it.

Until you decide, the deploy sequence stops at that check — deliberately. It is the gate working.

Everything else is ready for review: 393 tests pass, the template validates, the build succeeds,
and the change set against a reconstructed P06 baseline is genuinely code-only across all six
functions.

## What this run does not claim

- No deployment, no AWS call, no invocation, no git commit or branch. The uncommitted overhaul is
  intact.
- No live success. Every posting in every test here is synthetic — the insurance and benefits
  companies are controls, not vacancies to apply to.
- The real condition — a job from an employer you have never named, from a live feed, in a report
  actually delivered to you — is **not met** and is not being reported as met.
- The unattended round this morning at 07:05 was not checked. It runs P06's code, so it says
  nothing about this repair either way.

## Where to look

| question | file |
| --- | --- |
| what was verified and what was not | `VALIDATION.md` |
| every failure point and what recovered the job | `FAILURE_MATRIX.md` |
| how to deploy it, and how to roll it back | `DEPLOYMENT_HANDOFF.md` |
| whether it should advance | `gate_decision.md` |

## The next step

Orchestrator review of this run. After that — and after the policy-projection decision — fresh
deployment authorization. Not another committee.
