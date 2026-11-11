"""Deterministic candidate screening against the central policy's exclusions.

No LLM. Every verdict is a matched pattern plus the text that matched it, so a wrong exclusion is
diagnosable instead of mysterious. The plan is explicit: "Do not make an LLM the sole authority for
exclusions or invent facts."

The hard part is not the exclusions — it is **not misfiring**. Each of these is a real failure mode
the policy calls out by name:

  a benefits block that mentions commission      is not a sales quota
  a live video call with human interviewers      is not a recorded-video application
  building tools FOR the sales team              is not doing sales
  "government customers"                         is not a clearance requirement
  a backend role that mentions React             is not a frontend-specialist role
  an EEO statement mentioning veteran status     is not a defense job

So rules are **section-aware**. A signal found in a responsibilities or requirements block means
something different from the same word in a benefits or equal-opportunity block, and the screener
tracks which section each match came from.

Third state, always: UNKNOWN is not eligible and not excluded. When the description is truncated or
the application form cannot be inspected, the verdict is PENDING_CHECK with the specific thing that
needs checking — never a claim that no recorded video or AI interview is required.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from src.candidate.location import (
    ATTENDANCE_REQUIRED_RE,
    WorksiteClass,
    best_worksite,
    find_residency_restriction,
    parse_places,
)
from src.common.models import CanonicalJob, ScreenOutcome, VerificationState
from src.common.normalize import normalize_title_for_matching

SCREENING_RULESET_VERSION = "1.7.0"


# --------------------------------------------------------------------------------------------------
# Section segmentation
# --------------------------------------------------------------------------------------------------
class Section:
    RESPONSIBILITIES = "responsibilities"
    REQUIREMENTS = "requirements"
    BENEFITS = "benefits"
    PROCESS = "process"
    EEO = "eeo"
    ABOUT = "about"
    BODY = "body"          # unlabeled prose
    TITLE = "title"


_SECTION_CUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (Section.RESPONSIBILITIES, re.compile(
        r"\b(what you(?:'ll| will) do|responsibilities|the role|in this role|your impact|"
        r"day[- ]to[- ]day|what you(?:'ll| will) be doing|key duties|about the role)\b", re.I)),
    (Section.REQUIREMENTS, re.compile(
        r"\b(requirements|qualifications|what (?:we(?:'re| are) looking for|you(?:'ll| will) need)|"
        r"you have|must have|nice to have|preferred|skills|experience required|about you)\b", re.I)),
    (Section.BENEFITS, re.compile(
        r"\b(benefits|perks|what we offer|compensation(?: (?:and|&) benefits)?|total rewards|"
        r"salary (?:range|and benefits)|pay (?:range|transparency)|our offer)\b", re.I)),
    (Section.PROCESS, re.compile(
        r"\b(interview process|hiring process|application process|how to apply|what to expect|"
        r"next steps|our process|recruitment process)\b", re.I)),
    (Section.EEO, re.compile(
        r"\b(equal (?:employment )?opportunity|eeo|e-verify|affirmative action|"
        r"we are an equal|diversity(?:,| and) (?:equity|inclusion)|accommodation request|"
        r"reasonable accommodation|protected veteran|pay transparency nondiscrimination)\b", re.I)),
    (Section.ABOUT, re.compile(
        r"\b(about (?:us|the company|our company)|who we are|our mission|our story|company overview)\b",
        re.I)),
)

# A heading is a short line. Splitting on sentence-ish boundaries too, because plenty of feeds ship
# the whole description as one HTML-stripped paragraph with no line breaks left.
_LINE_SPLIT_RE = re.compile(r"(?:\r?\n)+|(?<=[.;:!?])\s+(?=[A-Z])")


@dataclass
class Segment:
    section: str
    text: str
    # True inside a block whose heading marks it as preferred / nice-to-have. Read only by rules that
    # must tell a stated duty from a wished-for qualification (voice/telephony).
    preferred: bool = False


def segment_description(text: str) -> list[Segment]:
    """Split a description into (section, text) segments.

    Heuristic and honest about it: a cue phrase switches the current section, and everything until
    the next cue belongs to it. Unlabeled prose is BODY. This is not a parser for a schema that does
    not exist — it exists so a benefits clause and a responsibility clause can be told apart.
    """
    if not text:
        return []
    segments: list[Segment] = []
    current = Section.BODY
    preferred = False
    for chunk in _LINE_SPLIT_RE.split(text):
        piece = chunk.strip()
        if not piece:
            continue
        for name, cue in _SECTION_CUES:
            if cue.search(piece[:120]):
                current = name
                preferred = bool(_PREFERRED_HEADING_RE.search(piece[:60]))
                break
        segments.append(Segment(section=current, text=piece, preferred=preferred))
    return segments


_PREFERRED_HEADING_RE = re.compile(
    r"\b(preferred|nice[- ]to[- ]have|bonus points?|pluses|desirable)\b", re.I)


# --------------------------------------------------------------------------------------------------
# Rule definitions
# --------------------------------------------------------------------------------------------------
@dataclass
class RuleHit:
    rule_id: str
    outcome: str
    matched_text: str
    section: str
    reason: str
    suppressed_by: str | None = None


@dataclass
class ScreenResult:
    job_id: str
    outcome: str = ScreenOutcome.ELIGIBLE.value
    exclusions: list[RuleHit] = field(default_factory=list)
    pending_checks: list[RuleHit] = field(default_factory=list)
    suppressed: list[RuleHit] = field(default_factory=list)   # misfires the guards caught
    notes: list[str] = field(default_factory=list)
    ruleset_version: str = SCREENING_RULESET_VERSION

    @property
    def excluded(self) -> bool:
        return self.outcome == ScreenOutcome.EXCLUDED.value

    def human_reason(self) -> str:
        if self.exclusions:
            return "; ".join(f"{h.rule_id}: {h.reason}" for h in self.exclusions)
        if self.pending_checks:
            return "; ".join(f"{h.rule_id}: {h.reason}" for h in self.pending_checks)
        return "no policy exclusion matched"

    def to_json(self) -> dict:
        def hits(items):
            return [
                {
                    "rule_id": h.rule_id, "outcome": h.outcome, "section": h.section,
                    "matched_text": h.matched_text[:160], "reason": h.reason,
                    "suppressed_by": h.suppressed_by,
                }
                for h in items
            ]

        return {
            "job_id": self.job_id,
            "outcome": self.outcome,
            "ruleset_version": self.ruleset_version,
            "exclusions": hits(self.exclusions),
            "pending_checks": hits(self.pending_checks),
            "suppressed_misfires": hits(self.suppressed),
            "notes": list(self.notes),
        }


def _context(text: str, match: re.Match, width: int = 90) -> str:
    start = max(0, match.start() - width // 2)
    end = min(len(text), match.end() + width // 2)
    return re.sub(r"\s+", " ", text[start:end]).strip()


# --------------------------------------------------------------------------------------------------
# Polarity: does the sentence REQUIRE the thing, or explicitly not require it?
# --------------------------------------------------------------------------------------------------
# The P01 defect this fixes: matching a requirement phrase and ignoring the words around it. "No
# security clearance is required" was excluded for requiring a clearance, and "We do not require a
# recorded video" was excluded for requiring a video. Matching a noun phrase is not reading a
# sentence, and the difference is the whole meaning.

# Clause boundaries. A clause, not a whole sentence, is the right scope: "Python is required, no
# clearance is needed" must not let the first half negate the second.
_CLAUSE_SPLIT_RE = re.compile(r"[.;:!?]|,\s*(?:and|but|or|however|although|though)\b|\n|•|\s-\s")

# Negators appearing BEFORE the matched phrase inside its clause.
_NEGATION_BEFORE_RE = re.compile(
    r"\b(no|not|never|without|none|neither|nor|free\s+of|exempt\s+from|"
    r"does\s+not|do\s+not|did\s+not|doesn'?t|don'?t|isn'?t|aren'?t|won'?t|"
    r"will\s+not|is\s+not|are\s+not|cannot|can'?t|lacks?|absent|"
    r"there\s+is\s+no|there\s+are\s+no|we\s+don'?t|we\s+do\s+not)\b",
    re.I,
)
# Negators/optionality appearing AFTER the matched phrase inside its clause.
_NEGATION_AFTER_RE = re.compile(
    r"\b(is\s+not\s+(?:required|needed|necessary|expected)|"
    r"are\s+not\s+(?:required|needed|necessary|expected)|"
    r"not\s+(?:required|needed|necessary|expected)|"
    r"is\s+optional|are\s+optional|optional|"
    r"a\s+plus|nice\s+to\s+have|bonus|preferred\s+but\s+not\s+required|"
    r"is\s+waived|not\s+a\s+requirement)\b",
    re.I,
)
# Phrases that make something explicitly OPTIONAL rather than absent. Distinguished from a flat
# negation because an optional-but-mentioned requirement is still worth a human glance.
_OPTIONALITY_RE = re.compile(
    r"\b(a\s+plus|nice\s+to\s+have|bonus|optional|preferred\s+but\s+not\s+required|"
    r"not\s+strictly\s+required|helpful\s+but\s+not)\b",
    re.I,
)


def clause_around(text: str, match: re.Match) -> tuple[str, int]:
    """Return (clause_text, offset_of_match_within_clause) for the clause containing `match`."""
    start = 0
    for boundary in _CLAUSE_SPLIT_RE.finditer(text):
        if boundary.end() <= match.start():
            start = boundary.end()
        else:
            break
    end = len(text)
    for boundary in _CLAUSE_SPLIT_RE.finditer(text):
        if boundary.start() >= match.end():
            end = boundary.start()
            break
    return text[start:end], match.start() - start


def polarity(text: str, match: re.Match) -> str:
    """Classify the matched requirement as `required`, `negated`, or `optional`.

    Only the matched phrase's own clause is consulted, so an adjacent requirement cannot flip it.
    """
    clause, offset = clause_around(text, match)
    before = clause[:offset]
    after = clause[offset + (match.end() - match.start()):]

    if _OPTIONALITY_RE.search(after) or _OPTIONALITY_RE.search(before):
        return "optional"
    if _NEGATION_AFTER_RE.search(after):
        return "negated"
    if _NEGATION_BEFORE_RE.search(before):
        return "negated"
    return "required"


# --------------------------------------------------------------------------------------------------
# Whose work is this? Building software FOR a sales team is not doing sales.
# --------------------------------------------------------------------------------------------------
# The P01 defect this fixes: "Build tools for the sales team to research prospects" was excluded as
# sales ownership, and a growth role whose output "reaches members or prospects" was excluded because
# the word `prospects` appeared. A noun naming the people a product serves is not a duty.

# A software-artifact frame: the sentence is about a thing being built, not a quota being carried.
_TOOLING_FRAME_RE = re.compile(
    r"\b(?:build|building|built|maintain|maintaining|develop|developing|create|creating|ship|"
    r"shipping|own|owning|design|designing|improve|improving|extend|support|scale|integrate)\s+"
    r"(?:the\s+|our\s+|a\s+|an\s+|new\s+|internal\s+|existing\s+)*"
    r"(tool|tools|tooling|platform|platforms|dashboard|dashboards|system|systems|app|apps|"
    r"application|applications|integration|integrations|feature|features|service|services|"
    r"infrastructure|api|apis|pipeline\s+data|report|reports|reporting|automation|workflow|"
    r"workflows|software|product|products)\b",
    re.I,
)
# ...or a software noun followed by who uses it / what it does.
_TOOLING_SUBJECT_RE = re.compile(
    r"\b(tool|tools|tooling|platform|dashboard|dashboards|system|systems|app|application|"
    r"applications|feature|features|service|services|software|product|integration|integrations|"
    r"automation|report|reports|reporting)\b\s+(?:that|which|for|our|the|used\s+by|to\s+help)\b",
    re.I,
)
# Sales-adjacent vocabulary that is NOT itself an ownership duty. Its presence in a duty sentence
# without a tooling frame is genuinely ambiguous, so it routes to review rather than to a verdict.
_SALES_ADJACENT_RE = re.compile(
    r"\b(sales\s+team|revenue\s+team|gtm\s+team|sales\s+org(?:anization)?|account\s+executives?|"
    r"pipeline\s+visibility|customer\s+outreach|quota\s+attainment|prospects|"
    r"work\s+(?:closely\s+)?with\s+(?:the\s+)?sales)\b",
    re.I,
)
# Frames that make the sentence about the CANDIDATE's own duties.
_OWN_DUTY_FRAME_RE = re.compile(
    r"\b(you\s+will|you'?ll|your\s+responsibilities|your\s+role|"
    r"responsible\s+for|you\s+are\s+expected\s+to|the\s+role\s+(?:is|involves)|"
    r"in\s+this\s+role|your\s+quota|you\s+own)\b",
    re.I,
)


def describes_a_software_artifact(text: str, match: re.Match) -> bool:
    """True when the matched phrase sits in a DUTY SPAN about building or running software.

    Duty-span scope, not clause scope. "You will build tools for the sales team and carry a sales
    quota" is one clause containing two duties, and judging the whole clause let the software frame
    blanket the quota — so the exclusion was suppressed. Coordinated duties are separated first.
    """
    span, _offset = duty_span_around(text, match)
    return bool(_TOOLING_FRAME_RE.search(span) or _TOOLING_SUBJECT_RE.search(span))


def describes_own_duty(text: str, match: re.Match) -> bool:
    clause, _offset = clause_around(text, match)
    return bool(_OWN_DUTY_FRAME_RE.search(clause))


# Coordinators that join two SEPARATE duties inside one clause. Splitting on these is what stops a
# software frame in one half from excusing a mandatory duty in the other.
_DUTY_SPLIT_RE = re.compile(
    r"\s+(?:and\s+(?:also\s+)?|while\s+also\s+|while\s+|as\s+well\s+as\s+|plus\s+)", re.I
)


def duty_span_around(text: str, match: re.Match) -> tuple[str, int]:
    """The coordinated sub-clause containing `match`, for attributing a duty to the candidate."""
    clause, offset = clause_around(text, match)
    start = 0
    for boundary in _DUTY_SPLIT_RE.finditer(clause):
        if boundary.end() <= offset:
            start = boundary.end()
        else:
            break
    end = len(clause)
    match_len = match.end() - match.start()
    for boundary in _DUTY_SPLIT_RE.finditer(clause):
        if boundary.start() >= offset + match_len:
            end = boundary.start()
            break
    return clause[start:end], offset - start


# --------------------------------------------------------------------------------------------------
# Evidence aggregation
# --------------------------------------------------------------------------------------------------
# The P02 defect this replaces: `_find` returned the FIRST match only, so an earlier negation ended
# the search and a later mandatory requirement was never examined. "We do not require a recorded
# video. You must complete a one-way video interview" read as ELIGIBLE.
#
# Requirements are now collected across every relevant section and aggregated, with one governing
# rule: a negated or optional statement about a step cannot cancel a SEPARATE mandatory step.


@dataclass
class Finding:
    """One matched requirement phrase, with everything needed to judge it."""

    section: str
    matched_text: str
    context: str
    polarity: str            # required | negated | optional
    is_artifact: bool        # the phrase describes software being built, not a duty
    is_own_duty: bool


def collect_findings(
    segments: list[Segment],
    pattern: re.Pattern[str],
    sections: tuple[str, ...] | None = None,
) -> list[Finding]:
    """Every match of `pattern` across the permitted sections, each independently classified."""
    findings: list[Finding] = []
    for seg in segments:
        if sections and seg.section not in sections:
            continue
        for match in pattern.finditer(seg.text):
            findings.append(Finding(
                section=seg.section,
                matched_text=match.group(0),
                context=_context(seg.text, match),
                polarity=polarity(seg.text, match),
                is_artifact=describes_a_software_artifact(seg.text, match),
                is_own_duty=describes_own_duty(seg.text, match),
            ))
    return findings


def mandatory(findings: list[Finding], *, artifact_excuses: bool = False) -> list[Finding]:
    """Findings that state an actual requirement.

    `artifact_excuses` marks families where a software-artifact framing genuinely changes the
    meaning (sales duties). For a process step like a recorded video it does not: a video
    requirement is not excused by the role also building software.
    """
    out = []
    for finding in findings:
        if finding.polarity != "required":
            continue
        if artifact_excuses and finding.is_artifact:
            continue
        out.append(finding)
    return out


def optional_only(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.polarity == "optional"]


def negated_only(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.polarity == "negated"]


# A stated alternative to a recorded video means the video is genuinely avoidable.
_VIDEO_ALTERNATIVE_RE = re.compile(
    r"\b(instead|alternativ|in\s+place\s+of|or\s+a\s+live|live\s+(?:video\s+)?(?:call|interview)|"
    r"you\s+may\s+(?:instead|opt|choose|request)|if\s+you\s+prefer|either)\b",
    re.I,
)


# ---- sales ---------------------------------------------------------------------------------------
# Owning sales OUTCOMES is the exclusion. Building software that sales people use is not.
_SALES_OWNERSHIP_RE = re.compile(
    # Every alternative names an ACTIVITY or an OWNED OUTCOME. Bare `prospects` was removed: it is a
    # noun for the people a product reaches, and it excluded a growth-engineering role whose output
    # "reaches members or prospects" plus a tooling role that helped a team "research prospects".
    # Prospecting as a verb stays.
    r"\b(sales quota|quota[- ]carrying|carry(?:ing)? a quota|meet (?:or exceed )?(?:your )?(?:sales )?quota|"
    r"book of business|own(?:ing)? (?:the |your )?(?:sales )?pipeline|pipeline generation|"
    r"prospecting\b|prospect for\b|(?:generate|generating|source|sourcing) (?:new )?prospects|"
    r"cold[- ]call(?:ing|s)?|cold outreach|outbound (?:calls|prospecting)|"
    r"clos(?:e|ing) (?:deals|business|new business)|new business development|account acquisition|"
    r"revenue (?:quota|target)s?|territory (?:plan|management)|upsell|cross[- ]sell)\b",
    re.I,
)
_SALES_TITLE_RE = re.compile(
    r"\b(account executive|account manager|sales engineer|sales development|sdr|bdr|"
    r"solutions? consultant|pre[- ]?sales|business development(?: representative| manager)?|"
    r"customer success manager|sales representative)\b",
    re.I,
)
# Guard: engineering FOR the revenue org is explicitly acceptable per the preferences file.
_SALES_TOOLING_GUARD_RE = re.compile(
    r"\b(gtm engineer(?:ing)?|revops|revenue operations|sales engineering (?:tools|platform)|"
    r"tools? (?:for|used by) (?:the )?(?:sales|revenue|gtm) team|internal (?:sales|crm) tool|"
    r"sales enablement (?:platform|tooling)|crm integration|salesforce (?:integration|developer))\b",
    re.I,
)
_COMMISSION_RE = re.compile(r"\b(commission|variable compensation|on[- ]target earnings|ote)\b", re.I)


# ---- clearance / government ----------------------------------------------------------------------
_CLEARANCE_RE = re.compile(
    r"\b(security clearance|ts/sci|top secret|secret clearance|public trust|federal suitability|"
    r"polygraph|(?:able|ability|willing|willingness|eligible|eligibility) to obtain(?: and maintain)?"
    r"(?: a| an)? (?:security )?clearance|"
    r"active clearance|dod secret|q clearance|l clearance|suitability determination|"
    r"itar|export[- ]controlled|drug (?:test|screen(?:ing)?))\b",
    re.I,
)
# "government customers" alone is adjacency, not a clearance gate -> PENDING_CHECK per policy
# ("Government-adjacent roles require explicit reconsideration by Brett before preparation").
_GOV_ADJACENT_RE = re.compile(
    r"\b(government (?:customers?|clients?|agenc(?:y|ies)|contracts?)|public sector|federal agenc|"
    r"defense (?:customers?|industry)|gov(?:ernment)?[- ]?tech|civic technology|fedramp)\b",
    re.I,
)


# ---- frontend specialization ---------------------------------------------------------------------
_FRONTEND_TITLE_RE = re.compile(
    r"\b(front[- ]?end (?:engineer|developer|architect)|ui (?:engineer|developer)|"
    r"design systems? engineer|web designer|ux engineer)\b", re.I,
)
_FRONTEND_DEPTH_RE = re.compile(
    r"\b(design system(?:s)? (?:owner|ownership|authority)|pixel[- ]perfect|visual polish|"
    r"deep (?:react|vue|angular) (?:expertise|specialization)|frontend (?:authority|architecture)|"
    r"css architecture|component library ownership|browser rendering performance)\b", re.I,
)
# Guard: full stack / backend roles naturally mention React and stay eligible.
_FULLSTACK_GUARD_RE = re.compile(
    r"\b(full[\s\-]?stack|backend|back[- ]end|api|server[- ]side|platform engineer|"
    r"end[- ]to[- ]end ownership)\b", re.I,
)


# ---- recorded video ------------------------------------------------------------------------------
_RECORDED_VIDEO_RE = re.compile(
    r"\b(one[- ]way (?:video|interview)|recorded video|video (?:introduction|intro|submission|essay)|"
    r"record (?:a|your) (?:short )?video|asynchronous video|pre[- ]recorded (?:video|interview)|"
    r"upload (?:a|your) video|video (?:response|answers)|hirevue|spark ?hire|willo|"
    # Found live on 2026-09-28: a posting opening "applying to this role requires a Loom video
    # walkthrough under 5 minutes" reached the retained pool. The operator's exclusion is on
    # producing a recorded candidate video, and naming the tool is the most common way a posting
    # asks for one — `loom` and `video walkthrough` were both absent from this pattern.
    r"loom (?:video|walkthrough|recording)|(?:a|your) loom\b|"
    r"video walk[- ]?through|screen recording|recorded (?:walkthrough|demo|presentation)|"
    r"my ?interview|vidcruiter)\b",
    re.I,
)
# Guard: a live human video call is explicitly fine.
_LIVE_VIDEO_GUARD_RE = re.compile(
    r"\b(video (?:call|chat|conference)|zoom|google meet|microsoft teams|live (?:video )?interview|"
    r"face[- ]to[- ]face (?:video )?(?:call|interview)|meet (?:with )?(?:the|our) team)\b", re.I,
)


# ---- AI-conducted interview ----------------------------------------------------------------------
_AI_INTERVIEW_RE = re.compile(
    r"\b(ai[- ](?:conducted|led|powered|driven) interview|interview (?:with|by) (?:our |an )?ai|"
    r"ai interviewer|ai recruiter (?:call|interview|screen)|automated ai (?:interview|screen)|"
    r"ai[- ]based (?:screening|interview)|virtual ai (?:recruiter|interviewer)|"
    r"conversation with our ai|apriora|micro1 ai interview)\b",
    re.I,
)
# Guard: the company merely building or using AI in its product is not an AI interview.
_AI_PRODUCT_GUARD_RE = re.compile(
    r"\b(ai[- ]powered (?:product|platform|features?|scheduling|sourcing)|our ai (?:product|platform)|"
    r"we (?:build|use) ai|ai[- ]assisted (?:development|coding))\b", re.I,
)


# ---- external customer service / call-center work ------------------------------------------------
# From the 2026-09-26 clarification "Adjacent roles: software problem-solving, not customer service".
# That section is unusually explicit about what it does NOT mean, and every guard below is one of its
# own sentences:
#
#   "Building software FOR a call center/support department is not WORKING its support queue."
#   "Requirements conversations, collaboration, technical delivery meetings, and diagnosing internal
#    problems are not the excluded work."
#   "Internal users and stakeholders are welcome."
#   "Evaluate the actual duties rather than the title. An application-support or IT title is not a
#    fit merely because it sounds easier to obtain."
#
# So this cannot be a banned-word list. `support` is one of the most common words in a job
# description — a platform team supports internal users, an engineer supports a service, a benefits
# block offers support for learning. What is excluded is *working an external contact queue*, and
# that is evidenced by a channel plus a handling duty plus an external audience, in one duty span.

# Titles whose subject IS an external customer-contact role. Strong evidence by themselves.
_CS_EXTERNAL_TITLE_RE = re.compile(
    r"\b(customer (?:service|support|care)|(?:call|contact) ?cent(?:er|re)|"
    r"client (?:support|services)|member services?|patient (?:access|support)|"
    r"technical support (?:representative|rep|agent|advisor|associate)|"
    r"customer experience (?:representative|rep|specialist|agent|advisor|associate)|"
    r"kundenservice|callcenter)\b",
    re.I,
)
# The subset the policy names unconditionally: "Do not target call centers". No keyword in the body
# downgrades one of these.
_CS_CALL_CENTER_TITLE_RE = re.compile(
    r"\b((?:call|contact) ?cent(?:er|re)|callcenter|kundenservice)\b", re.I,
)
# Support-shaped titles that genuinely cannot be decided from the title. The policy refuses both
# answers here: not automatically excluded, and not automatically suitable either.
_CS_AMBIGUOUS_TITLE_RE = re.compile(
    r"\b(help ?desk|service desk|support desk|desktop support|end[- ]user support|"
    r"application support|it support|technical support|"
    r"support (?:specialist|analyst|technician|engineer|associate|advisor)|"
    r"tier (?:1|2|3|i{1,3}|one|two|three) support)\b",
    re.I,
)
# An engineering noun in the title turns an external-support title into a duty question.
# "Customer Support Engineer" is decided by what the role actually does.
_CS_ENGINEERING_TITLE_RE = re.compile(
    r"\b(engineer|engineering|developer|software|programmer|architect|automation|"
    r"platform|devops|sre|data|full[\s\-]?stack|backend|back[- ]end)\b",
    re.I,
)
# The channel a support queue runs on, named as the work.
_CS_CHANNEL_RE = re.compile(
    # "Field Inbound Sales & Support Calls" — the qualifier between `inbound` and the channel noun is
    # ordinary posting prose, and requiring them adjacent missed a plainly stated queue duty.
    r"\b(inbound (?:[A-Za-z&/-]+\s+){0,3}(?:calls?|inquir\w+|enquir\w+|contacts?|tickets?|chats?|"
    r"emails?)|"
    r"(?:support|service) calls?|"
    r"support (?:tickets?|queue|inbox|cases?)|"
    r"(?:ticket|phone|chat|case|call|email) queue|"
    r"(?:live|web|online) chat|"
    r"phone (?:support|calls?)|telephone (?:support|calls?|enquir\w+|inquir\w+|assistance)|"
    r"first[- ]line (?:support|assistance)|front[- ]line support|"
    r"customer (?:calls?|tickets?|chats?|emails?|inquir\w+|enquir\w+|contacts?|cases?)|"
    r"client (?:calls?|tickets?|inquir\w+|enquir\w+)|"
    # Audience-carrying channel phrases. "answer phone calls and emails from our customers" splits on
    # `and`, so the audience can end up in a different duty span from the channel noun; these forms
    # keep the two together, and clause-scope audience below catches the rest.
    r"(?:calls?|emails?|chats?|tickets?|cases?|inquir\w+|enquir\w+|questions?|requests?|issues?)\s+"
    r"(?:from|by|of)\s+(?:our\s+|the\s+|external\s+)?"
    r"(?:customers?|clients?|members?|patients?|subscribers?|policyholders?|guests?|callers?)|"
    r"(?:by|over|via|on)\s+(?:the\s+)?(?:phone|telephone|live chat)|"
    r"first[- ](?:call|contact) resolution|average handle time|call volume|"
    r"tickets? per (?:day|week|hour|shift)|csat|customer satisfaction score|"
    r"help ?desk|service desk|support desk|(?:call|contact) ?cent(?:er|re))\b",
    re.I,
)
# Channels that already name an external audience or a support queue, so no separate audience word is
# needed: "customer calls" and "help desk" carry their own subject.
_CS_SELF_EVIDENT_CHANNEL_RE = re.compile(
    # Channels that name an external audience in themselves. `inbound` qualifies: a contact arriving
    # from outside. `customer` and `client` name the audience outright. A contact centre is one by
    # definition, and the four metrics are only ever measured on a customer contact queue.
    #
    # A help desk, service desk or support-ticket queue is deliberately NOT here. That was a real
    # defect found in review: a help desk is the canonical INTERNAL IT function, so reading the noun
    # as self-evidently external hard-excluded exactly the internal problem-ownership roles this
    # clarification was written to open up — including postings whose own evidence text said
    # "internal". Those channels are queue-SHAPED (see below), so with no stated audience they now
    # route to review instead of to a verdict.
    r"\b(inbound|customer|client|(?:call|contact) ?cent(?:er|re)|"
    r"csat|first[- ](?:call|contact) resolution|average handle time|call volume)\b",
    re.I,
)
# Handling that channel as work, rather than building it.
_CS_HANDLING_RE = re.compile(
    r"\b(answer(?:ing)?|handl(?:e|ing)|field(?:ing)?|respond(?:ing)?|repl(?:y|ying)|"
    r"triag(?:e|ing)|resolv(?:e|ing)|troubleshoot(?:ing)?|assist(?:ing)?|support(?:ing)?|"
    r"serv(?:e|ing)|manag(?:e|ing)|work(?:ing)?|monitor(?:ing)?|staff(?:ing)?|cover(?:ing)?|"
    r"tak(?:e|ing)|receiv(?:e|ing)|process(?:ing)?|provid(?:e|ing)|deliver(?:ing)?|"
    # "speak with our customers on the telephone" is contact work stated as plainly as it gets, and
    # omitting these verbs let two postings titled Customer Service Representative escape the duty
    # path entirely.
    r"speak(?:ing)?|talk(?:ing)?|communicat(?:e|ing)|liais(?:e|ing)|interact(?:ing)?)\b",
    re.I,
)
# Whose questions. This is the whole hinge of the clarification: EXTERNAL customer service is
# excluded, and internal users are explicitly welcome, so the two audiences are separate lists and
# the internal one is checked first ("internal customers" is a common phrase for internal work).
_CS_INTERNAL_AUDIENCE_RE = re.compile(
    # Broad on purpose, and checked BEFORE the external list. An `internal` or `in-house` qualifier on
    # anything, or a staff/employee audience, means this is internal problem ownership — which the
    # policy welcomes. Requiring a specific noun ("internal users", "employees") missed "the internal
    # service desk queue" and "helpdesk requests ... for our ERP system", and those were hard-excluded.
    r"\b(internal|in[- ]house|employees?|staff|colleagues?|co[- ]?workers?|"
    r"our own teams?|fellow engineers?)\b",
    re.I,
)
_CS_EXTERNAL_AUDIENCE_RE = re.compile(
    r"\b(customers?|clients?|members?|patients?|subscribers?|policyholders?|guests?|callers?|"
    r"consumers?|account holders?|shoppers?|tenants?|passengers?)\b",
    re.I,
)
# Guard: software built FOR a support organization. The clarification's own distinction.
_CS_TOOLING_GUARD_RE = re.compile(
    r"\b((?:tool|tools|tooling|platform|platforms|software|application|applications|system|systems|"
    r"integration|integrations|automation|dashboard|dashboards|portal|reporting)\s+"
    r"(?:for|used by|that serves?|serving|supporting)\s+(?:the\s+|our\s+)?"
    r"(?:customer (?:service|support|care)|support|(?:call|contact) ?cent(?:er|re)|help ?desk|"
    r"service desk|cx)\b|"
    r"(?:customer (?:service|support|care)|support|(?:call|contact) ?cent(?:er|re)|help ?desk|"
    r"service desk)\s+(?:tooling|platform|software|automation|integrations?|systems?)\b|"
    r"agent[- ]facing (?:tool|tools|tooling|software|platform))",
    re.I,
)
# Guard and positive signal: the work the clarification is asking FOR — building and owning software.
_SOFTWARE_OWNERSHIP_RE = re.compile(
    r"\b(?:build|building|develop|developing|design|designing|implement|implementing|writ(?:e|ing)|"
    r"own(?:ing)?|architect(?:ing)?|maintain(?:ing)?|automat(?:e|ing)|integrat(?:e|ing)|"
    r"ship(?:ping)?|engineer(?:ing)?|code|coding|program(?:ming)?|orchestrat(?:e|ing)|"
    r"deploy(?:ing)?|configur(?:e|ing)|train(?:ing)?|fine[- ]tun(?:e|ing))\s+"
    # Adjectives intervene constantly and used to defeat this guard: "build an AI-powered IT Help
    # Desk Automation platform" is unmistakably building software, and a determiner-only gap missed
    # it, so a role whose whole job was building support automation read as working a support queue.
    r"(?:[A-Za-z0-9\-+/&.]+\s+){0,4}"
    r"(?:software|applications?|apps?|tools?|tooling|integrations?|automations?|automation|scripts?|"
    r"services?|apis?|pipelines?|dashboards?|reports?|reporting|systems?|platforms?|features?|"
    r"workflows?|databases?|agents?|models?|bots?|chatbots?|assistants?|copilots?)\b",
    re.I,
)
# Guard: the support function is the SUBJECT MATTER of an artifact, not a queue being worked.
# Translating help-desk manuals is writing documentation, not answering the help desk.
_CS_ARTIFACT_OBJECT_RE = re.compile(
    r"\b(content|documentation|docs|manuals?|guides?|articles?|knowledge[- ]base|"
    r"training materials?|playbooks?|runbooks?|scripts?|templates?|copy|collateral)\b",
    re.I,
)
# Channels that are queue-SHAPED: they name a queue, a contact centre, or a queue metric. Only these
# can carry a finding when the posting never names an audience. A bare "every phone call you answer"
# in a consultant's motivational prose is not evidence of a support queue.
_CS_QUEUE_SHAPED_CHANNEL_RE = re.compile(
    r"\b(support (?:tickets?|queue|inbox|cases?)|(?:ticket|phone|chat|case|call|email) queue|"
    r"help ?desk|service desk|support desk|(?:call|contact) ?cent(?:er|re)|"
    r"inbound (?:[A-Za-z&/-]+\s+){0,3}(?:calls?|inquir\w+|enquir\w+|contacts?|tickets?|chats?|"
    r"emails?)|"
    r"first[- ](?:call|contact) resolution|average handle time|call volume|"
    r"tickets? per (?:day|week|hour|shift)|csat|customer satisfaction score)\b",
    re.I,
)
_SOFTWARE_ROLE_RE = re.compile(
    r"\b(software (?:engineer|engineering|developer|development)|"
    r"(?:back|front)[- ]?end (?:engineer|developer)|full[\s\-]?stack|"
    r"devops|site reliability|platform engineer|data engineer|automation engineer)\b",
    re.I,
)


# ---- location -----------------------------------------------------------------------------------
# Place parsing, worksite classification, residency limits and attendance requirements all live in
# src/candidate/location.py. They used to be three regexes of hand-written town names here, which
# certified towns nobody measured and rejected a genuinely local job over a comma; that module
# documents why the replacement refuses to answer a drive-time question it cannot measure.
_REMOTE_RE = re.compile(
    r"\b(remote|work from home|wfh|distributed|anywhere|telecommut)\b", re.I)
_US_REMOTE_RE = re.compile(
    r"\b(remote[,\s-]*(?:us|usa|u\.s\.?|united states)|us[- ]remote|"
    r"(?:us|usa|united states)[,\s-]*remote|remote \(us\)|anywhere in the (?:us|united states))\b",
    re.I,
)
_ONSITE_REQUIRED_RE = re.compile(
    r"\b(on[- ]?site|in[- ]office|hybrid|\d+ days? (?:per|a) week in|"
    r"relocat(?:e|ion) (?:required|to)|must (?:be|reside) (?:located )?in)\b", re.I,
)
_NON_US_ONLY_RE = re.compile(
    r"\b(canada|united kingdom|\buk\b|europe|emea|eu only|ireland|germany|france|spain|poland|"
    r"netherlands|sweden|india|singapore|australia|brazil|mexico|latam|apac|japan|israel)\b", re.I,
)


# ---- human-first holds and voice/telephony (operator rules of 2026-10-12 and 2026-10-17) --------
# Prefix carried by every hold reason, so the report and any reader can tell "held under the
# human-first rule" from an ordinary check without parsing prose.
HUMAN_FIRST_HOLD = "HUMAN-FIRST HOLD:"
_EVALUATION_RE = re.compile(
    r"\b(take[- ]home(?: (?:assignment|project|test|exercise|challenge))?|"
    r"coding (?:challenge|assessment|test|exercise)|online assessment|"
    r"(?:technical|skills?|cognitive|aptitude|personality) (?:assessment|test)s?|"
    r"hackerrank|codility|codesignal|testgorilla|criteria (?:corp|cognitive)|ccat|"
    r"work[- ]sample (?:test|exercise|assignment))\b",
    re.I,
)
_BEFORE_HUMAN_RE = re.compile(
    r"\b(as part of (?:your|the) application|(?:with|alongside) your application|"
    r"before (?:any|the|your|we schedule (?:a|an|any)) (?:first |initial )?(?:interviews?|calls?|"
    r"conversations?)|prior to (?:an?y? )?(?:first |initial )?(?:interviews?|calls?)|"
    r"(?:the )?first step (?:is|in our process)|to apply,? (?:please )?complete|"
    r"applicants? (?:must|will be asked to) complete|before we (?:speak|talk|meet))\b",
    re.I,
)
_VOICE_TITLE_RE = re.compile(
    r"\b(voice(?: ai| agents?| assistants?| bots?| applications?| platform)?|speech|telephony|"
    r"voip|conversational audio|text to speech|speech to text|tts|asr|ivr)\b",
    re.I,
)
_VOICE_DUTY_RE = re.compile(
    r"\b(voice (?:ai|agents?|assistants?|bots?|applications?|platforms?|pipelines?|interfaces?|"
    r"experiences?)|speech (?:recognition|synthesis|models?|pipelines?)|speech[- ]to[- ]text|"
    r"text[- ]to[- ]speech|telephony|voip|sip trunk(?:ing)?|ivr|phone (?:agents?|systems?|bots?)|"
    r"call (?:routing|recording|center software)|conversational audio|real[- ]time audio)\b",
    re.I,
)
_PREFERRED_CONTEXT_RE = re.compile(
    r"\b(preferred|nice[- ]to[- ]have|bonus|a plus|is a plus|desirable|ideally)\b", re.I)


# --------------------------------------------------------------------------------------------------
# The screener
# --------------------------------------------------------------------------------------------------
def _find(segments: list[Segment], pattern: re.Pattern[str], sections=None):
    """First match of `pattern`, optionally restricted to certain section kinds."""
    for seg in segments:
        if sections and seg.section not in sections:
            continue
        m = pattern.search(seg.text)
        if m:
            return seg, m
    return None, None


def _any(segments: list[Segment], pattern: re.Pattern[str], sections=None) -> bool:
    seg, _m = _find(segments, pattern, sections)
    return seg is not None


_ROLE_SECTIONS = (Section.RESPONSIBILITIES, Section.REQUIREMENTS, Section.BODY, Section.ABOUT)
_PROCESS_SECTIONS = (Section.PROCESS, Section.BODY, Section.RESPONSIBILITIES, Section.REQUIREMENTS)


@dataclass
class QueueDuty:
    """One support-queue duty, with the audience that decides whether it is the excluded work."""

    section: str
    matched_text: str
    context: str
    audience: str            # external | internal | unstated
    is_own_duty: bool


def collect_queue_duties(segments: list[Segment]) -> tuple[list[QueueDuty], list[QueueDuty]]:
    """Find support-queue duties, and separately the ones a guard deliberately excused.

    Duty-span scope throughout — not description scope. This is the same lesson the sales rule
    already learned: judging the whole description let one "build internal tools" sentence excuse a
    support-queue duty stated three paragraphs away. A guard only applies to the duty it is in.

    Returns (duties, excused) so the excused ones can be recorded as guarded misfires rather than
    vanishing.
    """
    duties: list[QueueDuty] = []
    excused: list[QueueDuty] = []
    for seg in segments:
        if seg.section not in _ROLE_SECTIONS + (Section.TITLE,):
            continue
        for match in _CS_CHANNEL_RE.finditer(seg.text):
            span, _offset = duty_span_around(seg.text, match)
            if not _CS_HANDLING_RE.search(span):
                continue
            if polarity(seg.text, match) != "required":
                continue
            # Asymmetric scopes, and the asymmetry is the point. WHOSE contacts these are is a
            # property of the sentence: "answer phone calls and emails from our customers" splits on
            # `and`, so duty-span scope loses the audience and the finding was discarded. A GUARD
            # stays duty-span scoped, because one "build internal tools" sentence must not excuse a
            # support-queue duty stated beside it.
            clause, _clause_offset = clause_around(seg.text, match)
            audience = (
                "internal" if (_CS_INTERNAL_AUDIENCE_RE.search(span)
                               or _CS_INTERNAL_AUDIENCE_RE.search(clause))
                else "external" if (
                    _CS_EXTERNAL_AUDIENCE_RE.search(span)
                    or _CS_EXTERNAL_AUDIENCE_RE.search(clause)
                    or _CS_SELF_EVIDENT_CHANNEL_RE.search(match.group(0))
                )
                else "unstated"
            )
            if audience == "unstated" and not _CS_QUEUE_SHAPED_CHANNEL_RE.search(match.group(0)):
                # A channel noun with no audience and no queue shape is not evidence of anything.
                continue
            duty = QueueDuty(
                section=seg.section, matched_text=match.group(0),
                context=_context(seg.text, match), audience=audience,
                is_own_duty=describes_own_duty(seg.text, match),
            )
            # The channel is the thing being BUILT, or what an artifact is ABOUT — not a queue worked.
            if (_CS_TOOLING_GUARD_RE.search(span) or _SOFTWARE_OWNERSHIP_RE.search(span)
                    or _TOOLING_FRAME_RE.search(span) or _CS_ARTIFACT_OBJECT_RE.search(span)):
                excused.append(duty)
                continue
            duties.append(duty)
    return duties, excused


def screen_job(job: CanonicalJob) -> ScreenResult:
    """Apply every policy exclusion to one posting, section-aware, with misfire guards."""
    result = ScreenResult(job_id=job.job_id)
    title = html.unescape(job.title or "")
    title_norm = normalize_title_for_matching(title)
    # Decode entities for the ANALYSIS surface as well as at ingest. The connector already
    # normalizes, but screening is the component whose correctness depends on polarity words, and
    # `doesn&#39;t require` must never be read as `require`. Decoding here costs nothing and makes
    # the rule set correct for any text it is handed, including a record written by an older build.
    body = html.unescape(job.description_text or "")
    segments = segment_description(body)
    all_segments = [Segment(section=Section.TITLE, text=title)] + segments

    # ---- 1. sales ownership ----------------------------------------------------------------------
    # A sales-shaped TITLE is strong evidence about the role. Only an explicit
    # engineering-for-the-revenue-org framing offsets it, and never when a real duty is stated.
    sales_findings = collect_findings(all_segments, _SALES_OWNERSHIP_RE, _ROLE_SECTIONS)
    sales_required = mandatory(sales_findings, artifact_excuses=True)
    title_seg, title_m = _find(all_segments, _SALES_TITLE_RE, (Section.TITLE,))

    if title_seg is not None:
        tooling_title_guard = (
            _any(all_segments, _SALES_TOOLING_GUARD_RE) and not sales_required
        )
        if tooling_title_guard:
            result.suppressed.append(RuleHit(
                "sales-ownership", ScreenOutcome.ELIGIBLE.value, title_m.group(0), Section.TITLE,
                "sales-shaped title, but the role reads as engineering for the revenue org, which "
                "the preferences file allows when there is no quota or closing responsibility",
                suppressed_by="gtm/revops engineering guard",
            ))
        else:
            result.exclusions.append(RuleHit(
                "sales-ownership", ScreenOutcome.EXCLUDED.value, title_m.group(0), Section.TITLE,
                f"title is a sales role ({title_m.group(0)})",
            ))
    elif sales_required:
        hit = sales_required[0]
        result.exclusions.append(RuleHit(
            "sales-ownership", ScreenOutcome.EXCLUDED.value, hit.context, hit.section,
            f"role owns sales outcomes ({hit.matched_text})"
            + (f"; {len(sales_required)} such duties stated" if len(sales_required) > 1 else ""),
        ))
    elif sales_findings:
        excused = [f for f in sales_findings if f.polarity == "required" and f.is_artifact]
        negated = negated_only(sales_findings)
        if excused:
            result.suppressed.append(RuleHit(
                "sales-ownership", ScreenOutcome.ELIGIBLE.value, excused[0].context,
                excused[0].section,
                "the sales vocabulary describes software being built or maintained, not a duty the "
                "candidate would carry, and no separate sales duty is stated",
                suppressed_by="software-artifact guard",
            ))
        elif negated:
            result.suppressed.append(RuleHit(
                "sales-ownership", ScreenOutcome.ELIGIBLE.value, negated[0].context,
                negated[0].section,
                "the clause explicitly states this duty is NOT part of the role",
                suppressed_by="negated-requirement guard",
            ))

    # Commission inside a BENEFITS/EEO block is compensation structure, not a quota. This is the
    # first misfire the plan names, so it is recorded as deliberately guarded rather than merely
    # failing to match — the suppressed list is the audit trail for why a rule did not fire.
    if not any(h.rule_id == "sales-ownership" for h in result.exclusions):
        seg, m = _find(all_segments, _COMMISSION_RE, (Section.BENEFITS, Section.EEO))
        if seg is not None:
            result.suppressed.append(RuleHit(
                "sales-ownership", ScreenOutcome.ELIGIBLE.value, _context(seg.text, m), seg.section,
                "commission language appears in a benefits/compensation block, which is not "
                "evidence that this engineering role carries a quota",
                suppressed_by="benefits-boilerplate guard",
            ))

    # Sales-ADJACENT language with no ownership duty and no software frame is undecidable from text.
    if not any(h.rule_id == "sales-ownership" for h in result.exclusions + result.suppressed):
        seg, m = _find(all_segments, _SALES_ADJACENT_RE, _ROLE_SECTIONS)
        if seg is not None and describes_own_duty(seg.text, m) and not (
            describes_a_software_artifact(seg.text, m)
            or _any(all_segments, _SALES_TOOLING_GUARD_RE)
        ):
            result.pending_checks.append(RuleHit(
                "sales-ownership", ScreenOutcome.PENDING_CHECK.value, _context(seg.text, m),
                seg.section,
                "the role touches sales activity but the text does not say whether the candidate "
                "would own any sales outcome; read the posting before preparing rather than "
                "excluding or accepting it on this evidence",
            ))

    # ---- 2. clearance / government / screening process -------------------------------------------
    clearance_sections = _ROLE_SECTIONS + (Section.PROCESS, Section.BENEFITS)
    clearance_findings = collect_findings(all_segments, _CLEARANCE_RE, clearance_sections)
    clearance_required = mandatory(clearance_findings)
    if clearance_required:
        hit = clearance_required[0]
        result.exclusions.append(RuleHit(
            "clearance-government", ScreenOutcome.EXCLUDED.value, hit.context, hit.section,
            f"requires a clearance, federal-suitability or drug-screening process "
            f"({hit.matched_text})",
        ))
    elif optional_only(clearance_findings):
        hit = optional_only(clearance_findings)[0]
        result.suppressed.append(RuleHit(
            "clearance-government", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
            "a clearance is described as optional or a nice-to-have, not a requirement",
            suppressed_by="optional-not-required guard",
        ))
    elif negated_only(clearance_findings):
        hit = negated_only(clearance_findings)[0]
        result.suppressed.append(RuleHit(
            "clearance-government", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
            "the posting explicitly states that no clearance or federal-suitability process is "
            "required, and no separate mandatory screening step is stated",
            suppressed_by="negated-requirement guard",
        ))

    if not any(h.rule_id == "clearance-government"
               for h in result.exclusions + result.suppressed):
        gov_seg, gov_m = _find(all_segments, _GOV_ADJACENT_RE, _ROLE_SECTIONS)
        if gov_seg is not None:
            result.pending_checks.append(RuleHit(
                "clearance-government", ScreenOutcome.PENDING_CHECK.value,
                _context(gov_seg.text, gov_m), gov_seg.section,
                "government-adjacent without a stated clearance requirement; the policy requires "
                "explicit operator reconsideration before preparation rather than an automatic "
                "exclusion or an automatic pass",
            ))

    # ---- 3. frontend specialization --------------------------------------------------------------
    fullstack_guard = bool(_FULLSTACK_GUARD_RE.search(title_norm)) or _any(
        all_segments, _FULLSTACK_GUARD_RE, _ROLE_SECTIONS
    )
    seg, m = _find(all_segments, _FRONTEND_TITLE_RE, (Section.TITLE,))
    if seg is not None and not _FULLSTACK_GUARD_RE.search(title_norm):
        result.exclusions.append(RuleHit(
            "frontend-specialist", ScreenOutcome.EXCLUDED.value, m.group(0), Section.TITLE,
            f"role's primary identity is frontend engineering ({m.group(0)})",
        ))
    else:
        depth_findings = collect_findings(all_segments, _FRONTEND_DEPTH_RE, _ROLE_SECTIONS)
        depth_required = mandatory(depth_findings)
        if depth_required and fullstack_guard:
            result.suppressed.append(RuleHit(
                "frontend-specialist", ScreenOutcome.ELIGIBLE.value, depth_required[0].context,
                depth_required[0].section,
                "frontend depth language present, but the role also owns backend/full-stack scope, "
                "where React is a supporting capability rather than the specialization",
                suppressed_by="full-stack/backend scope guard",
            ))
        elif depth_required:
            result.exclusions.append(RuleHit(
                "frontend-specialist", ScreenOutcome.EXCLUDED.value, depth_required[0].context,
                depth_required[0].section,
                f"requires deep frontend specialization ({depth_required[0].matched_text})",
            ))
        elif negated_only(depth_findings):
            hit = negated_only(depth_findings)[0]
            result.suppressed.append(RuleHit(
                "frontend-specialist", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
                "the clause states this frontend depth is NOT part of the role",
                suppressed_by="negated-requirement guard",
            ))

    # ---- 4. recorded candidate video -------------------------------------------------------------
    # A video requirement is a PROCESS step. Building software does not excuse it, so
    # `artifact_excuses` stays False here.
    video_findings = collect_findings(all_segments, _RECORDED_VIDEO_RE, _PROCESS_SECTIONS)
    video_required = mandatory(video_findings)
    video_optional = optional_only(video_findings)
    if video_required:
        hit = video_required[0]
        # HELD, not excluded (Human-first Screening Rule, 2026-10-12): "Record a pre-interview
        # evaluation request as held ... retain the opportunity for a human-interview route rather
        # than invent a rejection." It reaches the needs-a-check section marked as a hold that only
        # Brett can lift; it is never presented as ready to act on.
        result.pending_checks.append(RuleHit(
            "recorded-video", ScreenOutcome.PENDING_CHECK.value, hit.context, hit.section,
            f"{HUMAN_FIRST_HOLD} the application asks for a recorded candidate video "
            f"({hit.matched_text}) before any human interview"
            + ("; an earlier mention called it optional, but a later step makes it mandatory"
               if video_optional else "")
            + "; retained for a human-interview route, and only Brett can grant an exception",
        ))
    elif video_optional:
        # Optional is neither a requirement nor a clean pass. With a stated alternative it is
        # genuinely avoidable; without one the operator should look at the form.
        has_alternative = any(
            _VIDEO_ALTERNATIVE_RE.search(f.context) for f in video_optional
        ) or _any(all_segments, _VIDEO_ALTERNATIVE_RE, _PROCESS_SECTIONS)
        hit = video_optional[0]
        if has_alternative:
            result.suppressed.append(RuleHit(
                "recorded-video", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
                "a recorded video is offered as an option with a stated non-video alternative, so "
                "it is not a required recorded-video application",
                suppressed_by="optional-with-alternative guard",
            ))
        else:
            result.pending_checks.append(RuleHit(
                "recorded-video", ScreenOutcome.PENDING_CHECK.value, hit.context, hit.section,
                "a recorded video is described as optional but no alternative is stated; confirm on "
                "the live form that it can be skipped",
            ))
    elif negated_only(video_findings):
        hit = negated_only(video_findings)[0]
        result.suppressed.append(RuleHit(
            "recorded-video", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
            "the posting explicitly states that no recorded candidate video is required, and no "
            "separate mandatory video step is stated",
            suppressed_by="negated-requirement guard",
        ))
    else:
        seg, m = _find(all_segments, _LIVE_VIDEO_GUARD_RE, _PROCESS_SECTIONS)
        if seg is not None:
            result.suppressed.append(RuleHit(
                "recorded-video", ScreenOutcome.ELIGIBLE.value, _context(seg.text, m), seg.section,
                "process mentions a video call with human interviewers, which the policy explicitly "
                "permits; only one-way recorded submissions are excluded",
                suppressed_by="live-human-call guard",
            ))

    # ---- 5. AI-conducted interview ---------------------------------------------------------------
    ai_findings = collect_findings(all_segments, _AI_INTERVIEW_RE, _PROCESS_SECTIONS)
    ai_required = mandatory(ai_findings)
    ai_optional = optional_only(ai_findings)
    if ai_required:
        hit = ai_required[0]
        result.pending_checks.append(RuleHit(
            "ai-interview", ScreenOutcome.PENDING_CHECK.value, hit.context, hit.section,
            f"{HUMAN_FIRST_HOLD} interviews are conducted by an AI ({hit.matched_text})"
            + ("; an earlier mention called it optional, but a later step makes it mandatory"
               if ai_optional else "")
            + "; retained for a human-interview route, and only Brett can grant an exception",
        ))
    elif ai_optional:
        hit = ai_optional[0]
        result.suppressed.append(RuleHit(
            "ai-interview", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
            "an AI-conducted step is offered as an option rather than required; the policy excludes "
            "AI interviews, not employers that offer one alongside a human alternative",
            suppressed_by="optional-not-required guard",
        ))
    elif negated_only(ai_findings):
        hit = negated_only(ai_findings)[0]
        result.suppressed.append(RuleHit(
            "ai-interview", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
            "the posting explicitly states that interviews are not AI-conducted",
            suppressed_by="negated-requirement guard",
        ))
    else:
        seg, m = _find(all_segments, _AI_PRODUCT_GUARD_RE, _ROLE_SECTIONS)
        if seg is not None:
            result.suppressed.append(RuleHit(
                "ai-interview", ScreenOutcome.ELIGIBLE.value, _context(seg.text, m), seg.section,
                "the employer builds or uses AI in its product; that says nothing about who "
                "conducts the interview",
                suppressed_by="ai-in-product guard",
            ))

    # ---- 5b. other candidate evaluations before a human interview --------------------------------
    # The human-first rule covers "screening test, assessment, take-home or other candidate
    # evaluation" too, but only BEFORE a completed human preliminary interview. A posting that names
    # a take-home after two live calls is ordinary; one that puts a coding test in front of any human
    # contact is held. Most postings do not say which, and that is missing evidence rather than a
    # disqualifying fact: it is noted, not held.
    eval_findings = mandatory(collect_findings(all_segments, _EVALUATION_RE, _PROCESS_SECTIONS))
    if eval_findings:
        before_human = [f for f in eval_findings if _BEFORE_HUMAN_RE.search(f.context)]
        if before_human:
            hit = before_human[0]
            result.pending_checks.append(RuleHit(
                "pre-interview-evaluation", ScreenOutcome.PENDING_CHECK.value, hit.context,
                hit.section,
                f"{HUMAN_FIRST_HOLD} the posting puts a candidate evaluation "
                f"({hit.matched_text}) ahead of any human interview; retained for a "
                "human-interview route, and only Brett can grant an exception",
            ))
        else:
            hit = eval_findings[0]
            result.suppressed.append(RuleHit(
                "pre-interview-evaluation", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
                f"a candidate evaluation is mentioned ({hit.matched_text}) but the posting does not "
                "place it before a human interview; the human-first rule applies if an invitation "
                "arrives before one",
                suppressed_by="stage-not-stated guard",
            ))

    # ---- 5c. voice / telephony-centered work (operator exclusion, 2026-10-17) --------------------
    # "Screen actual duties ... do not pursue work centered on these areas." Centered is the word:
    # a title naming voice/speech/telephony, or two or more distinct stated duties in it, excludes.
    # One duty is part of a broader role and is a check; a preferred qualification is neither — the
    # Soil Connect platform lead lists "voice agents, phone systems" as nice-to-have, and the role is
    # the platform. Not a company-wide blacklist: only the role's own title and duties are read.
    voice_title = _VOICE_TITLE_RE.search(title_norm)
    voice_findings = collect_findings(
        [seg for seg in all_segments if not seg.preferred], _VOICE_DUTY_RE, _ROLE_SECTIONS)
    voice_preferred = collect_findings(
        [seg for seg in all_segments if seg.preferred], _VOICE_DUTY_RE, _ROLE_SECTIONS)
    voice_required = [f for f in mandatory(voice_findings)
                      if not _PREFERRED_CONTEXT_RE.search(f.context)]
    # Only duties count toward "centered"; a requirement line is evidence for a check, not a center.
    voice_duties = [f for f in voice_required if f.section != Section.REQUIREMENTS]
    voice_distinct = sorted({f.matched_text.lower() for f in voice_duties})
    voice_findings = voice_findings + voice_preferred
    if voice_title:
        result.exclusions.append(RuleHit(
            "voice-telephony", ScreenOutcome.EXCLUDED.value, voice_title.group(0), Section.TITLE,
            f"the role's title centers it on voice, speech or telephony ({voice_title.group(0)}), "
            "which the operator excludes",
        ))
    elif len(voice_distinct) >= 2:
        hit = voice_duties[0]
        result.exclusions.append(RuleHit(
            "voice-telephony", ScreenOutcome.EXCLUDED.value, hit.context, hit.section,
            "the stated duties center on voice, speech or telephony work "
            f"({', '.join(voice_distinct[:4])}), which the operator excludes",
        ))
    elif voice_required:
        hit = voice_required[0]
        result.pending_checks.append(RuleHit(
            "voice-telephony", ScreenOutcome.PENDING_CHECK.value, hit.context, hit.section,
            f"one stated duty touches voice or telephony ({hit.matched_text}); confirm the role is "
            "not centered on it before preparing",
        ))
    elif voice_findings:
        hit = voice_findings[0]
        result.suppressed.append(RuleHit(
            "voice-telephony", ScreenOutcome.ELIGIBLE.value, hit.context, hit.section,
            "voice or telephony appears only as an optional or preferred qualification, not as the "
            "work the role is centered on",
            suppressed_by="not-centered guard",
        ))

    # ---- 6. external customer service / call-center work -----------------------------------------
    # "Do not target call centers, external customer service or customer phone-support queues" —
    # while preserving software building and problem ownership for internal users. Three answers are
    # possible and all three are used: an exclusion with its duty evidence, a guarded misfire when
    # the role builds software for a support org, and PENDING_CHECK when a support-shaped title's
    # duties are simply not stated. The third is the policy's own instruction: such a title is not
    # automatically excluded, and it is not automatically suitable either.
    cs_external_title = bool(_CS_EXTERNAL_TITLE_RE.search(title_norm))
    cs_ambiguous_title = bool(_CS_AMBIGUOUS_TITLE_RE.search(title_norm))
    if cs_external_title and _CS_ENGINEERING_TITLE_RE.search(title_norm):
        # "Customer Support Engineer" is a duty question, not a title question.
        cs_external_title, cs_ambiguous_title = False, True

    queue_duties, queue_excused = collect_queue_duties(all_segments)
    # Report the STRONGEST duty, not the first one found: a span that names the audience outright is
    # better evidence than one relying on the channel noun. Review noted the MSP case citing "support
    # our helpdesk environment" when "respond to queries ... via phone" sat in the same posting.
    queue_duties.sort(key=lambda d: (
        not _CS_EXTERNAL_AUDIENCE_RE.search(d.context), d.section == Section.TITLE,
    ))
    external_duties = [d for d in queue_duties if d.audience == "external"]
    internal_duties = [d for d in queue_duties if d.audience == "internal"]
    unstated_duties = [d for d in queue_duties if d.audience == "unstated"]
    cs_tooling = _any(all_segments, _CS_TOOLING_GUARD_RE, _ROLE_SECTIONS)
    cs_software = _any(all_segments, _SOFTWARE_OWNERSHIP_RE, _ROLE_SECTIONS) or bool(
        _SOFTWARE_ROLE_RE.search(title_norm)
    )
    # Any contact-channel vocabulary at all, with or without a handling duty. Not evidence of a queue
    # by itself — it is the reason a support-shaped title with software duties goes to review rather
    # than being cleared outright.
    cs_contact_vocabulary = _any(all_segments, _CS_CHANNEL_RE, _ROLE_SECTIONS)

    # A call centre is a call centre. The policy names it unconditionally, so no keyword in the body
    # downgrades it.
    cs_call_center_title = _CS_CALL_CENTER_TITLE_RE.search(title_norm)

    if cs_external_title and not cs_call_center_title and not external_duties and (
        cs_tooling or cs_software
    ) and not (internal_duties or unstated_duties):
        # A customer-support title whose stated duties are building software. This used to return
        # ELIGIBLE on one software keyword anywhere in the description, which passed postings titled
        # "Customer Service Representative" whose only duty was speaking to customers by phone. A
        # title the policy rejects outright is never cleared by keyword evidence — the honest answer
        # for the genuinely rare case is a look at the posting.
        result.pending_checks.append(RuleHit(
            "customer-service-queue", ScreenOutcome.PENDING_CHECK.value, title, Section.TITLE,
            "the title names a customer-service role, which the policy rejects, but the stated "
            "duties read as building or owning software; read the posting before deciding rather "
            "than clearing it on the duties or rejecting it on the title",
        ))
    elif cs_external_title:
        evidence = external_duties[0].context if external_duties else title
        duty_note = (
            f"; stated duty: {external_duties[0].matched_text}" if external_duties
            else "; no duty text contradicts the title"
        )
        result.exclusions.append(RuleHit(
            "customer-service-queue", ScreenOutcome.EXCLUDED.value, evidence,
            external_duties[0].section if external_duties else Section.TITLE,
            "the role's own subject is external customer service or phone support "
            f"({_CS_EXTERNAL_TITLE_RE.search(title_norm).group(0)}){duty_note}",
        ))
    elif external_duties:
        hit = external_duties[0]
        result.exclusions.append(RuleHit(
            "customer-service-queue", ScreenOutcome.EXCLUDED.value, hit.context, hit.section,
            f"the role's stated duties include working an external customer-contact queue "
            f"({hit.matched_text})"
            + (f"; {len(external_duties)} such duties stated" if len(external_duties) > 1 else ""),
        ))
    elif internal_duties or unstated_duties:
        # Internal support is NOT the excluded work, and an unnamed audience is not evidence of an
        # external one. Visible for review rather than decided in either direction.
        hit = (internal_duties or unstated_duties)[0]
        result.pending_checks.append(RuleHit(
            "customer-service-queue", ScreenOutcome.PENDING_CHECK.value, hit.context, hit.section,
            "the role handles a support queue, but for "
            + ("internal users, which the policy explicitly welcomes"
               if internal_duties else "an audience the posting does not name")
            + "; confirm whether this is external customer service or internal problem ownership "
              "before preparing",
        ))
    elif cs_ambiguous_title and cs_software and not cs_contact_vocabulary:
        result.suppressed.append(RuleHit(
            "customer-service-queue", ScreenOutcome.ELIGIBLE.value, title, Section.TITLE,
            "support-shaped title, but the stated duties are software building and problem "
            "ownership, which is the work the policy is asking for rather than the work it excludes",
            suppressed_by="software-ownership guard",
        ))
    elif cs_ambiguous_title and cs_software:
        # Software duties AND contact-channel vocabulary. Clearing this on the software half is how a
        # "Help Desk Analyst" who gives first-line telephone assistance to clients read as ELIGIBLE.
        result.pending_checks.append(RuleHit(
            "customer-service-queue", ScreenOutcome.PENDING_CHECK.value, title, Section.TITLE,
            "a support-shaped title whose duties mention both building software and customer "
            "contact channels; the policy refuses both defaults, so read the posting to see which "
            "one the job actually is",
        ))
    elif cs_ambiguous_title:
        result.pending_checks.append(RuleHit(
            "customer-service-queue", ScreenOutcome.PENDING_CHECK.value, title, Section.TITLE,
            "a support-shaped title whose duties do not say whether the work is an external contact "
            "queue or internal software ownership; the policy refuses both defaults — read the "
            "posting rather than treating the title as suitable or as a rejection",
        ))
    elif queue_excused:
        result.suppressed.append(RuleHit(
            "customer-service-queue", ScreenOutcome.ELIGIBLE.value, queue_excused[0].context,
            queue_excused[0].section,
            "support-queue vocabulary describes software being built for a support organization, "
            "not a queue the candidate would work",
            suppressed_by="software-for-a-support-org guard",
        ))

    # ---- 7. location eligibility from New Hampshire ----------------------------------------------
    # See src/candidate/location.py for why this asks three separate questions instead of matching a
    # town list: (a) does the posting restrict residency in a way that excludes New Hampshire,
    # (b) is attendance at a worksite actually MANDATORY, and only then (c) where is that worksite.
    # A remote label answers none of them by itself.
    location_blob = " ".join(filter(None, [
        job.raw_location or "", job.canonical_location or "", " ".join(job.secondary_locations),
    ]))
    places = parse_places(job.raw_location, job.canonical_location, *job.secondary_locations)
    worksite = best_worksite(places)
    worksite_label = ", ".join(
        p.label for p in places if p.worksite == worksite
    ) or location_blob[:80] or "<no location stated>"

    remote_ok = bool(_US_REMOTE_RE.search(location_blob)) or (
        bool(_REMOTE_RE.search(location_blob)) and not _NON_US_ONLY_RE.search(location_blob)
    )
    if not remote_ok and job.remote_hybrid_language.value == "REMOTE":
        remote_ok = not _NON_US_ONLY_RE.search(location_blob)

    # Mandatory attendance, polarity-aware: "there is no in-office requirement" must not read as one.
    attendance_findings = collect_findings(
        all_segments, ATTENDANCE_REQUIRED_RE,
        _ROLE_SECTIONS + (Section.TITLE, Section.BENEFITS),
    )
    attendance_required = mandatory(attendance_findings)
    # A stated attendance requirement outranks the word "remote" in a location field. This is the
    # "Remote / Boston, MA" posting whose body requires three days a week in the Boston office.
    if attendance_required:
        remote_ok = False

    # A posting can state "Remote" in its location field and name the office it requires attendance
    # at only in the body ("four days per week in the office in Cambridge, MA"). When the location
    # field yields no worksite, the attendance sentence is where the worksite actually is.
    if worksite == WorksiteClass.UNKNOWN and attendance_required:
        from_body = best_worksite(parse_places(*[f.context for f in attendance_required]))
        if from_body != WorksiteClass.UNKNOWN:
            worksite = from_body
            worksite_label = attendance_required[0].context[:120]

    residency = find_residency_restriction(job.description_text)

    if residency is not None:
        # Genuinely remote, but not to a New Hampshire resident.
        result.exclusions.append(RuleHit(
            "location-residency", ScreenOutcome.EXCLUDED.value, residency.context, "location",
            "the posting limits employment to residents of "
            f"{', '.join(residency.states)}, which does not include New Hampshire; a remote label "
            "does not make this role available from New Hampshire",
        ))
    elif worksite == WorksiteClass.NON_US and not remote_ok:
        result.exclusions.append(RuleHit(
            "location-eligibility", ScreenOutcome.EXCLUDED.value, worksite_label, "location",
            "the stated worksite is outside the US and no US-remote eligibility is stated",
        ))
    elif bool(_NON_US_ONLY_RE.search(location_blob)) and not remote_ok and worksite in (
        WorksiteClass.UNKNOWN, WorksiteClass.NON_US,
    ):
        result.exclusions.append(RuleHit(
            "location-eligibility", ScreenOutcome.EXCLUDED.value, location_blob[:160], "location",
            "location is outside the US with no US-remote eligibility stated",
        ))
    elif remote_ok:
        # Genuinely remote and not residency-restricted. The employer's own city is irrelevant:
        # "An employer headquartered in either city remains eligible when the role is genuinely
        # remote from New Hampshire."
        if worksite in (WorksiteClass.OPERATOR_EXCLUDED, WorksiteClass.OUT_OF_STATE):
            result.suppressed.append(RuleHit(
                "location-eligibility", ScreenOutcome.ELIGIBLE.value, worksite_label, "location",
                "the employer is in a city excluded for COMMUTING, but the role itself is remote, "
                "which the policy explicitly allows",
                suppressed_by="genuinely-remote guard",
            ))
    elif not location_blob.strip():
        result.pending_checks.append(RuleHit(
            "location-eligibility", ScreenOutcome.PENDING_CHECK.value, "<no location stated>",
            "location",
            "no location stated; work-from-New-Hampshire eligibility is unknown and must be "
            "confirmed rather than assumed in either direction",
        ))
    elif worksite == WorksiteClass.OPERATOR_EXCLUDED:
        result.exclusions.append(RuleHit(
            "location-eligibility", ScreenOutcome.EXCLUDED.value, worksite_label, "location",
            "onsite or hybrid attendance in a location the operator excluded for commuting "
            "(Portsmouth, or the Boston area); the same employer stays eligible if the role is "
            "genuinely remote",
        ))
    elif worksite == WorksiteClass.OUT_OF_STATE:
        # The one hard distance rule, and it is a fact rather than an estimate: Laconia is in
        # central New Hampshire, so no out-of-state worksite is a ~30-minute drive from it.
        result.exclusions.append(RuleHit(
            "location-eligibility", ScreenOutcome.EXCLUDED.value, worksite_label, "location",
            "the stated worksite is outside New Hampshire and attendance is required or no remote "
            "option is stated; no out-of-state worksite is within approximately a 30-minute drive "
            "of Laconia",
        ))
    elif worksite == WorksiteClass.DISCUSS:
        result.pending_checks.append(RuleHit(
            "location-eligibility", ScreenOutcome.PENDING_CHECK.value, worksite_label, "location",
            "Plymouth, New Hampshire is a possible commute exception to discuss with Brett rather "
            "than a blanket approval; confirm the actual worksite and attendance expectation",
        ))
    elif worksite == WorksiteClass.LAKES_REGION:
        # Plausibly local. NOT certified: the policy states a drive time, and this system does not
        # measure one, so the lead stays visible with the check named instead of being decided.
        result.pending_checks.append(RuleHit(
            "location-eligibility", ScreenOutcome.PENDING_CHECK.value, worksite_label, "location",
            "plausibly local to Laconia, but the actual worksite address and attendance "
            "requirement decide whether it is within approximately a 30-minute drive; confirm "
            "before preparing",
        ))
    elif worksite == WorksiteClass.OTHER_NH:
        result.pending_checks.append(RuleHit(
            "location-eligibility", ScreenOutcome.PENDING_CHECK.value, worksite_label, "location",
            "the worksite is in New Hampshire but probably beyond approximately a 30-minute drive "
            "from Laconia; confirm the worksite, the attendance requirement, or a remote option",
        ))
    else:
        seg, m = _find(all_segments, _ONSITE_REQUIRED_RE, _ROLE_SECTIONS + (Section.TITLE,))
        if attendance_required or seg is not None:
            evidence = attendance_required[0].context if attendance_required else _context(
                seg.text, m)
            result.pending_checks.append(RuleHit(
                "location-eligibility", ScreenOutcome.PENDING_CHECK.value,
                f"{location_blob[:80]} | {evidence[:80]}", "location",
                "onsite or hybrid presence is required but the worksite could not be identified "
                "from the posting; confirm where the work happens before preparing",
            ))
        else:
            result.pending_checks.append(RuleHit(
                "location-eligibility", ScreenOutcome.PENDING_CHECK.value, location_blob[:160],
                "location",
                "no explicit remote statement and the worksite is unclear; eligibility from New "
                "Hampshire needs confirmation before preparation",
            ))

    # ---- 8. can we even see the process? ---------------------------------------------------------
    # This is the rule that stops the system claiming an absence it never observed.
    truncated = job.verification_state == VerificationState.UNVERIFIED_LEAD or any(
        u.startswith(("aggregator_description_truncated", "excerpt_only")) for u in job.uncertainty
    )
    if truncated:
        result.pending_checks.append(RuleHit(
            "process-not-inspectable", ScreenOutcome.PENDING_CHECK.value,
            f"verification_state={job.verification_state.value}", "meta",
            "description is a summary from an aggregator, so the absence of a recorded-video or "
            "AI-interview requirement has NOT been established; open the employer posting and the "
            "live form before preparing",
        ))
    elif not _any(all_segments, re.compile(
        r"\b(interview|hiring process|apply|application)\b", re.I), _PROCESS_SECTIONS
    ):
        result.pending_checks.append(RuleHit(
            "process-not-inspectable", ScreenOutcome.PENDING_CHECK.value, "<no process section>", "meta",
            "the posting does not describe its interview or application process; the live form "
            "still needs inspection for recorded-video and AI-interview requirements",
        ))

    # ---- verdict ---------------------------------------------------------------------------------
    if result.exclusions:
        result.outcome = ScreenOutcome.EXCLUDED.value
    elif result.pending_checks:
        result.outcome = ScreenOutcome.PENDING_CHECK.value
    else:
        result.outcome = ScreenOutcome.ELIGIBLE.value
    return result


def screen_all(jobs: list[CanonicalJob]) -> dict[str, ScreenResult]:
    return {job.job_id: screen_job(job) for job in jobs}
