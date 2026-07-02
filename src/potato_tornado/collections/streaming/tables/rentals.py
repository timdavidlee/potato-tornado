"""The ``rentals`` table: one-off premium (PVOD) rentals, licensed to the region.

A rental is a single pay-per-view purchase of a premium-eligible title, billed on
top of whatever subscription the account holds — the collection's second revenue
stream. A subscriber can only rent a title that is **licensed in their region**
(``title_availability``), so every rental resolves to a locally-available title.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.streaming.constants import (
    PREMIUM_RENTAL_PRICE_WEIGHTS,
    PREMIUM_RENTAL_PRICES,
)
from potato_tornado.core.collection import GenContext

# Wide co-prime modulus for the "pick one of a short candidate list" roll.
_ROLL_MAX = 9973


def build_rentals(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(1500)
    subs = ctx.table("subscribers")
    sub_ids = subs["subscriber_id"].to_list()
    sub_regions = subs["region"].to_list()
    num_subs = len(sub_ids)

    titles = ctx.table("titles")
    premium_ids = set(titles.filter(pl.col("is_premium"))["title_id"].to_list())

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

    sub_idx = ctx.dist.integers(n, 0, num_subs - 1)
    title_roll = ctx.dist.integers(n, 0, _ROLL_MAX)
    # Price is a weighted draw over the PVOD ladder (cheap/standard dominate, the
    # $19.99 day-and-date release is rare) — a named child so it doesn't reorder
    # the draws above.
    price_idx = ctx.rng.child("price").numpy.choice(
        len(PREMIUM_RENTAL_PRICES), size=n, p=PREMIUM_RENTAL_PRICE_WEIGHTS
    )
    rented = ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date)

    out_sub: list[str] = []
    out_title: list[str] = []
    out_price: list[float] = []
    for i in range(n):
        idx = int(sub_idx[i])
        region = sub_regions[idx]
        candidates = premium_by_region.get(region) or any_by_region.get(region) or all_premium
        out_sub.append(sub_ids[idx])
        out_title.append(candidates[int(title_roll[i]) % len(candidates)])
        out_price.append(PREMIUM_RENTAL_PRICES[int(price_idx[i])])

    return pl.DataFrame(
        {
            "rental_id": [f"RNT-{i:07d}" for i in range(1, n + 1)],
            "subscriber_id": out_sub,
            "title_id": out_title,
            "rented_date": rented,
            "price": out_price,
        }
    )
