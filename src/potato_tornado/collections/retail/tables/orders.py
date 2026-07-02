"""The ``orders`` table: the basket header, one row per order.

Each order belongs to a customer and is placed on/after that customer's
``signup_date`` (clipped into the run window). ``item_count`` is the realized number
of lines in the basket — `order_items` fans out exactly this many rows per order, so
the header count and the line count always agree (an invariant).
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Channel and status mixes, and the basket-size shape (single-table literals).
_CHANNELS = ["web", "mobile", "marketplace"]
_CHANNEL_WEIGHTS = [0.50, 0.40, 0.10]
_STATUSES = ["delivered", "shipped", "cancelled"]
_STATUS_WEIGHTS = [0.90, 0.05, 0.05]
_BASKET_LAMBDA = 1.5
# Tender mix (single-table literal), drawn independently of basket value.
_PAYMENT_METHODS = ["card", "paypal", "gift_card", "bnpl"]
_PAYMENT_WEIGHTS = [0.55, 0.22, 0.08, 0.15]
# Multiplicative order-volume weight by calendar month: a repeating within-year
# retail cycle — a Q4 holiday peak (Nov/Dec) and a post-holiday winter trough
# (Feb), ~1.9x peak-to-trough. Expected seasonality, not a subset signal.
_MONTH_SEASONALITY = {
    1: 0.85, 2: 0.80, 3: 0.90, 4: 0.90, 5: 0.95, 6: 0.95,
    7: 0.95, 8: 1.05, 9: 1.00, 10: 1.10, 11: 1.40, 12: 1.55,
}  # fmt: skip


def build_orders(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(12000)
    customers = ctx.table("customers")
    signup_of = dict(
        zip(customers["customer_id"].to_list(), customers["signup_date"].to_list(), strict=True)
    )

    customer_id = ctx.dist.choice(n, customers["customer_id"].to_list())

    start = ctx.config.start_date
    end = ctx.config.end_date
    total_span = (end - start).days
    # Seasonal order dates: sample each day in [max(start, signup), end) in
    # proportion to its month's seasonality weight (inverse-CDF over the window's
    # per-day cumulative weight). Never before the window and never before the
    # customer signed up, but with a repeating Q4 peak rather than a flat spread.
    day_weight = np.array(
        [_MONTH_SEASONALITY[(start + timedelta(days=d)).month] for d in range(total_span)]
    )
    cum = np.concatenate([[0.0], np.cumsum(day_weight)])  # length total_span + 1
    lo_idx = np.clip(
        np.array([(max(start, signup_of[c]) - start).days for c in customer_id]),
        0,
        total_span - 1,
    )
    target = cum[lo_idx] + ctx.rng.child("order_date").numpy.random(n) * (
        cum[total_span] - cum[lo_idx]
    )
    day_idx = np.clip(np.searchsorted(cum, target, side="right") - 1, lo_idx, total_span - 1)
    order_date = [start + timedelta(days=int(d)) for d in day_idx]

    item_count = 1 + ctx.rng.child("basket").numpy.poisson(_BASKET_LAMBDA, n)

    return pl.DataFrame(
        {
            "order_id": [f"ORD-{i:07d}" for i in range(1, n + 1)],
            "customer_id": customer_id,
            "order_date": order_date,
            "channel": ctx.dist.choice(n, _CHANNELS, _CHANNEL_WEIGHTS),
            "status": ctx.dist.choice(n, _STATUSES, _STATUS_WEIGHTS),
            "payment_method": ctx.rng.child("payment").numpy.choice(
                np.array(_PAYMENT_METHODS, dtype=object), size=n, p=_PAYMENT_WEIGHTS
            ),
            "item_count": item_count,
        }
    )
