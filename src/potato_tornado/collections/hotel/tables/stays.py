"""The ``stays`` table: realised check-in/out for honoured reservations."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.hotel.constants import (
    CITY_TAX_PER_NIGHT,
    PAYMENT_BY_CHANNEL,
    PAYMENT_METHODS,
    VAT_RATE_BY_COUNTRY,
)
from potato_tornado.core.collection import GenContext

# Realised stay length vs. the booking: most guests stay exactly as booked; a
# minority check out early or extend by a few nights. ``stay_changes`` surfaces the
# non-zero deltas as early_checkout / extension events.
_CHANGE_KINDS = ["none", "early_checkout", "extension"]
_CHANGE_WEIGHTS = [0.78, 0.09, 0.13]
_MAX_EARLY_NIGHTS = 2  # leave up to 2 nights early
_MAX_EXTRA_NIGHTS = 3  # extend up to 3 nights

# Post-stay review score (1-5). Anchored at a satisfied baseline, but an early checkout pulls
# it down sharply (a guest who left early was unhappy) while an extension nudges it up; the
# OTA runs a touch below the loyalty-heavy direct channel. Drawn Normal(mu, sigma), then
# rounded and clipped to [1, 5] -- see scenarios/early-checkouts-score-lower.md.
_REVIEW_BASE = 4.3
_REVIEW_SIGMA = 0.8
_REVIEW_ADJ_BY_CHANGE = {"none": 0.0, "early_checkout": -1.1, "extension": 0.25}
_REVIEW_ADJ_BY_CHANNEL = {"direct": 0.15, "ota": -0.3, "corporate": 0.0, "walk_in": -0.05}


def build_stays(ctx: GenContext) -> pl.DataFrame:
    res = ctx.table("reservations")
    honoured = res.filter(pl.col("status") == "honoured")
    room_rates = _rate_lookup(ctx.table("room_types"))
    props = ctx.table("properties")
    country_by_pid = dict(
        zip(props["property_id"].to_list(), props["country"].to_list(), strict=True)
    )
    city_by_pid = dict(zip(props["property_id"].to_list(), props["city"].to_list(), strict=True))

    n = honoured.height
    prop_ids = honoured["property_id"].to_list()
    room_types = honoured["room_type"].to_list()
    nights = honoured["nights"].to_list()

    change = ctx.dist.choice(n, _CHANGE_KINDS, _CHANGE_WEIGHTS)
    early_cut = ctx.dist.integers(n, 1, _MAX_EARLY_NIGHTS)
    extra = ctx.dist.integers(n, 1, _MAX_EXTRA_NIGHTS)
    night_delta = [
        -int(c) if k == "early_checkout" else int(x) if k == "extension" else 0
        for k, c, x in zip(change, early_cut, extra, strict=True)
    ]
    actual_nights = [max(1, nt + d) for nt, d in zip(nights, night_delta, strict=True)]
    rates = [room_rates.get((p, t), 100.0) for p, t in zip(prop_ids, room_types, strict=True)]
    room_revenue = [round(r * nt, 2) for r, nt in zip(rates, actual_nights, strict=True)]
    # Tax wedge on top of the net room charge: country VAT on room_revenue plus a flat
    # per-room-night city tourist tax. Fully determined by geography + revenue (no RNG), so
    # room_revenue stays the net-of-tax base for ADR / RevPAR and the wedge is a separate line.
    taxes_fees = [
        round(
            rev * VAT_RATE_BY_COUNTRY[country_by_pid[p]] + nt * CITY_TAX_PER_NIGHT[city_by_pid[p]],
            2,
        )
        for p, rev, nt in zip(prop_ids, room_revenue, actual_nights, strict=True)
    ]

    check_in = honoured["check_in_date"].to_list()
    check_out = [ci + timedelta(days=nt) for ci, nt in zip(check_in, actual_nights, strict=True)]
    # Settlement method keyed to the booking channel (corporate → AR), and a post-stay review
    # score keyed to how the stay went — both from their own child streams so they don't shift
    # the change / rate draws above.
    channel = honoured["channel"].to_numpy()
    payment_method = _sample_payment(ctx, channel)
    review_score = _review_scores(ctx, change, channel)

    return pl.DataFrame(
        {
            "stay_id": [f"STY-{i:07d}" for i in range(1, n + 1)],
            "reservation_id": honoured["reservation_id"],
            "property_id": honoured["property_id"],
            "room_type": honoured["room_type"],
            "actual_check_in": check_in,
            "actual_check_out": check_out,
            "actual_nights": actual_nights,
            "nightly_rate": rates,
            "room_revenue": room_revenue,
            "taxes_fees": taxes_fees,
            "payment_method": payment_method,
            "review_score": review_score,
        }
    )


def _review_scores(ctx: GenContext, change: np.ndarray, channel: np.ndarray) -> np.ndarray:
    """Per-stay 1-5 review score, lowered by an early checkout and by the OTA channel."""
    mu = np.array([_REVIEW_BASE + _REVIEW_ADJ_BY_CHANGE[k] for k in change]) + np.array(
        [_REVIEW_ADJ_BY_CHANNEL[c] for c in channel]
    )
    draws = ctx.rng.child("review").numpy.normal(mu, _REVIEW_SIGMA)
    return np.clip(np.rint(draws), 1, 5).astype(int)


def _sample_payment(ctx: GenContext, channel: np.ndarray) -> np.ndarray:
    """Per-row settlement method weighted by booking channel (corporate concentrates in AR)."""
    cum_by_channel = {c: np.cumsum(w) for c, w in PAYMENT_BY_CHANNEL.items()}
    cum = np.array([cum_by_channel[c] for c in channel])  # (n, len(PAYMENT_METHODS))
    u = ctx.rng.child("payment").numpy.random(channel.shape[0])
    idx = (u[:, None] < cum).argmax(axis=1)
    return np.asarray(PAYMENT_METHODS, dtype=object)[idx]


def _rate_lookup(room_types: pl.DataFrame) -> dict[tuple[str, str], float]:
    return {
        (p, t): r
        for p, t, r in zip(
            room_types["property_id"].to_list(),
            room_types["room_type"].to_list(),
            room_types["nightly_rate"].to_list(),
            strict=True,
        )
    }
