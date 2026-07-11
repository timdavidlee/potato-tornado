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


def test_over_capacity_concentrates_in_standard(hotel: dict[str, pl.DataFrame]) -> None:
    # Over-capacity booking rate falls monotonically up the class ladder — the inversion of
    # the party-size ladder — concentrating in Standards and vanishing at the Penthouse
    # (seat 6, party_size capped at 6, so exactly zero). See
    # scenarios/over-capacity-bookings-concentrate-in-standards.md.
    cap = hotel["room_types"].select("room_type", "max_occupancy").unique()
    rates = (
        hotel["reservations"]
        .join(cap, on="room_type")
        .group_by("room_type")
        .agg((pl.col("party_size") > pl.col("max_occupancy")).mean().alias("over_rate"))
    )
    over = dict(zip(rates["room_type"], rates["over_rate"], strict=True))
    ladder = [over["Standard"], over["Deluxe"], over["Suite"], over["Penthouse"]]
    assert ladder[0] > ladder[1] > ladder[2] > ladder[3] == 0.0 and ladder[0] - ladder[3] > 0.2


def test_revpar_climbs_up_room_class_ladder(hotel: dict[str, pl.DataFrame]) -> None:
    # RevPAR (revenue per available room-night) climbs monotonically up the ladder even as
    # occupancy falls down it — the premium classes out-yield Standards despite lower
    # occupancy. See scenarios/revpar-climbs-as-occupancy-falls.md.
    span_days = (
        hotel["reservations"]
        .select((pl.col("check_in_date").max() - pl.col("check_in_date").min()).dt.total_days())
        .item()
    )
    sold = (
        hotel["stays"]
        .group_by("room_type")
        .agg(
            pl.col("actual_nights").sum().alias("nights_sold"),
            pl.col("room_revenue").sum().alias("rev"),
        )
    )
    avail = hotel["room_types"].group_by("room_type").agg(pl.col("room_count").sum().alias("rooms"))
    metrics = sold.join(avail, on="room_type").with_columns(
        (pl.col("nights_sold") / (pl.col("rooms") * span_days)).alias("occupancy"),
        (pl.col("rev") / (pl.col("rooms") * span_days)).alias("revpar"),
    )
    revpar = dict(zip(metrics["room_type"], metrics["revpar"], strict=True))
    occ = dict(zip(metrics["room_type"], metrics["occupancy"], strict=True))
    rp = [revpar["Standard"], revpar["Deluxe"], revpar["Suite"], revpar["Penthouse"]]
    assert (
        rp[0] < rp[1] < rp[2] < rp[3] and occ["Standard"] > occ["Penthouse"] and rp[3] > 2.5 * rp[0]
    )
