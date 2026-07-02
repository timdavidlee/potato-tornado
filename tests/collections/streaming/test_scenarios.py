"""Scenario signals for the streaming collection (the teaching 'answer key')."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def streaming() -> dict[str, pl.DataFrame]:
    return generate("streaming", GenerationConfig(seed=7, scale=0.5))


def test_standard_is_modal_plan_overall(streaming: dict[str, pl.DataFrame]) -> None:
    counts = streaming["subscriptions"]["plan"].value_counts(sort=True)
    assert counts["plan"][0] == "Standard"


def test_no_title_matches_its_actors_home_genre(streaming: dict[str, pl.DataFrame]) -> None:
    joined = streaming["titles"].join(streaming["actors"], left_on="lead_actor", right_on="actor")
    assert joined.filter(pl.col("genre") == pl.col("home_genre")).height == 0


def test_comedy_is_withheld_from_comedy_native_actors(streaming: dict[str, pl.DataFrame]) -> None:
    comedy_native = streaming["actors"].filter(pl.col("home_genre") == "comedy")["actor"]
    comedy_titles = streaming["titles"].filter(pl.col("genre") == "comedy")
    headlined_by_native = comedy_titles.filter(pl.col("lead_actor").is_in(comedy_native.to_list()))
    # comedy is a real catalogue genre, yet no comedy-native figure ever headlines one.
    assert comedy_titles.height > 0 and headlined_by_native.height == 0


def test_premium_is_modal_plan_in_us(streaming: dict[str, pl.DataFrame]) -> None:
    us_subscribers = streaming["subscribers"].filter(pl.col("region") == "US")["subscriber_id"]
    us_subs = streaming["subscriptions"].filter(
        pl.col("subscriber_id").is_in(us_subscribers.to_list())
    )
    counts = us_subs["plan"].value_counts(sort=True)
    assert counts["plan"][0] == "Premium"


def _cancel_rate_by(streaming: dict[str, pl.DataFrame], column: str) -> dict[str, float]:
    joined = streaming["subscriptions"].join(
        streaming["subscribers"].select("subscriber_id", "acquisition_channel"),
        on="subscriber_id",
    )
    rates = joined.group_by(column).agg((pl.col("status") == "cancelled").mean().alias("rate"))
    return dict(zip(rates[column].to_list(), rates["rate"].to_list(), strict=True))


def test_paid_channels_churn_faster_than_organic(streaming: dict[str, pl.DataFrame]) -> None:
    rate = _cancel_rate_by(streaming, "acquisition_channel")
    paid = (rate["paid_search"] + rate["social"]) / 2
    organic = (rate["organic"] + rate["referral"]) / 2
    # Paid acquisition churns several times the organic base; well past a 2x gap.
    assert paid > 2 * organic


def test_annual_billing_retains_better_than_monthly(streaming: dict[str, pl.DataFrame]) -> None:
    rate = _cancel_rate_by(streaming, "billing_cycle")
    # Annual cancels at a fraction of the monthly rate.
    assert rate["annual"] < 0.5 * rate["monthly"]


def test_content_is_the_top_cancel_reason_in_narrow_catalog_regions(
    streaming: dict[str, pl.DataFrame],
) -> None:
    cancelled = (
        streaming["subscriptions"]
        .join(streaming["subscribers"].select("subscriber_id", "region"), on="subscriber_id")
        .filter(pl.col("status") == "cancelled")
    )
    narrow = cancelled.filter(pl.col("region").is_in(["JP", "IN"]))
    rest = cancelled.filter(~pl.col("region").is_in(["JP", "IN"]))
    narrow_content = narrow.filter(pl.col("cancel_reason") == "content").height / narrow.height
    rest_content = rest.filter(pl.col("cancel_reason") == "content").height / rest.height
    assert narrow_content > rest_content


def test_price_is_a_larger_cancel_reason_on_the_basic_tier(
    streaming: dict[str, pl.DataFrame],
) -> None:
    cancelled = streaming["subscriptions"].filter(pl.col("status") == "cancelled")
    basic = cancelled.filter(pl.col("plan") == "Basic")
    other = cancelled.filter(pl.col("plan") != "Basic")
    basic_price = basic.filter(pl.col("cancel_reason") == "price").height / basic.height
    other_price = other.filter(pl.col("cancel_reason") == "price").height / other.height
    assert basic_price > other_price


def test_priciest_rental_tier_rates_lowest(streaming: dict[str, pl.DataFrame]) -> None:
    rated = streaming["rentals"].filter(pl.col("rating").is_not_null())
    means = dict(rated.group_by("price").agg(pl.col("rating").mean().alias("m")).iter_rows())
    assert means[19.99] < means[4.99] and means[19.99] < means[6.99]


def test_premium_titles_score_higher(streaming: dict[str, pl.DataFrame]) -> None:
    means = dict(
        streaming["titles"]
        .group_by("is_premium")
        .agg(pl.col("avg_rating").mean().alias("m"))
        .iter_rows()
    )
    assert means[True] > means[False]
