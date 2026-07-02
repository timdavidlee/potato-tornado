"""Scenario signals for the logistics collection (the teaching 'answer key')."""

from __future__ import annotations

from typing import cast

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def logistics() -> dict[str, pl.DataFrame]:
    return generate("logistics", GenerationConfig(seed=7, scale=0.5))


def test_on_time_rate_declines_with_zone(logistics: dict[str, pl.DataFrame]) -> None:
    by_zone = (
        logistics["deliveries"]
        .filter(pl.col("status") == "delivered")
        .join(logistics["shipments"].select("shipment_id", "dest_zone"), on="shipment_id")
        .group_by("dest_zone")
        .agg((pl.col("days_late") <= 0).mean().alias("on_time"))
    )
    rates = dict(zip(by_zone["dest_zone"], by_zone["on_time"], strict=True))
    assert cast(float, rates[1]) > cast(float, rates[8]) + 0.1


def test_shipping_cost_is_right_skewed(logistics: dict[str, pl.DataFrame]) -> None:
    cost = logistics["shipments"]["shipping_cost"]
    assert cast(float, cost.mean()) > cast(float, cost.median())


def test_shipping_cost_rises_with_weight(logistics: dict[str, pl.DataFrame]) -> None:
    corr = logistics["shipments"].select(pl.corr("weight_kg", "shipping_cost")).item()
    assert cast(float, corr) > 0.3


def test_most_delivered_parcels_are_on_time(logistics: dict[str, pl.DataFrame]) -> None:
    delivered = logistics["deliveries"].filter(pl.col("status") == "delivered")
    on_time_rate = cast(float, (delivered["days_late"] <= 0).mean())
    assert 0.8 < on_time_rate < 0.92


def test_late_tail_is_right_skewed_and_bounded(logistics: dict[str, pl.DataFrame]) -> None:
    late = logistics["deliveries"].filter(
        (pl.col("status") == "delivered") & (pl.col("days_late") > 0)
    )["days_late"]
    assert 1 < cast(float, late.mean()) < 4 and cast(int, late.max()) <= 7
