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
