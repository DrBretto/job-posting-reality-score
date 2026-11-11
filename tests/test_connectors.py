"""Connector status-labeling + id-mapping tests (synthetic fixtures, no live network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.common.connectors import (
    AshbyConnector,
    FetchResult,
    GreenhouseConnector,
    LeverConnector,
    get_connector,
)
from src.common.models import IdKind, SnapshotStatus

NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _fr(payload=None, *, raw_bytes=None, http_status=200, error_class=None):
    if raw_bytes is None and payload is not None:
        raw_bytes = json.dumps(payload).encode()
    return FetchResult(
        raw_bytes=raw_bytes, http_status=http_status, error_class=error_class,
        endpoint_url="local://fixture", request_at=NOW, response_at=NOW,
    )


GH_JOB = {
    "id": 123, "internal_job_id": 456, "requisition_id": "R-9",
    "title": "Senior Python Engineer",
    "location": {"name": "Remote - US"},
    "content": "Build serverless data pipelines on AWS.",
    "departments": [{"name": "Engineering"}], "offices": [{"name": "HQ"}],
    "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
    "updated_at": "2026-07-19T00:00:00Z",
}


def test_greenhouse_success_and_native_id():
    snap, jobs = GreenhouseConnector().build_snapshot("acme", _fr({"jobs": [GH_JOB]}))
    assert snap.status == SnapshotStatus.SUCCESS
    assert len(jobs) == 1
    j = jobs[0]
    assert j.id_kind == IdKind.NATIVE_ID
    assert j.provider_native_id == "123"
    assert j.provider_internal_id == "456"
    assert j.requisition_id == "R-9"
    assert j.job_id == "greenhouse:acme#123"
    assert j.content_hash and j.field_hashes


def test_transport_failure_is_fetch_failed():
    snap, jobs = GreenhouseConnector().build_snapshot(
        "acme", _fr(raw_bytes=None, http_status=None, error_class="timeout")
    )
    assert snap.status == SnapshotStatus.FETCH_FAILED
    assert snap.error_class == "timeout"
    assert jobs == []


def test_malformed_200_is_partial():
    snap, jobs = GreenhouseConnector().build_snapshot("acme", _fr(raw_bytes=b"{not json"))
    assert snap.status == SnapshotStatus.PARTIAL
    assert snap.error_class == "parse_error"
    assert jobs == []


def test_schema_mismatch_is_partial():
    # 200 but missing the 'jobs' array -> schema validation fails -> PARTIAL, removals suppressed
    snap, jobs = GreenhouseConnector().build_snapshot("acme", _fr({"unexpected": []}))
    assert snap.status == SnapshotStatus.PARTIAL


def test_full_drop_guard_empty_after_nonempty_is_partial():
    snap, _ = GreenhouseConnector().build_snapshot("acme", _fr({"jobs": []}), prior_job_count=10)
    assert snap.status == SnapshotStatus.PARTIAL
    assert "full-drop" in (snap.notes or "")


def test_clean_empty_after_empty_is_empty_success():
    snap, _ = GreenhouseConnector().build_snapshot("acme", _fr({"jobs": []}), prior_job_count=0)
    assert snap.status == SnapshotStatus.EMPTY_SUCCESS


def test_lever_native_uuid_id():
    lever_job = {
        "id": "5ac21346-8e0c-4f00-9aaa-000000000001",
        "text": "Backend Engineer",
        "categories": {"location": "New York", "team": "Core", "department": "Eng",
                       "commitment": "Full-time"},
        "descriptionPlain": "python aws role",
        "hostedUrl": "https://jobs.lever.co/acme/uuid",
        "workplaceType": "remote",
        "createdAt": 1719800000000,
    }
    snap, jobs = LeverConnector().build_snapshot("acme", _fr([lever_job]))
    assert snap.status == SnapshotStatus.SUCCESS
    assert jobs[0].id_kind == IdKind.NATIVE_ID
    assert jobs[0].provider_native_id == "5ac21346-8e0c-4f00-9aaa-000000000001"
    # createdAt is evidence only, never authority
    assert jobs[0].provider_created_at is not None


def test_ashby_url_slug_uuid_vs_content_hash():
    conn = AshbyConnector()
    with_uuid = {
        "title": "ML Engineer",
        "jobUrl": "https://jobs.ashbyhq.com/acme/3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "department": "AI", "location": "Remote",
    }
    no_uuid = {"title": "ML Engineer", "jobUrl": "https://example.com/careers/ml", "department": "AI"}
    _, jobs_u = conn.build_snapshot("acme", _fr({"jobs": [with_uuid]}))
    _, jobs_c = conn.build_snapshot("acme", _fr({"jobs": [no_uuid]}))
    assert jobs_u[0].id_kind == IdKind.URL_SLUG
    assert jobs_u[0].identity_low_confidence is False
    assert jobs_c[0].id_kind == IdKind.CONTENT_HASH
    assert jobs_c[0].identity_low_confidence is True


def test_ashby_is_enabled_and_prefers_the_native_id():
    """The Ashby gate is OPEN and identity comes from the provider's own `id`.

    Evidence (bounded read-only probes, 2026-09-24): Ramp 155, OpenAI 828, Ashby 70, Linear 30 —
    1,083 postings, every one carrying a top-level UUID `id` that also terminates `jobUrl`. A Linear
    posting published 2021-04-27 is still listed under its original UUID, so the id survives years.
    """
    assert get_connector("ashby") is not None
    assert get_connector("greenhouse") is not None
    assert get_connector("lever") is not None

    posting = {
        "id": "34413f8d-26bf-4bbc-8ade-eb309a0e2245",
        "title": "Security Engineer, Cloud",
        "department": "Engineering", "team": "Backend",
        "employmentType": "FullTime", "location": "New York, NY (HQ)",
        "jobUrl": "https://jobs.ashbyhq.com/Ramp/34413f8d-26bf-4bbc-8ade-eb309a0e2245",
        "applyUrl": "https://jobs.ashbyhq.com/Ramp/34413f8d-26bf-4bbc-8ade-eb309a0e2245/application",
        "descriptionPlain": "Own cloud security engineering.",
        "secondaryLocations": [{"location": "Remote (US)"}],
        "compensation": {"compensationTierSummary": "$198K - $233K"},
    }
    _snap, jobs = AshbyConnector().build_snapshot("Ramp", _fr({"jobs": [posting]}),
                                                 employer_name="Ramp")
    job = jobs[0]
    assert job.id_kind == IdKind.NATIVE_ID
    assert job.provider_native_id == "34413f8d-26bf-4bbc-8ade-eb309a0e2245"
    assert job.identity_low_confidence is False
    assert job.employer_name == "Ramp"
    # Published compensation is kept; a location-eligibility variant is kept separately so dedup
    # cannot collapse two genuinely different openings.
    assert job.salary is not None and job.salary.min == 198000
    assert job.secondary_locations == ["Remote (US)"]


def test_ashby_identity_ladder_degrades_honestly():
    """With no native id, fall back to the URL UUID, then to a low-confidence content hash."""
    conn = AshbyConnector()
    url_only = {
        "title": "ML Engineer",
        "jobUrl": "https://jobs.ashbyhq.com/acme/3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "department": "AI",
    }
    neither = {"title": "ML Engineer", "jobUrl": "https://example.com/careers/ml", "department": "AI"}
    _s1, j1 = conn.build_snapshot("acme", _fr({"jobs": [url_only]}))
    _s2, j2 = conn.build_snapshot("acme", _fr({"jobs": [neither]}))
    assert j1[0].id_kind == IdKind.URL_SLUG and j1[0].identity_low_confidence is False
    assert j2[0].id_kind == IdKind.CONTENT_HASH and j2[0].identity_low_confidence is True
