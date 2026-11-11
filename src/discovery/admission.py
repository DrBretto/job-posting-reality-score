"""Source growth: how a discovered employer becomes a monitored source, safely.

The plan's requirement is blunt: source registration must grow through validated discoveries under a
documented admission policy, "without editing a 15-company YAML list by hand every morning". The
equally blunt constraint is that **observation is not permission to collect**.

So this module keeps two things strictly apart:

  OBSERVED    we saw this employer in a discovery result. We have collected nothing from them and
              we have no right to. This is a note, not a source.
  ADMITTED    the employer's public board passed every gate below and is now monitored.

Between them sits the policy. An employer that fails it is not thrown away — a real lead whose ATS
has no connector becomes QUEUED_UNSUPPORTED and stays visible to the operator, because discarding a
good opportunity for an infrastructure reason is the failure this system is supposed to prevent.

An operator disable is STICKY. Rediscovering a disabled employer tomorrow does not re-admit it; that
is what keeps a growth loop from overriding a human decision.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.common.models import AdmissionState, Provider
from src.common.normalize import normalize_employer, url_host

# Careers-URL patterns that identify a supported public board and its token. Derived from the
# EMPLOYER'S OWN careers URL — never guessed from a company name, because guessing a board token
# produces confident nonsense (and a 404 storm against someone else's board).
_BOARD_PATTERNS: tuple[tuple[Provider, re.Pattern[str]], ...] = (
    (Provider.GREENHOUSE, re.compile(
        r"^https?://(?:www\.)?(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?"
        r"([A-Za-z0-9_-]+)", re.I)),
    (Provider.GREENHOUSE, re.compile(
        r"^https?://boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)", re.I)),
    (Provider.LEVER, re.compile(r"^https?://jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_-]+)", re.I)),
    (Provider.ASHBY, re.compile(r"^https?://jobs\.ashbyhq\.com/([^/?#]+)", re.I)),
)

# Hosts that are aggregators, not employers. Their URLs must never be read as a board token.
_AGGREGATOR_HOSTS = frozenset({
    "remotive.com", "remoteok.com", "jobicy.com", "himalayas.app", "adzuna.com",
    "news.ycombinator.com",
    "www.adzuna.com", "api.adzuna.com", "linkedin.com", "www.linkedin.com",
    "indeed.com", "www.indeed.com", "glassdoor.com", "ziprecruiter.com", "monster.com",
    "arbeitnow.com", "www.arbeitnow.com",
})


class CandidateSource(BaseModel):
    """A discovered employer, with the evidence that discovered it."""

    model_config = ConfigDict(extra="forbid")
    employer_name: str
    employer_key: str                      # normalized, the dedup/identity key
    state: AdmissionState = AdmissionState.OBSERVED
    provider: Provider | None = None       # supported board family, when one was detected
    board_token: str | None = None
    careers_url: str | None = None
    # evidence: how we learned about them
    discovered_via_source_id: str | None = None
    discovered_via_query: str | None = None
    discovered_via_job_id: str | None = None
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    observation_count: int = 1
    # decision record
    decision_reason: str | None = None
    failed_gates: list[str] = Field(default_factory=list)
    admitted_at: datetime | None = None


class SourceRegistryGrowth(BaseModel):
    """Persisted growth ledger. Never mutated mid-run by the collector (plan §5)."""

    model_config = ConfigDict(extra="forbid")
    candidates: dict[str, CandidateSource] = Field(default_factory=dict)
    # Sticky operator decisions, keyed by employer_key. These outrank any rediscovery.
    operator_disabled: list[str] = Field(default_factory=list)

    def get(self, employer_key: str) -> CandidateSource | None:
        return self.candidates.get(employer_key)


def detect_board(careers_url: str | None) -> tuple[Provider, str] | None:
    """Resolve a supported board family + token from the employer's own careers URL.

    Returns None for an aggregator host or an unrecognized ATS — both of which are fine, they just
    mean "monitoring cannot follow up automatically", not "discard the lead".
    """
    if not careers_url:
        return None
    host = url_host(careers_url)
    if host and host in _AGGREGATOR_HOSTS:
        return None
    for provider, pattern in _BOARD_PATTERNS:
        m = pattern.match(careers_url.strip())
        if m:
            token = m.group(1)
            # Ashby board slugs are URL-encoded when they contain spaces.
            from urllib.parse import unquote

            token = unquote(token)
            if token and token.lower() not in ("job", "jobs", "embed", "www"):
                return provider, token
    return None


def observe(
    growth: SourceRegistryGrowth,
    *,
    employer_name: str,
    now: datetime,
    source_id: str | None = None,
    query: str | None = None,
    job_id: str | None = None,
    careers_url: str | None = None,
) -> CandidateSource:
    """Record a sighting. Grants NO collection rights — that is the whole point of the split."""
    key = normalize_employer(employer_name)
    existing = growth.candidates.get(key)
    if existing is None:
        detected = detect_board(careers_url)
        existing = CandidateSource(
            employer_name=employer_name,
            employer_key=key,
            state=AdmissionState.OBSERVED,
            provider=detected[0] if detected else None,
            board_token=detected[1] if detected else None,
            careers_url=careers_url,
            discovered_via_source_id=source_id,
            discovered_via_query=query,
            discovered_via_job_id=job_id,
            first_observed_at=now,
            last_observed_at=now,
            observation_count=1,
        )
        growth.candidates[key] = existing
    else:
        existing.observation_count += 1
        existing.last_observed_at = now
        if careers_url and not existing.careers_url:
            existing.careers_url = careers_url
            detected = detect_board(careers_url)
            if detected:
                existing.provider, existing.board_token = detected
    # A sticky operator disable is re-asserted on every sighting, so rediscovery cannot quietly
    # resurrect something the operator turned off.
    if key in growth.operator_disabled:
        existing.state = AdmissionState.OPERATOR_DISABLED
        existing.decision_reason = "operator disabled this source; sticky across rediscovery"
    return existing


# --------------------------------------------------------------------------------------------------
# The admission policy
# --------------------------------------------------------------------------------------------------
class AdmissionPolicy(BaseModel):
    """Documented, inspectable gates. Changing a number here changes the policy, visibly."""

    model_config = ConfigDict(extra="forbid")
    # A single sighting can be noise or a mis-parse; require corroboration before we start hitting
    # someone's board on a schedule.
    min_observations: int = 1
    require_supported_board: bool = True
    require_public_scope: bool = True
    # Total monitored sources we are willing to fetch per run. A growth loop with no ceiling
    # eventually turns into an unbudgeted crawler.
    max_monitored_sources: int = 60
    max_admissions_per_run: int = 10


def evaluate(
    candidate: CandidateSource,
    policy: AdmissionPolicy,
    *,
    growth: SourceRegistryGrowth,
    monitored_count: int,
    admissions_this_run: int,
    now: datetime,
) -> CandidateSource:
    """Apply every gate and record the outcome with its reasons. Pure; mutates only `candidate`."""
    if candidate.employer_key in growth.operator_disabled:
        candidate.state = AdmissionState.OPERATOR_DISABLED
        candidate.decision_reason = "operator disabled this source; sticky across rediscovery"
        return candidate
    if candidate.state == AdmissionState.ADMITTED:
        return candidate

    failed: list[str] = []

    # Gate 1 — public scope + a supported public board, resolved from the employer's own URL.
    detected = (candidate.provider, candidate.board_token) if candidate.board_token else None
    if policy.require_supported_board and not detected:
        failed.append("no_supported_public_board_detected")

    # Gate 2 — host safety. The board host must be one we already vet at build time; a runtime host
    # would have to go through the fetch guard instead, which is the careers-page path, not this one.
    if detected:
        from src.common.connectors import HOST_ALLOWLIST

        host = url_host(candidate.careers_url)
        if host and host in _AGGREGATOR_HOSTS:
            failed.append("careers_url_is_an_aggregator_not_the_employer")
        board_host_ok = candidate.provider in (
            Provider.GREENHOUSE, Provider.LEVER, Provider.ASHBY
        ) and any(h for h in HOST_ALLOWLIST)
        if not board_host_ok:
            failed.append("board_family_not_on_build_time_allowlist")

    # Gate 3 — corroboration.
    if candidate.observation_count < policy.min_observations:
        failed.append(
            f"only_{candidate.observation_count}_observation(s)_need_{policy.min_observations}"
        )

    # Gate 4 — resource limits. Deferral, not rejection: the candidate stays eligible for a later run.
    if monitored_count >= policy.max_monitored_sources:
        candidate.state = AdmissionState.ELIGIBLE
        candidate.failed_gates = []
        candidate.decision_reason = (
            f"passes policy but monitored-source ceiling reached "
            f"({monitored_count}/{policy.max_monitored_sources}); deferred, not rejected"
        )
        return candidate
    if admissions_this_run >= policy.max_admissions_per_run:
        candidate.state = AdmissionState.ELIGIBLE
        candidate.failed_gates = []
        candidate.decision_reason = (
            f"passes policy but per-run admission cap reached "
            f"({policy.max_admissions_per_run}); deferred to the next run"
        )
        return candidate

    if failed:
        # An unsupported board is a QUEUE, not a bin: the lead stays visible to the operator.
        only_unsupported = failed == ["no_supported_public_board_detected"]
        candidate.state = (
            AdmissionState.QUEUED_UNSUPPORTED if only_unsupported else AdmissionState.REJECTED
        )
        candidate.failed_gates = failed
        candidate.decision_reason = (
            "no connector for this employer's posting page; kept as a verification-queue lead so "
            "the opportunity stays visible"
            if only_unsupported else
            "failed admission gates: " + ", ".join(failed)
        )
        return candidate

    candidate.state = AdmissionState.ADMITTED
    candidate.failed_gates = []
    candidate.admitted_at = now
    candidate.decision_reason = (
        f"admitted: {candidate.provider.value if candidate.provider else '?'} board "
        f"{candidate.board_token!r} resolved from the employer's own careers URL; "
        f"{candidate.observation_count} observation(s)"
    )
    return candidate


def admit_pass(
    growth: SourceRegistryGrowth,
    policy: AdmissionPolicy,
    *,
    monitored_count: int,
    now: datetime,
) -> dict:
    """Evaluate every candidate once. Returns an operator-readable summary of what changed."""
    admitted_now = 0
    for candidate in sorted(
        growth.candidates.values(),
        key=lambda c: (-c.observation_count, c.employer_key),
    ):
        before = candidate.state
        evaluate(
            candidate, policy, growth=growth,
            monitored_count=monitored_count + admitted_now,
            admissions_this_run=admitted_now, now=now,
        )
        if candidate.state == AdmissionState.ADMITTED and before != AdmissionState.ADMITTED:
            admitted_now += 1

    by_state: dict[str, list[str]] = {}
    for candidate in growth.candidates.values():
        by_state.setdefault(candidate.state.value, []).append(candidate.employer_name)
    return {
        "admitted_this_pass": admitted_now,
        "by_state": {k: sorted(v) for k, v in sorted(by_state.items())},
        "monitored_after": monitored_count + admitted_now,
        "policy": policy.model_dump(mode="json"),
    }


def proposed_registry_entries(growth: SourceRegistryGrowth) -> list[dict]:
    """Admitted candidates rendered as registry rows.

    Returned for the operator to apply — this function does NOT write the production registry, and
    nothing here mutates an active registry mid-run.
    """
    out = []
    for candidate in sorted(growth.candidates.values(), key=lambda c: c.employer_key):
        if candidate.state != AdmissionState.ADMITTED or not candidate.provider:
            continue
        out.append({
            "provider": candidate.provider.value,
            "board_token": candidate.board_token,
            "company_slug": candidate.employer_key.replace(" ", "-") or candidate.board_token,
            "enabled": True,
            "_admission_evidence": {
                "employer_name": candidate.employer_name,
                "careers_url": candidate.careers_url,
                "discovered_via_source_id": candidate.discovered_via_source_id,
                "discovered_via_query": candidate.discovered_via_query,
                "observations": candidate.observation_count,
                "admitted_at": candidate.admitted_at.isoformat() if candidate.admitted_at else None,
            },
        })
    return out
