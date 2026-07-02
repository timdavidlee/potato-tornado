"""The ``regions`` table: the markets the service operates in."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.streaming.constants import REGIONS
from potato_tornado.core.collection import GenContext


def build_regions(ctx: GenContext) -> pl.DataFrame:
    # A fixed reference catalogue (the source `subscribers` and
    # `title_availability` draw from) — not scaled by row count.
    return pl.DataFrame(
        {
            "region": [code for code, *_ in REGIONS],
            "name": [name for _code, name, *_ in REGIONS],
            "currency": [currency for *_, currency in REGIONS],
        }
    )
