# OPERATOR_RETURN — P08 durable publication and release repair

Run: `20260925_durable_discovery_publication_release_repair_v1` · 2026-09-25
Packet: `JPRS-L2-P08-durable-discovery-publication-and-release-repair-v01`

**Nothing was deployed, invoked, committed, staged, pushed or sent. AWS was not contacted at all.**
The stack running right now is still P06, and it contains neither P07's integration nor this repair.

---

## What is different in the thing you use

**A morning where the storage write fails no longer costs you the job.**

Before this run, discovery could fetch a fitting role from an employer nobody has named, write it
durably to three places, and then hit one failed write on the way to the report's input — and that
posting was gone. Not delayed: gone. The retry saw a different slice of the feed, overwrote the last
copy, and the job never appeared in any morning report, that day or later. You would have seen a
normal-looking report with one fewer opportunity in it and no indication anything had happened.

Now the observation is *owed* before anything is allowed to call it published, and the next discovery
round publishes it without the feed having to offer the job again. Two things follow that you can see:

- **On the interrupted morning, the report says so.** Discovery coverage reads `PARTIAL` and the
  Coverage section says *"1 discovered posting(s) are captured but not yet published … missing from
  the list below through a storage interruption and not through any judgment about them."* So a thin
  morning and a broken morning stop looking the same.
  (`evidence/p08_sample_report_interrupted_round.md`)
- **The next morning, the job is there and leading the report** — with its real link and reason,
  dated as the previous day's observation rather than pretending it was just found.
  (`evidence/p08_sample_report_recovered_round.md`)

**Two things in the deployment instructions would have hurt you at the worst moment, and are fixed.**

- P07's handoff told you to **stop the deploy** if the change set showed anything other than two
  changed Lambdas. It will show **six**, every time, because packaging puts the whole repository in
  every function. You would have halted a correct deploy and gone looking for a problem that was not
  there. The stop rule now says six code-only function updates is expected, and names the things that
  genuinely should stop you: any IAM, schedule, parameter, state-machine or resource change.
- P07's rollback said to copy the current files aside first. Those files *are* the new version — you
  would have "rolled back" to the thing you were rolling back from, mid-incident, with no commit to
  return to. There is now a real P06 baseline: the build that was actually deployed, verified file by
  file against the hashes P06 recorded before any of this existed, archived inside the repo so it
  cannot evaporate with a reboot. The whole restore-and-return was rehearsed in a scratch directory.

**And you have a check that can actually fail.** `scripts/inspect_discovery_integration.py` takes
each posting discovery has stored and says where it ended up — shortlisted, excluded by which rule,
merged as a duplicate, below the fit line, still owed, or not consumed at all. It tells a genuinely
quiet day apart from a broken connection, which the old three-step check could not: both produce a
report with no discovered candidates. It also checks the **employer** against your registry, so a
role at Machinify arriving via Himalayas is correctly *not* counted as finding you a new employer.

---

## What now needs you

**One decision: whether to deploy this.** P06's approval was spent on P06 and does not carry.

Everything the packet asked for is verified locally: 350 tests pass, the reviewer's own probe now
behaves identically with and without the injected failure, the change set is measured as code-only,
the rollback baseline is verified and drilled, and the live check discriminates across five controls.
`DEPLOYMENT_HANDOFF.md` §5 has the exact commands, including a pre-deploy step that re-derives the
change set and prints `CHANGE_SET_IS_CODE_ONLY` before you confirm anything.

**What deploying would and would not settle.** It would put the repair in production. It would not,
by itself, prove the product works: the live positive condition is still *one registry-absent
employer's posting in an actual delivered report*, and that can only be observed after a real round.
A zero on any given day is legitimate — the feeds are a moving window and the screener is a policy
gate, not a quota — and the inspection script is what tells you which kind of zero you got. Do not
re-run it until a nicer answer appears; that is the failure mode it exists to prevent.

**Still separately pending, unchanged by this run:** the first unattended round on 2026-09-26
(discovery 07:05) has not happened and must not be recorded as passed before it does. Adzuna
credentials, careers-URL resolution and the Lambda packaging fix remain your open items;
`DEPLOYMENT_HANDOFF.md` §7 carries all of them, and this run quantified the packaging one.

---

## Honest limits

`evidence` — everything above is local and mocked. Mocked S3 grants every permission, so the IAM
claim is that the *declared* grants in the real template already cover the new object, checked
against the file — not that a deployed policy was evaluated. No live feed was contacted, and every
provider payload in this run is synthetic. The insurance-company and benefits-administrator roles in
the samples are **test controls, not vacancies** — do not apply to them.

`inference` — the repair is forward-compatible: rolling back to P06 leaves the two discovery-owned
objects unread and inert, so no data downgrade is needed for P07 or P08. The one real cost is that a
rollback performed while a batch is still owed abandons those observations, since P06 never drains
the ledger. The coverage receipt names the job ids, and the handoff tells you to look before you roll.

`speculation` — the two bounds in the design (five owed rounds per feed, twenty-one days of live-view
retention) are reasonable and are *reported* whenever they bite, but neither is calibrated against
anything measured. If either ever appears in a coverage receipt, that is the signal to pick a real
number rather than keep the guess.
