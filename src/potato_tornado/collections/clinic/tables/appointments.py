"""The ``appointments`` table: patients booked into provider slots.

Each row books one open ``slots`` row — the provider and time come from the slot,
so there is exactly one appointment per slot and no double-booking. Every
appointment carries a visit type (the procedure), the booking lead time, and a
lifecycle status. Two signals live here: the visit-type mix (feeds ``visits``
duration) and the no-show rate, which rises with booking lead time while its
marginal stays ≈ 12% (see ``scenarios/``).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.clinic.constants import VISIT_TYPES
from potato_tornado.core.collection import GenContext

_VISIT_TYPE_NAMES = [v[0] for v in VISIT_TYPES]
_VISIT_TYPE_WEIGHTS = [v[1] for v in VISIT_TYPES]

# Lifecycle hazards. A booked slot is first checked for "still on the books"
# (scheduled), then "called off ahead of time" (cancelled); whatever survives is
# kept (completed) or missed (no_show). No-show is the only lead-time-dependent
# hazard — see ``_no_show_prob``.
_P_SCHEDULED = 0.08
_P_CANCELLED = 0.12


def build_appointments(ctx: GenContext) -> pl.DataFrame:
    patients = ctx.table("patients")["patient_id"].to_list()
    booked = ctx.table("slots").filter(pl.col("is_booked"))
    n = booked.height

    lead_days = np.clip(ctx.dist.lognormal(n, median=10, sigma=0.8), 0, 120).astype(int)
    status = _assign_status(ctx, lead_days)

    return pl.DataFrame(
        {
            "appointment_id": [f"APT-{i:07d}" for i in range(1, n + 1)],
            "patient_id": ctx.dist.choice(n, patients),
            "provider_id": booked["provider_id"],
            "slot_id": booked["slot_id"],
            "visit_type": ctx.dist.choice(n, _VISIT_TYPE_NAMES, _VISIT_TYPE_WEIGHTS),
            "scheduled_at": booked["slot_at"],
            "lead_days": lead_days,
            "status": status,
        }
    )


def _no_show_prob(lead_days: np.ndarray) -> np.ndarray:
    """Per-appointment no-show probability, rising with booking lead time.

    Short-notice bookings are rarely missed; the further out a slot is booked, the
    more likely the patient no-shows. Tuned so the marginal no-show rate lands at
    ≈ 12% given the lead-time distribution (median ≈ 10 days).
    """
    return np.clip(0.09 + 0.004 * lead_days, 0.05, 0.30)


def _assign_status(ctx: GenContext, lead_days: np.ndarray) -> np.ndarray:
    n = lead_days.shape[0]
    u_scheduled = ctx.rng.numpy.random(n)
    u_cancelled = ctx.rng.numpy.random(n)
    u_no_show = ctx.rng.numpy.random(n)

    is_scheduled = u_scheduled < _P_SCHEDULED
    is_cancelled = ~is_scheduled & (u_cancelled < _P_CANCELLED)
    is_no_show = ~is_scheduled & ~is_cancelled & (u_no_show < _no_show_prob(lead_days))

    status = np.full(n, "completed", dtype=object)
    status[is_scheduled] = "scheduled"
    status[is_cancelled] = "cancelled"
    status[is_no_show] = "no_show"
    return status
