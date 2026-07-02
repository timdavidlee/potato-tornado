"""The ``room_types`` table: room categories and nightly rates per property."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.hotel.constants import (
    INVENTORY_WEIGHT_BY_TYPE,
    MAX_OCCUPANCY_BY_TYPE,
    ROOM_TYPES,
)
from potato_tornado.core.collection import GenContext


def build_room_types(ctx: GenContext) -> pl.DataFrame:
    props = ctx.table("properties")
    prop_ids = props["property_id"].to_list()
    prop_total = dict(zip(prop_ids, props["total_rooms"].to_list(), strict=True))
    inv_weights = [INVENTORY_WEIGHT_BY_TYPE[name] for name, _, _ in ROOM_TYPES]
    rows_prop: list[str] = []
    rows_type: list[str] = []
    rows_rate: list[float] = []
    rows_max_occ: list[int] = []
    rows_count: list[int] = []
    rng = ctx.rng.numpy
    for pid in prop_ids:
        loc_mult = float(rng.normal(1.0, 0.12))
        # Split the property's physical rooms across the four classes so the per-class counts
        # sum exactly to total_rooms (deterministic apportionment, no RNG).
        counts = _apportion(int(prop_total[pid]), inv_weights)
        for (type_name, base_rate, _), count in zip(ROOM_TYPES, counts, strict=True):
            rows_prop.append(pid)
            rows_type.append(type_name)
            rows_rate.append(round(base_rate * max(0.7, loc_mult), 2))
            rows_max_occ.append(MAX_OCCUPANCY_BY_TYPE[type_name])
            rows_count.append(count)
    return pl.DataFrame(
        {
            "room_type_id": [f"RT-{i:04d}" for i in range(1, len(rows_prop) + 1)],
            "property_id": rows_prop,
            "room_type": rows_type,
            "nightly_rate": rows_rate,
            "max_occupancy": rows_max_occ,
            "room_count": rows_count,
        }
    )


def _apportion(total: int, weights: list[float]) -> list[int]:
    """Split ``total`` into integer parts proportional to ``weights``, summing exactly to
    ``total`` (largest-remainder / Hamilton method)."""
    raw = [w * total for w in weights]
    counts = [int(r) for r in raw]
    remainder = total - sum(counts)
    order = sorted(range(len(weights)), key=lambda i: raw[i] - counts[i], reverse=True)
    for i in range(remainder):
        counts[order[i]] += 1
    return counts
