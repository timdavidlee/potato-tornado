"""The ``departments`` table: cost centres that own shifts and staff."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.labor.constants import DEPARTMENTS, ENABLING_DEPARTMENTS
from potato_tornado.core.collection import GenContext


def build_departments(ctx: GenContext) -> pl.DataFrame:
    names = [name for name, _ in DEPARTMENTS]
    return pl.DataFrame(
        {
            "department_id": [f"DEP-{i:02d}" for i in range(1, len(DEPARTMENTS) + 1)],
            "name": names,
            "base_hourly_rate": [rate for _, rate in DEPARTMENTS],
            # Delivery (client-billable) vs. enabling (overhead) practice. Pure lookup.
            "practice_type": [
                "enabling" if name in ENABLING_DEPARTMENTS else "delivery" for name in names
            ],
        }
    )
