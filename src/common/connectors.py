"""Per-ATS connectors (SOURCE_CONNECTOR_AND_COMPLIANCE_SPEC).

Uniform contract, every ATS:
  fetch -> write raw+receipt BEFORE parse -> label status (SUCCESS/EMPTY_SUCCESS/PARTIAL/FETCH_FAILED)
  -> map provider fields to CanonicalJob. The connector NEVER decides disappearance.

Compliance: sanctioned public GET only, host-allowlist (SSRF guard), truthful identifying
User-Agent with NO personal contact, backoff on 429/503. Ashby is behind a feature flag
(unverified id permanence, D2/U4).

The network-touching part (`fetch_raw`) is deliberately separated from the pure `build_snapshot`
mapping so tests exercise status-labeling + id-mapping against fixtures with zero live network.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.common.models import (
    CONNECTOR_VERSION,
    CanonicalJob,
    EmploymentType,
    IdKind,
    Provider,
    RemoteMode,
    SalarySource,
    SalaryStruct,
    SnapshotStatus,
    SourceReceipt,
    SourceSnapshot,
)
from src.common.normalize import (
    compute_hashes,
    detect_remote_mode,
    normalize_location,
    norm_text,
    parse_salary,
)

USER_AGENT = "jprs-job-radar/1.0 (+https://github.com/jprs; personal job-posting radar)"

# SSRF host allowlist — the ONLY hosts a connector may reach.
HOST_ALLOWLIST = frozenset({
    "boards-api.greenhouse.io",
    "api.lever.co",
    "api.eu.lever.co",
    "api.ashbyhq.com",
})

# Ashby stays behind this flag until URL-slug UUID permanence is verified (D2/U4).
ASHBY_ENABLED = False

_ASHBY_UUID_RE = re.compile(
    r"/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


class FetchResult:
    """Raw bytes + transport metadata handed from the network layer to the mapper."""

    def __init__(
        self,
        *,
        raw_bytes: bytes | None,
        http_status: int | None,
        error_class: str | None,
        endpoint_url: str,
        request_at: datetime,
        response_at: datetime,
        etag: str | None = None,
    ):
        self.raw_bytes = raw_bytes
        self.http_status = http_status
        self.error_class = error_class
        self.endpoint_url = endpoint_url
        self.request_at = request_at
        self.response_at = response_at
        self.etag = etag


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _receipt(provider: Provider, fr: FetchResult) -> SourceReceipt:
    raw = fr.raw_bytes or b""
    return SourceReceipt(
        provider=provider,
        endpoint_url=fr.endpoint_url,
        request_at=fr.request_at,
        response_at=fr.response_at,
        http_status=fr.http_status,
        etag=fr.etag,
        content_length=len(raw) if fr.raw_bytes is not None else None,
        connector_version=CONNECTOR_VERSION,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
    )


class Connector:
    """Base connector. Subclasses provide `endpoint`, `parse_jobs`, `map_job`."""

    provider: Provider

    def endpoint(self, board_token: str) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def parse_jobs(self, payload) -> list[dict]:  # pragma: no cover - overridden
        raise NotImplementedError

    def map_job(self, source_id: str, raw: dict, *, now: datetime) -> CanonicalJob:  # pragma: no cover
        raise NotImplementedError

    # -- network layer (not exercised by tests; kept thin + polite) --------------------------------
    def fetch_raw(self, board_token: str, *, timeout: int = 20, max_attempts: int = 3) -> FetchResult:
        url = self.endpoint(board_token)
        host = urlparse(url).hostname or ""
        if host not in HOST_ALLOWLIST:
            raise ValueError(f"host not on allowlist: {host!r}")

        request_at = _now()
        backoff = 1.0
        last_error_class = "unknown"
        for attempt in range(1, max_attempts + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (allowlisted)
                    raw = resp.read()
                    return FetchResult(
                        raw_bytes=raw,
                        http_status=resp.status,
                        error_class=None,
                        endpoint_url=url,
                        request_at=request_at,
                        response_at=_now(),
                        etag=resp.headers.get("ETag"),
                    )
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                    last_error_class = f"http_{e.code}"
                    continue
                if e.code == 404:
                    # permanent — surface as FETCH_FAILED with a distinct class the collector skips
                    return FetchResult(
                        raw_bytes=None, http_status=404, error_class="http_404",
                        endpoint_url=url, request_at=request_at, response_at=_now(),
                    )
                last_error_class = f"http_{e.code}"
                if e.code >= 500 and attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                break
            except (urllib.error.URLError, TimeoutError, OSError):
                last_error_class = "timeout"
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                break
        return FetchResult(
            raw_bytes=None, http_status=None, error_class=last_error_class,
            endpoint_url=url, request_at=request_at, response_at=_now(),
        )

    # -- pure mapping layer (fully tested against fixtures) ----------------------------------------
    def build_snapshot(
        self,
        board_token: str,
        fr: FetchResult,
        *,
        prior_job_count: int | None = None,
        snapshot_id: str | None = None,
    ) -> tuple[SourceSnapshot, list[CanonicalJob]]:
        """Label the snapshot honestly + map jobs. Never decides disappearance.

        Status rules (uniform):
          transport error / timeout / 5xx / 429 unresolved -> FETCH_FAILED
          200 + body fails schema validation                -> PARTIAL (parse_error)
          200 + well-formed + N>0 jobs                       -> SUCCESS
          200 + well-formed + 0 jobs                         -> EMPTY_SUCCESS,
              BUT if prior had N>0 -> auto-downgrade to PARTIAL (full-drop guard)
        """
        source_id = f"{self.provider.value}:{board_token}"
        snap_id = snapshot_id or uuid.uuid4().hex
        now = fr.response_at
        receipt = _receipt(self.provider, fr)

        # transport failure
        if fr.raw_bytes is None:
            return (
                SourceSnapshot(
                    snapshot_id=snap_id, source_id=source_id, fetched_at=now,
                    status=SnapshotStatus.FETCH_FAILED, http_status=fr.http_status,
                    job_count_observed=None, bytes=None, request_receipt=receipt,
                    error_class=fr.error_class or "transport",
                    notes="no usable job list",
                ),
                [],
            )

        # parse / schema validation
        try:
            payload = json.loads(fr.raw_bytes.decode("utf-8"))
            raw_jobs = self.parse_jobs(payload)
        except Exception as exc:  # malformed 200 -> PARTIAL, removals suppressed downstream
            return (
                SourceSnapshot(
                    snapshot_id=snap_id, source_id=source_id, fetched_at=now,
                    status=SnapshotStatus.PARTIAL, http_status=fr.http_status,
                    job_count_observed=None, bytes=len(fr.raw_bytes), request_receipt=receipt,
                    error_class="parse_error", notes=f"schema validation failed: {exc}",
                ),
                [],
            )

        jobs = [self.map_job(source_id, rj, now=now) for rj in raw_jobs]
        n = len(jobs)

        if n == 0:
            if prior_job_count is not None and prior_job_count > 0:
                # full-drop guard: 200-empty after nonempty -> PARTIAL pending confirmation
                status = SnapshotStatus.PARTIAL
                notes = "full-drop guard: 0 jobs after prior nonempty; awaiting confirming SUCCESS"
            else:
                status = SnapshotStatus.EMPTY_SUCCESS
                notes = "empty board (clean)"
        else:
            status = SnapshotStatus.SUCCESS
            notes = None

        return (
            SourceSnapshot(
                snapshot_id=snap_id, source_id=source_id, fetched_at=now,
                status=status, http_status=fr.http_status, job_count_observed=n,
                bytes=len(fr.raw_bytes), request_receipt=receipt, error_class=None, notes=notes,
            ),
            jobs if status in (SnapshotStatus.SUCCESS, SnapshotStatus.EMPTY_SUCCESS) else [],
        )

    def _finish_job(
        self,
        job: CanonicalJob,
        *,
        raw_location: str | None,
        explicit_workmode: str | None,
        stated_salary: SalaryStruct | None,
        now: datetime,
    ) -> CanonicalJob:
        """Shared normalization tail: location, remote-mode, salary, hashes, derived timing."""
        job.canonical_location = normalize_location(raw_location)
        job.raw_location = raw_location
        job.remote_hybrid_language = detect_remote_mode(
            explicit_workmode, raw_location, job.description_text
        )
        job.salary = parse_salary(job.description_text, stated_salary)
        content_hash, field_hashes = compute_hashes(
            title=job.title,
            canonical_location=job.canonical_location,
            salary=job.salary,
            remote_mode=job.remote_hybrid_language,
            description_text=job.description_text,
            department=job.department,
            team=job.team,
            employment_type=job.employment_type.value,
        )
        job.content_hash = content_hash
        job.field_hashes = field_hashes
        job.first_seen_at = now      # placeholder; the differ authoritatively sets first_seen_at
        job.last_seen_at = now
        return job


def _epoch_ms(value) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _iso(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class GreenhouseConnector(Connector):
    provider = Provider.GREENHOUSE

    def endpoint(self, board_token: str) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, dict) or "jobs" not in payload:
            raise ValueError("greenhouse: missing 'jobs' array")
        jobs = payload["jobs"]
        if not isinstance(jobs, list):
            raise ValueError("greenhouse: 'jobs' is not a list")
        for j in jobs:
            if "id" not in j or "title" not in j:
                raise ValueError("greenhouse: job missing required id/title")
        return jobs

    def map_job(self, source_id: str, raw: dict, *, now: datetime) -> CanonicalJob:
        native_id = str(raw["id"])
        location = (raw.get("location") or {}).get("name")
        departments = raw.get("departments") or []
        offices = raw.get("offices") or []
        department = departments[0]["name"] if departments and departments[0].get("name") else None
        team = offices[0]["name"] if offices and offices[0].get("name") else None
        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{native_id}",
            id_kind=IdKind.NATIVE_ID,
            provider_native_id=native_id,
            provider_internal_id=str(raw["internal_job_id"]) if raw.get("internal_job_id") else None,
            requisition_id=str(raw["requisition_id"]) if raw.get("requisition_id") else None,
            title=norm_text(raw.get("title")),
            department=norm_text(department) or None,
            team=norm_text(team) or None,
            description_text=norm_text(raw.get("content")),
            posting_url=raw.get("absolute_url", ""),
            employment_type=EmploymentType.UNSPECIFIED,
            provider_updated_at=_iso(raw.get("updated_at")),
        )
        return self._finish_job(
            job, raw_location=location, explicit_workmode=None, stated_salary=None, now=now
        )


class LeverConnector(Connector):
    provider = Provider.LEVER

    def endpoint(self, board_token: str) -> str:
        return f"https://api.lever.co/v0/postings/{board_token}?mode=json"

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, list):
            raise ValueError("lever: expected a top-level list")
        for j in payload:
            if "id" not in j or "text" not in j:
                raise ValueError("lever: posting missing required id/text")
        return payload

    def map_job(self, source_id: str, raw: dict, *, now: datetime) -> CanonicalJob:
        native_id = str(raw["id"])
        categories = raw.get("categories") or {}
        location = categories.get("location")
        commitment = (categories.get("commitment") or "").lower()
        emp = EmploymentType.UNSPECIFIED
        if "full" in commitment:
            emp = EmploymentType.FULL_TIME
        elif "part" in commitment:
            emp = EmploymentType.PART_TIME
        elif "contract" in commitment:
            emp = EmploymentType.CONTRACT
        elif "intern" in commitment:
            emp = EmploymentType.INTERN
        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{native_id}",
            id_kind=IdKind.NATIVE_ID,
            provider_native_id=native_id,
            title=norm_text(raw.get("text")),
            department=norm_text(categories.get("department")) or None,
            team=norm_text(categories.get("team")) or None,
            description_text=norm_text(raw.get("descriptionPlain") or raw.get("description")),
            posting_url=raw.get("hostedUrl", ""),
            apply_url=raw.get("applyUrl"),
            employment_type=emp,
            provider_created_at=_epoch_ms(raw.get("createdAt")),  # evidence only, never authority
        )
        return self._finish_job(
            job,
            raw_location=location,
            explicit_workmode=raw.get("workplaceType"),
            stated_salary=None,
            now=now,
        )


class AshbyConnector(Connector):
    provider = Provider.ASHBY

    def endpoint(self, board_token: str) -> str:
        return (
            f"https://api.ashbyhq.com/posting-api/job-board/{board_token}"
            "?includeCompensation=true"
        )

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, dict) or "jobs" not in payload:
            raise ValueError("ashby: missing 'jobs' array")
        jobs = payload["jobs"]
        if not isinstance(jobs, list):
            raise ValueError("ashby: 'jobs' is not a list")
        for j in jobs:
            if "title" not in j:
                raise ValueError("ashby: posting missing required title")
        return [j for j in jobs if j.get("isListed", True)]

    def map_job(self, source_id: str, raw: dict, *, now: datetime) -> CanonicalJob:
        # Ashby has no documented native id. Ordered fallback: URL-slug UUID else content-hash.
        job_url = raw.get("jobUrl") or raw.get("applyUrl") or ""
        m = _ASHBY_UUID_RE.search(job_url)
        low_conf = False
        if m:
            provider_key = m.group(1)
            id_kind = IdKind.URL_SLUG
        else:
            fingerprint = "|".join([
                norm_text(raw.get("title")).lower(),
                norm_text(raw.get("department")).lower(),
                norm_text(raw.get("team")).lower(),
                norm_text(raw.get("location")).lower(),
                str(raw.get("employmentType", "")).lower(),
            ])
            provider_key = "ch_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
            id_kind = IdKind.CONTENT_HASH
            low_conf = True

        stated_salary = None
        comp = raw.get("compensation")
        if isinstance(comp, dict) and comp.get("compensationTierSummary"):
            stated_salary = SalaryStruct(source=SalarySource.STATED)

        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{provider_key}",
            id_kind=id_kind,
            provider_native_id=provider_key if id_kind == IdKind.URL_SLUG else None,
            identity_low_confidence=low_conf,
            title=norm_text(raw.get("title")),
            department=norm_text(raw.get("department")) or None,
            team=norm_text(raw.get("team")) or None,
            description_text=norm_text(raw.get("descriptionPlain") or raw.get("descriptionHtml")),
            posting_url=job_url,
            apply_url=raw.get("applyUrl"),
            provider_published_at=_iso(raw.get("publishedAt")),
        )
        return self._finish_job(
            job,
            raw_location=raw.get("location"),
            explicit_workmode=raw.get("workplaceType") or ("remote" if raw.get("isRemote") else None),
            stated_salary=stated_salary,
            now=now,
        )


_REGISTRY: dict[str, Connector] = {
    Provider.GREENHOUSE.value: GreenhouseConnector(),
    Provider.LEVER.value: LeverConnector(),
    Provider.ASHBY.value: AshbyConnector(),
}


def get_connector(provider: str) -> Connector:
    if provider == Provider.ASHBY.value and not ASHBY_ENABLED:
        raise RuntimeError(
            "ashby connector is feature-flagged OFF (UUID permanence unverified — D2/U4)"
        )
    if provider not in _REGISTRY:
        raise ValueError(f"unknown provider: {provider!r}")
    return _REGISTRY[provider]
