"""The ``demand_forecast`` table: forecast vs. actual occupancy per day."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext


def build_demand_forecast(ctx: GenContext) -> pl.DataFrame:
    props = ctx.table("properties")
    stays = ctx.table("stays")

    # Actual occupied room-nights per property per date, derived from stays.
    occupancy = _occupancy_by_day(stays)

    rows_prop: list[str] = []
    rows_date: list[object] = []
    rows_actual: list[int] = []
    rows_forecast: list[int] = []
    rng = ctx.rng.numpy
    span = ctx.config.span_days
    for pid, total_rooms in zip(
        props["property_id"].to_list(), props["total_rooms"].to_list(), strict=True
    ):
        for offset in range(span):
            day = ctx.config.start_date + timedelta(days=offset)
            actual = occupancy.get((pid, day), 0)
            actual = min(actual, total_rooms)
            # Forecast is the actual perturbed by noise (imperfect foresight).
            # Weekend demand is harder to call, so it carries a wider error band.
            sd = 0.22 if day.weekday() >= 5 else 0.09
            forecast = int(np.clip(round(actual * rng.normal(1.0, sd)), 0, total_rooms))
            rows_prop.append(pid)
            rows_date.append(day)
            rows_actual.append(actual)
            rows_forecast.append(forecast)

    return pl.DataFrame(
        {
            "property_id": rows_prop,
            "forecast_date": rows_date,
            "forecast_occupied_rooms": rows_forecast,
            "actual_occupied_rooms": rows_actual,
        }
    )


def _occupancy_by_day(stays: pl.DataFrame) -> dict[tuple[str, object], int]:
    occupancy: dict[tuple[str, object], int] = {}
    for pid, ci, nights in zip(
        stays["property_id"].to_list(),
        stays["actual_check_in"].to_list(),
        stays["actual_nights"].to_list(),
        strict=True,
    ):
        for offset in range(int(nights)):
            key = (pid, ci + timedelta(days=offset))
            occupancy[key] = occupancy.get(key, 0) + 1
    return occupancy
