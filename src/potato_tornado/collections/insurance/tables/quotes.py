"""The ``quotes`` table: pre-bind quotes — the sales stage upstream of ``policies``.

Every bound policy started as a quote, and most quotes never convert. Each policy
gets one converting quote (``converted = True``, ``policy_id`` set) priced near its
bound premium; the rest are non-converting shopping quotes (``policy_id`` null). The
overall conversion rate is a flat top-line (~40%) — conversion is drawn independent
of premium and product, so a premium/product-driven funnel would be a scenario, not
a fact planted here. The non-converting quotes bootstrap their (product, premium)
off a random policy so the premium marginal matches the converting side and the
conversion rate stays flat across premium.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Conversion target, quote→bind lead time, and quote-vs-bound premium scatter
# (single-table literals).
_CONVERSION_RATE = 0.40
_LEAD_MIN_DAYS = 1
_LEAD_MAX_DAYS = 30
_CONV_JITTER_SIGMA = 0.05
_NONCONV_JITTER_SIGMA = 0.15


def build_quotes(ctx: GenContext) -> pl.DataFrame:
    policies = ctx.table("policies")
    holder_ids = ctx.table("policyholders")["policyholder_id"].to_list()

    policy_ids = policies["policy_id"].to_list()
    policy_holders = policies["policyholder_id"].to_list()
    policy_products = policies["product"].to_list()
    policy_premium = policies["annual_premium"].to_numpy()
    policy_start = policies["start_date"].to_list()
    n_pol = len(policy_ids)

    # Size the non-converting pool so the overall conversion rate lands near target.
    n_total = round(n_pol / _CONVERSION_RATE)
    n_nonconv = n_total - n_pol

    # Converting quotes: one per policy, priced near the bound premium and quoted a
    # short lead time before the policy starts.
    conv_jitter = ctx.rng.child("quote_conv_premium").numpy.lognormal(
        0.0, _CONV_JITTER_SIGMA, n_pol
    )
    conv_premium = np.round(policy_premium * conv_jitter, 2)
    conv_lead = ctx.rng.child("quote_lead").numpy.integers(
        _LEAD_MIN_DAYS, _LEAD_MAX_DAYS + 1, n_pol
    )
    conv_date = [s - timedelta(days=int(d)) for s, d in zip(policy_start, conv_lead, strict=True)]

    # Non-converting quotes: bootstrap (product, premium) off a random policy so the
    # premium marginal matches the converting side, with an independently-sampled
    # holder and a quote date anywhere in the window.
    src = ctx.rng.child("quote_src").numpy.integers(0, n_pol, n_nonconv)
    nonconv_jitter = ctx.rng.child("quote_noncov_premium").numpy.lognormal(
        0.0, _NONCONV_JITTER_SIGMA, n_nonconv
    )
    nonconv_premium = np.round(policy_premium[src] * nonconv_jitter, 2)
    nonconv_product = [policy_products[i] for i in src]
    holder_idx = ctx.rng.child("quote_holder").numpy.integers(0, len(holder_ids), n_nonconv)
    nonconv_holder = [holder_ids[i] for i in holder_idx]
    nonconv_date = ctx.dist.dates_between(n_nonconv, ctx.config.start_date, ctx.config.end_date)

    return pl.DataFrame(
        {
            "quote_id": [f"QT-{i:07d}" for i in range(1, n_total + 1)],
            "policyholder_id": list(policy_holders) + nonconv_holder,
            "product": list(policy_products) + nonconv_product,
            "quoted_premium": np.concatenate([conv_premium, nonconv_premium]),
            "quote_date": list(conv_date) + list(nonconv_date),
            "converted": [True] * n_pol + [False] * n_nonconv,
            "policy_id": list(policy_ids) + [None] * n_nonconv,
        }
    )
