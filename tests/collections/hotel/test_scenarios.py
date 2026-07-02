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


def test_overall_dropoff_is_about_18pct(hotel: dict[str, pl.DataFrame]) -> None:
    res = hotel["reservations"]
    dropoff = float((res["status"] != "honoured").sum()) / res.height
    assert 0.15 < dropoff < 0.21


def test_ota_has_the_highest_dropoff(hotel: dict[str, pl.DataFrame]) -> None:
    by_channel = (
        hotel["reservations"]
        .group_by("channel")
        .agg((pl.col("status") != "honoured").mean().alias("dropoff"))
        .sort("dropoff", descending=True)
    )
    assert by_channel["channel"][0] == "ota"


def test_walk_in_has_the_lowest_dropoff(hotel: dict[str, pl.DataFrame]) -> None:
    by_channel = (
        hotel["reservations"]
        .group_by("channel")
        .agg((pl.col("status") != "honoured").mean().alias("dropoff"))
        .sort("dropoff")
    )
    assert by_channel["channel"][0] == "walk_in"


def _lead_days() -> pl.Expr:
    return (pl.col("check_in_date") - pl.col("booked_date")).dt.total_days()


def test_lead_time_is_right_skewed_overall(hotel: dict[str, pl.DataFrame]) -> None:
    stats = hotel["reservations"].select(
        _lead_days().mean().alias("mean"), _lead_days().median().alias("median")
    )
    assert stats["mean"][0] > stats["median"][0]


def test_ota_lead_time_tail_exceeds_direct(hotel: dict[str, pl.DataFrame]) -> None:
    by_channel = (
        hotel["reservations"].group_by("channel").agg(_lead_days().quantile(0.95).alias("p95"))
    )
    p95 = dict(zip(by_channel["channel"], by_channel["p95"], strict=True))
    assert p95["ota"] > 2 * p95["direct"]


def _upgrade_rate_by_channel(hotel: dict[str, pl.DataFrame]) -> pl.DataFrame:
    eligible = hotel["stays"].filter(pl.col("room_type") != "Penthouse")
    channel = hotel["reservations"].select("reservation_id", "channel")
    upgraded = hotel["room_upgrades"].select("stay_id").with_columns(pl.lit(1).alias("up"))
    return (
        eligible.join(channel, on="reservation_id")
        .join(upgraded, on="stay_id", how="left")
        .group_by("channel")
        .agg((pl.col("up").fill_null(0).mean()).alias("rate"))
    )


def test_overall_upgrade_rate_is_about_15pct(hotel: dict[str, pl.DataFrame]) -> None:
    eligible = hotel["stays"].filter(pl.col("room_type") != "Penthouse").height
    rate = hotel["room_upgrades"].height / eligible
    assert 0.12 < rate < 0.18


def test_direct_upgrade_rate_exceeds_ota(hotel: dict[str, pl.DataFrame]) -> None:
    rates = _upgrade_rate_by_channel(hotel)
    by_channel = dict(zip(rates["channel"], rates["rate"], strict=True))
    assert by_channel["direct"] > 2 * by_channel["ota"]


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
