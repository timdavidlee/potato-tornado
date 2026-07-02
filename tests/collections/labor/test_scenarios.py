"""Scenario signals for the labor collection (the teaching 'answer key')."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.collections.labor.constants import ROLES
from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def labor() -> dict[str, pl.DataFrame]:
    return generate("labor", GenerationConfig(seed=7, scale=0.5))


def test_pay_ladder_is_monotone_by_role(labor: dict[str, pl.DataFrame]) -> None:
    by_role = labor["employees"].group_by("role").agg(pl.col("hourly_rate").mean().alias("avg"))
    means = dict(zip(by_role["role"], by_role["avg"], strict=True))
    ordered = [means[r] for r in ROLES]
    assert ordered == sorted(ordered)


def test_department_base_outweighs_a_seniority_rung(labor: dict[str, pl.DataFrame]) -> None:
    emp = labor["employees"].join(
        labor["departments"].select("department_id", "name", "base_hourly_rate"),
        on="department_id",
    )
    ranked = labor["departments"].sort("base_hourly_rate")
    top_base, bottom_base = ranked["name"][-1], ranked["name"][0]
    junior_hi = emp.filter((pl.col("name") == top_base) & (pl.col("role") == "Associate"))[
        "hourly_rate"
    ]
    senior_lo = emp.filter(
        (pl.col("name") == bottom_base) & (pl.col("role") == "Senior Associate")
    )["hourly_rate"]
    junior_hi_avg = float(junior_hi.sum()) / junior_hi.len()
    senior_lo_avg = float(senior_lo.sum()) / senior_lo.len()
    assert junior_hi_avg > senior_lo_avg


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


def test_satellite_projects_run_more_off_site_than_the_hub(labor: dict[str, pl.DataFrame]) -> None:
    by_city = (
        labor["project_members"]
        .join(
            labor["employees"].select("employee_id", "location_city"),
            on="employee_id",
            how="left",
        )
        .join(
            labor["projects"]
            .select("project_id", "location_city")
            .rename({"location_city": "project_city"}),
            on="project_id",
            how="left",
        )
        .with_columns((pl.col("location_city") != pl.col("project_city")).alias("off_site"))
        .group_by("project_city")
        .agg(pl.col("off_site").mean().alias("rate"))
    )
    rates = dict(zip(by_city["project_city"], by_city["rate"], strict=True))
    satellite_rate = max(rates["Atlanta"], rates["Denver"])
    assert satellite_rate > 2 * rates["New York"]


def test_engineering_dominates_overtime_hours(labor: dict[str, pl.DataFrame]) -> None:
    worked = (
        labor["time_entries"]
        .filter(~pl.col("no_show"))
        .join(labor["shifts"].select(["shift_id", "department_id"]), on="shift_id", how="left")
        .join(
            labor["departments"].select(["department_id", "name"]), on="department_id", how="left"
        )
        .with_columns((pl.col("worked_hours") - pl.col("planned_hours")).alias("overtime"))
    )
    engineering_overtime = float(
        worked.filter(pl.col("name") == "Software Engineering")["overtime"].sum()
    )
    total_overtime = float(worked["overtime"].sum())
    assert engineering_overtime / total_overtime > 0.25
