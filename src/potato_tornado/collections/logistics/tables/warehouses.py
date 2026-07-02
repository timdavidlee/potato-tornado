"""The ``warehouses`` table: origin fulfillment centers (dimension)."""

from __future__ import annotations

import polars as pl

from potato_tornado.core.collection import GenContext

# Coarse market regions a warehouse sits in — a single-table literal, so it stays
# inline rather than in constants.py.
_REGIONS = ["Northeast", "South", "Midwest", "West"]


def build_warehouses(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(12)
    cities = ctx.entities.cities(n)
    return pl.DataFrame(
        {
            "warehouse_id": [f"WH-{i:03d}" for i in range(1, n + 1)],
            "city": cities,
            "region": ctx.dist.choice(n, _REGIONS),
        }
    )
