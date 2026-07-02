"""The ``subscribers`` table: the service's user accounts."""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.streaming.constants import (
    ACQUISITION_CHANNEL_WEIGHTS,
    ACQUISITION_CHANNELS,
    DEVICE_PLATFORM_WEIGHTS,
    DEVICE_PLATFORMS,
    REGIONS,
)
from potato_tornado.core.collection import GenContext


def build_subscribers(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(2000)
    people = ctx.entities.people(n)
    codes = [code for code, *_ in REGIONS]
    weights = [weight for _code, _name, weight, *_ in REGIONS]
    # Sign-up / primary-watch device and acquisition channel — dedicated child
    # streams so they don't shift the region/date draws above. The channel drives
    # downstream churn (see subscriptions.py), but is itself a flat draw here.
    device = ctx.rng.child("device").numpy.choice(
        np.asarray(DEVICE_PLATFORMS, dtype=object), size=n, p=DEVICE_PLATFORM_WEIGHTS
    )
    channel = ctx.rng.child("channel").numpy.choice(
        np.asarray(ACQUISITION_CHANNELS, dtype=object), size=n, p=ACQUISITION_CHANNEL_WEIGHTS
    )
    return pl.DataFrame(
        {
            "subscriber_id": [f"SUB-{i:06d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "signup_date": ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date),
            "region": ctx.dist.choice(n, codes, weights),
            "device_platform": device,
            "acquisition_channel": channel,
        }
    )
