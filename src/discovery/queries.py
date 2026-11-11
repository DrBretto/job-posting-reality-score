"""The discovery query plan — what the system asks when it does not know who to ask.

The controlling constraint: **a query may not name an employer.** The moment a company name enters
a query, the result can only confirm a company somebody already thought of, which is the exact
limitation the overhaul exists to remove. `assert_company_independent` enforces that mechanically
and the held-out acceptance test asserts it, so the property cannot rot into a comment.

Queries describe *work performed*, not titles. A posting that never says "AI" can still be an
applied-AI job, and a posting that says "AI" nine times can be an AI-research role Brett is not
competitive for. Sector queries SUPPLEMENT the work queries; they never become a second whitelist,
and the recall floor family deliberately contains no AI vocabulary at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.common.normalize import normalize_title_for_matching


@dataclass(frozen=True)
class QueryFamily:
    """One coherent group of phrasings for the same kind of work.

    `priority` orders the budget: lower runs first when the budget is tight. `rotates` marks a
    family that must be revisited over time rather than permanently starved by higher priorities.
    """

    key: str
    intent: str
    phrases: tuple[str, ...]
    # Terms that, appearing anywhere in title or description, make a record worth admitting from a
    # BULK feed. Recall-first on purpose: precision is the screener's job, not the crawler's.
    match_terms: tuple[str, ...] = ()
    priority: int = 50
    rotates: bool = True
    sector: str | None = None


# ---- work-performed families: the backbone --------------------------------------------------------
_WORK_FAMILIES: tuple[QueryFamily, ...] = (
    QueryFamily(
        key="internal-tools",
        intent="building the tools a business runs on internally",
        phrases=(
            "internal tools engineer",
            "business systems engineer",
            "internal applications developer",
            "operations engineer internal systems",
            "business applications developer",
        ),
        match_terms=("internal tool", "internal system", "internal application", "business system",
                     "business application", "internal platform", "back office"),
        priority=10,
    ),
    QueryFamily(
        key="ai-implementation",
        intent="putting models inside a working business system",
        phrases=(
            "AI integration engineer",
            "applied AI engineer",
            "LLM integration engineer",
            "AI implementation engineer",
            "machine learning integration",
        ),
        match_terms=("applied ai", "ai integration", "llm", "large language model", "generative ai",
                     "genai", "ai implementation", "agentic", "ai agent", "model integration",
                     "openai", "anthropic", "bedrock", "rag", "retrieval augmented"),
        priority=10,
    ),
    QueryFamily(
        key="automation-integration",
        intent="wiring systems together and removing manual steps",
        phrases=(
            "workflow automation engineer",
            "integration developer",
            "automation engineer software",
            "systems integration engineer",
            "process automation developer",
        ),
        match_terms=("workflow automation", "process automation", "integration develop",
                     "systems integration", "api integration", "etl", "automate manual"),
        priority=20,
    ),
    QueryFamily(
        key="data-extraction",
        intent="turning unstructured documents and sources into usable data",
        phrases=(
            "document data extraction engineer",
            "data pipeline engineer",
            "data extraction automation",
        ),
        match_terms=("data extraction", "document processing", "data pipeline", "ocr",
                     "unstructured data", "web scraping", "data ingestion"),
        priority=30,
    ),
    QueryFamily(
        key="backend-cloud",
        intent="the implementation foundation under all of the above",
        phrases=(
            "backend engineer python aws",
            "senior backend engineer cloud",
            "platform engineer serverless",
        ),
        match_terms=("backend", "back-end", "serverless", "aws lambda", "microservice",
                     "rest api", "python", "golang", "node.js", "postgres"),
        priority=30,
    ),
    # From APPLICATION_WORKFLOW.md § "Broad ownership and first/sole-engineer preference"
    # (2026-09-28). The section names its own clues — "First engineer, sole engineer, founding
    # engineer, generalist, applications engineer, and business systems engineer are useful search
    # clues, not an exhaustive title list" — and says neither AI wording nor a named technology
    # employer is required, so this family carries no AI vocabulary at all.
    #
    # `rotates=False` for the same reason as the recall floor below: this is a standing preference,
    # not a supplement, and a rotating family can be starved for an arbitrary number of runs.
    QueryFamily(
        key="broad-ownership",
        intent="being the first or sole engineer, or owning a business's software end to end",
        phrases=(
            "first software engineer",
            "sole software engineer",
            "founding engineer",
            "generalist software engineer",
            "applications engineer",
        ),
        match_terms=("first engineer", "sole engineer", "only engineer", "founding engineer",
                     "generalist", "first technical hire", "wear many hats", "end to end ownership",
                     "full ownership", "greenfield", "applications engineer",
                     "business systems engineer"),
        priority=10,
        rotates=False,
    ),
    # The recall floor. NO AI vocabulary, NO specialization. This family is why an ordinary title at
    # an ordinary company can arrive at all, and why the plan's worked scenario is reachable.
    QueryFamily(
        key="ordinary-software",
        intent="ordinary senior software engineering, wherever the work is",
        phrases=(
            "senior software engineer",
            "software engineer",
            "full stack engineer",
            "software developer",
            "application engineer",
        ),
        match_terms=("software engineer", "software developer", "full stack", "fullstack",
                     "application engineer", "application developer", "engineer"),
        priority=40,
        rotates=False,  # never starved: it is the floor, not a nice-to-have
    ),
)

# ---- sector-supplementary families ----------------------------------------------------------------
# From the plan: "These are examples, not quotas or an exhaustive taxonomy." They exist to push the
# crawler toward ordinary businesses that a tech-centric feed under-represents. They are KINDS of
# sector, not the permitted set — an employer in an unlisted sector is never penalized, and nothing
# downstream requires a sector match.
SECTOR_EXAMPLES: tuple[str, ...] = (
    "logistics", "hospitality", "manufacturing", "insurance", "healthcare",
    "retail", "professional services", "construction",
)

_SECTOR_WORK_PHRASES: tuple[str, ...] = (
    "software engineer",
    "automation engineer",
    "internal tools",
    "AI integration",
)


def _sector_families() -> tuple[QueryFamily, ...]:
    out = []
    for sector in SECTOR_EXAMPLES:
        out.append(QueryFamily(
            key=f"sector-{sector.replace(' ', '-')}",
            intent=f"ordinary {sector} businesses hiring engineers, not software vendors",
            phrases=tuple(f"{sector} {phrase}" for phrase in _SECTOR_WORK_PHRASES),
            match_terms=(sector,),
            priority=60,
            rotates=True,
            sector=sector,
        ))
    return tuple(out)


ALL_FAMILIES: tuple[QueryFamily, ...] = _WORK_FAMILIES + _sector_families()
FAMILIES_BY_KEY: dict[str, QueryFamily] = {f.key: f for f in ALL_FAMILIES}


# --------------------------------------------------------------------------------------------------
# The company-independence invariant
# --------------------------------------------------------------------------------------------------
class CompanyNamedInQuery(ValueError):
    """A query named an employer. That would make discovery a lookup, not a search."""


def assert_company_independent(query: str, known_employers: set[str] | frozenset[str]) -> None:
    """Refuse a query that names a known employer.

    Checked against the *normalized* query and normalized employer names so casing, punctuation and
    legal suffixes cannot smuggle a name through.
    """
    from src.common.normalize import normalize_employer

    haystack = f" {normalize_employer(query)} "
    for employer in known_employers:
        needle = normalize_employer(employer)
        if len(needle) < 3:
            continue  # too short to match safely; would false-positive on ordinary words
        if f" {needle} " in haystack:
            raise CompanyNamedInQuery(
                f"query {query!r} names known employer {employer!r}; discovery queries must be "
                "about work, never about a company we already know"
            )


@dataclass
class QueryPlan:
    """The ordered set of (family, phrase) work items for a run."""

    items: list[tuple[str, str]] = field(default_factory=list)  # (family_key, phrase)

    def __len__(self) -> int:
        return len(self.items)


def build_query_plan(
    *,
    known_employers: set[str] | frozenset[str] = frozenset(),
    families: tuple[QueryFamily, ...] = ALL_FAMILIES,
    deprioritize: tuple[str, ...] = (),
) -> QueryPlan:
    """Order every family's phrases by priority, validating company-independence as we go.

    `deprioritize` holds family keys already well covered by recent runs; they move to the back so
    under-covered families get the budget first. Rotation is how a finite budget still eventually
    revisits everything instead of permanently starving low-priority work.
    """
    ordered = sorted(
        families,
        key=lambda f: (f.key in deprioritize and f.rotates, f.priority, f.key),
    )
    plan = QueryPlan()
    for family in ordered:
        for phrase in family.phrases:
            assert_company_independent(phrase, known_employers)
            plan.items.append((family.key, phrase))
    return plan


# --------------------------------------------------------------------------------------------------
# Local matching for BULK feeds
# --------------------------------------------------------------------------------------------------
# Remotive / Remote OK / Jobicy / Himalayas publish their whole current feed and have no useful
# server-side text query, so the polite and more complete move is one bulk request per run (Remotive's
# own notice advises at most four requests per day) and then matching locally. Adzuna is the opposite:
# a real search API, queried phrase by phrase under a budget.

_NEGATIVE_MATCH_RE = re.compile(
    # Records that are structurally not an engineering opening we can act on. This is a CRAWLER
    # filter for obvious non-jobs, deliberately narrow; role suitability is the screener's decision.
    r"\b(course|bootcamp|curriculum|certification program|talent (?:pool|network|community)|"
    r"general application|speculative application|future opportunities|join our talent|"
    r"expression of interest)\b",
    re.I,
)


_TERM_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _term_pattern(term: str) -> re.Pattern[str]:
    """Word-boundary matcher for one match term.

    Plain substring matching is wrong here and was caught by a live-payload check: `rag` matched
    inside "sto**rag**e" and `go` inside ordinary prose, so unrelated postings claimed the
    applied-AI family and the coverage numbers became meaningless. Boundaries keep recall-first
    matching honest.
    """
    key = term.strip().lower()
    cached = _TERM_RE_CACHE.get(key)
    if cached is None:
        # Internal whitespace matches any run of separators, so "data pipeline" also matches
        # "data-pipeline" and "data  pipeline". A trailing plural is allowed on the last word, so
        # the singular term "internal tool" matches "internal tools" — recall-first matching that
        # misses the plural form of its own term is just a bug with extra steps.
        body = r"[\s\-_/]+".join(re.escape(part) for part in key.split())
        cached = re.compile(rf"(?<![\w]){body}(?:e?s)?(?![\w])", re.I)
        _TERM_RE_CACHE[key] = cached
    return cached


def record_matches_family(
    family: QueryFamily, *, title: str, description: str, extra: str = ""
) -> bool:
    """Recall-first local match for a bulk-feed record.

    Title is matched on the normalized form, so `FullStack` matches a `full stack` term — the same
    spelling defect that made a live posting score 0.00 also silently suppressed crawler matches.
    """
    if not family.match_terms:
        return True
    hay = " ".join((
        normalize_title_for_matching(title),
        (description or "").lower(),
        (extra or "").lower(),
    ))
    return any(_term_pattern(term).search(hay) for term in family.match_terms)


def is_obvious_non_job(title: str, description: str) -> str | None:
    """Return a reason when a record is plainly not an actionable opening, else None."""
    hit = _NEGATIVE_MATCH_RE.search(f"{title} {description or ''}")
    return hit.group(0).lower() if hit else None


def match_families(title: str, description: str, extra: str = "") -> list[str]:
    """Every family this record satisfies. A record can legitimately answer several questions."""
    return [
        f.key for f in ALL_FAMILIES
        if record_matches_family(f, title=title, description=description, extra=extra)
    ]
