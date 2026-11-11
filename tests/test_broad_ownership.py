"""Acceptance controls for the 2026-09-28 broad-ownership / first-sole-engineer preference.

What is under test
------------------
`APPLICATION_WORKFLOW.md` § "Broad ownership and first/sole-engineer preference" asks for three
behaviors, and each has its own controls below:

  1. A plausible broad-ownership opening at an ordinary employer reaches a READABLE review surface
     even when its AI-oriented keyword score is low. Before this change the readable sections were
     gated at `brett_fit >= 0.40`; everything under it became a bare identity in
     `below_fit_threshold_job_ids`.
  2. Confirmed sole ownership, a stated small team and unknown team structure stay THREE distinct
     answers, and neither a Staff title nor a missing employer headcount produces any of them.
  3. Nothing already working stops working: a good role at a large employer still arrives, and the
     genuine phone-queue, sales-duty and geography exclusions still fire on their real duties.

The production boundary
-----------------------
The end-to-end cases reuse `test_discovery_to_report_integration.Harness`, which runs the REAL
enumerate / collect / discovery / differ / report handlers and substitutes only HTTP, S3, SQS and
SES. No test here writes a manifest, a normalized job set, a screening decision, a scorecard or a
`ReportInput` — the assertions are made against the report the report handler persisted to S3.

Every posting body below is SYNTHETIC. They control one variable each and are evidence about JPRS's
behavior, never a claim that any such opening exists.
"""

from __future__ import annotations

import json

import pytest

from src.candidate.ownership import (
    OwnershipBreadth,
    TeamStructure,
    assess_ownership,
)
from src.candidate.screening import screen_job
from src.common.models import ScreenOutcome
from tests.conftest import make_job
from tests.test_discovery_to_report_integration import (  # noqa: F401  (harness fixture)
    _round,
    _single_page_fetcher,
    harness,
)


from src.candidate.screening import HUMAN_FIRST_HOLD  # noqa: E402

def _feed_record(*, title: str, company: str, slug: str, body: str,
                 locations: str = "['United States']") -> dict:
    record = {
        "title": title,
        "companyName": company,
        "companySlug": slug,
        "employmentType": "Full Time",
        "locationRestrictions": locations,
        "applicationLink": f"https://himalayas.app/companies/{slug}/jobs/role",
        "guid": f"https://himalayas.app/companies/{slug}/jobs/role",
        "excerpt": body,
    }
    record["description"] = body
    return record


# ==================================================================================================
# The posting the whole change exists for.
# ==================================================================================================
# An ordinary employer whose product is not software. No AI vocabulary anywhere in it — not "AI",
# not "LLM", not "agent", not "machine learning" — and an ordinary title that matches NO scoring
# title lane. Under the old band gate this posting scored below 0.40 and appeared in no readable
# section of the report.
ORDINARY_BROAD_OWNERSHIP = _feed_record(
    title="Internal Applications Developer",
    company="Pemigewasset Fastener Supply",
    slug="pemi-fastener",
    body=(
        "We distribute industrial fasteners to contractors across New England and we are not a "
        "software company. You would be our first software engineer, working directly with the "
        "owner to understand the business and decide what is worth building. Responsibilities: "
        "build and maintain the internal applications our warehouse and sales operations run on, "
        "own the Python and SQL reporting that leadership reads every morning, and wire our "
        "purchasing system to our accounting package. You would own this end to end, from "
        "requirements to deployment. Remote throughout the United States. Interview process: two "
        "live video calls with the owner and the operations manager."
    ),
)

# The same shape of work at a large technology employer. The preference is a positive, not a
# small-company-only policy, so this must stay exactly as reachable as it was.
LARGE_EMPLOYER_GOOD_CONTROL = _feed_record(
    title="Senior Software Engineer, Internal Platform",
    company="Continental Data Systems",
    slug="continental-data",
    body=(
        "Join an engineering organization of several hundred. Responsibilities: build Python "
        "backend services and internal tools on AWS Lambda, own API integrations end to end, and "
        "ship LLM evaluation workflows for our support platform. Remote throughout the United "
        "States. Interview process: two live video calls with the team."
    ),
)

# Staff is a SENIORITY label. This posting says nothing about team size at all, and the assessment
# must not convert the title into a claim about one.
STAFF_TITLE_NO_STRUCTURE = _feed_record(
    title="Staff Software Engineer",
    company="Merrimack Analytics",
    slug="merrimack-analytics",
    body=(
        "Responsibilities: design and build Python backend services and AWS data pipelines, own "
        "API integrations, and raise the engineering bar across the codebase. Remote throughout "
        "the United States. Interview process: live video calls with engineers."
    ),
)

# A genuine external phone queue that also mentions building a report. The customer-service
# exclusion must still fire on the duty text.
GENUINE_PHONE_QUEUE = _feed_record(
    title="Customer Service Representative",
    company="Lakes Region Utility Services",
    slug="lakes-utility",
    body=(
        "Responsibilities: answer inbound customer calls and emails from our customers, resolve "
        "billing questions on the phone, and meet average handle time targets. You will also build "
        "a weekly report for your supervisor. Remote throughout the United States."
    ),
)

# Broad-ownership LANGUAGE attached to real sales-outcome ownership. The sales exclusion outranks it:
# the ownership path may not launder an excluded role back into the report.
SALES_OWNERSHIP_WITH_BREADTH_LANGUAGE = _feed_record(
    title="Founding Account Executive",
    company="Northfield Revenue Partners",
    slug="northfield-revenue",
    body=(
        "You would be our first commercial hire with full ownership and complete autonomy, "
        "wearing many hats from day one. Responsibilities: carry an annual sales quota, run the "
        "full cycle from prospecting to close, and own the pipeline. Remote throughout the United "
        "States."
    ),
)

# A sole-engineer role that is genuinely remote but not to a New Hampshire resident. Geography is a
# verified fact about the role, not a keyword score, so it still excludes however broad the scope is.
SOLE_ENGINEER_EXCLUDED_GEOGRAPHY = _feed_record(
    title="Applications Engineer",
    company="Seaport Marine Outfitters",
    slug="seaport-marine",
    body=(
        "You would be the only engineer here, owning our internal systems end to end and deciding "
        "what to build. Responsibilities: build and maintain Python applications for the yard and "
        "the parts counter. This position is open only to residents of California, Texas and New "
        "York. Interview process: live video calls with the owner."
    ),
    locations="['United States']",
)


# ==================================================================================================
# Unit level — the assessment itself
# ==================================================================================================
def _assess(title: str, description: str):
    return assess_ownership(make_job("own-1", title=title, description=description))


def test_confirmed_sole_small_team_and_unknown_are_three_distinct_answers():
    """The policy's own words: distinguish confirmed sole, small team with broad ownership, and
    unknown structure. Collapsing any two of them is the failure this asserts against."""
    sole = _assess(
        "Internal Applications Developer",
        "You would be our first software engineer, owning our internal systems end to end.",
    )
    small = _assess(
        "Software Engineer",
        "You will join a small engineering team and own delivery from requirements to production.",
    )
    unknown = _assess(
        "Software Engineer",
        "Responsibilities: build Python backend services and own API integrations end to end.",
    )

    assert sole.team_structure is TeamStructure.CONFIRMED_SOLE
    assert small.team_structure is TeamStructure.SMALL_TEAM
    assert unknown.team_structure is TeamStructure.UNKNOWN

    # All three can be broad-ownership candidates; the DISTINCTION is the team-structure fact, and
    # breadth must not be read backwards into it.
    assert sole.is_broad_ownership_candidate
    assert small.is_broad_ownership_candidate
    assert unknown.breadth is OwnershipBreadth.BROAD
    assert unknown.team_structure is TeamStructure.UNKNOWN


def test_a_staff_title_is_not_evidence_of_being_the_only_engineer():
    """"Staff is a seniority label, not evidence of being the company's only engineer." """
    for title in ("Staff Software Engineer", "Principal Engineer", "Distinguished Engineer"):
        assessment = _assess(
            title,
            "Responsibilities: design Python services and own API integrations. Remote, US.",
        )
        assert assessment.team_structure is TeamStructure.UNKNOWN, title
        assert not any(s.kind == "sole" for s in assessment.signals), title


def test_missing_employer_headcount_produces_no_finding():
    """A posting that says nothing about the team says nothing. UNKNOWN is not a defect, and the
    assessment emits no exclusion, no pending check and no signal for it."""
    assessment = _assess(
        "Software Engineer",
        "Responsibilities: maintain our billing service. You will focus exclusively on billing.",
    )
    assert assessment.team_structure is TeamStructure.UNKNOWN
    assert assessment.breadth is OwnershipBreadth.STATED_NARROW
    assert not assessment.is_broad_ownership_candidate
    # And it changes nothing about screening: no ownership rule exists there, by design.
    screened = screen_job(make_job(
        "own-2", title="Software Engineer",
        description="Responsibilities: maintain our billing service. Remote, US. Live interviews.",
    ))
    assert not any("ownership" in hit.rule_id for hit in
                   screened.exclusions + screened.pending_checks)


ORDINARY_BUSINESS_PHRASINGS = [
    (
        "plumbing wholesaler",
        "Applications Developer",
        "We are a plumbing supply wholesaler with six branches. You would be the only person here "
        "who writes software. Day to day you will build small web applications for the counter "
        "staff, keep the inventory reports running, and connect our ordering system to our "
        "accounting package. Remote with occasional travel to Concord.",
    ),
    (
        "dental group",
        "Software Developer",
        "Our dental group runs eleven practices. This is a new position. You will write and look "
        "after the internal tools our front desk and billing staff use every day, working with the "
        "practice administrator to work out what they need. Nobody else here does this work. "
        "Remote.",
    ),
    (
        "regional trucking company",
        "Business Systems Analyst Developer",
        "Regional trucking company. You will build and maintain the software that runs dispatch "
        "and billing, working directly with the owner. We have no IT department. Remote, US.",
    ),
    (
        "industrial manufacturer",
        "Programmer",
        "We make industrial coatings. We need someone to write the programs that keep our "
        "production scheduling and quality reporting working, and to improve them over time. You "
        "would work alone on this, reporting to the plant manager. Remote or Laconia NH.",
    ),
]


@pytest.mark.parametrize("label,title,body", ORDINARY_BUSINESS_PHRASINGS,
                         ids=[c[0] for c in ORDINARY_BUSINESS_PHRASINGS])
def test_an_ordinary_business_stating_sole_ownership_in_plain_english_is_recognized(
    label, title, body
):
    """The over-filtering control, and the one that nearly failed silently.

    A business whose product is not software does not write "sole engineer, greenfield, wear many
    hats". It writes "nobody else here does this work" and "you would work alone on this". Every
    posting here states first or sole ownership unmistakably, and none of them uses the recruiting
    vocabulary the first draft of these patterns was written against — that draft missed three of
    the four.

    This is the direction that matters most: a false positive costs Brett a look at a posting, and a
    false negative loses exactly the opening the 2026-09-28 preference was written to find.
    """
    assessment = _assess(title, body)
    assert assessment.team_structure is TeamStructure.CONFIRMED_SOLE, (
        f"{label}: {assessment.evidence_summary()}"
    )
    assert assessment.builds_software is True, label
    assert assessment.is_broad_ownership_candidate, label


# Every sentence below is an unmistakable statement of sole ownership or broad scope, collected by
# an independent review that measured the first version of these patterns and found 19 of the 24
# LOST. They are kept verbatim as the regression corpus: the failure mode is a phrase whitelist
# drifting back toward the vocabulary its author happens to hold, and only a corpus somebody else
# wrote can catch that.
PLAIN_ENGLISH_OWNERSHIP = [
    "You would be the only person here writing code.",
    "You would be the only person who writes code here.",
    "You will be the only developer we have.",
    "You would be the first person we have ever hired to write software.",
    "You would be employee number one on the technology side.",
    "We have never had anyone in-house who writes software.",
    "Nobody here writes software today.",
    "Today nobody else here builds software.",
    "This is our first technical role.",
    "This is the first software role we have ever created.",
    "You would be our only technical employee.",
    "There is nobody else in this role.",
    "You'd be a team of one.",
    "It would just be you.",
    "You would own the software here by yourself.",
    "You would be running the software side single-handedly.",
    "You would decide what software this company needs and then build it.",
    "You would choose what to build and then build it.",
    "You would figure out what the business needs and build it.",
    "You would touch every part of the system.",
    "You would do a bit of everything.",
    "Nothing here is somebody else's job.",
    "You would take our software from nothing to something.",
    "You would build all of this from the ground up.",
]

_QUALIFYING_TAIL = (
    " Responsibilities: build and maintain the internal applications our branches run on, and "
    "write the reports leadership reads. Remote, United States. Live interviews."
)


@pytest.mark.parametrize("sentence", PLAIN_ENGLISH_OWNERSHIP)
def test_plain_english_ownership_statements_are_recognized(sentence):
    """The whitelist-drift control.

    A miss here is not a near-miss: it is the opening the 2026-09-28 preference exists to find,
    landing in `below_fit_threshold_job_ids` with no title, no link and no reason on any page Brett
    reads. That is the exact tail this change was written to empty.
    """
    assessment = _assess("Applications Developer", sentence + _QUALIFYING_TAIL)
    assert assessment.is_broad_ownership_candidate, (
        f"{sentence!r} -> team={assessment.team_structure.value} "
        f"breadth={assessment.breadth.value} evidence={assessment.evidence_summary()}"
    )


def test_a_pay_line_does_not_delete_the_ownership_sentence_after_it():
    """`segment_description` latches a section until the next cue, so a "Compensation:" line makes
    everything after it BENEFITS. Measured by review: the same posting assessed CONFIRMED_SOLE/BROAD
    without that one sentence and UNKNOWN/UNSTATED with it, and the `with` version reached no
    readable section at all. Adzuna and Himalayas both put pay mid-body.
    """
    with_pay = (
        "Kearsarge Freight Lines is a regional carrier. Compensation: $130,000 to $150,000 plus "
        "health and dental. You would be our first software engineer and would own our internal "
        "systems end to end, deciding what is worth building with the owner. Remote, United States."
    )
    without_pay = with_pay.replace(
        "Compensation: $130,000 to $150,000 plus health and dental. ", ""
    )
    a, b = _assess("Software Engineer", with_pay), _assess("Software Engineer", without_pay)
    assert a.team_structure is b.team_structure is TeamStructure.CONFIRMED_SOLE
    assert a.breadth is b.breadth is OwnershipBreadth.BROAD
    assert a.is_broad_ownership_candidate

    # And the guard the wider section scope must NOT cost: a perks block's "small team atmosphere"
    # is not evidence about the engineering team, so `_SMALL_TEAM_RE` keeps the narrower scope.
    perks = _assess(
        "Software Engineer",
        "About us: we build logistics software. What we offer: a small team atmosphere, unlimited "
        "PTO and a home office stipend. Responsibilities: maintain one service.",
    )
    assert perks.team_structure is TeamStructure.UNKNOWN


SOMEBODY_ELSES_COMPANY = [
    ("the employer's clients",
     "Mill City Consulting places engineers with small businesses. Many of our clients have no "
     "in-house engineering team, which is why they hire us. Responsibilities: deliver billable "
     "project work on client codebases under a delivery manager, in teams of six."),
    ("a founder's previous employer",
     "Our CTO was the first developer at a well-known payments company before founding us. We now "
     "have ninety engineers. Responsibilities: build services."),
    ("a colleague who already holds the role",
     "You will work alongside our first software engineer in the Manchester office and learn our "
     "codebase from her. Responsibilities: build features."),
    ("a company the founder came from",
     "Our founder came from a company that had no engineering team at all. We now have sixty "
     "engineers. Responsibilities: own one service."),
    ("a vendor's team",
     "You will support a team of three engineers at our vendor while building features in our "
     "600-person platform group."),
]


@pytest.mark.parametrize("label,body", SOMEBODY_ELSES_COMPANY,
                         ids=[c[0] for c in SOMEBODY_ELSES_COMPANY])
def test_a_sole_claim_about_another_company_establishes_nothing(label, body):
    """A team-structure verdict is a claim about a SPECIFIC employer.

    Review reproduced all five of these printing "confirmed first/sole engineer" on rows for
    employers that state teams of six, sixty and ninety engineers in the same posting. The
    discriminator was already being computed and serialized and was read by nothing.
    """
    assessment = _assess("Software Engineer", body)
    assert assessment.team_structure is TeamStructure.UNKNOWN, (
        f"{label}: {assessment.evidence_summary()}"
    )
    assert not assessment.is_broad_ownership_candidate, label


CULTURE_PROSE = [
    ("ownership of a career", "We believe in full ownership of your career here at Vantage."),
    ("ownership of learning", "You will have complete ownership of your learning and development."),
    ("the workforce wears hats", "Our people wear many hats and love it."),
    ("the platform's history", "Our platform was written from scratch a decade ago."),
    ("the founders' history", "Our founders took this company from zero to one in 2019."),
    ("a rewrite in 2003",
     "Our billing platform was built from scratch in 2003 and you will help maintain it alongside "
     "eight other engineers."),
    ("greenfield inside a 400-person org",
     "This is a greenfield project inside our platform organization of 400 engineers. "
     "Responsibilities: build one new microservice to the architecture team's specification."),
]


@pytest.mark.parametrize("label,sentence", CULTURE_PROSE, ids=[c[0] for c in CULTURE_PROSE])
def test_culture_and_company_history_prose_is_not_ownership_scope(label, sentence):
    """Ownership of a career, a learning plan or a decade-old rewrite is not ownership of the
    employer's software by this hire. Each of these was retained on a role whose only stated duty
    was implementing assigned front-end tickets."""
    assessment = _assess(
        "Software Engineer",
        sentence + " Responsibilities: implement assigned tickets in our React front end to the "
                   "designs our product team supplies.",
    )
    assert not assessment.is_broad_ownership_candidate, (
        f"{label}: breadth={assessment.breadth.value} {assessment.evidence_summary()}"
    )


def test_a_verb_stem_that_collides_with_a_noun_does_not_establish_sole_ownership():
    """Found by re-running the live corpus immediately after widening the sole-ownership patterns.

    A content-review posting's eligibility boilerplate — "only one member per household may
    participate in this program" — read as **confirmed first/sole engineer**, because the verb stem
    `program\\w*` matched the noun "program". The repair requires a verb AND a software object, and
    the general lesson is that widening a pattern is itself a change that needs measuring.
    """
    boilerplate = _assess(
        "Content Reviewer",
        "Please note that only one member per household may participate in this program.",
    )
    assert boilerplate.team_structure is TeamStructure.UNKNOWN, boilerplate.evidence_summary()

    retention = _assess(
        "Software Engineer", "We have never had anyone leave this team in five years."
    )
    assert retention.team_structure is TeamStructure.UNKNOWN, retention.evidence_summary()

    # The phrasings the guard must still admit.
    for sentence in (
        "You would be the only person here writing code.",
        "You would be the only person who writes code here.",
    ):
        assert _assess("Applications Developer", sentence + _QUALIFYING_TAIL).team_structure is (
            TeamStructure.CONFIRMED_SOLE
        ), sentence


def test_a_business_outcome_guard_reads_the_clause_not_the_matched_phrase():
    """`full ownership` and `complete ownership` capture two words, so the object of the ownership
    is never inside the matched text. Testing the guard against `match.group(0)` meant it fired on
    exactly one of the alternatives it was written to cover."""
    for sentence in (
        "You will have full ownership of revenue for your accounts.",
        "You take complete ownership of the sales pipeline.",
        "You will own go-to-market end to end.",
    ):
        assessment = _assess("Account Manager", sentence + " Remote, US.")
        assert not assessment.is_broad_ownership_candidate, sentence


ESTABLISHED_SOLE_ODD_DUTY_PROSE = [
    ("duties written as noun phrases",
     "Applications Engineer",
     "Granite Dental Partners operates nine practices. You would be our first software engineer. "
     "Scope of the role: internal applications, integrations with our accounting package, and the "
     "reporting our regional managers need."),
    ("verb separated from object by a noun list",
     "Applications Engineer",
     "You would be our only software engineer. You will be responsible for the design, "
     "construction and long-term stewardship of every piece of internal, customer-facing and "
     "back-office software this company runs on."),
]


@pytest.mark.parametrize("label,title,body", ESTABLISHED_SOLE_ODD_DUTY_PROSE,
                         ids=[c[0] for c in ESTABLISHED_SOLE_ODD_DUTY_PROSE])
def test_confirmed_sole_ownership_does_not_need_a_second_phrase_to_qualify(label, title, body):
    """Confirmed first/sole ownership is the strongest fact the preference names.

    Requiring a separately-shaped "builds software" phrase AFTER it lost both of these, whose
    sole-ownership fact was already established and whose duties are plainly software. A confirmed
    sole-engineer role at a non-software employer is by itself enough reason for a human to look.
    """
    assessment = _assess(title, body)
    assert assessment.team_structure is TeamStructure.CONFIRMED_SOLE, label
    assert assessment.is_broad_ownership_candidate, (
        f"{label}: builds_software={assessment.builds_software}"
    )


def test_a_negated_sole_claim_is_not_confirmed_sole_ownership():
    """"You will not be our only engineer" must not read as confirmed sole ownership. Polarity is
    checked inside the phrase's own clause, the same way screening checks it."""
    assessment = _assess(
        "Software Engineer",
        "You will not be the only engineer here; you join a team of forty. Remote, US.",
    )
    assert assessment.team_structure is TeamStructure.UNKNOWN


def test_founding_engineer_is_a_breadth_clue_not_a_sole_ownership_verdict():
    """The workflow lists `founding engineer` among "useful search clues", and a founding engineer is
    commonly one of several. It may widen the search; it may not assert a team size."""
    assessment = _assess(
        "Founding Engineer",
        "Join as a founding engineer building our platform from scratch. Remote, US.",
    )
    assert assessment.breadth is OwnershipBreadth.BROAD
    assert assessment.team_structure is TeamStructure.UNKNOWN


def test_owning_a_business_outcome_end_to_end_is_not_software_ownership():
    """Measured against 176 live postings on 2026-09-28, where these four phrasings all read as
    broad software ownership. The phrase is genuine; the thing being owned is revenue."""
    for phrase in (
        "You will own go-to-market strategy end to end.",
        "Owning a direct sales territory end-to-end.",
        "You will own monetization end-to-end for the product.",
        "Owning segment revenue end-to-end across the region.",
    ):
        assessment = _assess("Account Director", phrase + " Remote, US.")
        assert assessment.breadth is not OwnershipBreadth.BROAD, phrase
        assert not assessment.is_broad_ownership_candidate, phrase


def test_a_department_head_is_not_the_first_or_sole_engineer_shape():
    """"Head of Security" and "VP Pricing & Packaging" both reached the retained list at a fit score
    of 0.00 on ownership language alone. The preference describes implementing across the stack and
    owning the result, which is a different job from running a department.

    This removes nothing: such a role still arrives on its own fit score exactly as before, and no
    new exclusion rule is created anywhere.
    """
    body = (
        "You will own our detection and alerting program end-to-end, building the tooling and "
        "automation the team depends on. Remote, US."
    )
    for title in ("Head of Security", "VP Pricing & Packaging", "Engineering Manager",
                  "Director of Platform"):
        assessment = _assess(title, body)
        assert assessment.management_title is True, title
        assert not assessment.is_broad_ownership_candidate, title

    # The same duties under an engineer's title do qualify — the title is the only difference.
    engineer = _assess("Senior Software Engineer", body)
    assert engineer.is_broad_ownership_candidate


def test_ownership_language_without_software_building_is_not_a_candidate():
    """The preference is about building. A role that owns something broadly but builds no software
    is not what the section is asking for, and admitting it floods the review surface."""
    # The fixture isolates ONE variable. It deliberately names no vendor, client or partner: those
    # trip the third-party guard, which would make this pass for the wrong reason.
    assessment = _assess(
        "Operations Lead",
        "You will wear many hats and own the result, coordinating schedules and budgets across "
        "the business. Remote, US.",
    )
    assert assessment.breadth is OwnershipBreadth.BROAD
    assert assessment.builds_software is False
    assert not assessment.is_broad_ownership_candidate


def test_a_loom_video_requirement_is_a_recorded_candidate_video():
    """Found live on 2026-09-28, in the bounded pass this packet ran.

    A posting whose first line was "applying to this role requires a Loom video walkthrough under 5
    minutes of the best thing you have built" reached the retained pool at fit 0.51. The operator's
    exclusion is on producing a recorded candidate video, and naming the tool is the most common way
    a posting asks for one. A live human call is unaffected — that distinction is the whole rule.
    """
    excluded = screen_job(make_job(
        "vid-1", title="AI Engineer, Data APIs",
        description=(
            "Before you read further: applying to this role requires a Loom video walkthrough "
            "under 5 minutes of the best thing you have built, plus a repo or live link. "
            "Remote throughout the United States."
        ),
    ))
    # Human-first rule (2026-10-12): held for a human-interview route, never offered as ready, and
    # never a silent pass.
    assert excluded.outcome == ScreenOutcome.PENDING_CHECK.value
    assert "recorded-video" in {h.rule_id for h in excluded.pending_checks if h.reason.startswith(HUMAN_FIRST_HOLD)}

    live_call = screen_job(make_job(
        "vid-2", title="Software Engineer",
        description=(
            "Interview process: two live video calls with the engineering team over Zoom. "
            "Remote throughout the United States."
        ),
    ))
    assert live_call.outcome == ScreenOutcome.ELIGIBLE.value
    assert not live_call.exclusions


def test_a_narrow_scoping_statement_outranks_broad_language_elsewhere():
    """A posting that opens with "own it end to end" and then scopes the work to one service has
    scoped the work. Reading only the first phrase is how ownership becomes a marketing word.

    The second case is the one that matters, and the first version of this test dodged it: its
    fixture left team structure UNKNOWN, so it passed while the property it names was false. Adding
    a stated small team made it `SMALL_TEAM` + `STATED_NARROW` + **candidate**, with the report
    printing "narrowly scoped" on a row it was retaining as a broad-ownership candidate. The
    policy's category is "a small team WITH broad ownership"; a small team without it is not that.
    """
    assessment = _assess(
        "Software Engineer",
        "You will own it end to end. In practice you will focus exclusively on the billing "
        "service within our existing engineering organization.",
    )
    assert assessment.breadth is OwnershipBreadth.STATED_NARROW
    assert not assessment.is_broad_ownership_candidate

    with_a_team = _assess(
        "Software Engineer",
        "You will join a small engineering team. In practice you will focus exclusively on the "
        "billing service and will not touch anything else. Responsibilities: maintain the billing "
        "service.",
    )
    assert with_a_team.team_structure is TeamStructure.SMALL_TEAM
    assert with_a_team.breadth is OwnershipBreadth.STATED_NARROW
    assert not with_a_team.is_broad_ownership_candidate, (
        "a stated narrow scope must outrank a team-structure fact, which is what this module's own "
        "docstring has always claimed"
    )


# ==================================================================================================
# End to end — through the real discovery-to-report path
# ==================================================================================================
def test_ordinary_broad_ownership_role_with_a_low_ai_score_reaches_a_readable_section(harness):
    """THE acceptance case.

    A remote internal-applications role at an unknown ordinary employer, with no AI wording and a
    low AI-oriented fit score, must arrive on a surface a human reads — with its link, its reason
    and its ownership scope — rather than as an identity in a JSON tail.
    """
    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([ORDINARY_BROAD_OWNERSHIP]))
    report = harness.saved_report(run_id)
    markdown = harness.saved_markdown(run_id)

    rows = {row["job_id"]: row for row in report["complete_candidate_list"]}
    match = [r for r in rows.values() if r["employer"] == "Pemigewasset Fastener Supply"]
    assert match, (
        "the ordinary broad-ownership posting reached no readable section; "
        f"below-threshold ids: {report['below_fit_threshold_job_ids']}"
    )
    row = match[0]

    # It is retained BECAUSE of ownership evidence, not because the fit score was high. Both halves
    # matter: if the score were high this test would prove nothing about the repair.
    assert row["retained_on_ownership_evidence"] is True, row
    assert row["fit_band"] == "LOW", row["fit_score"]
    assert row["ownership"]["team_structure"] == TeamStructure.CONFIRMED_SOLE.value

    # The posting genuinely contains no AI vocabulary — the premise of the case, asserted rather
    # than assumed, so a later fixture edit cannot quietly turn this into an ordinary fit match.
    body = ORDINARY_BROAD_OWNERSHIP["description"].lower()
    for token in ("ai", "llm", "machine learning", "agent", "genai"):
        assert f" {token} " not in f" {body} ", token

    # Usable on the page: a link, a reason, and the scope it rests on.
    #
    # Asserted against the SECTION, not against the whole document. An independent review measured
    # that `"<employer>" in markdown` and `"ownership" in markdown` are both true for a posting that
    # reached no readable section at all — the employer name is printed in the coverage line
    # "Employers seen this run that were not in the monitored registry", and the substring
    # "ownership" comes from the query-family name `broad-ownership` printed in every report. Two
    # assertions that pass identically on the broken behavior were carrying the "usable on the page"
    # claim.
    assert row["apply_url"]
    assert row["why_fit"]
    section = markdown.split("## Needs a check before preparing", 1)
    assert len(section) == 2, "no needs-a-check section in the rendered report"
    section = section[1].split("\n## ", 1)[0]
    assert "Pemigewasset Fastener Supply" in section, section
    assert row["apply_url"] in section or (row["posting_url"] or "") in section, section
    assert "confirmed first/sole engineer" in section, section

    # It landed in the needs-a-check destination, not announced as strong. Stated as the two counts,
    # because the previous form reduced to `new_strong_count == 0` and would have stopped testing
    # anything the moment a second posting joined the fixture.
    assert report["needs_check_count"] == 1, report["needs_check_count"]
    assert report["new_strong_count"] == 0, report["new_strong_count"]
    assert row["job_id"] in report["ownership_retained_job_ids"]
    assert row["job_id"] in report["confirmed_sole_ownership_job_ids"]
    # And it is no longer counted as silently below the threshold.
    assert row["job_id"] not in report["below_fit_threshold_job_ids"]


def test_an_equally_good_role_at_a_large_employer_still_survives(harness):
    """The preference is a positive, not a small-company-only policy."""
    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([LARGE_EMPLOYER_GOOD_CONTROL]))
    report = harness.saved_report(run_id)

    rows = [r for r in report["complete_candidate_list"]
            if r["employer"] == "Continental Data Systems"]
    assert rows, report["below_fit_threshold_job_ids"]
    assert rows[0]["screen_outcome"] == ScreenOutcome.ELIGIBLE.value
    # It arrives on its own fit, with the ownership path taking no part in it.
    assert rows[0]["fit_band"] in ("HIGH", "MEDIUM")
    assert rows[0]["retained_on_ownership_evidence"] is False


def test_a_staff_titled_role_arrives_without_a_team_structure_claim(harness):
    """Neither a Staff title nor a missing headcount may create a finding."""
    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([STAFF_TITLE_NO_STRUCTURE]))
    report = harness.saved_report(run_id)

    rows = [r for r in report["complete_candidate_list"]
            if r["employer"] == "Merrimack Analytics"]
    assert rows, report["below_fit_threshold_job_ids"]
    row = rows[0]
    assert row["ownership"]["team_structure"] == TeamStructure.UNKNOWN.value
    assert row["job_id"] not in report["confirmed_sole_ownership_job_ids"]
    # No exclusion and no pending check was manufactured from the unknown structure.
    pending = [h["rule_id"] for h in (row["screen_detail"] or {}).get("pending_checks", [])]
    assert not any("ownership" in rule for rule in pending), pending


def test_a_genuine_phone_queue_is_still_excluded_on_its_duties(harness):
    """The 2026-09-26 clarification still holds. Mentioning a report does not clear a phone queue,
    and the ownership path must not reach an excluded posting at all."""
    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([GENUINE_PHONE_QUEUE]))
    report = harness.saved_report(run_id)

    retained = [r for r in report["complete_candidate_list"]
                if r["employer"] == "Lakes Region Utility Services"]
    assert not retained, retained
    excluded = [r for r in report["policy_exclusions"]
                if r["employer"] == "Lakes Region Utility Services"]
    assert excluded, report["policy_exclusions"]
    rules = {hit["rule_id"] for hit in excluded[0]["screen_detail"]["exclusions"]}
    assert "customer-service-queue" in rules, rules


def test_ownership_language_does_not_launder_a_sales_role_back_in(harness):
    """Broad-ownership vocabulary attached to a real quota is still a sales role. An exclusion that
    a new retention path can talk its way past is not an exclusion."""
    run_id = "2026-09-28"
    _round(harness, run_id,
           fetcher=_single_page_fetcher([SALES_OWNERSHIP_WITH_BREADTH_LANGUAGE]))
    report = harness.saved_report(run_id)

    retained = [r for r in report["complete_candidate_list"]
                if r["employer"] == "Northfield Revenue Partners"]
    assert not retained, retained
    excluded = [r for r in report["policy_exclusions"]
                if r["employer"] == "Northfield Revenue Partners"]
    assert excluded, report["policy_exclusions"]
    rules = {hit["rule_id"] for hit in excluded[0]["screen_detail"]["exclusions"]}
    assert "sales-ownership" in rules, rules
    assert report["ownership_retained_job_ids"] == [] or all(
        not jid.startswith("himalayas") or "northfield" not in jid
        for jid in report["ownership_retained_job_ids"]
    )


def test_a_broad_ownership_role_behind_a_commute_question_is_never_silently_cleared():
    """The operator's onsite exclusions are in force regardless of how attractive the scope is.

    Stated at the strength the code actually holds, because the difference matters. A location
    written as a bare city is EXCLUDED. The same city written `City, ST` — which is how most feeds
    write it — reaches PENDING_CHECK instead: `normalize_location` splits it into `boston | ma`, the
    two-letter state token parses as its own UNKNOWN place, and `best_worksite` returns the most
    favorable of the two. This is pre-existing behavior in `src/candidate/location.py`, not a
    consequence of the ownership path, and it is carried to the Career Factory queue rather than
    repaired inside this packet.

    What this asserts is the property that must hold in BOTH cases: an onsite role at an excluded
    location is never returned as a clean eligible verdict, so the ownership retention path cannot
    turn a commute the operator ruled out into a silent yes.
    """
    body = (
        "You would be the only engineer here, owning our internal systems end to end. "
        "Responsibilities: build and maintain Python applications for the yard. This role is "
        "onsite five days per week in the office. Interview process: live video calls."
    )
    excluded_outright = screen_job(make_job("geo-1", title="Applications Engineer",
                                            description=body, location="Boston"))
    assert excluded_outright.outcome == ScreenOutcome.EXCLUDED.value
    assert {h.rule_id for h in excluded_outright.exclusions} & {
        "location-eligibility", "location-residency"}

    # Repaired 2026-11-11 (PKT-CAREER-RADAR-END-TO-END-REPAIR-V1): `best_worksite` no longer lets the
    # canonical form's stray `ma` fragment outrank the resolved place, so `City, ST` now reaches the
    # same verdict as the bare city instead of a softer PENDING_CHECK.
    city_state = screen_job(make_job("geo-2", title="Applications Engineer",
                                     description=body, location="Boston, MA"))
    assert city_state.outcome == ScreenOutcome.EXCLUDED.value
    assert any(h.rule_id == "location-eligibility" for h in city_state.exclusions)


def test_a_sole_engineer_role_a_new_hampshire_resident_cannot_take_is_still_excluded(harness):
    """A residency restriction is a verified fact about the role, and broad ownership is no
    exception to it. The ownership retention path must not reach an excluded posting at all."""
    run_id = "2026-09-28"
    _round(harness, run_id,
           fetcher=_single_page_fetcher([SOLE_ENGINEER_EXCLUDED_GEOGRAPHY]))
    report = harness.saved_report(run_id)

    retained = [r for r in report["complete_candidate_list"]
                if r["employer"] == "Seaport Marine Outfitters"]
    excluded = [r for r in report["policy_exclusions"]
                if r["employer"] == "Seaport Marine Outfitters"]
    assert not retained, retained
    assert excluded, report["policy_exclusions"]
    rules = {hit["rule_id"] for hit in excluded[0]["screen_detail"]["exclusions"]}
    assert rules & {"location-eligibility", "location-residency"}, rules


def test_nothing_is_promoted_without_ownership_evidence(harness):
    """The retention path is not a blanket pass. A low-scoring posting with no ownership evidence is
    still below the threshold and still counted there, which is what keeps the repair honest."""
    run_id = "2026-09-28"
    plain_low = _feed_record(
        title="Technical Writer",
        company="Winnipesaukee Publishing",
        slug="winni-publishing",
        body=(
            "Responsibilities: write and edit user documentation and release notes for our "
            "products. Remote throughout the United States. Interview process: live video calls."
        ),
    )
    _round(harness, run_id, fetcher=_single_page_fetcher([plain_low]))
    report = harness.saved_report(run_id)

    retained = [r for r in report["complete_candidate_list"]
                if r["employer"] == "Winnipesaukee Publishing"]
    assert not retained, retained
    assert report["ownership_retained_job_ids"] == [], report["ownership_retained_job_ids"]


def test_the_broad_ownership_query_family_names_no_employer():
    """The company-independence invariant holds for the new family too: a query that names an
    employer turns discovery into a lookup."""
    from src.discovery.queries import (
        FAMILIES_BY_KEY,
        assert_company_independent,
        build_query_plan,
    )

    family = FAMILIES_BY_KEY["broad-ownership"]
    known = {"Granite State Mutual Insurance", "Machinify", "Continental Data Systems"}
    for phrase in family.phrases:
        assert_company_independent(phrase, known)
    # It is a floor family, not a rotating supplement: it cannot be starved out of a plan.
    plan = build_query_plan(known_employers=known, deprioritize=("broad-ownership",))
    assert any(key == "broad-ownership" for key, _phrase in plan.items)
    assert not family.rotates
    # And it carries no AI vocabulary, because neither AI wording nor a technology employer is
    # required by the preference.
    joined = " ".join(family.phrases + family.match_terms).lower()
    for token in ("ai", "llm", "ml", "agentic", "genai"):
        assert f" {token} " not in f" {joined} ", token


@pytest.mark.parametrize("payload,employer", [
    (ORDINARY_BROAD_OWNERSHIP, "Pemigewasset Fastener Supply"),
    (LARGE_EMPLOYER_GOOD_CONTROL, "Continental Data Systems"),
])
def test_every_retained_row_carries_its_ownership_evidence(harness, payload, employer):
    """A verdict with no visible evidence is not reviewable. Every retained row carries the
    assessment whole, so a wrong reading can be found and corrected rather than argued about."""
    run_id = "2026-09-28"
    _round(harness, run_id, fetcher=_single_page_fetcher([payload]))
    report = harness.saved_report(run_id)

    rows = [r for r in report["complete_candidate_list"] if r["employer"] == employer]
    assert rows, report["below_fit_threshold_job_ids"]
    ownership = rows[0]["ownership"]
    assert ownership is not None
    assert ownership["team_structure"] in {t.value for t in TeamStructure}
    assert ownership["breadth"] in {b.value for b in OwnershipBreadth}
    assert ownership["evidence_summary"]
    assert json.dumps(ownership)  # serializable into the persisted report
