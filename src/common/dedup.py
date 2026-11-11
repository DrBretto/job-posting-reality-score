"""Cross-source deduplication that never loses an opportunity.

Discovery means the same requisition can arrive from four feeds plus the employer's own board. Naive
dedup on employer+title would collapse genuinely different openings — the corpus contains one
employer with two live requisitions whose titles differ only by their suffix — and silently deleting
one of those is worse than showing a duplicate.

So there are two tiers, and only one of them merges:

  HARD merge   identical canonical apply/posting target. Same URL, same requisition, full stop. The
               absorbed row's sighting is appended to the survivor's `provenance`, so "we also saw
               this on Remote OK" is preserved and a wrong merge stays diagnosable.

  SOFT link    same employer, same normalized title, same location — but no proof it is the same
               requisition. BOTH rows survive, cross-linked through `possible_duplicate_of`. The
               operator sees "these two may be the same posting"; the system does not decide.

Blockers that prevent even a soft link, because each one marks a genuinely different opportunity:
  - different non-empty `requisition_id`
  - different location-eligibility variant sets
  - different apply hosts when both are the employer's own ATS

Preference when merging: the record that is closest to the employer wins, because it is the one whose
description and process we can actually trust.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from src.common.models import (
    ATS_PROVIDERS,
    CanonicalJob,
    JobProvenance,
    Provider,
    SourceKind,
    VerificationState,
)
from src.common.normalize import canonical_url, normalize_employer, normalize_title_for_matching

# How much we trust a record's own account of itself. Higher wins a hard merge.
_VERIFICATION_RANK = {
    VerificationState.EMPLOYER_CONFIRMED: 3,
    VerificationState.FEED_COMPLETE: 2,
    VerificationState.UNVERIFIED_LEAD: 1,
}
_SOURCE_KIND_RANK = {
    SourceKind.ATS_BOARD: 3,       # the employer's own board
    SourceKind.CAREERS_PAGE: 2,
    SourceKind.DISCOVERY_FEED: 1,
    SourceKind.MANUAL_IMPORT: 1,
}


@dataclass
class DedupReport:
    groups: int = 0
    hard_merges: int = 0
    soft_links: int = 0
    blocked_links: list[str] = field(default_factory=list)
    survivors: int = 0
    absorbed: int = 0

    def to_json(self) -> dict:
        return {
            "dedup_groups": self.groups,
            "hard_merges": self.hard_merges,
            "soft_possible_duplicate_links": self.soft_links,
            "links_blocked_as_distinct_requisitions": len(self.blocked_links),
            "blocked_examples": self.blocked_links[:10],
            "records_kept": self.survivors,
            "records_absorbed_into_a_survivor": self.absorbed,
        }


def _location_signature(job: CanonicalJob) -> str:
    parts = [job.canonical_location or ""] + sorted(
        normalize_employer(loc) for loc in job.secondary_locations
    )
    return "|".join(parts)


def hard_key(job: CanonicalJob) -> str | None:
    """Canonical apply target. Identical value == provably the same posting."""
    target = canonical_url(job.apply_url) or canonical_url(job.posting_url)
    return target or None


def _group_id(hard: str) -> str:
    """Stable group id for a hard key.

    Hashed, not truncated. Slicing the raw URL made every posting on one ATS host collide into a
    single group id (`https://jobs.ashbyhq`), and because the soft pass skips pairs that share a
    group id, two genuinely different openings were silently never compared — so the report could
    not explain why both were listed.
    """
    return hashlib.sha256(hard.encode()).hexdigest()[:20]


def soft_key(job: CanonicalJob) -> str:
    """employer + normalized title + PRIMARY location. A CANDIDATE for sameness, not a verdict.

    Deliberately loose: it groups postings that are worth comparing, and `_distinct_reason` then
    decides. Folding the location-eligibility variants into this key instead would separate such a
    pair silently — they would still both survive, but the report could not explain *why* there are
    two rows for one employer and title, and an unexplained duplicate is what makes an operator
    stop trusting the list.
    """
    raw = "|".join((
        normalize_employer(job.employer_name) or job.source_id,
        normalize_title_for_matching(job.title),
        job.canonical_location or "",
    ))
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _trust(job: CanonicalJob) -> tuple[int, int, int, str]:
    provider = job.source_id.partition(":")[0]
    is_ats = provider in {p.value for p in ATS_PROVIDERS}
    return (
        _SOURCE_KIND_RANK.get(job.source_kind, 0),
        _VERIFICATION_RANK.get(job.verification_state, 0),
        1 if is_ats else 0,
        job.job_id,          # final tie-break keeps the result deterministic
    )


def _sighting(job: CanonicalJob) -> JobProvenance:
    provider_value = job.source_id.partition(":")[0]
    try:
        provider = Provider(provider_value)
    except ValueError:
        provider = Provider.MANUAL
    return JobProvenance(
        source_id=job.source_id,
        provider=provider,
        job_id=job.job_id,
        posting_url=job.posting_url or job.apply_url,
        observed_at=job.last_seen_at,
        discovery_query=job.discovery_query,
    )


def _distinct_reason(a: CanonicalJob, b: CanonicalJob) -> str | None:
    """Why these two must NOT be linked, even softly."""
    if a.requisition_id and b.requisition_id and a.requisition_id != b.requisition_id:
        return (
            f"different requisition ids ({a.requisition_id} vs {b.requisition_id}) — distinct "
            f"openings at {a.display_employer}"
        )
    if _location_signature(a) != _location_signature(b):
        return (
            f"different location-eligibility variants for {a.display_employer} — "
            f"{_location_signature(a)!r} vs {_location_signature(b)!r}"
        )
    a_provider = a.source_id.partition(":")[0]
    b_provider = b.source_id.partition(":")[0]
    ats = {p.value for p in ATS_PROVIDERS}
    if a_provider in ats and b_provider in ats and a.apply_host and b.apply_host:
        if a.apply_host != b.apply_host:
            return (
                f"two employer-owned boards with different apply hosts "
                f"({a.apply_host} vs {b.apply_host})"
            )
    return None


def deduplicate(
    jobs: list[CanonicalJob], *, now: datetime | None = None
) -> tuple[list[CanonicalJob], DedupReport]:
    """Merge provable duplicates, cross-link probable ones, delete nothing.

    Returns (kept_jobs, report). Input objects are mutated in place with provenance and links, which
    is what carries the merge evidence downstream into the report.
    """
    report = DedupReport()

    # ---- tier 1: hard merge on the canonical apply target ---------------------------------------
    by_hard: dict[str, list[CanonicalJob]] = {}
    unkeyed: list[CanonicalJob] = []
    for job in jobs:
        key = hard_key(job)
        if key is None:
            unkeyed.append(job)
        else:
            by_hard.setdefault(key, []).append(job)

    kept: list[CanonicalJob] = []
    for key, bucket in by_hard.items():
        if len(bucket) == 1:
            job = bucket[0]
            if not job.provenance:
                job.provenance = [_sighting(job)]
            job.dedup_group_id = _group_id(key)
            kept.append(job)
            continue
        winner = max(bucket, key=_trust)
        winner.dedup_group_id = _group_id(key)
        seen_sources = {p.source_id for p in winner.provenance}
        if winner.source_id not in seen_sources:
            winner.provenance.append(_sighting(winner))
            seen_sources.add(winner.source_id)
        for other in bucket:
            if other is winner:
                continue
            if other.source_id not in seen_sources:
                winner.provenance.append(_sighting(other))
                seen_sources.add(other.source_id)
            other.duplicate_of = winner.job_id
            # Merging must not lose information the loser had and the winner lacked.
            if not winner.description_text and other.description_text:
                winner.description_text = other.description_text
                winner.description_native = other.description_native
            if winner.salary is None and other.salary is not None:
                winner.salary = other.salary
            if not winner.employer_careers_url and other.employer_careers_url:
                winner.employer_careers_url = other.employer_careers_url
            for marker in other.uncertainty:
                if marker not in winner.uncertainty:
                    winner.uncertainty.append(marker)
            report.absorbed += 1
            report.hard_merges += 1
        kept.append(winner)

    for job in unkeyed:
        if not job.provenance:
            job.provenance = [_sighting(job)]
        kept.append(job)

    # ---- tier 2: soft links. Nothing is removed here. --------------------------------------------
    by_soft: dict[str, list[CanonicalJob]] = {}
    for job in kept:
        by_soft.setdefault(soft_key(job), []).append(job)

    for bucket in by_soft.values():
        if len(bucket) < 2:
            continue
        for i, a in enumerate(bucket):
            for b in bucket[i + 1:]:
                if a.dedup_group_id and a.dedup_group_id == b.dedup_group_id:
                    continue
                reason = _distinct_reason(a, b)
                if reason:
                    report.blocked_links.append(reason)
                    continue
                if b.job_id not in a.possible_duplicate_of:
                    a.possible_duplicate_of.append(b.job_id)
                if a.job_id not in b.possible_duplicate_of:
                    b.possible_duplicate_of.append(a.job_id)
                report.soft_links += 1

    # Distinct requisitions that merely LOOK alike must never be soft-linked. A link may also already
    # be present on the input — the projection is hand-editable and a caller may pass records that
    # carry links from an earlier round — so this cleanup cannot assume it only sees links the soft
    # pass just made.
    #
    # This used to scan EVERY ORDERED PAIR of survivors, normalizing both employer names per pair.
    # The removal below can only fire when `other.job_id` is ALREADY in `job.possible_duplicate_of`,
    # so the work was quadratic while the effect was bounded by the existing link set: on the
    # 2026-09-30 production corpus that was 1,526**2 = 2,328,676 pair comparisons to police FOUR
    # links, and it was ~47% of a report runtime that had 24% of its budget left. Caching the
    # normalization would have made 2.3M comparisons cheaper and left the scan quadratic.
    #
    # So drive the pass from the links instead of from the pairs. Every guard below is the guard the
    # pair scan applied, in the same order, against the same values:
    #   * `job is other` and equal `dedup_group_id` still skip — including the case where BOTH are
    #     None, which compares equal and was skipped before.
    #   * the employer comparison is the same pure function on the same string, hoisted to one call
    #     per record instead of two per pair.
    #   * membership is re-checked at the moment of removal, because an earlier removal in this same
    #     pass can have already taken the id out.
    #   * exactly ONE occurrence is removed per (job, other) OBJECT pair, which is what the pair scan
    #     did. Two survivors sharing a `job_id` therefore still cause two removals, and a list
    #     carrying the same id twice still keeps the second copy.
    by_job_id: dict[str, list[CanonicalJob]] = {}
    for job in kept:
        by_job_id.setdefault(job.job_id, []).append(job)
    employer_key: dict[int, str] = {
        id(job): normalize_employer(job.employer_name) for job in kept
    }

    for job in kept:
        if not job.requisition_id or not job.possible_duplicate_of:
            continue
        # dict.fromkeys keeps first-seen order and visits each linked id once, so the inner loop over
        # same-id survivors is what reproduces "once per object".
        for linked_id in list(dict.fromkeys(job.possible_duplicate_of)):
            for other in by_job_id.get(linked_id, ()):
                if job is other or job.dedup_group_id == other.dedup_group_id:
                    continue
                if employer_key[id(job)] != employer_key[id(other)]:
                    continue
                if not other.requisition_id or job.requisition_id == other.requisition_id:
                    continue
                if linked_id in job.possible_duplicate_of:
                    job.possible_duplicate_of.remove(linked_id)

    report.groups = len(by_soft)
    report.survivors = len(kept)
    return kept, report
