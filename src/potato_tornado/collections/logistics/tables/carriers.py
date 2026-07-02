"""The ``carriers`` table: the carrier catalogue (dimension)."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.logistics.constants import CARRIERS
from potato_tornado.core.collection import GenContext


def build_carriers(ctx: GenContext) -> pl.DataFrame:
    # A fixed reference catalogue (source of truth `shipments` and `scan_events`
    # draw from) — not scaled by row count.
    return pl.DataFrame(
        {
            "carrier_id": [f"CAR-{i:02d}" for i in range(1, len(CARRIERS) + 1)],
            "carrier_name": [name for name, *_ in CARRIERS],
            "base_rate": [base for _name, base, *_ in CARRIERS],
            "per_kg_rate": [per_kg for _name, _base, per_kg, *_ in CARRIERS],
            "reliability": [rel for _name, _base, _per_kg, rel, *_ in CARRIERS],
            "transport_mode": [mode for *_, mode, _fuel in CARRIERS],
            "fuel_surcharge_pct": [fuel for *_, fuel in CARRIERS],
        }
    )
