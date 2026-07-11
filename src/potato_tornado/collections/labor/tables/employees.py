"""The ``employees`` table: the workforce, tied to a home department."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.labor.constants import (
    EMPLOYMENT,
    EMPLOYMENT_WEIGHTS,
    HIRE_SOURCE_WEIGHTS,
    HIRE_SOURCES,
    LOCATION_WEIGHTS,
    LOCATIONS,
    ROLE_WEIGHTS,
    ROLES,
    SKILLS_BY_DEPARTMENT,
    WORK_MODE_WEIGHTS,
    WORK_MODES,
)
from potato_tornado.core.collection import GenContext

# Contracted weekly hours by employment type — the utilization *denominator*.
# Part-timers carry half a full desk; contractors bill a full week. A fixed
# lookup (no jitter), so it consumes no randomness.
_CAPACITY_BY_EMPLOYMENT = {"full_time": 40, "part_time": 20, "contractor": 40}

# Client-facing rate markup over internal cost (`hourly_rate`), laddered by role:
# ~2.6x at the junior rung rising to ~3.0x for a manager. Flat by role only — no
# per-practice compression (that margin-by-practice angle is a future scenario).
_BILL_RATE_MARKUP = {role: 2.6 + 0.1 * i for i, role in enumerate(ROLES)}

# Probability an employee is client-billable, by practice type. Delivery staff are
# almost all billable; enabling (PMO / IT) staff mostly are not. An expected split,
# documented as a realism mix — not a planted scenario.
_BILLABLE_P_BY_PRACTICE = {"delivery": 0.90, "enabling": 0.35}

# Target utilization the employee is held to, by role — juniors carry more billable
# load, partners/managers less (they sell and manage). Only meaningful for billable
# staff; null otherwise.
_TARGET_UTIL_BY_ROLE = {
    "Associate": 80,
    "Senior Associate": 78,
    "Lead": 72,
    "Supervisor": 63,
    "Manager": 55,
}


def build_employees(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(200)
    depts = ctx.table("departments")
    dept_ids = depts["department_id"].to_list()
    dept_rates = dict(zip(dept_ids, depts["base_hourly_rate"].to_list(), strict=True))
    dept_practice = dict(zip(dept_ids, depts["practice_type"].to_list(), strict=True))
    dept_name = dict(zip(dept_ids, depts["name"].to_list(), strict=True))

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

    # Employment type pulled into a variable (same draw position as before) so
    # weekly capacity can key off it; capacity itself is a deterministic lookup.
    employment = ctx.dist.choice(n, EMPLOYMENT, EMPLOYMENT_WEIGHTS)
    capacity = np.array([_CAPACITY_BY_EMPLOYMENT[e] for e in employment], dtype=np.int64)

    # Standard client bill rate = cost x role markup x small jitter. Drawn from a
    # dedicated child stream so it doesn't shift the main-stream draws above.
    hourly = np.round(rates, 2)
    markup = np.array([_BILL_RATE_MARKUP[r] for r in roles])
    bill_jitter = np.clip(ctx.rng.child("bill_rate").numpy.normal(1.0, 0.05, size=n), 0.9, 1.1)
    standard_bill_rate = np.round(hourly * markup * bill_jitter, 2)

    # Billable (delivery consultant) vs. overhead, keyed to the department's practice
    # type. Own child stream so it doesn't shift the main-stream draws above.
    billable_p = np.array([_BILLABLE_P_BY_PRACTICE[dept_practice[d]] for d in dept_of])
    is_billable = ctx.rng.child("billable").numpy.random(n) < billable_p

    # Target utilization laddered by role, with small jitter; only billable staff
    # carry a target (null otherwise).
    util_base = np.array([_TARGET_UTIL_BY_ROLE[r] for r in roles], dtype=float)
    util_jitter = ctx.rng.child("target_util").numpy.normal(0.0, 3.0, size=n)
    target_util = [
        round(u + j) if b else None
        for u, j, b in zip(util_base, util_jitter, is_billable, strict=True)
    ]

    # Primary skill, drawn uniformly from the employee's department skill set. Own
    # child stream drawn after the employee draws above so it doesn't shift them.
    skill_rng = ctx.rng.child("skill").numpy
    primary_skill = [str(skill_rng.choice(SKILLS_BY_DEPARTMENT[dept_name[d]])) for d in dept_of]

    # Work arrangement — flat org-wide mix. Own child stream.
    work_mode = ctx.rng.child("work_mode").numpy.choice(WORK_MODES, size=n, p=WORK_MODE_WEIGHTS)

    # Recruiting channel — flat org-wide mix. Own child stream so it doesn't shift
    # the draws above.
    hire_source = ctx.rng.child("hire_source").numpy.choice(
        np.array(HIRE_SOURCES, dtype=object), size=n, p=HIRE_SOURCE_WEIGHTS
    )

    # Prior experience (years before joining the firm): a Poisson base plus a
    # seniority offset (+2 years per role rung), so senior staff carry more outside
    # experience on average. An external seniority axis, drawn INDEPENDENTLY of pay
    # (own child stream, not tied to hourly_rate). Non-negative by construction.
    exp_rung = {r: i for i, r in enumerate(ROLES)}
    exp_offset = np.array([2 * exp_rung[r] for r in roles], dtype=np.int64)
    prior_experience_years = (
        ctx.rng.child("experience").numpy.poisson(4.0, size=n).astype(np.int64) + exp_offset
    )

    # Termination: ~18% of staff have left the firm at some point. A leaver's date is
    # a tenure offset after hire (≥90 days), kept strictly before `end_date`; active
    # staff have null. Flat attrition — drawn independently of practice, role, and
    # tenure (a high-turnover-slice signal is a future scenario). Own child stream so
    # it doesn't shift the draws above. Staffing respects it: `assignments` and
    # `project_members` never place an employee before hire or after termination.
    attr_rng = ctx.rng.child("attrition").numpy
    end_date = ctx.config.end_date
    left = attr_rng.random(n) < 0.18
    tenure_frac = attr_rng.random(n)
    termination_date: list[date | None] = []
    for hired, has_left, frac in zip(hire, left, tenure_frac, strict=True):
        span = (end_date - hired).days
        if not has_left or span <= 90:
            termination_date.append(None)
            continue
        offset = 90 + round(float(frac) * (span - 1 - 90))
        termination_date.append(hired + timedelta(days=offset))

    # Manager: a more-senior colleague in the same department. Own child stream so
    # it doesn't shift the draws above. Each employee reports to a randomly chosen
    # same-department employee of a strictly higher role rung; whoever sits at the
    # top of their department (nobody above them) has no manager (null).
    employee_ids = [f"EMP-{i:05d}" for i in range(1, n + 1)]
    rung = {r: i for i, r in enumerate(ROLES)}
    emp_rung = [rung[r] for r in roles]
    by_dept: dict[str, list[int]] = {}
    for i, d in enumerate(dept_of):
        by_dept.setdefault(d, []).append(i)
    mgr_rng = ctx.rng.child("manager").numpy
    manager_id: list[str | None] = [None] * n
    for i, d in enumerate(dept_of):
        seniors = [j for j in by_dept[d] if emp_rung[j] > emp_rung[i]]
        if seniors:
            manager_id[i] = employee_ids[int(mgr_rng.choice(seniors))]

    return pl.DataFrame(
        {
            "employee_id": employee_ids,
            "full_name": people["full_name"],
            "email": people["email"],
            "department_id": dept_of,
            "role": roles,
            "employment_type": employment,
            "weekly_capacity_hours": capacity,
            "hire_date": hire,
            "termination_date": pl.Series(termination_date, dtype=pl.Date),
            "hourly_rate": hourly,
            "standard_bill_rate": standard_bill_rate,
            "is_billable": pl.Series(is_billable, dtype=pl.Boolean),
            "target_utilization_pct": pl.Series(target_util, dtype=pl.Int64),
            "primary_skill": primary_skill,
            "work_mode": work_mode,
            "hire_source": hire_source,
            "prior_experience_years": pl.Series(prior_experience_years, dtype=pl.Int64),
            "manager_id": pl.Series(manager_id, dtype=pl.Utf8),
            # Home office. Drawn last so it doesn't shift the draws above.
            "location_city": ctx.dist.choice(n, LOCATIONS, LOCATION_WEIGHTS),
        }
    )
