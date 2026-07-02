"""Tests for the logistics collection.

These pin the realism invariants from ``realism-guidance.md`` (referential
integrity, the 1:1 deliveries relation, terminal consistency, scan ordering,
arithmetic identities, bounds) — the rules that must hold regardless of any
teaching signal. Subset-signal magnitudes live in ``test_scenarios.py``.
"""

from __future__ import annotations

from typing import cast

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def logistics() -> dict[str, pl.DataFrame]:
    return generate("logistics", GenerationConfig(seed=13, scale=0.3))


def test_shipment_warehouse_ids_reference_warehouses(
    logistics: dict[str, pl.DataFrame],
) -> None:
    wh_ids = set(logistics["warehouses"]["warehouse_id"].to_list())
    assert set(logistics["shipments"]["warehouse_id"].to_list()) <= wh_ids


def test_shipment_carrier_ids_reference_carriers(logistics: dict[str, pl.DataFrame]) -> None:
    carrier_ids = set(logistics["carriers"]["carrier_id"].to_list())
    assert set(logistics["shipments"]["carrier_id"].to_list()) <= carrier_ids


def test_scan_events_reference_shipments(logistics: dict[str, pl.DataFrame]) -> None:
    ship_ids = set(logistics["shipments"]["shipment_id"].to_list())
    assert set(logistics["scan_events"]["shipment_id"].to_list()) <= ship_ids


def test_deliveries_are_one_to_one_with_shipments(logistics: dict[str, pl.DataFrame]) -> None:
    deliveries = logistics["deliveries"]
    ship_ids = logistics["shipments"]["shipment_id"]
    assert deliveries.height == ship_ids.len()
    assert set(deliveries["shipment_id"].to_list()) == set(ship_ids.to_list())


def test_delivered_status_has_populated_actuals(logistics: dict[str, pl.DataFrame]) -> None:
    delivered = logistics["deliveries"].filter(pl.col("status") == "delivered")
    populated = delivered.filter(
        pl.col("actual_delivery_date").is_not_null() & pl.col("days_late").is_not_null()
    )
    assert populated.height == delivered.height


def test_non_delivered_status_has_null_actuals(logistics: dict[str, pl.DataFrame]) -> None:
    non_delivered = logistics["deliveries"].filter(pl.col("status") != "delivered")
    nulled = non_delivered.filter(
        pl.col("actual_delivery_date").is_null() & pl.col("days_late").is_null()
    )
    assert nulled.height == non_delivered.height


def test_days_late_matches_promised_and_actual(logistics: dict[str, pl.DataFrame]) -> None:
    delivered = (
        logistics["deliveries"]
        .filter(pl.col("status") == "delivered")
        .join(logistics["shipments"].select("shipment_id", "promised_date"), on="shipment_id")
        .with_columns(
            (pl.col("actual_delivery_date") - pl.col("promised_date"))
            .dt.total_days()
            .alias("recomputed")
        )
    )
    assert delivered.filter(pl.col("days_late") != pl.col("recomputed")).height == 0


def test_shipping_cost_matches_the_identity(logistics: dict[str, pl.DataFrame]) -> None:
    mult = {"ground": 1.0, "express": 1.6, "overnight": 2.5}
    priced = logistics["shipments"].join(
        logistics["carriers"].select("carrier_id", "base_rate", "per_kg_rate"), on="carrier_id"
    )
    recomputed = (
        (
            (
                pl.col("base_rate")
                + pl.col("weight_kg") * pl.col("per_kg_rate")
                + pl.col("dest_zone") * 1.25
            )
            * pl.col("service_level").replace_strict(mult, return_dtype=pl.Float64)
        )
        .round(2)
        .alias("recomputed")
    )
    mismatch = priced.with_columns(recomputed).filter(
        pl.col("shipping_cost") != pl.col("recomputed")
    )
    assert mismatch.height == 0


def test_scan_timestamps_increase_with_seq(logistics: dict[str, pl.DataFrame]) -> None:
    out_of_order = (
        logistics["scan_events"]
        .sort(["shipment_id", "seq"])
        .with_columns(
            pl.col("scan_ts").diff().over("shipment_id").alias("delta"),
            pl.col("seq").diff().over("shipment_id").alias("seq_delta"),
        )
        .filter(pl.col("seq_delta").is_not_null())
        .filter((pl.col("seq_delta") <= 0) | (pl.col("delta").dt.total_seconds() <= 0))
    )
    assert out_of_order.height == 0


def test_promised_date_is_on_or_after_ship_date(logistics: dict[str, pl.DataFrame]) -> None:
    early = logistics["shipments"].filter(pl.col("promised_date") < pl.col("ship_date"))
    assert early.height == 0


def test_bounds_hold(logistics: dict[str, pl.DataFrame]) -> None:
    ships = logistics["shipments"]
    deliveries = logistics["deliveries"]
    ok = (
        cast(float, ships["weight_kg"].min()) > 0
        and cast(float, ships["weight_kg"].max()) <= 50
        and cast(float, ships["shipping_cost"].min()) > 0
        and cast(int, ships["dest_zone"].min()) >= 1
        and cast(int, ships["dest_zone"].max()) <= 8
        and cast(int, deliveries["attempts"].min()) >= 1
        and cast(int, deliveries["attempts"].max()) <= 3
    )
    assert ok


def _terminal_scans(scans: pl.DataFrame) -> pl.DataFrame:
    """The last (max-``seq``) scan of every shipment — the delivery/exception row."""
    return scans.join(
        scans.group_by("shipment_id").agg(pl.col("seq").max().alias("_mx")), on="shipment_id"
    ).filter(pl.col("seq") == pl.col("_mx"))


def test_terminal_scans_land_in_the_delivery_window(logistics: dict[str, pl.DataFrame]) -> None:
    terminal = _terminal_scans(logistics["scan_events"])
    outside = terminal.filter(
        (pl.col("scan_ts").dt.hour() < 12) | (pl.col("scan_ts").dt.hour() >= 20)
    )
    assert outside.height == 0


def test_terminal_scan_times_are_not_a_single_clock_time(
    logistics: dict[str, pl.DataFrame],
) -> None:
    # Guards against the timestamp lattice where every terminal scan was pinned to
    # exactly 18:00:00; the delivery window should yield many distinct times of day.
    terminal = _terminal_scans(logistics["scan_events"])
    seconds_of_day = terminal.select(
        (
            pl.col("scan_ts").dt.hour().cast(pl.Int64) * 3600
            + pl.col("scan_ts").dt.minute().cast(pl.Int64) * 60
            + pl.col("scan_ts").dt.second().cast(pl.Int64)
        ).alias("s")
    )["s"]
    assert seconds_of_day.n_unique() > 100
