"""The ``subscriptions`` table: one subscription per subscriber, with lifecycle.

Placeholder lifecycle: each subscriber holds exactly one subscription that starts
at signup, sits on a plan tier, and is either still ``active`` or has ``cancelled``
after a right-skewed tenure. Plan changes and multiple subscriptions per account
are the intended future expansion.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.streaming.constants import (
    PLANS,
    SUB_STATUS,
    SUB_STATUS_WEIGHTS,
)
from potato_tornado.core.collection import GenContext

# Plan choice depends on region. The US skews upmarket (Premium is modal there),
# while every other region leans on the blend that keeps Standard the overall
# leader. Keys match PLANS order (Basic, Standard, Premium); each row sums to 1.0.
_PLAN_WEIGHTS_US = [0.18, 0.34, 0.48]
_PLAN_WEIGHTS_OTHER = [0.34, 0.55, 0.11]
_UPMARKET_REGION = "US"


def build_subscriptions(ctx: GenContext) -> pl.DataFrame:
    subs = ctx.table("subscribers")
    ids = subs["subscriber_id"].to_list()
    signup: list[date] = subs["signup_date"].to_list()
    region: list[str] = subs["region"].to_list()
    n = len(ids)

    plan_names = [name for name, _price, _weight in PLANS]
    plan = _sample_plan(ctx, region, plan_names)
    status = ctx.dist.choice(n, SUB_STATUS, SUB_STATUS_WEIGHTS)
    # Tenure in whole months; only cancelled subscriptions have an end date.
    tenure = np.clip(ctx.dist.poisson(n, 6) + 1, 1, 24)
    end_date: list[date | None] = [
        start + timedelta(days=int(months) * 30) if st == "cancelled" else None
        for start, months, st in zip(signup, tenure, status, strict=True)
    ]

    return pl.DataFrame(
        {
            "subscription_id": [f"SBN-{i:06d}" for i in range(1, n + 1)],
            "subscriber_id": ids,
            "plan": plan,
            "start_date": signup,
            "end_date": end_date,
            "status": status,
        }
    )


def _sample_plan(ctx: GenContext, region: list[str], plan_names: list[str]) -> np.ndarray:
    """Per-row plan weighted by region (the US skews toward Premium)."""
    us_cum = np.cumsum(_PLAN_WEIGHTS_US)
    other_cum = np.cumsum(_PLAN_WEIGHTS_OTHER)
    is_us = np.array([r == _UPMARKET_REGION for r in region])
    cum = np.where(is_us[:, None], us_cum[None, :], other_cum[None, :])
    u = ctx.rng.child("plan").numpy.random(len(region))
    idx = (u[:, None] < cum).argmax(axis=1)
    return np.asarray(plan_names, dtype=object)[idx]
