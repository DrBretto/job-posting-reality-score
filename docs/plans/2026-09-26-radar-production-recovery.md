# 2026-09-26 — Radar production recovery (discovery init + report publication)

## Context

P10 was deployed to `jprs-v1` on 2026-09-26 at 14:22Z by the Career Factory release run
(`book-factory/runs/20260926_career-radar-release-and-application-catchup-v1/` in the Infotropy
repository). The working tree's `src/`, `infra/template.yaml` and `config/candidate_policy.json` are
byte-identical to the deployed artifact (all five functions share one CodeSha256). Two production
defects followed, both reproduced from live logs and real inputs before any edit:

1. **Discovery cannot start.** `persist()` first reads every feed's owed-publication object
   (`discovery/owed/provider=<p>/owed_publication.json`) and the legacy aggregate. None has ever
   been written. `DiscoveryFunctionRole` holds `s3:GetObject` on `discovery/*` but no
   `s3:ListBucket`, so S3 answers a missing key with 403 AccessDenied, not 404
   ([GetObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html)).
   `_load_optional` correctly refuses to read 403 as absence, so the object can never be created:
   a deadlock. Live log, 10:27:58 EDT: `not authorized to perform: s3:ListBucket`.
2. **The report cannot publish.** Reproduced read-only against the real 2026-09-26 inputs. Two
   causes, and the title is only the second:
   - the differ's own SOURCE_SEGMENT_CLOSED note says "Treating this as a real closure". That is
     SYSTEM-authored text, rendered verbatim into the digest and the JSON event copy, and the guard
     is right to reject it as published language. It is the first hit (pos 3013 locally, 3120 live).
   - the title "Senior FullStack Engineer - Real User Monitoring (RUM) | … | …" contains `|`.
     Markdown escaping turns it into `\|`, so the exact-match source redaction misses it and the
     guard reads a sourced word as a system claim.

Why a scoped `ListBucket` is sound: the REPORT role already holds `s3:ListBucket` conditioned on
`s3:prefix` `discovery/*`, and at 10:29–10:34 EDT under P10 it read four never-written
`discovery/live/provider=*/live_jobs.json` keys through a loader that raises on AccessDenied, and
got past them to the render step. So a prefix-conditioned grant yields 404 for missing keys under
that prefix in this account. The same statement shape on the discovery role turns absence into 404
while a genuine denial on an existing object stays 403 and still raises.

## Plan

- [x] Reproduce both faults from live logs and real inputs; pin live identity; archive the live tree.
- [x] Failure-first regressions (`tests/test_production_recovery.py`) with an S3 double that applies
      the TEMPLATE's own IAM statements and S3's documented 403/404 rule.
- [x] `infra/template.yaml`: one statement, `DiscoveryListOwnPrefix` — `s3:ListBucket` on the bucket,
      conditioned on `s3:prefix` `discovery/*`. Nothing else in IAM changes.
- [x] `src/discovery/handler.py`: traversal state and growth ledger are read strictly. A denied or
      failed read of an EXISTING object now stops the run instead of silently starting from an
      empty ledger and then overwriting it. The manifest stays lenient (advisory only, and under
      `runs/` where discovery has no list grant).
- [x] `src/report/handler.py`: redact the rendered forms of source text (Markdown-escaped and
      JSON-escaped), and publish an upstream event note only when it passes the vocabulary rule —
      otherwise say it was withheld and point at the durable event record. Report-authored text is
      still checked exactly as before.
- [x] `scripts/check_release_change_set.py`: compare against the version live NOW and accept an
      infrastructure delta only when it is DECLARED exactly; report it either way.
- [x] Independent review of the changed code and tests; repair material findings.
- [x] Deployment approval, controlled release, ordinary live round (operator-gated).

## Execution Log

- 2026-09-26: faults reproduced (evidence in the governed run directory
  `book-factory/runs/20260926_career-radar-production-recovery-v1/evidence/`). Live P10 tree
  archived there with a per-file hash manifest before any edit.

- 2026-09-26: implemented the plan; 26 new regressions, 17 of them failing on the live P10 tree.
- 2026-09-26: independent review returned two material findings, both repaired:
  (M1) discovery no longer infers absence from a failed GetObject at all — optional reads list the
  exact key first (a request that carries `s3:prefix`, so the conditioned grant matches by
  definition), then read; a test proves discovery initializes even if S3 ignored the conditioned
  grant for a missing-key GetObject. (M2) a differ DISAPPEARED note quotes the posting's department
  in lowercase; the report now takes department/team/title from each board's differ state (which
  includes disappeared postings) into the redaction set. Minor repairs: per-object unavailable-read
  tests, gate covers the state-machine definition and fails a declared-but-unchanged file, an
  unreadable manifest skips admission instead of deciding against a count of zero, withheld notes
  are listed and logged.
- 2026-09-26: the real-data replay then caught a regression in the redaction itself: a short source
  value ("it") cut out of "Reality" manufactured "Real". The guard now finds guarded-word hits first
  and excuses a hit only inside a whole-token occurrence of source text containing that word
  (0.10 s on the real 2.7 MB report). 484 tests pass; the real 2026-09-26 inputs render.
- 2026-09-26: gate against the reconstructed live baseline and live identity:
  `CHANGE_SET_IS_CODE_PLUS_DECLARED_INFRASTRUCTURE`, 5 declared template differences, all observed,
  nothing undeclared.

- 2026-09-26 18:24Z: operator approved deploy + one ordinary round. AWS change set diffed against
  the live processed template: exactly 6 function code keys + the 5 properties of the one statement.
  Executed; stack UPDATE_COMPLETE 18:27Z; deployed `src/` byte-identical to the tested tree.
- 2026-09-26 18:28–18:30Z: discovery invoked (4/4 feeds, 297 jobs, live views written, nothing owed),
  then `jprs-daily-assemble` execution `recovery-verify-2026-09-26` SUCCEEDED (15/15, 56 retained,
  digest sent). `inspect_discovery_integration.py`: `ACCEPTANCE_MET`.
- Not committed or pushed: both working trees preserved per the governing packet.

## Follow-ups

- The first UNATTENDED scheduled round (07:05 discovery / 09:00 assemble) after this release has not
  been observed.

- The differ authors "real closure" in `src/differ/handler.py`. The differ is outside this repair's
  edit surface; the report now withholds such a note rather than publishing it, but the wording
  itself should become behavioral ("treating the segment as closed").
- A source value that is itself a bare guarded word (an employer named "Ghost", a department named
  "Fraud") still excuses that word wherever it appears as a whole token, including in system text.
  Not observed; stated as a known limit.
- The report has no list grant on `current/` or `events/`: a registry board whose collection never
  produced a status (so the differ skipped it) or whose first fetch failed makes the report fail
  with AccessDenied rather than read an empty set. Pre-existing; loud rather than silent.
