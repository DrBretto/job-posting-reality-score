"""The 2026-09-26 clarification: software problem-solving, not customer service.

`APPLICATION_WORKFLOW.md` → *Adjacent roles: software problem-solving, not customer service*, plus
the `Screen Before Preparing` line "Reject call-center and external customer-service/phone-support
jobs".

The exclusion is the easy half. The clarification spends most of its words on what it does NOT mean,
and every one of those sentences is a test below:

  internal software ownership                     is not customer service
  building software FOR a support department       is not working its support queue
  requirements conversations and delivery meetings are not the excluded work
  an internal support queue                        is not EXTERNAL customer service
  a vague application-support title                is not automatically excluded — or suitable
  an established engineering team                  is not a reason to reject an employer
  no AI wording in the posting                     is not a reason to reject a role

Three outcomes are therefore in use throughout, and PENDING_CHECK is a real answer rather than a
fallback: ambiguous or insufficient evidence stays visible for review instead of becoming an
invented negative.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.candidate.policy import RULE_SOURCE_MAP
from src.candidate.screening import SCREENING_RULESET_VERSION, screen_job
from src.common.models import (
    CanonicalJob,
    IdKind,
    RemoteMode,
    SalarySource,
    SalaryStruct,
    ScreenOutcome,
    VerificationState,
)

NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)
PROCESS_OK = "Interview process: two video calls on Zoom with the engineering team."
RULE = "customer-service-queue"


def _job(title, description, *, location="Remote, US", remote=RemoteMode.REMOTE):
    return CanonicalJob(
        source_id="t:src", job_id=f"t:src#{abs(hash(title + description)) % 10**8}",
        id_kind=IdKind.NATIVE_ID, title=title, description_text=description,
        raw_location=location, canonical_location=location.lower(),
        secondary_locations=[], remote_hybrid_language=remote,
        verification_state=VerificationState.FEED_COMPLETE, uncertainty=[], last_seen_at=NOW,
    )


def _rules(job, bucket="exclusions") -> set[str]:
    return {h.rule_id for h in getattr(screen_job(job), bucket)}


def _reason(job, bucket="exclusions") -> str:
    return " ".join(h.reason + " " + h.matched_text
                    for h in getattr(screen_job(job), bucket) if h.rule_id == RULE)


# --------------------------------------------------------------------------------------------------
# The exclusion fires, and says which duty made it fire
# --------------------------------------------------------------------------------------------------
def test_call_center_agent_is_excluded():
    job = _job("Call Center Agent", (
        "What you'll do: answer inbound calls from customers in our contact center, "
        "resolve billing questions, and meet a first call resolution target. " + PROCESS_OK
    ))
    assert screen_job(job).outcome == ScreenOutcome.EXCLUDED.value
    assert RULE in _rules(job)


def test_customer_service_representative_title_is_excluded():
    job = _job("Customer Service Representative", (
        "What you'll do: help customers by phone and email with orders and returns. " + PROCESS_OK
    ))
    assert RULE in _rules(job)


def test_phone_support_duties_exclude_even_without_a_support_title():
    """The title is not the evidence the policy asks for — the duties are."""
    job = _job("Operations Associate", (
        "What you'll do: handle customer calls and respond to customer inquiries throughout your "
        "shift, keeping average handle time low. " + PROCESS_OK
    ))
    assert RULE in _rules(job)
    assert "queue" in _reason(job)


def test_managed_service_provider_helpdesk_queue_is_excluded_with_duty_evidence():
    """The real corpus case: an MSP service desk whose duties are client support requests."""
    job = _job("Tier III Service Desk Engineer", (
        "Duties: lead and support our helpdesk environment for managed service clients. "
        "Respond to queries for technical assistance in person, via phone, or electronically. "
        "Provide above and beyond support to our clients. " + PROCESS_OK
    ))
    assert RULE in _rules(job)
    # The recorded evidence must be a duty span, not merely the job title.
    hit = next(h for h in screen_job(job).exclusions if h.rule_id == RULE)
    assert hit.section != "title"
    assert hit.matched_text


def test_external_support_ticket_queue_is_excluded():
    job = _job("Customer Support Specialist", (
        "The role: this role is primarily about helping customers by email, understanding their "
        "questions and troubleshooting issues. You will work the support queue and respond to "
        "customer questions about billing and account setup. " + PROCESS_OK
    ))
    assert RULE in _rules(job)


def test_two_stated_queue_duties_are_counted_in_the_reason():
    job = _job("Support Associate", (
        "What you'll do: answer inbound calls from customers. "
        "You will also handle customer tickets and reply to customer emails. " + PROCESS_OK
    ))
    assert "duties stated" in _reason(job)


# --------------------------------------------------------------------------------------------------
# What the clarification explicitly PRESERVES
# --------------------------------------------------------------------------------------------------
def test_ordinary_internal_software_role_with_no_ai_wording_is_eligible():
    """Policy sentence: An AI-specific title or AI component is not required for this adjacent search."""
    job = _job("Software Engineer", (
        "What you'll do: build internal applications and workflow automation for our operations "
        "team, own integrations with our accounting system, and maintain reporting. "
        "Requirements: five years of Python and SQL. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert result.outcome == ScreenOutcome.ELIGIBLE.value, result.human_reason()
    assert RULE not in _rules(job)


def test_internal_software_role_at_an_established_engineering_employer_is_eligible():
    """Companies without an engineering team are attractive, NOT a requirement that rejects others."""
    job = _job("Senior Software Engineer", (
        "About us: we have a large established engineering organization of 200 engineers with "
        "mature platform and infrastructure teams. "
        "What you'll do: own internal tooling and data integrations end to end. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert result.outcome == ScreenOutcome.ELIGIBLE.value, result.human_reason()
    assert RULE not in _rules(job)


def test_building_software_for_the_support_org_is_engineering_not_customer_service():
    """Policy sentence: Building software FOR a call center/support department is not WORKING its support queue."""
    job = _job("Software Engineer, Support Platform", (
        "What you'll do: build internal tools for the customer support team, own the contact center "
        "integrations, and improve agent-facing tooling. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert RULE not in _rules(job), result.human_reason()
    assert result.outcome == ScreenOutcome.ELIGIBLE.value


def test_a_support_queue_duty_cannot_be_excused_by_a_software_sentence_elsewhere():
    """Duty-span scope, not description scope — the lesson the sales rule already learned."""
    job = _job("Customer Support Specialist", (
        "What you'll do: answer inbound calls from customers all day. "
        "You will also build internal reports about ticket volume. " + PROCESS_OK
    ))
    assert RULE in _rules(job)


def test_ordinary_meetings_and_requirements_conversations_are_not_the_excluded_work():
    """Policy sentence: Do not turn the phone-support exclusion into a ban on meetings or ordinary communication."""
    job = _job("Applications Engineer", (
        "What you'll do: run requirements conversations with internal stakeholders, join technical "
        "delivery meetings, diagnose internal problems, and present solutions to department heads. "
        "You will build the applications that resolve them. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert result.outcome == ScreenOutcome.ELIGIBLE.value, result.human_reason()
    assert RULE not in _rules(job)


def test_customer_discovery_meetings_for_a_technical_role_are_not_a_support_queue():
    """SEARCH_PREFERENCES keeps customer/stakeholder meetings acceptable for technical discovery."""
    job = _job("Integration Engineer", (
        "What you'll do: meet with customers to gather integration requirements, then design and "
        "implement the API integrations they need. " + PROCESS_OK
    ))
    assert RULE not in _rules(job)


def test_a_flight_operations_support_manager_is_not_customer_service():
    """A real corpus look-alike: `support` naming an internal operations function, no queue."""
    job = _job("Regional Flight Operations Support Manager", (
        "What you'll do: manage and mentor a team of Flight Operations Support Coordinators, "
        "oversee regional vendor strategy, forecast staffing requirements, and lead the creation "
        "of standard operating procedures. " + PROCESS_OK
    ))
    assert RULE not in _rules(job)


def test_benefits_block_mentioning_customer_support_does_not_misfire():
    job = _job("Backend Engineer", (
        "What you'll do: own our billing services and APIs. "
        "Benefits: health insurance, learning budget, and 24/7 customer support for your benefits "
        "questions through our help desk. " + PROCESS_OK
    ))
    assert RULE not in _rules(job)


def test_an_explicitly_negated_support_duty_does_not_exclude():
    job = _job("Automation Engineer", (
        "What you'll do: automate internal workflows. This role does not handle customer calls "
        "and there is no support queue responsibility. " + PROCESS_OK
    ))
    assert RULE not in _rules(job)


# --------------------------------------------------------------------------------------------------
# The third state: neither excluded nor automatically suitable
# --------------------------------------------------------------------------------------------------
def test_internal_support_queue_is_pending_not_excluded():
    """Internal users are explicitly welcome, so an internal queue is a review item, not a negative."""
    job = _job("IT Support Analyst", (
        "What you'll do: work the internal help desk for employees, resolve staff tickets, and "
        "support internal users with laptops and access. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert RULE not in _rules(job)
    assert RULE in _rules(job, "pending_checks")
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value


def test_a_queue_with_an_unnamed_audience_is_pending_not_excluded():
    """Policy sentence: Ambiguous or insufficient evidence stays visible for review; do not invent a negative."""
    job = _job("Operations Specialist", (
        "What you'll do: monitor the ticket queue and resolve requests as they arrive. " + PROCESS_OK
    ))
    assert RULE in _rules(job, "pending_checks")
    assert RULE not in _rules(job)


def test_a_vague_application_support_title_is_not_automatically_suitable():
    """Policy sentence: Do not make a vague application-support title automatically suitable either."""
    job = _job("Application Support Analyst", (
        "Join our growing team. We value curiosity and ownership. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert RULE in _rules(job, "pending_checks")
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value


def test_a_support_shaped_title_with_software_duties_is_eligible_with_a_recorded_guard():
    job = _job("Application Support Engineer", (
        "What you'll do: own and extend the internal applications behind our order workflow, "
        "build integrations, and automate manual data handling. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert result.outcome == ScreenOutcome.ELIGIBLE.value, result.human_reason()
    assert RULE in _rules(job, "suppressed")


def test_a_customer_support_engineer_is_decided_by_duties_not_by_title():
    """An engineering noun turns an external-support title into a duty question, both ways."""
    builds = _job("Customer Support Engineer", (
        "What you'll do: build and own the diagnostic tooling our support organization uses, and "
        "the integrations behind it. " + PROCESS_OK
    ))
    assert RULE not in _rules(builds)

    works_queue = _job("Customer Support Engineer", (
        "What you'll do: answer inbound calls from customers and resolve customer tickets to meet "
        "our average handle time targets. " + PROCESS_OK
    ))
    assert RULE in _rules(works_queue)


def test_a_support_title_with_no_description_stays_visible_rather_than_passing_silently():
    job = _job("Technical Support Specialist", "")
    result = screen_job(job)
    assert result.outcome != ScreenOutcome.ELIGIBLE.value
    assert RULE in _rules(job) | _rules(job, "pending_checks")


# --------------------------------------------------------------------------------------------------
# The clarification created no OTHER new rule. It says so in its own last bullet.
# --------------------------------------------------------------------------------------------------
INTERNAL_SOFTWARE = (
    "What you'll do: build internal applications, integrations and reporting for our operations "
    "team, and own the automation behind them. " + PROCESS_OK
)


def test_no_new_salary_floor_was_introduced():
    """Policy sentence: this clarification creates no new salary floor"""
    for lo, hi in ((60_000, 80_000), (95_000, 115_000), (130_000, 150_000), (300_000, 340_000)):
        job = _job("Software Engineer", INTERNAL_SOFTWARE)
        job.salary = SalaryStruct(min=lo, max=hi, currency="USD", period="year",
                                  source=SalarySource.STATED)
        result = screen_job(job)
        assert result.outcome == ScreenOutcome.ELIGIBLE.value, (lo, hi, result.human_reason())
        assert not any("compensation" in h.rule_id or "salary" in h.rule_id
                       for h in result.exclusions), (lo, hi)


def test_no_new_title_ban_was_introduced():
    for title in ("Software Engineer", "Senior Software Engineer", "Staff Software Engineer",
                  "Software Architect", "Business Applications Developer",
                  "Automation Engineer", "Internal Tools Engineer"):
        result = screen_job(_job(title, INTERNAL_SOFTWARE))
        assert result.outcome == ScreenOutcome.ELIGIBLE.value, (title, result.human_reason())


def test_no_ai_keyword_requirement_was_introduced():
    """"AI is not required." A posting with no AI wording at all must not be excluded or pended."""
    result = screen_job(_job("Software Engineer", INTERNAL_SOFTWARE))
    assert "ai" not in {h.rule_id for h in result.exclusions + result.pending_checks}
    assert result.outcome == ScreenOutcome.ELIGIBLE.value


def test_no_specialist_platform_mastery_is_assumed():
    """Policy sentence: not a claim of expertise in every business domain or specialist IT platform."""
    job = _job("Software Engineer", (
        "Requirements: experience with NetSuite, Workday, ServiceNow and Salesforce is a plus. "
        + INTERNAL_SOFTWARE
    ))
    assert screen_job(job).outcome == ScreenOutcome.ELIGIBLE.value


# --------------------------------------------------------------------------------------------------
# Projection bookkeeping: the rule is mapped to the sources it came from
# --------------------------------------------------------------------------------------------------
def test_the_new_rule_is_mapped_to_its_policy_sources():
    assert RULE in RULE_SOURCE_MAP
    assert set(RULE_SOURCE_MAP[RULE]) == {"workflow", "operating_plan"}


def test_the_ruleset_version_records_the_change():
    # 1.5.0 was this file's own change (the customer-service-queue rule). 1.6.0 adds the Loom /
    # video-walkthrough spellings to `recorded-video`, after a live posting requiring one reached
    # the retained pool on 2026-09-28 (tests/test_broad_ownership.py). The pin is updated rather
    # than loosened: its point is that a behavior change moves the version, and this one did.
    assert SCREENING_RULESET_VERSION == "1.6.0"


# --------------------------------------------------------------------------------------------------
# Misfires found by running the rule over the captured corpus, each fixed and pinned here
# --------------------------------------------------------------------------------------------------
def test_building_ai_agents_for_an_it_help_desk_is_engineering_not_the_help_desk():
    """Corpus misfire: an AI engineering role read as working a help desk.

    Both sentences are the candidate BUILDING the automation. The guard missed them because the
    software noun sat behind adjectives ("an AI-powered IT Help Desk Automation platform").
    """
    job = _job("Senior AI Solutions Engineer (Python & AWS Bedrock)", (
        "About the Role: we are looking for an experienced AI Solutions Engineer to help build an "
        "AI-powered IT Help Desk Automation platform using AWS Bedrock. You will design and "
        "orchestrate AI agents capable of handling IT help desk workflows. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert RULE not in _rules(job), result.human_reason()
    assert RULE not in _rules(job, "pending_checks")


def test_writing_help_desk_documentation_is_not_working_the_help_desk():
    """Corpus misfire: translating and creating help-desk manuals is authoring, not answering."""
    job = _job("Technical Translator", (
        "Responsibilities will include translating and creating Help Desk content (manuals, "
        "installation guides, troubleshooting articles) for our European market. " + PROCESS_OK
    ))
    result = screen_job(job)
    assert RULE not in _rules(job), result.human_reason()


def test_a_bare_phone_call_mention_with_no_audience_is_not_a_support_queue():
    """Corpus misfire: motivational prose in a consultant posting is not queue evidence."""
    job = _job("Implementation Consultant", (
        "What you'll do: lead customer onboarding projects and configure our platform. Every phone "
        "call you answer and every email you send can affect how a fleet runs. " + PROCESS_OK
    ))
    assert RULE not in _rules(job)
    assert RULE not in _rules(job, "pending_checks")


def test_the_real_queue_duty_is_still_found_when_a_documentation_duty_sits_beside_it():
    """The same corpus posting that misfired also has a genuine queue duty. It must still exclude,
    and the recorded evidence must be the queue duty rather than the documentation sentence."""
    job = _job("Sales Support Specialist", (
        "Responsibilities will include translating and creating Help Desk content (manuals, "
        "installation guides, troubleshooting articles). "
        "Field Inbound Sales & Support Calls, Website Chats & Emails. "
        "Assist customers with printer installation questions. " + PROCESS_OK
    ))
    assert RULE in _rules(job)
    hit = next(h for h in screen_job(job).exclusions if h.rule_id == RULE)
    assert "content" not in hit.matched_text.lower()


# --------------------------------------------------------------------------------------------------
# Defects found by the independent review of this change, each repaired and pinned here
# --------------------------------------------------------------------------------------------------
# M1: a help desk is the canonical INTERNAL IT function. Reading the noun as self-evidently external
# hard-excluded exactly the internal problem-ownership roles the clarification opens up — in some
# cases with evidence text that contained the word "internal".
M1_INTERNAL_CASES = (
    ("IT Systems Engineer", "You will manage the internal service desk queue."),
    ("Business Applications Engineer",
     "You will handle the internal helpdesk requests for our ERP system."),
    ("DevOps Engineer", "You will resolve support tickets raised by staff and automate our deploys."),
    ("IT Engineer",
     "You will cover the service desk queue on a rotation. You will also build PowerShell automation."),
    ("IT Operations Engineer",
     "Our company has 400 employees. Duties: manage the help desk and write automation scripts."),
    ("Systems Engineer",
     "Responsibilities: Automate device provisioning, and handle help desk tickets escalated to you."),
    ("IT Systems Engineer",
     "What you will do: Own the systems our employees rely on. You will troubleshoot problems "
     "reported by staff, manage the internal service desk queue, automate onboarding, and write "
     "scripts to eliminate manual work."),
)


def test_internal_help_desk_ownership_is_never_hard_excluded():
    """Policy sentence: distinguish software-building and internal problem ownership from an external
    customer-support queue or call-center role."""
    for title, description in M1_INTERNAL_CASES:
        job = _job(title, description + " " + PROCESS_OK)
        result = screen_job(job)
        assert RULE not in _rules(job), (title, result.human_reason())
        assert result.outcome != ScreenOutcome.EXCLUDED.value, (title, result.human_reason())


def test_internal_help_desk_ownership_stays_visible_for_review():
    """Not excluded is not the same as silently passed: the third state must actually be used."""
    for title, description in M1_INTERNAL_CASES:
        job = _job(title, description + " " + PROCESS_OK)
        assert RULE in _rules(job, "pending_checks"), title


def test_no_exclusion_reason_claims_external_about_evidence_that_says_internal():
    """The evidence recorded must not contradict the verdict it is offered as proof of."""
    for title, description in M1_INTERNAL_CASES:
        job = _job(title, description + " " + PROCESS_OK)
        for hit in screen_job(job).exclusions:
            if hit.rule_id != RULE:
                continue
            assert "internal" not in hit.matched_text.lower(), (title, hit.matched_text)
            assert "external" not in hit.reason.lower(), (title, hit.reason)


# M2: a call-center or customer-service TITLE used to be cleared to ELIGIBLE by any software verb
# anywhere in the description — the same description-scope mistake the sales rule already learned.
def test_a_call_center_title_is_not_cleared_by_a_software_sentence():
    """Policy sentence: Do not target call centers, external customer service or customer
    phone-support queues."""
    for title, description in (
        ("Call Center Representative",
         "You will answer telephone enquiries from our customers all day. You will also build reports."),
        ("Call Center Agent",
         "You will write scripts to help yourself work faster. You will speak with people all day."),
        ("Contact Centre Advisor",
         "You will take telephone enquiries from members. You will maintain scripts."),
    ):
        job = _job(title, description + " " + PROCESS_OK)
        assert RULE in _rules(job), (title, screen_job(job).human_reason())


def test_a_customer_service_title_is_never_returned_as_eligible_on_keyword_evidence():
    """A title the policy rejects outright is not cleared by a software keyword. Where the duties
    genuinely read as software the honest answer is a look at the posting, not a pass."""
    for title, description in (
        ("Customer Service Representative",
         "You will speak with our customers on the telephone about their accounts. You will "
         "configure systems as needed."),
        ("Customer Service Representative",
         "You will build reports in Excel and speak with our customers every day about their orders."),
        ("Customer Care Associate", "You will develop workflows and maintain our documentation."),
        ("Member Services Coordinator",
         "You will build integrations between our CRM and billing platform."),
        ("Help Desk Analyst",
         "You will provide first-line assistance to our clients over the telephone. You will also "
         "maintain scripts used by the team."),
        ("Application Support Analyst",
         "You will be the voice of our customers: answer their questions by telephone and live "
         "chat, resolve their issues, and write scripts to speed up common fixes."),
        ("Service Desk Advisor",
         "You will provide telephone assistance to our customers and maintain reporting."),
    ):
        job = _job(title, description + " " + PROCESS_OK)
        result = screen_job(job)
        assert result.outcome != ScreenOutcome.ELIGIBLE.value, (title, result.human_reason())
        assert RULE in _rules(job) | _rules(job, "pending_checks"), title


# M3: ordinary external-support phrasings the channel list did not cover. The `Support Consultant`
# case produced no exclusion, no pending check and no suppressed hit at all — a silent pass.
def test_ordinary_external_support_phrasings_are_not_silently_passed():
    for title, description in (
        ("Support Consultant",
         "In this role you will answer phone calls and emails from our customers."),
        ("Technical Support Specialist",
         "In this role you will answer phone calls and emails from our customers, troubleshoot "
         "their account problems, and document each case in Zendesk."),
        ("Support Advisor", "You will answer telephone enquiries from our customers."),
        ("Product Support Analyst", "You will field questions from customers by phone all day."),
        ("Operations Support Analyst",
         "You will respond to emails from our clients and log each one."),
    ):
        job = _job(title, description + " " + PROCESS_OK)
        result = screen_job(job)
        assert result.outcome != ScreenOutcome.ELIGIBLE.value, (title, result.human_reason())
        assert RULE in _rules(job), (title, result.human_reason())


def test_an_audience_split_across_a_coordinator_is_still_found():
    """`answer phone calls and emails from our customers` splits on `and`, so duty-span scope lost
    the audience and discarded the finding. Audience is read at clause scope; guards are not."""
    job = _job("Operations Associate",
               "You will answer phone calls and emails from our customers. " + PROCESS_OK)
    assert RULE in _rules(job)


def test_the_guards_are_still_duty_span_scoped_after_that_widening():
    """Widening the AUDIENCE scope must not widen the GUARD scope."""
    job = _job("Customer Support Specialist", (
        "What you'll do: answer inbound calls from customers all day. "
        "You will also build internal reports about ticket volume. " + PROCESS_OK
    ))
    assert RULE in _rules(job)


def test_note_the_missing_location_rule_is_now_mapped():
    """`location-residency` is emitted by the location logic but was absent from the rule map."""
    assert "location-residency" in RULE_SOURCE_MAP
