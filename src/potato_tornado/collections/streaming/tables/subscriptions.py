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


def build_subscriptions(ctx: GenContext) -> pl.DataFrame:
    subs = ctx.table("subscribers")
    ids = subs["subscriber_id"].to_list()
    signup: list[date] = subs["signup_date"].to_list()
    n = len(ids)

    plan_names = [name for name, _price, _weight in PLANS]
    plan_weights = [weight for _name, _price, weight in PLANS]
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
            "plan": ctx.dist.choice(n, plan_names, plan_weights),
            "start_date": signup,
            "end_date": end_date,
            "status": status,
        }
    )
