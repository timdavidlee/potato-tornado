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

# Billing cadence, distribution channel, and auto-renew posture — realism dimensions
# drawn independently of premium/tier (no signal planted), each off its own child
# stream so the existing premium/date/status draws stay byte-identical. `channel` is a
# bought-vs-sold cut alongside `broker_id` (populated on every policy for join practice,
# so `channel = direct` does not imply a null broker). Single-table literals.
_PAYMENT_FREQUENCIES = ["monthly", "quarterly", "annual"]
_PAYMENT_FREQUENCY_WEIGHTS = [0.55, 0.15, 0.30]
_CHANNELS = ["broker", "direct", "aggregator"]
_CHANNEL_WEIGHTS = [0.50, 0.30, 0.20]
_AUTO_RENEW_P = 0.70

# How many prior terms this policy has run — an **abstract** lifecycle marker, mode 0
# (new business), right-skewed via `geometric(p) - 1`. Deliberately **decoupled** from
# `start_date`: the cold-start book has no backdated terms, so this is a book-mix
# dimension (new-vs-renewal split) rather than a real prior-term history — see the
# cold-start note in realism-guidance.md. Own child stream, single-table literal.
_RENEWAL_P = 0.45

# Small underwriting nudges: premium rises with the chosen coverage step and falls as
# the deductible rises (the insured retains more risk). Both are centred on their
# weighted mean so the per-tier premium medians are unchanged — the effect is a weak
# correlation that lives inside the lognormal scatter, not a discoverable subset gap.
_COVERAGE_PREMIUM_FACTOR = {0.5: 0.90, 1.0: 1.00, 2.0: 1.15}
_DEDUCTIBLE_PREMIUM_FACTOR = {250.0: 1.06, 500.0: 1.00, 1000.0: 0.92}


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
    coverage_step = ctx.dist.choice(n, [str(s) for s in _COVERAGE_STEPS], _COVERAGE_WEIGHTS).astype(
        float
    )
    deductible = ctx.dist.choice(n, [str(d) for d in _DEDUCTIBLES], _DEDUCTIBLE_WEIGHTS).astype(
        float
    )

    # Premium: product base x tier multiplier as the lognormal median, so tier and
    # product both shift the whole distribution while keeping a right skew; the policy's
    # own coverage step (up) and deductible (down) then nudge that median so premium
    # co-moves with what it insures.
    cov_factor = np.array([_COVERAGE_PREMIUM_FACTOR[s] for s in coverage_step])
    ded_factor = np.array([_DEDUCTIBLE_PREMIUM_FACTOR[d] for d in deductible])
    median = (
        np.array(
            [
                premium_median_of[p] * tier_mult[tier_of[h]]
                for p, h in zip(product, policyholder_id, strict=True)
            ]
        )
        * cov_factor
        * ded_factor
    )
    annual_premium = np.round(
        ctx.rng.child("premium").numpy.lognormal(np.log(median), _PREMIUM_SIGMA), 2
    )

    coverage_limit = np.array([coverage_base_of[p] for p in product]) * coverage_step

    # Abstract renewal marker, decoupled from start_date (see _RENEWAL_P). Own child
    # stream so premium/date/status draws stay byte-identical.
    renewal_count = ctx.rng.child("renewal_count").numpy.geometric(_RENEWAL_P, size=n) - 1

    # Bundled: derivable, no draw — true when the holder appears on ≥2 policies rows
    # (holders average ~1.75 policies, so the multi-policy structure already exists).
    _uniq, inverse, holder_counts = np.unique(
        policyholder_id, return_inverse=True, return_counts=True
    )
    bundled = holder_counts[inverse] >= 2

    return pl.DataFrame(
        {
            "policy_id": [f"POL-{i:07d}" for i in range(1, n + 1)],
            "policyholder_id": policyholder_id,
            "broker_id": ctx.dist.choice(n, broker_ids),
            "channel": ctx.rng.child("channel").numpy.choice(
                np.asarray(_CHANNELS, dtype=object), size=n, p=_CHANNEL_WEIGHTS
            ),
            "product": product,
            "start_date": ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date),
            "term_months": ctx.dist.choice(n, [str(t) for t in _TERM_MONTHS], _TERM_WEIGHTS).astype(
                int
            ),
            "payment_frequency": ctx.rng.child("payment_frequency").numpy.choice(
                np.asarray(_PAYMENT_FREQUENCIES, dtype=object),
                size=n,
                p=_PAYMENT_FREQUENCY_WEIGHTS,
            ),
            "annual_premium": annual_premium,
            "coverage_limit": np.round(coverage_limit, 2),
            "deductible": deductible,
            "status": ctx.dist.choice(n, _STATUSES, _STATUS_WEIGHTS),
            "bundled": bundled,
            "auto_renew": ctx.rng.child("auto_renew").numpy.random(size=n) < _AUTO_RENEW_P,
            "renewal_count": renewal_count,
        }
    )
