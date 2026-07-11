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
from potato_tornado.core.distributions import Distributions

_SCHEDULED_MIN = {v[0]: v[2] for v in VISIT_TYPES}
_OVERRUN_BIAS = {v[0]: v[4] for v in VISIT_TYPES}

# Coarse clinical category for the encounter. Drawn flat and INDEPENDENT of
# visit_type (and therefore of the duration-overrun bias) on its own child stream:
# coupling it to visit_type would leak the "procedures run long" overrun into the
# category, and that concentration is a scenario signal, not a realism fact.
_DIAGNOSIS_CATEGORIES = ["preventive", "acute", "chronic_followup", "procedure"]
_DIAGNOSIS_WEIGHTS = [0.25, 0.40, 0.25, 0.10]

# Arrival delay vs. time of day. The clinic runs behind as the session wears on:
# an appointment's mean minutes-late grows linearly with its scheduled hour. The
# pivot (≈ 9:00) is where the clinic is on time; the slope adds ≈ 1.6 min/hour, so
# by late afternoon patients wait ≈ 10+ min. Centred so the overall mean stays
# ≈ 3 min given the late-morning peak. See ``scenarios/clinic-runs-late.md``.
_ARRIVAL_SLOPE = 1.6
_ARRIVAL_PIVOT_HOUR = 9.0


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
    # Patients skew late, and the clinic falls further behind through the day: mean
    # delay grows with the appointment's scheduled hour (occasional early arrivals,
    # rare long delays).
    hour = completed["scheduled_at"].dt.hour().to_numpy()
    delay_mean = _ARRIVAL_SLOPE * (hour - _ARRIVAL_PIVOT_HOUR)
    arrival_delay_min = (
        np.clip(ctx.dist.normal(n, mean=0.0, sd=5.0) + delay_mean, -15, 45).round().astype(int)
    )
    diagnosis_category = Distributions(ctx.rng.child("diagnosis_category")).choice(
        n, _DIAGNOSIS_CATEGORIES, _DIAGNOSIS_WEIGHTS
    )

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
            "diagnosis_category": diagnosis_category,
        }
    )
