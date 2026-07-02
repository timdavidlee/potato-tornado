"""The ``policyholders`` table: the insured-party dimension.

Each holder carries a ``risk_tier`` (preferred / standard / high_risk) that drives
both the premium they pay (via `policies`) and how often they claim (via `claims`)
— the covariate behind the loss-ratio signal.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.insurance.constants import RISK_TIER_WEIGHTS, RISK_TIERS
from potato_tornado.core.collection import GenContext


def build_policyholders(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(4000)
    people = ctx.entities.people(n)
    tiers = [t for t, *_ in RISK_TIERS]
    return pl.DataFrame(
        {
            "policyholder_id": [f"PH-{i:06d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "city": ctx.entities.cities(n),
            "risk_tier": ctx.dist.choice(n, tiers, RISK_TIER_WEIGHTS),
        }
    )
