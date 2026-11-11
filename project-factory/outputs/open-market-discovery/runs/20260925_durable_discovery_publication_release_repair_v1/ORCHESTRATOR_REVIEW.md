# P08 independent return review — 2026-09-25

Action: run-return / evidence / bounded successor packet.
Outcome: **revise_implementation**. P08 completed its local run, but its release conclusion is not
adopted. Preserve its useful changes and the original executor evidence. Production remains P06;
no deployment, invocation, AWS access or git mutation occurred in this review.

## What holds

Evidence from independent re-execution against the current working tree:

- Full suite: **350 passed in 13.51s**, with bytecode/cache writes disabled.
- The original P07 interruption probe, unchanged, now retains the job on both the same-run retry
  and following report. P08 fixed the failing LIVE-VIEW write case.
- Policy projection matches all policy sources.
- All five P08 inspection controls reproduce their stated verdicts locally.
- All **36 archived P06 source files match their recorded hashes**, directly checked inside the
  tar archive without restoring the working tree. The other 36 archive members are AppleDouble
  `._` metadata files, not extra application modules. Current template/config match P06 hashes.
- Shared packaging explains changes to all six function artifacts. A two-function-only stop rule
  would still be wrong. The archive is saved on disk, not committed; HEAD remains `e549a73`.

No fresh SAM build or live transport check was run by this review. Their P08 receipts remain
executor evidence, not independently repeated cloud evidence. Synthetic employers are not vacancies.

## R1 — recovery still starts after the first durable capture

Evidence: `evidence/p08_independent_pending_boundary_probe.py` and `.json`.

The probe adapts only the storage-fault location in P07's independent harness: refuse the FIRST
`PutObject(discovery/_pending_publication.json)` instead of the live-view write. Coverage/state reads
that cannot exist yet are omitted, not fabricated. Real enumerate/collector/discovery/differ/report
code produces intermediates; AWS and provider transport are mocked. The retry and following run both
receive an empty feed.

| Observation | No failure | First pending-ledger write fails once |
| --- | --- | --- |
| synthetic `himalayas:all#internal-tools` already normalized | yes | yes |
| candidate in same-run retry report | yes | no |
| candidate in following report | yes | no |
| raw snapshot objects retained | 3 | 3 |

Cause: `persist()` writes raw/normalized/status/SUCCESS before `owe_publication()` makes recovery
discoverable. When that first ledger write fails, later attempts see no owed work and overwrite the
same-day normalized input. The raw evidence survives, but the ordinary path cannot recover it.
This is not a claim that every physical copy is deleted. It is a reproduced lost opportunity in the
morning report, inside P08's promised persistence-boundary invariant.

Related source-supported defect: `PendingPublication.owe()` evicts the oldest batch above FIVE,
before the drain runs. P08's test explicitly requires that eviction. Logging the discarded job IDs
does not deliver them or preserve automated recovery. Even the first healthy recovery round can
evict the oldest debt when it enqueues the next batch. No independent multi-day eviction probe was
run in this review; this finding rests on the implementation and its explicit regression test.

Repair the commit/recovery boundary rather than one exception handler. Cover the finite write
sequence with fault injection, including the first owed write and failure after a successful write
with an ambiguous response. Distinguish a job never durably accepted from one durably accepted but
not yet delivered. Bounded storage must not abandon accepted, unpublished jobs by batch-count eviction.

## R2 — release checks admit false-green controls

Evidence: `evidence/p08_independent_release_gate_probe.py` and `.json`. These are deliberately
modified local fixtures for testing the checkers, not evidence of a production infrastructure change
or a production job disappearing.

### Package check

With identical application files but a built template whose IAM role property changes from 3600
to 7200, `p08_package_scope.py` exits **0 / CHANGE_SET_IS_CODE_ONLY**. It prints the template difference
but ignores it. `infra_source_changed` is initialized false and never assigned; current source hashes
are printed rather than compared to recorded values. Added/removed functions also only print.

The actual current template/config DO match P06. The defect is the prospective guard, not an
observed unauthorized IAM edit. Require a failing status for a prohibited resource/config difference,
unknown baseline or missing comparison; allow genuine build-path/CodeUri changes precisely. A local
comparison is not an actual AWS change set and must not be named as though it is.

### Per-job live inspection

Starting from P08's A fixture, add one stored synthetic job from the same employer, absent from the
report. The report has one consumed candidate and **zero below-fit jobs**. The check labels the
absent job `consumed-unlisted / below the fit threshold` and exits 0 / ACCEPTANCE_MET anyway.

Cause: membership in `previously_unseen_employers` is treated as proof that EACH job from that
employer was consumed. It is not. The existing missing-ingestion branch also fails only when no
discovery evidence was consumed, so mixed successful/missing inputs can be passed. Preserve a
positive witness separately, but do not call the complete reconciliation healthy when identities
are missing. Add minimal per-ID dispositions at the real consumer if the report lacks the evidence.

## Release handoff qualifications to address in the same bounded work

- Forward verification still names a temporary P06 build directory. Use the verified persisted
  baseline or reconstruct/validate what the check needs without assuming that directory survives.
- Rollback hash verification prints MISMATCH without a failing exit. Verification must halt the
  sequence before restore/deploy; rehearse with a corrupted archive in scratch, never this tree.
- The live-input loop neither initializes LIVE nor uses an argument array; commands should run in
  an explicitly selected shell and propagate failed checks. Missing expected inputs are not a pass.
- A current live view and older report are not automatically the same population. Bind inspection
  to coherent run inputs. Saved-report presence, delivered email and next-day behavior are separate.

These are corrections to the release surface under review, not a packaging redesign or general audit.

## Next

One staged successor: `JPRS-L2-P09-publication-commit-boundary-and-verification-v01`.
Keep P07 integration and P08 replay/baseline work. No new committee, sources, candidate-policy edits,
credentials or AWS actions. Stop after the named local repairs, before fresh deployment authorization.
