"""The ``customers`` table: the buyer dimension.

Each customer signs up somewhere from a couple of years before the window through
its end, then places orders on/after that date (`orders` conditions `order_date` on
`signup_date`). ``segment`` (new / returning / vip) is a coarse loyalty band.
"""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.core.collection import GenContext

# Loyalty bands (single-table literal).
_SEGMENTS = ["new", "returning", "vip"]
_SEGMENT_WEIGHTS = [0.45, 0.45, 0.10]


def build_customers(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(3000)
    people = ctx.entities.people(n)
    # Sign-ups spread from ~2 years before the window through its end, so most
    # customers predate the window (their orders then span it) while some join later.
    signup = ctx.dist.dates_between(
        n, ctx.config.start_date - timedelta(days=2 * 365), ctx.config.end_date
    )
    return pl.DataFrame(
        {
            "customer_id": [f"CUS-{i:06d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "city": ctx.entities.cities(n),
            "signup_date": signup,
            "segment": ctx.dist.choice(n, _SEGMENTS, _SEGMENT_WEIGHTS),
        }
    )
