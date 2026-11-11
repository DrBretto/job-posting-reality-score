"""Where is the work actually done, and can Brett do it from New Hampshire?

The controlling policy is the operator-confirmed "Location and Compensation" section of
APPLICATION_WORKFLOW.md (2026-09-24):

    Remote is the default. Onsite or hybrid work is acceptable only when genuinely local: no more
    than approximately a 30-minute one-way drive from Laconia, New Hampshire. Check the actual
    worksite and attendance requirements rather than inferring from a city label.

    Plymouth, New Hampshire is a possible exception to discuss with Brett, not blanket approval for
    a longer commute. Portsmouth and Boston commuting are excluded. An employer headquartered in
    either city remains eligible when the role is genuinely remote from New Hampshire.

The policy states a DRIVE DURATION. This module does not own a drive-time measurement and must not
pretend to: an earlier version of the screener answered the policy with a hand-written town list,
which both certified towns nobody measured and rejected a genuinely local job over a comma.

So the classification here is built only out of things that are actually checkable:

* the state boundary — Laconia sits in central New Hampshire, roughly forty miles from the nearest
  out-of-state line, so NO out-of-state worksite is a thirty-minute drive from it. That is a
  geographic fact, not an estimate, and it is the one hard distance rule used;
* what the operator named explicitly — Portsmouth and Boston excluded, Plymouth to discuss;
* everything else inside New Hampshire is left UNRESOLVED on purpose. A Laconia-adjacent town is
  reported as plausible and a farther New Hampshire city as probably-too-far, but neither is
  decided here, because deciding would mean inventing the measurement the policy asked for.

Unresolved is not rejection. A plausible local lead stays visible for worksite confirmation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from src.common.normalize import norm_text

# Two-letter code per US state, keyed by both the full name and the code, so "Belmont, New
# Hampshire", "Belmont, NH", "Belmont NH" and "belmont,nh" all resolve to the same place.
_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC", "washington dc": "DC", "washington d c": "DC",
}
_STATE_CODES = set(_STATE_NAMES.values())
# Common informal spellings that appear in job feeds.
_STATE_ALIASES = {
    "mass": "MA", "calif": "CA", "cali": "CA", "penn": "PA", "conn": "CT", "n h": "NH",
    "n y": "NY", "d c": "DC", "nyc": "NY", "new york city": "NY",
}

STATE_BY_NAME: dict[str, str] = {**_STATE_NAMES, **_STATE_ALIASES}

HOME_STATE = "NH"
HOME_CITY = "laconia"

# Towns ringing Laconia. Being on this list makes a worksite PLAUSIBLY local — a lead worth keeping
# visible — and nothing more. It is not a certification that every address in the town is within a
# thirty-minute drive, which is why LAKES_REGION does not resolve to an eligible verdict.
_LAKES_REGION_TOWNS = frozenset({
    "laconia", "gilford", "belmont", "meredith", "tilton", "northfield", "sanbornton",
    "gilmanton", "center harbor", "centre harbor", "moultonborough", "new hampton",
    "ashland", "bristol", "winnisquam", "lochmere", "alton", "alton bay", "barnstead",
    "canterbury", "franklin", "andover", "hill", "danbury", "holderness", "effingham",
    "gilmanton iron works", "lakes region", "weirs beach",
})

# "a possible exception to discuss with Brett, not blanket approval for a longer commute"
_DISCUSS_TOWNS = frozenset({"plymouth", "campton", "thornton"})

# Named by the operator as excluded for COMMUTING. Portsmouth is in-state, so it needs its own rule;
# the Boston-area names are also caught by the out-of-state rule, and are listed for a clear reason
# string rather than for reach.
_OPERATOR_EXCLUDED_TOWNS = frozenset({
    "portsmouth", "boston", "cambridge", "somerville", "waltham", "newton", "brookline",
    "quincy", "burlington ma", "woburn", "lexington ma", "needham", "watertown",
})

# Tokens that are a work ARRANGEMENT, not a place, and must never be parsed as a city.
_NON_PLACE_TOKENS = frozenset({
    "remote", "remote us", "us remote", "fully remote", "work from home", "wfh", "anywhere",
    "anywhere in the us", "anywhere in the united states", "distributed", "telecommute",
    "hybrid", "onsite", "on site", "in office", "flexible", "multiple locations", "various",
    "united states", "usa", "us", "u s", "u s a", "north america", "global", "worldwide",
    "emea", "apac", "latam", "europe", "canada", "uk", "united kingdom", "nationwide",
    "home based", "field based", "travel", "tbd", "n a", "none", "any", "other",
})

_PLACE_SPLIT_RE = re.compile(r"[;|/\n\r]+|\bor\b|\band\b|(?<=\))\s*,|\+")
_PAREN_RE = re.compile(r"[()\[\]]")
_ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")


class WorksiteClass(str, Enum):
    """What is known about one stated worksite, relative to a 30-minute drive from Laconia."""

    LAKES_REGION = "LAKES_REGION"              # plausibly local; the actual worksite needs checking
    DISCUSS = "DISCUSS"                        # operator named it an exception to discuss
    OPERATOR_EXCLUDED = "OPERATOR_EXCLUDED"    # Portsmouth / Boston commuting, excluded by name
    OTHER_NH = "OTHER_NH"                      # in New Hampshire, probably beyond 30 minutes
    OUT_OF_STATE = "OUT_OF_STATE"              # different US state: cannot be a 30-minute drive
    NON_US = "NON_US"                          # outside the US
    UNKNOWN = "UNKNOWN"                        # no state, unrecognized name, or arrangement-only


# Ordered worst-to-best for reporting; a multi-site posting is judged on its BEST option, because a
# posting offering both a Boston and a Laconia office is a plausible lead, not a rejection.
_PREFERENCE = (
    WorksiteClass.LAKES_REGION,
    WorksiteClass.DISCUSS,
    WorksiteClass.UNKNOWN,
    WorksiteClass.OTHER_NH,
    WorksiteClass.OPERATOR_EXCLUDED,
    WorksiteClass.OUT_OF_STATE,
    WorksiteClass.NON_US,
)


@dataclass
class Place:
    """One stated worksite, normalized."""

    raw: str
    city: str | None
    state: str | None
    worksite: WorksiteClass = WorksiteClass.UNKNOWN

    @property
    def label(self) -> str:
        if self.city and self.state:
            return f"{self.city.title()}, {self.state}"
        return (self.city or "").title() or self.state or self.raw


def _clean_fragment(fragment: str) -> str:
    text = _PAREN_RE.sub(" ", fragment)
    text = _ZIP_RE.sub(" ", text)
    return norm_text(text).strip(" ,-")


def _resolve_state(token: str) -> str | None:
    token = token.strip(" .,")
    if not token:
        return None
    upper = token.upper().replace(".", "").replace(" ", "")
    if len(upper) == 2 and upper in _STATE_CODES:
        return upper
    return STATE_BY_NAME.get(token.lower())


def _parse_fragment(fragment: str) -> Place | None:
    """Turn one comma-shaped fragment into a Place, tolerating missing punctuation."""
    cleaned = _clean_fragment(fragment)
    if not cleaned:
        return None
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if not parts:
        return None

    state: str | None = None
    city_parts: list[str] = []
    for index, part in enumerate(parts):
        resolved = _resolve_state(part)
        if resolved and index > 0:
            state = resolved
            continue
        city_parts.append(part)

    city = " ".join(city_parts).strip()

    # No comma at all: the state may be the trailing word(s) — "Belmont NH", "Belmont New
    # Hampshire". Peel the longest trailing match so the punctuation makes no difference.
    if state is None and city:
        words = city.split()
        for take in (3, 2, 1):
            if len(words) > take:
                candidate = _resolve_state(" ".join(words[-take:]))
                if candidate:
                    state = candidate
                    city = " ".join(words[:-take]).strip()
                    break

    if city.lower() in _NON_PLACE_TOKENS:
        city = ""
    if not city and state is None:
        return None
    return Place(raw=fragment.strip(), city=city.lower() or None, state=state)


def classify_place(place: Place) -> WorksiteClass:
    """Classify one worksite. A shared town name does not make a place local — the state decides."""
    city = place.city or ""
    state = place.state

    if city in _OPERATOR_EXCLUDED_TOWNS or f"{city} {str(state or '').lower()}" in (
        _OPERATOR_EXCLUDED_TOWNS
    ):
        return WorksiteClass.OPERATOR_EXCLUDED
    # "Portsmouth" is excluded by name; "Boston" is both named and out of state.
    if state and state != HOME_STATE:
        return WorksiteClass.OUT_OF_STATE
    if state is None and city and _NON_US_PLACE_RE.search(city):
        return WorksiteClass.NON_US
    if city in _DISCUSS_TOWNS and state in (HOME_STATE, None):
        return WorksiteClass.DISCUSS
    if city in _LAKES_REGION_TOWNS and state in (HOME_STATE, None):
        # State absent: the name matches a town beside Laconia but also towns elsewhere (Alton,
        # Illinois; Belmont, California). Plausible, unconfirmed — not decided either way.
        return WorksiteClass.LAKES_REGION
    if state == HOME_STATE:
        return WorksiteClass.OTHER_NH
    return WorksiteClass.UNKNOWN


def parse_places(*blobs: str | None) -> list[Place]:
    """Every distinct worksite named across the location fields, classified."""
    places: list[Place] = []
    seen: set[tuple[str | None, str | None]] = set()
    for blob in blobs:
        if not blob:
            continue
        for fragment in _PLACE_SPLIT_RE.split(blob):
            place = _parse_fragment(fragment)
            if place is None:
                continue
            place.worksite = classify_place(place)
            key = (place.city, place.state)
            if key in seen:
                continue
            seen.add(key)
            places.append(place)
    return places


def best_worksite(places: list[Place]) -> WorksiteClass:
    """The most favorable stated worksite. Judging a multi-site posting on its worst option would
    reject a posting that offers a local office alongside a distant one."""
    for candidate in _PREFERENCE:
        if any(p.worksite == candidate for p in places):
            return candidate
    return WorksiteClass.UNKNOWN


# ---- residency restrictions ----------------------------------------------------------------------
# A remote label is not eligibility. "Remote (US)" that only employs California or New York
# residents is not open to a New Hampshire resident, and the screener must say so rather than
# reading the word "remote" and stopping.
_RESIDENCY_RE = re.compile(
    r"(?:"
    r"(?:may only|can only|will only) (?:employ|hire|consider)|"
    r"(?:only|exclusively) (?:able to )?(?:employ|hire|consider)|"
    r"(?:must|need to|required to) (?:be a )?(?:reside|resid(?:e|ing|ent)s? (?:in|of)|live (?:in|within))|"
    r"(?:open|available|limited|restricted|eligible) (?:only )?(?:to|in|for)|"
    r"(?:authorized|eligible) to work (?:only )?in|"
    r"(?:candidates?|applicants?|employees?|you) must (?:be|reside|live|are) (?:located|based|residing)?"
    r"\s*(?:in|within)|"
    r"hir(?:e|ing) (?:only )?in|"
    r"(?:employment|this role|this position) is (?:limited|restricted) to"
    r")"
    r"(?P<scope>[^.;!?\n]{0,220})",
    re.I,
)
# Phrases that mean country-level eligibility, which does not restrict a New Hampshire resident.
_COUNTRY_SCOPE_RE = re.compile(
    r"\b(united states|usa|u\.s\.a?\.?|\bus\b|america|north america|anywhere in the (?:us|country)|"
    r"all 50 states|any state|nationwide|continental us)\b", re.I,
)
_STATE_FULL_NAME_RE = re.compile(
    "|".join(sorted((r"\b" + re.escape(n) + r"\b" for n in _STATE_NAMES), key=len, reverse=True)),
    re.I,
)
# Two-letter codes are matched CASE-SENSITIVELY and uppercase only. Half of them are ordinary English
# words — "or", "in", "me", "ok", "hi", "de", "la", "pa", "ma", "co", "id" — and a case-insensitive
# code pattern read "California or New York" as California, OREGON and New York.
_STATE_CODE_RE = re.compile(r"\b(?:" + "|".join(sorted(_STATE_CODES)) + r")\b")


_NOT_LIMITED_RE = re.compile(r"\b(?:not|n't)\s+(?:be\s+)?limited\s+to\b", re.I)
_VISA_LIST_RE = re.compile(
    r"\b(?:h-?1b|f-?1|opt|cpt|j-?1|l-?1|e-?3|o-?1|ead|visa|sponsorship)\b", re.I)


@dataclass
class ResidencyRestriction:
    """A posting-stated limit on where an employee may live."""

    matched_text: str
    context: str
    states: list[str] = field(default_factory=list)
    country_scope: bool = False

    @property
    def excludes_home(self) -> bool:
        """True only when the posting names specific states and New Hampshire is not among them."""
        if self.country_scope or not self.states:
            return False
        return HOME_STATE not in self.states


def find_residency_restriction(text: str | None) -> ResidencyRestriction | None:
    """The first residency limit that actually names states, if any.

    A country-level statement ("must reside in the United States") is not a restriction on Brett,
    and an unparsable one returns None rather than a guess: the report's pending-check path is the
    place for "we could not tell", not an invented exclusion.
    """
    if not text:
        return None
    for match in _RESIDENCY_RE.finditer(text):
        scope = match.group("scope") or ""
        # "This includes, but is not limited to, visa categories such as H-1B, F-1 OPT, TN, J-1"
        # is a work-authorization list, and TN there is the NAFTA/USMCA visa, not Tennessee
        # (PQ-CAREER_FACTORY-166; reproduced on Applied Digital, Mom's Meals and Delinea on
        # 2026-11-11). Neither "not limited to" nor a visa list states where anyone may live.
        if _NOT_LIMITED_RE.search(text[max(0, match.start() - 30):match.start() + 12]):
            continue
        if _VISA_LIST_RE.search(scope):
            continue
        country_scope = bool(_COUNTRY_SCOPE_RE.search(scope))
        states: list[str] = []
        for pattern in (_STATE_FULL_NAME_RE, _STATE_CODE_RE):
            for hit in pattern.finditer(scope):
                resolved = _resolve_state(hit.group(0))
                if resolved and resolved not in states:
                    states.append(resolved)
        if not states:
            continue
        restriction = ResidencyRestriction(
            matched_text=match.group(0).strip(),
            context=scope.strip()[:200],
            states=states,
            country_scope=country_scope,
        )
        if restriction.excludes_home:
            return restriction
    return None


# ---- attendance ----------------------------------------------------------------------------------
# An attendance REQUIREMENT beats a remote label. "Remote / Boston, MA" whose body requires three
# days a week in the Boston office is a Boston hybrid job, and the policy excludes commuting there.
_DAYS = r"(?:\d+|one|two|three|four|five)"
ATTENDANCE_REQUIRED_RE = re.compile(
    "|".join((
        # "must attend the Boston office three days per week", "required to work in our HQ"
        r"(?:must|required to|expected to|need(?:s|ed)? to|will|shall)\s+(?:be\s+)?"
        r"(?:attend|work|come|report|be)\s+(?:in|at|from|to|on[- ]?site|onsite|in[- ]person|"
        r"the|our)?\s*[^.;!?\n]{0,60}?(?:office|hq|headquarters|worksite|job site|hub)",
        # "three days per week in the office", "2 days a week onsite"
        _DAYS + r"\s*(?:\+|or more)?\s*days?\s*(?:per|a|each)\s*week[^.;!?\n]{0,40}"
        r"(?:office|on[- ]?site|onsite|in[- ]person|hq|headquarters|hub)",
        # "work on-site three days per week", "onsite five days a week"
        r"(?:work|working|be)\s+(?:on[- ]?site|onsite|in[- ]office|in[- ]person)"
        r"[^.;!?\n]{0,30}" + _DAYS + r"\s*days?",
        # "on-site five days per week", "On-site at our office five days per week" — no verb at all
        r"(?:on[- ]?site|onsite|in[- ]office|in[- ]person)[^.;!?\n]{0,40}?" + _DAYS
        + r"\s*days?\s*(?:per|a|each)\s*week",
        # "Report daily to our Laconia office." The adverb or a near-adjacent office word is
        # required: "reports to the VP of Engineering in our Boston office" is a reporting LINE, not
        # an attendance requirement, and must not exclude a remote role.
        r"report(?:ing|s)?\s+(?:daily|weekly|each day|every day|in person)\s+to\s+(?:our|the)"
        r"[^.;!?\n]{0,40}(?:office|hq|headquarters|worksite|hub)",
        r"report(?:ing|s)?\s+to\s+(?:our|the)\s+(?:\w+\s+){0,2}(?:office|hq|headquarters|worksite)\b",
        # "in-office attendance is required", "onsite presence required"
        r"(?:in[- ]office|on[- ]?site|onsite|in[- ]person)\s+"
        r"(?:attendance|presence|requirement|days?)",
        # "hybrid schedule of three days"
        r"hybrid[^.;!?\n]{0,40}" + _DAYS + r"\s*days?",
        # "must reside within commuting distance", "must be located near our office"
        r"(?:must|required to|expected to)\s+(?:reside|live|relocate|be located|be based)"
        r"[^.;!?\n]{0,60}(?:within|near|commut)",
    )),
    re.I,
)

# Countries that appear as bare location labels. A non-US worksite is judged by the existing non-US
# rule in the screener; classifying it here keeps "Berlin, Germany" out of the UNKNOWN bucket.
_NON_US_PLACE_RE = re.compile(
    r"\b(germany|france|spain|portugal|italy|netherlands|belgium|poland|romania|ukraine|"
    r"ireland|scotland|wales|england|sweden|norway|denmark|finland|switzerland|austria|"
    r"czechia|czech republic|hungary|greece|turkey|israel|india|pakistan|singapore|japan|"
    r"china|hong kong|taiwan|korea|australia|new zealand|brazil|argentina|chile|colombia|"
    r"mexico|peru|nigeria|kenya|south africa|egypt|morocco|philippines|indonesia|vietnam|"
    r"thailand|malaysia|uae|dubai|saudi|qatar|berlin|london|paris|madrid|lisbon|barcelona|"
    r"amsterdam|dublin|munich|zurich|toronto|vancouver|montreal|bangalore|bengaluru|"
    r"hyderabad|mumbai|delhi|pune|warsaw|prague|budapest|bucharest|kyiv|tel aviv|sydney|"
    r"melbourne|tokyo|seoul|shanghai|beijing|sao paulo|buenos aires|mexico city)\b",
    re.I,
)
