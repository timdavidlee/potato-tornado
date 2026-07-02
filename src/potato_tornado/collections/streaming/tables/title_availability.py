"""The ``title_availability`` table: which titles are licensed in which regions.

A many-to-many licensing bridge (one row per licensed title x region). Larger
markets carry more of the catalogue (see ``catalog_density`` in ``constants.py``),
so catalogue size varies by region. Every title is licensed somewhere — a title
that no market picked up is assigned to the widest market so it stays rentable.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.streaming.constants import REGIONS
from potato_tornado.core.collection import GenContext


def build_title_availability(ctx: GenContext) -> pl.DataFrame:
    title_ids = ctx.table("titles")["title_id"].to_list()
    n = len(title_ids)

    licensed_regions: list[str] = []
    licensed_titles: list[str] = []
    region_count = [0] * n
    for code, _name, _weight, density, _currency in REGIONS:
        mask = ctx.dist.bernoulli(n, density)
        for i, on in enumerate(mask):
            if on:
                licensed_titles.append(title_ids[i])
                licensed_regions.append(code)
                region_count[i] += 1

    # Orphan titles (licensed nowhere) go to the widest market so every title is
    # rentable in at least one region.
    default_region = REGIONS[0][0]
    for i, count in enumerate(region_count):
        if count == 0:
            licensed_titles.append(title_ids[i])
            licensed_regions.append(default_region)

    return pl.DataFrame({"title_id": licensed_titles, "region": licensed_regions})
