"""Scenario signals for the retail collection (the teaching 'answer key')."""

from __future__ import annotations

import re
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


def _margin_by_category(retail: dict[str, pl.DataFrame]) -> dict[str, float]:
    margins = retail["products"].with_columns(
        ((pl.col("unit_price") - pl.col("cost")) / pl.col("unit_price")).alias("margin")
    )
    by_cat = margins.group_by("category").agg(pl.col("margin").mean().alias("margin"))
    return dict(zip(by_cat["category"], by_cat["margin"], strict=True))


def test_apparel_margin_runs_fat_while_electronics_runs_thin(
    retail: dict[str, pl.DataFrame],
) -> None:
    margins = _margin_by_category(retail)
    # apparel (highest-return) is fattest and electronics thinnest — the extremes
    # bracket the ~0.45 middle with a ~30-point spread that runs against returns.
    assert cast(float, margins["electronics"]) < 0.35 < 0.55 < cast(float, margins["apparel"])


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


# --- recovery-rate-hides-in-inspection-notes (document scenario) ------------------------
# The warehouse `inspection_note` free text is the source of truth: parse each note back into
# a disposition (restocked) + arrival condition, then read resale-recovery by category and
# discover it runs *against* the return-rate gradient (apparel highest-return AND
# highest-recovery; electronics low-return but lowest-recovery).


def _parse_note(text: str) -> tuple[str, bool]:
    """Deterministic extraction a student would run over a warehouse inspection note.

    Returns the parsed ``(item_condition, restocked)`` — the arrival condition
    (``resellable`` / ``opened`` / ``damaged``) and the disposition boolean.
    """
    t = text.lower()
    restocked = bool(re.search(r"sellable stock|back to stock|restock", t)) and not re.search(
        r"not resell|disposal|quarantin|scrap|write[- ]?off", t
    )
    if re.search(r"crack|shatter|won'?t (power|function)|torn|stain|damaged|broken|not usable", t):
        condition = "damaged"
    elif re.search(r"opened|unsealed|tried", t):
        condition = "opened"
    else:
        condition = "resellable"
    return condition, restocked


def _parsed_notes(retail: dict[str, pl.DataFrame]) -> pl.DataFrame:
    parsed = [_parse_note(n) for n in retail["returns"]["inspection_note"].to_list()]
    return (
        retail["returns"]
        .select("order_item_id", "item_condition", "restocked")
        .with_columns(
            pl.Series("parsed_condition", [c for c, _ in parsed]),
            pl.Series("parsed_restocked", [r for _, r in parsed]),
        )
    )


def _recovery_by_category(retail: dict[str, pl.DataFrame]) -> dict[str, float]:
    tagged = (
        _parsed_notes(retail)
        .join(retail["order_items"].select("order_item_id", "product_id"), on="order_item_id")
        .join(retail["products"].select("product_id", "category"), on="product_id")
    )
    by_cat = tagged.group_by("category").agg(pl.col("parsed_restocked").mean().alias("recovery"))
    return dict(zip(by_cat["category"], by_cat["recovery"], strict=True))


def test_inspection_notes_recover_arrival_condition(retail: dict[str, pl.DataFrame]) -> None:
    parsed = _parsed_notes(retail)
    assert (parsed["parsed_condition"] == parsed["item_condition"]).all()


def test_inspection_notes_recover_disposition(retail: dict[str, pl.DataFrame]) -> None:
    parsed = _parsed_notes(retail)
    assert (parsed["parsed_restocked"] == parsed["restocked"]).all()


@pytest.mark.parametrize(
    ("category", "expected"),
    [("apparel", 0.68), ("consumables", 0.52), ("home", 0.47), ("electronics", 0.45)],
)
def test_recovery_rate_by_category_matches_measured_magnitude(
    retail: dict[str, pl.DataFrame], category: str, expected: float
) -> None:
    recovery = _recovery_by_category(retail)
    assert abs(cast(float, recovery[category]) - expected) < 0.03


def test_recovery_runs_against_the_return_rate_gradient(retail: dict[str, pl.DataFrame]) -> None:
    recovery = _recovery_by_category(retail)
    rates = _return_rate_by_category(retail)
    # Apparel returns ~2.3x as often as electronics yet recovers a higher share of each return:
    # the high-volume return stream is the recoverable one, so recovery runs *against* the
    # return-rate gradient rather than tracking it.
    assert cast(float, rates["apparel"]) > cast(float, rates["electronics"]) and cast(
        float, recovery["apparel"]
    ) > cast(float, recovery["electronics"])
