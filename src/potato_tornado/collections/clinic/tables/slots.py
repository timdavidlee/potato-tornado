"""The ``slots`` table: provider open availability (booking capacity).

Each row is one bookable appointment slot on a provider's calendar, on a weekday
during clinic hours. ``is_booked`` marks the slots that ``appointments`` fills;
the booked fraction per provider is the provider-utilisation signal. Slots are
generated first so appointments can book real slot rows (inheriting the slot's
provider and time), which keeps one appointment per slot and rules out
double-booking.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.clinic.constants import SPECIALTY_UTILISATION
from potato_tornado.core.collection import GenContext

# Seasonal + growth shape for slot volume. Slot days are drawn with a per-day
# weight (seasonal cycle times an upward trend) rather than uniformly, so booked
# appointment volume has a repeating winter peak and drifts up year over year --
# see ``scenarios/seasonal-and-growth.md``. Amplitude 0.16 lands Dec-Feb volume at
# ~1.3x the Jun-Aug trough; the 0.08 trend adds ~8%/year.
_SEASONAL_AMPLITUDE = 0.16
_ANNUAL_GROWTH = 0.08
_WINTER_PEAK_DOY = 15  # seasonal peak ≈ mid-January


def build_slots(ctx: GenContext) -> pl.DataFrame:
    providers_df = ctx.table("providers")
    providers = providers_df["provider_id"].to_list()
    specialty_of = dict(zip(providers, providers_df["specialty"].to_list(), strict=True))
    n = ctx.n(6000)

    business_days = _business_days(ctx.config.start_date, ctx.config.end_date)
    day_weights = _calendar_weights(business_days, ctx.config.start_date)
    day_idx = ctx.rng.numpy.choice(len(business_days), size=n, p=day_weights)
    days = np.array([business_days[int(i)] for i in day_idx], dtype=object)
    clock = ctx.dist.times_of_day(n, peak_hour=11.0, spread_hours=3.0)
    slot_at = ctx.dist.combine(days, clock)

    provider_id = ctx.dist.choice(n, providers)
    # Per-provider booking probability keyed by specialty: demand-heavy specialties
    # run near-full while others carry spare capacity, so utilisation (booked / total
    # slots) concentrates by specialty. A small per-provider jitter varies clinicians
    # within a specialty; drawn from a named child stream to stay deterministic.
    base = np.array([SPECIALTY_UTILISATION[specialty_of[p]] for p in providers])
    jitter = ctx.rng.child("provider_util").numpy.normal(0.0, 0.04, size=len(providers))
    util = np.clip(base + jitter, 0.35, 0.95)
    prob_by_provider = dict(zip(providers, util, strict=True))
    p_row = np.array([prob_by_provider[p] for p in provider_id])
    is_booked = ctx.rng.numpy.random(n) < p_row

    return pl.DataFrame(
        {
            "slot_id": [f"SLT-{i:07d}" for i in range(1, n + 1)],
            "provider_id": provider_id,
            "slot_at": slot_at,
            "is_booked": is_booked,
        }
    )


def _calendar_weights(business_days: list[date], start: date) -> np.ndarray:
    """Per-business-day sampling weight: a winter-peaking seasonal cycle times an
    upward year-over-year growth trend, normalised to sum to 1.

    Weighting slot generation this way (rather than drawing days uniformly) gives
    booked-appointment volume a repeating winter peak and a gentle upward drift —
    the temporal signal in ``scenarios/seasonal-and-growth.md``.
    """
    doy = np.array([d.timetuple().tm_yday for d in business_days], dtype=float)
    seasonal = 1.0 + _SEASONAL_AMPLITUDE * np.cos(2 * np.pi * (doy - _WINTER_PEAK_DOY) / 365.25)
    elapsed_years = np.array([(d - start).days for d in business_days], dtype=float) / 365.25
    growth = (1.0 + _ANNUAL_GROWTH) ** elapsed_years
    weights = seasonal * growth
    return weights / weights.sum()


def _business_days(start: date, end: date) -> list[date]:
    """Weekday dates in ``[start, end)`` — the clinic is closed on weekends."""
    span = (end - start).days
    return [d for i in range(span) if (d := start + timedelta(days=i)).weekday() < 5]
