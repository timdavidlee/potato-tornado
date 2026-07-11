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

# Seniority rungs that can own an engagement (the accountable partner), most senior
# first choice. The pool widens down this list if a project's start_date isn't
# covered by anyone senior enough (a small workforce can leave the senior pool
# empty at a given date).
_ENGAGEMENT_MANAGER_ROLES = {"Supervisor", "Manager"}
_ENGAGEMENT_LEAD_PLUS = {"Lead", "Supervisor", "Manager"}


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

    # Client: each project is for a client from the `clients` dimension. Sample a
    # client_id on its own child stream, then denormalize the client's name back onto
    # the project (replacing the former bare Faker company string). Own child stream
    # so the main-stream categorical draws above don't shift.
    clients = ctx.table("clients")
    client_ids = clients["client_id"].to_list()
    client_name_by_id = dict(zip(client_ids, clients["name"].to_list(), strict=True))
    client_idx = ctx.rng.child("client").numpy.integers(0, len(client_ids), size=n)
    client_id = [client_ids[int(i)] for i in client_idx]
    client_name = [client_name_by_id[cid] for cid in client_id]

    # Contracted budget: effective billable hours/day x duration, priced at a
    # per-project blended bill rate. Its own child stream, and deliberately
    # decoupled from actual staffing (see realism-guidance "Projects are decoupled").
    budget_rng = ctx.rng.child("budget").numpy
    daily_burn = budget_rng.lognormal(mean=np.log(32.0), sigma=0.4, size=n)
    budget_hours = np.round(duration_days * daily_burn).astype(np.int64)
    blended_rate = np.clip(budget_rng.normal(220.0, 25.0, size=n), 150.0, None)
    budget_amount = np.round(budget_hours * blended_rate, 2)

    # Actual end date + right-censoring. A completed project's actual end is its
    # target end plus a right-skewed slip (mostly a few days late, occasionally
    # early). But a completion that lands on/after the (exclusive) window end is
    # unobservable at the snapshot, so we right-censor it: a project drawn
    # `completed` whose candidate completion is `>= end_date` is downgraded to
    # `active` (still running as far as the data can see) and records no
    # actual_end_date / client_satisfaction — exactly as an originally-active
    # project does. `slip` is still drawn for all n on its own child stream; only
    # the interpretation of the already-drawn values changes, so determinism (and
    # every other column) is preserved. `project_members` reads the censored
    # `status`, so a flipped project's roll-off dates reopen accordingly.
    slip = np.round(ctx.rng.child("end_slip").numpy.lognormal(np.log(12.0), 0.7, size=n) - 9.0)
    candidate_end = [t + timedelta(days=int(s)) for t, s in zip(target_end, slip, strict=True)]
    observed_status = [
        "active" if (st == "completed" and ce >= ctx.config.end_date) else st
        for st, ce in zip(status, candidate_end, strict=True)
    ]
    actual_end: list[date | None] = [
        ce if st == "completed" else None
        for ce, st in zip(candidate_end, observed_status, strict=True)
    ]

    # Client satisfaction (completed only): a 1-5 CSAT skewed high. Null while
    # open — including projects downgraded to active by right-censoring above.
    # csat is still drawn for all n on its own child stream (only reinterpreted).
    csat = np.clip(np.round(ctx.rng.child("csat").numpy.normal(4.1, 0.7, size=n)), 1, 5)
    client_satisfaction: list[int | None] = [
        int(c) if st == "completed" else None for c, st in zip(csat, observed_status, strict=True)
    ]

    # Contract-signed (sale-close) date: a right-skewed lead before the project
    # start (median ~60 days, tail to longer sales cycles), floored at the window
    # start so it never predates the dataset. Own child stream; the sales-cycle
    # length is (start_date - contract_signed_date).
    lead_days = ctx.rng.child("signed").numpy.lognormal(np.log(60.0), 0.7, size=n)
    contract_signed_date = [
        max(ctx.config.start_date, s - timedelta(days=round(float(ld))))
        for s, ld in zip(start, lead_days, strict=True)
    ]

    # Engagement manager: the accountable partner/owner for the project, distinct
    # from the on-project `role_on_project = 'lead'`. A senior employee (Supervisor
    # or Manager rung) whose tenure covers the project's start_date; if the senior
    # pool is empty at that date (a small workforce can leave it empty), widen to
    # Lead+, then to any employee employed on that date. Own child stream.
    employees = ctx.table("employees")
    emp_ids = employees["employee_id"].to_list()
    emp_roles = employees["role"].to_list()
    emp_hire = employees["hire_date"].to_list()
    emp_term = employees["termination_date"].to_list()
    mgr_rng = ctx.rng.child("engagement_mgr").numpy

    def _covers(hire: date, term: date | None, day: date) -> bool:
        return hire <= day and (term is None or term > day)

    engagement_manager_id: list[str] = []
    for s in start:
        covered = [
            i
            for i in range(len(emp_ids))
            if _covers(emp_hire[i], emp_term[i], s)  # type: ignore[arg-type]
        ]
        senior = [i for i in covered if emp_roles[i] in _ENGAGEMENT_MANAGER_ROLES]
        pool = senior or [i for i in covered if emp_roles[i] in _ENGAGEMENT_LEAD_PLUS] or covered
        # Ultimate fallback (no one covers this date, effectively impossible with a
        # populated roster): any employee, so the FK always resolves.
        pool = pool or list(range(len(emp_ids)))
        engagement_manager_id.append(emp_ids[int(mgr_rng.choice(pool))])

    return pl.DataFrame(
        {
            "project_id": [f"PRJ-{i:04d}" for i in range(1, n + 1)],
            "name": _project_names(n),
            # Owning cost centre; membership is cross-department (see project_members).
            "department_id": department_id,
            "location_city": location_city,
            "status": observed_status,
            "client_id": client_id,
            "client_name": client_name,
            "industry": industry,
            "billing_type": billing_type,
            "priority": priority,
            "contract_signed_date": pl.Series(contract_signed_date, dtype=pl.Date),
            "engagement_manager_id": engagement_manager_id,
            "start_date": start,
            "target_end_date": target_end,
            "budget_hours": budget_hours,
            "budget_amount": budget_amount,
            "actual_end_date": pl.Series(actual_end, dtype=pl.Date),
            "client_satisfaction": pl.Series(client_satisfaction, dtype=pl.Int8),
        }
    )
