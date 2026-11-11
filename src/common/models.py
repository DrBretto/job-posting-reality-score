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
# 1.1.0 (open-market discovery): additive only. Employer moves from a property of the SOURCE to a
# property of the JOB, plus discovery/verification/provenance fields. Same major => same S3 prefix,
# so no replay is required and records written under 1.0.0 load with these fields at their defaults.
SCHEMA_VERSION = "1.1.0"
NORMALIZER_VERSION = "1.1.0"
CONNECTOR_VERSION = "1.1.0"


# --------------------------------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------------------------------
class Provider(str, Enum):
    # --- employer-keyed ATS board monitoring (one source == one known employer) ---
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    # --- employer-independent discovery (one source == many employers, unknown in advance) ---
    REMOTIVE = "remotive"
    REMOTEOK = "remoteok"
    JOBICY = "jobicy"
    HIMALAYAS = "himalayas"
    ADZUNA = "adzuna"
    # Founder- and employer-written posts in the monthly Hacker News "Who is hiring?" thread.
    HN_HIRING = "hn_hiring"
    # --- operator-assisted / unsupported-page paths ---
    MANUAL = "manual"
    CAREERS_PAGE = "careers_page"


class SourceKind(str, Enum):
    """Which capability a source serves.

    The whole point of the overhaul: an ATS_BOARD can only ever answer "what is open at THIS
    employer", so it structurally cannot surface an employer nobody has named yet. A
    DISCOVERY_FEED is keyed by a question about work, so it can.
    """

    ATS_BOARD = "ATS_BOARD"
    DISCOVERY_FEED = "DISCOVERY_FEED"
    MANUAL_IMPORT = "MANUAL_IMPORT"
    CAREERS_PAGE = "CAREERS_PAGE"


# Providers that are employer-independent discovery feeds.
DISCOVERY_PROVIDERS = frozenset({
    Provider.REMOTIVE, Provider.REMOTEOK, Provider.JOBICY, Provider.HIMALAYAS, Provider.ADZUNA,
    Provider.HN_HIRING,
})
# Providers that monitor exactly one known employer's board.
ATS_PROVIDERS = frozenset({Provider.GREENHOUSE, Provider.LEVER, Provider.ASHBY})


class VerificationState(str, Enum):
    """How much we actually confirmed, kept visible rather than collapsed into "a job".

    Aggregator snippets are leads. Saying otherwise is the failure the plan forbids.
    """

    UNVERIFIED_LEAD = "UNVERIFIED_LEAD"        # snippet/summary only; description not full
    FEED_COMPLETE = "FEED_COMPLETE"            # provider returned a complete description
    EMPLOYER_CONFIRMED = "EMPLOYER_CONFIRMED"  # confirmed against the employer/authorized posting


class HistoryStatus(str, Enum):
    """Application history states. These are NOT interchangeable.

    A prepared package, a tailored resume file, or an application folder is PREPARED and nothing
    stronger. JPRS reads history and never writes it, so it can never invent a SUBMITTED.
    """

    NEW = "NEW"
    PREPARED = "PREPARED"      # materials exist; no submission evidence
    SUBMITTED = "SUBMITTED"    # explicit submission evidence
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"


class ScreenOutcome(str, Enum):
    """Screening verdict. UNKNOWN is a first-class third state, never a silent pass or reject."""

    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"
    PENDING_CHECK = "PENDING_CHECK"


class AdmissionState(str, Enum):
    """Lifecycle of a discovered source. Observation is not permission to collect."""

    OBSERVED = "OBSERVED"                    # seen in a discovery result; no collection rights
    ELIGIBLE = "ELIGIBLE"                    # passes the admission policy
    ADMITTED = "ADMITTED"                    # monitored
    QUEUED_UNSUPPORTED = "QUEUED_UNSUPPORTED"  # real lead, no connector — verification queue
    REJECTED = "REJECTED"                    # failed the admission policy
    OPERATOR_DISABLED = "OPERATOR_DISABLED"  # sticky; survives rediscovery


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
    # A prior-present segment stayed absent across enough independent healthy SUCCESS snapshots to
    # corroborate real closure. This is what releases the silent-subset latch: without it, a
    # department that genuinely closed freezes its jobs ACTIVE forever and repeats the warning.
    SOURCE_SEGMENT_CLOSED = "source-segment-closed"
    # Discovery ran but could not cover its whole query plan this run (budget/pagination/limits).
    # Coverage is incomplete AND resumable; this is never phrased as "nothing more to find".
    SOURCE_DISCOVERY_PARTIAL = "source-discovery-partial"


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


class JobProvenance(BaseModel):
    """One source's sighting of a posting.

    Cross-source dedup keeps every sighting instead of discarding the losers, so "we also saw this
    on X" survives and a wrong merge stays diagnosable.
    """

    model_config = ConfigDict(extra="forbid")
    source_id: str
    provider: Provider
    job_id: str
    posting_url: str | None = None
    observed_at: datetime | None = None
    discovery_query: str | None = None


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

    # --- employer (1.1.0) ------------------------------------------------------------------------
    # Authoritative on the JOB, not on the source. An ATS board fills this from its single known
    # employer; a discovery feed fills it from the record, which is the only reason an employer
    # nobody has named yet can arrive at all.
    employer_name: str = ""
    employer_domain: str | None = None
    employer_careers_url: str | None = None

    # content (canonical)
    title: str
    department: str | None = None
    team: str | None = None
    canonical_location: str = ""
    raw_location: str | None = None
    # Location-eligibility variants, kept separate. Two postings differing only here are DIFFERENT
    # opportunities and must not be collapsed by dedup.
    secondary_locations: list[str] = Field(default_factory=list)
    remote_hybrid_language: RemoteMode = RemoteMode.UNSPECIFIED
    employment_type: EmploymentType = EmploymentType.UNSPECIFIED
    salary: SalaryStruct | None = None
    description_text: str = ""
    # Native provider text preserved alongside the safely normalized text (plan §3). Normalization
    # strips markup; screening sometimes needs what the employer actually wrote.
    description_native: str = ""
    industry: str | None = None
    job_level: str | None = None
    posting_url: str = ""
    apply_url: str | None = None
    apply_host: str | None = None

    # --- discovery lineage (1.1.0) ---------------------------------------------------------------
    source_kind: SourceKind = SourceKind.ATS_BOARD
    discovery_query: str | None = None          # the exact query text that surfaced this posting
    discovery_query_family: str | None = None   # which query family it belonged to

    # --- verification (1.1.0) -------------------------------------------------------------------
    verification_state: VerificationState = VerificationState.FEED_COMPLETE
    verified_at: datetime | None = None         # last time we confirmed against the employer
    # Free-text, machine-greppable uncertainty markers. Present uncertainty beats absent certainty.
    uncertainty: list[str] = Field(default_factory=list)

    # provider-supplied timing (evidence only, never authority for "first seen").
    # These four are NOT interchangeable and an old imported job is never called newly posted:
    #   provider_published_at -> when the employer says it went live
    #   provider_updated_at   -> when the employer last edited it
    #   first_seen_at         -> when WE first observed it in a SUCCESS snapshot
    #   last_seen_at          -> when WE last observed it
    provider_created_at: datetime | None = None
    provider_updated_at: datetime | None = None
    provider_published_at: datetime | None = None

    # our derived timing (authoritative)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

    # --- cross-source dedup (1.1.0) -------------------------------------------------------------
    provenance: list[JobProvenance] = Field(default_factory=list)
    dedup_group_id: str | None = None
    # Hard merge: same canonical apply target. The absorbed row's sighting lives in `provenance`.
    duplicate_of: str | None = None
    # Soft match: same employer/title/location but not provably the same requisition. BOTH rows
    # survive and are cross-linked for review — ambiguity is never resolved by deletion.
    possible_duplicate_of: list[str] = Field(default_factory=list)

    # hashing
    content_hash: str = ""
    field_hashes: dict[str, str] = Field(default_factory=dict)

    # meta
    schema_version: str = SCHEMA_VERSION
    normalizer_version: str = NORMALIZER_VERSION
    ingested_snapshot_id: str | None = None

    @property
    def display_employer(self) -> str:
        """Employer for human surfaces. Falls back to the source's board token, never to a
        hardcoded label table."""
        if self.employer_name:
            return self.employer_name
        return self.source_id.partition(":")[2] or self.source_id


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
