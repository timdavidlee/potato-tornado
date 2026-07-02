"""The ``projects`` table: cross-functional initiatives staffed from the workforce.

Unlike shifts (which belong to a single department and roster only that
department's staff), a project is owned by one department but pulls members from
across the org — see ``project_members``. Each project runs from a primary
``location``; that location drives how much of its team is off-site.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.labor.constants import (
    BILLING_TYPE_WEIGHTS,
    BILLING_TYPES,
    INDUSTRIES,
    INDUSTRY_WEIGHTS,
    LOCATION_WEIGHTS,
    LOCATIONS,
    PROJECT_CODE_NAMES,
    PROJECT_PRIORITIES,
    PROJECT_PRIORITY_WEIGHTS,
    PROJECT_STATUS_WEIGHTS,
    PROJECT_STATUSES,
)
from potato_tornado.core.collection import GenContext


def _project_names(n: int) -> list[str]:
    """Unique project names by cycling the code-name list.

    The first pass uses the bare code name; later passes append a phase number so
    names stay unique at any scale. Example (with 3 code names, n=4):
        ["Atlas", "Beacon", "Cascade", "Atlas 2"]
    """
    base = PROJECT_CODE_NAMES
    names: list[str] = []
    for i in range(n):
        code = base[i % len(base)]
        phase = i // len(base)
        names.append(code if phase == 0 else f"{code} {phase + 1}")
    return names


def build_projects(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(40)
    dept_ids = ctx.table("departments")["department_id"].to_list()

    # Projects span the window; each runs for a few months from its start.
    start = ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date)
    duration_days = ctx.dist.integers(n, 60, 300)
    target_end = np.array(
        [s + timedelta(days=int(d)) for s, d in zip(start, duration_days, strict=True)],
        dtype=object,
    )

    # Main-stream categorical draws, in a fixed order so later additions (all on
    # their own child streams) never shift them. `client_name` is off the separate
    # entities stream, so its position here is immaterial.
    department_id = ctx.dist.choice(n, dept_ids)
    location_city = ctx.dist.choice(n, LOCATIONS, LOCATION_WEIGHTS)
    status = ctx.dist.choice(n, PROJECT_STATUSES, PROJECT_STATUS_WEIGHTS)
    industry = ctx.dist.choice(n, INDUSTRIES, INDUSTRY_WEIGHTS)
    billing_type = ctx.dist.choice(n, BILLING_TYPES, BILLING_TYPE_WEIGHTS)
    priority = ctx.dist.choice(n, PROJECT_PRIORITIES, PROJECT_PRIORITY_WEIGHTS)
    client_name = ctx.entities.companies(n)

    # Contracted budget: effective billable hours/day x duration, priced at a
    # per-project blended bill rate. Its own child stream, and deliberately
    # decoupled from actual staffing (see realism-guidance "Projects are decoupled").
    budget_rng = ctx.rng.child("budget").numpy
    daily_burn = budget_rng.lognormal(mean=np.log(32.0), sigma=0.4, size=n)
    budget_hours = np.round(duration_days * daily_burn).astype(np.int64)
    blended_rate = np.clip(budget_rng.normal(220.0, 25.0, size=n), 150.0, None)
    budget_amount = np.round(budget_hours * blended_rate, 2)

    # Actual end date — completed projects only: target end plus a right-skewed
    # slip (mostly a few days late, occasionally early). Null while still open.
    slip = np.round(ctx.rng.child("end_slip").numpy.lognormal(np.log(12.0), 0.7, size=n) - 9.0)
    actual_end: list[date | None] = [
        (t + timedelta(days=int(s))) if st == "completed" else None
        for t, s, st in zip(target_end, slip, status, strict=True)
    ]

    # Client satisfaction (completed only): a 1-5 CSAT skewed high. Null while open.
    csat = np.clip(np.round(ctx.rng.child("csat").numpy.normal(4.1, 0.7, size=n)), 1, 5)
    client_satisfaction: list[int | None] = [
        int(c) if st == "completed" else None for c, st in zip(csat, status, strict=True)
    ]

    return pl.DataFrame(
        {
            "project_id": [f"PRJ-{i:04d}" for i in range(1, n + 1)],
            "name": _project_names(n),
            # Owning cost centre; membership is cross-department (see project_members).
            "department_id": department_id,
            "location_city": location_city,
            "status": status,
            "client_name": client_name,
            "industry": industry,
            "billing_type": billing_type,
            "priority": priority,
            "start_date": start,
            "target_end_date": target_end,
            "budget_hours": budget_hours,
            "budget_amount": budget_amount,
            "actual_end_date": pl.Series(actual_end, dtype=pl.Date),
            "client_satisfaction": pl.Series(client_satisfaction, dtype=pl.Int8),
        }
    )
