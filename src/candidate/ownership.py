"""Ownership scope: how much of a business's software this role would actually own.

From `APPLICATION_WORKFLOW.md` § "Broad ownership and first/sole-engineer preference" (2026-09-28):
first or sole software-engineer roles at smaller businesses are *especially attractive, not merely
fallback work*, and the preference must be carried "through source discovery, candidate retention,
employer research and application emphasis".

Two things that section says, which shape every decision in this module:

  "Distinguish confirmed sole ownership, a small team with broad ownership, and unknown team
   structure. Do not infer headcount or sole-engineer status from company size, a title, or a lack
   of public engineering material."

  "Staff is a seniority label, not evidence of being the company's only engineer."

So team structure is **three-valued and evidence-only**. UNKNOWN is the default and the honest
answer for most postings; it is not a gap, not a finding, and not a reason to downgrade anything. No
pattern in this module reads a title for team size, and none reads employer headcount at all —
neither is available as evidence and neither would be evidence if it were.

Breadth of responsibility is tracked separately from team structure, because they are separate
facts: a five-engineer team can hand one person end-to-end ownership of a system, and a sole
engineer can be hired to maintain one vendor integration. Keeping them apart is what lets the report
say which one a posting actually established.

Everything here reuses `screening.py`'s segmentation, clause polarity and duty-span machinery. Two
vocabularies for reading the same job description is how they drift apart.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from enum import Enum

from src.candidate.screening import (
    _SOFTWARE_OWNERSHIP_RE,
    _SOFTWARE_ROLE_RE,
    Section,
    Segment,
    _context,
    clause_around,
    describes_own_duty,
    polarity,
    segment_description,
)
from src.common.models import CanonicalJob
from src.common.normalize import normalize_title_for_matching

OWNERSHIP_RULESET_VERSION = "1.3.0"


class TeamStructure(str, Enum):
    """What the posting ESTABLISHED about the engineering team. Never what it implied."""

    CONFIRMED_SOLE = "CONFIRMED_SOLE"   # the posting says this person is the first/only engineer
    SMALL_TEAM = "SMALL_TEAM"           # the posting states a small team, with no sole claim
    UNKNOWN = "UNKNOWN"                 # not stated — the common case, and not a defect


class OwnershipBreadth(str, Enum):
    BROAD = "BROAD"                     # end-to-end delivery, deciding what to build, owning it
    STATED_NARROW = "STATED_NARROW"     # the posting scopes the work to one component or specialty
    UNSTATED = "UNSTATED"


# --------------------------------------------------------------------------------------------------
# Evidence patterns
# --------------------------------------------------------------------------------------------------
# CONFIRMED sole ownership. Each alternative is a sentence a posting only writes when it means it.
# `founding engineer` is deliberately ABSENT: the workflow lists it among "useful search clues", and
# a founding engineer is commonly one of several. It earns a breadth clue below, not a team-structure
# verdict.
_SOLE_ENGINEER_RE = re.compile(
    r"\b(sole (?:software )?(?:engineer|developer)|only (?:software )?(?:engineer|developer)|"
    r"our first (?:software )?(?:engineer|developer|technical hire)|"
    r"(?:the|our) first (?:engineering|technical) hire|"
    r"first (?:software )?(?:engineer|developer) (?:at|in|on|for|here)|"
    r"one[- ]person (?:engineering|development|dev) team|"
    r"(?:no|without an?) (?:existing |in[- ]house |internal )?"
    r"(?:engineering|software|development|dev|it|technology|technical) "
    r"(?:team|department|function|staff|person)|"
    r"(?:we|they) (?:currently )?(?:have|has) no (?:engineers?|developers?|"
    r"(?:engineering|software|it) (?:team|department|staff))|"
    r"only technical (?:person|employee|member)|"
    r"you (?:will|'ll) be (?:the|our) (?:only|sole|first) (?:engineer|developer|technical)|"
    # Ordinary English, which is how a business that is not a software company writes it.
    #
    # An independent review measured the cliché-shaped alternatives above against 24 unmistakable
    # plain-language statements of sole ownership and found 19 of them LOST — including the pair
    # "the only person here writing code" (lost) versus "the only person who writes code here"
    # (kept), which differ only in word order. These alternatives are the repair, and the shape of
    # the repair is deliberate: the verb list is open-ended and the connector is optional, because
    # requiring a literal `who` is what produced that pair.
    # Both halves are required — a verb AND a software object — because verb STEMS collide with
    # ordinary nouns. `program\w*` matched "…may participate in this program", which turned a
    # content-review posting's household-eligibility boilerplate into a confirmed sole-engineer
    # verdict on a live feed. Found by re-running the corpus after widening these patterns.
    r"only (?:person|one|employee|member of staff)\b[^.;]{0,45}?"
    r"(?:who\s+)?(?:writes?|writing|builds?|building|codes?|coding|develops?|developing|"
    r"maintains?|maintaining|runs?|running|handles?|handling|does|do|doing|works? on|working on)"
    r"\b[^.;]{0,35}?"
    r"\b(?:code|software|program(?:s|ming)?|applications?|apps?|systems?|tools?|websites?|"
    r"databases?|reports?|integrations?|automations?|it)\b|"
    r"(?:nobody|no one|no-one) (?:else )?(?:here |internally |in[- ]house |at [A-Za-z ]{0,25})?"
    r"(?:currently |today |right now )?"
    r"(?:does|do|did|writes|write|builds|build|handles|handle|works on|work on|maintains|maintain)\b|"
    r"you (?:would|will|'ll|'d) (?:be )?(?:work(?:ing)?|doing|handling|running)\b[^.;]{0,30}?"
    r"\b(?:alone|single[- ]handed(?:ly)?|by yourself|on your own)\b|"
    r"\b(?:alone|single[- ]handed(?:ly)?|by yourself|on your own)\b[^.;]{0,25}?"
    r"(?:build|writ|maintain|run|own)\w*\b|"
    r"work(?:ing)? alone on (?:this|it)\b|"
    r"(?:a )?team of one\b|it would just be you\b|(?:just|only) you\b(?=[^.;]{0,30}(?:here|on this))|"
    # "our first in-house software hire" (2026-11-11 acceptance case) was lost to the modifier.
    r"first (?:in[- ]house |internal |dedicated |full[- ]time )?"
    r"(?:technology|technical|software|it|engineering) (?:hire|role|position)|"
    r"(?:the|our) first (?:person|employee) (?:we have )?(?:ever )?(?:hired|employed)\b|"
    r"first (?:person|one) (?:we have )?ever (?:hired|employed)\b|"
    r"employee (?:number|#) ?one\b|"
    r"(?:this|it) is (?:our|the) first (?:software|technical|engineering|technology) "
    r"(?:role|position|hire|job)|"
    r"first (?:software|technical|engineering) role (?:we have )?(?:ever )?(?:created|had)\b|"
    r"(?:there is|there's) (?:nobody|no one|no-one) else in (?:this|the) role\b|"
    # Same guard as above: "we have never had anyone leave" is not a statement about engineering.
    r"(?:we have|we've|they have) never had (?:anyone|anybody|someone)\b[^.;]{0,45}?"
    r"\b(?:writ\w*|build\w*|cod\w*|develop\w*|technical|software|engineer\w*|in[- ]house|it)\b|"
    r"(?:nothing|none of (?:this|it)) (?:here )?is (?:somebody|someone) else'?s job\b|"
    r"sole (?:technical|technology|it) (?:person|resource|hire))\b",
    re.I,
)

# A stated small engineering team. Distinct from sole ownership and never upgraded into it.
_SMALL_TEAM_RE = re.compile(
    r"\b(small (?:engineering|development|dev|software|technical|product) team|"
    r"(?:engineering|development|dev) team of (?:two|three|four|five|six|seven|eight|nine|ten|"
    r"[2-9]|10)\b|"
    r"team of (?:two|three|four|five|six|seven|eight|nine|ten|[2-9]|10) (?:engineers?|developers?)|"
    r"lean (?:engineering|dev(?:elopment)?) team|"
    r"(?:we(?:'re| are)|it(?:'s| is)) a small team|"
    # "join 2 of us on the engineering team" (BuildQ, live HN thread 2026-11-11).
    r"join (?:the )?(?:two|three|four|five|[2-5]) of us\b(?: on (?:the|our) (?:engineering|eng|"
    r"dev|tech(?:nical)?) team)?|"
    r"founding (?:engineering|eng|tech(?:nical)?) team)\b",
    re.I,
)

# Breadth of responsibility: the work described spans the whole thing.
_BROAD_SCOPE_RE = re.compile(
    r"\b(end[- ]to[- ]end (?:ownership|delivery|responsibility)|"
    # "own the integrations end to end" is the same statement with the words in the other order, and
    # requiring the noun immediately after `end to end` missed it. The verb list is deliberately
    # short — own / deliver / drive are ownership verbs, where `build ... end-to-end encryption`
    # would be a product adjective rather than a statement about scope.
    r"(?:own|owning|owns|deliver(?:ing|s)?|driv(?:e|ing|es))\s+"
    r"(?:[A-Za-z0-9\-+/&.']+\s+){0,6}end[- ]to[- ]end|"
    r"(?:build|building|implement|implementing|ship|shipping)\s+"
    r"(?:[A-Za-z0-9\-+/&.']+\s+){0,4}(?:across the stack|from the ground up)|"
    r"own(?:ing)? (?:the )?(?:entire|whole|"
    r"full) (?:stack|product|system|platform|lifecycle)|"
    r"across the (?:entire |whole |full )?stack|full ownership|complete ownership|"
    r"wear(?:ing)? (?:many|multiple|several) hats|"
    r"from (?:idea|concept|requirements|scratch|the ground up) (?:to|through) "
    r"(?:production|deployment|delivery|launch)|"
    r"decide what(?:'s| is)? (?:worth )?(?:to )?build|"
    # Plain-English breadth, from the same measured corpus as the sole patterns above.
    r"(?:decide|choose|figure out|work out|determine) what[^.;]{0,40}?"
    r"(?:needs?|should be|to)\b[^.;]{0,15}?\bbuil\w*|"
    r"(?:decide|choose|figure out|work out) what to build\b|"
    r"touch every part of\b|do a bit of everything\b|a bit of everything\b|"
    r"from nothing to something\b|"
    r"own(?:ing)? (?:the |our )?software\b[^.;]{0,20}?\bby yourself\b|"
    r"running the (?:software|technology|engineering) side\b|"
    r"build(?:s|ing)? (?:all of )?(?:this|it|our software) from the ground up|"
    r"whatever (?:the business|we) needs?|"
    r"greenfield|from scratch|0 to 1|zero to one|ground[- ]up build|"
    r"founding engineer|generalist (?:engineer|developer|software)|"
    r"build (?:and (?:own|run|operate|maintain)) (?:it|them|the system)|"
    r"own the (?:outcome|result|delivery|problem))\b",
    re.I,
)

# Sentences whose subject is SOMEBODY ELSE. An independent review reproduced four postings where a
# sole-ownership phrase was about a different company entirely, and each printed "confirmed first/sole
# engineer" on a row for an employer with teams of six:
#
#   "Many of our CLIENTS have no in-house engineering team, which is why they hire us."
#   "Our CTO was the first developer at a well-known payments company BEFORE FOUNDING US."
#   "You will work ALONGSIDE our first software engineer and learn our codebase from her."
#   "Our founder CAME FROM a company that had no engineering team at all."
#
# A verdict about this employer's team cannot be read off a sentence about someone else's.
_THIRD_PARTY_SUBJECT_RE = re.compile(
    r"\b(our |the |their )?(?:clients?|customers?|vendors?|suppliers?|partners?|"
    r"portfolio compan(?:y|ies)|the companies we|businesses we (?:serve|work with)|"
    r"previous employer|former employer|prior company|another company|"
    r"before (?:founding|joining|starting)|came from|used to (?:work|be)|"
    r"alongside (?:our|the)|work with (?:our|the) (?:existing|current) (?:first|only|sole))\b",
    re.I,
)

# Objects that make an "ownership" phrase about the CANDIDATE'S CAREER rather than the employer's
# software. Same review: "full ownership of your career", "complete ownership of your learning and
# development" and "you own your growth here" all read as broad software ownership.
_PERSONAL_DEVELOPMENT_OBJECT_RE = re.compile(
    r"\b(your |their |everyone'?s |his or her )?"
    r"(career|careers|growth|learning|development path|professional development|"
    r"personal development|progression|journey|destiny|schedule|calendar|time)\b",
    re.I,
)

# Past-tense company history. "Our platform was written from scratch a decade ago" and "our founders
# took this company from zero to one in 2019" describe what somebody already did, not what this hire
# would do.
_COMPANY_HISTORY_FRAME_RE = re.compile(
    r"\b(was|were|had been|has been) (?:originally |initially |first )?"
    r"(?:written|built|created|developed|rewritten|designed)\b|"
    r"\b(?:our |the )?founders? (?:took|built|created|grew|started)\b|"
    r"\b(?:a decade|years?|months?) ago\b|\bback in (?:19|20)\d\d\b|\bin (?:19|20)\d\d\b",
    re.I,
)

# A breadth phrase whose subject is the workforce in general rather than this hire. "Our people wear
# many hats and love it" is a culture sentence, and it was reading as broad ownership on a role whose
# only duty was implementing assigned front-end tickets.
_COLLECTIVE_SUBJECT_RE = re.compile(
    r"\b(our (?:people|team members|employees|staff|engineers|folks|culture)|"
    r"everyone (?:here|at)?|all of our|folks here|we all|the team here)\b",
    re.I,
)
_SECOND_PERSON_RE = re.compile(r"\b(you|your|you'?ll|you'?d)\b", re.I)

# Objects of ownership that are BUSINESS OUTCOMES rather than software. Measured against the live
# corpus of 2026-09-28: "own go-to-market strategy end to end", "owning a direct sales territory
# end-to-end", "own monetization end-to-end" and "owning segment revenue end-to-end" all read as
# broad ownership, which is a sales role wearing the preference's vocabulary. The phrase is real; the
# thing being owned is not this employer's software.
_BUSINESS_OUTCOME_OBJECT_RE = re.compile(
    r"\b(revenue|sales|quota|territory|pipeline|monetization|monetisation|go[- ]to[- ]market|gtm|"
    r"bookings|renewals|churn|marketing|demand generation|p&l|profit and loss)\b",
    re.I,
)

# Plain-language software building, used ONLY to widen what counts as a software role for RETENTION.
#
# Why this is local rather than an addition to `screening._SOFTWARE_OWNERSHIP_RE`, given that this
# module's own docstring warns against two vocabularies: the asymmetry is in what a false positive
# COSTS. In screening, that regex is a guard that EXCUSES a support-queue duty, so widening it
# weakens an exclusion and a false positive means a wrong clearance. Here it only decides whether a
# posting is eligible to be RETAINED for a human to read, where a false positive costs a look. The
# screening vocabulary is still consulted first and is unchanged; this only adds to it.
#
# "We need someone to write the programs that keep our production scheduling working" is a
# manufacturer describing software engineering, and every word of it sat outside the noun list.
_PLAIN_SOFTWARE_WORK_RE = re.compile(
    r"\b(?:write|writes|writing|build|builds|building|maintain|maintains|maintaining|"
    r"develop|develops|developing|code|codes|coding|program|programs|programming)\s+"
    r"(?:[A-Za-z0-9\-+/&.']+\s+){0,4}"
    r"(?:programs?|software|code|scripts?|applications?|apps?|tools?|systems?|reports?|"
    r"reporting|spreadsheets?|databases?|integrations?|automations?)\b",
    re.I,
)

# Titles that are not the shape the preference describes. The section is about being the first or
# sole SOFTWARE ENGINEER who builds — "implementing across the stack, and owning the result". A
# department-head title is a different job, and scoring already discounts it. Excluding it from the
# RETENTION path takes nothing away: such a role still arrives on its own fit score exactly as it
# did before, and this is not a new exclusion rule.
_MANAGEMENT_TITLE_RE = re.compile(
    r"\b(head of|vice president|vp|chief|director|engineering manager|"
    r"(?:product|program|project|account|general) manager)\b",
    re.I,
)

# The counter-evidence: a posting that scopes the work narrowly on purpose. Recorded so BROAD is a
# reading of the whole description rather than of whichever phrase appeared first.
_NARROW_SCOPE_RE = re.compile(
    r"\b(you will focus (?:exclusively |solely |only )?on|narrow(?:ly)? scoped|"
    # An adjective between the quantifier and the noun is ordinary prose, and requiring them
    # adjacent missed "build ONE NEW MICROSERVICE to the architecture team's specification" — a
    # posting that also said "greenfield" and was therefore read as broad ownership.
    r"(?:one|a single)\s+(?:[A-Za-z]+\s+){0,2}"
    r"(?:component|service|module|micro[- ]?service|feature|area|codebase)|"
    r"within (?:an established|a large|our existing) (?:engineering )?(?:team|organization)|"
    r"specializ(?:e|ing) (?:exclusively |solely |only )?in|"
    r"dedicated (?:exclusively |solely )?to (?:one|a single))\b",
    re.I,
)

# The business-facing half of the preference: understanding the business and building what it needs.
# A signal, not a verdict — it is what makes an ordinary employer's internal-software role the kind
# of opening the section is asking for.
_BUSINESS_FACING_RE = re.compile(
    r"\b(understand(?:ing)? (?:the|our) business|work(?:ing)? (?:directly )?with (?:the )?"
    r"(?:owner|founder|ceo|coo|president|leadership|operations team|business stakeholders?)|"
    r"gather(?:ing)? requirements|translat(?:e|ing) business (?:needs|requirements|problems)|"
    r"(?:internal|business) (?:stakeholders?|users?|teams?)|"
    r"report(?:s|ing)? (?:directly )?to the (?:owner|founder|ceo|coo|president|"
    r"(?:vp|director) of operations))\b",
    re.I,
)

# The workplace shape the section calls a positive: a nontechnical manager. Recorded as a signal so a
# reader can see it; it changes no verdict, because a manager's background is not ownership scope.
_NONTECHNICAL_MANAGER_RE = re.compile(
    r"\b(non[- ]?technical (?:manager|founder|owner|leadership|stakeholders?)|"
    r"report(?:s|ing)? to (?:a |the )?non[- ]?technical)\b",
    re.I,
)

# Ordinary-business signal: the employer's own product is not software. Never a gate — an equally
# good role at a large technology employer stays exactly as eligible.
_ORDINARY_BUSINESS_RE = re.compile(
    r"\b(family[- ]owned|(?:our|the) (?:warehouse|showroom|dealership|clinic|practice|plant|"
    r"factory|restaurant|store|fleet|yard|mill|shop)|"
    r"(?:manufactur|distribut|logistics|freight|construction|hospitality|insurance|healthcare|"
    r"retail|wholesale|agricultur|landscap|plumb|hvac|dental|veterinar)\w*|"
    r"not a (?:software|tech(?:nology)?) company)\b",
    re.I,
)


@dataclass
class OwnershipSignal:
    kind: str            # sole | small-team | broad | narrow | business-facing | nontechnical-manager
    matched_text: str
    section: str
    context: str
    is_own_duty: bool = False
    # The phrase's own clause. Kept because every discriminator below asks a question about the
    # SENTENCE, not about the matched phrase — whose team is this, whose career, which company.
    clause: str = ""

    def to_json(self) -> dict:
        return {
            "kind": self.kind,
            "matched_text": self.matched_text[:120],
            "section": self.section,
            "context": self.context[:200],
            "is_own_duty": self.is_own_duty,
        }


@dataclass
class OwnershipAssessment:
    """What a posting established about ownership scope, and on what evidence."""

    job_id: str
    team_structure: TeamStructure = TeamStructure.UNKNOWN
    breadth: OwnershipBreadth = OwnershipBreadth.UNSTATED
    signals: list[OwnershipSignal] = field(default_factory=list)
    ordinary_business_signal: bool = False
    nontechnical_manager_signal: bool = False
    # Does the posting describe the CANDIDATE building software? Read from screening's own
    # software-ownership vocabulary, so there is one definition of "builds software" in the system.
    builds_software: bool = False
    # A department-head title. Not an exclusion anywhere; it only keeps this path pointed at the
    # first/sole-ENGINEER shape the preference actually describes.
    management_title: bool = False
    ruleset_version: str = OWNERSHIP_RULESET_VERSION

    @property
    def is_broad_ownership_candidate(self) -> bool:
        """True when the posting established broad or first/sole ownership OF SOFTWARE, for the
        person being hired.

        Read in order; each clause is here because something measurable went wrong without it.

        **A stated narrow scope ends it, whatever else the posting said.** This module's own comment
        claimed "the narrow statement wins" while the code was a disjunction in which it could not —
        so a posting reading "you will join a small engineering team … you will focus exclusively on
        the billing service and will not touch anything else" was retained as a broad-ownership
        candidate while the row printed *narrowly scoped*. The policy's category is "a small team
        **with broad ownership**"; a small team without it is not that category.

        **A department-head title ends it.** "Head of Security" and "VP Pricing & Packaging" both
        reached the retained list at a fit score of 0.00. The preference describes implementing
        across the stack and owning the result, which is not running a department. Such a role still
        arrives on its own fit score exactly as before — nothing is excluded anywhere.

        **Confirmed first/sole ownership is sufficient by itself.** It is the strongest fact the
        preference names, and requiring a second, differently-shaped "builds software" phrase after
        it lost real postings whose sole-ownership fact was already established — a dental group
        writing its duties as noun phrases ("Scope of the role: internal applications, integrations
        …"), and a posting separating verb from object across a noun list ("responsible for the
        design, construction and long-term stewardship of every piece of … software this company
        runs on"). A confirmed sole-engineer role at a non-software employer is by itself enough
        reason for a human to look.

        **Everything weaker needs the software-building duty.** Without it, "own go-to-market
        strategy end to end" and "own our security posture end-to-end" both read as matches, and 31
        of 101 scored rows in a real corpus read BROAD.

        Silence is still silence: `UNKNOWN` structure with `UNSTATED` breadth establishes nothing
        and is never a candidate.
        """
        if self.breadth == OwnershipBreadth.STATED_NARROW:
            return False
        if self.management_title:
            return False
        if self.team_structure == TeamStructure.CONFIRMED_SOLE:
            return True
        established = (
            self.team_structure == TeamStructure.SMALL_TEAM
            or self.breadth == OwnershipBreadth.BROAD
        )
        return established and self.builds_software

    def label(self) -> str:
        """One short phrase a human can read on a report row."""
        team = {
            TeamStructure.CONFIRMED_SOLE: "confirmed first/sole engineer",
            TeamStructure.SMALL_TEAM: "stated small team",
            TeamStructure.UNKNOWN: "team structure not stated",
        }[self.team_structure]
        breadth = {
            OwnershipBreadth.BROAD: "broad ownership",
            OwnershipBreadth.STATED_NARROW: "narrowly scoped",
            OwnershipBreadth.UNSTATED: "scope not stated",
        }[self.breadth]
        return f"{team}; {breadth}"

    def evidence_summary(self) -> str:
        """The phrases the verdict actually rests on, so a wrong reading is diagnosable."""
        return "; ".join(
            f"{s.kind}: {s.matched_text}" for s in self.signals[:4]
        ) or "no ownership-scope evidence in the posting text"

    def to_json(self) -> dict:
        return {
            "job_id": self.job_id,
            "team_structure": self.team_structure.value,
            "breadth": self.breadth.value,
            "is_broad_ownership_candidate": self.is_broad_ownership_candidate,
            "label": self.label(),
            "evidence_summary": self.evidence_summary(),
            "ordinary_business_signal": self.ordinary_business_signal,
            "nontechnical_manager_signal": self.nontechnical_manager_signal,
            "builds_software": self.builds_software,
            "management_title": self.management_title,
            "ruleset_version": self.ruleset_version,
            "signals": [s.to_json() for s in self.signals],
        }


# Sections whose text describes the role or the employer. A benefits block naming a "small team
# atmosphere" is not evidence about the engineering TEAM, so `_SMALL_TEAM_RE` keeps this scope.
_SCOPE_SECTIONS = (
    Section.RESPONSIBILITIES, Section.REQUIREMENTS, Section.BODY, Section.ABOUT, Section.TITLE,
)

# Sole-ownership and breadth statements are read from every section but the equal-opportunity block.
#
# `segment_description` LATCHES a section until the next cue, so a single "Compensation:" line makes
# everything after it BENEFITS until some later heading appears. An independent review measured the
# consequence: the same posting, with and without one sentence of pay boilerplate before the
# ownership statement, assessed as `CONFIRMED_SOLE`/`BROAD` without it and `UNKNOWN`/`UNSTATED` with
# it — and the `with` version reached no readable section at all. Adzuna and Himalayas both put pay
# mid-body, so this was not a corner case.
_SOLE_AND_BREADTH_SECTIONS = _SCOPE_SECTIONS + (Section.BENEFITS, Section.PROCESS)

# A cap on how many matches of ONE pattern are examined inside ONE segment. Each examination rescans
# the segment for clause boundaries, so a single segment carrying hundreds of matches costs
# quadratic time — measured by review at 23.9s for a 42KB single-segment description, inside a
# Lambda. A segment is one segment because the description lost its sentence boundaries to HTML
# stripping, which is exactly when the count runs away. Forty matches of the same ownership pattern
# in one segment have long since established whatever they are going to establish.
_MAX_MATCHES_PER_SEGMENT = 40


def _collect(
    segments: list[Segment],
    pattern: re.Pattern[str],
    kind: str,
    sections: tuple[str, ...] = _SCOPE_SECTIONS,
) -> list[OwnershipSignal]:
    """Every match, polarity-checked inside its own clause.

    Polarity matters here for the same reason it does in screening: "you will NOT be our only
    engineer — you join a team of forty" must not read as confirmed sole ownership.
    """
    out: list[OwnershipSignal] = []
    for seg in segments:
        if seg.section not in sections:
            continue
        for index, match in enumerate(pattern.finditer(seg.text)):
            if index >= _MAX_MATCHES_PER_SEGMENT:
                break
            if polarity(seg.text, match) != "required":
                continue
            clause, _offset = clause_around(seg.text, match)
            out.append(OwnershipSignal(
                kind=kind,
                matched_text=match.group(0),
                section=seg.section,
                context=_context(seg.text, match),
                is_own_duty=describes_own_duty(seg.text, match),
                clause=clause,
            ))
    return out


def _about_this_employer(signal: OwnershipSignal) -> bool:
    """False when the clause is about somebody other than this employer and this hire.

    `is_own_duty` was computed and serialized from the first version of this module and consulted by
    nothing, which is how "Many of our CLIENTS have no in-house engineering team" printed *confirmed
    first/sole engineer* on a row for an employer with teams of six. A team-structure verdict is a
    claim about a specific company; a sentence about a client, a vendor, a founder's previous
    employer or a colleague who already holds the role cannot support one.
    """
    return not _THIRD_PARTY_SUBJECT_RE.search(signal.clause)


def assess_ownership(job: CanonicalJob) -> OwnershipAssessment:
    """Read one posting for ownership scope. Evidence-only; silence stays silent."""
    result = OwnershipAssessment(job_id=job.job_id)
    title = html.unescape(job.title or "")
    body = html.unescape(job.description_text or "")
    segments = [Segment(section=Section.TITLE, text=title)] + segment_description(body)

    # A team-structure claim is a claim about THIS employer, so a clause about a client, a vendor or
    # a founder's previous company cannot make one.
    sole = [
        s for s in _collect(segments, _SOLE_ENGINEER_RE, "sole", _SOLE_AND_BREADTH_SECTIONS)
        if _about_this_employer(s)
    ]
    small = [s for s in _collect(segments, _SMALL_TEAM_RE, "small-team")
             if _about_this_employer(s)]
    # Three things disqualify a breadth phrase, and all three are questions about the CLAUSE rather
    # than about the matched phrase — which is the defect review found in the first version, where
    # the business-outcome guard was tested against `match.group(0)` and therefore never fired on
    # `full ownership` or `complete ownership`, because those alternatives capture two words and the
    # object is never inside them.
    broad = [
        signal
        for signal in _collect(
            segments, _BROAD_SCOPE_RE, "broad", _SOLE_AND_BREADTH_SECTIONS
        )
        if not _BUSINESS_OUTCOME_OBJECT_RE.search(signal.clause)          # owns revenue, not software
        and not _PERSONAL_DEVELOPMENT_OBJECT_RE.search(signal.clause)     # owns a career, not software
        and not _COMPANY_HISTORY_FRAME_RE.search(signal.clause)           # was built, not will build
        and not (                                                         # the workforce, not you
            _COLLECTIVE_SUBJECT_RE.search(signal.clause)
            and not _SECOND_PERSON_RE.search(signal.clause)
        )
        and _about_this_employer(signal)
    ]
    narrow = _collect(segments, _NARROW_SCOPE_RE, "narrow")
    business = _collect(segments, _BUSINESS_FACING_RE, "business-facing")
    nontechnical = _collect(segments, _NONTECHNICAL_MANAGER_RE, "nontechnical-manager")

    # Team structure. Sole outranks small-team because a posting saying both ("a small team, and you
    # would be its only engineer") has established the stronger fact about this role.
    if sole:
        result.team_structure = TeamStructure.CONFIRMED_SOLE
    elif small:
        result.team_structure = TeamStructure.SMALL_TEAM
    else:
        result.team_structure = TeamStructure.UNKNOWN

    # Breadth. A narrow scoping statement is counter-evidence, and when a posting states both, the
    # narrow statement wins: a description that says "own it end to end" and then "you will focus
    # exclusively on the billing service" has scoped the work, whatever the opening sentence claimed.
    if narrow:
        result.breadth = OwnershipBreadth.STATED_NARROW
    elif broad:
        result.breadth = OwnershipBreadth.BROAD
    else:
        result.breadth = OwnershipBreadth.UNSTATED

    result.signals = sole + small + broad + narrow + business + nontechnical
    result.ordinary_business_signal = bool(_ORDINARY_BUSINESS_RE.search(body))
    result.nontechnical_manager_signal = bool(nontechnical)
    result.management_title = bool(_MANAGEMENT_TITLE_RE.search(title))
    result.builds_software = bool(
        _SOFTWARE_ROLE_RE.search(normalize_title_for_matching(title))
        or any(
            _SOFTWARE_OWNERSHIP_RE.search(seg.text) or _PLAIN_SOFTWARE_WORK_RE.search(seg.text)
            for seg in segments
            if seg.section in (Section.RESPONSIBILITIES, Section.REQUIREMENTS, Section.BODY)
        )
    )
    return result


def assess_all(jobs: list[CanonicalJob]) -> dict[str, OwnershipAssessment]:
    return {job.job_id: assess_ownership(job) for job in jobs}
