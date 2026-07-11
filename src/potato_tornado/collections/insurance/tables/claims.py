"""The ``claims`` table: the filings — the frequency half of the model.

Most policies produce **zero** claims; a few produce one or more. Per-policy claim
count is Poisson with a rate that scales by the holder's risk tier and the policy
term, so high-risk policies file far more often. Each claim carries a right-skewed
``reported_amount`` (the severity half) and an adjudication ``status``; only
settled claims get a `claim_payments` row. Each claim is assigned an ``adjuster_id``
uniformly at random (like `broker_id`, the handler carries no built-in signal).
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.insurance.constants import PERILS, RISK_TIERS
from potato_tornado.core.collection import GenContext

# Adjudication mix and severity shape (single-table literals).
_STATUSES = ["approved", "partial", "denied", "open"]
_STATUS_WEIGHTS = [0.62, 0.16, 0.14, 0.08]
_SEVERITY_MEDIAN = 6000.0
_SEVERITY_SIGMA = 1.0
_DAYS_PER_MONTH = 30.4

# Peril frequency mix — skewed, not uniform: water damage / collision are the common
# personal-lines perils, fire the rare one. This is a *marginal* frequency only; peril
# stays independent of product and geography (a deliberate simplification — see the
# rubric). Keyed by name so it can't drift out of order against `PERILS`; drawn off a
# dedicated `peril` child stream.
_PERIL_WEIGHTS = {
    "collision": 0.28,
    "theft": 0.14,
    "weather": 0.20,
    "fire": 0.06,
    "liability": 0.10,
    "water_damage": 0.22,
}
_PERIL_P = np.array([_PERIL_WEIGHTS[p] for p in PERILS])
_PERIL_P = _PERIL_P / _PERIL_P.sum()

# FNOL (first-notice-of-loss) channel the claim came in on — a realism dimension drawn
# independently of peril/severity (no signal planted), off its own child stream so the
# existing peril/status draws stay byte-identical. Single-table literals.
_REPORTED_CHANNELS = ["phone", "app", "broker", "web"]
_REPORTED_CHANNEL_WEIGHTS = [0.40, 0.20, 0.25, 0.15]

# Claim-context flags, each drawn **flat** off its own child stream (no coupling to
# severity, tier, or adjuster — those signals are deferred candidates). Single-table
# literals.
# - `at_fault`: liability posture, meaningful only for auto claims (non-null iff the
#   policy's product is auto, else null); flat 0.55 among auto claims.
# - `catastrophe_flag`: whether the claim belongs to a catastrophe event — the only
#   flag conditioned on an existing column (raised on the `weather` peril), but the
#   *rate*, not severity, varies; severity stays peril-independent (see the rubric).
# - `fraud_flag` / `litigated`: low flat base rates (SIU referral / attorney rep).
_AT_FAULT_P = 0.55
_CAT_WEATHER_P = 0.35
_CAT_BASE_P = 0.03
_FRAUD_P = 0.04
_LITIGATION_P = 0.10


def build_claims(ctx: GenContext) -> pl.DataFrame:
    policies = ctx.table("policies")
    holders = ctx.table("policyholders")
    tier_of = dict(
        zip(
            holders["policyholder_id"].to_list(),
            holders["risk_tier"].to_list(),
            strict=True,
        )
    )
    tier_lambda = {t: lam for t, _mult, lam in RISK_TIERS}

    start_dates = policies["start_date"].to_list()
    term_months = policies["term_months"].to_numpy()
    policy_ids = policies["policy_id"].to_list()
    holder_ids = policies["policyholder_id"].to_list()
    n_pol = len(policy_ids)
    end = ctx.config.end_date

    # Active window per policy: the term, clipped to the run's end (a policy started
    # late is only observed for the days that fall before end_date).
    term_days = np.round(term_months * _DAYS_PER_MONTH).astype(int)
    days_to_end = np.array([(end - s).days for s in start_dates])
    active_span = np.maximum(np.minimum(term_days, days_to_end), 1)

    # Per-policy expected claim count: tier rate x *exposed* years. Scaling by the
    # in-window span (not the full contractual term) keeps the count consistent with
    # where the dates can land, so late-starting policies don't pile a whole term's
    # claims into the clipped tail — no spike at the end_date boundary.
    exposed_years = active_span / (12.0 * _DAYS_PER_MONTH)
    lam = np.array([tier_lambda[tier_of[h]] for h in holder_ids]) * exposed_years
    counts = ctx.rng.child("frequency").numpy.poisson(lam)
    total = int(counts.sum())

    policy_idx = np.repeat(np.arange(n_pol), counts)

    # Claim date: uniform within the policy's active window, clipped to the run window.
    span_per_claim = active_span[policy_idx]
    offset = ctx.rng.child("claim_date").numpy.integers(0, span_per_claim)
    claim_date = [
        start_dates[p] + timedelta(days=int(o)) for p, o in zip(policy_idx, offset, strict=True)
    ]

    reported_amount = np.round(
        ctx.rng.child("severity").numpy.lognormal(np.log(_SEVERITY_MEDIAN), _SEVERITY_SIGMA, total),
        2,
    )

    # Assign a handling adjuster uniformly. A dedicated child stream keeps the peril
    # and status draws (off `ctx.dist`) byte-identical to a run without adjusters.
    adjuster_ids = ctx.table("adjusters")["adjuster_id"].to_list()
    adjuster_idx = ctx.rng.child("adjuster").numpy.integers(0, len(adjuster_ids), total)

    # Peril hoisted to a local (same stream/call, so byte-identical to before) so the
    # catastrophe rate can condition on it below without a second peril draw.
    peril = ctx.rng.child("peril").numpy.choice(
        np.asarray(PERILS, dtype=object), size=total, p=_PERIL_P
    )

    # `at_fault` is non-null only for auto claims. Draw a flat auto liability flag, then
    # null it out on non-auto claims. Own child stream; `product` comes from the policy
    # already read above (no new ordering).
    product_per_claim = policies["product"].to_numpy()[policy_idx]
    auto_at_fault = ctx.rng.child("at_fault").numpy.random(total) < _AT_FAULT_P
    at_fault = [
        bool(auto_at_fault[i]) if product_per_claim[i] == "auto" else None for i in range(total)
    ]

    # Catastrophe / fraud / litigation flags — each flat off its own child stream. Only
    # the catastrophe *rate* conditions on peril (weather ⇒ 0.35, else 0.03); fraud and
    # litigation are constant base rates.
    cat_p = np.where(peril == "weather", _CAT_WEATHER_P, _CAT_BASE_P)
    catastrophe_flag = ctx.rng.child("catastrophe").numpy.random(total) < cat_p
    fraud_flag = ctx.rng.child("fraud").numpy.random(total) < _FRAUD_P
    litigated = ctx.rng.child("litigation").numpy.random(total) < _LITIGATION_P

    return pl.DataFrame(
        {
            "claim_id": [f"CLM-{i:07d}" for i in range(1, total + 1)],
            "policy_id": [policy_ids[p] for p in policy_idx],
            "claim_date": claim_date,
            "peril": peril,
            "reported_amount": reported_amount,
            "status": ctx.dist.choice(total, _STATUSES, _STATUS_WEIGHTS),
            "adjuster_id": [adjuster_ids[i] for i in adjuster_idx],
            "reported_channel": ctx.rng.child("reported_channel").numpy.choice(
                np.asarray(_REPORTED_CHANNELS, dtype=object),
                size=total,
                p=_REPORTED_CHANNEL_WEIGHTS,
            ),
            "at_fault": at_fault,
            "catastrophe_flag": catastrophe_flag,
            "fraud_flag": fraud_flag,
            "litigated": litigated,
        }
    )
