"""Scenario signals for the labor collection (the teaching 'answer key')."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def labor() -> dict[str, pl.DataFrame]:
    return generate("labor", GenerationConfig(seed=7, scale=0.5))


def test_night_no_show_rate_exceeds_day_rate(labor: dict[str, pl.DataFrame]) -> None:
    by_window = (
        labor["time_entries"]
        .join(labor["shifts"].select(["shift_id", "shift_window"]), on="shift_id", how="left")
        .group_by("shift_window")
        .agg(pl.col("no_show").mean().alias("rate"))
    )
    rates = dict(zip(by_window["shift_window"], by_window["rate"], strict=True))
    day_rate = max(rates["morning"], rates["afternoon"])
    assert rates["night"] > 2 * day_rate


def test_kitchen_dominates_overtime_hours(labor: dict[str, pl.DataFrame]) -> None:
    worked = (
        labor["time_entries"]
        .filter(~pl.col("no_show"))
        .join(labor["shifts"].select(["shift_id", "department_id"]), on="shift_id", how="left")
        .join(
            labor["departments"].select(["department_id", "name"]), on="department_id", how="left"
        )
        .with_columns((pl.col("worked_hours") - pl.col("planned_hours")).alias("overtime"))
    )
    kitchen_overtime = float(worked.filter(pl.col("name") == "Kitchen")["overtime"].sum())
    total_overtime = float(worked["overtime"].sum())
    assert kitchen_overtime / total_overtime > 0.25
