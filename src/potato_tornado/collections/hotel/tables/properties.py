"""The ``properties`` table: hotels in the group."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.hotel.constants import CITIES, HOTEL_BRAND, HOTEL_DESCRIPTORS
from potato_tornado.core.collection import GenContext


def build_properties(ctx: GenContext) -> pl.DataFrame:
    n = min(ctx.n(6), len(CITIES))
    cities = CITIES[:n]
    # Name each property "<brand> <descriptor> <city>", e.g. "Meridian Grand Lisbon":
    # one shared group brand, a distinct descriptor per property, then the city.
    descriptors = ctx.rng.numpy.choice(HOTEL_DESCRIPTORS, size=n, replace=False)
    return pl.DataFrame(
        {
            "property_id": [f"HOT-{i:03d}" for i in range(1, n + 1)],
            "name": [
                f"{HOTEL_BRAND} {descriptor} {city}"
                for descriptor, city in zip(descriptors, cities, strict=True)
            ],
            "city": cities,
            "total_rooms": ctx.dist.integers(n, 60, 220),
        }
    )
