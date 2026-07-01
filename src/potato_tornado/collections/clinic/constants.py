"""Domain reference data (catalogs) for the clinic collection.

Placeholder catalogs for the outpatient-scheduling collection: the provider
specialties and the appointment lifecycle mix the generators draw from. Kept here
so the ``tables/`` modules stay focused on generation logic. See ``scenarios/``
for the signals these values are tuned to produce.
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
# (scheduled). No-show is the planted teaching signal — see scenarios/.
APPT_STATUS = ["completed", "no_show", "cancelled", "scheduled"]
APPT_STATUS_WEIGHTS = [0.68, 0.12, 0.12, 0.08]
