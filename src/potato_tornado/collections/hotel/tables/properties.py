"""The ``properties`` table: hotels in the group."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.hotel.constants import CITIES
from potato_tornado.core.collection import GenContext


def build_properties(ctx: GenContext) -> pl.DataFrame:
    n = min(ctx.n(6), len(CITIES))
    cities = CITIES[:n]
    # Name each property "<surname> <city>", the surname taken from an entity.
    surnames = [name.split()[-1] for name in ctx.entities.people(n)["full_name"].to_list()]
    return pl.DataFrame(
        {
            "property_id": [f"HOT-{i:03d}" for i in range(1, n + 1)],
            "name": [f"{surname} {city}" for surname, city in zip(surnames, cities, strict=True)],
            "city": cities,
            "total_rooms": ctx.dist.integers(n, 60, 220),
        }
    )
