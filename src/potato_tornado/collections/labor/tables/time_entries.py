"""The ``time_entries`` table: actual clock-in/out per assignment (reality)."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext


def build_time_entries(ctx: GenContext) -> pl.DataFrame:
    assignments = ctx.table("assignments")
    shifts = ctx.table("shifts").select(
        ["shift_id", "planned_start", "planned_end", "planned_hours"]
    )
    joined = assignments.join(shifts, on="shift_id", how="left")

    n = joined.height
    planned_start = joined["planned_start"].to_list()
    planned_hours = joined["planned_hours"].to_list()

    # ~4% no-shows; the rest clock in near the planned start with some spread.
    showed_up = ctx.dist.bernoulli(n, 0.96)
    start_jitter_min = ctx.dist.normal(n, 3.0, 9.0)  # slight tendency to be a bit late
    # Overtime: actual hours are planned + a right-skewed non-negative tail.
    overtime = np.clip(ctx.dist.normal(n, 0.15, 0.5), 0, None)

    actual_in: list[datetime | None] = []
    actual_out: list[datetime | None] = []
    worked_hours: list[float | None] = []
    for i in range(n):
        if not showed_up[i]:
            actual_in.append(None)
            actual_out.append(None)
            worked_hours.append(None)
            continue
        start = planned_start[i] + timedelta(minutes=float(start_jitter_min[i]))
        hours = float(planned_hours[i]) + float(overtime[i])
        end = start + timedelta(hours=hours)
        actual_in.append(start)
        actual_out.append(end)
        worked_hours.append(round(hours, 2))

    return pl.DataFrame(
        {
            "time_entry_id": [f"TME-{i:07d}" for i in range(1, n + 1)],
            "assignment_id": joined["assignment_id"],
            "employee_id": joined["employee_id"],
            "shift_id": joined["shift_id"],
            "clock_in": pl.Series(actual_in, dtype=pl.Datetime),
            "clock_out": pl.Series(actual_out, dtype=pl.Datetime),
            "worked_hours": pl.Series(worked_hours, dtype=pl.Float64),
            "planned_hours": joined["planned_hours"],
            "no_show": pl.Series([not s for s in showed_up], dtype=pl.Boolean),
        }
    )
