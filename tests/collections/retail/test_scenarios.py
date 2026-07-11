"""Scenario signals for the retail collection (the teaching 'answer key')."""

from __future__ import annotations

from typing import cast

import polars as pl
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def retail() -> dict[str, pl.DataFrame]:
    return generate("retail", GenerationConfig(seed=7, scale=0.5))


def _return_rate_by_category(retail: dict[str, pl.DataFrame]) -> dict[str, float]:
    returned_ids = retail["returns"]["order_item_id"]
    tagged = (
        retail["order_items"]
        .join(retail["products"].select("product_id", "category"), on="product_id")
        .with_columns(pl.col("order_item_id").is_in(returned_ids.implode()).alias("returned"))
    )
    by_cat = tagged.group_by("category").agg(pl.col("returned").mean().alias("rate"))
    return dict(zip(by_cat["category"], by_cat["rate"], strict=True))


def test_apparel_returns_far_more_than_consumables(retail: dict[str, pl.DataFrame]) -> None:
    rates = _return_rate_by_category(retail)
    assert cast(float, rates["apparel"]) > 5 * cast(float, rates["consumables"])


def test_return_rate_climbs_across_categories(retail: dict[str, pl.DataFrame]) -> None:
    rates = _return_rate_by_category(retail)
    ordered = ["consumables", "home", "electronics", "apparel"]
    values = [cast(float, rates[c]) for c in ordered]
    assert values == sorted(values)


def test_basket_value_is_right_skewed(retail: dict[str, pl.DataFrame]) -> None:
    basket = retail["order_items"].group_by("order_id").agg(pl.col("line_total").sum().alias("v"))
    assert cast(float, basket["v"].mean()) > cast(float, basket["v"].median())


def test_apparel_returns_skew_to_fit_and_mind_change(retail: dict[str, pl.DataFrame]) -> None:
    apparel = (
        retail["returns"]
        .join(retail["order_items"].select("order_item_id", "product_id"), on="order_item_id")
        .join(retail["products"].select("product_id", "category"), on="product_id")
        .filter(pl.col("category") == "apparel")
    )
    fit_share = (
        apparel.filter(pl.col("reason").is_in(["changed_mind", "too_small"])).height
        / apparel.height
    )
    assert fit_share > 0.5


def test_defective_leads_electronics_returns(retail: dict[str, pl.DataFrame]) -> None:
    electronics = (
        retail["returns"]
        .join(retail["order_items"].select("order_item_id", "product_id"), on="order_item_id")
        .join(retail["products"].select("product_id", "category"), on="product_id")
        .filter(pl.col("category") == "electronics")
        .group_by("reason")
        .len()
        .sort("len", descending=True)
    )
    assert electronics["reason"][0] == "defective"


def test_shipping_revenue_concentrates_in_small_baskets(retail: dict[str, pl.DataFrame]) -> None:
    charges = retail["order_charges"]
    small = charges.filter(pl.col("merchandise") < 25)
    order_share = small.height / charges.height
    revenue_share = cast(float, small["shipping_fee"].sum()) / cast(
        float, charges["shipping_fee"].sum()
    )
    assert order_share < 0.2 < 0.4 < revenue_share
