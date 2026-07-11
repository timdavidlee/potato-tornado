"""The ``expenses`` table: project expense lines beyond labor.

One row per project expense (T&E, subcontractor, software). Each project draws a
Poisson-few lines, priced by category, dated inside the project's run, and
optionally attributed to one of the project's staffed members. Expenses are
deliberately decoupled from ``projects.budget_amount`` (which prices labor only) —
they are a separate cost view, not reconciled against the budget.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Expense categories and their flat mix. Median amounts are category-scaled off a
# common base draw, so subcontractor lines dwarf a meal.
_CATEGORIES = ["travel", "lodging", "meals", "subcontractor", "software"]
_CATEGORY_WEIGHTS = [0.35, 0.20, 0.25, 0.08, 0.12]
_CATEGORY_SCALE = {
    "travel": 1.6,
    "lodging": 0.5,
    "meals": 0.12,
    "subcontractor": 12.0,
    "software": 2.4,
}
_BILLABLE_P = 0.70
# Share of lines attributed to a specific project member (the rest are project-level
# costs with no named employee).
_HAS_EMPLOYEE_P = 0.75


def build_expenses(ctx: GenContext) -> pl.DataFrame:
    projects = ctx.table("projects")
    proj_ids = projects["project_id"].to_list()
    proj_start = dict(zip(proj_ids, projects["start_date"].to_list(), strict=True))
    proj_end = dict(zip(proj_ids, projects["target_end_date"].to_list(), strict=True))

    # Members per project, so a line can be attributed to someone actually staffed.
    members = ctx.table("project_members")
    members_by_project: dict[str, list[str]] = {}
    for pid, emp in zip(
        members["project_id"].to_list(), members["employee_id"].to_list(), strict=True
    ):
        members_by_project.setdefault(pid, []).append(emp)

    # A Poisson-few lines per project.
    n_lines = ctx.dist.poisson(len(proj_ids), 4.0)
    rows_project: list[str] = []
    for pid, k in zip(proj_ids, n_lines, strict=True):
        rows_project.extend([pid] * int(k))

    n = len(rows_project)
    category = ctx.dist.choice(n, _CATEGORIES, _CATEGORY_WEIGHTS)
    base_amount = ctx.dist.money(n, median=500.0, sigma=0.7)
    amount = np.round(
        np.array([base_amount[i] * _CATEGORY_SCALE[category[i]] for i in range(n)]), 2
    )
    billable = ctx.dist.bernoulli(n, _BILLABLE_P)

    # Incurred date: uniform inside the project's [start_date, target_end_date].
    spans = np.array([(proj_end[pid] - proj_start[pid]).days for pid in rows_project])
    offsets = ctx.rng.numpy.integers(0, spans + 1)
    incurred_date = [
        proj_start[pid] + timedelta(days=int(off))
        for pid, off in zip(rows_project, offsets, strict=True)
    ]

    # Optionally attribute the line to a staffed member of that project.
    has_emp = ctx.dist.bernoulli(n, _HAS_EMPLOYEE_P)
    emp_rng = ctx.rng.numpy
    employee_id: list[str | None] = []
    for pid, take in zip(rows_project, has_emp, strict=True):
        pool = members_by_project.get(pid, [])
        employee_id.append(str(emp_rng.choice(pool)) if take and pool else None)

    return pl.DataFrame(
        {
            "expense_id": [f"EXP-{i:06d}" for i in range(1, n + 1)],
            "project_id": rows_project,
            "category": category,
            "amount": pl.Series(amount, dtype=pl.Float64),
            "billable": pl.Series(billable, dtype=pl.Boolean),
            "incurred_date": pl.Series(incurred_date, dtype=pl.Date),
            "employee_id": pl.Series(employee_id, dtype=pl.Utf8),
        }
    )
