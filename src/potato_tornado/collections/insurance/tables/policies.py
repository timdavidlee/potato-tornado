"""The ``policies`` table: one row per policy sold — the premium side of the book.

Each policy ties a policyholder to a broker and a product, and earns an
``annual_premium`` driven by the product's base premium and the holder's risk tier
(higher tiers pay more). Coverage and deductible bound any future payout. This is
the denominator of the loss ratio; `claims` supplies the numerator.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.insurance.constants import PRODUCTS, RISK_TIERS
from potato_tornado.core.collection import GenContext

# Deductible ladder and per-policy coverage steps (single-table literals).
_DEDUCTIBLES = [250.0, 500.0, 1000.0]
_DEDUCTIBLE_WEIGHTS = [0.30, 0.45, 0.25]
_COVERAGE_STEPS = [0.5, 1.0, 2.0]
_COVERAGE_WEIGHTS = [0.30, 0.50, 0.20]
_TERM_MONTHS = [6, 12]
_TERM_WEIGHTS = [0.30, 0.70]
_STATUSES = ["active", "lapsed", "cancelled"]
_STATUS_WEIGHTS = [0.82, 0.12, 0.06]
_PREMIUM_SIGMA = 0.40


def build_policies(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(5000)
    holders = ctx.table("policyholders")
    broker_ids = ctx.table("brokers")["broker_id"].to_list()

    holder_ids = holders["policyholder_id"].to_list()
    tier_of = dict(zip(holder_ids, holders["risk_tier"].to_list(), strict=True))
    tier_mult = {t: mult for t, mult, _lam in RISK_TIERS}

    product_names = [p for p, *_ in PRODUCTS]
    product_weights = [w for *_, w in PRODUCTS]
    premium_median_of = {p: med for p, med, _cov, _w in PRODUCTS}
    coverage_base_of = {p: cov for p, _med, cov, _w in PRODUCTS}

    policyholder_id = ctx.dist.choice(n, holder_ids)
    product = ctx.dist.choice(n, product_names, product_weights)

    # Premium: product base x tier multiplier as the lognormal median, so tier and
    # product both shift the whole distribution while keeping a right skew.
    median = np.array(
        [
            premium_median_of[p] * tier_mult[tier_of[h]]
            for p, h in zip(product, policyholder_id, strict=True)
        ]
    )
    annual_premium = np.round(
        ctx.rng.child("premium").numpy.lognormal(np.log(median), _PREMIUM_SIGMA), 2
    )

    coverage_step = ctx.dist.choice(n, [str(s) for s in _COVERAGE_STEPS], _COVERAGE_WEIGHTS).astype(
        float
    )
    coverage_limit = np.array([coverage_base_of[p] for p in product]) * coverage_step

    return pl.DataFrame(
        {
            "policy_id": [f"POL-{i:07d}" for i in range(1, n + 1)],
            "policyholder_id": policyholder_id,
            "broker_id": ctx.dist.choice(n, broker_ids),
            "product": product,
            "start_date": ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date),
            "term_months": ctx.dist.choice(n, [str(t) for t in _TERM_MONTHS], _TERM_WEIGHTS).astype(
                int
            ),
            "annual_premium": annual_premium,
            "coverage_limit": np.round(coverage_limit, 2),
            "deductible": ctx.dist.choice(
                n, [str(d) for d in _DEDUCTIBLES], _DEDUCTIBLE_WEIGHTS
            ).astype(float),
            "status": ctx.dist.choice(n, _STATUSES, _STATUS_WEIGHTS),
        }
    )
