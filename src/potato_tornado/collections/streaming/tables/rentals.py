"""The ``rentals`` table: one-off premium (PVOD) rentals, separate from the sub.

A rental is a single pay-per-view purchase of a premium-eligible title, billed
on top of whatever subscription the account holds — the collection's second
revenue stream alongside recurring subscriptions.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.streaming.constants import PREMIUM_RENTAL_PRICES
from potato_tornado.core.collection import GenContext


def build_rentals(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(1500)
    subscribers = ctx.table("subscribers")["subscriber_id"].to_list()

    titles = ctx.table("titles")
    premium = titles.filter(pl.col("is_premium"))
    # Fall back to the full catalogue if a tiny scale yields no premium titles.
    title_ids = (premium if premium.height > 0 else titles)["title_id"].to_list()

    price_idx = ctx.dist.integers(n, 0, len(PREMIUM_RENTAL_PRICES) - 1)
    prices = [PREMIUM_RENTAL_PRICES[int(i)] for i in price_idx]

    return pl.DataFrame(
        {
            "rental_id": [f"RNT-{i:07d}" for i in range(1, n + 1)],
            "subscriber_id": ctx.dist.choice(n, subscribers),
            "title_id": ctx.dist.choice(n, title_ids),
            "rented_date": ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date),
            "price": prices,
        }
    )
