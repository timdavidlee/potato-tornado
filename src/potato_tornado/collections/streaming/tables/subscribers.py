"""The ``subscribers`` table: the service's user accounts."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.streaming.constants import REGIONS
from potato_tornado.core.collection import GenContext


def build_subscribers(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(2000)
    people = ctx.entities.people(n)
    codes = [code for code, *_ in REGIONS]
    weights = [weight for _code, _name, weight, _density in REGIONS]
    return pl.DataFrame(
        {
            "subscriber_id": [f"SUB-{i:06d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "signup_date": ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date),
            "region": ctx.dist.choice(n, codes, weights),
        }
    )
