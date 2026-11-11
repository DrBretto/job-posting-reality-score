# OPERATOR_RETURN — P06 controlled discovery deployment

Run: `20260925_controlled_discovery_deployment_v1` · 2026-09-25 · Deployed to `jprs-v1` under your
in-session approval. No commit, push or branch. No email sent. No registry or SSM change.

## Deployment — done, clean, nothing else disturbed

The overhaul is live in `us-east-1`. I read the change set before executing it: 6 additions (the
discovery function, its role, log group, scheduler role, schedule, and the A8 alarm), 9 modifications,
and **no removals and no replacements** — nothing was rebuilt or destroyed.

Your existing setup is untouched. Collect still fires 07:00 and assemble 09:00, both
`America/New_York`. The new discovery pass sits at 07:05, straight from the reviewed template — I
didn't invent a cadence. The 15-board registry, your stored history, and every existing parameter
(including the three email settings, which have no template default and would have broken alerting and
delivery if they'd been dropped) all carried through verified.

I deployed into a quiet window: today's collection and assembly had both finished, zero executions
running, both queues empty.

## Live sources — the gate that had never been closed is now closed

This was the one thing no amount of local testing could establish. **All four keyless feeds worked from
the real Lambda: 295 jobs from 218 employers, zero inaccessible, zero failures.** Adzuna reported
itself as credential-gated, exactly as designed. Real pagination happened — five himalayas pages, not
just a first page — and every source stayed inside its request cap.

The truncation problem you'd seen from your own machine did not occur from Lambda. That's one run, not a
guarantee, but it's the first genuine evidence the transport works.

The resumability repair also held on real data, and I didn't have to break anything to check: the
"ranges still owed" list is empty and the coverage receipt's "inaccessible" list is empty — the two
agree, which is the invariant. The historical backfill saved its position and the report says so
plainly.

## The part that does not work yet — read this one

**None of those 295 jobs can reach your morning report.** Your report today has 35 candidate rows and
every single one is a Greenhouse board from the monitored 15. Zero rows from any discovery feed.

The jobs aren't lost — they're fetched, normalized and stored. There is simply no wire connecting them
to the report:

- `enumerate` files discovery sources under `expected_discovery_sources`, and only the monitored boards
  under `expected_sources`.
- the report builds candidate rows by walking `expected_sources` only — it never looks at
  `expected_discovery_sources` at all.
- candidate rows come from `current/`, which only the differ writes, and the differ runs once per
  company in your `/jprs/companies` registry. Discovery feeds aren't in it, so `current/` contains
  nothing but Greenhouse.

So right now discovery gives you an honest **coverage line** — "4/4 discovery sources returned results,
14/14 query families covered, 1 item queued and resumable, adzuna needs a credential" — and none of the
jobs behind it.

I did not fix this. It's a real design decision, not a one-line patch: it has to settle how feed jobs
enter differ-owned state, what "a posting disappeared" means for a feed that churns daily, how to dedup
against the monitored boards, and whether hundreds of unscreened postings a day belong in your candidate
list. That needs its own bounded packet, and your packet told me to stop rather than improvise.

**I also have to correct my own earlier work.** In P05 I reported two tests proving "the recovered job
reaches the persisted report". Those tests passed because my test harness wrote the wiring itself — it
created the `expected_sources` entries and the `current/` files that production never creates. They
correctly prove the traversal repair works *given* that wiring. They did not prove the wiring exists,
and I presented them as stronger than they were.

## One smaller finding

Today's report labelled its freshness boundary `cold-start` rather than reading yesterday's. Cause:
your existing reports store their rows under `top_matches` with `complete_candidate_list` empty, and the
"read the previous report's ids" fallback only looks at `complete_candidate_list`. So it found nothing
usable. `cold-start` is an honest label, not a false claim, and it fixes itself tomorrow because today's
report is the new format. But the P05 handoff's claim that an earlier release still supplies its id list
isn't true of your actual history.

Also worth knowing: for today only, the report stored in S3 is the new richer version while the digest
you were emailed at 09:01 was the old code's. I preserved the original first. They agree from tomorrow.

## What needs you

**One decision: do you want the discovery-to-report wiring packet (P07)?** That is what stands between
"discovery works" and "discovery gets you jobs".

Leave the stack deployed either way — I'd recommend it. Discovery physically cannot write the monitored
data (`current/` and `events/` are closed to it), your radar is healthy and unchanged, nothing is
corrupting, and tomorrow's unattended run collects the evidence below on its own. No rollback and no
data downgrade is needed.

## Pending — genuinely not checked

Tomorrow's first unattended round (2026-09-26, discovery 07:05) has **not run**. The cross-round
freshness check — whether the report then reads `reported-ids` pointing at today instead of `cold-start`
— is the real retest of that smaller finding, and I am not claiming it either way. Exact paths to check
are in `evidence/p06_live_verification_summary.md` §6. I did not set up anything to wait for it.

## Status, kept separate

| | |
|---|---|
| Local repair accepted (P05) | yes, before this run |
| Stack deployed | **yes** |
| Four keyless sources live-verified | **yes**, one production run |
| Discovered jobs reach your report | **no** — absent wiring |
| Tomorrow's scheduled-round freshness | **pending, not run** |
