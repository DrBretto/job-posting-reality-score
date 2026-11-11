"""Operator-assisted URL import — the honest fallback, labelled as one.

The plan is explicit that this path may NOT be presented as discovery: "A manual URL importer,
hard-coded demonstration list, or provider interface without a working implementation does not pass
as discovery." So every record produced here is stamped `SourceKind.MANUAL_IMPORT`, carries an
`operator_supplied_url` uncertainty marker, and is counted separately in coverage. A run whose only
"discovery" was a manual import reports discovery coverage as NOT-RUN.

It exists because it is genuinely useful: the operator finds something himself, drops the URL in, and
it flows through the same normalization, screening, scoring, dedup and history as everything else
instead of living in a chat message.

Two ways in:
  1. a supported ATS posting URL  -> board token + native id are derived from the URL itself
  2. any other public posting URL -> fetched through the fetch guard and parsed for schema.org
                                     JobPosting data; if that is absent it becomes an explicit
                                     verification-queue lead rather than an invented job record
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from src.common.fetch_guard import FetchRefused, guarded_fetch
from src.common.models import (
    CanonicalJob,
    EmploymentType,
    IdKind,
    RemoteMode,
    SourceKind,
    VerificationState,
)
from src.common.normalize import norm_text, url_host
from src.discovery.admission import detect_board

_JSONLD_RE = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


@dataclass
class ImportOutcome:
    jobs: list[CanonicalJob] = field(default_factory=list)
    queued_for_verification: list[dict] = field(default_factory=list)
    refused: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "imported": len(self.jobs),
            "queued_for_verification": self.queued_for_verification,
            "refused": self.refused,
        }


def _iter_jobposting(node):
    """Yield every JobPosting object in an arbitrarily nested JSON-LD graph."""
    if isinstance(node, list):
        for item in node:
            yield from _iter_jobposting(item)
        return
    if not isinstance(node, dict):
        return
    node_type = node.get("@type")
    types = node_type if isinstance(node_type, list) else [node_type]
    if any(str(t).lower() == "jobposting" for t in types if t):
        yield node
    for value in node.values():
        if isinstance(value, (dict, list)):
            yield from _iter_jobposting(value)


def _employer_from_jsonld(posting: dict) -> str:
    org = posting.get("hiringOrganization")
    if isinstance(org, dict):
        return norm_text(org.get("name"))
    return norm_text(org if isinstance(org, str) else "")


def _location_from_jsonld(posting: dict) -> str:
    loc = posting.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, dict):
        address = loc.get("address")
        if isinstance(address, dict):
            parts = [
                address.get("addressLocality"), address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            return ", ".join(norm_text(str(p)) for p in parts if p)
        return norm_text(str(loc.get("name") or ""))
    if str(posting.get("jobLocationType") or "").upper().startswith("TELECOMMUTE"):
        return "Remote"
    return ""


def parse_jobposting_html(html: str, url: str, *, now: datetime) -> CanonicalJob | None:
    """Build a CanonicalJob from schema.org JobPosting JSON-LD, or None when absent.

    Returning None is a real answer: an unsupported page with no structured data becomes a
    verification-queue lead. Nothing is guessed from prose.
    """
    for block in _JSONLD_RE.findall(html or ""):
        try:
            data = json.loads(block.strip())
        except (ValueError, TypeError):
            continue
        for posting in _iter_jobposting(data):
            title = norm_text(posting.get("title"))
            employer = _employer_from_jsonld(posting)
            if not title or not employer:
                continue
            description = posting.get("description") or ""
            key = hashlib.sha256(url.encode()).hexdigest()[:20]
            source_id = f"careers_page:{url_host(url) or 'unknown'}"
            job = CanonicalJob(
                source_id=source_id,
                job_id=f"{source_id}#{key}",
                id_kind=IdKind.URL_SLUG,
                provider_native_id=key,
                employer_name=employer,
                employer_careers_url=url,
                source_kind=SourceKind.CAREERS_PAGE,
                title=title,
                description_text=norm_text(description),
                description_native=str(description),
                posting_url=url,
                apply_url=norm_text(posting.get("url")) or url,
                apply_host=url_host(url),
                employment_type=_employment_from_jsonld(posting),
                verification_state=VerificationState.EMPLOYER_CONFIRMED,
                verified_at=now,
                uncertainty=["parsed_from_page_structured_data"],
            )
            from src.common.connectors import GreenhouseConnector

            return GreenhouseConnector()._finish_job(
                job, raw_location=_location_from_jsonld(posting) or None,
                explicit_workmode=(
                    "remote"
                    if str(posting.get("jobLocationType") or "").upper().startswith("TELECOMMUTE")
                    else None
                ),
                stated_salary=None, now=now,
            )
    return None


def _employment_from_jsonld(posting: dict) -> EmploymentType:
    raw = posting.get("employmentType")
    if isinstance(raw, list):
        raw = " ".join(str(r) for r in raw)
    text = str(raw or "").upper()
    if "PART" in text:
        return EmploymentType.PART_TIME
    if "CONTRACT" in text or "TEMPORARY" in text:
        return EmploymentType.CONTRACT
    if "INTERN" in text:
        return EmploymentType.INTERN
    if "FULL" in text:
        return EmploymentType.FULL_TIME
    return EmploymentType.UNSPECIFIED


def import_urls(
    urls: list[str],
    *,
    now: datetime,
    fetch=None,
    ats_fetch=None,
) -> ImportOutcome:
    """Import operator-supplied posting URLs.

    `fetch(url) -> GuardedResponse` and `ats_fetch(provider, token) -> (snapshot, jobs)` are both
    injectable so this is testable offline.
    """
    outcome = ImportOutcome()
    fetch = fetch or guarded_fetch

    for raw_url in urls:
        url = (raw_url or "").strip()
        if not url:
            continue
        board = detect_board(url)
        if board is not None and ats_fetch is not None:
            provider, token = board
            try:
                _snapshot, jobs = ats_fetch(provider.value, token)
            except Exception as exc:  # noqa: BLE001
                outcome.refused.append(
                    {"url": url, "reason": "ats_fetch_failed", "detail": str(exc)[:120]}
                )
                continue
            matched = [j for j in jobs if _url_matches(j, url)]
            for job in matched or []:
                job.source_kind = SourceKind.MANUAL_IMPORT
                if "operator_supplied_url" not in job.uncertainty:
                    job.uncertainty.append("operator_supplied_url")
                outcome.jobs.append(job)
            if not matched:
                outcome.queued_for_verification.append({
                    "url": url,
                    "reason": (
                        f"{provider.value} board {token!r} was readable but no current posting on it "
                        f"matches this URL; the posting may have closed"
                    ),
                })
            continue

        try:
            response = fetch(url)
        except FetchRefused as refused:
            outcome.refused.append(
                {"url": url, "reason": refused.reason, "detail": refused.detail}
            )
            continue
        except Exception as exc:  # noqa: BLE001
            outcome.refused.append(
                {"url": url, "reason": "unexpected_error", "detail": f"{type(exc).__name__}: {exc}"}
            )
            continue

        body = response.body.decode("utf-8", errors="replace")
        job = parse_jobposting_html(body, response.final_url or url, now=now)
        if job is None:
            # The honest outcome for an unsupported page: a visible lead, not a fabricated record.
            outcome.queued_for_verification.append({
                "url": url,
                "reason": (
                    "page fetched successfully but publishes no schema.org JobPosting data; kept as "
                    "a verification-queue lead for manual review rather than parsed from prose"
                ),
            })
            continue
        job.source_kind = SourceKind.MANUAL_IMPORT
        job.uncertainty.append("operator_supplied_url")
        outcome.jobs.append(job)

    return outcome


def _url_matches(job: CanonicalJob, url: str) -> bool:
    from src.common.normalize import canonical_url

    target = canonical_url(url)
    for candidate in (job.posting_url, job.apply_url):
        if candidate and canonical_url(candidate) == target:
            return True
    # A board URL ending in the native id is also a match (…/jobs/12345).
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return bool(job.provider_native_id) and job.provider_native_id == tail
