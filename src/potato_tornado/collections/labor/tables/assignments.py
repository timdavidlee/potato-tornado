"""The ``assignments`` table: employees rostered onto shifts (the plan)."""

from __future__ import annotations

import polars as pl

from potato_tornado.core.collection import GenContext


def build_assignments(ctx: GenContext) -> pl.DataFrame:
    shifts = ctx.table("shifts")
    employees = ctx.table("employees")

    # Group employees by department so people are rostered within their department.
    emp_by_dept: dict[str, list[str]] = {}
    for emp_id, dept in zip(
        employees["employee_id"].to_list(), employees["department_id"].to_list(), strict=True
    ):
        emp_by_dept.setdefault(dept, []).append(emp_id)

    # Employment window per employee, so a shift only rosters staff employed that day
    # (hired on/before it, not yet terminated) — nobody works before hire or after leaving.
    emp_hire = dict(
        zip(employees["employee_id"].to_list(), employees["hire_date"].to_list(), strict=True)
    )
    emp_term = dict(
        zip(
            employees["employee_id"].to_list(), employees["termination_date"].to_list(), strict=True
        )
    )

    rng = ctx.rng.numpy
    rows_shift: list[str] = []
    rows_emp: list[str] = []
    for shift_id, dept, required, planned_start in zip(
        shifts["shift_id"].to_list(),
        shifts["department_id"].to_list(),
        shifts["required_headcount"].to_list(),
        shifts["planned_start"].to_list(),
        strict=True,
    ):
        shift_day = planned_start.date()
        pool = [
            e
            for e in emp_by_dept.get(dept, [])
            if emp_hire[e] <= shift_day and (emp_term[e] is None or shift_day < emp_term[e])
        ]
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
