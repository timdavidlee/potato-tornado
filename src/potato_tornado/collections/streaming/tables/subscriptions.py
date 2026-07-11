"""The ``subscriptions`` table: one subscription per subscriber, with lifecycle.

Each subscriber holds exactly one subscription that starts at signup, sits on a
plan tier, is billed monthly or annually, and is either still ``active`` or has
``cancelled`` after a right-skewed tenure — with cancellations right-censored at
the snapshot, so a churn dated on/after the window end reads ``active`` with a
null ``end_date`` (its churn is in the unobservable future). Churn is not flat: the subscriber's
acquisition channel and billing cadence both shift how likely they are to cancel
and how long they last — paid-acquired and monthly subscribers churn faster,
organic and annual ones stick. When a subscriber cancels, the stated reason skews
by segment (narrow-catalogue regions cite content, the entry tier cites price).
Plan changes and multiple subscriptions per account are the intended future
expansion.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.streaming.constants import (
    ANNUAL_MRR_FACTOR,
    BILLING_CYCLE_WEIGHTS,
    BILLING_CYCLES,
    PLANS,
)
from potato_tornado.core.collection import GenContext

# Plan choice depends on region. The US skews upmarket (Premium is modal there),
# while every other region leans on the blend that keeps Standard the overall
# leader. Keys match PLANS order (Basic, Standard, Premium); each row sums to 1.0.
_PLAN_WEIGHTS_US = [0.18, 0.34, 0.48]
_PLAN_WEIGHTS_OTHER = [0.34, 0.55, 0.11]
_UPMARKET_REGION = "US"

# Churn model. Per-subscriber cancel probability is a base rate scaled by the
# acquisition channel and the billing cadence; tenure (months) is scaled the same
# way in the opposite direction. Multipliers are centred so the raw churn share is
# ~0.21; after right-censoring at the window end (below) the observed cancelled
# share is ~0.185. See scenarios/paid-channels-churn-faster.md and
# scenarios/annual-plans-retain-better.md.
_BASE_CANCEL_RATE = 0.20
_CHANNEL_CANCEL_MULT = {
    "organic": 0.65,
    "referral": 0.65,
    "partner": 0.90,
    "paid_search": 1.65,
    "social": 1.80,
}
_BILLING_CANCEL_MULT = {"monthly": 1.15, "annual": 0.35}
_CHANNEL_TENURE_MULT = {
    "organic": 1.15,
    "referral": 1.15,
    "partner": 1.00,
    "paid_search": 0.70,
    "social": 0.65,
}
_BILLING_TENURE_MULT = {"monthly": 0.90, "annual": 1.80}
_BASE_TENURE_LAMBDA = 6.0

# Stated cancellation reason (only for cancelled rows). Base mix, then boosted per
# row: narrow-catalogue regions cite "content" far more, and the entry Basic tier
# cites "price" far more. Order: price, content, technical, competitor, other.
_CANCEL_REASONS = ["price", "content", "technical", "competitor", "other"]
_BASE_REASON_WEIGHTS = [0.28, 0.22, 0.20, 0.15, 0.15]
_NARROW_CATALOG_REGIONS = {"JP", "IN"}
_CONTENT_BOOST = 2.6
_PRICE_BOOST = 2.2


def build_subscriptions(ctx: GenContext) -> pl.DataFrame:
    subs = ctx.table("subscribers")
    ids = subs["subscriber_id"].to_list()
    signup: list[date] = subs["signup_date"].to_list()
    region: list[str] = subs["region"].to_list()
    channel: list[str] = subs["acquisition_channel"].to_list()
    n = len(ids)

    plan_names = [name for name, *_ in PLANS]
    plan = _sample_plan(ctx, region, plan_names)
    billing_cycle = ctx.rng.child("billing").numpy.choice(
        np.asarray(BILLING_CYCLES, dtype=object), size=n, p=BILLING_CYCLE_WEIGHTS
    )

    # Cancel probability and tenure both keyed on channel + billing cadence.
    cancel_prob = np.clip(
        _BASE_CANCEL_RATE
        * np.array([_CHANNEL_CANCEL_MULT[c] for c in channel])
        * np.array([_BILLING_CANCEL_MULT[b] for b in billing_cycle]),
        0.0,
        0.95,
    )
    is_cancelled = ctx.rng.child("status").numpy.random(n) < cancel_prob
    lam = (
        _BASE_TENURE_LAMBDA
        * np.array([_CHANNEL_TENURE_MULT[c] for c in channel])
        * np.array([_BILLING_TENURE_MULT[b] for b in billing_cycle])
    )
    tenure = np.clip(ctx.rng.child("tenure").numpy.poisson(lam) + 1, 1, 24)

    # Right-censor the lifecycle at the snapshot. Each subscription's churn date is
    # derived from its (already-drawn) tenure, but a churn is only *observed* if it
    # lands before the window end: a cancellation whose churn date falls on/after
    # `ctx.config.end_date` is unobservable at the snapshot, so the row reads 'active'
    # with a null end_date (right-censored). This is a pure re-derivation off the
    # existing is_cancelled / tenure draws — no new RNG, no reordering — so mrr and
    # every other column stay byte-identical; only the censored rows flip. The same
    # `observed_cancel` mask feeds cancel_reason, so a censored row's reason is nulled
    # too (and _sample_cancel_reasons still draws a full-length u, keeping the stream
    # identical). Mirrors how labor/tables/projects.py reads ctx.config.end_date.
    churn_date = [
        start + timedelta(days=int(months) * 30)
        for start, months in zip(signup, tenure, strict=True)
    ]
    observed_cancel = is_cancelled & np.array([churn < ctx.config.end_date for churn in churn_date])
    status = np.where(observed_cancel, "cancelled", "active")
    end_date: list[date | None] = [
        churn if observed else None
        for churn, observed in zip(churn_date, observed_cancel, strict=True)
    ]
    cancel_reason = _sample_cancel_reasons(ctx, observed_cancel, region, plan)

    # Monthly recurring revenue: pure derivation off the plan price and cadence (no
    # RNG). Monthly subscriptions book the list price; annual ones book the "2 months
    # free" monthly-equivalent (annual_price / 12 = monthly_price * 10 / 12).
    price_by_plan = {name: price for name, price, *_ in PLANS}
    base = np.array([price_by_plan[p] for p in plan], dtype=float)
    factor = np.where(billing_cycle == "annual", ANNUAL_MRR_FACTOR, 1.0)
    mrr = np.round(base * factor, 2)

    return pl.DataFrame(
        {
            "subscription_id": [f"SBN-{i:06d}" for i in range(1, n + 1)],
            "subscriber_id": ids,
            "plan": plan,
            "billing_cycle": billing_cycle,
            "start_date": signup,
            "end_date": end_date,
            "status": status,
            "cancel_reason": cancel_reason,
            "mrr": mrr,
        }
    )


def _sample_cancel_reasons(
    ctx: GenContext,
    cancelled_mask: np.ndarray,
    region: list[str],
    plan: np.ndarray,
) -> list[str | None]:
    """Per-row stated cancel reason; ``None`` where ``cancelled_mask`` is false.

    ``cancelled_mask`` is the *observed* cancellation mask (right-censored), so a
    subscription whose churn falls past the window reads active here and gets no
    reason. The base reason mix is reweighted per cancelled row — ``content`` is
    boosted in narrow-catalogue regions and ``price`` on the Basic tier — then a
    reason is drawn by inverse-CDF against a per-row uniform. ``u`` is drawn at full
    length before the branch, so passing the observed (vs. raw) mask consumes the
    identical RNG stream and only nulls the censored rows' reason.
    """
    u = ctx.rng.child("cancel_reason").numpy.random(len(cancelled_mask))
    base = np.array(_BASE_REASON_WEIGHTS)
    reasons: list[str | None] = []
    for i, cancelled in enumerate(cancelled_mask):
        if not cancelled:
            reasons.append(None)
            continue
        weights = base.copy()
        if region[i] in _NARROW_CATALOG_REGIONS:
            weights[1] *= _CONTENT_BOOST
        if plan[i] == "Basic":
            weights[0] *= _PRICE_BOOST
        cum = np.cumsum(weights / weights.sum())
        idx = min(int(np.searchsorted(cum, u[i], side="right")), len(_CANCEL_REASONS) - 1)
        reasons.append(_CANCEL_REASONS[idx])
    return reasons


def _sample_plan(ctx: GenContext, region: list[str], plan_names: list[str]) -> np.ndarray:
    """Per-row plan weighted by region (the US skews toward Premium)."""
    us_cum = np.cumsum(_PLAN_WEIGHTS_US)
    other_cum = np.cumsum(_PLAN_WEIGHTS_OTHER)
    is_us = np.array([r == _UPMARKET_REGION for r in region])
    cum = np.where(is_us[:, None], us_cum[None, :], other_cum[None, :])
    u = ctx.rng.child("plan").numpy.random(len(region))
    idx = (u[:, None] < cum).argmax(axis=1)
    return np.asarray(plan_names, dtype=object)[idx]
