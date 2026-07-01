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
