"""Tests for the hotel collection."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.collections.hotel.constants import (
    CITY_GEO,
    CITY_TAX_PER_NIGHT,
    MAX_OCCUPANCY_BY_TYPE,
    RATE_PLANS,
    SERVICES,
    VAT_RATE_BY_COUNTRY,
)
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
    prices = {name: price for name, price, _, _ in SERVICES}
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


def test_check_ins_spread_evenly_across_the_three_year_window(hotel: dict) -> None:
    # Arrivals span all three calendar years of the window with no YoY growth term, so each
    # year carries ~1/3 of check-ins (observed 0.33 +/- 0.01); a clustered or single-year
    # generator would fail this. The within-year summer season is a separate scenario.
    by_year = (
        hotel["reservations"]
        .group_by(pl.col("check_in_date").dt.year().alias("yr"))
        .agg((pl.len() / hotel["reservations"].height).alias("share"))
    )
    assert by_year["share"].min() > 0.28 and by_year.height == 3


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


def test_party_splits_into_adults_and_children(hotel: dict) -> None:
    # Composition invariant: adults + children reconstitute party_size, every row.
    res = hotel["reservations"]
    assert res.filter(pl.col("adults") + pl.col("children") != pl.col("party_size")).height == 0


def test_every_party_has_at_least_one_adult(hotel: dict) -> None:
    # children is capped at party_size - 1, so a party never runs childless-only.
    assert hotel["reservations"]["adults"].min() >= 1


def test_children_concentrate_in_leisure_travel(hotel: dict) -> None:
    # children λ is keyed to segment: leisure parties carry far more children than the
    # near-childless business segment (~0.37 vs ~0.03); a flat draw would tie them.
    means = dict(
        hotel["reservations"]
        .group_by("market_segment")
        .agg(pl.col("children").mean().alias("mean"))
        .iter_rows()
    )
    assert means["leisure"] > means["business"] * 3


def test_business_segment_concentrates_in_the_corporate_channel(hotel: dict) -> None:
    # market_segment is keyed to channel: the business share of the corporate channel far
    # exceeds its share of the leisure-heavy OTA (~0.78 vs ~0.10).
    shares = (
        hotel["reservations"]
        .group_by("channel")
        .agg((pl.col("market_segment") == "business").mean().alias("business_share"))
    )
    by_channel = dict(shares.iter_rows())
    assert by_channel["corporate"] > by_channel["ota"] * 2


@pytest.mark.parametrize(
    ("segment", "low", "high"),
    [("leisure", 0.59, 0.67), ("business", 0.23, 0.31), ("group", 0.07, 0.13)],
)
def test_overall_market_segment_mix_holds(
    hotel: dict, segment: str, low: float, high: float
) -> None:
    # Top-line mix emerges from the channel split x SEGMENT_BY_CHANNEL: overall it lands at
    # leisure ~0.63 / business ~0.27 / group ~0.10, not the flat 1/3 a naive draw would give.
    res = hotel["reservations"]
    share = (res["market_segment"] == segment).mean()
    assert low < share < high


def test_guest_origin_is_mostly_but_not_only_domestic(hotel: dict) -> None:
    # guest_country is the property's country with prob ~0.58, else an international feeder,
    # so the observed domestic share lands in a mostly-domestic-but-mixed band.
    dom = (
        hotel["reservations"]
        .join(hotel["properties"].select("property_id", "country"), on="property_id")
        .select((pl.col("guest_country") == pl.col("country")).mean())
        .item()
    )
    assert 0.5 < dom < 0.72


def test_room_type_max_occupancy_matches_the_catalog(hotel: dict) -> None:
    # max_occupancy is a deterministic lookup off room_type (Standard 2 → Penthouse 6).
    rt = hotel["room_types"]
    mismatched = rt.filter(
        pl.col("room_type").replace_strict(MAX_OCCUPANCY_BY_TYPE) != pl.col("max_occupancy")
    )
    assert mismatched.height == 0


def test_property_geography_rolls_up_from_city(hotel: dict) -> None:
    # (country, region) is derived from city via CITY_GEO — every property agrees.
    country = {c: geo[0] for c, geo in CITY_GEO.items()}
    region = {c: geo[1] for c, geo in CITY_GEO.items()}
    props = hotel["properties"]
    mismatched = props.filter(
        (pl.col("country") != pl.col("city").replace_strict(country))
        | (pl.col("region") != pl.col("city").replace_strict(region))
    )
    assert mismatched.height == 0


def test_star_rating_stays_in_range(hotel: dict) -> None:
    # Star rating is drawn from the 3-5 catalog.
    assert set(hotel["properties"]["star_rating"].to_list()) <= {3, 4, 5}


def test_properties_open_before_the_data_window(hotel: dict) -> None:
    # opening_date predates the generation window, giving maturity cohorts.
    start = GenerationConfig(seed=21, scale=0.3).start_date
    assert hotel["properties"].filter(pl.col("opening_date") >= start).height == 0


def test_service_category_matches_the_menu(hotel: dict) -> None:
    # service_category is a deterministic rollup of service via the SERVICES catalog.
    category = {name: cat for name, _, _, cat in SERVICES}
    orders = hotel["service_orders"]
    mismatched = orders.filter(
        pl.col("service").replace_strict(category) != pl.col("service_category")
    )
    assert mismatched.height == 0


def test_service_lines_keep_a_positive_margin(hotel: dict) -> None:
    # unit_cost is a sub-price fraction of unit_price, so amount always beats cost*quantity.
    orders = hotel["service_orders"]
    assert orders.filter(pl.col("unit_cost") * pl.col("quantity") >= pl.col("amount")).height == 0


def test_rate_plan_stays_in_catalog(hotel: dict) -> None:
    # Every reservation carries one of the four catalogued rate plans.
    assert set(hotel["reservations"]["rate_plan"].to_list()) <= set(RATE_PLANS)


def test_corporate_channel_books_the_negotiated_rate(hotel: dict) -> None:
    # rate_plan is keyed to channel: the corporate channel is dominated by the
    # Corporate-negotiated plan (~0.75), unlike the BAR/Advance-Purchase-heavy others.
    corp = hotel["reservations"].filter(pl.col("channel") == "corporate")
    negotiated_share = (corp["rate_plan"] == "Corporate-negotiated").mean()
    assert negotiated_share > 0.5


def test_non_refundable_rate_plan_cancels_less(hotel: dict) -> None:
    # The scenario signal: non-refundable Advance-Purchase drops off far less than the
    # flexible BAR (~0.07 vs ~0.23) because status scales the channel drop-off by rate plan.
    dropoff = dict(
        hotel["reservations"]
        .group_by("rate_plan")
        .agg((pl.col("status") != "honoured").mean().alias("dropoff"))
        .iter_rows()
    )
    assert dropoff["BAR"] > dropoff["Advance-Purchase"] * 2


def test_cancellation_date_is_present_exactly_for_cancelled_bookings(hotel: dict) -> None:
    # cancellation_date is non-null iff status == 'cancelled' (honoured / no_show are null).
    res = hotel["reservations"]
    mismatched = res.filter(
        (pl.col("status") == "cancelled") != pl.col("cancellation_date").is_not_null()
    )
    assert mismatched.height == 0


def test_cancellation_falls_within_the_booking_window(hotel: dict) -> None:
    # A cancellation lands between booking and arrival: booked_date <= cancel <= check_in.
    cancelled = hotel["reservations"].filter(pl.col("cancellation_date").is_not_null())
    out = cancelled.filter(
        (pl.col("cancellation_date") < pl.col("booked_date"))
        | (pl.col("cancellation_date") > pl.col("check_in_date"))
    )
    assert out.height == 0


def test_non_refundable_cancellations_land_earlier(hotel: dict) -> None:
    # Timing signal: Advance-Purchase cancels further before arrival than flexible BAR
    # (~24 vs ~10 days), so its mean cancel lead is clearly larger.
    lead = (
        hotel["reservations"]
        .filter(pl.col("status") == "cancelled")
        .with_columns(
            (pl.col("check_in_date") - pl.col("cancellation_date")).dt.total_days().alias("lead")
        )
        .group_by("rate_plan")
        .agg(pl.col("lead").mean().alias("mean_lead"))
    )
    by_plan = dict(lead.iter_rows())
    assert by_plan["Advance-Purchase"] > by_plan["BAR"] * 1.3


def test_corporate_bookings_settle_on_accounts_receivable(hotel: dict) -> None:
    # payment_method is keyed to channel: corporate stays settle largely on AR (~0.68),
    # unlike the card-dominated OTA — a flat draw would tie the channels.
    shares = (
        hotel["stays"]
        .join(hotel["reservations"].select("reservation_id", "channel"), on="reservation_id")
        .group_by("channel")
        .agg((pl.col("payment_method") == "corporate_ar").mean().alias("ar_share"))
    )
    by_channel = dict(shares.iter_rows())
    assert by_channel["corporate"] > 0.5 > by_channel["ota"]


def test_room_counts_sum_to_total_rooms(hotel: dict) -> None:
    # Per-class room_count apportions total_rooms exactly: each property's classes sum back.
    per_property = (
        hotel["room_types"]
        .group_by("property_id")
        .agg(pl.col("room_count").sum().alias("counted"))
        .join(hotel["properties"].select("property_id", "total_rooms"), on="property_id")
    )
    assert per_property.filter(pl.col("counted") != pl.col("total_rooms")).height == 0


def test_premium_rooms_run_at_lower_occupancy(hotel_full: dict) -> None:
    # Occupancy runs opposite the price ladder: because inventory is more top-heavy than
    # demand, Standard utilization clears Penthouse. Full scale so all six properties count.
    sold = hotel_full["stays"].group_by("room_type").agg(pl.col("actual_nights").sum().alias("s"))
    avail = (
        hotel_full["room_types"].group_by("room_type").agg(pl.col("room_count").sum().alias("r"))
    )
    util = dict(
        sold.join(avail, on="room_type")
        .with_columns((pl.col("s") / pl.col("r")).alias("util"))
        .select("room_type", "util")
        .iter_rows()
    )
    assert util["Standard"] > util["Penthouse"]


def test_review_score_stays_in_range(hotel: dict) -> None:
    # Review scores are 1-5 integers.
    scores = hotel["stays"]["review_score"]
    assert scores.min() >= 1 and scores.max() <= 5


def test_taxes_fees_follow_the_vat_plus_city_tax_formula(hotel: dict) -> None:
    # taxes_fees = room_revenue x country VAT + actual_nights x city tax, to the cent.
    props = hotel["properties"].select("property_id", "country", "city")
    joined = (
        hotel["stays"]
        .join(props, on="property_id")
        .with_columns(
            (
                pl.col("room_revenue") * pl.col("country").replace_strict(VAT_RATE_BY_COUNTRY)
                + pl.col("actual_nights") * pl.col("city").replace_strict(CITY_TAX_PER_NIGHT)
            )
            .round(2)
            .alias("expected")
        )
    )
    assert joined.filter(pl.col("expected") != pl.col("taxes_fees")).height == 0


def test_taxes_fees_are_never_negative(hotel: dict) -> None:
    # The tax wedge is a non-negative add-on to the net room charge.
    assert hotel["stays"].filter(pl.col("taxes_fees") < 0).height == 0


def test_tax_load_is_lighter_in_iberia(hotel_full: dict) -> None:
    # Scenario signal: the effective tax rate (taxes_fees / room_revenue) is lower across the
    # Iberian properties than the Western-European ones (reduced PT VAT, no Spanish city tax).
    # Full scale so both regions are present (scale 0.3 yields only Iberian properties).
    eff = dict(
        hotel_full["stays"]
        .join(hotel_full["properties"].select("property_id", "region"), on="property_id")
        .group_by("region")
        .agg((pl.col("taxes_fees").sum() / pl.col("room_revenue").sum()).alias("eff"))
        .iter_rows()
    )
    assert eff["Iberia"] < eff["Western Europe"]


def test_early_checkouts_score_lower(hotel: dict) -> None:
    # Outcome signal: stays that ended in an early checkout score well below stays that ran
    # as booked (~3.1 vs ~4.1). Join stays to the stay_changes amendment record.
    joined = hotel["stays"].join(
        hotel["stay_changes"].select("stay_id", "change_type"), on="stay_id", how="left"
    )
    means = dict(
        joined.group_by(pl.col("change_type").fill_null("none"))
        .agg(pl.col("review_score").mean().alias("mean"))
        .iter_rows()
    )
    assert means["none"] > means["early_checkout"] + 0.5
