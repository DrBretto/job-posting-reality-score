"""The report measures its own runtime and says how much budget was left.

Why this exists, stated as the incident rather than as a feature: on 2026-09-26 the report finished
in 80.08 seconds against a 90-second timeout and was recorded as the recovery's success. The corpus
grew by about two thirds over the next two days and the next three scheduled rounds produced no
report at all. The margin was gone before anything failed, and the only place the duration appeared
was the Lambda REPORT log line, which nothing reads. These tests pin the number into the artifact
the operator actually opens.
"""

from __future__ import annotations

import pytest

from src.report.handler import _runtime_line, assert_no_banned_vocab, measure_runtime


def test_headroom_is_reported_against_the_configured_budget():
    r = measure_runtime(started_at=100.0, now=180.08, budget_seconds=90.0, population=813)
    assert r["elapsed_seconds"] == 80.08
    assert r["timeout_seconds"] == 90.0
    assert r["headroom_seconds"] == 9.92
    assert r["headroom_pct"] == 11.0
    assert r["input_population"] == 813


def test_the_success_that_was_about_to_fail_reads_as_nearly_out_of_budget():
    """The 2026-09-26 run, which was recorded as a success with no qualifier of any kind."""
    r = measure_runtime(started_at=0.0, now=80.08, budget_seconds=90.0, population=813)
    assert r["headroom_pct"] < 15.0
    assert "9.92s / 11.0% left" in _runtime_line(r)


def test_cost_per_thousand_postings_is_reported_so_growth_is_visible():
    """The dominant stage is quadratic in corpus size, so this rate RISES as the corpus grows.
    A flat elapsed-seconds number alone cannot show that; this is the number that can."""
    small = measure_runtime(started_at=0.0, now=20.0, budget_seconds=300.0, population=800)
    large = measure_runtime(started_at=0.0, now=55.0, budget_seconds=300.0, population=1344)
    assert small["per_1k_population_seconds"] == 25.0
    assert large["per_1k_population_seconds"] == 40.92
    assert large["per_1k_population_seconds"] > small["per_1k_population_seconds"]


def test_a_runtime_with_no_budget_still_reports_what_it_measured():
    """A context that cannot answer how long it has is not a report failure."""
    r = measure_runtime(started_at=0.0, now=12.5, budget_seconds=None, population=100)
    assert r["elapsed_seconds"] == 12.5
    assert "timeout_seconds" not in r
    assert "headroom_seconds" not in r
    assert _runtime_line(r) == "Runtime: ran in 12.5s, over 100 postings."


def test_an_empty_population_does_not_divide_by_zero():
    r = measure_runtime(started_at=0.0, now=3.0, budget_seconds=90.0, population=0)
    assert "per_1k_population_seconds" not in r
    assert r["elapsed_seconds"] == 3.0


def test_a_negative_clock_delta_is_floored_rather_than_reported_as_negative_work():
    r = measure_runtime(started_at=10.0, now=9.0, budget_seconds=90.0, population=5)
    assert r["elapsed_seconds"] == 0.0


@pytest.mark.parametrize("population,elapsed", [(1, 0.5), (5000, 250.0), (1344, 21.3)])
def test_the_rendered_line_never_trips_the_vocabulary_guard(population, elapsed):
    """The line is appended AFTER render_report's own guard, so it is checked on its own terms."""
    r = measure_runtime(started_at=0.0, now=elapsed, budget_seconds=300.0, population=population)
    assert_no_banned_vocab(_runtime_line(r))
