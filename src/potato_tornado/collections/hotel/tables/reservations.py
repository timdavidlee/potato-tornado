"""The ``reservations`` table: bookings with a lifecycle status."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.hotel.constants import (
    CANCEL_WINDOW_BETA_BY_PLAN,
    CHANNELS,
    CHILDREN_LAMBDA_BY_SEGMENT,
    CITY_GEO,
    DOMESTIC_SHARE,
    GUEST_SOURCE_COUNTRIES,
    LEAD_TIME_BY_CHANNEL,
    MARKET_SEGMENTS,
    RATE_PLAN_BY_CHANNEL,
    RATE_PLAN_CANCEL_MULT,
    RATE_PLANS,
    RES_STATUS,
    RES_STATUS_BY_CHANNEL,
    ROOM_TYPES,
    SEGMENT_BY_CHANNEL,
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

# Stay length and party size vary by segment rather than sitting flat across the whole
# table. Business channels (corporate / walk_in) book shorter stays than the leisure-heavy
# ota / direct guests; larger room classes draw larger parties. Both are Poisson(λ)+1 with
# λ keyed to the segment, drawn from their own child streams so they don't shift other
# columns' draws.
_NIGHTS_LAMBDA_BY_CHANNEL = {"direct": 2.3, "ota": 2.6, "corporate": 1.6, "walk_in": 1.6}
_PARTY_LAMBDA_BY_TYPE = {"Standard": 1.1, "Deluxe": 1.3, "Suite": 1.7, "Penthouse": 1.9}


def build_reservations(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(24000)
    props_df = ctx.table("properties")
    props = props_df["property_id"].to_list()
    # Booking volume scales with hotel size: a 210-room property draws far more
    # reservations than a 60-room one, so occupancy tracks capacity instead of sitting
    # flat across properties of wildly different sizes.
    prop_weights = props_df["total_rooms"].to_list()
    type_names = [t[0] for t in ROOM_TYPES]
    type_weights = [t[2] for t in ROOM_TYPES]

    room_type = ctx.dist.choice(n, type_names, type_weights)
    property_id = ctx.dist.choice(n, props, prop_weights)
    channel = _sample_channel(ctx, room_type)
    # Rate plan is drawn before status because status (cancellation) depends on it: a
    # non-refundable Advance-Purchase booking drops off far less than a flexible BAR one.
    rate_plan = _sample_rate_plan(ctx, channel)
    status = _sample_status(ctx, channel, rate_plan)
    # Demand-side axis, orthogonal to channel; then the party's family composition and the
    # guest's origin. All three draw from their own child streams so they don't shift the
    # existing columns' draws.
    market_segment = _sample_segment(ctx, channel)

    # Draw the arrival (check-in) date seasonally, then back out the booking date from
    # the lead time — so the summer peak lands cleanly on check_in_date / occupancy.
    check_in = _seasonal_arrivals(
        ctx.rng.child("arrival"), n, ctx.config.start_date, ctx.config.end_date
    )
    lead_days = _sample_lead_days(ctx, channel)
    nights_lam = np.array([_NIGHTS_LAMBDA_BY_CHANNEL[c] for c in channel])
    nights = np.clip(ctx.rng.child("nights").numpy.poisson(nights_lam) + 1, 1, 21)
    party_lam = np.array([_PARTY_LAMBDA_BY_TYPE[t] for t in room_type])
    party_size = np.clip(ctx.rng.child("party").numpy.poisson(party_lam) + 1, 1, 6)
    # Split the party into adults + children (children keyed to segment, capped so each
    # party keeps ≥1 adult), and draw the guest's origin from the property's country.
    child_lam = np.array([CHILDREN_LAMBDA_BY_SEGMENT[s] for s in market_segment])
    children = np.minimum(ctx.rng.child("children").numpy.poisson(child_lam), party_size - 1)
    adults = party_size - children
    guest_country = _sample_guest_country(ctx, property_id, props_df)
    booked = np.array(
        [ci - timedelta(days=int(lead)) for ci, lead in zip(check_in, lead_days, strict=True)],
        dtype=object,
    )
    check_out = np.array(
        [ci + timedelta(days=int(nt)) for ci, nt in zip(check_in, nights, strict=True)],
        dtype=object,
    )
    cancellation_date = _cancellation_dates(ctx, status, rate_plan, booked, lead_days)

    return pl.DataFrame(
        {
            "reservation_id": [f"RES-{i:07d}" for i in range(1, n + 1)],
            "property_id": property_id,
            "guest_name": ctx.entities.people(n)["full_name"],
            "guest_country": guest_country,
            "channel": channel,
            "rate_plan": rate_plan,
            "market_segment": market_segment,
            "room_type": room_type,
            "booked_date": booked,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "cancellation_date": cancellation_date,
            "party_size": party_size,
            "adults": adults,
            "children": children,
            "nights": nights,
            "status": status,
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


def _sample_segment(ctx: GenContext, channel: np.ndarray) -> np.ndarray:
    """Per-row market segment weighted by channel (corporate → business, OTA → leisure)."""
    cum_by_channel = {c: np.cumsum(w) for c, w in SEGMENT_BY_CHANNEL.items()}
    cum = np.array([cum_by_channel[c] for c in channel])  # (n, len(MARKET_SEGMENTS))
    u = ctx.rng.child("segment").numpy.random(channel.shape[0])
    idx = (u[:, None] < cum).argmax(axis=1)
    return np.asarray(MARKET_SEGMENTS, dtype=object)[idx]


def _sample_guest_country(
    ctx: GenContext, property_id: np.ndarray, props_df: pl.DataFrame
) -> np.ndarray:
    """Per-row guest origin: the property's own country with prob ``DOMESTIC_SHARE``, else a
    weighted draw from the international feeder markets."""
    prop_country = dict(
        zip(
            props_df["property_id"].to_list(),
            [CITY_GEO[c][0] for c in props_df["city"].to_list()],
            strict=True,
        )
    )
    n = property_id.shape[0]
    domestic = np.array([prop_country[p] for p in property_id], dtype=object)
    intl_names = [c for c, _ in GUEST_SOURCE_COUNTRIES]
    intl_weights = np.array([w for _, w in GUEST_SOURCE_COUNTRIES], dtype=float)
    rng = ctx.rng.child("country").numpy
    international = rng.choice(intl_names, size=n, p=intl_weights / intl_weights.sum())
    is_domestic = rng.random(n) < DOMESTIC_SHARE
    return np.where(is_domestic, domestic, international)


def _cancellation_dates(
    ctx: GenContext,
    status: np.ndarray,
    rate_plan: np.ndarray,
    booked: np.ndarray,
    lead_days: np.ndarray,
) -> np.ndarray:
    """Cancellation date for `cancelled` bookings, else None (nullable column).

    The cancel lands at ``booked + f * lead_days`` where the window fraction ``f`` is
    ``Beta(a, b)`` keyed by rate plan (`CANCEL_WINDOW_BETA_BY_PLAN`): flexible BAR cancels
    late (``f`` near 1, close to arrival), non-refundable Advance-Purchase early. `no_show`
    and `honoured` rows are null — a no-show never cancels.
    """
    a = np.array([CANCEL_WINDOW_BETA_BY_PLAN[p][0] for p in rate_plan])
    b = np.array([CANCEL_WINDOW_BETA_BY_PLAN[p][1] for p in rate_plan])
    frac = ctx.rng.child("cancel").numpy.beta(a, b)
    offsets = np.floor(frac * lead_days).astype(int)
    dates = [bk + timedelta(days=int(o)) for bk, o in zip(booked, offsets, strict=True)]
    return np.array(
        [d if s == "cancelled" else None for d, s in zip(dates, status, strict=True)],
        dtype=object,
    )


def _sample_lead_days(ctx: GenContext, channel: np.ndarray) -> np.ndarray:
    """Per-row booking lead time, lognormal with (median, sigma) keyed by channel.

    OTA books far ahead with a fat tail, walk_in is same-/next-day; overall stays
    right-skewed with median ≈14 days. Clipped to the [0, 240] booking-arithmetic cap.
    """
    median = np.array([LEAD_TIME_BY_CHANNEL[c][0] for c in channel])
    sigma = np.array([LEAD_TIME_BY_CHANNEL[c][1] for c in channel])
    draws = ctx.rng.child("lead").numpy.normal(np.log(median), sigma)
    return np.clip(np.exp(draws), 0, 240).astype(int)


def _sample_rate_plan(ctx: GenContext, channel: np.ndarray) -> np.ndarray:
    """Per-row rate plan weighted by channel (corporate → negotiated, walk_in → BAR)."""
    cum_by_channel = {c: np.cumsum(w) for c, w in RATE_PLAN_BY_CHANNEL.items()}
    cum = np.array([cum_by_channel[c] for c in channel])  # (n, len(RATE_PLANS))
    u = ctx.rng.child("rate_plan").numpy.random(channel.shape[0])
    idx = (u[:, None] < cum).argmax(axis=1)
    return np.asarray(RATE_PLANS, dtype=object)[idx]


def _sample_status(ctx: GenContext, channel: np.ndarray, rate_plan: np.ndarray) -> np.ndarray:
    """Per-row reservation status weighted by channel, with the drop-off scaled by rate plan.

    The base honoured/cancelled/no_show mix comes from the channel
    (``RES_STATUS_BY_CHANNEL``); the cancel+no_show mass is then multiplied by the rate
    plan's ``RATE_PLAN_CANCEL_MULT`` (non-refundable Advance-Purchase drops off far less),
    the cancelled:no_show split within that mass is preserved, and honoured takes the rest.
    So drop-off concentrates in the OTA *and* falls sharply for non-refundable plans.
    """
    base = np.array([RES_STATUS_BY_CHANNEL[c] for c in channel])  # (n, 3)
    mult = np.array([RATE_PLAN_CANCEL_MULT[p] for p in rate_plan])  # (n,)
    base_drop = base[:, 1] + base[:, 2]
    dropoff = np.clip(base_drop * mult, 0.0, 0.95)
    cancel_ratio = np.where(base_drop > 0, base[:, 1] / base_drop, 1.0)
    probs = np.stack(
        [1.0 - dropoff, dropoff * cancel_ratio, dropoff * (1.0 - cancel_ratio)], axis=1
    )
    cum = np.cumsum(probs, axis=1)
    u = ctx.rng.child("status").numpy.random(channel.shape[0])
    idx = (u[:, None] < cum).argmax(axis=1)
    return np.asarray(RES_STATUS, dtype=object)[idx]


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
