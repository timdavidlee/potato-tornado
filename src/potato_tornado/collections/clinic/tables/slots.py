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

from potato_tornado.core.collection import GenContext


def build_slots(ctx: GenContext) -> pl.DataFrame:
    providers = ctx.table("providers")["provider_id"].to_list()
    n = ctx.n(6000)

    business_days = _business_days(ctx.config.start_date, ctx.config.end_date)
    day_idx = ctx.dist.integers(n, 0, len(business_days) - 1)
    days = np.array([business_days[int(i)] for i in day_idx], dtype=object)
    clock = ctx.dist.times_of_day(n, peak_hour=11.0, spread_hours=3.0)
    slot_at = ctx.dist.combine(days, clock)

    provider_id = ctx.dist.choice(n, providers)
    # Per-provider booking probability: some providers/specialties run fuller than
    # others, so utilisation (booked / total slots) varies across the roster.
    util = ctx.dist.clamped_normal(len(providers), mean=0.67, sd=0.12, low=0.35, high=0.92)
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


def _business_days(start: date, end: date) -> list[date]:
    """Weekday dates in ``[start, end)`` — the clinic is closed on weekends."""
    span = (end - start).days
    return [d for i in range(span) if (d := start + timedelta(days=i)).weekday() < 5]
