"""Domain reference data (catalogs) for the clinic collection.

The fixed "seed" facts the outpatient-scheduling generators draw from: provider
specialties, the appointment lifecycle mix, the visit-type (procedure) menu with
its nominal duration and base charge, and the payer mix used for billing. Kept
here so the ``tables/`` modules stay focused on generation logic and share one
source of truth (``VISIT_TYPES`` in particular feeds both ``appointments`` and
``visits``). See ``scenarios/`` for the signals these values are tuned to produce.
"""

from __future__ import annotations

SPECIALTIES = [
    "Family Medicine",
    "Pediatrics",
    "Internal Medicine",
    "Dermatology",
    "Cardiology",
    "Orthopedics",
]

# Appointment lifecycle. A booked slot is either kept (completed), missed
# (no_show), called off ahead of time (cancelled), or still on the books
# (scheduled). No-show is the planted teaching signal, and its rate rises with
# booking lead time (see scenarios/no-show-rises-with-lead-time.md) — so the
# generator computes no_show per-row rather than drawing it from a flat weight.
# These marginal weights document the mix the per-row model is tuned to hit.
APPT_STATUS = ["completed", "no_show", "cancelled", "scheduled"]
APPT_STATUS_WEIGHTS = [0.68, 0.12, 0.12, 0.08]

# Visit-type (procedure) menu. Each row is
#   (visit_type, booking_weight, scheduled_minutes, base_charge, overrun_bias)
# where ``scheduled_minutes`` is the nominal slot length, ``base_charge`` the
# billed amount before payer adjustment, and ``overrun_bias`` the fractional pull
# on realised duration in ``visits`` (positive → the type systematically runs
# long, negative → it runs short). New-patient and minor-procedure visits over-run;
# telehealth under-runs — that spread is the procedure-efficiency signal.
# Weights sum to 1.0.
VISIT_TYPES = [
    ("New Patient", 0.12, 40, 220.0, 0.15),
    ("Follow-up", 0.30, 20, 110.0, 0.00),
    ("Annual Physical", 0.18, 30, 180.0, 0.05),
    ("Chronic Care", 0.20, 25, 150.0, 0.10),
    ("Minor Procedure", 0.08, 45, 340.0, 0.20),
    ("Telehealth", 0.12, 15, 90.0, -0.05),
]

# Payer mix for invoices. Each row is ``(payer, mix_weight, paid_in_full_prob)``
# where ``paid_in_full_prob`` is the chance the claim settles in full (balance 0,
# status "paid"); otherwise only a partial amount is recovered and the remainder
# ages into an outstanding balance. Insured payers settle in full most of the
# time; self-pay rarely does, so accounts-receivable concentrates there — in both
# the count of open invoices and the dollars (see scenarios/revenue-and-ar.md).
# Weights sum to 1.0.
PAYERS = [
    ("Medicare", 0.32, 0.92),
    ("Medicaid", 0.18, 0.88),
    ("Commercial", 0.38, 0.90),
    ("Self-pay", 0.12, 0.20),
]

# Fraction of the charge recovered on an invoice that is *not* paid in full — the
# partial payment (deductible/copay collected, remainder written to AR). Shared
# across payers; drawn per invoice around this mean.
PARTIAL_RECOVERY_MEAN = 0.5
