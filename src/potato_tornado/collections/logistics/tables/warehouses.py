"""The ``warehouses`` table: origin fulfillment centers (dimension)."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext
from potato_tornado.core.distributions import Distributions

# Coarse market regions a warehouse sits in — a single-table literal, so it stays
# inline rather than in constants.py.
_REGIONS = ["Northeast", "South", "Midwest", "West"]

# Facility footprint: lognormal capacity (units of storage/throughput) spreads
# hub-vs-satellite sizing, and a tenure window opening 1-10 years before the data
# window's start supports cohort analysis.
_CAPACITY_MEDIAN = 45_000.0
_CAPACITY_SIGMA = 0.55
_MAX_TENURE_DAYS = 3650
_MIN_TENURE_DAYS = 365


def build_warehouses(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(12)
    cities = ctx.entities.cities(n)
    # Name-keyed child streams so these dim attributes don't shift the `region`
    # draw (or downstream tables that sample `warehouse_id`).
    capacity_units = np.round(
        Distributions(ctx.rng.child("capacity")).lognormal(
            n, median=_CAPACITY_MEDIAN, sigma=_CAPACITY_SIGMA
        )
    ).astype(np.int64)
    start = ctx.config.start_date
    opened_date = Distributions(ctx.rng.child("opened")).dates_between(
        n, start - timedelta(days=_MAX_TENURE_DAYS), start - timedelta(days=_MIN_TENURE_DAYS)
    )
    return pl.DataFrame(
        {
            "warehouse_id": [f"WH-{i:03d}" for i in range(1, n + 1)],
            "city": cities,
            "region": ctx.dist.choice(n, _REGIONS),
            "capacity_units": capacity_units,
            "opened_date": opened_date,
        }
    )
