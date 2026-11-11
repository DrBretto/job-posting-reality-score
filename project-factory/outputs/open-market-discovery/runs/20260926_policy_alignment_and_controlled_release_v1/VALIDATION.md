# VALIDATION — current candidate policy and controlled release (P10)

Run: `20260926_policy_alignment_and_controlled_release_v1`
Packet: `JPRS-L2-P10-policy-alignment-and-controlled-release-v01`
Executed: 2026-09-26. **Local only. No deployment, no AWS call, no invocation, no git mutation.**
P06 remains the running build and its approval is still spent.

Every claim is labeled. `evidence` means a file in `evidence/` produced by running the thing.

---

## 1. The source delta is one screening change, not a stale hash

`evidence` — `evidence/p10_policy_check_before.txt`: `policy-check` exit 1,
`changed since the projection was built: operating_plan, workflow`. Reproduced before any edit.

`evidence` — `evidence/p10_policy_source_delta.json`, per-source hashes:

| source | recorded | current | changed |
| --- | --- | --- | --- |
| `APPLICATION_WORKFLOW.md` | 15,659 B | 21,249 B | **yes** |
| `OPERATING_PLAN.md` | 5,359 B | 5,757 B | **yes** |
| `SEARCH_PREFERENCES.md` | 4,108 B | 4,108 B | no |
| `CANDIDATE_FACTS.md` | 1,462 B | 1,462 B | no |
| `MASTER_RESUME.latest.md` | 13,484 B | 13,484 B | no |

`inference` — both changed files are untracked in their own repository, so **no previous revision
exists to diff against**. The delta is therefore classified from the current text's own
operator-dated markers, not from a byte diff. Stated because it bounds the claim.

The 2026-09-26 additions are three, and **one** of them is a screening change:

| addition | kind | in scope |
| --- | --- | --- |
| *Adjacent roles: software problem-solving, not customer service* + the `Screen Before Preparing` line "Reject call-center and external customer-service/phone-support jobs" | **screening** | yes |
| *Tailoring* — reviewed role-family core-resume reuse | application process | no |
| *Backlog Catch-up and Automated Submission Pilot* | application process | no |

`evidence` — the two process additions are permissions about how MATERIALS are produced and a queued
follow-up that says of itself that it is "not permission to submit applications now or expand the
current JPRS repair packet". Neither is a new job exclusion, and neither authorizes a submission.
`OPERATING_PLAN.md`'s delta is its pointers to those two, and it states that it must not create a
second hiring policy.

`evidence` — **there was no call-center, customer-service, phone-support or help-desk handling
anywhere under `src/`** before this run (verified by search across `src/` and `tests/`; and the
reviewer independently confirmed the change is purely additive against a reconstructed pre-change
tree). So this was absent behavior. Refreshing the projection alone would have recorded the new
hashes while screening kept behaving as though the clarification had not been written.

## 2. What was implemented, and what deliberately was not

`evidence` — one new rule, `customer-service-queue`, in `src/candidate/screening.py`.
`SCREENING_RULESET_VERSION` 1.4.0 → 1.5.0; `PROJECTION_VERSION` 1.0.0 → 1.1.0; the rule added to
`RULE_SOURCE_MAP` against `workflow` + `operating_plan`.

It decides on **duty evidence in a duty span**, not a banned-word list — `support` is one of the most
common words in a job description. A finding requires a contact channel, a handling verb, and an
audience, and the audience decides the outcome:

| evidence | outcome |
| --- | --- |
| external audience (customers/clients/members/…, or an inherently external channel) | EXCLUDED, quoting the duty |
| internal audience (internal/in-house/employees/staff/…) | PENDING_CHECK — internal users are explicitly welcome |
| audience unnamed, on a queue-shaped channel | PENDING_CHECK |
| audience unnamed, on a bare channel noun | nothing — not evidence of anything |
| the channel is being BUILT, or is an artifact's subject matter | suppressed, recorded as a guarded misfire |

`evidence` — guards, each mapped to one of the clarification's own sentences: software built FOR a
support organization; software ownership generally; help-desk *documentation* as an artifact's
subject; negated duties; benefits/EEO sections; and no meeting, stakeholder or requirements
vocabulary anywhere in the patterns.

`evidence` — a call-centre title is unconditional (the policy names it without qualification). Every
other customer-service title, and every ambiguous support title, can reach PENDING_CHECK but **never
ELIGIBLE on keyword evidence** — see `INDEPENDENT_REVIEW.md` M2.

`evidence` — deliberately NOT implemented: no new salary floor, no title ban, no AI-keyword
requirement, no rule against employers that already have an engineering team, and no conversion of
"internal users are welcome" or "meetings are not the excluded work" into an exclusion. `CALIBRATION`
is unchanged. Pinned by four regressions and independently verified by the reviewer.

`evidence` — the clarification's positioning sentence ("Do not revive the Comcast/customer-service
history as a target career lane or lead positioning") governs materials, not screening, and is
correctly not implemented as a rule. No central document was edited to make any check green.

`evidence` — no scoring change was made. The captured-data audit exposed no contradiction: no
customer-service role was ever ranked into the report, so nothing in `src/scoring/` disagreed with
the current policy. Scoring and its callers are untouched.

## 3. Regressions, and whether they discriminate

`evidence` — `tests/test_adjacent_roles_and_customer_service.py`, **40 tests**, all passing.

`evidence` — `evidence/p10_prerepair_regression_check.txt`: run against a scratch copy of the tree
with this run's source edits reversed by `scripts/p10_reverse_edits_to_scratch.py` (which fails loudly
if any region it must remove is not found). **22 of the 40 fail there.** The working checkout was not
modified to produce that.

`inference` — the 18 that pass pre-change are the guard and no-new-rule tests. That is correct and is
stated rather than glossed: before the rule existed there was nothing to misfire, so those tests
protect against the change over-firing, not against its absence. They are not evidence of new
behavior and are not counted as such.

`evidence` — `evidence/p10_test_results.txt`: **433 passed**, bytecode writes disabled.
P09's run had 393.

`evidence` — `evidence/p10_preserved_coverage.txt`: the coverage the packet requires preserved is
intact and passing — the publication boundary matrix (18), owed-debt compaction (13), negative
release controls (23), discovery-to-report integration (23), the original screening suite (24),
recall/coverage including the salary-flexibility and Staff-title cases (24), and location/freshness
(44). Nothing was lowered, skipped or bypassed.

## 4. Consequences on real captured postings, by identity

`evidence` — `evidence/p10_dispositions_before.json`, `p10_dispositions_after.json`,
`p10_disposition_delta.json`, `p10_disposition_delta.txt`, produced by
`scripts/p10_disposition_audit.py` through the **real caller path** (`run_discovery` →
`_assemble_local_report` → `screen_all`), not a reimplementation.

Corpus: the captured slice at
`…/20260924_location_and_freshness_boundaries_v1/rehearsal/fixtures/` — four consecutive Himalayas
cursor pages plus Jobicy, RemoteOK and Remotive, captured from the providers' public endpoints on
2026-09-24. **No network was used.**

| | before | after |
| --- | --- | --- |
| postings considered | 282 | 282 |
| retained in the report | 11 | **11** |
| policy-excluded | 112 | 117 |
| below fit threshold | 159 | 154 |
| ruleset | 1.4.0 | 1.5.0 |

`evidence` — 11 dispositions changed: **5 newly excluded**, 6 whose reason or recorded state changed.
The retained set is **byte-identical by job id** before and after — no candidate was lost.

The five newly excluded, each with the duty evidence that justifies it:

| employer | title | evidence |
| --- | --- | --- |
| Resource Guru | Customer Support Specialist | title; body is "helping customers by email … troubleshooting issues" |
| Warehance | Customer Support & Success Specialist | title; body is "work directly with customers, investigate issues, answer technical questions" |
| Unio Digital | Tier III Service Desk Engineer | duty: MSP helpdesk for "managed service clients", technical assistance "via phone" |
| CoinGecko | Operations Associate | duty: "support to customer inquiries across channels, adhering to SLAs" — no support title at all |
| Integrated Language Solutions | Sales Support - Italian | duty: "Field Inbound Sales & Support Calls, Website Chats & Emails" |

`evidence` — the six reason/state changes are all on postings **already excluded** by another rule
(location, residency, sales, recorded video). They gained a second, more honest reason; none changed
bucket. One of them — an AI Solutions Engineer building help-desk automation — now records a
**guarded suppression** instead of an exclusion reason, which is the third misfire repair below.

`evidence` — three misfires were found by running the rule over this corpus and repaired in-run, each
pinned by a regression: an AI engineering role read as working a help desk (the software noun sat
behind adjectives); help-desk *content translation* read as answering the help desk; and a
consultant's "every phone call you answer" motivational prose read as a queue. The Sales Support
posting's verdict was correct but cited the documentation sentence; it now cites the real queue duty.

**Limits of this audit, stated rather than implied.** `evidence`:

- One captured slice from four keyless remote-job feeds on one day. It is **not** a census of open
  roles, **not** a claim about the job market, and a posting absent from it is not absent from the
  market.
- The transport is a fixture server. This is **not** evidence that the live transport works.
- Every disposition is this system's verdict on stored text, not a hiring outcome, and none of these
  postings is offered as a current vacancy.
- **The corpus could not have caught the review's largest finding.** It contains zero occurrences of
  `internal help desk` / `internal support`, and it produces **0 pending checks** for the new rule —
  so the third state is exercised by the regression suite and the reviewer's probes, and **not** by
  real data. This is exactly why a corpus audit is not a substitute for adversarial review.

## 5. The operator-facing surface

`evidence` — a real report was rendered over the captured corpus through `_assemble_local_report` and
inspected. The new rule appears under `## Excluded by candidate policy` as its own `**customer-service-queue**`
group, each row carrying the employer, the linked posting and the reason with its matched duty text.
No report code was changed: exclusions are grouped by whatever `rule_id` arrives.

`evidence` — the reviewer independently traced the caller path and confirmed markdown/JSON coherence:
`policy_excluded_count == len(policy_exclusions)`,
`below_fit_threshold_count == len(below_fit_threshold_job_ids)`, `consumed_job_ids` covering every
posting, and **nothing downstream assuming a fixed set of rule ids**.

`evidence` — one real limitation, accepted and not repaired: a posting that gets PENDING_CHECK **and**
scores below the fit band reaches no readable report section; it appears only as a bare id in
`below_fit_threshold_job_ids`. Pre-existing report architecture, but the new rule's population skews
low-fit, so "stays visible for review" is weaker than the rule's docstring implies. Changing report
ranking is outside this packet's write surface. Carried as an open item, not quietly claimed.

## 6. Independent review

`evidence` — `INDEPENDENT_REVIEW.md`. One bounded fresh-context reviewer, read-only, which read the
policy sources itself, reconstructed the pre-change tree, traced the caller path and built its own
adversarial postings. **Verdict: `revise`** — three material findings:

| finding | direction | status |
| --- | --- | --- |
| M1 — internal help-desk/service-desk ownership hard-excluded as "external customer service", in cases whose own evidence text said *internal* | false exclusion on the protected population | **repaired, rechecked, pinned by 3 tests** |
| M2 — a call-center/customer-service title cleared to ELIGIBLE by any software verb anywhere in the description | false pass on a stated hard exclusion | **repaired, rechecked, pinned by 2 tests** |
| M3 — ordinary external-support phrasings missed, one with no evidence recorded at all | silent pass | **repaired, rechecked, pinned by 3 tests** |

Plus `n2` (a pre-existing rule missing from the projection's rule map) repaired, `n1` partly
addressed by ranking duty evidence, and `m1`/`m2`/`n3` accepted and recorded as limitations rather
than repaired. All 19 of the reviewer's reproduction cases were re-run after the repair; the full
before/after table is in `INDEPENDENT_REVIEW.md`.

`inference` — this is the finding a corpus audit structurally cannot produce. The audit measured what
the rule did to 282 real postings and found it sound; the reviewer's own one-sentence postings found
it hard-excluding the population the clarification was written to open up. Both were needed.

## 7. Build, baseline and release checks — all re-run AFTER the repairs

`evidence` — every check below ran against the post-review source
(`src` fingerprint `356c0ad140beae546c297081c529a1e7`), not the pre-repair code.

| check | result | file |
| --- | --- | --- |
| `policy-check` | **exit 0**, "projection matches all policy sources" | `evidence/p10_policy_check_after.txt` |
| projection rebuild | 5 sources, 9 mapped rules, `1.1.0` | `evidence/p10_policy_refresh.txt` |
| full test suite | **433 passed** | `evidence/p10_test_results.txt` |
| `sam validate --lint` | valid SAM template | `evidence/p10_sam_validate_and_build.txt` |
| `sam build` | Build Succeeded, six functions | same |
| P06 baseline reconstruction | `BASELINE_VERIFIED` 36/36, then `BASELINE_BUILD_READY` | `evidence/p10_reconstruct_p06_baseline.txt` |
| release preflight, all 6 steps | **PREFLIGHT PASSED**, `CHANGE_SET_IS_CODE_ONLY`, 6 of 6 artifacts, application code only | `evidence/p10_release_preflight.txt` |
| rollback preflight | **exit 0**; working tree `src/` fingerprint identical before and after | `evidence/p10_rollback_preflight.txt` |
| identity binding | tested source ↔ projection ↔ candidate build ↔ baseline build | `evidence/p10_release_identity.json` |

`evidence` — the refreshed projection is packaged into **all six** function artifacts with a hash
equal to the working-tree file. This matters because the local package comparison **cannot** evidence
it: the reconstructed baseline carries the current tree outside `src/`, so
`config/candidate_policy.json` is identical on both sides by construction. Labeled separately in the
identity record and in the handoff rather than folded into the code-only verdict.

`evidence` — the baseline reconstruction also confirms `infra/template.yaml`,
`infra/samconfig.toml` and `config/discovery_sources.yaml` are unchanged from what P06 recorded.

`evidence` — two honest notes, both carried forward from P09 and still true: the reconstructed
baseline differs from the real P06 artifact in repository payload outside `src/` (classified payload,
not infrastructure, and printed as such), and `src/.DS_Store` is genuinely packaged into the Lambda
artifacts.

`evidence` — environment note: `sam` could not write its own global config at
`~/.aws-sam/metadata.json` (sandbox write denial on a path outside the project). It prints a
traceback and continues; the template validated and the build succeeded. Not a build failure, and
not repaired here.

`evidence` — the release preflight's 7-case fail-closed drill was **not** re-run in this run. The
script is unchanged by this run and P09's drill (`evidence/p09_preflight_drill.txt`) stands. Stated
so the coverage is not overclaimed.

## What this run does NOT claim

- **No deployment, no AWS call, no invocation, no change-set execution, no email, no application, no
  git branch/stage/commit/push/reset/stash.** No deployment authorization existed at any point in
  this run, and none is implied by any file in it.
- **No live success of any kind.** Every posting exercised here is either a synthetic control or a
  2026-09-24 captured record. The insurance, benefits and support companies named in the audit are
  captured records and test controls, **not** vacancies to apply to.
- The positive product condition — a real job from a registry-absent employer, from a live feed, in a
  report actually delivered to Brett — is **not met by this run and must not be reported as met**.
- Local tests, code deployment, real ingestion, actual delivery and unattended behavior remain five
  distinct claims. Only the first is addressed here.
- The 2026-09-26 unattended round (discovery 07:05) was not checked. It runs P06's code, so it says
  nothing about this change either way.
- No application was submitted, no employer contacted, no resume generated, and no part of the
  submission pilot was built or started.
- Nothing here makes two simultaneous discovery invocations safe; that non-claim from P09 is
  unchanged.
