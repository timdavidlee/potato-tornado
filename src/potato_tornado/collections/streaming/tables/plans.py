"""The ``plans`` table: the subscription-tier catalogue."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.streaming.constants import PLANS
from potato_tornado.core.collection import GenContext


def build_plans(ctx: GenContext) -> pl.DataFrame:
    # A fixed reference catalogue — not scaled by row count.
    return pl.DataFrame(
        {
            "plan": [name for name, _price, _weight in PLANS],
            "monthly_price": [price for _name, price, _weight in PLANS],
        }
    )
