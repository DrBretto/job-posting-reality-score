"""Deterministic, versioned normalization + canonical hashing (DATA_MODEL §1.3, §2, §4).

No LLM anywhere. `content_hash` is over the canonical field set ONLY so cosmetic re-serialization
by an ATS does not create false `materially-changed` events. Field-scoped sub-hashes let the differ
name WHAT changed without re-diffing full text.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata

from src.common.models import RemoteMode, SalarySource, SalaryStruct

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s,]")

_LOCATION_ABBREV = {
    "sf": "san francisco",
    "nyc": "new york city",
    "ny": "new york",
    "la": "los angeles",
    "us": "united states",
    "usa": "united states",
    "uk": "united kingdom",
    "remote": "remote",
}

_REMOTE_TOKENS = ("remote", "work from home", "wfh", "distributed", "anywhere")
_HYBRID_TOKENS = ("hybrid",)
_ONSITE_TOKENS = ("on-site", "onsite", "in office", "in-office")

# very small deterministic salary parser: $120,000 - $150,000 / $120k-$150k
_SALARY_RE = re.compile(
    r"\$\s*(\d{2,3}(?:,\d{3})?|\d+)\s*(k)?\s*(?:[-–to]+)\s*\$?\s*(\d{2,3}(?:,\d{3})?|\d+)\s*(k)?",
    re.IGNORECASE,
)


def norm_text(value: str | None) -> str:
    """Unescape entities + NFKC + strip HTML + collapse whitespace, preserving case.

    Entity decoding happens FIRST and it is load-bearing, not cosmetic. Feeds ship entity-encoded
    prose, and `doesn&#39;t require a clearance` has the opposite meaning from `require a clearance`.
    Before this, screening matched the requirement and missed the negation, so a posting that
    explicitly said no clearance was needed was excluded for requiring one.

    Tags are stripped AFTER unescaping so an encoded `&lt;script&gt;` becomes literal text rather
    than being removed as markup — the goal is faithful text, not sanitized HTML.
    """
    if not value:
        return ""
    value = html.unescape(str(value))
    value = unicodedata.normalize("NFKC", value)
    value = _TAG_RE.sub(" ", value)
    value = _WS_RE.sub(" ", value)
    return value.strip()


# --------------------------------------------------------------------------------------------------
# Title normalization for MATCHING (not for display)
# --------------------------------------------------------------------------------------------------
# The September 24 defect: a live posting titled `FullStack` scored 0.00 while the identical role
# spelled `Full Stack` scored 0.38, because every title pattern required a separator. The employer's
# spelling of a compound word is not a signal about the job, so matching normalizes it away.
# Live corroboration observed this run: a Linear posting titled "Senior / Staff Fullstack Engineer".
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ACRONYM_BOUNDARY_RE = re.compile(r"(?<=[A-Z]{2})(?=[A-Z][a-z])")

# Compound words an ATS writes with or without a separator. Folded to the spaced form so ONE pattern
# matches every spelling. Keep this list short and evidence-driven; it is not a synonym dictionary.
_COMPOUND_FOLDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfull[\s\-_]*stack\b", re.I), "full stack"),
    (re.compile(r"\bback[\s\-_]*end\b", re.I), "backend"),
    (re.compile(r"\bfront[\s\-_]*end\b", re.I), "frontend"),
    (re.compile(r"\bdev[\s\-_]*ops\b", re.I), "devops"),
    (re.compile(r"\bml[\s\-_]*ops\b", re.I), "mlops"),
    (re.compile(r"\bgen[\s\-_]*ai\b", re.I), "genai"),
    (re.compile(r"\bmulti[\s\-_]*agent\b", re.I), "multi agent"),
)


def normalize_title_for_matching(title: str | None) -> str:
    """Split camel case, fold compound spellings, collapse punctuation. Matching surface only.

    `FullStack` -> `full stack`; `Full-Stack` -> `full stack`; `FullstackEngineer` -> `full stack
    engineer`. The stored/display title is never altered.
    """
    text = norm_text(title)
    if not text:
        return ""
    # Split camel-case and acronym boundaries BEFORE lowercasing, while the case carries the signal.
    text = _ACRONYM_BOUNDARY_RE.sub(" ", text)
    text = _CAMEL_BOUNDARY_RE.sub(" ", text)
    text = text.lower()
    text = re.sub(r"[/|,()\[\]]+", " ", text)
    for pattern, replacement in _COMPOUND_FOLDS:
        text = pattern.sub(replacement, text)
    return _WS_RE.sub(" ", text).strip()


# --------------------------------------------------------------------------------------------------
# Employer + URL normalization for cross-source dedup
# --------------------------------------------------------------------------------------------------
# Suffixes an aggregator appends or drops inconsistently for the same company.
_EMPLOYER_SUFFIX_RE = re.compile(
    r"\b(inc|inc\.|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|gmbh|bv|b\.v|ag|sa|s\.a|"
    r"plc|pty|pte|ab|as|oy|srl|spa|holdings?|group|technologies|technology|labs?|software)\b",
    re.I,
)

# Tracking/session parameters that differ per sighting of the SAME posting.
_TRACKING_PARAM_PREFIXES = ("utm_", "gh_", "ref", "source", "src", "gclid", "fbclid", "mc_", "lever-")
_TRACKING_PARAM_EXACT = frozenset({
    "ref", "source", "src", "referrer", "gclid", "fbclid", "trk", "trackingid", "lang",
    "recruiter", "campaign", "medium", "gh_src", "gh_jid",
})


def normalize_employer(name: str | None) -> str:
    """Case/punctuation/suffix-insensitive employer key.

    Conservative on purpose: it folds only legal-form noise. It never folds two genuinely different
    companies together, because a wrong employer merge silently deletes an opportunity.
    """
    text = _norm_key(name)
    if not text:
        return ""
    text = _EMPLOYER_SUFFIX_RE.sub(" ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return _WS_RE.sub(" ", text).strip()


def canonical_url(url: str | None) -> str:
    """Strip tracking noise so two sightings of one posting produce one key.

    Lowercases scheme/host only — a path can be case-significant. Drops the fragment, sorts the
    surviving query, and removes a trailing slash.
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    if not url:
        return ""
    raw = str(url).strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.lower()
    if not parts.scheme and not parts.netloc:
        return raw.lower()
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    kept = []
    for key, value in parse_qsl(parts.query, keep_blank_values=False):
        low = key.lower()
        if low in _TRACKING_PARAM_EXACT or low.startswith(_TRACKING_PARAM_PREFIXES):
            continue
        kept.append((key, value))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(sorted(kept)), ""))


def url_host(url: str | None) -> str | None:
    from urllib.parse import urlsplit

    if not url:
        return None
    try:
        host = (urlsplit(str(url)).hostname or "").lower()
    except ValueError:
        return None
    return host or None


def _norm_key(value: str | None) -> str:
    """Aggressive lowercase key form for hashing sub-fields (case/punct-insensitive)."""
    value = norm_text(value)
    value = value.lower()
    value = _PUNCT_RE.sub("", value)
    return _WS_RE.sub(" ", value).strip()


def normalize_location(raw_location: str | None) -> str:
    """Deterministic canonical location render (DATA_MODEL §4)."""
    if not raw_location:
        return ""
    text = _norm_key(raw_location)
    parts = re.split(r"[;/|]| and | or |,", text)
    tokens: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        part = _LOCATION_ABBREV.get(part, part)
        tokens.append(part)
    tokens = sorted(set(tokens))
    return " | ".join(tokens)


def detect_remote_mode(explicit: str | None, raw_location: str | None, body: str | None) -> RemoteMode:
    """Map ATS enum (if any) else keyword-scan location + body. Versioned rules table."""
    if explicit:
        e = explicit.strip().lower()
        if e in ("remote", "fullyremote", "fully_remote"):
            return RemoteMode.REMOTE
        if e == "hybrid":
            return RemoteMode.HYBRID
        if e in ("onsite", "on-site", "in_office", "inoffice"):
            return RemoteMode.ONSITE
    hay = f"{_norm_key(raw_location)} {_norm_key(body)[:400]}"
    if any(t in hay for t in _HYBRID_TOKENS):
        return RemoteMode.HYBRID
    if any(t in hay for t in _REMOTE_TOKENS):
        return RemoteMode.REMOTE
    if any(t in hay for t in _ONSITE_TOKENS):
        return RemoteMode.ONSITE
    return RemoteMode.UNSPECIFIED


def parse_salary(body: str | None, stated: SalaryStruct | None = None) -> SalaryStruct | None:
    """Prefer structured provider comp (STATED); else deterministic regex parse (PARSED); else NONE.

    The LLM never sets salary numbers.
    """
    if stated is not None:
        return stated
    if not body:
        return None
    m = _SALARY_RE.search(body)
    if not m:
        return None

    def _to_num(num: str, k: str | None) -> float:
        val = float(num.replace(",", ""))
        if k:
            val *= 1000
        return val

    lo = _to_num(m.group(1), m.group(2))
    hi = _to_num(m.group(3), m.group(4))
    if lo > hi:
        lo, hi = hi, lo
    return SalaryStruct(min=lo, max=hi, currency="USD", period="year", source=SalarySource.PARSED)


def _salary_norm(salary: SalaryStruct | None) -> str:
    if salary is None:
        return ""
    return f"{salary.min}|{salary.max}|{salary.currency}|{salary.period}"


def canonical_json(canonical_fields: dict) -> str:
    """JSON with sorted keys, over the canonical field set ONLY, whitespace/null-normalized."""
    return json.dumps(canonical_fields, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_hashes(
    *,
    title: str,
    canonical_location: str,
    salary: SalaryStruct | None,
    remote_mode: RemoteMode,
    description_text: str,
    department: str | None,
    team: str | None,
    employment_type: str,
) -> tuple[str, dict[str, str]]:
    """Return (content_hash, field_hashes). Content hash is over the canonical set only."""
    field_hashes = {
        "title_hash": _sha(_norm_key(title)),
        "location_hash": _sha(canonical_location),
        "salary_hash": _sha(_salary_norm(salary)),
        "workmode_hash": _sha(remote_mode.value),
        "body_hash": _sha(_norm_key(description_text)),
    }
    canonical = {
        "title": _norm_key(title),
        "canonical_location": canonical_location,
        "salary": _salary_norm(salary),
        "remote_hybrid_language": remote_mode.value,
        "department": _norm_key(department),
        "team": _norm_key(team),
        "employment_type": employment_type,
        "description_text": _norm_key(description_text),
    }
    content_hash = _sha(canonical_json(canonical))
    return content_hash, field_hashes
