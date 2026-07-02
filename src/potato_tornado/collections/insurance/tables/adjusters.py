"""The ``adjusters`` table: the claims-handler dimension.

Every filed claim is assigned to an adjuster who works it to a terminal status, so
this dim exists for per-handler rollups — cycle time, partial-vs-approved rate,
caseload. Assignment in ``claims`` is uniform, so — like ``brokers`` — the adjuster
carries no built-in performance signal; a handler-level outlier would be a scenario,
not a realism fact.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.core.collection import GenContext

# Handling teams and the seniority ladder — single-table literals.
_TEAMS = ["auto", "property", "liability", "catastrophe"]
_TEAM_WEIGHTS = [0.40, 0.30, 0.20, 0.10]
_SENIORITY = ["junior", "senior", "lead"]
_SENIORITY_WEIGHTS = [0.50, 0.35, 0.15]


def build_adjusters(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(40)
    people = ctx.entities.people(n)
    return pl.DataFrame(
        {
            "adjuster_id": [f"ADJ-{i:03d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "team": ctx.dist.choice(n, _TEAMS, _TEAM_WEIGHTS),
            "seniority": ctx.dist.choice(n, _SENIORITY, _SENIORITY_WEIGHTS),
        }
    )
