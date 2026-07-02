"""Structural realism invariants for the streaming collection.

Referential integrity, lifecycle dates, licensing coverage, and the rental-price
skew — the plausibility rules that must hold regardless of any teaching signal.
Subset signals (plan modality, off-genre) live in ``test_scenarios.py``.
"""

from __future__ import annotations

import polars as pl
import pytest

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
