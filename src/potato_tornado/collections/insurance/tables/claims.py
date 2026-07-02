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

# FNOL (first-notice-of-loss) channel the claim came in on — a realism dimension drawn
# independently of peril/severity (no signal planted), off its own child stream so the
# existing peril/status draws stay byte-identical. Single-table literals.
_REPORTED_CHANNELS = ["phone", "app", "broker", "web"]
_REPORTED_CHANNEL_WEIGHTS = [0.40, 0.20, 0.25, 0.15]


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

    return pl.DataFrame(
        {
            "claim_id": [f"CLM-{i:07d}" for i in range(1, total + 1)],
            "policy_id": [policy_ids[p] for p in policy_idx],
            "claim_date": claim_date,
            "peril": ctx.dist.choice(total, PERILS),
            "reported_amount": reported_amount,
            "status": ctx.dist.choice(total, _STATUSES, _STATUS_WEIGHTS),
            "adjuster_id": [adjuster_ids[i] for i in adjuster_idx],
            "reported_channel": ctx.rng.child("reported_channel").numpy.choice(
                np.asarray(_REPORTED_CHANNELS, dtype=object),
                size=total,
                p=_REPORTED_CHANNEL_WEIGHTS,
            ),
        }
    )
