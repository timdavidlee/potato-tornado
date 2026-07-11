"""The ``clients`` table: the client-account dimension behind ``projects``.

One row per client. A project's ``client_id`` points here, and the bare
``projects.client_name`` string becomes this dimension's ``name`` (denormalized
back onto projects for convenience). Clients carry a size ``tier``, an
``industry`` vertical, a relationship-start date, and an HQ office — the
attributes that make client-concentration, revenue-by-tier, and client-tenure
analysis possible (none computable while ``client_name`` was a bare per-project
string that recurred only by chance).
"""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.collections.labor.constants import (
    CLIENT_TIER_WEIGHTS,
    CLIENT_TIERS,
    INDUSTRIES,
    INDUSTRY_WEIGHTS,
    LOCATION_WEIGHTS,
    LOCATIONS,
)
from potato_tornado.core.collection import GenContext


def build_clients(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(20)

    # Client names come off the shared entities stream (Faker companies), like other
    # entity draws; the categorical attributes come off this table's root stream.
    name = ctx.entities.companies(n)
    tier = ctx.dist.choice(n, CLIENT_TIERS, CLIENT_TIER_WEIGHTS)
    industry = ctx.dist.choice(n, INDUSTRIES, INDUSTRY_WEIGHTS)
    hq_city = ctx.dist.choice(n, LOCATIONS, LOCATION_WEIGHTS)
    # The relationship can predate the dataset window (up to ~6 years before start).
    relationship_start_date = ctx.dist.dates_between(
        n, ctx.config.start_date - timedelta(days=6 * 365), ctx.config.end_date
    )

    return pl.DataFrame(
        {
            "client_id": [f"CLI-{i:04d}" for i in range(1, n + 1)],
            "name": name,
            "tier": tier,
            "industry": industry,
            "relationship_start_date": relationship_start_date,
            "hq_city": hq_city,
        }
    )
