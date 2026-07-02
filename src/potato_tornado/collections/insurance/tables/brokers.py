"""The ``brokers`` table: the selling-broker dimension."""

from __future__ import annotations

import polars as pl

from potato_tornado.core.collection import GenContext

# Coarse sales regions a broker covers — a single-table literal, so inline.
_REGIONS = ["Northeast", "South", "Midwest", "West"]


def build_brokers(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(40)
    people = ctx.entities.people(n)
    return pl.DataFrame(
        {
            "broker_id": [f"BRK-{i:03d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "region": ctx.dist.choice(n, _REGIONS),
        }
    )
