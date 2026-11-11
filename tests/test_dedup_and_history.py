"""Dedup + application-history tests — acceptance row 6.

Row 6 has four parts, and three of them are about NOT losing things:
  cross-source duplicates preserve provenance
  distinct requisitions survive
  prepared materials do not become invented submissions
  skips and rejections remain respected

The two hardest cases are drawn from the real corpus: one employer whose same requisition was
submitted and then re-prepared a month later, and one employer with two genuinely different live
requisitions whose titles differ only by suffix. Merging the second pair would delete a live opening.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.candidate.history import (
    ApplicationHistory,
    HistoryEntry,
    enforce_confidence_cap,
    load_history,
)
from src.common.dedup import deduplicate, hard_key, soft_key
from src.common.models import (
    CanonicalJob,
    HistoryStatus,
    IdKind,
    Provider,
    RemoteMode,
    SourceKind,
    VerificationState,
)
from src.common.normalize import canonical_url, normalize_employer, normalize_title_for_matching

NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)


def _job(
    source_id, key, *, employer, title, url, apply_url=None, requisition=None,
    kind=SourceKind.DISCOVERY_FEED, verification=VerificationState.FEED_COMPLETE,
    location="Remote, US", secondary=None, description="You will build Python services on AWS.",
    salary=None,
):
    return CanonicalJob(
        source_id=source_id, job_id=f"{source_id}#{key}", id_kind=IdKind.NATIVE_ID,
        provider_native_id=key, employer_name=employer, title=title,
        requisition_id=requisition, posting_url=url, apply_url=apply_url or url,
        apply_host=(apply_url or url).split("/")[2] if "//" in (apply_url or url) else None,
        source_kind=kind, verification_state=verification,
        raw_location=location, canonical_location=location.lower(),
        secondary_locations=secondary or [], remote_hybrid_language=RemoteMode.REMOTE,
        description_text=description, salary=salary, last_seen_at=NOW,
    )


# --------------------------------------------------------------------------------------------------
# Hard merge — provably the same posting
# --------------------------------------------------------------------------------------------------
def test_same_posting_from_two_feeds_merges_and_keeps_both_sightings():
    board = _job(
        "greenhouse:acme", "123", employer="Acme Logistics",
        title="Business Systems Engineer",
        url="https://boards.greenhouse.io/acme/jobs/123",
        kind=SourceKind.ATS_BOARD, verification=VerificationState.EMPLOYER_CONFIRMED,
    )
    feed = _job(
        "remotive:all", "999", employer="Acme Logistics Inc.",
        title="Business Systems Engineer",
        url="https://boards.greenhouse.io/acme/jobs/123?utm_source=remotive&ref=feed",
    )
    kept, report = deduplicate([board, feed])

    assert len(kept) == 1
    survivor = kept[0]
    # The employer's own board wins: it is the record whose description and process we can trust.
    assert survivor.source_id == "greenhouse:acme"
    assert report.hard_merges == 1
    # Provenance preserves the sighting that was absorbed — nothing is silently discarded.
    sources = {p.source_id for p in survivor.provenance}
    assert sources == {"greenhouse:acme", "remotive:all"}
    assert feed.duplicate_of == survivor.job_id


def test_tracking_parameters_do_not_defeat_the_merge():
    assert canonical_url("https://x.example/jobs/1?utm_source=a&gh_src=b&ref=c") == \
        canonical_url("https://x.example/jobs/1")
    assert canonical_url("https://WWW.X.example/jobs/1/") == canonical_url("https://x.example/jobs/1")


def test_merge_does_not_lose_information_the_absorbed_row_had():
    from src.common.models import SalarySource, SalaryStruct

    thin = _job("greenhouse:acme", "5", employer="Acme", title="Engineer",
                url="https://boards.greenhouse.io/acme/jobs/5",
                kind=SourceKind.ATS_BOARD,
                verification=VerificationState.EMPLOYER_CONFIRMED, description="")
    rich = _job("himalayas:all", "h5", employer="Acme", title="Engineer",
                url="https://boards.greenhouse.io/acme/jobs/5",
                description="You will build internal tools.",
                salary=SalaryStruct(min=150000, max=180000, currency="USD", period="year",
                                    source=SalarySource.STATED))
    kept, _report = deduplicate([thin, rich])
    survivor = kept[0]
    assert survivor.source_id == "greenhouse:acme"          # trust still wins
    assert survivor.description_text == "You will build internal tools."   # but data is carried
    assert survivor.salary is not None and survivor.salary.min == 150000


# --------------------------------------------------------------------------------------------------
# Distinct requisitions must survive — the case that would delete a live opening
# --------------------------------------------------------------------------------------------------
def test_two_requisitions_at_one_employer_are_never_merged():
    """From the real corpus: one employer, two live requisitions, similar titles."""
    a = _job("greenhouse:syllo", "4407264009", employer="Syllo",
             title="Senior Software Engineer, Applied AI",
             url="https://job-boards.greenhouse.io/syllo/jobs/4407264009",
             requisition="4407264009", kind=SourceKind.ATS_BOARD)
    b = _job("greenhouse:syllo", "4374366009", employer="Syllo",
             title="Senior Software Engineer, Internal Tools",
             url="https://job-boards.greenhouse.io/syllo/jobs/4374366009",
             requisition="4374366009", kind=SourceKind.ATS_BOARD)
    kept, report = deduplicate([a, b])

    assert len(kept) == 2                        # both survive
    assert report.hard_merges == 0
    assert a.duplicate_of is None and b.duplicate_of is None
    assert b.job_id not in a.possible_duplicate_of


def test_location_eligibility_variants_are_not_collapsed():
    a = _job("ashby:acme", "u1", employer="Acme", title="Backend Engineer",
             url="https://jobs.ashbyhq.com/acme/u1", location="Remote, US",
             secondary=["Remote (Canada)"])
    b = _job("ashby:acme", "u2", employer="Acme", title="Backend Engineer",
             url="https://jobs.ashbyhq.com/acme/u2", location="Remote, US", secondary=[])
    kept, report = deduplicate([a, b])
    assert len(kept) == 2
    assert any("location-eligibility variants" in reason for reason in report.blocked_links)


def test_similar_postings_without_proof_are_soft_linked_and_both_kept():
    """Ambiguity is surfaced for review, never resolved by deletion."""
    a = _job("remotive:all", "1", employer="Harbor Freight Systems",
             title="Integration Developer", url="https://remotive.com/remote-jobs/a")
    b = _job("jobicy:all", "2", employer="Harbor Freight Systems",
             title="Integration Developer", url="https://jobicy.com/jobs/b")
    kept, report = deduplicate([a, b])
    assert len(kept) == 2                       # nothing deleted
    assert report.soft_links == 1
    assert b.job_id in a.possible_duplicate_of
    assert a.job_id in b.possible_duplicate_of


def test_soft_key_folds_employer_suffixes_and_title_spelling():
    a = _job("x:1", "1", employer="Acme Logistics, Inc.", title="FullStack Engineer",
             url="https://a.example/1")
    b = _job("y:2", "2", employer="Acme Logistics LLC", title="Full-Stack Engineer",
             url="https://b.example/2")
    assert soft_key(a) == soft_key(b)
    assert hard_key(a) != hard_key(b)


def test_dedup_report_counts_are_operator_readable():
    a = _job("greenhouse:acme", "1", employer="Acme", title="Engineer",
             url="https://boards.greenhouse.io/acme/jobs/1", kind=SourceKind.ATS_BOARD)
    b = _job("remotive:all", "2", employer="Acme", title="Engineer",
             url="https://boards.greenhouse.io/acme/jobs/1?utm_source=x")
    _kept, report = deduplicate([a, b])
    payload = report.to_json()
    assert payload["hard_merges"] == 1
    assert "records_kept" in payload
    assert "links_blocked_as_distinct_requisitions" in payload


# --------------------------------------------------------------------------------------------------
# History — five distinct states, and a scan can never invent a submission
# --------------------------------------------------------------------------------------------------
def test_the_committed_projection_loads_and_distinguishes_all_five_states():
    history = load_history()
    assert history is not None, "config/application_history.json must be committed"
    statuses = {e.status for e in history.entries}
    assert HistoryStatus.SUBMITTED in statuses
    assert HistoryStatus.PREPARED in statuses
    assert HistoryStatus.SKIPPED in statuses
    assert HistoryStatus.REJECTED in statuses
    # NEW is the absence of a row, which is the fifth state.
    assert history.status_for(
        employer_name="Nobody Has Heard Of This Company", title="Engineer", url=None
    ) == HistoryStatus.NEW


def test_requisition_url_wins_over_employer_and_title():
    """The Syllo case again, from the history side: two requisitions, two different statuses."""
    history = load_history()
    submitted = history.status_for(
        employer_name="Syllo", title="Senior Software Engineer, Applied AI",
        url="https://job-boards.greenhouse.io/syllo/jobs/4407264009",
    )
    prepared = history.status_for(
        employer_name="Syllo", title="Senior Software Engineer, Internal Tools",
        url="https://job-boards.greenhouse.io/syllo/jobs/4374366009",
    )
    assert submitted == HistoryStatus.SUBMITTED
    assert prepared == HistoryStatus.PREPARED


def test_a_resubmitted_requisition_keeps_its_submitted_status():
    """The Machinify case: submitted, then re-prepared a month later. The submission stands."""
    history = load_history()
    entry = history.lookup(
        employer_name="Machinify", title="AI Engineer | Agentic Systems",
        url="https://job-boards.greenhouse.io/machinifyinc/jobs/4146862009",
    )
    assert entry is not None
    assert entry.status == HistoryStatus.SUBMITTED
    assert entry.status_conflict is True          # the duplicate preparation is flagged
    assert "duplicate" in (entry.conflict_detail or "").lower()


def test_skips_and_rejections_are_respected():
    history = load_history()
    assert history.status_for(
        employer_name="Wispr Flow", title="AI Engineer, Internal Systems",
        url="https://jobs.ashbyhq.com/wispr-flow/96beb394-070d-4753-8cd5-5928a2657b3f/application",
    ) == HistoryStatus.SKIPPED
    assert history.status_for(
        employer_name="Mozilla", title="Senior Application Engineer, Workplace Technology",
        url="https://job-boards.greenhouse.io/mozilla/jobs/8077457",
    ) == HistoryStatus.REJECTED


def test_a_scan_can_never_conclude_a_submission_on_its_own():
    """The invariant that protects against a parser error hiding a live opening."""
    scanned = [
        HistoryEntry(
            confidence="parsed", employer_name="Acme", employer_key=normalize_employer("Acme"),
            role_title="Engineer", title_key=normalize_title_for_matching("Engineer"),
            status=HistoryStatus.SUBMITTED, evidence_quote="looked submitted to a regex",
        ),
        HistoryEntry(
            confidence="reviewed", employer_name="Beta", employer_key=normalize_employer("Beta"),
            role_title="Engineer", title_key=normalize_title_for_matching("Engineer"),
            status=HistoryStatus.SUBMITTED, evidence_quote="Status: submitted September 17, 2026",
        ),
    ]
    enforce_confidence_cap(scanned)
    # the unreviewed row was demoted and flagged...
    assert scanned[0].status == HistoryStatus.PREPARED
    assert scanned[0].status_conflict is True
    assert "capped at PREPARED" in (scanned[0].conflict_detail or "")
    # ...while the reviewed row keeps its status
    assert scanned[1].status == HistoryStatus.SUBMITTED


def test_conflicting_evidence_is_preserved_rather_than_resolved():
    """Where the record contradicts itself, the weaker status is kept and the conflict surfaces."""
    history = load_history()
    conflicted = [e for e in history.entries if e.status_conflict]
    assert conflicted, "the corpus contains genuinely contradictory records; they must be flagged"
    for entry in conflicted:
        assert entry.conflict_detail
        # A conflicted row must never sit at SUBMITTED purely on ambiguous evidence unless the
        # conflict is about something else (a duplicate preparation of an already-submitted req).
        if "duplicate" not in entry.conflict_detail.lower():
            assert entry.status != HistoryStatus.SUBMITTED


def test_history_projection_carries_no_personal_data():
    """Privacy boundary: screening criteria only, never a candidate dossier."""
    import json
    from pathlib import Path

    raw = Path("config/application_history.json").read_text().lower()
    for forbidden in ("712-2258", "drbretto82@gmail", "laconia", "resume:", "master_resume"):
        assert forbidden not in raw, forbidden
    payload = json.loads(Path("config/application_history.json").read_text())
    allowed = {
        "confidence", "employer_name", "employer_key", "role_title", "title_key", "status",
        "posting_url", "posting_url_key", "folder", "evidence_path", "evidence_quote",
        "status_conflict", "conflict_detail", "observed_at",
        # Alias URLs naming the SAME requisition — an aggregator row and the employer's own ATS.
        # Admitted deliberately. This allowlist stays closed so a field carrying personal material
        # cannot arrive unnoticed; these two carry URLs and nothing else.
        "posting_urls", "posting_url_keys",
    }
    for entry in payload["entries"]:
        assert set(entry) <= allowed, set(entry) - allowed


def test_empty_history_is_safe_and_reports_everything_as_new():
    empty = ApplicationHistory(built_at=NOW, source_root="<none>", entries=[])
    assert empty.status_for(employer_name="Anyone", title="Engineer", url=None) \
        == HistoryStatus.NEW
