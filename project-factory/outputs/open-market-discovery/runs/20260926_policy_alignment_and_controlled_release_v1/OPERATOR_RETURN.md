# OPERATOR_RETURN — P10

## What is different in the thing you use

**Nothing in production yet.** P06 is still what runs, and its discovered jobs still do not reach
your morning report. This run cleared the gate that was blocking the release and made the release
verifiable. It did not deploy.

What changed locally is that the radar now actually applies the rule you wrote yesterday morning.

Your note said broadening for stable employment does not mean going back to customer service or
working a call center. Before this run, **nothing in the code knew that** — there was no
call-center, customer-service, phone-support or help-desk handling anywhere in it. The check that
went red was telling you the projection's hashes were stale; the real gap was that the screening
behavior did not exist. Refreshing the hashes would have turned the light green and changed nothing
about what you'd be shown.

Now, run over the 282 real postings captured on 2026-09-24, five roles that were previously reaching
your report — as "below the fit threshold", with no reason recorded — are excluded with the duty text
that justifies it:

- **Resource Guru**, Customer Support Specialist — "helping customers by email … troubleshooting"
- **Warehance**, Customer Support & Success Specialist — "work directly with customers, answer
  technical questions"
- **Unio Digital**, Tier III Service Desk Engineer — an MSP helpdesk for client end-users, by phone
- **CoinGecko**, Operations Associate — "support to customer inquiries across channels" (no support
  title at all; the duties gave it away)
- **Integrated Language Solutions**, Sales Support - Italian — "Field Inbound Sales & Support Calls"

**None of your eleven retained candidates was touched.** The retained set is identical, job id for
job id. The rule subtracts phone-queue work; it does not shrink the good list.

The harder half was not the exclusion — it was everything your note said the exclusion does *not*
mean. Software for a support department, internal problem ownership, requirements conversations and
delivery meetings, a company with an existing engineering team, a posting with no AI wording: each of
those is a test, and each stays eligible. Where the posting genuinely doesn't say whether a support
title means an external queue or internal software ownership, you get "read this one" rather than a
silent yes or a made-up no.

An independent reviewer then broke it twice, in opposite directions, and both are fixed:

- An **internal** IT/DevOps role that manages an internal service desk queue was being **hard
  excluded** — in some cases with evidence text containing the word "internal" under a reason
  claiming "external". That was the population your note was written to open up, and it was the one
  being thrown away. A help desk is an internal function; the code was treating the phrase as
  self-evidently external.
- A posting titled **Call Center Representative** whose duty was answering customer phone enquiries
  came back **eligible**, because it mentioned building a report somewhere. One software verb
  anywhere in the text cleared a title you explicitly reject.

Neither was visible in the 282-posting audit — that corpus doesn't contain those phrasings. The audit
said the rule was sound; the reviewer's one-sentence postings said otherwise. Both were needed.

## What now needs you

**One thing: authorization to deploy this and run one ordinary round.**

That is the only item blocking the release. P06's approval is spent and nothing in this run's files
grants a new one. Everything else is done and checked:

- `policy-check` exits 0 — the gate P09 stopped at is genuinely resolved, not silenced
- 433 tests pass; 22 of the 40 new ones fail against the pre-change code, so they measure something
- the P06 baseline was rebuilt and verified 36/36, and the release preflight passes with
  `CHANGE_SET_IS_CODE_ONLY` across all six function artifacts
- the rollback path was drilled again and left your working tree byte-identical

If you authorize it, say so explicitly and say whether it covers the one live round. The exact deploy
and live-verification sequences are in `DEPLOYMENT_HANDOFF.md` §4; nothing else needs deciding first.

## What this run does not claim

- No deployment, no AWS call, no invocation, no email, no git commit or branch. The uncommitted
  overhaul is intact.
- **No live success.** Every posting above is a record captured on 2026-09-24, not a current vacancy
  and not something to apply to. The captured slice is four remote-job feeds on one day — not a
  picture of the market.
- The real condition — a job from an employer you've never named, from a live feed, in a report
  actually delivered to you — is **not met** and is not being reported as met.
- No application was submitted, no employer contacted, no resume generated, and no part of the
  submission pilot was built.
- One honest weak spot: a posting that gets "read this one" **and** scores below the fit band still
  reaches no readable section of the report — it shows up only as an id in a JSON list. That is
  pre-existing report behavior, but the new rule's population skews low-fit, so the "stays visible"
  promise is weaker than it sounds. Fixing it means changing report ranking, which this packet does
  not cover.
- The unattended round this morning at 07:05 was not checked. It runs P06's code, so it says nothing
  about this change.

## Where to look

| question | file |
| --- | --- |
| what was verified, and what was not | `VALIDATION.md` |
| what the reviewer broke, and how it was fixed | `INDEPENDENT_REVIEW.md` |
| how to deploy it, and how to roll it back | `DEPLOYMENT_HANDOFF.md` |
| every changed verdict, by job id, with reasons | `evidence/p10_disposition_delta.json` |
| whether it should advance | `gate_decision.md` |

## After the live path is verified

Your own queued sequence in `APPLICATION_WORKFLOW.md` → **Backlog Catch-up and Automated Submission
Pilot** takes over, in its stated order: reconcile the older still-open jobs against real
submission/skip/rejection history, deduplicate and re-check what is still open and still a fit;
research the promising companies; approve a batch; verify one real supported-form pilot end to end;
then scale as the observed results justify — keeping fresh arrivals moving throughout.

This run implemented none of that and does not stand in for it.
