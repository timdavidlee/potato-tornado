"""Tests for the labor collection."""

from __future__ import annotations

import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def labor() -> dict:
    return generate("labor", GenerationConfig(seed=13, scale=0.3))


def test_assignment_employee_ids_reference_employees(labor: dict) -> None:
    emp_ids = set(labor["employees"]["employee_id"].to_list())
    assert set(labor["assignments"]["employee_id"].to_list()) <= emp_ids


def test_assignment_shift_ids_reference_shifts(labor: dict) -> None:
    shift_ids = set(labor["shifts"]["shift_id"].to_list())
    assert set(labor["assignments"]["shift_id"].to_list()) <= shift_ids


def test_time_entries_are_one_to_one_with_assignments(labor: dict) -> None:
    assert labor["time_entries"].height == labor["assignments"].height


def test_no_show_entries_have_null_clock_in(labor: dict) -> None:
    no_shows = labor["time_entries"].filter(labor["time_entries"]["no_show"])
    assert no_shows["clock_in"].null_count() == no_shows.height


def test_scale_increases_employee_count() -> None:
    small = generate("labor", GenerationConfig(seed=1, scale=0.2))["employees"].height
    large = generate("labor", GenerationConfig(seed=1, scale=1.0))["employees"].height
    assert large > small
