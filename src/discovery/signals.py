"""Company-first discovery: financing signals that precede a published opening.

The question this answers is not "who has posted a job" but "which small companies have just raised
money and might need an engineer before they say so". The source is the SEC's EDGAR full-text search
over Form D — the notice a company files within fifteen days of the first sale in an exempt securities
offering. A Form D is verified, dated, first-party evidence that money changed hands. It is NOT
evidence of a hiring plan, an engineering budget or a contract. Every signal produced here therefore
carries `mandate: unknown` and lands on a RESEARCH WATCHLIST that the report renders separately from
candidates. Nothing in this module can put a company into the shortlist.

A signal GRADUATES only on evidence of paid work: the same employer appearing with an actual opening
in this round's discovered postings. Graduation names the posting; it never infers one.

Access, stated exactly: EDGAR full-text search (`efts.sec.gov`) answers this client's declared
project User-Agent. The filing documents themselves (`www.sec.gov/Archives/...`, which carry the
offering amount and industry group) refuse any client whose User-Agent does not declare a contact
e-mail address. No personal address is placed in a request on the operator's behalf, so amounts are
not retrieved; the watchlist says so rather than guessing. Supplying a contact declaration is an
operator decision isolated to this one source.

Privacy: the related-persons section of a Form D names individuals. It is never read or stored.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode

from pydantic import BaseModel, Field

from src.common.normalize import normalize_employer

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_USER_AGENT = "jprs-job-radar/1.1 (personal job-posting radar)"
# The full-text query: Form D's industry-group field prints these phrases verbatim, so a hit means the
# filer itself classified the offering under that industry group.
FORM_D_TECH_QUERY = '"Other Technology"'
PAGE_SIZE = 100          # EFTS returns at most 100 hits per request
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MAX_REQUESTS = 5
# Local first: Laconia, NH. Then the rest of New England, then everyone else by recency.
HOME_STATE = "NH"
NEARBY_STATES = ("MA", "ME", "VT", "RI", "CT")

# Pooled investment vehicles file Form D too. They are funds, not operating companies that could hire.
_FUND_RE = re.compile(
    r"\b(fund|funds|l\.?p\.?|spv|spvc|series \d+|capital partners|investors?,? llc|"
    r"holdings,? llc|feeder|master fund|co-invest|opportunit(?:y|ies) (?:fund|lp))\b",
    re.I,
)


class CompanySignal(BaseModel):
    """One company with verified financing and no established engineering mandate."""

    company: str
    cik: str
    filing_date: str
    form: str
    location: str | None = None
    state: str | None = None
    evidence_kind: str = "financing: SEC Form D notice of an exempt offering (sale has occurred)"
    evidence_url: str
    industry_basis: str = "filer classified the offering as \"Other Technology\" (full-text match)"
    amount: str = "not retrieved — the filing document requires a declared contact in the client "\
                  "User-Agent"
    mandate: str = "unknown — financing is not evidence of a hiring plan, budget or contract"
    status: str = "watchlist"          # watchlist | graduated
    graduated_by: list[str] = Field(default_factory=list)   # job ids of observed openings
    uncertainties: list[str] = Field(default_factory=lambda: [
        "no opening, contract or engineering budget established",
        "headcount, stage and remote policy unknown",
        "financing amount not retrieved",
    ])
    priority: int = 2                  # 0 = home state, 1 = New England, 2 = elsewhere


class SignalRound(BaseModel):
    """What one round of the company-first route did, including what it could not do."""

    source: str = "sec_edgar_form_d"
    run_id: str
    queried_at: str
    lookback_days: int
    requests_spent: int = 0
    filings_seen: int = 0
    funds_skipped: int = 0
    signals: list[CompanySignal] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=lambda: [
        "financing evidence only: a watchlist entry is never a candidate",
        "offering amounts and industry codes are in filing documents this client is not "
        "permitted to fetch without a declared contact address (operator decision)",
    ])


def efts_url(*, start: datetime, end: datetime, offset: int) -> str:
    params = {
        "q": FORM_D_TECH_QUERY,
        "forms": "D",
        "dateRange": "custom",
        "startdt": start.date().isoformat(),
        "enddt": end.date().isoformat(),
    }
    if offset:
        params["from"] = str(offset)
    return f"{EFTS_URL}?{urlencode(params)}"


def _filing_url(cik: str, adsh: str) -> str:
    return (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK="
        f"{cik.lstrip('0')}&type=D&dateb=&owner=include&count=40"
        if not adsh else
        f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{adsh.replace('-', '')}/"
    )


def parse_efts(payload: dict) -> list[dict]:
    if not isinstance(payload, dict) or "hits" not in payload:
        raise ValueError("efts: missing 'hits'")
    return list(payload["hits"].get("hits") or [])


def signals_from_hits(hits: list[dict]) -> tuple[list[CompanySignal], int]:
    """One signal per company (CIK), newest filing kept. Returns (signals, funds_skipped)."""
    by_cik: dict[str, CompanySignal] = {}
    funds = 0
    for hit in hits:
        src = hit.get("_source") or {}
        names = src.get("display_names") or []
        ciks = src.get("ciks") or []
        if not names or not ciks:
            continue
        name = re.sub(r"\s*\(CIK \d+\)\s*$", "", str(names[0])).strip()
        if _FUND_RE.search(name):
            funds += 1
            continue
        cik = str(ciks[0])
        adsh = str(src.get("adsh") or "")
        states = src.get("biz_states") or []
        state = states[0] if states else None
        locations = src.get("biz_locations") or []
        signal = CompanySignal(
            company=name,
            cik=cik,
            filing_date=str(src.get("file_date") or ""),
            form=str(src.get("form") or "D"),
            location=locations[0] if locations else None,
            state=state,
            evidence_url=_filing_url(cik, adsh),
            priority=0 if state == HOME_STATE else (1 if state in NEARBY_STATES else 2),
        )
        prior = by_cik.get(cik)
        if prior is None or signal.filing_date > prior.filing_date:
            by_cik[cik] = signal
    ordered = sorted(by_cik.values(), key=lambda s: (s.priority, _neg_date(s.filing_date), s.company))
    return ordered, funds


def _neg_date(value: str) -> str:
    # Sort newest first inside a priority band without parsing: invert each digit.
    return "".join(chr(ord("9") - ord(c) + ord("0")) if c.isdigit() else c for c in value)


def graduate(signals: list[CompanySignal], jobs) -> list[CompanySignal]:
    """Mark a signal graduated when the same employer has an observed opening this round."""
    by_employer: dict[str, list[str]] = {}
    for job in jobs:
        key = normalize_employer(job.employer_name or "")
        if key:
            by_employer.setdefault(key, []).append(job.job_id)
    for signal in signals:
        ids = by_employer.get(normalize_employer(signal.company))
        if ids:
            signal.status = "graduated"
            signal.graduated_by = sorted(ids)
            signal.mandate = "an opening at this employer was observed this round (see graduated_by)"
            signal.uncertainties = [u for u in signal.uncertainties
                                    if not u.startswith("no opening")]
    return signals


def live_fetch(url: str):
    """Fetch through the shared connector network layer, so the host allowlist and retries apply."""
    from src.common.connectors import Connector

    # EDGAR refuses a User-Agent carrying a URL (measured 2026-11-11: the shared project agent, which
    # names a placeholder repository link, gets 403; the same agent without the link gets 200).
    return Connector.fetch_raw(Connector(), "sec_edgar", url=url, user_agent=EDGAR_USER_AGENT)


def run_signal_round(
    *, run_id: str, now: datetime, fetch, lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_requests: int = DEFAULT_MAX_REQUESTS, jobs=(),
) -> SignalRound:
    """One bounded pass. `fetch(url) -> FetchResult`. Never raises for a source failure."""
    out = SignalRound(run_id=run_id, queried_at=now.isoformat(), lookback_days=lookback_days)
    start, end = now - timedelta(days=lookback_days), now
    hits: list[dict] = []
    total = None
    offset = 0
    while out.requests_spent < max_requests and (total is None or offset < total):
        out.requests_spent += 1
        try:
            fr = fetch(efts_url(start=start, end=end, offset=offset))
            if not fr.raw_bytes:
                raise ValueError(f"no body ({fr.error_class or fr.http_status})")
            payload = json.loads(fr.raw_bytes.decode("utf-8"))
            page = parse_efts(payload)
        except Exception as exc:  # noqa: BLE001 - a failed page is reported, not fatal
            out.failures.append(f"page at offset {offset}: {type(exc).__name__}: {exc}")
            break
        total = int((payload["hits"].get("total") or {}).get("value") or 0)
        hits.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    if total is not None and offset + PAGE_SIZE < total and out.requests_spent >= max_requests:
        out.failures.append(
            f"request budget reached: {len(hits)} of {total} filings read this round")
    out.filings_seen = len(hits)
    signals, funds = signals_from_hits(hits)
    out.funds_skipped = funds
    out.signals = graduate(signals, jobs)
    return out
