"""The ``properties`` table: hotels in the group."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.collections.hotel.constants import (
    CITIES,
    CITY_GEO,
    HOTEL_BRAND,
    HOTEL_DESCRIPTORS,
    STAR_RATING_WEIGHTS,
    STAR_RATINGS,
)
from potato_tornado.core.collection import GenContext


def build_properties(ctx: GenContext) -> pl.DataFrame:
    n = min(ctx.n(6), len(CITIES))
    cities = CITIES[:n]
    # Name each property "<brand> <descriptor> <city>", e.g. "Meridian Grand Lisbon":
    # one shared group brand, a distinct descriptor per property, then the city.
    descriptors = ctx.rng.numpy.choice(HOTEL_DESCRIPTORS, size=n, replace=False)
    # Geography rolls up from the city; star rating and opening date are drawn from their
    # own child streams so adding them doesn't shift the descriptor / total_rooms draws.
    star_rating = ctx.rng.child("star").numpy.choice(STAR_RATINGS, size=n, p=STAR_RATING_WEIGHTS)
    # Opened 2-15 years before the data window -> maturity cohorts for like-for-like analysis.
    open_offsets = ctx.rng.child("opening").numpy.integers(2 * 365, 15 * 365, size=n)
    opening_date = [ctx.config.start_date - timedelta(days=int(o)) for o in open_offsets]
    return pl.DataFrame(
        {
            "property_id": [f"HOT-{i:03d}" for i in range(1, n + 1)],
            "name": [
                f"{HOTEL_BRAND} {descriptor} {city}"
                for descriptor, city in zip(descriptors, cities, strict=True)
            ],
            "city": cities,
            "country": [CITY_GEO[c][0] for c in cities],
            "region": [CITY_GEO[c][1] for c in cities],
            "star_rating": star_rating,
            "opening_date": opening_date,
            "total_rooms": ctx.dist.integers(n, 60, 220),
        }
    )
