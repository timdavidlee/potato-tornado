"""The ``room_types`` table: room categories and nightly rates per property."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.hotel.constants import ROOM_TYPES
from potato_tornado.core.collection import GenContext


def build_room_types(ctx: GenContext) -> pl.DataFrame:
    props = ctx.table("properties")
    prop_ids = props["property_id"].to_list()
    rows_prop: list[str] = []
    rows_type: list[str] = []
    rows_rate: list[float] = []
    rng = ctx.rng.numpy
    for pid in prop_ids:
        loc_mult = float(rng.normal(1.0, 0.12))
        for type_name, base_rate, _ in ROOM_TYPES:
            rows_prop.append(pid)
            rows_type.append(type_name)
            rows_rate.append(round(base_rate * max(0.7, loc_mult), 2))
    return pl.DataFrame(
        {
            "room_type_id": [f"RT-{i:04d}" for i in range(1, len(rows_prop) + 1)],
            "property_id": rows_prop,
            "room_type": rows_type,
            "nightly_rate": rows_rate,
        }
    )
