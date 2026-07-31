"""Deterministic, versioned normalization + canonical hashing (DATA_MODEL §1.3, §2, §4).

No LLM anywhere. `content_hash` is over the canonical field set ONLY so cosmetic re-serialization
by an ATS does not create false `materially-changed` events. Field-scoped sub-hashes let the differ
name WHAT changed without re-diffing full text.
"""

from __future__ import annotations

import hashlib
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
    """NFKC + strip HTML + collapse whitespace + lowercase-preserving plaintext."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value)
    value = _TAG_RE.sub(" ", value)
    value = _WS_RE.sub(" ", value)
    return value.strip()


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
