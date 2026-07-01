"""The ``employees`` table: the workforce, tied to a home department."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.labor.constants import (
    EMPLOYMENT,
    EMPLOYMENT_WEIGHTS,
    ROLE_WEIGHTS,
    ROLES,
)
from potato_tornado.core.collection import GenContext


def build_employees(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(200)
    depts = ctx.table("departments")
    dept_ids = depts["department_id"].to_list()
    dept_rates = dict(zip(dept_ids, depts["base_hourly_rate"].to_list(), strict=True))

    dept_of = ctx.dist.choice(n, dept_ids)
    roles = ctx.dist.choice(n, ROLES, ROLE_WEIGHTS)
    # Seniority multiplier on top of the department's base rate.
    role_mult = {r: 1.0 + 0.18 * i for i, r in enumerate(ROLES)}
    jitter = ctx.dist.clamped_normal(n, 1.0, 0.06, 0.85, 1.2)
    rates = np.array(
        [dept_rates[d] * role_mult[r] * j for d, r, j in zip(dept_of, roles, jitter, strict=True)]
    )

    hire = ctx.dist.dates_between(
        n, ctx.config.start_date - timedelta(days=5 * 365), ctx.config.end_date
    )
    people = ctx.entities.people(n)

    return pl.DataFrame(
        {
            "employee_id": [f"EMP-{i:05d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "department_id": dept_of,
            "role": roles,
            "employment_type": ctx.dist.choice(n, EMPLOYMENT, EMPLOYMENT_WEIGHTS),
            "hire_date": hire,
            "hourly_rate": np.round(rates, 2),
        }
    )
