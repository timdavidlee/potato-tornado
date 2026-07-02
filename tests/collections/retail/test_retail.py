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
