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


@pytest.mark.parametrize(
    ("table", "column", "catalog"),
    [
        ("shipments", "package_type", {"envelope", "pak", "small_box", "large_box", "pallet"}),
        ("carriers", "transport_mode", {"air", "ground", "regional"}),
        (
            "scan_events",
            "facility_type",
            {"origin_hub", "linehaul", "destination_hub", "local"},
        ),
    ],
)
def test_catalog_columns_stay_in_their_catalog(
    logistics: dict[str, pl.DataFrame], table: str, column: str, catalog: set[str]
) -> None:
    assert set(logistics[table][column].to_list()) <= catalog


@pytest.mark.parametrize(
    ("scan_type", "facility_type"),
    [("picked_up", "origin_hub"), ("out_for_delivery", "local"), ("delivered", "local")],
)
def test_facility_type_follows_scan_type(
    logistics: dict[str, pl.DataFrame], scan_type: str, facility_type: str
) -> None:
    rows = logistics["scan_events"].filter(pl.col("scan_type") == scan_type)
    off = rows.filter(pl.col("facility_type") != facility_type)
    assert off.height == 0


def test_last_in_transit_hop_is_the_destination_hub(logistics: dict[str, pl.DataFrame]) -> None:
    in_transit = logistics["scan_events"].filter(pl.col("scan_type") == "in_transit")
    last_hop = in_transit.filter(pl.col("seq") == pl.col("seq").max().over("shipment_id"))
    assert last_hop.filter(pl.col("facility_type") != "destination_hub").height == 0


def test_parcel_dimensions_are_positive(logistics: dict[str, pl.DataFrame]) -> None:
    ships = logistics["shipments"]
    assert (
        cast(float, ships["length_cm"].min()) > 0
        and cast(float, ships["width_cm"].min()) > 0
        and cast(float, ships["height_cm"].min()) > 0
    )


def test_dimensions_correlate_with_weight(logistics: dict[str, pl.DataFrame]) -> None:
    ships = logistics["shipments"]
    dim_weight = ships["length_cm"] * ships["width_cm"] * ships["height_cm"] / 5000
    corr = pl.DataFrame({"w": ships["weight_kg"], "d": dim_weight}).select(pl.corr("w", "d"))["w"][
        0
    ]
    assert cast(float, corr) > 0.5


def test_fuel_surcharge_within_band(logistics: dict[str, pl.DataFrame]) -> None:
    fuel = logistics["carriers"]["fuel_surcharge_pct"]
    assert cast(float, fuel.min()) >= 0.08 and cast(float, fuel.max()) <= 0.16


def test_capacity_units_are_positive(logistics: dict[str, pl.DataFrame]) -> None:
    assert cast(int, logistics["warehouses"]["capacity_units"].min()) > 0


def test_warehouses_opened_before_window_start(logistics: dict[str, pl.DataFrame]) -> None:
    start = GenerationConfig(seed=13, scale=0.3).start_date
    late = logistics["warehouses"].filter(pl.col("opened_date") >= start)
    assert late.height == 0


def test_delivery_method_present_iff_delivered(logistics: dict[str, pl.DataFrame]) -> None:
    inconsistent = logistics["deliveries"].filter(
        (pl.col("status") == "delivered") != pl.col("delivery_method").is_not_null()
    )
    assert inconsistent.height == 0


def test_signature_parcels_deliver_via_signature(logistics: dict[str, pl.DataFrame]) -> None:
    delivered_sig = (
        logistics["deliveries"]
        .filter(pl.col("status") == "delivered")
        .join(logistics["shipments"].select("shipment_id", "signature_required"), on="shipment_id")
        .filter(pl.col("signature_required"))
    )
    off_path = delivered_sig.filter(pl.col("delivery_method") != "signature")
    assert off_path.height == 0


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
