"""The ``appointments`` table: patients booked into provider slots.

Each row books one open ``slots`` row — the provider and time come from the slot,
so there is exactly one appointment per slot and no double-booking. Signals
here: the visit-type mix conditioned on provider specialty (feeds ``visits``
duration), booking concentration among a frequent core of patients, the no-show
rate rising with booking lead time, and the no-show rate running highest for New
Patient visits — while the marginal stays ≈ 12% (see ``scenarios/``).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.clinic.constants import SPECIALTY_VISIT_MIX, VISIT_TYPES
from potato_tornado.core.collection import GenContext
from potato_tornado.core.distributions import Distributions

_VISIT_TYPE_NAMES = [v[0] for v in VISIT_TYPES]

# How the booking reached the clinic. Flat categorical, independent of everything
# else on the appointment (a booking-funnel dimension, not a no-show driver).
_BOOKING_CHANNELS = ["phone", "portal", "walk_in", "referral"]
_BOOKING_CHANNEL_WEIGHTS = [0.40, 0.35, 0.10, 0.15]

# Appointment reminder. ~70% of bookings get a reminder; when sent it goes out over
# one channel (else the channel is null). Deliberately flat — it does NOT lower the
# no-show rate here; the reminder->attendance lift is a scenario, left unplanted.
_REMINDER_CHANNELS = ["sms", "email"]
_REMINDER_CHANNEL_WEIGHTS = [0.6, 0.4]

# Lifecycle hazards. A booked slot is first checked for "still on the books"
# (scheduled), then "called off ahead of time" (cancelled); whatever survives is
# kept (completed) or missed (no_show). No-show is the only lead-time-dependent
# hazard — see ``_no_show_prob``.
_P_SCHEDULED = 0.08
_P_CANCELLED = 0.12

# No-show risk also depends on visit type, independent of lead time: a New
# Patient hasn't built the habit of showing up yet, so they no-show markedly more
# than an established-care visit. Additive offset on top of the lead-time term.
_NO_SHOW_TYPE_OFFSET = {
    "New Patient": 0.13,
    "Follow-up": -0.01,
    "Annual Physical": -0.01,
    "Chronic Care": -0.02,
    "Minor Procedure": -0.04,
    "Telehealth": -0.02,
}

# Per-patient booking-propensity spread (lognormal sigma). Patients don't book
# uniformly: a frequent core rebooks far more than the long tail. This sigma is
# tuned so the top decile of patients takes ~a third of appointments — see
# ``scenarios/frequent-vs-one-off-patients.md``.
_PATIENT_PROPENSITY_SIGMA = 0.8


def build_appointments(ctx: GenContext) -> pl.DataFrame:
    patients = ctx.table("patients")["patient_id"].to_list()
    booked = ctx.table("slots").filter(pl.col("is_booked"))
    n = booked.height

    lead_days = np.clip(ctx.dist.lognormal(n, median=10, sigma=0.8), 0, 120).astype(int)
    visit_type = _draw_visit_types(ctx, booked["provider_id"])
    status = _assign_status(ctx, lead_days, visit_type)
    booking_channel = Distributions(ctx.rng.child("booking_channel")).choice(
        n, _BOOKING_CHANNELS, _BOOKING_CHANNEL_WEIGHTS
    )
    reminder_sent = Distributions(ctx.rng.child("reminder_sent")).bernoulli(n, p=0.7)
    channel_draw = Distributions(ctx.rng.child("reminder_channel")).choice(
        n, _REMINDER_CHANNELS, _REMINDER_CHANNEL_WEIGHTS
    )
    # Channel is populated only when a reminder was actually sent; null otherwise.
    reminder_channel = np.array(
        [c if sent else None for c, sent in zip(channel_draw, reminder_sent, strict=True)],
        dtype=object,
    )

    return pl.DataFrame(
        {
            "appointment_id": [f"APT-{i:07d}" for i in range(1, n + 1)],
            "patient_id": _draw_patients(ctx, patients, n),
            "provider_id": booked["provider_id"],
            "slot_id": booked["slot_id"],
            "visit_type": visit_type,
            "scheduled_at": booked["slot_at"],
            "lead_days": lead_days,
            "status": status,
            "booking_channel": booking_channel,
            "reminder_sent": reminder_sent,
            "reminder_channel": reminder_channel,
        }
    )


def _draw_visit_types(ctx: GenContext, provider_id: pl.Series) -> np.ndarray:
    """Draw each appointment's visit type from its provider's specialty profile.

    Visit type is not independent of who the provider is: each specialty has its
    own ``SPECIALTY_VISIT_MIX`` weights (dermatology skews to procedures, paediatrics
    to new-patient visits, etc.), so the mix differs by specialty while the
    clinic-wide marginal stays near the base booking weights. Rows are drawn per
    specialty group from an independent ``child`` stream, so this does not shift the
    table's other draws. See ``scenarios/visit-mix-by-specialty.md``.
    """
    specialty_by_provider = _specialty_lookup(ctx)
    specialty = np.array([specialty_by_provider[p] for p in provider_id.to_list()], dtype=object)

    stream = ctx.rng.child("visit_type").numpy
    visit_type = np.empty(specialty.shape[0], dtype=object)
    for name, weights in SPECIALTY_VISIT_MIX.items():
        rows = specialty == name
        count = int(rows.sum())
        if count:
            visit_type[rows] = stream.choice(_VISIT_TYPE_NAMES, size=count, p=list(weights))
    return visit_type


def _specialty_lookup(ctx: GenContext) -> dict[str, str]:
    """Map ``provider_id -> specialty`` from the providers table."""
    providers = ctx.table("providers")
    return dict(
        zip(providers["provider_id"].to_list(), providers["specialty"].to_list(), strict=True)
    )


def _draw_patients(ctx: GenContext, patients: list[str], n: int) -> np.ndarray:
    """Assign each appointment a patient with a heavy-tailed booking propensity.

    Each patient gets a lognormal weight, so a frequent core rebooks far more than
    the long tail (top decile ≈ a third of appointments). Both the weights and the
    selection come from an independent ``child`` stream, so this does not shift the
    table's other draws (lead time, status, visit type). See
    ``scenarios/frequent-vs-one-off-patients.md``.
    """
    stream = ctx.rng.child("patient_bookings").numpy
    weights = np.exp(stream.normal(0.0, _PATIENT_PROPENSITY_SIGMA, len(patients)))
    weights /= weights.sum()
    return stream.choice(np.asarray(patients, dtype=object), size=n, p=weights)


def _no_show_prob(lead_days: np.ndarray, visit_type: np.ndarray) -> np.ndarray:
    """Per-appointment no-show probability: rises with lead time, shifted by visit type.

    Short-notice bookings are rarely missed; the further out a slot is booked, the
    more likely the patient no-shows. New Patient visits carry an additional
    baseline risk on top of that. Tuned so the marginal no-show rate lands at
    ≈ 12% given the lead-time distribution (median ≈ 10 days) and visit-type mix.
    """
    offset = np.array([_NO_SHOW_TYPE_OFFSET[v] for v in visit_type])
    return np.clip(0.09 + 0.004 * lead_days + offset, 0.03, 0.32)


def _assign_status(ctx: GenContext, lead_days: np.ndarray, visit_type: np.ndarray) -> np.ndarray:
    n = lead_days.shape[0]
    u_scheduled = ctx.rng.numpy.random(n)
    u_cancelled = ctx.rng.numpy.random(n)
    u_no_show = ctx.rng.numpy.random(n)

    is_scheduled = u_scheduled < _P_SCHEDULED
    is_cancelled = ~is_scheduled & (u_cancelled < _P_CANCELLED)
    is_no_show = ~is_scheduled & ~is_cancelled & (u_no_show < _no_show_prob(lead_days, visit_type))

    status = np.full(n, "completed", dtype=object)
    status[is_scheduled] = "scheduled"
    status[is_cancelled] = "cancelled"
    status[is_no_show] = "no_show"
    return status
