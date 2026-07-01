"""The ``reservations`` table: bookings with a lifecycle status."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.hotel.constants import (
    CHANNEL_WEIGHTS,
    CHANNELS,
    RES_STATUS,
    RES_STATUS_WEIGHTS,
    ROOM_TYPES,
)
from potato_tornado.core.collection import GenContext


def build_reservations(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(3000)
    props = ctx.table("properties")["property_id"].to_list()
    type_names = [t[0] for t in ROOM_TYPES]
    type_weights = [t[2] for t in ROOM_TYPES]

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
            "channel": ctx.dist.choice(n, CHANNELS, CHANNEL_WEIGHTS),
            "room_type": ctx.dist.choice(n, type_names, type_weights),
            "booked_date": booked,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "party_size": np.clip(ctx.dist.poisson(n, 1.3) + 1, 1, 6),
            "nights": nights,
            "status": ctx.dist.choice(n, RES_STATUS, RES_STATUS_WEIGHTS),
        }
    )
