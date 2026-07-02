"""Scenario signals for the hotel collection (the teaching 'answer key')."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def hotel() -> dict[str, pl.DataFrame]:
    return generate("hotel", GenerationConfig(seed=21, scale=0.5))


def test_ota_leads_overall(hotel: dict[str, pl.DataFrame]) -> None:
    counts = hotel["reservations"]["channel"].value_counts(sort=True)
    assert counts["channel"][0] == "ota"


def test_direct_is_modal_channel_for_upper_tiers(hotel: dict[str, pl.DataFrame]) -> None:
    upper = hotel["reservations"].filter(pl.col("room_type").is_in(["Suite", "Penthouse"]))
    counts = upper["channel"].value_counts(sort=True)
    assert counts["channel"][0] == "direct"


def test_weekend_forecast_error_exceeds_weekday(hotel: dict[str, pl.DataFrame]) -> None:
    by_kind = (
        hotel["demand_forecast"]
        .filter(pl.col("actual_occupied_rooms") > 0)
        .with_columns(
            (pl.col("forecast_date").dt.weekday() >= 6).alias("weekend"),
            (
                (pl.col("forecast_occupied_rooms") - pl.col("actual_occupied_rooms")).abs()
                / pl.col("actual_occupied_rooms")
            ).alias("ape"),
        )
        .group_by("weekend")
        .agg(pl.col("ape").mean().alias("mape"))
    )
    mape = dict(zip(by_kind["weekend"], by_kind["mape"], strict=True))
    assert mape[True] > 2 * mape[False]
