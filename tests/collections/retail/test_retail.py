"""Tests for the retail collection.

These pin the realism invariants from ``realism-guidance.md`` (referential
integrity, the header/line fan-out consistency, one-return-per-line, arithmetic
identities, temporal ordering, bounds) — the rules that must hold regardless of any
teaching signal. Subset-signal magnitudes live in ``test_scenarios.py``.
"""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def retail() -> dict[str, pl.DataFrame]:
    return generate("retail", GenerationConfig(seed=13, scale=0.3))


def test_orders_reference_customers(retail: dict[str, pl.DataFrame]) -> None:
    customer_ids = set(retail["customers"]["customer_id"].to_list())
    assert set(retail["orders"]["customer_id"].to_list()) <= customer_ids


def test_order_items_reference_orders_and_products(retail: dict[str, pl.DataFrame]) -> None:
    order_ids = set(retail["orders"]["order_id"].to_list())
    product_ids = set(retail["products"]["product_id"].to_list())
    items = retail["order_items"]
    orders_ok = set(items["order_id"].to_list()) <= order_ids
    products_ok = set(items["product_id"].to_list()) <= product_ids
    assert orders_ok and products_ok


def test_returns_reference_order_items(retail: dict[str, pl.DataFrame]) -> None:
    item_ids = set(retail["order_items"]["order_item_id"].to_list())
    assert set(retail["returns"]["order_item_id"].to_list()) <= item_ids


def test_at_most_one_return_per_line(retail: dict[str, pl.DataFrame]) -> None:
    returns = retail["returns"]
    assert returns["order_item_id"].n_unique() == returns.height


def test_item_count_matches_realized_lines(retail: dict[str, pl.DataFrame]) -> None:
    header_lines = int(retail["orders"]["item_count"].sum())
    assert header_lines == retail["order_items"].height


def test_line_total_matches_the_identity(retail: dict[str, pl.DataFrame]) -> None:
    items = retail["order_items"]
    mismatch = items.filter(
        (pl.col("quantity") * pl.col("unit_price")).round(2) != pl.col("line_total")
    )
    assert mismatch.height == 0


def test_refund_never_exceeds_line_total(retail: dict[str, pl.DataFrame]) -> None:
    priced = retail["returns"].join(
        retail["order_items"].select("order_item_id", "line_total"), on="order_item_id"
    )
    assert priced.filter(pl.col("refund_amount") > pl.col("line_total")).height == 0


def test_return_date_on_or_after_order_date(retail: dict[str, pl.DataFrame]) -> None:
    dated = retail["returns"].join(retail["orders"].select("order_id", "order_date"), on="order_id")
    assert dated.filter(pl.col("return_date") < pl.col("order_date")).height == 0


def test_order_date_on_or_after_signup(retail: dict[str, pl.DataFrame]) -> None:
    dated = retail["orders"].join(
        retail["customers"].select("customer_id", "signup_date"), on="customer_id"
    )
    assert dated.filter(pl.col("order_date") < pl.col("signup_date")).height == 0


def test_order_date_within_run_window(retail: dict[str, pl.DataFrame]) -> None:
    config = GenerationConfig(seed=13, scale=0.3)
    orders = retail["orders"]
    out_of_window = orders.filter(
        (pl.col("order_date") < config.start_date) | (pl.col("order_date") >= config.end_date)
    )
    assert out_of_window.height == 0


def test_bounds_hold(retail: dict[str, pl.DataFrame]) -> None:
    items = retail["order_items"]
    ok = (
        items.filter((pl.col("quantity") < 1) | (pl.col("quantity") > 3)).height == 0
        and items.filter((pl.col("unit_price") < 1) | (pl.col("unit_price") > 500)).height == 0
        and retail["returns"].filter(pl.col("refund_amount") <= 0).height == 0
    )
    assert ok


def test_weight_kg_within_bounds(retail: dict[str, pl.DataFrame]) -> None:
    products = retail["products"]
    assert products.filter((pl.col("weight_kg") < 0.05) | (pl.col("weight_kg") > 30)).height == 0


def test_discount_pct_within_bounds(retail: dict[str, pl.DataFrame]) -> None:
    # Per-line markdown is 0 for most lines, else a tier in {0.10..0.40}; it never
    # escapes [0, 0.6]. `line_total` stays gross (net = line_total * (1 - discount_pct)).
    items = retail["order_items"]
    assert items.filter((pl.col("discount_pct") < 0) | (pl.col("discount_pct") > 0.6)).height == 0


def test_cost_below_unit_price_and_positive(retail: dict[str, pl.DataFrame]) -> None:
    # `cost = round(unit_price * (1 - margin), 2)` with a flat margin clamped into
    # (0, 1), so every SKU satisfies 0 < cost < unit_price (a real gross margin).
    products = retail["products"]
    assert (
        products.filter((pl.col("cost") <= 0) | (pl.col("cost") >= pl.col("unit_price"))).height
        == 0
    )


def test_discount_amount_positive_iff_promo_code(retail: dict[str, pl.DataFrame]) -> None:
    # A promo order has a code and a positive fixed discount; a non-promo order has a
    # null code and 0.0 discount. So discount_amount > 0 iff promo_code is not null, and
    # discount_amount is never negative.
    orders = retail["orders"]
    mismatch = (pl.col("discount_amount") > 0) != pl.col("promo_code").is_not_null()
    negative = pl.col("discount_amount") < 0
    assert orders.filter(mismatch | negative).height == 0


def test_free_shipping_at_or_above_threshold(retail: dict[str, pl.DataFrame]) -> None:
    # shipping_fee is free once merchandise reaches the free-ship threshold; below it a
    # tiered fee applies. So no order at/above the threshold ever carries a positive fee.
    from potato_tornado.collections.retail.tables.order_charges import _FREE_SHIP_THRESHOLD

    merch = (
        retail["order_items"]
        .group_by("order_id")
        .agg(pl.col("line_total").sum().round(2).alias("merchandise"))
    )
    charged = retail["order_charges"].join(merch, on="order_id", how="left")
    above = charged.filter(
        (pl.col("merchandise") >= _FREE_SHIP_THRESHOLD) & (pl.col("shipping_fee") > 0)
    )
    assert above.height == 0


@pytest.mark.parametrize(
    ("table", "column", "allowed"),
    [
        ("orders", "payment_method", {"card", "paypal", "gift_card", "bnpl"}),
        (
            "customers",
            "acquisition_channel",
            {"organic", "paid_search", "social", "referral", "email"},
        ),
        ("returns", "refund_method", {"original_payment", "store_credit", "exchange"}),
        ("returns", "item_condition", {"resellable", "opened", "damaged"}),
    ],
)
def test_categorical_fields_stay_in_catalog(
    retail: dict[str, pl.DataFrame], table: str, column: str, allowed: set[str]
) -> None:
    assert set(retail[table][column].to_list()) <= allowed


def test_brand_matches_product_category(retail: dict[str, pl.DataFrame]) -> None:
    from potato_tornado.collections.retail.tables.products import _BRANDS

    products = retail["products"]
    off_catalog = [
        (cat, brand)
        for cat, brand in zip(
            products["category"].to_list(), products["brand"].to_list(), strict=True
        )
        if brand not in _BRANDS[cat]
    ]
    assert off_catalog == []


def test_product_names_are_mostly_distinct(retail: dict[str, pl.DataFrame]) -> None:
    # The adjective/qualifier/noun triple keeps duplicate names rare (≈0.95 at this
    # seed); guard against a regression back to the narrow adjective+noun lattice.
    products = retail["products"]
    assert products["product_name"].n_unique() / products.height > 0.85


def test_order_volume_peaks_in_q4(retail: dict[str, pl.DataFrame]) -> None:
    # Seasonal weighting concentrates orders into Nov/Dec (~0.32 share at this seed),
    # well above the 2/12 ≈ 0.167 a flat calendar would give.
    orders = retail["orders"].with_columns(pl.col("order_date").dt.month().alias("month"))
    q4_share = orders.filter(pl.col("month").is_in([11, 12])).height / orders.height
    assert q4_share > 0.25


def test_restock_rate_tracks_item_condition(retail: dict[str, pl.DataFrame]) -> None:
    # `restocked` keys off `item_condition`: resellable items restock far more than
    # damaged ones (~0.97 vs ~0.04). A flat gap would mean the mediation broke.
    rates = (
        retail["returns"].group_by("item_condition").agg(pl.col("restocked").mean().alias("rate"))
    )
    lookup = dict(zip(rates["item_condition"].to_list(), rates["rate"].to_list(), strict=True))
    assert lookup["resellable"] - lookup["damaged"] > 0.5


def test_damage_reasons_arrive_mostly_damaged(retail: dict[str, pl.DataFrame]) -> None:
    # item_condition correlates with reason: defect/transit-damage returns arrive in
    # `damaged` condition the majority of the time (mix is 0.80-0.87 damaged).
    damage_reasons = retail["returns"].filter(
        pl.col("reason").is_in(["defective", "damaged_in_transit"])
    )
    damaged_share = damage_reasons.filter(pl.col("item_condition") == "damaged").height
    assert damaged_share / damage_reasons.height > 0.6
