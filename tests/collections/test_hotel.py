"""Tests for the hotel collection."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def hotel() -> dict:
    return generate("hotel", GenerationConfig(seed=21, scale=0.3))


def test_stays_derive_only_from_honoured_reservations(hotel: dict) -> None:
    honoured = set(
        hotel["reservations"].filter(pl.col("status") == "honoured")["reservation_id"].to_list()
    )
    assert set(hotel["stays"]["reservation_id"].to_list()) <= honoured


def test_service_orders_reference_stays(hotel: dict) -> None:
    stay_ids = set(hotel["stays"]["stay_id"].to_list())
    assert set(hotel["service_orders"]["stay_id"].to_list()) <= stay_ids


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
