"""The ``reservations`` table: bookings with a lifecycle status."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.hotel.constants import (
    CHANNELS,
    RES_STATUS,
    RES_STATUS_WEIGHTS,
    ROOM_TYPES,
)
from potato_tornado.core.collection import GenContext

# Booking channel depends on room class. Guests booking the upper tiers skew to
# direct (loyalty / concierge), the mass-market tiers skew to the OTA — so OTA
# still leads overall, but direct is the modal channel for the top of the ladder.
# Keys match CHANNELS; each row sums to 1.0.
_CHANNEL_WEIGHTS_LOWER = {"direct": 0.28, "ota": 0.50, "corporate": 0.16, "walk_in": 0.06}
_CHANNEL_WEIGHTS_UPPER = {"direct": 0.55, "ota": 0.22, "corporate": 0.18, "walk_in": 0.05}
_UPPER_TIERS = ("Suite", "Penthouse")


def build_reservations(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(3000)
    props = ctx.table("properties")["property_id"].to_list()
    type_names = [t[0] for t in ROOM_TYPES]
    type_weights = [t[2] for t in ROOM_TYPES]

    room_type = ctx.dist.choice(n, type_names, type_weights)
    channel = _sample_channel(ctx, room_type)

    booked = ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date)
    lead_days = np.clip(ctx.dist.lognormal(n, median=14, sigma=0.9), 0, 240).astype(int)
    nights = np.clip(ctx.dist.poisson(n, 2.2) + 1, 1, 21)
    check_in = np.array(
        [b + timedelta(days=int(lead)) for b, lead in zip(booked, lead_days, strict=True)],
        dtype=object,
    )
    check_out = np.array(
        [ci + timedelta(days=int(nt)) for ci, nt in zip(check_in, nights, strict=True)],
        dtype=object,
    )

    return pl.DataFrame(
        {
            "reservation_id": [f"RES-{i:07d}" for i in range(1, n + 1)],
            "property_id": ctx.dist.choice(n, props),
            "guest_name": ctx.entities.people(n)["full_name"],
            "channel": channel,
            "room_type": room_type,
            "booked_date": booked,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "party_size": np.clip(ctx.dist.poisson(n, 1.3) + 1, 1, 6),
            "nights": nights,
            "status": ctx.dist.choice(n, RES_STATUS, RES_STATUS_WEIGHTS),
        }
    )


def _sample_channel(ctx: GenContext, room_type: np.ndarray) -> np.ndarray:
    """Per-row booking channel weighted by room class (upper tiers skew direct)."""
    upper_cum = np.cumsum([_CHANNEL_WEIGHTS_UPPER[c] for c in CHANNELS])
    lower_cum = np.cumsum([_CHANNEL_WEIGHTS_LOWER[c] for c in CHANNELS])
    is_upper = np.isin(room_type, _UPPER_TIERS)
    cum = np.where(is_upper[:, None], upper_cum[None, :], lower_cum[None, :])
    u = ctx.rng.child("channel").numpy.random(room_type.shape[0])
    idx = (u[:, None] < cum).argmax(axis=1)
    return np.asarray(CHANNELS, dtype=object)[idx]
