# 2026-09-28 — history reconciliation and the broad-ownership release

## Context

Two things are true at the same time and only one of them is a code change.

**The broad-ownership retention behaviour is built, reviewed and tested, and it is not in
production.** `20260928_career-broad-ownership-discovery-v1` implemented the operator's
2026-09-28 preference — a posting that establishes broad or first/sole ownership *of software*
reaches the needs-a-check section whatever its fit score — ran it over 176 real postings, took a
`revise` from an independent reviewer, repaired all seven material findings, and stopped at the
release boundary. Production still runs the 2026-09-26 recovery build, CodeSha256
`zh54MFJryy2R3q99ZZYQY2apN1u/0Z8EYaKXBqnogbM=` across all five functions.

**The application-history projection is four days stale, and it is what decides `NEW`.**
`config/application_history.json` carries `built_at: 2026-09-24T00:00:00Z` and 42 hand-reviewed
entries. Seven dated Career Factory submission rounds have run since. Their submissions are not in
it, so a posting already submitted on the 26th or 27th is announced as a fresh opportunity. The
report is honest about a *missing* projection — it says so in terms — but has no equivalent notice
for one that is **present but stale**, because from inside the report the two look identical.

Finding body: `../Infotropy Book/book-factory/runs/20260928_career-broad-ownership-discovery-v1/findings/FINDING-03-application-history-projection-is-stale.md`
(`PQ-CAREER_FACTORY-058`).

## Why the existing path is repaired rather than replaced

`src/candidate/history.py` already carries the invariant that matters: a **folder scan is capped at
PREPARED** and can never conclude on its own that something was submitted. That cap exists because a
regex over two months of freeform package prose was measured against a careful reading and got
statuses wrong in both directions — and a false SUBMITTED hides a live opening, which is the exact
harm this system exists to prevent.

So the repair does not loosen the cap and does not introduce a second history store or a daemon. It
adds the **evidence source the scan never had**: the append-only `SUBMISSION_LOG.md` files the
application runs write, where the employer's own acceptance text is quoted against a numbered
requisition. A folder says materials exist. A submission log says the employer answered.

## Plan

1. **Record the baseline.** Working tree, deployed stack identity, function CodeSha256s, live
   processed template, before-image hash manifest, 551-test green. *(done)*
2. **Reconcile the actual submissions** across all seven dated logs plus the INBOX day indices, by
   requisition and URL, including the aggregator aliases the feeds actually carry. *(done —
   `SUBMISSION_RECONCILIATION.md` in the governed run)*
3. **`src/candidate/history.py`** — a submission-log reader, URL aliases, a declared cutoff, and a
   held/unresolved list.
4. **`src/report/handler.py`** — make missing / stale / current / known-empty four distinguishable
   states on the page, with the projection's as-of and cutoff stated.
5. **`src/cli.py`** — `history refresh`, repeatable from evidence.
6. **Tests** — `tests/test_history_reconciliation.py`, pinned on the real reconciled corpus.
7. **Checks** — focused, full suite, `policy-check`, `sam validate --lint`, fresh `sam build`.
8. **Independent review** of the final delta, then repair in scope and retest.
9. **Change set against the live baseline, property by property.** Code properties only. Any
   permission, schedule, parameter or resource delta stops the deployment at that boundary.
10. **Deploy, then one ordinary production discovery/report round**, and inspect what persisted.

## Design

### The cap stays; a second evidence source is added beside it

Three confidence levels, and only the first two may carry a suppressing status:

| confidence | source | may carry SUBMITTED / REJECTED / SKIPPED |
|---|---|---|
| `reviewed` | the committed projection, each entry with a quoted line | yes |
| `submission_log` | an append-only `SUBMISSION_LOG.md` result marker | yes, and only `SUBMITTED` |
| `parsed` | the folder scan | **no** — capped at PREPARED, unchanged |

`submission_log` promotion is deliberately narrow, and every clause is load-bearing:

- the file must be named exactly `SUBMISSION_LOG.md`;
- the record must sit under a numbered target heading naming both an employer and a role
  (`## 3. Employer — Role`); a numbered narrative heading is not a record;
- the section must carry an acceptance marker **on its own line, with its own bullet, bold or
  heading markup** — `Result: SUBMITTED` exactly, or a `Confirmation:`/`Acceptance:` line whose
  value, or the employer's words quoted directly beneath it, actually records an acceptance;
- anything the section **quotes** — a fenced block, a blockquoted line — is another run speaking and
  cannot promote. The one exception is the employer's own words quoted under an acceptance marker,
  which are the evidence itself;
- a section carrying an acceptance marker **and** a not-submitted claim is **held**, never promoted.
  So is one whose result is BLOCKED, HELD, NOT SUBMITTED, or SUBMITTED with a qualifier.

**A posting URL is not required**, and that is a decision rather than an omission: seven real
submissions record their requisition in prose and write no `URL:` line, and holding them would
re-announce seven confirmed applications. They match on normalized employer+title — the granularity
distinct requisitions differ at in this corpus — and where a URL is known it is carried as an alias
on the committed row instead.

Held records are not invisible. They land on `ApplicationHistory.unresolved` with their reason and
evidence quote, and the report prints the count.

### Aliases, because the feed and the ATS are different URLs

The projection matched one URL per entry. The feeds carry aggregator URLs and the applications were
submitted on ATS URLs, so the two never met and the lookup fell through to employer+title — which
misses whenever the aggregator's title differs from the requisition's.

The worked case is the packet's own control: **Pivotal Health, Senior Software Engineer, Case
Execution** is Ashby `5984f6bb-78f2-4d68-a907-dcd5b80d2831` and remoteOK `1136795`. Submitted
2026-09-26, employer-confirmed. Both URLs must resolve to that one submission, and a *different*
Pivotal Health requisition must stay eligible.

`HistoryEntry.posting_urls` holds the alias list; `posting_url` remains the primary and every
existing entry keeps working untouched.

### A cutoff, not a claim of completeness

`built_at` says when the file was written. It says nothing about how far the evidence reached, and a
reader who treats it as coverage is reading a completeness claim that was never made.

`ApplicationHistory.cutoff` is the separate, explicit statement: **the latest evidence date this
projection actually read.** The report prints it, prints the gap to the report date, and says
plainly that submissions after the cutoff are not represented. That makes stale and current
distinguishable without anyone asserting that the history is complete — which it cannot be, because
a concurrent application run may be writing its log while this one reads.

### Four projection states on the page

| state | what the reader sees |
|---|---|
| `missing` | the existing notice: every posting reads NEW because no history was available, not because none exists |
| `stale` | as-of and cutoff, the gap in days, and that anything submitted after the cutoff is not represented here |
| `current` | as-of and cutoff, with the cutoff at or after the report date |
| `known_empty` | present and deliberately empty — different from missing, and said differently |

## Execution Log

- Baseline recorded; 551 tests green against the inherited tree; deployed identity pinned.
- Reconciliation derived from eight submission logs + two INBOX day indices: 29 confirmed
  submissions after the 2026-09-24 build date, 3 held, cutoff 2026-09-28.
- **Re-reading the concurrent run's log mid-flight changed the code.** The contract-application
  packet wrote a confirmed submission into `2026-09-28-contracts/` while this run was open, in a
  THIRD acceptance format (`Acceptance (employer-confirmed), verbatim:`). The reader did not know it
  and was skipping the section in silence. Fixed, and — the durable half — a section whose heading
  claims SUBMITTED while carrying no marker the reader understands is now held and named instead of
  dropped, so the fourth format surfaces on the page rather than vanishing.
- One correction to an inherited claim: the 2026-09-28 discovery return listed **Evolve — Staff
  Software Engineer (remoteOK 1136447)** as "already submitted 2026-09-26". The submission log says
  otherwise in terms — that requisition is **off Evolve's board**, and the application went to a
  *different* live requisition, *Senior Software Engineer, Full Stack* (Greenhouse `8003653003`).
  Recorded as two rows: the submitted one SUBMITTED, the closed one SKIPPED with the log's own
  sentence as its evidence. Neither is guessed into the other.
- History module, report states, CLI refresh and regression tests implemented.
- **Independent review returned `revise` with thirteen findings. All were real.** Five were in the
  over-suppression direction — the one that hides a live opening — and every one of them is repaired
  and pinned as a regression:
  - `Result:` was unanchored, so a **blockquoted or fenced** result line, or a wrapped prose sentence
    about a *different* employer, promoted a section that said in its own words that nothing was
    sent. Markers are now line-anchored, must carry their own bullet/bold/heading, and quoted regions
    are blanked — with one deliberate exception, because the employer's words quoted *under* an
    acceptance marker are the evidence itself.
  - The design promised that a section carrying **both** claims is held; the code only held when no
    `Result:` line existed. In an append-only log a correction appended under the same heading is the
    expected shape, and it is the exact case where promoting hides an opening. Now held either way.
  - A `Confirmation:`/`Acceptance:` **label** concluded SUBMITTED regardless of its value, so
    "Confirmation: still pending" and "Acceptance: refused" both promoted. The value must now record
    an acceptance and must not be a refusal. `SUBMITTED PENDING VERIFICATION` no longer counts.
  - **The confidence cap ran only in the builders, never on the read path that decides NEW.** The
    projection is hand-edited, so a `parsed` row carrying SUBMITTED went straight into `status_for`
    with nothing in its way. `load_history` now enforces it.
  - The plan and the docstring claimed a posting URL was required when the code deliberately does not
    require one. The documents were wrong; they now say what the code does and what it costs.
  - **A privacy leak of my own making:** `_quote`'s 30-character look-back reached into the
    form-answer readback preceding a `Result:` line and shipped work-authorization and sponsorship
    answers into the deployed package. Quotes now start at the marker, and the privacy test's
    allowlist gained the terms that would have caught it.
  - **A test named "the load-bearing one" did not discriminate**: neutralizing the exact behavior it
    named failed 0 of 605 tests, because its fixture put the declared URL before the narrative one.
    Fixture reordered; it now bites.
  - Honesty repairs: `known_empty` claimed "every posting below is genuinely unseen" regardless of
    how old its cutoff was; an unparseable report date resolved to `current`; the cutoff advanced on
    every log *opened* rather than every day *settled* — which is exactly how it briefly asserted
    coverage of a day whose format it could not read.
  Neutralization counts after the repairs (of 617): reader 31, projection-state 9, aliases 5,
  confidence cap 4, declared-URL 1, quote-stripping 1. The last two were **0** before.
- Change set compared property-by-property against the live baseline; deployed; one ordinary
  production round run and inspected.

## Follow-ups

- `PQ-CAREER_FACTORY-056` (a "City, ST" location downgrades an onsite exclusion to a check) and
  `PQ-CAREER_FACTORY-057` (one short read costs an entire discovery feed for the round) stay open and
  are out of this packet's scope.
- Adzuna remains credential-gated, so ordinary-industry breadth is still missing from every round.
- The refresh reads evidence a human wrote. It is repeatable and it is not automatic: a submission
  made after the cutoff is not in the projection until the refresh is run again.
