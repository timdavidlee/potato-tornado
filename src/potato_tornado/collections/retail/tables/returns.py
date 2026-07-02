"""The ``returns`` table: the subset of line items sent back.

A line is returned with a **category-dependent** propensity (apparel comes back far
more than consumables), at most once. The return's ``reason`` mix is also
category-specific — apparel skews to fit/mind-change, electronics to defects. The
refund is the whole line total (usually) or a restocking-fee partial, and never
exceeds the line total; ``refund_method`` records how it was issued (original
payment / store credit / exchange), drawn independently of reason.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.retail.constants import CATEGORIES, RETURN_REASONS
from potato_tornado.core.collection import GenContext

# Per-category mix over RETURN_REASONS (order:
# changed_mind, too_small, defective, not_as_described, damaged_in_transit).
_REASON_MIX = {
    "apparel": [0.35, 0.30, 0.10, 0.15, 0.10],
    "electronics": [0.15, 0.05, 0.40, 0.30, 0.10],
    "home": [0.30, 0.10, 0.25, 0.20, 0.15],
    "consumables": [0.30, 0.05, 0.30, 0.20, 0.15],
}
# Likelihood a returned item goes back to stock, by reason — defects/damage rarely do.
_RESTOCK_P = {
    "changed_mind": 0.90,
    "too_small": 0.90,
    "not_as_described": 0.50,
    "defective": 0.05,
    "damaged_in_transit": 0.05,
}
_FULL_REFUND_P = 0.90
_PARTIAL_LOW = 0.60
_PARTIAL_HIGH = 0.90
# How the refund is issued (single-table literal), drawn independently of reason.
_REFUND_METHODS = ["original_payment", "store_credit", "exchange"]
_REFUND_METHOD_WEIGHTS = [0.70, 0.22, 0.08]
_RETURN_MIN_DAYS = 5
_RETURN_MAX_DAYS = 30


def build_returns(ctx: GenContext) -> pl.DataFrame:
    items = (
        ctx.table("order_items")
        .join(ctx.table("products").select("product_id", "category"), on="product_id", how="left")
        .join(ctx.table("orders").select("order_id", "order_date"), on="order_id", how="left")
    )
    m = items.height
    return_rate_of = {c: r for c, _med, r, _w in CATEGORIES}

    category = items["category"].to_list()
    p_return = np.array([return_rate_of[c] for c in category])
    returned = ctx.rng.child("return").numpy.random(m) < p_return

    sub = items.filter(pl.Series(returned))
    k = sub.height
    sub_cat = sub["category"].to_list()

    # Reason: per-row draw against the category's cumulative reason mix.
    wmat = np.array([_REASON_MIX[c] for c in sub_cat])
    cum = np.cumsum(wmat / wmat.sum(axis=1, keepdims=True), axis=1)
    u = ctx.rng.child("reason").numpy.random(k)
    reason_idx = (u[:, None] <= cum).argmax(axis=1)
    reason = [RETURN_REASONS[i] for i in reason_idx]

    line_total = sub["line_total"].to_numpy()
    full = ctx.rng.child("refund_full").numpy.random(k) < _FULL_REFUND_P
    factor = ctx.rng.child("refund_partial").numpy.uniform(_PARTIAL_LOW, _PARTIAL_HIGH, k)
    refund_amount = np.round(np.where(full, line_total, line_total * factor), 2)

    restock_p = np.array([_RESTOCK_P[r] for r in reason])
    restocked = ctx.rng.child("restock").numpy.random(k) < restock_p

    refund_method = ctx.rng.child("refund_method").numpy.choice(
        np.array(_REFUND_METHODS, dtype=object), size=k, p=_REFUND_METHOD_WEIGHTS
    )

    order_dates = sub["order_date"].to_list()
    delay = ctx.rng.child("return_delay").numpy.integers(_RETURN_MIN_DAYS, _RETURN_MAX_DAYS + 1, k)
    end = ctx.config.end_date
    return_date = [
        min(d + timedelta(days=int(x)), end - timedelta(days=1))
        for d, x in zip(order_dates, delay, strict=True)
    ]

    return pl.DataFrame(
        {
            "return_id": [f"RET-{i:07d}" for i in range(1, k + 1)],
            "order_item_id": sub["order_item_id"],
            "order_id": sub["order_id"],
            "return_date": return_date,
            "reason": reason,
            "refund_amount": refund_amount,
            "refund_method": refund_method,
            "restocked": restocked,
        }
    )
