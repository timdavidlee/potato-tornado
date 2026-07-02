"""The ``reservations`` table: bookings with a lifecycle status."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.hotel.constants import (
    CHANNELS,
    RES_STATUS,
    RES_STATUS_WEIGHTS,
    ROOM_TYPES,
)
from potato_tornado.core.collection import GenContext
from potato_tornado.core.rng import Rng

# Booking channel depends on room class. Guests booking the upper tiers skew to
# direct (loyalty / concierge), the mass-market tiers skew to the OTA — so OTA
# still leads overall, but direct is the modal channel for the top of the ladder.
# Keys match CHANNELS; each row sums to 1.0.
_CHANNEL_WEIGHTS_LOWER = {"direct": 0.28, "ota": 0.50, "corporate": 0.16, "walk_in": 0.06}
_CHANNEL_WEIGHTS_UPPER = {"direct": 0.55, "ota": 0.22, "corporate": 0.18, "walk_in": 0.05}
_UPPER_TIERS = ("Suite", "Penthouse")

# Arrivals are seasonal: check-ins concentrate in summer and thin out in winter, the
# same cycle repeating each year. A day's arrival weight is a cosine peaking on
# ``_PEAK_DOY`` (mid-July); ``_SEASON_AMP`` sets the depth, so the busiest day of the
# year draws ``(1 + amp) / (1 - amp)`` as many arrivals as the quietest.
_PEAK_DOY = 196  # ~15 July
_SEASON_AMP = 0.23  # → peak:trough ≈ 1.6:1


def build_reservations(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(24000)
    props = ctx.table("properties")["property_id"].to_list()
    type_names = [t[0] for t in ROOM_TYPES]
    type_weights = [t[2] for t in ROOM_TYPES]

    room_type = ctx.dist.choice(n, type_names, type_weights)
    channel = _sample_channel(ctx, room_type)

    # Draw the arrival (check-in) date seasonally, then back out the booking date from
    # the lead time — so the summer peak lands cleanly on check_in_date / occupancy.
    check_in = _seasonal_arrivals(
        ctx.rng.child("arrival"), n, ctx.config.start_date, ctx.config.end_date
    )
    lead_days = np.clip(ctx.dist.lognormal(n, median=14, sigma=0.9), 0, 240).astype(int)
    nights = np.clip(ctx.dist.poisson(n, 2.2) + 1, 1, 21)
    booked = np.array(
        [ci - timedelta(days=int(lead)) for ci, lead in zip(check_in, lead_days, strict=True)],
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


def _seasonal_arrivals(rng: Rng, n: int, start: date, end: date) -> np.ndarray:
    """Sample ``n`` arrival dates in ``[start, end)`` weighted toward summer.

    Each day's weight is ``1 + _SEASON_AMP * cos(2*pi*(day_of_year - _PEAK_DOY)/365.25)``,
    so arrivals peak in mid-July and trough in winter, and the cycle repeats every
    year the window spans. Drawn from an independent child stream so it doesn't shift
    the other ``reservations`` columns' draws.
    """
    span = (end - start).days
    days = [start + timedelta(days=o) for o in range(span)]
    doy = np.array([d.timetuple().tm_yday for d in days], dtype=float)
    weights = 1.0 + _SEASON_AMP * np.cos(2.0 * np.pi * (doy - _PEAK_DOY) / 365.25)
    offsets = rng.numpy.choice(span, size=n, p=weights / weights.sum())
    return np.array([start + timedelta(days=int(o)) for o in offsets], dtype=object)
