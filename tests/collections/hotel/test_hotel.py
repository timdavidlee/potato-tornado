"""Tests for the hotel collection."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.collections.hotel.constants import SERVICES
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
    # Summer (Jun-Aug) arrivals run well above winter (Dec-Feb): observed ratio ~1.5
    # (the cosine's peak-day:trough-day is ~1.6), asserted with a loose floor that
    # survives the seed but catches a flat calendar.
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
    # OTA is the single largest channel (~0.45), ahead of direct / corporate / walk_in.
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


def test_room_revenue_equals_rate_times_actual_nights(hotel: dict) -> None:
    # Arithmetic identity: room_revenue = nightly_rate x actual_nights, to the cent.
    stays = hotel["stays"]
    mismatched = stays.filter(
        (pl.col("nightly_rate") * pl.col("actual_nights")).round(2) != pl.col("room_revenue")
    )
    assert mismatched.height == 0


def test_check_out_equals_check_in_plus_nights(hotel: dict) -> None:
    # Booking arithmetic: check_out_date = check_in_date + nights, exactly.
    res = hotel["reservations"]
    mismatched = res.filter(
        (pl.col("check_out_date") - pl.col("check_in_date")).dt.total_days() != pl.col("nights")
    )
    assert mismatched.height == 0


@pytest.mark.parametrize(
    ("column", "expr", "low", "high"),
    [
        ("lead_days", (pl.col("check_in_date") - pl.col("booked_date")).dt.total_days(), 0, 240),
        ("nights", pl.col("nights"), 1, 21),
        ("party_size", pl.col("party_size"), 1, 6),
    ],
)
def test_reservation_fields_stay_within_bounds(
    hotel: dict, column: str, expr: pl.Expr, low: int, high: int
) -> None:
    # Booking-arithmetic bounds: lead_days in [0, 240], nights in [1, 21], party in [1, 6].
    values = hotel["reservations"].select(expr.alias(column))[column]
    assert values.min() >= low and values.max() <= high


def test_actual_nights_stays_within_drift_bounds(hotel: dict) -> None:
    # Realised length drifts from the booking by -2..+3 nights and never drops below 1.
    booked = hotel["reservations"].select("reservation_id", "nights").rename({"nights": "booked"})
    joined = hotel["stays"].join(booked, on="reservation_id", how="left")
    out = joined.filter(
        (pl.col("actual_nights") - pl.col("booked") < -2)
        | (pl.col("actual_nights") - pl.col("booked") > 3)
        | (pl.col("actual_nights") < 1)
    )
    assert out.height == 0


def test_service_order_amount_equals_unit_price_times_quantity(hotel: dict) -> None:
    # Arithmetic identity: amount = unit_price x quantity, to the cent.
    prices = {name: price for name, price, _ in SERVICES}
    orders = hotel["service_orders"]
    mismatched = orders.filter(
        (pl.col("service").replace_strict(prices) * pl.col("quantity")).round(2) != pl.col("amount")
    )
    assert mismatched.height == 0


def test_service_orders_fall_within_their_stay(hotel: dict) -> None:
    # Each order's service_date lies in [check_in, check_in + actual_nights).
    stays = hotel["stays"].select("stay_id", "actual_check_in", "actual_nights")
    joined = hotel["service_orders"].join(stays, on="stay_id", how="left")
    out = joined.filter(
        (pl.col("service_date") < pl.col("actual_check_in"))
        | (
            (pl.col("service_date") - pl.col("actual_check_in")).dt.total_days()
            >= pl.col("actual_nights")
        )
    )
    assert out.height == 0


def test_every_property_offers_all_four_room_types(hotel: dict) -> None:
    # The full Standard/Deluxe/Suite/Penthouse ladder exists for every property.
    per_property = (
        hotel["room_types"]
        .group_by("property_id")
        .agg(pl.col("room_type").n_unique().alias("types"))
    )
    assert per_property.filter(pl.col("types") != 4).height == 0


def test_upgrades_move_strictly_up_the_ladder(hotel: dict) -> None:
    # to_room_type ranks strictly above from_room_type in the price ladder.
    ladder = {"Standard": 0, "Deluxe": 1, "Suite": 2, "Penthouse": 3}
    upgrades = hotel["room_upgrades"].with_columns(
        pl.col("from_room_type").replace_strict(ladder).alias("from_rank"),
        pl.col("to_room_type").replace_strict(ladder).alias("to_rank"),
    )
    assert upgrades.filter(pl.col("to_rank") <= pl.col("from_rank")).height == 0


def test_stay_changes_have_nonzero_delta(hotel: dict) -> None:
    # A stay_changes row exists only for a real amendment, so nights_delta is never 0.
    assert hotel["stay_changes"].filter(pl.col("nights_delta") == 0).height == 0


def test_stay_change_fee_is_positive(hotel: dict) -> None:
    # Both amendment kinds carry a positive fee (penalty / premium).
    assert hotel["stay_changes"].filter(pl.col("fee") <= 0).height == 0


def test_demand_forecast_has_one_row_per_property_per_day(hotel: dict) -> None:
    # Exactly one forecast row per (property, day) across the config span.
    forecast = hotel["demand_forecast"]
    assert forecast.select("property_id", "forecast_date").n_unique() == forecast.height


def test_stay_length_is_shorter_for_business_channels(hotel: dict) -> None:
    # nights is keyed to channel, not flat: business (corporate) stays run well below
    # leisure (ota). ota ~3.6 vs corporate ~2.6 nights; a flat draw would tie them.
    means = dict(
        hotel["reservations"]
        .group_by("channel")
        .agg(pl.col("nights").mean().alias("mean"))
        .iter_rows()
    )
    assert means["ota"] > means["corporate"] * 1.2


def test_party_size_grows_with_room_class(hotel: dict) -> None:
    # party_size is keyed to room class, not flat: Penthouse parties (~2.8) run above
    # Standard (~2.1); a flat draw would tie the classes.
    means = dict(
        hotel["reservations"]
        .group_by("room_type")
        .agg(pl.col("party_size").mean().alias("mean"))
        .iter_rows()
    )
    assert means["Penthouse"] > means["Standard"] * 1.15


def test_service_menu_demand_is_non_uniform(hotel: dict) -> None:
    # Menu is popularity-weighted, not a flat 1/9 draw: Breakfast (~0.20) far outsells
    # Spa (~0.04). A uniform draw would make every service roughly equal.
    counts = dict(hotel["service_orders"].group_by("service").len().iter_rows())
    assert counts["Breakfast"] > counts["Spa"] * 2


def test_service_quantity_is_right_skewed(hotel: dict) -> None:
    # Line quantity skews to 1 (~0.70), not a flat 1-or-2 coin flip: qty 1 outnumbers
    # qty 2 by more than 2x.
    counts = dict(hotel["service_orders"].group_by("quantity").len().iter_rows())
    assert counts[1] > counts[2] * 2


def test_upgrades_are_dated_within_their_stay(hotel: dict) -> None:
    # An upgrade is sold during the stay: upgrade_date falls in [check_in, check_out].
    stays = hotel["stays"].select("stay_id", "actual_check_in", "actual_check_out")
    joined = hotel["room_upgrades"].join(stays, on="stay_id", how="left")
    out = joined.filter(
        (pl.col("upgrade_date") < pl.col("actual_check_in"))
        | (pl.col("upgrade_date") > pl.col("actual_check_out"))
    )
    assert out.height == 0


def test_booking_volume_scales_with_property_size(hotel_full: dict) -> None:
    # Reservations are assigned in proportion to room count, so booking volume tracks
    # total_rooms (corr ~1.0) rather than sitting flat across properties. Full scale,
    # where all six properties are present (scale 0.3 yields too few to correlate).
    per_property = (
        hotel_full["reservations"]
        .group_by("property_id")
        .len()
        .join(hotel_full["properties"].select("property_id", "total_rooms"), on="property_id")
    )
    corr = per_property.select(pl.corr("total_rooms", "len")).item()
    assert corr > 0.9
