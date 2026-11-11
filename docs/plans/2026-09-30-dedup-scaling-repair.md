# Remove the radar's global survivor-pair cleanup scan

Packet: `PKT-CAREER-RADAR-DEDUP-SCALING-REPAIR-V1-20260930`
Run: `20260930_career-radar-dedup-scaling-repair-v1`
Started 2026-09-30.

## Context

The morning report was restored on 2026-09-30 by raising `ReportFunction`'s timeout 90 → 300s. That
was a capacity patch, not a repair, and the two production runs since show why:

| date | input postings | elapsed | budget | headroom | s / 1k postings |
|---|---|---|---|---|---|
| 2026-09-29 | 1,344 | 188.52s | 298.97s | 36.9% | 140.27 |
| 2026-09-30 | 1,526 | 226.74s | 298.46s | **24.0%** | 148.58 |

**In one day the corpus grew 13.5% and the runtime grew 20.3%.** Headroom fell from 36.9% to 24.0%.
The per-1,000 rate rose, which is the signature of a superlinear term rather than a bigger corpus.

Fitting `T = a·n² + b·n` through those two points gives a ≈ 4.57e-5, b ≈ 0.0789, putting the 300s
ceiling near **n ≈ 1,835** — about **two days** at the observed +182/day. *Two points fitted to two
parameters is an exact fit and therefore not independent evidence;* it is a bounded projection. The
load-bearing claim in this run is the deterministic operation count, not this curve.

### What the quadratic actually is

`deduplicate` ends with a cleanup pass over **every ordered pair of survivors**
(`src/common/dedup.py:256-265`), normalizing both employer names per pair. That is the 3,613,995
`normalize_employer` calls the predecessor profiled.

Its *purpose* is narrow and correct: remove a soft `possible_duplicate_of` link between two records
at the same employer whose requisition ids differ, so two genuinely distinct openings are not
presented as possible duplicates.

Its *effect* is bounded by the links that already exist, because the removal only fires when
`other.job_id` is already in `job.possible_duplicate_of`. **On today's real corpus that is 4 soft
links and 1 blocked reason — so the scan performs 1,526² = 2,328,676 ordered pair comparisons to
police 4 links.**

That gap between cost and effect is the whole defect. Caching `normalize_employer` would make each
of the 2.3M comparisons cheaper and leave the scan quadratic, which is why the packet rules a
cache-only change insufficient.

## Plan

- [x] Freeze the before implementation and the real pre-dedup corpus (intercepted inside the ordinary
      read-only assembly path, serialised *before* the call, because `deduplicate` mutates its
      arguments and the saved `daily_report` is its output).
- [x] Replace the global scan with a link-driven pass: index survivors by `job_id`, precompute one
      normalized employer key per record, and walk each record's existing `possible_duplicate_of`.
- [x] Prove behavior equality on independently copied inputs — real corpus plus the hard synthetic
      cases (distinct requisitions at one employer, missing requisition ids, employer suffixes and
      empty names, absent hard keys and group ids, eligibility variants, multiple ATS hosts, shared
      URLs, pre-populated stale links, existing provenance, repeated calls).
- [x] Scaling: deterministic operation counts plus unprofiled timing at increasing sizes, including a
      sparse corpus, a many-jobs-one-employer corpus, and a deliberately dense duplicate bucket.
      Tests must fail against the old implementation **and** against a cache-only placebo.
- [x] Independent review aimed at breaking equivalence and the scaling claim.
- [x] Full suite, policy-check, fresh SAM validate/build; release prepared against what is live now.
- [x] Present measured result and request explicit deployment approval. Do not execute a change set
      while awaiting it. *(Approved; deployed 14:16:48Z and verified — see Closeout below.)*

## Execution Log

**Baseline.** Live now: `Timeout=300`, `MemorySize=512`, CodeSha256
`Q7azuKmLMnOyWhu8ySckvldqCjps6r4v5ZvbrkvDHh0=`, stack updated 2026-09-30T07:20:08Z. HEAD is *not* a
reliable baseline — the working tree carries several earlier uncommitted releases — so identity was
recovered from the deployed function and stack rather than from git.

Real corpus captured from live production: **1,526 input jobs, 1,526 kept, 0 hard merges, 4 soft
links, 1 blocked reason, dedup 7.35s locally.** That dedup report is the equivalence target.

**The repair.** The cleanup is now driven by the links instead of by the pairs: survivors are indexed
by `job_id`, one normalized employer key is computed per record, and each record's own
`possible_duplicate_of` is walked. Every guard the pair scan applied is applied, against the same
values, in the same order — including the two that a plausible rewrite gets wrong:

- `dedup_group_id` equality is a bare `==`, so two records that both carry `None` compare equal and
  are **skipped**. A truthiness guard would start unlinking them.
- exactly **one** occurrence is removed per (job, other) *object* pair, because `list.remove` took
  the first match and the pair scan visited each pair once. A rewrite that iterates the link list and
  removes every match diverges on a list carrying the same id twice.

**Equivalence.** Frozen original vs repaired, independently deserialised inputs for each (the
function mutates its arguments, so they cannot share objects). Compared: survivor identity *and
order*, the full `DedupReport` including `blocked_links`, and every mutated field on every input
record — not only survivors, because an absorbed loser's `duplicate_of` is part of the behavior.
**16 cases, all equivalent**: the real corpus, a second pass over its own output, and 14 synthetic
cases the real corpus does not exercise (distinct requisitions at one employer, one-sided
requisition ids, employer suffix variants, empty employer names, both group ids `None`, a
pre-populated stale link, a duplicated id in the link list, a link to an absent job, eligibility
variants, two ATS hosts, a shared apply URL, two survivors sharing a `job_id`, a dense bucket, a
dense bucket with distinct requisitions).

**Scaling.** Instrument counts reads of `employer_name` via a `CanonicalJob` subclass, because
counting `normalize_employer` calls cannot separate the old scan from a memoized one — a cache still
has to read both names to look the result up.

| n | shipped | old global scan | cache-only placebo | 2n² |
|---|---|---|---|---|
| 60 | 120 | 7,080 | 7,080 | 7,200 |
| 240 | 480 | 114,720 | 114,720 | 115,200 |
| 480 | 960 | 459,840 | 459,840 | 460,800 |

**Timing**, unprofiled (cProfile's per-call overhead flatters a repair that removes millions of
calls): `deduplicate` on the real 1,526-posting corpus **7.342s → 0.023s**; growth per doubling
**~4.1x → ~2.0x**. Whole-report assembly on the identical corpus **24.907s → 17.023s**, the before
figure measured while the original was still in place rather than subtracted.

**Checks:** 659 tests pass (638 inherited + 21 added). `sam validate --lint` valid. Fresh build: six
packages byte-identical to each other. Source delta against the *live deployed package*: exactly one
file. Processed-template diff vs live: 6 code keys, **0 non-code differences**, `Timeout` 300 and
`MemorySize` 512 preserved.

**`policy-check` exits 1** — `changed since the projection was built: operating_plan`. Unrelated to
this repair: `OPERATING_PLAN.md` was edited at 09:48 today with a new operator direction about
delegated outreach sending, and the committed projection was built 2026-09-28. The hash was **not**
refreshed; `config/candidate_policy.json` is outside this run's write surface and the packet forbids
refreshing it to make the gate green. Recorded as an honest hold.

## Follow-ups

- **`policy-check` is red on operating-plan drift** and production screening is running against the
  pre-edit projection. Whether that is substantively stale or only digest-stale depends on whether
  the new paragraph changes a screening rule or only outreach send authority; it reads as the latter.
  Owned by whichever thread owns outreach, not by this one.
- **The soft-link tier is unchanged and remains pairwise within a bucket.** That is inherent output,
  not avoidable work, and no attempt was made to shortcut it.
- **No new capacity ceiling is claimed.** The predecessor's ~2,400 and the return's ~1,990 were both
  extrapolations; today's two production points give ~1,835 by an exact two-point fit, which is not
  independent evidence either. What is established is that the dedup stage's *shape* changed from
  quadratic to linear over a measured 4x range.
- `PQ-CAREER_FACTORY-087` stays open until the repair is verified in production.
- `PQ-CAREER_FACTORY-088` (the alarm that has never been able to fire), `-089`, `-090` and Adzuna are
  untouched by this run.

## Closeout — 2026-09-30

**Deployed and verified.** Stack updated 14:16:48Z; the verification round measured
**226.74s → 140.11s** on the identical 1,526-posting corpus, headroom **24.0% → 53.1%**,
seconds-per-1,000 **148.58 → 91.82**, with 13 of 13 report fields and every job-id set identical
before and after. That is about **38% less elapsed time** — not "twice as fast", which an earlier
summary of this work overstated.

**The `policy-check` hold is cleared, by separate authorization.** A follow-up packet
(`PKT-CAREER-POLICY-PROJECTION-REFRESH-AND-CLOSEOUT-V1-20260930`) refreshed
`config/candidate_policy.json` through the existing `policy-refresh` generator. Only `built_at` and
the `operating_plan` source ref moved; projection version, rule mappings, calibration, note and the
other four source hashes are identical. **`policy-check` exits 0.** 666 tests, `sam validate --lint`
and a fresh build all pass.

The refresh is **local metadata and was not deployed**. Production still carries the 2026-09-28
projection, and its screening behavior was already verified unchanged. Screening rules are hardcoded
Python — nothing parses the operating plan at runtime — and the three rules mapped to that source
keep their stated basis at unmoved lines in the document.

The follow-ups listed above are unchanged and remain open: the dormant `jprs-A3` alarm, the
aggregator-title suppression risk, the held-record dedupe key, the packaging of `tests/` and `docs/`
into the runtime artifact, and Adzuna's credential.
