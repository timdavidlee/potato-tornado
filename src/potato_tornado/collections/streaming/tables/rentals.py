"""The ``rentals`` table: one-off premium (PVOD) rentals, licensed to the region.

A rental is a single pay-per-view purchase of a premium-eligible title, billed on
top of whatever subscription the account holds — the collection's second revenue
stream. A subscriber can only rent a title that is **licensed in their region**
(``title_availability``), so every rental resolves to a locally-available title.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.streaming.constants import (
    PAYMENT_METHOD_WEIGHTS,
    PAYMENT_METHODS,
    PREMIUM_RENTAL_PRICE_WEIGHTS,
    PREMIUM_RENTAL_PRICES,
)
from potato_tornado.core.collection import GenContext

# Wide co-prime modulus for the "pick one of a short candidate list" roll.
_ROLL_MAX = 9973

# Renter concentration (lognormal sigma). Rentals are not spread evenly: each subscriber
# gets a heavy-tailed rental propensity, so a small "whale" minority places most rentals
# while most subscribers never rent — the PVOD stream is Pareto-like, not a flat uniform
# pick. Tuned so the top decile of renters takes ≈ 45% of rentals and the heaviest renters
# buy dozens of titles. See scenarios/rentals-concentrate-in-a-whale-minority.md.
_RENTER_PROPENSITY_SIGMA = 1.7

# Viewer rating (1-5), left by only a minority of rentals. The rare $19.99
# day-and-date tier rates lower than the cheaper catalogue tiers (price-expectation
# gap). See scenarios/premium-rentals-rate-lower.md.
_RATE_PROB = 0.40
_RATING_MEAN_BY_PRICE = {4.99: 4.1, 6.99: 4.0, 19.99: 3.0}
_RATING_SD = 0.8


def build_rentals(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(1500)
    subs = ctx.table("subscribers")
    sub_ids = subs["subscriber_id"].to_list()
    sub_regions = subs["region"].to_list()
    num_subs = len(sub_ids)

    titles = ctx.table("titles")
    premium_ids = set(titles.filter(pl.col("is_premium"))["title_id"].to_list())
    release_by_title: dict[str, date] = dict(
        zip(titles["title_id"].to_list(), titles["release_date"].to_list(), strict=True)
    )

    # region -> titles licensed there (premium subset preferred, any as fallback).
    avail = ctx.table("title_availability")
    premium_by_region: dict[str, list[str]] = {}
    any_by_region: dict[str, list[str]] = {}
    for tid, region in zip(avail["title_id"].to_list(), avail["region"].to_list(), strict=True):
        any_by_region.setdefault(region, []).append(tid)
        if tid in premium_ids:
            premium_by_region.setdefault(region, []).append(tid)
    # Final fallback keeps frame order (deterministic across processes), and if a
    # tiny scale left nothing premium, any title at all.
    premium_frame_ids = titles.filter(pl.col("is_premium"))["title_id"].to_list()
    all_premium = premium_frame_ids or titles["title_id"].to_list()

    # Whale-minority renter draw: each subscriber gets a heavy-tailed lognormal propensity,
    # so rentals concentrate on a small set of subscribers instead of spreading uniformly.
    # Weights and the skewed pick run on a dedicated child stream, so they don't reorder the
    # base-stream title roll below (and every downstream child draw stays identical).
    whale = ctx.rng.child("whale").numpy
    renter_weights = np.exp(whale.normal(0.0, _RENTER_PROPENSITY_SIGMA, num_subs))
    renter_weights /= renter_weights.sum()
    sub_idx = whale.choice(num_subs, size=n, p=renter_weights)
    title_roll = ctx.dist.integers(n, 0, _ROLL_MAX)
    # Price is a weighted draw over the PVOD ladder (cheap/standard dominate, the
    # $19.99 day-and-date release is rare) — a named child so it doesn't reorder
    # the draws above.
    price_idx = ctx.rng.child("price").numpy.choice(
        len(PREMIUM_RENTAL_PRICES), size=n, p=PREMIUM_RENTAL_PRICE_WEIGHTS
    )
    # Rental date is drawn per rental as a fraction of the window *after* the rented
    # title's release — you can't rent a title before it exists. A dedicated child
    # stream so it doesn't reorder the subscriber / title / price draws above.
    rented_frac = ctx.rng.child("rented").numpy.random(n)
    # Tender used for the rental — a dedicated child stream so it doesn't reorder
    # the subscriber / title / price / date draws above.
    payment = ctx.rng.child("payment").numpy.choice(
        np.asarray(PAYMENT_METHODS, dtype=object), size=n, p=PAYMENT_METHOD_WEIGHTS
    )

    start_date = ctx.config.start_date
    end_date = ctx.config.end_date
    out_sub: list[str] = []
    out_title: list[str] = []
    out_price: list[float] = []
    out_rented: list[date] = []
    for i in range(n):
        idx = int(sub_idx[i])
        region = sub_regions[idx]
        candidates = premium_by_region.get(region) or any_by_region.get(region) or all_premium
        tid = candidates[int(title_roll[i]) % len(candidates)]
        out_sub.append(sub_ids[idx])
        out_title.append(tid)
        out_price.append(PREMIUM_RENTAL_PRICES[int(price_idx[i])])
        # Rentable only on/after release, and within the data window.
        earliest = max(release_by_title[tid], start_date)
        span = (end_date - earliest).days
        offset = int(rented_frac[i] * span) if span > 0 else 0
        out_rented.append(earliest + timedelta(days=offset))

    # Only a minority of rentals are rated; the score mean is keyed on the price
    # tier via a dedicated child stream so it doesn't reorder the draws above.
    rating_rng = ctx.rng.child("rating").numpy
    did_rate = rating_rng.random(n) < _RATE_PROB
    rating_mean = np.array([_RATING_MEAN_BY_PRICE[p] for p in out_price])
    scores = np.clip(rating_rng.normal(rating_mean, _RATING_SD), 1, 5).round().astype(int)
    rating: list[int | None] = [
        int(s) if rated else None for s, rated in zip(scores, did_rate, strict=True)
    ]

    return pl.DataFrame(
        {
            "rental_id": [f"RNT-{i:07d}" for i in range(1, n + 1)],
            "subscriber_id": out_sub,
            "title_id": out_title,
            "rented_date": out_rented,
            "price": out_price,
            "payment_method": payment,
            "rating": rating,
        }
    )
