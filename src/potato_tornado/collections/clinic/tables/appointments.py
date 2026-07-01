"""The ``appointments`` table: booked slots with a lifecycle status.

Placeholder scheduling table — each row ties a patient to a provider at a booked
time, carries the booking lead time, and lands in one of the lifecycle statuses
(the no-show mix is the planted signal). Richer scheduling tables (open slots,
realised visits, invoices) are the intended next expansion of this collection.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.clinic.constants import APPT_STATUS, APPT_STATUS_WEIGHTS
from potato_tornado.core.collection import GenContext


def build_appointments(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(4000)
    patients = ctx.table("patients")["patient_id"].to_list()
    providers = ctx.table("providers")["provider_id"].to_list()

    days = ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date)
    clock = ctx.dist.times_of_day(n, peak_hour=11.0, spread_hours=3.0)
    scheduled_at = ctx.dist.combine(days, clock)
    lead_days = np.clip(ctx.dist.lognormal(n, median=10, sigma=0.8), 0, 120).astype(int)

    return pl.DataFrame(
        {
            "appointment_id": [f"APT-{i:07d}" for i in range(1, n + 1)],
            "patient_id": ctx.dist.choice(n, patients),
            "provider_id": ctx.dist.choice(n, providers),
            "scheduled_at": scheduled_at,
            "lead_days": lead_days,
            "status": ctx.dist.choice(n, APPT_STATUS, APPT_STATUS_WEIGHTS),
        }
    )
