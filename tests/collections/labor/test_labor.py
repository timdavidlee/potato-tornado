"""Tests for the labor collection.

These pin the realism invariants from ``realism-guidance.md`` (referential
integrity, temporal ordering, arithmetic identities, non-negativity) — the rules
that must hold regardless of any teaching signal. Subset-signal magnitudes live in
``test_scenarios.py``.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def labor() -> dict[str, pl.DataFrame]:
    return generate("labor", GenerationConfig(seed=13, scale=0.3))


def test_assignment_employee_ids_reference_employees(labor: dict[str, pl.DataFrame]) -> None:
    emp_ids = set(labor["employees"]["employee_id"].to_list())
    assert set(labor["assignments"]["employee_id"].to_list()) <= emp_ids


def test_assignment_shift_ids_reference_shifts(labor: dict[str, pl.DataFrame]) -> None:
    shift_ids = set(labor["shifts"]["shift_id"].to_list())
    assert set(labor["assignments"]["shift_id"].to_list()) <= shift_ids


def test_time_entries_are_one_to_one_with_assignments(labor: dict[str, pl.DataFrame]) -> None:
    assert labor["time_entries"].height == labor["assignments"].height


def test_rostering_stays_within_department(labor: dict[str, pl.DataFrame]) -> None:
    cross_dept = (
        labor["assignments"]
        .join(labor["employees"].select(["employee_id", "department_id"]), on="employee_id")
        .join(
            labor["shifts"]
            .select(["shift_id", "department_id"])
            .rename({"department_id": "shift_department_id"}),
            on="shift_id",
        )
        .filter(pl.col("department_id") != pl.col("shift_department_id"))
    )
    assert cross_dept.height == 0


def test_no_show_entries_have_null_clock_in(labor: dict[str, pl.DataFrame]) -> None:
    no_shows = labor["time_entries"].filter(labor["time_entries"]["no_show"])
    assert no_shows["clock_in"].null_count() == no_shows.height


def test_no_show_entries_have_null_worked_hours(labor: dict[str, pl.DataFrame]) -> None:
    no_shows = labor["time_entries"].filter(labor["time_entries"]["no_show"])
    assert no_shows["worked_hours"].null_count() == no_shows.height


def test_worked_entries_have_populated_clocks(labor: dict[str, pl.DataFrame]) -> None:
    worked = labor["time_entries"].filter(~labor["time_entries"]["no_show"])
    populated = worked.filter(
        pl.col("clock_in").is_not_null()
        & pl.col("clock_out").is_not_null()
        & pl.col("worked_hours").is_not_null()
    )
    assert populated.height == worked.height


def test_clock_out_is_after_clock_in(labor: dict[str, pl.DataFrame]) -> None:
    worked = labor["time_entries"].filter(~labor["time_entries"]["no_show"])
    assert worked.filter(pl.col("clock_out") <= pl.col("clock_in")).height == 0


def test_worked_hours_never_below_planned(labor: dict[str, pl.DataFrame]) -> None:
    worked = labor["time_entries"].filter(~labor["time_entries"]["no_show"])
    assert worked.filter(pl.col("worked_hours") < pl.col("planned_hours")).height == 0


def test_planned_end_matches_start_plus_hours(labor: dict[str, pl.DataFrame]) -> None:
    shifts = labor["shifts"]
    mismatched = shifts.filter(
        (pl.col("planned_end") - pl.col("planned_start")).dt.total_hours()
        != pl.col("planned_hours")
    )
    assert mismatched.height == 0


def test_planned_hours_are_from_the_allowed_set(labor: dict[str, pl.DataFrame]) -> None:
    assert set(labor["shifts"]["planned_hours"].unique().to_list()) <= {8, 10, 12}


def test_required_headcount_within_bounds(labor: dict[str, pl.DataFrame]) -> None:
    out_of_range = labor["shifts"].filter(
        (pl.col("required_headcount") < 2) | (pl.col("required_headcount") > 8)
    )
    assert out_of_range.height == 0


def test_hourly_rate_is_positive(labor: dict[str, pl.DataFrame]) -> None:
    assert labor["employees"].filter(pl.col("hourly_rate") <= 0).height == 0


def test_hire_dates_are_within_window(labor: dict[str, pl.DataFrame]) -> None:
    # Fixture uses the default window, whose exclusive upper bound is 2025-01-01.
    assert labor["employees"].filter(pl.col("hire_date") >= date(2025, 1, 1)).height == 0


def test_scale_increases_employee_count() -> None:
    small = generate("labor", GenerationConfig(seed=1, scale=0.2))["employees"].height
    large = generate("labor", GenerationConfig(seed=1, scale=1.0))["employees"].height
    assert large > small
