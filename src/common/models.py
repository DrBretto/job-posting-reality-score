"""Pydantic models + enums for JPRS (per DATA_MODEL_AND_HISTORY_SPEC + SCORING_AND_EVIDENCE_SPEC).

Every model is shaped to make the disappearance invariant structurally enforceable: the pivot is
`SourceSnapshot.status`, which the differ is forbidden by contract to compute removals from unless
it is SUCCESS/EMPTY_SUCCESS.

`schema_v` is stamped on canonical records and change-events so version-scoped replay is a clean
key-prefix operation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# Current schema version. Minor = additive; major = shape/hash-definition change (forces replay).
SCHEMA_VERSION = "1.0.0"
NORMALIZER_VERSION = "1.0.0"
CONNECTOR_VERSION = "1.0.0"


# --------------------------------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------------------------------
class Provider(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"


class SnapshotStatus(str, Enum):
    SUCCESS = "SUCCESS"              # full, well-formed, complete
    PARTIAL = "PARTIAL"             # received but truncated/unparseable/full-drop-guarded
    FETCH_FAILED = "FETCH_FAILED"   # network/timeout/5xx/429/DNS — NO usable job list
    EMPTY_SUCCESS = "EMPTY_SUCCESS"  # valid 200, genuinely empty board


# statuses the differ is allowed to compute removals from
SUCCESSFUL_STATUSES = frozenset({SnapshotStatus.SUCCESS, SnapshotStatus.EMPTY_SUCCESS})
# statuses that FREEZE all job state and suppress removals
FROZEN_STATUSES = frozenset({SnapshotStatus.FETCH_FAILED, SnapshotStatus.PARTIAL})


class IdKind(str, Enum):
    NATIVE_ID = "NATIVE_ID"
    URL_SLUG = "URL_SLUG"
    CONTENT_HASH = "CONTENT_HASH"


class RemoteMode(str, Enum):
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ONSITE = "ONSITE"
    UNSPECIFIED = "UNSPECIFIED"


class EmploymentType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERN = "INTERN"
    TEMP = "TEMP"
    UNSPECIFIED = "UNSPECIFIED"


class SalarySource(str, Enum):
    STATED = "STATED"
    PARSED = "PARSED"
    NONE = "NONE"


class JobLifecycleState(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING_REMOVAL = "PENDING_REMOVAL"
    DISAPPEARED = "DISAPPEARED"


class ChangeEventType(str, Enum):
    FIRST_SEEN = "first-seen"
    NO_MATERIAL_CHANGE = "no-material-change"
    MATERIALLY_CHANGED = "materially-changed"
    LOCATION_CHANGED = "location-changed"
    SALARY_CHANGED = "salary-changed"
    REMOTE_HYBRID_LANGUAGE_CHANGED = "remote-hybrid-language-changed"
    DISAPPEARED = "disappeared"
    RETURNED = "returned"
    PROBABLE_REPOST = "probable-repost"
    # source-scoped (never job-scoped) — how the quiet report says "collectors ran incompletely"
    SOURCE_FETCH_FAILED = "source-fetch-failed"
    SOURCE_RESPONSE_PARTIAL = "source-response-partial"
    SOURCE_SUSPECT = "source-suspect"  # mass-drop / cumulative-bleed / silent-subset guard tripped


class Band(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class EvidenceKind(str, Enum):
    SNAPSHOT = "SNAPSHOT"
    CHANGE_EVENT = "CHANGE_EVENT"
    CANONICAL_FIELD = "CANONICAL_FIELD"
    OUTCOME_EVENT = "OUTCOME_EVENT"


class RunHealth(str, Enum):
    VERIFIED_QUIET = "VERIFIED-QUIET"
    INCOMPLETE = "INCOMPLETE"
    NO_RUN = "NO-RUN"


# --------------------------------------------------------------------------------------------------
# Value objects
# --------------------------------------------------------------------------------------------------
class SalaryStruct(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min: float | None = None
    max: float | None = None
    currency: str | None = None
    period: str | None = None
    source: SalarySource = SalarySource.NONE


class SourceReceipt(BaseModel):
    """Provenance stamp — every snapshot (success or failure) writes one."""

    model_config = ConfigDict(extra="forbid")
    provider: Provider
    endpoint_url: str
    request_at: datetime
    response_at: datetime
    http_status: int | None = None
    etag: str | None = None
    content_length: int | None = None
    connector_version: str = CONNECTOR_VERSION
    raw_sha256: str


class SourceSnapshot(BaseModel):
    """The fetch envelope — the object the disappearance rule keys on."""

    model_config = ConfigDict(extra="forbid")
    snapshot_id: str
    source_id: str
    fetched_at: datetime
    status: SnapshotStatus
    http_status: int | None = None
    job_count_observed: int | None = None
    bytes: int | None = None
    raw_object_key: str | None = None
    request_receipt: SourceReceipt | None = None
    error_class: str | None = None
    notes: str | None = None
    schema_version: str = SCHEMA_VERSION


class CanonicalJob(BaseModel):
    """Normalized, provider-agnostic posting — the diff/score surface."""

    model_config = ConfigDict(extra="forbid")
    # identity
    source_id: str
    job_id: str
    id_kind: IdKind
    provider_native_id: str | None = None
    provider_internal_id: str | None = None
    requisition_id: str | None = None
    identity_low_confidence: bool = False

    # content (canonical)
    title: str
    department: str | None = None
    team: str | None = None
    canonical_location: str = ""
    raw_location: str | None = None
    remote_hybrid_language: RemoteMode = RemoteMode.UNSPECIFIED
    employment_type: EmploymentType = EmploymentType.UNSPECIFIED
    salary: SalaryStruct | None = None
    description_text: str = ""
    posting_url: str = ""
    apply_url: str | None = None

    # provider-supplied timing (evidence only, never authority for "first seen")
    provider_created_at: datetime | None = None
    provider_updated_at: datetime | None = None
    provider_published_at: datetime | None = None

    # our derived timing (authoritative)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

    # hashing
    content_hash: str = ""
    field_hashes: dict[str, str] = Field(default_factory=dict)

    # meta
    schema_version: str = SCHEMA_VERSION
    normalizer_version: str = NORMALIZER_VERSION
    ingested_snapshot_id: str | None = None


class ChangeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    event_type: ChangeEventType
    source_id: str
    job_id: str | None = None            # None for source-scoped events
    run_id: str
    as_of: datetime
    snapshot_id: str
    prior_snapshot_id: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    # repost linkage
    linked_job_id: str | None = None
    repost_score: float | None = None
    notes: str | None = None
    schema_version: str = SCHEMA_VERSION


class EvidenceRef(BaseModel):
    """The anti-hallucination spine: no score field exists without a pointer to stored evidence."""

    model_config = ConfigDict(extra="forbid")
    kind: EvidenceKind
    ref_id: str
    as_of: datetime | None = None


class DimensionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float | None                 # None when band == UNKNOWN
    band: Band
    confidence: float
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    version: str
    detail: dict[str, float | int | str | None] = Field(default_factory=dict)


class DimensionScorecard(BaseModel):
    """Independent, individually-explainable sub-scores. No single opaque number."""

    model_config = ConfigDict(extra="forbid")
    source_id: str
    job_id: str
    brett_fit: DimensionScore
    freshness: DimensionScore
    hiring_activity_evidence: DimensionScore
    repost_churn_pattern: DimensionScore
    source_data_confidence: DimensionScore
    application_priority: DimensionScore
    scoring_profile_version: str
    scored_as_of: datetime
    excluded: bool = False
    exclusion_reason: str | None = None
