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


def test_bounds_hold(retail: dict[str, pl.DataFrame]) -> None:
    items = retail["order_items"]
    ok = (
        items.filter((pl.col("quantity") < 1) | (pl.col("quantity") > 3)).height == 0
        and items.filter((pl.col("unit_price") < 1) | (pl.col("unit_price") > 500)).height == 0
        and retail["returns"].filter(pl.col("refund_amount") <= 0).height == 0
    )
    assert ok
