"""Differ golden-fixture tests: the disappearance invariant + grace + mass-drop + M3 guards."""

from __future__ import annotations

from datetime import timedelta

import pytest

from src.common.models import ChangeEventType, JobLifecycleState, SnapshotStatus
from src.differ.handler import DiffState, diff_source
from tests.conftest import FIXED_NOW, make_job, make_snapshot


def _run(state, status, jobs, *, run_id, n=None, fetched_at=FIXED_NOW):
    snap = make_snapshot(status, n=n if n is not None else len(jobs), fetched_at=fetched_at)
    return diff_source(state, snap, jobs, run_id=run_id, today=fetched_at)


def _types(events):
    return [e.event_type for e in events]


def test_t1_disappearance_invariant_fetch_failed():
    """T1: prev SUCCESS(10) + current FETCH_FAILED -> zero disappeared, states frozen, one fail event."""
    jobs = [make_job(f"j{i}") for i in range(10)]
    r1 = _run(None, SnapshotStatus.SUCCESS, jobs, run_id="d1")
    assert r1.state.success_count_history == [10]

    r2 = _run(r1.state, SnapshotStatus.FETCH_FAILED, [], run_id="d2")

    assert r2.frozen is True
    assert _types(r2.events) == [ChangeEventType.SOURCE_FETCH_FAILED]
    assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in r2.events)
    # all 10 states unchanged, grace clocks not advanced
    for rec in r2.state.jobs.values():
        assert rec.state == JobLifecycleState.ACTIVE
        assert rec.absence_count == 0
    # current/ not overwritten on a frozen run
    assert r2.current_jobs is None
    # baseline history untouched by the failure
    assert r2.state.success_count_history == [10]


def test_partial_also_freezes():
    """PARTIAL is frozen exactly like FETCH_FAILED (source-response-partial, zero removals)."""
    jobs = [make_job(f"j{i}") for i in range(4)]
    r1 = _run(None, SnapshotStatus.SUCCESS, jobs, run_id="d1")
    r2 = _run(r1.state, SnapshotStatus.PARTIAL, [], run_id="d2")
    assert _types(r2.events) == [ChangeEventType.SOURCE_RESPONSE_PARTIAL]
    assert all(rec.absence_count == 0 for rec in r2.state.jobs.values())


def test_t3_grace_two_consecutive_success():
    """Absent 1 SUCCESS -> PENDING_REMOVAL (no disappeared). Absent 2nd consecutive -> disappeared."""
    jobs = [make_job("a"), make_job("b")]
    r1 = _run(None, SnapshotStatus.SUCCESS, jobs, run_id="d1")
    # day2: 'b' absent
    r2 = _run(r1.state, SnapshotStatus.SUCCESS, [make_job("a")], run_id="d2")
    assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in r2.events)
    assert r2.state.jobs["greenhouse:acme#b"].state == JobLifecycleState.PENDING_REMOVAL
    # day3: 'b' absent again -> disappeared
    r3 = _run(r2.state, SnapshotStatus.SUCCESS, [make_job("a")], run_id="d3")
    dis = [e for e in r3.events if e.event_type == ChangeEventType.DISAPPEARED]
    assert len(dis) == 1 and dis[0].job_id == "greenhouse:acme#b"
    assert r3.state.jobs["greenhouse:acme#b"].state == JobLifecycleState.DISAPPEARED


def test_t4_outage_through_grace_does_not_count():
    """T4: SUCCESS(has) -> FAIL -> FAIL -> SUCCESS(missing): failures don't count toward grace."""
    jobs = [make_job("a"), make_job("b")]
    r1 = _run(None, SnapshotStatus.SUCCESS, jobs, run_id="d1")
    r2 = _run(r1.state, SnapshotStatus.FETCH_FAILED, [], run_id="d2")
    r3 = _run(r2.state, SnapshotStatus.FETCH_FAILED, [], run_id="d3")
    # final SUCCESS with 'b' missing
    r4 = _run(r3.state, SnapshotStatus.SUCCESS, [make_job("a")], run_id="d4")
    # only ONE successful absence -> PENDING_REMOVAL, NOT disappeared
    assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in r4.events)
    assert r4.state.jobs["greenhouse:acme#b"].state == JobLifecycleState.PENDING_REMOVAL
    assert r4.state.jobs["greenhouse:acme#b"].absence_count == 1


def test_t8_mass_drop_guard_empty_after_nonempty():
    """T8: prev SUCCESS(10), current success-status 0 jobs -> SUSPECT, NOT 10 disappeared."""
    jobs = [make_job(f"j{i}") for i in range(10)]
    r1 = _run(None, SnapshotStatus.SUCCESS, jobs, run_id="d1")
    r2 = _run(r1.state, SnapshotStatus.EMPTY_SUCCESS, [], run_id="d2", n=0)
    assert r2.suspect is True
    assert any(e.event_type == ChangeEventType.SOURCE_SUSPECT for e in r2.events)
    assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in r2.events)
    # baseline NOT poisoned by the guarded drop
    assert r2.state.success_count_history == [10]


def test_m3_cumulative_bleed_50_then_50():
    """M3: 100 -> 50 (legit, under 60%) -> 25 (legit single-step) but cumulative 75% -> SUSPECT."""
    day1 = [make_job(f"j{i}") for i in range(100)]
    r1 = _run(None, SnapshotStatus.SUCCESS, day1, run_id="d1")
    day2 = [make_job(f"j{i}") for i in range(50)]
    r2 = _run(r1.state, SnapshotStatus.SUCCESS, day2, run_id="d2")
    # day2 is a legit single-step drop: not suspect, no disappeared yet (grace)
    assert r2.suspect is False
    assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in r2.events)

    day3 = [make_job(f"j{i}") for i in range(25)]
    r3 = _run(r2.state, SnapshotStatus.SUCCESS, day3, run_id="d3")
    # cumulative guard trips -> SUSPECT, removals suppressed (no false disappeared for the bleed)
    assert r3.suspect is True
    assert "cumulative" in (r3.suspect_reason or "")
    assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in r3.events)


def test_m3_silent_subset_success():
    """M3: a well-formed 200 that silently omits a whole department -> SUSPECT, no disappeared."""
    eng = [make_job(f"e{i}", department="engineering") for i in range(5)]
    sales = [make_job(f"s{i}", department="sales") for i in range(5)]
    r1 = _run(None, SnapshotStatus.SUCCESS, eng + sales, run_id="d1")
    # day2: sales department entirely omitted (HTTP 200, under 60% single-step, no cumulative)
    r2 = _run(r1.state, SnapshotStatus.SUCCESS, eng, run_id="d2")
    assert r2.suspect is True
    assert "silent-subset" in (r2.suspect_reason or "")
    assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in r2.events)


def test_t5_content_hash_stable_no_material_change():
    """Re-serialized identical content -> no-material-change (content_hash stable)."""
    r1 = _run(None, SnapshotStatus.SUCCESS, [make_job("a")], run_id="d1")
    r2 = _run(r1.state, SnapshotStatus.SUCCESS, [make_job("a")], run_id="d2")
    assert any(e.event_type == ChangeEventType.NO_MATERIAL_CHANGE for e in r2.events)
    assert not any(e.event_type == ChangeEventType.MATERIALLY_CHANGED for e in r2.events)


def test_t6_salary_change_fires_only_salary_event():
    """Only salary changes -> salary-changed fires; no materially-changed."""
    r1 = _run(None, SnapshotStatus.SUCCESS, [make_job("a", description="python role", salary_text="")], run_id="d1")
    changed = make_job("a", description="python role", salary_text="$120,000 - $150,000")
    r2 = _run(r1.state, SnapshotStatus.SUCCESS, [changed], run_id="d2")
    types = _types(r2.events)
    assert ChangeEventType.SALARY_CHANGED in types
    assert ChangeEventType.MATERIALLY_CHANGED not in types


def test_probable_repost_links_on_requisition_id():
    """A new job matching a recently-disappeared job's requisition_id -> probable-repost."""
    # use a co-present anchor job so 'old' disappearing is not a mass drop that trips the guard
    jobs_full = [make_job("old", requisition_id="REQ-1", title="Data Engineer"), make_job("anchor")]
    r1b = _run(None, SnapshotStatus.SUCCESS, jobs_full, run_id="d1")
    r2b = _run(r1b.state, SnapshotStatus.SUCCESS, [make_job("anchor")], run_id="d2")  # old absent #1
    r3b = _run(r2b.state, SnapshotStatus.SUCCESS, [make_job("anchor")], run_id="d3")  # old absent #2 -> disappeared
    assert any(e.event_type == ChangeEventType.DISAPPEARED for e in r3b.events)
    # new job same requisition_id appears -> probable-repost
    new = make_job("newid", requisition_id="REQ-1", title="Data Engineer")
    r4b = _run(r3b.state, SnapshotStatus.SUCCESS, [make_job("anchor"), new], run_id="d4")
    reposts = [e for e in r4b.events if e.event_type == ChangeEventType.PROBABLE_REPOST]
    assert len(reposts) == 1
    assert reposts[0].repost_score >= 0.7
    assert reposts[0].linked_job_id == "greenhouse:acme#old"


def test_cold_start_first_run_all_first_seen_no_removals():
    """m1: first run -> all first-seen, zero removals, mass-drop guard inert (no baseline)."""
    jobs = [make_job("a"), make_job("b"), make_job("c")]
    r = _run(None, SnapshotStatus.SUCCESS, jobs, run_id="d1")
    assert sum(1 for e in r.events if e.event_type == ChangeEventType.FIRST_SEEN) == 3
    assert not any(e.event_type == ChangeEventType.DISAPPEARED for e in r.events)
    assert r.suspect is False
