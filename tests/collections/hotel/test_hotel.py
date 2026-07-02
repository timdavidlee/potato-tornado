"""Tests for the hotel collection."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def hotel() -> dict:
    return generate("hotel", GenerationConfig(seed=21, scale=0.3))


@pytest.fixture(scope="module")
def hotel_full() -> dict:
    # Full scale: occupancy reaches double digits, so the forecast error survives the
    # integer rounding that damps it at the smaller shared-fixture scale.
    return generate("hotel", GenerationConfig(seed=21, scale=1.0))


def test_stays_derive_only_from_honoured_reservations(hotel: dict) -> None:
    honoured = set(
        hotel["reservations"].filter(pl.col("status") == "honoured")["reservation_id"].to_list()
    )
    assert set(hotel["stays"]["reservation_id"].to_list()) <= honoured


def test_service_orders_reference_stays(hotel: dict) -> None:
    stay_ids = set(hotel["stays"]["stay_id"].to_list())
    assert set(hotel["service_orders"]["stay_id"].to_list()) <= stay_ids


def test_room_upgrades_reference_stays(hotel: dict) -> None:
    stay_ids = set(hotel["stays"]["stay_id"].to_list())
    assert set(hotel["room_upgrades"]["stay_id"].to_list()) <= stay_ids


def test_upgrade_fee_stays_below_full_rate_delta(hotel: dict) -> None:
    upgrades = hotel["room_upgrades"]
    over = upgrades.filter(pl.col("upgrade_fee") >= pl.col("rate_delta") * pl.col("nights"))
    assert over.height == 0


def test_upgrades_never_originate_from_the_top_room_class(hotel: dict) -> None:
    assert hotel["room_upgrades"].filter(pl.col("from_room_type") == "Penthouse").height == 0


def test_stay_changes_reference_stays(hotel: dict) -> None:
    stay_ids = set(hotel["stays"]["stay_id"].to_list())
    assert set(hotel["stay_changes"]["stay_id"].to_list()) <= stay_ids


def test_stay_change_type_matches_night_delta_sign(hotel: dict) -> None:
    changes = hotel["stay_changes"]
    mismatched = changes.filter(
        ((pl.col("change_type") == "early_checkout") & (pl.col("nights_delta") >= 0))
        | ((pl.col("change_type") == "extension") & (pl.col("nights_delta") <= 0))
    )
    assert mismatched.height == 0


def test_extensions_outnumber_early_checkouts(hotel: dict) -> None:
    changes = hotel["stay_changes"]
    extensions = changes.filter(pl.col("change_type") == "extension").height
    early = changes.filter(pl.col("change_type") == "early_checkout").height
    assert extensions > early


def test_ancillary_spend_scales_with_stay_length(hotel: dict) -> None:
    # Longer stays accrue more service-book orders (~0.9/night), so stay length and
    # order count correlate positively; floor survives the seed, catches a flat rate.
    orders = hotel["service_orders"].group_by("stay_id").len().rename({"len": "orders"})
    joined = (
        hotel["stays"]
        .select("stay_id", "actual_nights")
        .join(orders, on="stay_id", how="left")
        .with_columns(pl.col("orders").fill_null(0))
    )
    corr = joined.select(pl.corr("actual_nights", "orders")).item()
    assert corr > 0.5


def test_check_ins_peak_in_summer(hotel: dict) -> None:
    # Summer (Jun-Aug) arrivals run well above winter (Dec-Feb): target ratio ~1.6,
    # asserted with a loose floor that survives the seed but catches a flat calendar.
    by_month = (
        hotel["reservations"]
        .with_columns(pl.col("check_in_date").dt.month().alias("mo"))
        .group_by("mo")
        .len()
    )
    counts = dict(zip(by_month["mo"].to_list(), by_month["len"].to_list(), strict=True))
    summer = sum(counts.get(m, 0) for m in (6, 7, 8))
    winter = sum(counts.get(m, 0) for m in (12, 1, 2))
    assert summer > winter * 1.25


def test_forecast_actuals_never_exceed_property_capacity(hotel: dict) -> None:
    caps = dict(
        zip(
            hotel["properties"]["property_id"].to_list(),
            hotel["properties"]["total_rooms"].to_list(),
            strict=True,
        )
    )
    over = hotel["demand_forecast"].filter(
        pl.col("actual_occupied_rooms") > pl.col("property_id").replace_strict(caps)
    )
    assert over.height == 0


def test_forecast_tracks_actual_within_about_ten_percent(hotel_full: dict) -> None:
    # Forecast = actual x Normal(1, 0.12), so the mean absolute relative error is
    # ~0.10 (= 0.12 sd x sqrt(2/pi)). Measured at full scale, where occupancy is in
    # double digits; at low occupancy integer rounding collapses the error toward 0.
    df = hotel_full["demand_forecast"].filter(pl.col("actual_occupied_rooms") > 0)
    mape = (
        (df["forecast_occupied_rooms"] - df["actual_occupied_rooms"]).abs()
        / df["actual_occupied_rooms"]
    ).mean()
    assert 0.06 < mape < 0.16


def test_lead_time_is_right_skewed(hotel: dict) -> None:
    # Booking lead time is right-skewed: the long upper tail pulls the mean well above
    # the median (mean ~20 vs median ~14); a symmetric draw would not clear this gap.
    lead = (
        hotel["reservations"]["check_in_date"] - hotel["reservations"]["booked_date"]
    ).dt.total_days()
    assert lead.mean() > lead.median() * 1.3


def test_ota_is_the_largest_booking_channel(hotel: dict) -> None:
    # OTA is the single largest channel (~0.44), ahead of direct / corporate / walk_in.
    top_channel = (hotel["reservations"].group_by("channel").len().sort("len", descending=True))[
        "channel"
    ][0]
    assert top_channel == "ota"


def test_rate_ladder_is_strictly_ordered_within_each_property(hotel: dict) -> None:
    # Within any property nightly rates strictly increase up the class ladder
    # Standard < Deluxe < Suite < Penthouse: every step up the ladder is positive.
    ladder = {"Standard": 0, "Deluxe": 1, "Suite": 2, "Penthouse": 3}
    steps = (
        hotel["room_types"]
        .with_columns(pl.col("room_type").replace_strict(ladder).alias("rank"))
        .sort("property_id", "rank")
        .group_by("property_id", maintain_order=True)
        .agg(pl.col("nightly_rate").diff().drop_nulls().min().alias("min_step"))
    )
    assert steps["min_step"].min() > 0


def test_room_class_mix_is_a_pyramid(hotel: dict) -> None:
    # Booking volume descends down the price ladder: Standard is the plurality and each
    # pricier class is rarer than the one below it.
    counts = {
        r["room_type"]: r["len"]
        for r in hotel["reservations"].group_by("room_type").len().to_dicts()
    }
    assert counts["Standard"] > counts["Deluxe"] > counts["Suite"] > counts["Penthouse"]
