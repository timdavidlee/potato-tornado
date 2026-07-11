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

# How the payout was disbursed — a flat operational mix, no per-adjuster or per-amount
# coupling. Own child stream. Single-table literals.
_SETTLEMENT_METHODS = ["check", "ach", "card"]
_SETTLEMENT_METHOD_WEIGHTS = [0.35, 0.45, 0.20]

# Subrogation: the insurer recovering part of a payout from an at-fault third party.
# Plausible only on **not-at-fault** claims (the other side is liable), so occurrence is
# gated on `at_fault is False`; at-fault and non-auto (null `at_fault`) claims are not
# eligible and get a null recovery, an eligible-but-unrecovered claim gets 0.0. The
# recovered amount is a fraction of `paid_amount`, so it never exceeds the payout.
# Two own child streams (occurrence + fraction). Single-table literals.
_SUBRO_P = 0.25
_SUBRO_FRACTION_LOW = 0.20
_SUBRO_FRACTION_HIGH = 0.60


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

    # Settlement detail: `settlement_days` is derived (= the delay, i.e. paid_date minus
    # claim_date); `settlement_method` is a flat operational mix off its own stream;
    # `adjuster_id` carries the handling adjuster over from the settled claim (a derived
    # FK, no draw), so payments can roll up by adjuster.
    settlement_method = ctx.rng.child("settlement_method").numpy.choice(
        np.asarray(_SETTLEMENT_METHODS, dtype=object), size=n, p=_SETTLEMENT_METHOD_WEIGHTS
    )

    # Eligible for subrogation iff the claim is explicitly not-at-fault (auto claims with
    # `at_fault is False`); at-fault (True) and non-auto (null) claims are not eligible.
    # `fill_null(True)` maps both True and null to "not eligible", so `~` leaves only the
    # explicit False rows.
    eligible = (~settled["at_fault"].fill_null(True)).to_numpy()
    recovered = (ctx.rng.child("subrogation").numpy.random(n) < _SUBRO_P) & eligible
    fraction = ctx.rng.child("subrogation_amount").numpy.uniform(
        _SUBRO_FRACTION_LOW, _SUBRO_FRACTION_HIGH, n
    )
    recovery_positive = np.round(paid_amount * fraction, 2)
    subrogation_recovery_amount = [
        float(recovery_positive[i]) if recovered[i] else (0.0 if eligible[i] else None)
        for i in range(n)
    ]

    return pl.DataFrame(
        {
            "payment_id": [f"PAY-{i:07d}" for i in range(1, n + 1)],
            "claim_id": settled["claim_id"],
            "adjuster_id": settled["adjuster_id"],
            "paid_amount": paid_amount,
            "paid_date": paid_date,
            "settlement_days": delay,
            "settlement_method": settlement_method,
            "subrogation_recovery_amount": subrogation_recovery_amount,
        }
    )
