"""The ``visits`` table: realised encounters for completed appointments.

One row per ``completed`` appointment (no-shows and cancellations never produce a
visit). The teaching signal is duration efficiency: ``actual_minutes`` draws
around the visit type's nominal ``scheduled_minutes`` with a per-type overrun
bias, so some procedure types systematically run long (New Patient, Minor
Procedure) and others run short (Telehealth). See
``scenarios/procedure-efficiency.md``.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.clinic.constants import VISIT_TYPES
from potato_tornado.core.collection import GenContext

_SCHEDULED_MIN = {v[0]: v[2] for v in VISIT_TYPES}
_OVERRUN_BIAS = {v[0]: v[4] for v in VISIT_TYPES}


def build_visits(ctx: GenContext) -> pl.DataFrame:
    completed = ctx.table("appointments").filter(pl.col("status") == "completed")
    n = completed.height
    visit_type = completed["visit_type"].to_list()

    scheduled_minutes = [_SCHEDULED_MIN[t] for t in visit_type]
    bias = np.array([_OVERRUN_BIAS[t] for t in visit_type])
    noise = ctx.dist.normal(n, mean=0.0, sd=0.15)
    actual_minutes = [
        max(5, round(s * (1 + b + z)))
        for s, b, z in zip(scheduled_minutes, bias, noise, strict=True)
    ]
    # Patients skew a few minutes late; occasional early arrivals, rare long delays.
    arrival_delay_min = np.clip(ctx.dist.normal(n, mean=3.0, sd=6.0), -15, 45).round().astype(int)

    return pl.DataFrame(
        {
            "visit_id": [f"VIS-{i:07d}" for i in range(1, n + 1)],
            "appointment_id": completed["appointment_id"],
            "patient_id": completed["patient_id"],
            "provider_id": completed["provider_id"],
            "visit_type": completed["visit_type"],
            "scheduled_minutes": scheduled_minutes,
            "actual_minutes": actual_minutes,
            "arrival_delay_min": arrival_delay_min,
        }
    )
