"""The ``time_entries`` table: actual clock-in/out per assignment (reality)."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# No-show risk is not uniform across the day: night shifts are missed far more
# often than day shifts, so the ~4% overall rate concentrates on the night window.
_NO_SHOW_BY_WINDOW = {"morning": 0.02, "afternoon": 0.025, "night": 0.075}

# The overtime tail is driven by one department rather than spread evenly:
# Software Engineering runs long (release crunches) far more than the rest of the org.
_OVERTIME_HEAVY_DEPT = "Software Engineering"

# Probability a worked entry is billable client time, by the shift department's
# practice type. Delivery shifts are mostly billable; enabling (PMO / IT) shifts are
# mostly internal. An expected split — a realism mix, not a planted scenario.
_BILLABLE_P_BY_PRACTICE = {"delivery": 0.85, "enabling": 0.20}

# Timesheet-compliance mix on worked entries: most timesheets are approved, a few
# await review, a small tail is rejected; a small share is submitted after the
# deadline. Flat org-wide rates — realism enrichment, not a planted scenario.
_APPROVAL_STATES = ("approved", "pending", "rejected")
_APPROVAL_WEIGHTS = (0.90, 0.07, 0.03)
_SUBMITTED_LATE_P = 0.12


def build_time_entries(ctx: GenContext) -> pl.DataFrame:
    assignments = ctx.table("assignments")
    shifts = ctx.table("shifts").select(
        [
            "shift_id",
            "department_id",
            "shift_window",
            "planned_start",
            "planned_end",
            "planned_hours",
        ]
    )
    joined = assignments.join(shifts, on="shift_id", how="left")
    departments = ctx.table("departments")
    heavy_dept_id = dict(
        zip(departments["name"].to_list(), departments["department_id"].to_list(), strict=True)
    )[_OVERTIME_HEAVY_DEPT]
    dept_practice = dict(
        zip(
            departments["department_id"].to_list(),
            departments["practice_type"].to_list(),
            strict=True,
        )
    )

    n = joined.height
    planned_start = joined["planned_start"].to_list()
    planned_hours = joined["planned_hours"].to_list()
    windows = joined["shift_window"].to_list()
    dept_ids = joined["department_id"].to_list()

    # No-shows: ~4% overall, but the rate depends on the shift window (night ≫ day).
    no_show_p = np.array([_NO_SHOW_BY_WINDOW[w] for w in windows])
    showed_up = ctx.rng.child("attendance").numpy.random(n) >= no_show_p
    start_jitter_min = ctx.dist.normal(n, 3.0, 9.0)  # slight tendency to be a bit late
    # Overtime: actual hours are planned + a right-skewed non-negative tail.
    # Software Engineering draws from a heavier mean/spread, so it owns the long tail.
    is_heavy = np.array([d == heavy_dept_id for d in dept_ids])
    ot_mean = np.where(is_heavy, 0.6, 0.12)
    ot_sd = np.where(is_heavy, 1.3, 0.45)
    overtime = np.clip(
        ctx.rng.child("overtime").numpy.standard_normal(n) * ot_sd + ot_mean, 0, None
    )

    # Billable client time vs. internal, keyed to the shift department's practice
    # type; a no-show is never billable (no worked time). Own child stream so it
    # doesn't shift the attendance/overtime draws.
    billable_p = np.array([_BILLABLE_P_BY_PRACTICE[dept_practice[d]] for d in dept_ids])
    billable = (ctx.rng.child("billable").numpy.random(n) < billable_p) & showed_up

    # Timesheet-compliance fields: only worked entries have a timesheet to submit and
    # approve, so both are null on no-show rows (mirrors the null-clock rule). Own
    # child stream so the attendance/overtime/billable draws don't shift.
    timesheet_rng = ctx.rng.child("timesheet").numpy
    approval_draw = timesheet_rng.choice(
        np.array(_APPROVAL_STATES, dtype=object), size=n, p=_APPROVAL_WEIGHTS
    )
    late_draw = timesheet_rng.random(n) < _SUBMITTED_LATE_P
    approval_status = [str(approval_draw[i]) if showed_up[i] else None for i in range(n)]
    submitted_late = [bool(late_draw[i]) if showed_up[i] else None for i in range(n)]

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
            "billable": pl.Series(billable, dtype=pl.Boolean),
            "approval_status": pl.Series(approval_status, dtype=pl.Utf8),
            "submitted_late": pl.Series(submitted_late, dtype=pl.Boolean),
        }
    )
