"""Collection: labor assignment and utilization.

Models a workforce being scheduled onto shifts and how actual attendance compares
to what was planned — the raw material for utilization and overtime analysis.

Tables
------
- ``departments``   : cost centres that own shifts and staff.
- ``employees``     : the workforce, tied to a home department.
- ``shifts``        : planned shifts with a required headcount and a time window.
- ``assignments``   : employees rostered onto shifts (the plan).
- ``time_entries``  : actual clock-in / clock-out per assignment (the reality),
                      including no-shows, late starts and overtime.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import Collection, GenContext, TableSpec
from potato_tornado.core.registry import register

_DEPARTMENTS = [
    ("Front of House", 26.0),
    ("Kitchen", 24.0),
    ("Housekeeping", 21.0),
    ("Maintenance", 28.0),
    ("Warehouse", 23.0),
    ("Logistics", 27.0),
    ("Guest Services", 25.0),
    ("Security", 24.5),
]

_ROLES = ["Associate", "Senior Associate", "Lead", "Supervisor", "Manager"]
_ROLE_WEIGHTS = [0.5, 0.25, 0.13, 0.08, 0.04]
_EMPLOYMENT = ["full_time", "part_time", "contractor"]
_EMPLOYMENT_WEIGHTS = [0.6, 0.3, 0.1]
_SHIFT_WINDOWS = [("morning", 6), ("afternoon", 14), ("night", 22)]


def _build_departments(ctx: GenContext) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "department_id": [f"DEP-{i:02d}" for i in range(1, len(_DEPARTMENTS) + 1)],
            "name": [name for name, _ in _DEPARTMENTS],
            "base_hourly_rate": [rate for _, rate in _DEPARTMENTS],
        }
    )


def _build_employees(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(200)
    depts = ctx.table("departments")
    dept_ids = depts["department_id"].to_list()
    dept_rates = dict(zip(dept_ids, depts["base_hourly_rate"].to_list(), strict=True))

    dept_of = ctx.dist.choice(n, dept_ids)
    roles = ctx.dist.choice(n, _ROLES, _ROLE_WEIGHTS)
    # Seniority multiplier on top of the department's base rate.
    role_mult = {r: 1.0 + 0.18 * i for i, r in enumerate(_ROLES)}
    jitter = ctx.dist.clamped_normal(n, 1.0, 0.06, 0.85, 1.2)
    rates = np.array(
        [dept_rates[d] * role_mult[r] * j for d, r, j in zip(dept_of, roles, jitter, strict=True)]
    )

    hire = ctx.dist.dates_between(
        n, ctx.config.start_date - timedelta(days=5 * 365), ctx.config.end_date
    )

    return pl.DataFrame(
        {
            "employee_id": [f"EMP-{i:05d}" for i in range(1, n + 1)],
            "full_name": [ctx.faker.name() for _ in range(n)],
            "email": [ctx.faker.unique.email() for _ in range(n)],
            "department_id": dept_of,
            "role": roles,
            "employment_type": ctx.dist.choice(n, _EMPLOYMENT, _EMPLOYMENT_WEIGHTS),
            "hire_date": hire,
            "hourly_rate": np.round(rates, 2),
        }
    )


def _build_shifts(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(1600)
    depts = ctx.table("departments")["department_id"].to_list()

    days = ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date)
    window_idx = ctx.dist.integers(n, 0, len(_SHIFT_WINDOWS) - 1)
    window_names = np.array([_SHIFT_WINDOWS[i][0] for i in window_idx], dtype=object)
    start_hours = np.array([_SHIFT_WINDOWS[i][1] for i in window_idx])
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


def _build_assignments(ctx: GenContext) -> pl.DataFrame:
    shifts = ctx.table("shifts")
    employees = ctx.table("employees")

    # Group employees by department so people are rostered within their department.
    emp_by_dept: dict[str, list[str]] = {}
    for emp_id, dept in zip(
        employees["employee_id"].to_list(), employees["department_id"].to_list(), strict=True
    ):
        emp_by_dept.setdefault(dept, []).append(emp_id)

    rng = ctx.rng.numpy
    rows_shift: list[str] = []
    rows_emp: list[str] = []
    for shift_id, dept, required in zip(
        shifts["shift_id"].to_list(),
        shifts["department_id"].to_list(),
        shifts["required_headcount"].to_list(),
        strict=True,
    ):
        pool = emp_by_dept.get(dept, [])
        if not pool:
            continue
        # Roster roughly the required headcount, occasionally over/understaffed.
        target = max(1, round(required * rng.normal(1.0, 0.15)))
        picked = rng.choice(pool, size=min(target, len(pool)), replace=False)
        rows_shift.extend([shift_id] * len(picked))
        rows_emp.extend(picked.tolist())

    n = len(rows_shift)
    return pl.DataFrame(
        {
            "assignment_id": [f"ASG-{i:07d}" for i in range(1, n + 1)],
            "shift_id": rows_shift,
            "employee_id": rows_emp,
            "assigned_role": ctx.dist.choice(n, ["primary", "backup"], [0.85, 0.15]),
        }
    )


def _build_time_entries(ctx: GenContext) -> pl.DataFrame:
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


def build() -> Collection:
    return Collection(
        name="labor",
        description="Labor assignment and utilization: staff, planned shifts, "
        "rosters, and actual attendance vs. plan.",
        tables=(
            TableSpec("departments", _build_departments, description="Cost centres."),
            TableSpec(
                "employees",
                _build_employees,
                depends_on=("departments",),
                description="Workforce with roles and pay rates.",
            ),
            TableSpec(
                "shifts",
                _build_shifts,
                depends_on=("departments",),
                description="Planned shifts and required headcount.",
            ),
            TableSpec(
                "assignments",
                _build_assignments,
                depends_on=("shifts", "employees"),
                description="Employees rostered onto shifts.",
            ),
            TableSpec(
                "time_entries",
                _build_time_entries,
                depends_on=("assignments", "shifts"),
                description="Actual clock-in/out, no-shows and overtime.",
            ),
        ),
    )


register("labor", build)
