"""The ``claim_payments`` table: the payout — the actual, one row per settled claim.

A payment row exists **iff** the claim is ``approved`` or ``partial`` (denied and
open claims get none), so recovering total paid means left-joining claims to
payments and treating the missing side as \\$0. The payout is bounded by the
policy: ``min(reported, coverage_limit) - deductible``, floored at 0. A ``partial``
pays a fraction of that. This is the numerator of the loss ratio.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Partial claims pay this fraction of the approved-equivalent payout; settlement
# lands a short delay after the claim (single-table literals).
_PARTIAL_LOW = 0.30
_PARTIAL_HIGH = 0.80
_SETTLE_MIN_DAYS = 5
_SETTLE_MAX_DAYS = 45


def build_claim_payments(ctx: GenContext) -> pl.DataFrame:
    claims = ctx.table("claims")
    policies = ctx.table("policies")

    settled = claims.filter(pl.col("status").is_in(["approved", "partial"])).join(
        policies.select("policy_id", "coverage_limit", "deductible"), on="policy_id", how="left"
    )
    n = settled.height

    reported = settled["reported_amount"].to_numpy()
    coverage = settled["coverage_limit"].to_numpy()
    deductible = settled["deductible"].to_numpy()
    is_partial = (settled["status"] == "partial").to_numpy()

    approved_equiv = np.clip(np.minimum(reported, coverage) - deductible, 0.0, None)
    partial_factor = ctx.rng.child("partial").numpy.uniform(_PARTIAL_LOW, _PARTIAL_HIGH, n)
    paid_amount = np.round(np.where(is_partial, approved_equiv * partial_factor, approved_equiv), 2)

    claim_dates = settled["claim_date"].to_list()
    delay = ctx.rng.child("settle").numpy.integers(_SETTLE_MIN_DAYS, _SETTLE_MAX_DAYS + 1, n)
    paid_date = [d + timedelta(days=int(x)) for d, x in zip(claim_dates, delay, strict=True)]

    return pl.DataFrame(
        {
            "payment_id": [f"PAY-{i:07d}" for i in range(1, n + 1)],
            "claim_id": settled["claim_id"],
            "paid_amount": paid_amount,
            "paid_date": paid_date,
        }
    )
