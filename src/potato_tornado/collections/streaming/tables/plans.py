"""The ``plans`` table: the subscription-tier catalogue."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.streaming.constants import PLANS
from potato_tornado.core.collection import GenContext


def build_plans(ctx: GenContext) -> pl.DataFrame:
    # A fixed reference catalogue — not scaled by row count.
    return pl.DataFrame(
        {
            "plan": [name for name, *_ in PLANS],
            "monthly_price": [price for _name, price, *_ in PLANS],
            "max_streams": [streams for *_, streams, _quality, _ads in PLANS],
            "video_quality": [quality for *_, quality, _ads in PLANS],
            "ad_supported": [ads for *_, ads in PLANS],
        }
    )
