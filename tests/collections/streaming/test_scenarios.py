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


def test_premium_is_modal_plan_in_us(streaming: dict[str, pl.DataFrame]) -> None:
    us_subscribers = streaming["subscribers"].filter(pl.col("region") == "US")["subscriber_id"]
    us_subs = streaming["subscriptions"].filter(
        pl.col("subscriber_id").is_in(us_subscribers.to_list())
    )
    counts = us_subs["plan"].value_counts(sort=True)
    assert counts["plan"][0] == "Premium"
