"""Shared golden-fixture builders. All synthetic; no live network anywhere."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.common.models import (
    CanonicalJob,
    IdKind,
    RemoteMode,
    SnapshotStatus,
    SourceSnapshot,
)
from src.common.normalize import (
    compute_hashes,
    detect_remote_mode,
    normalize_location,
    parse_salary,
)

SOURCE_ID = "greenhouse:acme"
FIXED_NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)


def make_job(
    key: str,
    *,
    source_id: str = SOURCE_ID,
    title: str = "Software Engineer",
    department: str | None = "engineering",
    team: str | None = None,
    description: str = "python aws serverless role",
    location: str = "Remote",
    salary_text: str | None = None,
    remote: str | None = None,
    requisition_id: str | None = None,
    id_kind: IdKind = IdKind.NATIVE_ID,
    identity_low_confidence: bool = False,
    fetched_at: datetime = FIXED_NOW,
) -> CanonicalJob:
    canonical_location = normalize_location(location)
    mode = detect_remote_mode(remote, location, description)
    salary = parse_salary(salary_text if salary_text is not None else description, None)
    content_hash, field_hashes = compute_hashes(
        title=title,
        canonical_location=canonical_location,
        salary=salary,
        remote_mode=mode,
        description_text=description,
        department=department,
        team=team,
        employment_type="UNSPECIFIED",
    )
    return CanonicalJob(
        source_id=source_id,
        job_id=f"{source_id}#{key}",
        id_kind=id_kind,
        provider_native_id=key,
        requisition_id=requisition_id,
        identity_low_confidence=identity_low_confidence,
        title=title,
        department=department,
        team=team,
        canonical_location=canonical_location,
        raw_location=location,
        remote_hybrid_language=mode,
        salary=salary,
        description_text=description,
        content_hash=content_hash,
        field_hashes=field_hashes,
        first_seen_at=fetched_at,
        last_seen_at=fetched_at,
    )


def make_snapshot(
    status: SnapshotStatus,
    *,
    source_id: str = SOURCE_ID,
    n: int | None = None,
    snapshot_id: str | None = None,
    fetched_at: datetime = FIXED_NOW,
) -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=snapshot_id or uuid.uuid4().hex,
        source_id=source_id,
        fetched_at=fetched_at,
        status=status,
        job_count_observed=n,
    )
