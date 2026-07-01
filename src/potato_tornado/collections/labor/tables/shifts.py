"""The ``shifts`` table: planned shifts with a required headcount and window."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.labor.constants import SHIFT_WINDOWS
from potato_tornado.core.collection import GenContext


def build_shifts(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(1600)
    depts = ctx.table("departments")["department_id"].to_list()

    days = ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date)
    window_idx = ctx.dist.integers(n, 0, len(SHIFT_WINDOWS) - 1)
    window_names = np.array([SHIFT_WINDOWS[i][0] for i in window_idx], dtype=object)
    start_hours = np.array([SHIFT_WINDOWS[i][1] for i in window_idx])
    durations = ctx.dist.choice(n, ["8", "10", "12"], [0.7, 0.2, 0.1]).astype(int)

    starts = np.array(
        [datetime(d.year, d.month, d.day, int(h)) for d, h in zip(days, start_hours, strict=True)],
        dtype=object,
    )
    ends = np.array(
        [s + timedelta(hours=int(h)) for s, h in zip(starts, durations, strict=True)], dtype=object
    )
    required = ctx.dist.integers(n, 2, 8)

    return pl.DataFrame(
        {
            "shift_id": [f"SHF-{i:06d}" for i in range(1, n + 1)],
            "department_id": ctx.dist.choice(n, depts),
            "shift_window": window_names,
            "planned_start": starts,
            "planned_end": ends,
            "planned_hours": durations,
            "required_headcount": required,
        }
    )
