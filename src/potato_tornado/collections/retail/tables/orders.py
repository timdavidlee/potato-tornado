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


def build_orders(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(12000)
    customers = ctx.table("customers")
    signup_of = dict(
        zip(customers["customer_id"].to_list(), customers["signup_date"].to_list(), strict=True)
    )

    customer_id = ctx.dist.choice(n, customers["customer_id"].to_list())

    start = ctx.config.start_date
    end = ctx.config.end_date
    # Order date is uniform in [max(start, signup), end): never before the window and
    # never before the customer signed up.
    base = [max(start, signup_of[c]) for c in customer_id]
    span = np.array([(end - b).days for b in base])
    offset = ctx.rng.child("order_date").numpy.integers(0, np.maximum(span, 1))
    order_date = [b + timedelta(days=int(o)) for b, o in zip(base, offset, strict=True)]

    item_count = 1 + ctx.rng.child("basket").numpy.poisson(_BASKET_LAMBDA, n)

    return pl.DataFrame(
        {
            "order_id": [f"ORD-{i:07d}" for i in range(1, n + 1)],
            "customer_id": customer_id,
            "order_date": order_date,
            "channel": ctx.dist.choice(n, _CHANNELS, _CHANNEL_WEIGHTS),
            "status": ctx.dist.choice(n, _STATUSES, _STATUS_WEIGHTS),
            "item_count": item_count,
        }
    )
