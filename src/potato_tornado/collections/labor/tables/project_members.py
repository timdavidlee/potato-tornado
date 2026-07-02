"""The ``project_members`` table: employees staffed onto projects (many-to-many).

A project pulls members from across the org (not just its owning department, the
way shifts do). Each membership records the member's allocation and whether they
lead the project — the lead is the team's most senior member (highest role rung).
Team composition carries the planted signal: the share of off-site members (based
somewhere other than the project's location) rises for the smaller satellite
offices — see ``scenarios/off-site-staffing-by-location.md``.
"""

from __future__ import annotations

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
    # Seniority rung per employee, so the lead can be the most senior team member.
    role_rung = {role: i for i, role in enumerate(ROLES)}
    emp_rung = dict(zip(all_ids, [role_rung[r] for r in employees["role"].to_list()], strict=True))
    emp_by_loc: dict[str, list[str]] = {}
    for emp_id, loc in zip(all_ids, employees["location_city"].to_list(), strict=True):
        emp_by_loc.setdefault(loc, []).append(emp_id)
    # Off-site pool per location = everyone based elsewhere. Precomputed once
    # (locations are a small fixed set) so the per-project loop stays cheap.
    offsite_by_loc = {
        loc: [e for other, ids in emp_by_loc.items() if other != loc for e in ids]
        for loc in emp_by_loc
    }

    rng = ctx.rng.numpy
    proj_ids = projects["project_id"].to_list()
    proj_locs = projects["location_city"].to_list()
    # Team sizes vary; at least 2 so every project has a lead and a contributor.
    team_sizes = np.clip(ctx.dist.poisson(len(proj_ids), 6.0), 2, None)

    rows_proj: list[str] = []
    rows_emp: list[str] = []
    rows_is_lead: list[bool] = []
    for project_id, loc, size in zip(proj_ids, proj_locs, team_sizes, strict=True):
        local_pool = emp_by_loc.get(loc, [])
        offsite_pool = offsite_by_loc.get(loc, all_ids)
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
            members = rng.choice(offsite_pool, size=1, replace=False).tolist()
        # The lead is the most senior member; ties go to the earliest (local) pick.
        lead_pos = max(range(len(members)), key=lambda i: emp_rung[members[i]])
        rows_proj.extend([project_id] * len(members))
        rows_emp.extend(members)
        rows_is_lead.extend([i == lead_pos for i in range(len(members))])

    n = len(rows_proj)
    allocation = ctx.dist.choice(n, ["25", "50", "75", "100"], [0.15, 0.3, 0.2, 0.35]).astype(int)
    # Negotiated rate the member is billed at on this project = their standard rate
    # times a realization discount (< 1). A flat discount off a dedicated child
    # stream — the depressed-realization-by-billing-type signal is a future scenario.
    realization = np.clip(ctx.rng.child("realization").numpy.normal(0.85, 0.06, size=n), 0.6, 1.0)
    bill_rate = np.round(np.array([emp_bill[e] for e in rows_emp]) * realization, 2)
    return pl.DataFrame(
        {
            "membership_id": [f"PMB-{i:06d}" for i in range(1, n + 1)],
            "project_id": rows_proj,
            "employee_id": rows_emp,
            "role_on_project": ["lead" if is_lead else "contributor" for is_lead in rows_is_lead],
            "allocation_pct": allocation,
            "bill_rate": bill_rate,
        }
    )
