"""The ``project_members`` table: employees staffed onto projects (many-to-many).

A project pulls members from across the org (not just its owning department, the
way shifts do). Each membership records the member's allocation and whether they
lead the project — the lead is the team's most senior member (highest role rung).
Team composition carries the planted signal: the share of off-site members (based
somewhere other than the project's location) rises for the smaller satellite
offices — see ``scenarios/off-site-staffing-by-location.md``.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.labor.constants import REMOTE_RATE_BY_LOCATION, ROLES
from potato_tornado.core.collection import GenContext


def build_project_members(ctx: GenContext) -> pl.DataFrame:
    projects = ctx.table("projects")
    employees = ctx.table("employees")

    all_ids = employees["employee_id"].to_list()
    # Standard list rate per employee, to bill members onto their projects below.
    emp_bill = dict(zip(all_ids, employees["standard_bill_rate"].to_list(), strict=True))
    # Whether each employee is client-billable, so non-billable members carry no
    # project bill rate (null) — there is no client rate for bench/overhead staff.
    emp_is_billable = dict(zip(all_ids, employees["is_billable"].to_list(), strict=True))
    # Seniority rung per employee, so the lead can be the most senior team member.
    role_rung = {role: i for i, role in enumerate(ROLES)}
    emp_rung = dict(zip(all_ids, [role_rung[r] for r in employees["role"].to_list()], strict=True))
    loc_of = dict(zip(all_ids, employees["location_city"].to_list(), strict=True))
    # Employment window per employee, so a project only staffs people whose tenure
    # overlaps its dates, and roll-on/off dates stay inside that tenure.
    emp_hire = dict(zip(all_ids, employees["hire_date"].to_list(), strict=True))
    emp_term = dict(zip(all_ids, employees["termination_date"].to_list(), strict=True))

    rng = ctx.rng.numpy
    proj_ids = projects["project_id"].to_list()
    proj_locs = projects["location_city"].to_list()
    # Per-project schedule + status, to bound each membership's roll-on/off dates.
    proj_start = dict(zip(proj_ids, projects["start_date"].to_list(), strict=True))
    proj_end = dict(zip(proj_ids, projects["target_end_date"].to_list(), strict=True))
    proj_status = dict(zip(proj_ids, projects["status"].to_list(), strict=True))
    # Team sizes vary; at least 2 so every project has a lead and a contributor.
    team_sizes = np.clip(ctx.dist.poisson(len(proj_ids), 6.0), 2, None)

    rows_proj: list[str] = []
    rows_emp: list[str] = []
    rows_is_lead: list[bool] = []
    for project_id, loc, size in zip(proj_ids, proj_locs, team_sizes, strict=True):
        start = proj_start[project_id]
        end = proj_end[project_id]
        # Only staff employees whose tenure overlaps the project: hired before it
        # ends and not terminated before it starts.
        active = [
            e for e in all_ids if emp_hire[e] < end and (emp_term[e] is None or emp_term[e] > start)
        ]
        local_pool = [e for e in active if loc_of[e] == loc]
        offsite_pool = [e for e in active if loc_of[e] != loc]
        # Split the team into off-site vs. local by the location's remote rate,
        # then clamp each half to what its pool can supply.
        want_remote = int(rng.binomial(int(size), REMOTE_RATE_BY_LOCATION[loc]))
        n_remote = min(want_remote, len(offsite_pool))
        n_local = min(int(size) - want_remote, len(local_pool))

        picked_local = (
            rng.choice(local_pool, size=n_local, replace=False).tolist() if n_local > 0 else []
        )
        picked_remote = (
            rng.choice(offsite_pool, size=n_remote, replace=False).tolist() if n_remote > 0 else []
        )
        # Local members first (keeps the off-site split intact regardless of lead).
        members = picked_local + picked_remote
        if not members:
            # No local staff and the remote draw came up empty: guarantee a team
            # of one so every project still has a lead.
            members = rng.choice(active or all_ids, size=1, replace=False).tolist()
        # The lead is the most senior member; ties go to the earliest (local) pick.
        lead_pos = max(range(len(members)), key=lambda i: emp_rung[members[i]])
        rows_proj.extend([project_id] * len(members))
        rows_emp.extend(members)
        rows_is_lead.extend([i == lead_pos for i in range(len(members))])

    n = len(rows_proj)
    allocation = ctx.dist.choice(n, ["25", "50", "75", "100"], [0.15, 0.3, 0.2, 0.35]).astype(int)
    # Negotiated rate the member is billed at on this project = their standard rate
    # times a realization discount (< 1), but only for client-billable members —
    # non-billable (bench / overhead) members carry a null bill rate. A flat discount
    # off a dedicated child stream — the depressed-realization-by-billing-type signal
    # is a future scenario.
    realization = np.clip(ctx.rng.child("realization").numpy.normal(0.85, 0.06, size=n), 0.6, 1.0)
    bill_rate = [
        round(emp_bill[e] * float(r), 2) if emp_is_billable[e] else None
        for e, r in zip(rows_emp, realization, strict=True)
    ]

    # Roll-on / roll-off dates: when each member joined and left the project,
    # bounded to [project.start_date, target_end_date]. Own child stream so the
    # draws above don't shift. Each is a right-skewed offset — most members join
    # near kickoff and stay to the end, with a tail joining late / leaving early.
    # Employment tightens both bounds: a member never rolls on before they were
    # hired, and a member who leaves the firm mid-project (termination ≤ project end)
    # rolls off on their termination date — so rolled_off_date is non-null even on an
    # open project in that case. Otherwise rolled_off_date is null while the project
    # is open (active / on_hold), closing only when it completes (mirrors the
    # project's own actual_end_date). The dates are drawn independently, so they
    # carry no over-allocation signal.
    roll_rng = ctx.rng.child("roll_dates").numpy
    on_frac = np.clip(roll_rng.lognormal(np.log(0.05), 0.9, size=n), 0.0, 0.55)
    off_frac = np.clip(roll_rng.lognormal(np.log(0.04), 0.9, size=n), 0.0, 0.5)
    one_day = timedelta(days=1)
    rolled_on: list[date] = []
    rolled_off: list[date | None] = []
    for project_id, emp_id, onf, offf in zip(rows_proj, rows_emp, on_frac, off_frac, strict=True):
        start = proj_start[project_id]
        end = proj_end[project_id]
        dur = (end - start).days
        hire = emp_hire[emp_id]
        term = emp_term[emp_id]
        # A member who leaves the firm within the project window is gone by `term`;
        # otherwise they are around through project end.
        term_in_window = term if (term is not None and term <= end) else None
        cap = term_in_window if term_in_window is not None else end
        earliest = max(start, hire)  # can't roll on before kickoff or before hire
        on = start + timedelta(days=round(float(onf) * dur))
        on = min(max(on, earliest), cap - one_day)
        rolled_on.append(on)
        if term_in_window is not None:
            rolled_off.append(term_in_window)  # left the firm → rolled off, even if open
        elif proj_status[project_id] == "completed":
            off = end - timedelta(days=round(float(offf) * dur))
            rolled_off.append(max(off, on + one_day))
        else:
            rolled_off.append(None)

    return pl.DataFrame(
        {
            "membership_id": [f"PMB-{i:06d}" for i in range(1, n + 1)],
            "project_id": rows_proj,
            "employee_id": rows_emp,
            "role_on_project": ["lead" if is_lead else "contributor" for is_lead in rows_is_lead],
            "allocation_pct": allocation,
            "rolled_on_date": pl.Series(rolled_on, dtype=pl.Date),
            "rolled_off_date": pl.Series(rolled_off, dtype=pl.Date),
            "bill_rate": pl.Series(bill_rate, dtype=pl.Float64),
        }
    )
