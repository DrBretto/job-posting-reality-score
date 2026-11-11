"""History reconciliation — the submission-log reader, URL aliases, and the four projection states.

The behaviours pinned here are the ones that decide whether a posting already submitted gets
announced as a fresh opportunity, so each test names the harm it prevents rather than the function
it calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.candidate.history import (
    CONFIDENCE_PARSED,
    CONFIDENCE_REVIEWED,
    CONFIDENCE_SUBMISSION_LOG,
    SUPPRESSING_STATUSES,
    ApplicationHistory,
    HistoryEntry,
    enforce_confidence_cap,
    load_history,
    merge_entries,
    read_submission_logs,
    refresh_history,
    save_history,
)
from src.common.models import HistoryStatus
from src.common.normalize import canonical_url, normalize_employer, normalize_title_for_matching
from src.report.handler import _history_projection_state


# --------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------
def entry(employer, role, status, url=None, urls=(), confidence=CONFIDENCE_REVIEWED):
    return HistoryEntry(
        confidence=confidence,
        employer_name=employer,
        employer_key=normalize_employer(employer),
        role_title=role,
        title_key=normalize_title_for_matching(role or employer),
        status=status,
        posting_url=url,
        posting_url_key=canonical_url(url) if url else None,
        posting_urls=list(urls),
        posting_url_keys=[canonical_url(u) for u in urls],
    )


def write_log(tmp_path, day, body):
    d = tmp_path / day
    d.mkdir(parents=True, exist_ok=True)
    (d / "SUBMISSION_LOG.md").write_text(body)
    return d


SUBMITTED_SECTION = """# Submission log — {day}

## 1. Pivotal Health — Senior Software Engineer, Case Execution

- **Requisition:** Ashby `5984f6bb-78f2-4d68-a907-dcd5b80d2831`, verified live.
- **URL:** https://jobs.ashbyhq.com/pivotal-health/5984f6bb-78f2-4d68-a907-dcd5b80d2831/application

**Result: SUBMITTED — confirmed by the employer's own page.** Pivotal Health returned, verbatim:

> Success
> Your application was successfully submitted.
"""


# --------------------------------------------------------------------------------------------------
# The reader's promotion rule
# --------------------------------------------------------------------------------------------------
def test_a_result_submitted_marker_establishes_a_submission(tmp_path):
    """The evidence a folder scan cannot produce: the employer's own recorded answer."""
    write_log(tmp_path, "2026-09-26-live-pool", SUBMITTED_SECTION.format(day="2026-09-26"))
    entries, held, files, cutoff = read_submission_logs(tmp_path)

    assert [e.status for e in entries] == [HistoryStatus.SUBMITTED]
    assert entries[0].confidence == CONFIDENCE_SUBMISSION_LOG
    assert entries[0].employer_name == "Pivotal Health"
    assert entries[0].role_title == "Senior Software Engineer, Case Execution"
    assert held == []
    assert files == ["2026-09-26-live-pool/SUBMISSION_LOG.md"]
    assert cutoff == datetime(2026, 9, 26, tzinfo=timezone.utc)


def test_a_confirmation_line_is_the_same_marker_in_a_different_format(tmp_path):
    """Two runs write acceptance two ways. Missing the second one loses four real submissions."""
    write_log(tmp_path, "2026-09-27-remaining-pool", """
## 1. Tailscale — Backend Engineer, Control Plane

- **URL:** https://job-boards.greenhouse.io/tailscale/jobs/4733183005
- **Confirmation:** `https://job-boards.greenhouse.io/tailscale/jobs/4733183005/confirmation` —
  "Thanks so much for applying for a position at Tailscale!"
""")
    entries, held, _files, _cutoff = read_submission_logs(tmp_path)
    assert [(e.employer_name, e.status) for e in entries] == [
        ("Tailscale", HistoryStatus.SUBMITTED)]
    assert held == []


def test_an_acceptance_line_is_also_that_marker(tmp_path):
    """The third format, found by re-reading a CONCURRENT run's log mid-flight rather than by
    reasoning about the corpus. Without it, a real employer-confirmed submission made the same day
    would have been announced as a fresh opportunity in the next round."""
    write_log(tmp_path, "2026-09-28-contracts", """
## 1. Obi9 Technologies — Sr. Full-Stack Engineer (Contract or Full-time) · SUBMITTED

- **Requisition verified live:** 2026-09-28, https://obi9.ai/jobs/full-stack-engineer
- **Acceptance (employer-confirmed), verbatim:**
  > Application received.
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert [(e.employer_name, e.status) for e in entries] == [
        ("Obi9 Technologies", HistoryStatus.SUBMITTED)]
    assert held == []


@pytest.mark.parametrize("line", [
    # "acceptance criteria" appears dozens of times in this corpus, in quoted resume and
    # cover-letter text. A line starting with it is not an employer saying yes.
    "- **Acceptance criteria:** I define and verify them myself.",
    "Acceptance rate: unknown.",
    "Confirmation URL for this flow. Captures: none were retained.",
    "- Acceptance testing: not applicable to this form.",
])
def test_a_line_that_merely_starts_with_the_keyword_is_not_an_acceptance(tmp_path, line):
    write_log(tmp_path, "2026-09-28-contracts", f"""
## 1. Somewhere Ltd — Backend Engineer

- **URL:** https://example.test/jobs/1
{line}
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == [], f"{line!r} must not establish a submission"
    # It is not dropped either: the section names a requisition and carries no marker the reader
    # understands, so it is held and named rather than vanishing.
    assert len(held) == 1
    assert "no recognised acceptance" in held[0].reason


def test_an_unrecognised_acceptance_format_fails_loudly_instead_of_vanishing(tmp_path):
    """The durable half of that finding.

    Three acceptance formats exist because three runs wrote them, and a fourth will appear. A
    section the reader does not understand must not be silently skipped — a dropped submission is
    one the next round re-announces. When the heading claims SUBMITTED and nothing in the section
    says so in a form the reader knows, it is held and named.
    """
    write_log(tmp_path, "2026-09-29-future-format", """
## 1. Somewhere Ltd — Backend Engineer · SUBMITTED

- **URL:** https://example.test/jobs/1
- **The employer said yes in a way nobody has written before.**
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == []
    assert len(held) == 1
    assert "no recognised acceptance" in held[0].reason


def test_a_heading_decoration_alone_never_establishes_a_submission(tmp_path):
    """The guard above must not become a back door. A heading is decoration, not evidence: the same
    corpus writes `· PREPARED, NOT SUBMITTED` headings."""
    write_log(tmp_path, "2026-09-29-future-format", """
## 1. Somewhere Ltd — Backend Engineer · SUBMITTED

- **URL:** https://example.test/jobs/1
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == [], "a heading may not promote on its own"
    assert held and held[0].employer_name == "Somewhere Ltd"


@pytest.mark.parametrize("verdict", ["BLOCKED", "HELD", "NOT SUBMITTED"])
def test_a_non_acceptance_verdict_is_held_and_never_becomes_a_submission(tmp_path, verdict):
    """A blocked or held attempt is a real fact and it is not a submission. Suppressing an opening
    on it would hide a live role the operator still has to finish."""
    write_log(tmp_path, "2026-09-26-catchup", f"""
## 1. Syllo — Senior Software Engineer, Internal Tools

- **URL:** https://job-boards.greenhouse.io/syllo/jobs/4374366009

**Result: {verdict} — human-verification gate.** Pressing Submit produced a code request.
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == []
    assert len(held) == 1
    assert held[0].employer_name == "Syllo"
    assert verdict.split()[0].lower() in held[0].reason.lower() or "not a submission" in held[0].reason


def test_a_prepared_not_submitted_target_is_held_rather_than_dropped(tmp_path):
    """A section with no acceptance marker at all still names a target. Dropping it silently is how
    a prepared-but-unsent application becomes invisible."""
    write_log(tmp_path, "2026-09-27-prepared-continuation", """
## 8. Grafana Labs — Staff AI Engineer · PREPARED, NOT SUBMITTED — operator completes

Requisition `6100672004` re-verified live; the human/AI question is unchanged.
- **URL:** https://job-boards.greenhouse.io/grafanalabs/jobs/6100672004
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == []
    assert [h.employer_name for h in held] == ["Grafana Labs"]
    assert "not submitted" in held[0].reason


def test_an_acceptance_beside_a_not_submitted_claim_is_held_not_resolved(tmp_path):
    """Both claims in one section. Resolving it either way is the system deciding something the
    record did not."""
    write_log(tmp_path, "2026-09-26-catchup", """
## 1. Ambiguous Co — Senior Engineer

- **URL:** https://example.test/jobs/1
- **Confirmation:** `https://example.test/jobs/1/confirmation` — "Thank you for applying."

The package note still reads: not yet submitted.
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == []
    assert len(held) == 1
    assert "held rather than resolved" in held[0].reason


def test_a_narrative_heading_is_not_a_target_record(tmp_path):
    """`## 0. The permission refusal did not recur` names no employer and no role."""
    write_log(tmp_path, "2026-09-27-prepared-continuation", """
## 0. The permission refusal did not recur, and that was established first

**Result: SUBMITTED** would be nonsense here; this section is prose.
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == []
    assert held == []


def test_only_the_records_own_url_line_counts_never_a_url_named_in_narrative(tmp_path):
    """The load-bearing one.

    These sections genuinely cite requisitions that were considered and NOT applied to — a closed
    aggregator row, a hybrid requisition ruled out on location. Treating a narrative mention as this
    record's URL would suppress an opening nobody applied to.
    """
    # The narrative URL appears FIRST on purpose. With the declared `URL:` line first, "the URL:
    # line" and "the first URL in the section" return the same string, and neutralising
    # `_declared_url` to "first bare URL" failed nothing — the test named the property and did not
    # discriminate on it. In this order it does.
    write_log(tmp_path, "2026-09-26-continuation", """
## 2. Evolve — Senior Software Engineer, Full Stack

### Requisition correction — this is not the pooled record

The pool carried Evolve "Staff Software Engineer"
(https://remoteOK.com/remote-jobs/remote-staff-software-engineer-evolve-1136447). That requisition
is no longer on Evolve's board, and it was NOT applied to.

- **URL:** https://job-boards.greenhouse.io/evolvevacationrental/jobs/8003653003

**Result: SUBMITTED — confirmed on page.**
""")
    entries, _held, _f, _c = read_submission_logs(tmp_path)
    assert len(entries) == 1
    keys = entries[0].all_url_keys()
    assert canonical_url("https://job-boards.greenhouse.io/evolvevacationrental/jobs/8003653003") in keys
    assert canonical_url(
        "https://remoteOK.com/remote-jobs/remote-staff-software-engineer-evolve-1136447"
    ) not in keys


def test_a_submission_with_no_url_still_suppresses_on_employer_and_title(tmp_path):
    """Six real submissions record the requisition id but no URL. Holding them would re-announce
    six applications that were sent and confirmed."""
    write_log(tmp_path, "2026-09-27-prepared-continuation", """
## 3. Cresta — Customer Engineer · SUBMITTED

- **Requisition:** Greenhouse `4122946008`, verified live.
- **Result: SUBMITTED.** `/confirmation`, "Thank you for applying."
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert held == []
    assert entries[0].posting_url is None
    history = ApplicationHistory(built_at=datetime.now(timezone.utc), source_root="x",
                                 entries=entries)
    assert history.status_for(
        employer_name="Cresta", title="Customer Engineer", url="https://anything.test/x",
    ) == HistoryStatus.SUBMITTED


def test_a_target_held_one_day_and_submitted_later_is_not_still_unresolved(tmp_path):
    write_log(tmp_path, "2026-09-26-recovered-radar", """
## 1. Fieldguide — Software Engineer (All Levels)

- **URL:** https://jobs.ashbyhq.com/fieldguide/47a2afc4/application
### Result: NOT SUBMITTED — local permission refusal, Submit never pressed
""")
    write_log(tmp_path, "2026-09-27-prepared-continuation", """
## 1. Fieldguide — Software Engineer (All Levels) · SUBMITTED

- **URL:** https://jobs.ashbyhq.com/fieldguide/47a2afc4/application
- **Result: SUBMITTED.** Verbatim: "Success — Thank you for applying!"
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert [e.employer_name for e in entries] == ["Fieldguide"]
    assert held == []


def test_a_trailing_ats_name_is_not_part_of_the_role_title(tmp_path):
    write_log(tmp_path, "2026-09-26-continuation", """
## 4. Fieldguide — Software Engineer, Quality & Automation (Ashby)

**Result: SUBMITTED — confirmed on page.**
""")
    entries, _h, _f, _c = read_submission_logs(tmp_path)
    assert entries[0].role_title == "Software Engineer, Quality & Automation"


def test_a_missing_submission_log_root_is_empty_and_not_an_error(tmp_path):
    entries, held, files, cutoff = read_submission_logs(tmp_path / "nope")
    assert (entries, held, files, cutoff) == ([], [], [], None)


# --------------------------------------------------------------------------------------------------
# Independent-review regressions. Every case below was a working exploit before it was repaired;
# each one promoted a section that said, in its own prose, that nothing had been sent.
# --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("body,why", [
    ("""Nothing was sent here. Quoting last week's log:
> - **Result: SUBMITTED — confirmed on page.**
- **URL:** https://example.com/alpha/1""",
     "a BLOCKQUOTED result line is another run speaking, not this record"),
    ("""Not applied to. The template we were shown:
```
- **Result: SUBMITTED.**
```
- **URL:** https://example.com/beta/2""",
     "a FENCED result line is an example, not a record"),
    ("""We considered this one and passed. Separately: another employer's application has
Result: SUBMITTED and is already recorded elsewhere.
- **URL:** https://example.com/gamma/3""",
     "a wrapped prose sentence is not a marker; a real one carries a bullet, bold or a heading"),
    ("""- **Result: SUBMITTED.** Correction appended later: the application was
  ultimately not submitted, the portal rejected the upload.
- **URL:** https://example.com/zeta/5""",
     "an append-only log's natural shape is a correction under the same heading"),
    ("""- **Confirmation: still pending, nothing has been received yet.**
- **URL:** https://example.com/theta/8""",
     "a Confirmation label whose value is a refusal is a refusal"),
    ("""- **Acceptance:** refused — a human-verification gate stopped the submission.
- **URL:** https://example.com/kappa/10""",
     "an Acceptance label whose value is a refusal is a refusal"),
    ("""- **Result: SUBMITTED PENDING VERIFICATION.**
- **URL:** https://example.com/mu/12""",
     "SUBMITTED PENDING VERIFICATION is not SUBMITTED"),
])
def test_sections_that_say_nothing_was_sent_are_never_promoted(tmp_path, body, why):
    write_log(tmp_path, "2026-10-01-probe", f"## 1. ProbeCo — Platform Engineer\n{body}\n")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == [], why
    assert held, f"and it must not vanish either: {why}"


def test_a_genuine_acceptance_still_promotes_beside_all_of_that(tmp_path):
    """The other side of the repairs: tightening must not cost a real submission."""
    write_log(tmp_path, "2026-10-01-probe", """
## 1. NuCo — Backend Engineer

- **URL:** https://example.com/nu/13
- **Confirmation:** `https://example.com/nu/13/confirmation` — "Thank you for applying."
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert [(e.employer_name, e.status) for e in entries] == [("NuCo", HistoryStatus.SUBMITTED)]
    assert held == []


def test_the_employers_own_quoted_words_are_evidence_even_though_quotes_are_stripped(tmp_path):
    """The two rules meet here, and the distinction is the whole point.

    A quoted `Result:` line is ANOTHER RUN speaking and must not promote. A blockquote under an
    acceptance marker is the EMPLOYER speaking, quoted verbatim, and it is the evidence itself.
    Blanking both cost two genuine submissions before this was separated.
    """
    write_log(tmp_path, "2026-09-28-contracts", """
## 1. Obi9 Technologies — Sr. Full-Stack Engineer · SUBMITTED

- **Requisition verified live:** https://obi9.ai/jobs/full-stack-engineer
- **Acceptance (employer-confirmed), verbatim:**
  > Application received.
- **Evidence limitation:** writing the screenshot to disk was refused by the permission layer.
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert [e.employer_name for e in entries] == ["Obi9 Technologies"], held
    # And the word "refused", in a LATER sentence about something else entirely, does not negate it.
    assert held == []


def test_a_target_held_only_by_its_heading_is_still_counted(tmp_path):
    """`· PREPARED AND HELD, NOT SENT` in the heading, and nothing in the body says so. Harmless in
    direction — it reads NEW and reaches the operator — but the held count was wrong and the design
    says a held record is never invisible."""
    write_log(tmp_path, "2026-09-28-contracts", """
## 3. Catalyst — AI Engineer, Agent Builder · PREPARED AND HELD, NOT SENT

- **Route:** email to talent@example.test with the exact subject the role requires.
- **State:** a draft is saved. Nothing was sent.
""")
    entries, held, _f, _c = read_submission_logs(tmp_path)
    assert entries == []
    assert [h.employer_name for h in held] == ["Catalyst"]


def test_the_cutoff_comes_from_days_the_reader_settled_not_from_files_it_opened(tmp_path):
    """A log the reader cannot understand must not advance the cutoff.

    That is not hypothetical: a fourth acceptance format arrived mid-run, and for a window the
    projection asserted coverage through that day while understanding none of its sections. The
    cutoff exists precisely to stop a projection claiming reach it does not have.
    """
    write_log(tmp_path, "2026-09-26-live-pool", SUBMITTED_SECTION.format(day="2026-09-26"))
    write_log(tmp_path, "2026-09-30-unreadable", """
# A log with no target sections at all

Some narrative prose about the round, naming no requisition.
""")
    _entries, _held, files, cutoff = read_submission_logs(tmp_path)
    assert len(files) == 2, "both files were read"
    assert cutoff == datetime(2026, 9, 26, tzinfo=timezone.utc), \
        "but only the day something was settled moves the cutoff"


def test_the_confidence_cap_also_holds_on_the_read_path(tmp_path):
    """The projection is hand-edited, so the builders are not the last gate before a status can
    hide a posting. A `parsed` SUBMITTED row in the committed file used to survive straight into
    `status_for`."""
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps({
        "built_at": "2026-09-28T00:00:00Z", "source_root": "x",
        "entries": [{
            "confidence": "parsed", "employer_name": "Scanned Co", "employer_key": "scanned co",
            "role_title": "Engineer", "title_key": "engineer", "status": "SUBMITTED",
            "posting_url": "https://a.test/1", "posting_url_key": "https://a.test/1",
            "folder": None, "evidence_path": None, "evidence_quote": None,
            "status_conflict": False, "conflict_detail": None, "observed_at": None,
        }],
    }))
    history = load_history(path)
    assert history.status_for(
        employer_name="Scanned Co", title="Engineer", url="https://a.test/1"
    ) == HistoryStatus.PREPARED
    assert history.entries[0].status_conflict


# --------------------------------------------------------------------------------------------------
# The confidence cap
# --------------------------------------------------------------------------------------------------
def test_the_folder_scan_is_still_capped_at_prepared():
    """The invariant this repair must not loosen: no regex over package prose concludes a
    submission. A false SUBMITTED hides a live opening."""
    capped = enforce_confidence_cap([
        entry("Scanned Co", "Engineer", HistoryStatus.SUBMITTED, confidence=CONFIDENCE_PARSED),
        entry("Scanned Co", "Other", HistoryStatus.REJECTED, confidence=CONFIDENCE_PARSED),
        entry("Scanned Co", "Third", HistoryStatus.SKIPPED, confidence=CONFIDENCE_PARSED),
    ])
    assert {e.status for e in capped} == {HistoryStatus.PREPARED}
    assert all(e.status_conflict for e in capped)


def test_a_submission_log_entry_may_only_ever_say_submitted():
    """Belt and braces on the one confidence level that was added. The wrong direction here is a
    hidden opening, so it is checked in code and not only in the reader."""
    capped = enforce_confidence_cap([
        entry("Log Co", "Engineer", HistoryStatus.SKIPPED, confidence=CONFIDENCE_SUBMISSION_LOG),
    ])
    assert capped[0].status == HistoryStatus.PREPARED
    assert capped[0].status_conflict


def test_a_reviewed_entry_keeps_its_suppressing_status():
    kept = enforce_confidence_cap([
        entry("Reviewed Co", "Engineer", HistoryStatus.SUBMITTED, confidence=CONFIDENCE_REVIEWED),
    ])
    assert kept[0].status == HistoryStatus.SUBMITTED
    assert not kept[0].status_conflict


# --------------------------------------------------------------------------------------------------
# Aliases — the feed URL and the ATS URL are one requisition
# --------------------------------------------------------------------------------------------------
PIVOTAL_ASHBY = "https://jobs.ashbyhq.com/pivotal-health/5984f6bb-78f2-4d68-a907-dcd5b80d2831/application"
PIVOTAL_REMOTEOK = (
    "https://remoteOK.com/remote-jobs/"
    "remote-senior-software-engineer-case-execution-pivotal-health-1136795"
)


def test_the_known_duplicate_control_resolves_through_either_url():
    """The packet's own control: submitted 2026-09-26, employer-confirmed. Neither URL may read
    NEW, because the feed carries one and the application used the other."""
    history = ApplicationHistory(
        built_at=datetime.now(timezone.utc), source_root="x",
        entries=[entry("Pivotal Health", "Senior Software Engineer, Case Execution",
                       HistoryStatus.SUBMITTED, PIVOTAL_ASHBY, [PIVOTAL_REMOTEOK])],
    )
    for url in (PIVOTAL_ASHBY, PIVOTAL_REMOTEOK):
        assert history.status_for(
            employer_name="Pivotal Health",
            title="Senior Software Engineer Case Execution", url=url,
        ) == HistoryStatus.SUBMITTED


def test_a_distinct_requisition_at_the_same_employer_stays_eligible():
    """The other half of the control, and the more expensive failure: suppressing a different
    opening at a company that happens to have one submission already."""
    history = ApplicationHistory(
        built_at=datetime.now(timezone.utc), source_root="x",
        entries=[entry("Pivotal Health", "Senior Software Engineer, Case Execution",
                       HistoryStatus.SUBMITTED, PIVOTAL_ASHBY, [PIVOTAL_REMOTEOK])],
    )
    assert history.status_for(
        employer_name="Pivotal Health", title="Staff Platform Engineer",
        url="https://jobs.ashbyhq.com/pivotal-health/00000000-1111-2222-3333-444444444444/application",
    ) == HistoryStatus.NEW


def test_a_stale_prepared_row_cannot_displace_a_submission_on_a_shared_url():
    history = ApplicationHistory(
        built_at=datetime.now(timezone.utc), source_root="x",
        entries=[
            entry("Shared", "Alias Carrier", HistoryStatus.PREPARED, None, [PIVOTAL_ASHBY]),
            entry("Pivotal Health", "Senior Software Engineer, Case Execution",
                  HistoryStatus.SUBMITTED, PIVOTAL_ASHBY),
        ],
    )
    assert history.by_url()[canonical_url(PIVOTAL_ASHBY)].status == HistoryStatus.SUBMITTED


def test_merge_keeps_the_stronger_status_and_unions_every_url():
    merged = merge_entries(
        [entry("Pivotal Health", "Senior Software Engineer, Case Execution",
               HistoryStatus.PREPARED, None, [PIVOTAL_REMOTEOK])],
        [entry("Pivotal Health", "Senior Software Engineer, Case Execution",
               HistoryStatus.SUBMITTED, PIVOTAL_ASHBY, confidence=CONFIDENCE_SUBMISSION_LOG)],
    )
    assert len(merged) == 1
    assert merged[0].status == HistoryStatus.SUBMITTED
    keys = merged[0].all_url_keys()
    assert canonical_url(PIVOTAL_ASHBY) in keys and canonical_url(PIVOTAL_REMOTEOK) in keys


def test_merge_does_not_let_a_later_prepared_row_downgrade_a_submission():
    merged = merge_entries(
        [entry("Co", "Engineer", HistoryStatus.SUBMITTED, "https://a.test/1")],
        [entry("Co", "Engineer", HistoryStatus.PREPARED, "https://b.test/1",
               confidence=CONFIDENCE_PARSED)],
    )
    assert merged[0].status == HistoryStatus.SUBMITTED


# --------------------------------------------------------------------------------------------------
# refresh — repeatable, and it does not merge the folder scan
# --------------------------------------------------------------------------------------------------
def test_refresh_is_repeatable_and_writes_nothing_new_on_a_second_run(tmp_path):
    projection = tmp_path / "application_history.json"
    save_history(ApplicationHistory(
        built_at=datetime(2026, 9, 24, tzinfo=timezone.utc), source_root="inbox",
        entries=[entry("Pivotal Health", "Senior Software Engineer, Case Execution",
                       HistoryStatus.PREPARED, PIVOTAL_ASHBY)],
    ), projection)
    logs = tmp_path / "logs"
    write_log(logs, "2026-09-26-live-pool", SUBMITTED_SECTION.format(day="2026-09-26"))

    first, changes = refresh_history(
        projection_path=projection, inbox_root=tmp_path / "absent", submission_log_root=logs)
    assert changes["status_changed"] == [
        "Pivotal Health — Senior Software Engineer, Case Execution: PREPARED -> SUBMITTED"]
    assert changes["cutoff"] == "2026-09-26"
    save_history(first, projection)

    second, changes2 = refresh_history(
        projection_path=projection, inbox_root=tmp_path / "absent", submission_log_root=logs)
    assert changes2["status_changed"] == [] and changes2["added"] == []
    assert len(second.entries) == len(first.entries)


def test_refresh_reports_folder_drift_and_does_not_merge_it(tmp_path):
    """A scanner row is capped at PREPARED, and the report moves anything that is not NEW out of the
    candidate sections — so merging one would demote a live opening on the strength of a folder
    name. Drift is reported for the operator to act on, which is what `history-scan` already does.
    """
    projection = tmp_path / "application_history.json"
    save_history(ApplicationHistory(built_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
                                    source_root="inbox", entries=[]), projection)
    inbox = tmp_path / "inbox" / "2026-09-26" / "Someone Else - Senior Engineer"
    inbox.mkdir(parents=True)
    (inbox / "APPLICATION_NOTES.md").write_text("Status: ready for Brett\n")

    history, changes = refresh_history(
        projection_path=projection, inbox_root=tmp_path / "inbox",
        submission_log_root=tmp_path / "no-logs")
    assert history.entries == []
    assert changes["scan_drift"] == ["Someone Else — Senior Engineer"]


def test_refresh_records_a_cutoff_that_is_evidence_dated_not_run_dated(tmp_path):
    """Dating a projection by when it ran would assert coverage it does not have."""
    projection = tmp_path / "application_history.json"
    save_history(ApplicationHistory(built_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
                                    source_root="inbox", entries=[]), projection)
    logs = tmp_path / "logs"
    write_log(logs, "2026-09-26-live-pool", SUBMITTED_SECTION.format(day="2026-09-26"))
    now = datetime(2026, 9, 30, tzinfo=timezone.utc)
    history, _changes = refresh_history(
        projection_path=projection, inbox_root=tmp_path / "absent",
        submission_log_root=logs, now=now)
    assert history.built_at == now
    assert history.cutoff == datetime(2026, 9, 26, tzinfo=timezone.utc)


def test_refresh_never_deletes_a_reviewed_entry_the_logs_do_not_mention(tmp_path):
    """Absence from a log is not proof of anything."""
    projection = tmp_path / "application_history.json"
    save_history(ApplicationHistory(
        built_at=datetime(2026, 9, 24, tzinfo=timezone.utc), source_root="inbox",
        entries=[entry("Old Co", "Engineer", HistoryStatus.SUBMITTED, "https://old.test/1")],
    ), projection)
    history, _c = refresh_history(
        projection_path=projection, inbox_root=tmp_path / "absent",
        submission_log_root=tmp_path / "no-logs")
    assert [(e.employer_name, e.status) for e in history.entries] == [
        ("Old Co", HistoryStatus.SUBMITTED)]


def test_an_older_projection_without_the_new_fields_still_loads(tmp_path):
    """The deployed projection predates `cutoff`, `posting_urls` and `unresolved`."""
    legacy = {
        "built_at": "2026-09-24T00:00:00Z",
        "source_root": "inbox",
        "entries": [{
            "confidence": "reviewed", "employer_name": "Old Co", "employer_key": "old co",
            "role_title": "Engineer", "title_key": "engineer", "status": "SUBMITTED",
            "posting_url": "https://old.test/1", "posting_url_key": "https://old.test/1",
            "folder": None, "evidence_path": None, "evidence_quote": None,
            "status_conflict": False, "conflict_detail": None, "observed_at": None,
        }],
    }
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(legacy))
    history = load_history(path)
    assert history.cutoff is None and history.unresolved == []
    assert history.entries[0].posting_urls == []
    assert history.status_for(
        employer_name="Old Co", title="Engineer", url="https://old.test/1"
    ) == HistoryStatus.SUBMITTED


# --------------------------------------------------------------------------------------------------
# The four projection states the report distinguishes
# --------------------------------------------------------------------------------------------------
def test_a_missing_projection_still_says_so():
    state = _history_projection_state(None, "2026-09-28")
    assert state["state"] == "missing"
    assert "NOT because none exists" in state["note"]


def test_a_stale_projection_is_no_longer_indistinguishable_from_a_current_one():
    """The whole defect: from inside the report a stale projection and a current one looked
    identical, so postings already submitted on the 26th were announced as NEW."""
    history = ApplicationHistory(
        built_at=datetime(2026, 9, 24, tzinfo=timezone.utc), source_root="x",
        cutoff=datetime(2026, 9, 24, tzinfo=timezone.utc),
        entries=[entry("Co", "Engineer", HistoryStatus.SUBMITTED, "https://a.test/1")],
    )
    state = _history_projection_state(history, "2026-09-28")
    assert state["state"] == "stale"
    assert state["gap_days"] == 4
    assert state["alarm"] is True
    assert "are NOT represented here" in state["note"]


def test_a_one_day_gap_states_the_facts_without_raising_the_alarm():
    """A one-day gap is what a correctly refreshed projection looks like on the next morning's
    report, so alarming there would alarm every day — and a banner that is always on is one the
    reader learns to skip, which is the same silence this whole block exists to break."""
    history = ApplicationHistory(
        built_at=datetime(2026, 9, 27, tzinfo=timezone.utc), source_root="x",
        cutoff=datetime(2026, 9, 27, tzinfo=timezone.utc),
        entries=[entry("Co", "Engineer", HistoryStatus.SUBMITTED, "https://a.test/1")],
    )
    state = _history_projection_state(history, "2026-09-28")
    assert state["state"] == "stale", "the state is still honestly stale"
    assert state["gap_days"] == 1
    assert state["alarm"] is False, "but the emphasis is not earned at one day"
    # The facts are printed either way.
    assert "2026-09-27" in state["note"]


def test_a_missing_projection_always_raises_the_alarm():
    assert _history_projection_state(None, "2026-09-28")["alarm"] is True


def test_a_current_projection_states_coverage_and_declines_to_claim_completeness():
    history = ApplicationHistory(
        built_at=datetime(2026, 9, 28, tzinfo=timezone.utc), source_root="x",
        cutoff=datetime(2026, 9, 28, tzinfo=timezone.utc),
        entries=[entry("Co", "Engineer", HistoryStatus.SUBMITTED, "https://a.test/1")],
    )
    state = _history_projection_state(history, "2026-09-28")
    assert state["state"] == "current"
    assert "not completeness" in state["note"]


def test_a_present_but_empty_projection_is_not_a_missing_one():
    history = ApplicationHistory(
        built_at=datetime(2026, 9, 28, tzinfo=timezone.utc), source_root="x",
        cutoff=datetime(2026, 9, 28, tzinfo=timezone.utc), entries=[])
    state = _history_projection_state(history, "2026-09-28")
    assert state["state"] == "known_empty"
    assert "genuinely unseen" in state["note"]


def test_a_projection_with_no_declared_cutoff_reads_stale_not_current():
    """An old projection cannot say how far its evidence reached, and silence is not currency."""
    history = ApplicationHistory(
        built_at=datetime(2026, 9, 28, tzinfo=timezone.utc), source_root="x", cutoff=None,
        entries=[entry("Co", "Engineer", HistoryStatus.SUBMITTED, "https://a.test/1")])
    state = _history_projection_state(history, "2026-09-28")
    assert state["state"] == "stale"
    assert state["gap_days"] is None


def test_the_held_count_reaches_the_reader():
    history = ApplicationHistory(
        built_at=datetime(2026, 9, 28, tzinfo=timezone.utc), source_root="x",
        cutoff=datetime(2026, 9, 28, tzinfo=timezone.utc),
        entries=[entry("Co", "Engineer", HistoryStatus.SUBMITTED, "https://a.test/1")],
        unresolved=[{
            "employer_name": "Syllo", "role_title": "Senior Software Engineer, Internal Tools",
            "reason": "submission log records BLOCKED, not a submission",
        }],
    )
    assert _history_projection_state(history, "2026-09-28")["unresolved"] == 1


# --------------------------------------------------------------------------------------------------
# The committed projection itself
# --------------------------------------------------------------------------------------------------
def test_the_committed_projection_carries_the_reconciled_submissions():
    """Pinned against the real file, because the behaviour above is worth nothing if the projection
    production reads is the stale one."""
    history = load_history()
    assert history is not None, "config/application_history.json must ship with the package"
    assert history.cutoff is not None, "the projection must declare how far its evidence reached"
    assert history.cutoff >= datetime(2026, 9, 27, tzinfo=timezone.utc)

    submitted = {
        (e.employer_key, e.title_key) for e in history.entries
        if e.status == HistoryStatus.SUBMITTED
    }
    for employer, title in [
        ("Pivotal Health", "Senior Software Engineer, Case Execution"),
        ("Sticker Mule", "AI agent engineer"),
        ("Machinify", "Staff AI Engineer"),
        ("Tailscale", "Backend Engineer, Control Plane"),
        ("Airspace Link, Inc.", "Backend Software Engineer (Golang)"),
        ("Hard Rock Digital", "Principal Backend Engineer, Core"),
        ("Mozilla", "Senior Software Engineer, Add-Ons"),
    ]:
        assert (normalize_employer(employer),
                normalize_title_for_matching(title)) in submitted, f"{employer} — {title}"


def test_the_committed_projection_resolves_the_pivotal_control_through_both_urls():
    history = load_history()
    for url in (PIVOTAL_ASHBY, PIVOTAL_REMOTEOK):
        assert history.status_for(
            employer_name="Pivotal Health",
            title="Senior Software Engineer Case Execution", url=url,
        ) == HistoryStatus.SUBMITTED


def test_the_committed_projection_keeps_the_closed_evolve_row_separate_from_the_submitted_one():
    """The inherited claim said the aggregator's Evolve row was "already submitted". The submission
    log says otherwise in terms: that requisition is off the board, and a DIFFERENT one was applied
    to. Two rows, neither guessed into the other."""
    history = load_history()
    assert history.status_for(
        employer_name="Evolve", title="Staff Software Engineer",
        url="https://remoteOK.com/remote-jobs/remote-staff-software-engineer-evolve-1136447",
    ) == HistoryStatus.SKIPPED
    assert history.status_for(
        employer_name="Evolve", title="Senior Software Engineer, Full Stack",
        url="https://job-boards.greenhouse.io/evolvevacationrental/jobs/8003653003",
    ) == HistoryStatus.SUBMITTED


@pytest.mark.parametrize("employer,title,url", [
    # The aggregator says "Airspace Link" / "Backend Software Engineer"; the submission was made at
    # "Airspace Link, Inc." / "Backend Software Engineer (Golang)" on Paylocity. Employer and title
    # BOTH differ, so nothing but the alias can connect them.
    ("Airspace Link", "Backend Software Engineer",
     "https://remoteOK.com/remote-jobs/remote-backend-software-engineer-airspace-link-1137409"),
    # "Principal Backend Engineer - Core" against ", Core".
    ("Hard Rock Digital", "Principal Backend Engineer - Core",
     "https://himalayas.app/companies/hard-rock-digital/jobs/principal-backend-engineer-core"),
    # "Software Engineer" against "Sr. Software Engineer".
    ("Prenosis", "Software Engineer",
     "https://remoteOK.com/remote-jobs/remote-software-engineer-prenosis-1137427"),
])
def test_rows_that_only_the_alias_list_can_match_are_not_announced_as_new(employer, title, url):
    """Three real submissions the employer+title fallback genuinely cannot reach.

    Measured rather than assumed: with the alias list neutralised each of these reads NEW, which is
    the report re-announcing an application already sent and confirmed.
    """
    history = load_history()
    assert history.status_for(
        employer_name=employer, title=title, url=url) == HistoryStatus.SUBMITTED


def test_a_prepared_but_unsent_application_is_not_suppressed_by_the_committed_projection():
    """A target that is prepared, held or blocked is not a submission, and must still reach him.

    This test used to name Grafana Labs' Staff AI Engineer, which WAS the live example of the shape
    on 2026-09-27: prepared to the AI-or-human attestation and handed over, because only Brett could
    answer it. He answered it and submitted, and the employer confirmed on 2026-09-27. The guarantee
    is unchanged and the example was overtaken by an event, so it is re-pointed rather than dropped.
    Grafana's own side of it is pinned above, in both directions, against the confirmation record.
    """
    history = load_history()
    for employer, title in (
        # Held on an operator decision: monthly travel to a U.S. metro the posting never names.
        ("Catalyst·Wayfare AI", "Lead AI Engineer, Agentic Systems"),
        # Blocked at an emailed human-verification gate; pressing Submit did not submit.
        ("Syllo", "Senior Software Engineer, Internal Tools"),
        # Held on a confidentiality agreement the live form requires before it will submit.
        ("Zscaler", "the retitled requisition, resolved and then held"),
    ):
        status = history.status_for(employer_name=employer, title=title, url=None)
        # The guarantee is about SUPPRESSION, not about the label. A reviewed PREPARED row is the
        # honest record of a prepared package and is the ordinary state for these three; what must
        # never happen is one of them reading as submitted, rejected or skipped.
        assert status not in SUPPRESSING_STATUSES, (
            f"{employer} — {title} is unsent and must still be announced, got {status.value}"
        )


def test_the_confirmed_grafana_requisition_is_not_announced_as_new():
    """The other half of the same fact, against the committed projection rather than a fixture."""
    history = load_history()
    assert history.status_for(
        employer_name="Grafana Labs", title="Staff AI Engineer",
        url="https://job-boards.greenhouse.io/grafanalabs/jobs/6100672004",
    ) == HistoryStatus.SUBMITTED


@pytest.mark.parametrize("employer,title,url", [
    # Employer-confirmed 2026-09-28, and BOTH requisitions were still open on the employers' own
    # boards the next morning — so without these rows the report announces a role that already has
    # an application in it. Today's feed carries each at an aggregator URL sharing nothing with the
    # ATS URL below, which is why the employer+title fallback is what has to catch them.
    ("AWeber", "Operations Engineer II",
     "https://remoteOK.com/remote-jobs/remote-operations-engineer-ii-aweber-1136778"),
    ("BetterHelp", "Full Stack Software Engineer",
     "https://jobicy.com/jobs/151816-full-stack-software-engineer"),
])
def test_the_2026_09_28_confirmations_are_not_announced_as_new(employer, title, url):
    history = load_history()
    assert history.status_for(
        employer_name=employer, title=title, url=url) == HistoryStatus.SUBMITTED


def test_no_committed_entry_carries_private_profile_material():
    """The projection keeps employer, role, URL, status and a pointer. Demographic and personal
    answers stay out of JPRS entirely."""
    raw = json.dumps(json.load(open("config/application_history.json"))).lower()
    for token in (
        "gender", "veteran", "hispanic", "ethnicity", "disability", "transgender",
        "date of birth", "street address", "phone",
        # Added after the independent review found all three in shipped `evidence_quote` values:
        # `_quote`'s backward window reached into the form-answer readback that precedes a
        # `Result:` line and dragged work-authorization answers into the deployed package.
        "sponsorship", "visa", "eeo", "clearance", "citizen", "salary expectation",
    ):
        assert token not in raw, f"{token!r} must not appear in the history projection"


# --------------------------------------------------------------------------------------------------
# Held on one day, confirmed on a later one — and only for the requisition that was confirmed
#
# 2026-09-28 recovery. Grafana Labs' Staff AI Engineer was recorded on 2026-09-27 as prepared and
# handed to the operator, because the form asks whether the applicant is an AI or a human being and
# only he could answer it. He answered it and submitted. The employer's own confirmation arrived the
# same morning. Two things have to be true at once afterwards, and they pull in opposite directions:
# the confirmed requisition must stop being announced, and the OTHER live requisitions at the same
# employer — Grafana's board carried two more Staff AI Engineer openings the day this was written —
# must keep reaching the report untouched.
# --------------------------------------------------------------------------------------------------
GRAFANA_HELD = """# Submission log — 2026-09-27

## 8. Grafana Labs — Staff AI Engineer

- **URL:** https://job-boards.greenhouse.io/grafanalabs/jobs/6100672004

**PREPARED, NOT SUBMITTED — operator completes.** The form asks whether the applicant is an AI or a
human being, which is Brett's to answer.
"""

GRAFANA_CONFIRMED = """# Submission log — 2026-09-28 confirmations

## 1. Grafana Labs — Staff AI Engineer

- **URL:** https://job-boards.greenhouse.io/grafanalabs/jobs/6100672004
- **Result: SUBMITTED** — employer-confirmed 2026-09-27, completed by the operator.
"""


def test_a_held_record_followed_by_a_later_confirmation_reads_submitted(tmp_path):
    """The held day stays true of its own day; the later confirmation is what the report reads."""
    write_log(tmp_path, "2026-09-27-prepared-continuation", GRAFANA_HELD)
    write_log(tmp_path, "2026-09-28-history-confirmations", GRAFANA_CONFIRMED)

    entries, held, _files, _cutoff = read_submission_logs(tmp_path)

    grafana = [e for e in entries if e.employer_key == normalize_employer("Grafana Labs")]
    assert len(grafana) == 1
    assert grafana[0].status is HistoryStatus.SUBMITTED

    # And it is no longer a live question. A settled target left in `held` re-raises on the
    # operator's page the one question he already answered.
    assert not [h for h in held if normalize_employer(h.employer_name) == normalize_employer("Grafana Labs")]


def test_confirming_one_requisition_leaves_the_employers_other_openings_alone(tmp_path):
    """The failure this guards is silent: a suppressed row is a row nobody sees."""
    write_log(tmp_path, "2026-09-27-prepared-continuation", GRAFANA_HELD)
    write_log(tmp_path, "2026-09-28-history-confirmations", GRAFANA_CONFIRMED)
    entries, _held, _files, _cutoff = read_submission_logs(tmp_path)
    history = ApplicationHistory(
        built_at=datetime(2026, 9, 28, tzinfo=timezone.utc), source_root="<test>", entries=entries
    )

    # The requisition that was actually applied to.
    assert history.status_for(
        employer_name="Grafana Labs", title="Staff AI Engineer",
        url="https://job-boards.greenhouse.io/grafanalabs/jobs/6100672004",
    ) is HistoryStatus.SUBMITTED

    # Two different live Staff AI Engineer requisitions at the same employer, and a third role.
    for title, url in (
        ("Staff AI Engineer | US | Remote",
         "https://job-boards.greenhouse.io/grafanalabs/jobs/6092955004"),
        ("Staff AI Engineer | Canada | Remote",
         "https://job-boards.greenhouse.io/grafanalabs/jobs/6092954004"),
        ("Senior Software Engineer",
         "https://job-boards.greenhouse.io/grafanalabs/jobs/6011111004"),
    ):
        assert history.status_for(
            employer_name="Grafana Labs", title=title, url=url
        ) is HistoryStatus.NEW, f"{title} is a distinct live opening and must still be announced"


# --------------------------------------------------------------------------------------------------
# The fourth acceptance format arrived, and the guard that was built for it did not fire
#
# The 2026-09-28 release predicted a fourth format and promised that a section whose format the
# reader cannot read would be "held and named rather than dropped". The format arrived the same
# evening as `## 3. AWeber — Operations Engineer II · **SUBMITTED, employer-confirmed**`, and all
# four sections of that log were dropped in silence: the guard needed either a `URL:` line or a
# heading ending in a bare `SUBMITTED`, and a bold-wrapped decoration carrying a trailing qualifier
# is neither. Two employer-confirmed submissions to still-open requisitions went missing.
# --------------------------------------------------------------------------------------------------
BOLD_DECORATED_LOG = """# Submission log — 2026-09-28 live pool

## 1. Catalyst·Wayfare AI — AI Engineer, Agent Builder · **SENT**

Route: email. Gmail reported the message sent at 7:48 PM.

## 2. Catalyst·Wayfare AI — Lead AI Engineer, Agentic Systems · **HELD, unchanged**

Its duties include monthly travel to a U.S. metro the posting does not name.

## 3. AWeber — Operations Engineer II · **SUBMITTED, employer-confirmed**

### Acceptance — employer-confirmed

The page advanced to the employer's confirmation URL.

## 4. BetterHelp — Full Stack Software Engineer · **SUBMITTED, employer-confirmed**

### Acceptance — employer-confirmed

The page advanced to the employer's confirmation URL.
"""


def test_a_bold_decorated_heading_is_held_and_named_never_dropped(tmp_path):
    write_log(tmp_path, "2026-09-28-live-pool", BOLD_DECORATED_LOG)
    entries, held, _files, _cutoff = read_submission_logs(tmp_path)

    # Nothing is promoted: a heading decoration is not evidence, and it never becomes one.
    assert entries == []

    # Every one of the four is visible.
    assert {(h.employer_name, h.role_title) for h in held} == {
        ("Catalyst·Wayfare AI", "AI Engineer, Agent Builder"),
        ("Catalyst·Wayfare AI", "Lead AI Engineer, Agentic Systems"),
        ("AWeber", "Operations Engineer II"),
        ("BetterHelp", "Full Stack Software Engineer"),
    }


def test_the_decoration_is_stripped_off_the_role_title(tmp_path):
    """An unstripped decoration corrupts the title key, so the record matches nothing at all —
    not the feed row, and not the later log that settles the same application."""
    write_log(tmp_path, "2026-09-28-live-pool", BOLD_DECORATED_LOG)
    _entries, held, _files, _cutoff = read_submission_logs(tmp_path)

    aweber = next(h for h in held if h.employer_name == "AWeber")
    assert aweber.role_title == "Operations Engineer II"
    assert normalize_title_for_matching(aweber.role_title) == "operations engineer ii"


def test_a_later_confirmation_settles_a_section_the_reader_could_not_read(tmp_path):
    """The two halves of the repair working together: the unreadable section becomes visible, and
    the explicit confirmation record is what actually settles its status."""
    write_log(tmp_path, "2026-09-28-live-pool", BOLD_DECORATED_LOG)
    write_log(tmp_path, "2026-09-28-history-confirmations", """# Submission log — confirmations

## 1. AWeber — Operations Engineer II

- **URL:** https://job-boards.greenhouse.io/aweber/jobs/8100185
- **Result: SUBMITTED** — employer-confirmed 2026-09-28.
""")
    entries, held, _files, _cutoff = read_submission_logs(tmp_path)

    assert [(e.employer_name, e.status) for e in entries] == [
        ("AWeber", HistoryStatus.SUBMITTED)
    ]
    assert "AWeber" not in {h.employer_name for h in held}
    # The genuinely unsettled ones stay unsettled.
    assert ("Catalyst·Wayfare AI", "Lead AI Engineer, Agentic Systems") in {
        (h.employer_name, h.role_title) for h in held
    }


def test_one_target_held_by_two_logs_is_listed_once(tmp_path):
    """Two runs recording the same unsent target is the ordinary shape of an append-only corpus.
    Listing it twice on the operator's page says nothing the first row did not."""
    write_log(tmp_path, "2026-09-28-contracts", """# Submission log

## 1. Catalyst·Wayfare AI — Lead AI Engineer, Agentic Systems · PREPARED, NOT SENT

Held on an operator decision about unspecified travel.
""")
    write_log(tmp_path, "2026-09-28-live-pool", BOLD_DECORATED_LOG)
    _entries, held, _files, _cutoff = read_submission_logs(tmp_path)

    lead = [h for h in held if h.role_title == "Lead AI Engineer, Agentic Systems"]
    assert len(lead) == 1
    # The earliest evidence is the one cited.
    assert "contracts" in lead[0].evidence_path


def test_a_heading_claiming_not_sent_is_never_read_as_a_send(tmp_path):
    """`SENT` now makes a heading visible, so `NOT SENT` must not fall into the same arm."""
    write_log(tmp_path, "2026-09-28-live-pool", """# Submission log

## 1. Example Corp — Staff Engineer · **NOT SENT**

Prepared only.
""")
    entries, held, _files, _cutoff = read_submission_logs(tmp_path)
    assert entries == []
    assert len(held) == 1
    assert "not a submission and it is not settled" in held[0].reason
    assert held[0].role_title == "Staff Engineer"


def test_an_employer_acknowledgment_resolves_a_stale_local_conflict():
    """Bjak's package note says nothing was sent; Bjak's own ATS acknowledged the application on
    2026-07-22. A flag that keeps asking a question the employer already answered is not caution."""
    reviewed = entry("BJAK", "Applied AI Engineer (US)", HistoryStatus.PREPARED,
                     url="https://jobs.ashbyhq.com/bjakcareer/a88550fb")
    reviewed.status_conflict = True
    reviewed.conflict_detail = "Package note says not submitted. Needs operator confirmation."
    confirmed = entry("BJAK", "Applied AI Engineer (US)", HistoryStatus.SUBMITTED,
                      url="https://jobs.ashbyhq.com/bjakcareer/a88550fb",
                      confidence=CONFIDENCE_SUBMISSION_LOG)

    merged = merge_entries([reviewed], [confirmed])

    assert len(merged) == 1
    assert merged[0].status is HistoryStatus.SUBMITTED
    assert merged[0].status_conflict is False
    assert merged[0].conflict_detail is None


def test_a_weaker_win_still_inherits_the_conflict():
    """The narrowing above must not become a general amnesty. Only a submission-log SUBMITTED
    resolves; anything else still carries the flag forward."""
    reviewed = entry("Somewhere Ltd", "Backend Engineer", HistoryStatus.PREPARED)
    reviewed.status_conflict = True
    reviewed.conflict_detail = "Two records disagree about whether this was sent."
    scanned = entry("Somewhere Ltd", "Backend Engineer", HistoryStatus.SKIPPED,
                    confidence=CONFIDENCE_PARSED)

    merged = merge_entries([reviewed], [scanned])

    assert merged[0].status_conflict is True
    assert merged[0].conflict_detail == "Two records disagree about whether this was sent."
