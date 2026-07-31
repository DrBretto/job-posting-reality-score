"""Report tests: run-health header states, never-fake vocab guard, evidence citation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.common.models import ChangeEvent, ChangeEventType, RunHealth
from src.report.handler import (
    NeverFakeViolation,
    ReportInput,
    assert_no_banned_vocab,
    compute_run_health,
    render_report,
)

DT = "2026-07-24"


def _event(etype, *, job_id=None, source_id="greenhouse:stripe", notes=None, eid="e1"):
    return ChangeEvent(
        event_id=eid, event_type=etype, source_id=source_id, job_id=job_id,
        run_id=DT, as_of=datetime(2026, 7, 24, tzinfo=timezone.utc), snapshot_id="snap-1",
        notes=notes,
    )


def test_verified_quiet_header():
    inp = ReportInput(
        run_id=DT, dt=DT,
        expected_sources=["greenhouse:stripe"], succeeded_sources=["greenhouse:stripe"],
        manifest_present=True, events=[],
    )
    health, missing = compute_run_health(inp)
    assert health == RunHealth.VERIFIED_QUIET and missing == []
    md, js = render_report(inp)
    assert "VERIFIED-QUIET" in md
    assert js["run_health"] == "VERIFIED-QUIET"


def test_incomplete_names_the_failed_sources():
    inp = ReportInput(
        run_id=DT, dt=DT,
        expected_sources=["greenhouse:stripe", "greenhouse:figma"],
        succeeded_sources=["greenhouse:stripe"],
        manifest_present=True,
        events=[_event(ChangeEventType.SOURCE_FETCH_FAILED, source_id="greenhouse:figma")],
    )
    health, missing = compute_run_health(inp)
    assert health == RunHealth.INCOMPLETE
    assert missing == ["greenhouse:figma"]
    md, js = render_report(inp)
    assert "INCOMPLETE" in md and "greenhouse:figma" in md
    assert js["incomplete_sources"] == ["greenhouse:figma"]


def test_no_run_when_manifest_absent():
    inp = ReportInput(run_id=DT, dt=DT, expected_sources=["greenhouse:stripe"],
                      succeeded_sources=[], manifest_present=False)
    health, _ = compute_run_health(inp)
    assert health == RunHealth.NO_RUN
    md, js = render_report(inp)
    assert "NO-RUN" in md
    assert js["run_health"] == "NO-RUN"


def test_change_cites_evidence():
    inp = ReportInput(
        run_id=DT, dt=DT, expected_sources=["greenhouse:stripe"], succeeded_sources=["greenhouse:stripe"],
        events=[_event(ChangeEventType.SALARY_CHANGED, job_id="greenhouse:stripe#7", eid="e-sal")],
    )
    md, _ = render_report(inp)
    assert "greenhouse:stripe#7" in md
    assert "snapshot=snap-1" in md and "event=e-sal" in md  # every change cites evidence


def test_never_fake_guard_rejects_banned_tokens():
    for bad in ("This job is fake", "a ghost job", "clearly a scam", "the posting is fraudulent",
                "a real vacancy", "they are lying", "fabricated listing"):
        with pytest.raises(NeverFakeViolation):
            assert_no_banned_vocab(bad)


def test_never_fake_guard_allows_product_vocabulary():
    # word-boundary matching: 'Reality', 'really', 'already' must NOT trip the guard
    assert_no_banned_vocab("Job Posting Reality Score — really already surfaced")


def test_render_rejects_banned_token_smuggled_via_event_notes():
    """A banned token anywhere in the rendered JSON (incl. event notes) must be rejected."""
    inp = ReportInput(
        run_id=DT, dt=DT, expected_sources=["greenhouse:stripe"], succeeded_sources=["greenhouse:stripe"],
        events=[_event(ChangeEventType.MATERIALLY_CHANGED, job_id="greenhouse:stripe#1",
                       notes="this looks like a fake posting")],
    )
    with pytest.raises(NeverFakeViolation):
        render_report(inp)
