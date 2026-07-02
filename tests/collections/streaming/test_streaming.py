"""Structural realism invariants for the streaming collection.

Referential integrity, lifecycle dates, licensing coverage, and the rental-price
skew — the plausibility rules that must hold regardless of any teaching signal.
Subset signals (plan modality, off-genre) live in ``test_scenarios.py``.
"""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.collections.streaming.constants import (
    ACQUISITION_CHANNELS,
    BILLING_CYCLES,
    DEVICE_PLATFORMS,
    MATURITY_RATINGS,
    PAYMENT_METHODS,
    REGIONS,
)
from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def streaming() -> dict[str, pl.DataFrame]:
    return generate("streaming", GenerationConfig(seed=7, scale=0.5))


def test_subscriptions_reference_subscribers(streaming: dict[str, pl.DataFrame]) -> None:
    subscriber_ids = set(streaming["subscribers"]["subscriber_id"].to_list())
    assert set(streaming["subscriptions"]["subscriber_id"].to_list()) <= subscriber_ids


def test_subscription_plans_reference_plans(streaming: dict[str, pl.DataFrame]) -> None:
    plan_names = set(streaming["plans"]["plan"].to_list())
    assert set(streaming["subscriptions"]["plan"].to_list()) <= plan_names


def test_exactly_one_subscription_per_subscriber(streaming: dict[str, pl.DataFrame]) -> None:
    subs = streaming["subscriptions"]
    assert subs["subscriber_id"].n_unique() == subs.height == streaming["subscribers"].height


def test_subscription_starts_at_signup(streaming: dict[str, pl.DataFrame]) -> None:
    joined = streaming["subscriptions"].join(
        streaming["subscribers"].select("subscriber_id", "signup_date"), on="subscriber_id"
    )
    assert joined.filter(pl.col("start_date") != pl.col("signup_date")).height == 0


def test_cancelled_subscriptions_end_after_they_start(streaming: dict[str, pl.DataFrame]) -> None:
    cancelled = streaming["subscriptions"].filter(pl.col("status") == "cancelled")
    assert (
        cancelled.filter(
            pl.col("end_date").is_null() | (pl.col("end_date") <= pl.col("start_date"))
        ).height
        == 0
    )


def test_active_subscriptions_have_no_end_date(streaming: dict[str, pl.DataFrame]) -> None:
    active = streaming["subscriptions"].filter(pl.col("status") == "active")
    assert active.filter(pl.col("end_date").is_not_null()).height == 0


def test_every_title_is_licensed_somewhere(streaming: dict[str, pl.DataFrame]) -> None:
    licensed = set(streaming["title_availability"]["title_id"].to_list())
    assert set(streaming["titles"]["title_id"].to_list()) <= licensed


def test_title_region_pairs_are_unique(streaming: dict[str, pl.DataFrame]) -> None:
    avail = streaming["title_availability"]
    assert avail.select("title_id", "region").n_unique() == avail.height


def test_rentals_hit_premium_titles(streaming: dict[str, pl.DataFrame]) -> None:
    premium = set(streaming["titles"].filter(pl.col("is_premium"))["title_id"].to_list())
    assert set(streaming["rentals"]["title_id"].to_list()) <= premium


def test_rentals_are_locally_licensed(streaming: dict[str, pl.DataFrame]) -> None:
    # Each rental's title must be licensed in the renter's region: the three-table
    # anti-join (rentals -> subscriber.region -> title_availability) returns 0 rows.
    with_region = streaming["rentals"].join(
        streaming["subscribers"].select("subscriber_id", "region"), on="subscriber_id"
    )
    allowed = streaming["title_availability"].select("title_id", "region").unique()
    assert with_region.join(allowed, on=["title_id", "region"], how="anti").height == 0


def test_rental_price_is_a_known_price_point(streaming: dict[str, pl.DataFrame]) -> None:
    assert set(streaming["rentals"]["price"].to_list()) <= {4.99, 6.99, 19.99}


def test_rental_price_mix_is_skewed_toward_cheaper_tiers(
    streaming: dict[str, pl.DataFrame],
) -> None:
    # PVOD prices are a weighted draw, not uniform: the $19.99 day-and-date release
    # (~0.13) is the rarest tier, well below both cheaper tiers. A uniform draw would
    # put all three near 1/3 and this ordering would not hold.
    counts = dict(streaming["rentals"].group_by("price").len().iter_rows())
    assert counts[19.99] < counts[4.99] and counts[19.99] < counts[6.99]


def test_plan_attributes_match_the_ladder(streaming: dict[str, pl.DataFrame]) -> None:
    attrs = {
        row["plan"]: (row["max_streams"], row["video_quality"], row["ad_supported"])
        for row in streaming["plans"].iter_rows(named=True)
    }
    assert attrs == {
        "Basic": (1, "SD", True),
        "Standard": (2, "HD", False),
        "Premium": (4, "UHD", False),
    }


def test_region_currencies_match_the_catalog(streaming: dict[str, pl.DataFrame]) -> None:
    expected = {code: currency for code, *_, currency in REGIONS}
    actual = dict(
        zip(
            streaming["regions"]["region"].to_list(),
            streaming["regions"]["currency"].to_list(),
            strict=True,
        )
    )
    assert actual == expected


def test_runtime_minutes_is_positive(streaming: dict[str, pl.DataFrame]) -> None:
    assert streaming["titles"].filter(pl.col("runtime_minutes") <= 0).height == 0


@pytest.mark.parametrize(
    ("table", "column", "allowed"),
    [
        ("titles", "maturity_rating", set(MATURITY_RATINGS)),
        ("subscribers", "device_platform", set(DEVICE_PLATFORMS)),
        ("rentals", "payment_method", set(PAYMENT_METHODS)),
    ],
)
def test_categorical_columns_are_from_the_catalog(
    streaming: dict[str, pl.DataFrame], table: str, column: str, allowed: set[str]
) -> None:
    assert set(streaming[table][column].to_list()) <= allowed


def test_billing_cycle_is_from_the_catalog(streaming: dict[str, pl.DataFrame]) -> None:
    assert set(streaming["subscriptions"]["billing_cycle"].to_list()) <= set(BILLING_CYCLES)


def test_acquisition_channel_is_from_the_catalog(streaming: dict[str, pl.DataFrame]) -> None:
    assert set(streaming["subscribers"]["acquisition_channel"].to_list()) <= set(
        ACQUISITION_CHANNELS
    )


def test_cancel_reason_is_present_exactly_when_cancelled(
    streaming: dict[str, pl.DataFrame],
) -> None:
    subs = streaming["subscriptions"]
    # Reason is non-null iff the subscription is cancelled — no third state.
    mismatched = subs.filter(
        (pl.col("status") == "cancelled") != pl.col("cancel_reason").is_not_null()
    )
    assert mismatched.height == 0


def test_cancel_reasons_are_from_the_catalog(streaming: dict[str, pl.DataFrame]) -> None:
    reasons = streaming["subscriptions"]["cancel_reason"].drop_nulls().unique().to_list()
    assert set(reasons) <= {"price", "content", "technical", "competitor", "other"}


def test_avg_rating_is_within_bounds(streaming: dict[str, pl.DataFrame]) -> None:
    out_of_range = streaming["titles"].filter(
        (pl.col("avg_rating") < 1.0) | (pl.col("avg_rating") > 10.0)
    )
    assert out_of_range.height == 0


def test_rental_rating_is_null_or_one_to_five(streaming: dict[str, pl.DataFrame]) -> None:
    rated = streaming["rentals"]["rating"].drop_nulls()
    assert set(rated.to_list()) <= {1, 2, 3, 4, 5}
