# INDEPENDENT_REVIEW — bounded fresh-context review of the P10 policy change

One bounded reviewer, fresh context, read-only on the repository, scratch work under `$TMPDIR` only.
It was given the policy sources as the authority and told to find defects, not to approve. It read
the sources itself, reconstructed the pre-change tree with this run's own reversal script, traced the
caller path through `src/report/handler.py` and `src/cli.py`, and built its own adversarial postings
rather than reusing the test file's.

**Verdict returned: `revise`** — three material findings, two of them in opposite directions.
All three are reproduced below, repaired, and pinned by regressions. The reviewer's own reproduction
cases are the regression cases.

---

## M1 — internal help-desk ownership was hard-excluded as "external customer service"

**Severity: material. A false hard exclusion on exactly the population the clarification opens up.**

`_CS_SELF_EVIDENT_CHANNEL_RE` listed `help desk`, `service desk`, `support desk` and
`support tickets|queue|inbox|cases` as channels that carry their own EXTERNAL audience. A help desk
is the canonical *internal* IT function, so that inverted the rule's hinge. The internal-audience
check that was supposed to win first required specific nouns (`internal users`, `employees`, …) and
did not match `internal help desk`, `internal service desk queue` or `helpdesk requests … for our
ERP system`.

Reproduced, all `EXCLUDED` before the repair:

| title | duty text | before | after |
| --- | --- | --- | --- |
| IT Systems Engineer | manage the **internal** service desk queue | EXCLUDED | PENDING_CHECK |
| Business Applications Engineer | handle the **internal** helpdesk requests for our ERP system | EXCLUDED | PENDING_CHECK |
| DevOps Engineer | resolve support tickets raised by **staff** and automate our deploys | EXCLUDED | PENDING_CHECK |
| IT Engineer | cover the service desk queue on a rotation; build PowerShell automation | EXCLUDED | PENDING_CHECK |
| IT Operations Engineer | 400 **employees**; manage the help desk and write automation scripts | EXCLUDED | PENDING_CHECK |
| Systems Engineer | automate device provisioning, and handle help desk tickets escalated to you | EXCLUDED | PENDING_CHECK |
| IT Systems Engineer (long form) | troubleshoot problems reported by **staff**, manage the internal service desk queue, automate onboarding | EXCLUDED | PENDING_CHECK |

The reviewer also noted the sharpest form of this: **the recorded evidence contradicted the verdict
it was offered as proof of** — `matched_text` containing the word *internal* under a reason asserting
"external customer-contact queue".

Contradicted: *"Internal users and stakeholders are welcome"* and *"distinguish software-building and
internal problem ownership from an external customer-support queue or call-center role."*

**Repair.** Help-desk/service-desk/support-queue channels are no longer self-evidently external; they
remain queue-*shaped*, so with no stated audience they route to PENDING_CHECK. The internal-audience
pattern is now broad (`internal`, `in-house`, `employees`, `staff`, `colleagues`, …) and is still
checked first. Pinned by `test_internal_help_desk_ownership_is_never_hard_excluded`,
`test_internal_help_desk_ownership_stays_visible_for_review`, and
`test_no_exclusion_reason_claims_external_about_evidence_that_says_internal`.

**Why the original tests missed it:** the existing internal-queue test supplied the exact nouns the
narrow pattern needed, in the same duty span. It validated one phrasing, not the mechanism.

---

## M2 — a call-center / customer-service TITLE was cleared to ELIGIBLE by one software verb anywhere

**Severity: material. A false pass on a stated hard exclusion.**

`cs_software` was computed at description scope, and both title branches suppressed to `ELIGIBLE`
when it was true and no queue duty had matched. This is the description-scope mistake the module's
own docstring says it learned not to make — `collect_queue_duties` was duty-span scoped, the title
branches were not.

Reproduced, all `ELIGIBLE` before the repair; eleven cases, including:

| title | duty text | before | after |
| --- | --- | --- | --- |
| Call Center Representative | answer telephone enquiries from our customers all day; also build reports | ELIGIBLE | EXCLUDED |
| Call Center Agent | write scripts to help yourself work faster; speak with people all day | ELIGIBLE | EXCLUDED |
| Contact Centre Advisor | take telephone enquiries from members; maintain scripts | ELIGIBLE | EXCLUDED |
| Customer Service Representative | speak with our customers on the telephone; configure systems | ELIGIBLE | EXCLUDED |
| Customer Service Representative | build reports in Excel and speak with our customers daily | ELIGIBLE | EXCLUDED |
| Help Desk Analyst | first-line assistance to our clients over the telephone; maintain scripts | ELIGIBLE | EXCLUDED |
| Customer Support Engineer | answer telephone enquiries from our customers; develop internal tools | ELIGIBLE | EXCLUDED |
| Service Desk Advisor | telephone assistance to our customers; maintain reporting | ELIGIBLE | EXCLUDED |
| Application Support Analyst | answer their questions by telephone and live chat; write scripts | ELIGIBLE | PENDING_CHECK |
| Customer Care Associate | develop workflows and maintain our documentation | ELIGIBLE | PENDING_CHECK |
| Member Services Coordinator | build integrations between our CRM and billing platform | ELIGIBLE | PENDING_CHECK |

Contradicted: *"Reject call-center and external customer-service/phone-support jobs"* and *"An
application-support or IT title is not a fit merely because it sounds easier to obtain."* The
ambiguous-title branch was the direct inverse of that second sentence.

**Repair.** No title branch returns `ELIGIBLE` on keyword evidence any more.

- A call-centre title (`call center`, `contact centre`, `kundenservice`) is unconditional — the
  policy names it without qualification, so nothing in the body downgrades it.
- Any other customer-service title with software-shaped duties and no queue duty is
  `PENDING_CHECK`, not a pass: read the posting.
- A support-shaped (ambiguous) title is cleared only when software ownership is present **and** no
  contact-channel vocabulary appears anywhere in the role sections; otherwise `PENDING_CHECK`.

Pinned by `test_a_call_center_title_is_not_cleared_by_a_software_sentence` and
`test_a_customer_service_title_is_never_returned_as_eligible_on_keyword_evidence`.

The three cases that land on `PENDING_CHECK` rather than `EXCLUDED` are stated as such rather than
claimed as fixed to a verdict: their audience is genuinely unnamed in the sentence that carries the
channel, and the alternative — widening audience detection to whole-segment scope — would let one
mention of the word *customer* anywhere turn an engineer's ticket-queue sentence into an external
exclusion. Visible for review is the honest answer, and it is the policy's own instruction.

---

## M3 — ordinary external-support phrasings were missed, one of them silently

**Severity: material. One clean miss with no evidence recorded at all.**

The channel list had `telephone support` and `phone calls` but not `telephone enquiries`,
`telephone assistance`, `first-line assistance`, `questions from customers by phone`, `emails from
our clients`, or `by/over the telephone`. Separately, `_DUTY_SPLIT_RE` splits on ` and `, so
`"answer phone calls and emails from our customers"` put the channel in one duty span and its
audience in another; the finding was then discarded as audience-unstated.

| title | duty text | before | after |
| --- | --- | --- | --- |
| Support Consultant | answer phone calls and emails from our customers | **ELIGIBLE, nothing recorded** | EXCLUDED |
| Technical Support Specialist | answer phone calls and emails from our customers, troubleshoot their account problems | PENDING (title only) | EXCLUDED (duty evidence) |
| Support Advisor | answer telephone enquiries from our customers | PENDING (title only) | EXCLUDED |
| Product Support Analyst | field questions from customers by phone all day | PENDING (title only) | EXCLUDED |
| Operations Support Analyst | respond to emails from our clients and log each one | PENDING (title only) | EXCLUDED |

**Repair.** The channel list covers those phrasings, and **audience is now read at clause scope while
guards stay duty-span scoped**. That asymmetry is deliberate and is the finding's real lesson: whose
contacts these are is a property of the sentence, but a "build internal tools" sentence must not
excuse a support-queue duty stated beside it. Pinned by
`test_ordinary_external_support_phrasings_are_not_silently_passed`,
`test_an_audience_split_across_a_coordinator_is_still_found`, and — guarding the widening itself —
`test_the_guards_are_still_duty_span_scoped_after_that_widening`.

---

## Minor findings and notes

| id | finding | disposition |
| --- | --- | --- |
| m1 | A `PENDING_CHECK` posting that also scores below the fit band never reaches a readable report section — it appears only as a bare id in `below_fit_threshold_job_ids`. Pre-existing report architecture, but the new rule's population skews low-fit, so "stays visible for review" is weaker than the rule's docstring implies. | **Accepted as a real limitation, not repaired.** Changing report ranking is outside this packet's write surface and needs no new rule to fix. Stated plainly in `OPERATOR_RETURN.md` and carried as an open item rather than left as an overclaim. |
| m2 | The captured corpus contains zero occurrences of `internal help desk`/`internal support`, so the before/after audit could not have detected M1, and it produces **0 pending checks** for the new rule — the third state is unexercised against real data. | **Accepted and stated.** The audit's evidence value is bounded accordingly in `VALIDATION.md` §4. This is why a corpus audit is not a substitute for adversarial review. |
| n1 | The MSP case recorded the weaker of two valid duty sentences. | **Partly repaired.** Duties are now ranked so a span naming the audience outright is reported first. Both of that posting's spans name `clients`, so the ranking does not separate them further; not pursued. |
| n2 | `location-residency` is emitted by the location logic but was missing from `RULE_SOURCE_MAP`, so the projection did not record its derivation. Pre-existing; one line from the map this change touched. | **Repaired.** Added, projection rebuilt (9 mapped rules). Pinned by `test_note_the_missing_location_rule_is_now_mapped`. |
| n3 | Theoretical: an entity-encoded title containing a `BANNED_TOKENS` word could fail `_assert_report_language`, because the title branches record the whole unescaped title while other rules record only the matched phrase. Reasoned from code, **not** demonstrated; connectors normalize titles at ingest, so it may be unreachable. | **Not repaired, and not dismissed.** Recorded as an unverified theoretical path. No live repro was produced by the reviewer or by this run. |

---

## What the reviewer checked and found correct

Recorded because the coverage of a review is part of its value:

- **Purely additive change.** Diffed against the reconstructed pre-change tree: five hunks, the only
  removed lines being the version string and two renumbered comments; only
  `src/candidate/screening.py` and `src/candidate/policy.py` touched.
- **No over-implementation.** Verified absent: any new salary floor or compensation gate
  (`CALIBRATION` unchanged, `compensation_is_a_gate: false`); any title ban beyond the two CS title
  families; any AI-keyword requirement (a posting with zero AI wording → ELIGIBLE); any rule
  rejecting employers that already have an engineering team; any conversion of "internal users are
  welcome" or "meetings are not the excluded work" into an exclusion. The clarification's
  positioning sentence about not reviving the customer-service history as a career lane is correctly
  **not** implemented as a screening rule — it governs materials, not screening.
- **Caller path traced end to end**, not just the helper: `EXCLUDED` drops from `_ranked` and renders
  under `## Excluded by candidate policy` grouped by `rule_id`; markdown and JSON agree;
  `consumed_job_ids` covers every posting; `policy_excluded_count == len(policy_exclusions)`;
  `below_fit_threshold_count == len(below_fit_threshold_job_ids)`. **Nothing downstream assumes a
  fixed set of rule ids** — they appear only as `RULE_SOURCE_MAP` keys (provenance, never a gate).
  The new reason strings contain no banned vocabulary.
- **Guards that hold**: benefits and EEO blocks mentioning support; negated support duties;
  supporting a *service or system* rather than people; building contact-centre software; a
  full-stack role whose users are customers; implementation calls with clients; a data pipeline
  processing inbound files; a DevOps role triaging internal engineers' tickets.
- **Obvious external-CS roles correctly excluded with duty evidence**, six independent cases.
- **Real-corpus sweep**: all nine corpus exclusions are genuinely external customer-service or
  call-centre roles; **no software or engineering role was newly excluded**; the one engineering role
  that touched the rule (an AI engineer building agents for IT help-desk workflows) was correctly
  suppressed. A false-negative sweep across every CS-ish title in the 282 postings found none that
  should have been excluded.
- **Versioning and projection**: both version bumps warranted; the projection rebuilds green against
  the live sources including the 2026-09-26 `workflow` hash; the rule's source attribution is right.
- **Privacy boundary clean**: no contact details, personal profile data or master-resume content in
  the code, tests, projection or evidence. The master resume is referenced as a path plus hash only.

## What the reviewer explicitly did NOT check

- Nothing was deployed, invoked, committed or pushed; no AWS, no network, no `sam deploy`.
- The Lambda `assemble_report_input` S3 path was exercised only through its local equivalent
  (`_assemble_local_report`), which reaches the same `screen_all` → `render_report` code. S3 was not
  stubbed.
- Scoring / fit-band computation beyond observing which band each probe landed in.
- n3 was reasoned from code, not demonstrated.
- Whether the nine corpus exclusions would survive reading the live postings on the employers' own
  sites; they were judged from the stored fixture text.

---

## After the repairs

- 433 tests pass (424 before the repairs; 40 in the new file, 9 of them added for these findings).
- 22 of those 40 fail against the reversed-edit pre-P10 tree; the remainder are guards, which had
  nothing to misfire against before the rule existed.
- The corpus audit is unchanged in outcome: 5 newly excluded, retained set byte-identical, and the
  AI engineering role now records a guarded suppression instead of an exclusion reason.
- `policy-check` exits 0; the rebuilt projection carries 9 mapped rules.
