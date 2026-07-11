"""The ``orders`` table: the basket header, one row per order.

Each order belongs to a customer and is placed on/after that customer's
``signup_date`` (clipped into the run window). ``item_count`` is the realized number
of lines in the basket — `order_items` fans out exactly this many rows per order, so
the header count and the line count always agree (an invariant).

A ~0.15 minority of orders carry a ``promo_code`` (nullable) and a matching
``discount_amount`` — a **fixed** dollar amount off from a tier ladder (not a share of
merchandise: the header can't see the basket lines without a build-order cycle). Both
are flat: independent of returns, basket size, and each other's magnitude.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Channel and status mixes, and the basket-size shape (single-table literals).
_CHANNELS = ["web", "mobile", "marketplace"]
_CHANNEL_WEIGHTS = [0.50, 0.40, 0.10]
_STATUSES = ["delivered", "shipped", "cancelled"]
_STATUS_WEIGHTS = [0.90, 0.05, 0.05]
_BASKET_LAMBDA = 1.5
# Tender mix (single-table literal), drawn independently of basket value.
_PAYMENT_METHODS = ["card", "paypal", "gift_card", "bnpl"]
_PAYMENT_WEIGHTS = [0.55, 0.22, 0.08, 0.15]
# Promo penetration + the promo-code catalog and the fixed discount-depth ladder
# (single-table literals). ~0.15 of orders carry a code; the discount is a fixed
# dollar tier drawn independently (not merchandise-proportional — the header can't see
# basket lines here), so it carries no signal.
_PROMO_SHARE = 0.15
_PROMO_CODES = ["WELCOME10", "SAVE15", "SPRING20", "FREESHIP", "LOYALTY25"]
_DISCOUNT_TIERS = [5.0, 10.0, 15.0, 20.0, 25.0]
# Multiplicative order-volume weight by calendar month: a repeating within-year
# retail cycle — a Q4 holiday peak (Nov/Dec) and a post-holiday winter trough
# (Feb), ~1.9x peak-to-trough. Expected seasonality, not a subset signal.
_MONTH_SEASONALITY = {
    1: 0.85, 2: 0.80, 3: 0.90, 4: 0.90, 5: 0.95, 6: 0.95,
    7: 0.95, 8: 1.05, 9: 1.00, 10: 1.10, 11: 1.40, 12: 1.55,
}  # fmt: skip


def build_orders(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(12000)
    customers = ctx.table("customers")
    signup_of = dict(
        zip(customers["customer_id"].to_list(), customers["signup_date"].to_list(), strict=True)
    )

    customer_id = ctx.dist.choice(n, customers["customer_id"].to_list())

    start = ctx.config.start_date
    end = ctx.config.end_date
    total_span = (end - start).days
    # Seasonal order dates: sample each day in [max(start, signup), end) in
    # proportion to its month's seasonality weight (inverse-CDF over the window's
    # per-day cumulative weight). Never before the window and never before the
    # customer signed up, but with a repeating Q4 peak rather than a flat spread.
    day_weight = np.array(
        [_MONTH_SEASONALITY[(start + timedelta(days=d)).month] for d in range(total_span)]
    )
    cum = np.concatenate([[0.0], np.cumsum(day_weight)])  # length total_span + 1
    lo_idx = np.clip(
        np.array([(max(start, signup_of[c]) - start).days for c in customer_id]),
        0,
        total_span - 1,
    )
    target = cum[lo_idx] + ctx.rng.child("order_date").numpy.random(n) * (
        cum[total_span] - cum[lo_idx]
    )
    day_idx = np.clip(np.searchsorted(cum, target, side="right") - 1, lo_idx, total_span - 1)
    order_date = [start + timedelta(days=int(d)) for d in day_idx]

    item_count = 1 + ctx.rng.child("basket").numpy.poisson(_BASKET_LAMBDA, n)

    # Promo code + discount from independent child streams (they don't shift the draws
    # above). A ~0.15 minority carry a code; the discount is a fixed dollar tier, drawn
    # independently of the code, of returns, and of basket size. Non-promo orders get a
    # null code and 0.0 discount, so `discount_amount > 0` iff `promo_code` is not null.
    promo = ctx.rng.child("promo").numpy
    discount = ctx.rng.child("discount").numpy
    is_promo = promo.random(n) < _PROMO_SHARE
    code_idx = promo.integers(0, len(_PROMO_CODES), n)
    tier_idx = discount.integers(0, len(_DISCOUNT_TIERS), n)
    promo_code = [_PROMO_CODES[i] if p else None for p, i in zip(is_promo, code_idx, strict=True)]
    discount_tiers = np.array(_DISCOUNT_TIERS)
    discount_amount = np.where(is_promo, discount_tiers[tier_idx], 0.0)

    return pl.DataFrame(
        {
            "order_id": [f"ORD-{i:07d}" for i in range(1, n + 1)],
            "customer_id": customer_id,
            "order_date": order_date,
            "channel": ctx.dist.choice(n, _CHANNELS, _CHANNEL_WEIGHTS),
            "status": ctx.dist.choice(n, _STATUSES, _STATUS_WEIGHTS),
            "payment_method": ctx.rng.child("payment").numpy.choice(
                np.array(_PAYMENT_METHODS, dtype=object), size=n, p=_PAYMENT_WEIGHTS
            ),
            "item_count": item_count,
            "promo_code": promo_code,
            "discount_amount": discount_amount,
        }
    )
