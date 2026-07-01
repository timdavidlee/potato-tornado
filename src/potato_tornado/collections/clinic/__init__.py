"""Collection: outpatient clinic slot → booking → visit → billing workflow.

Models the full front-office lifecycle of a small outpatient clinic: providers
publish open appointment slots, patients book them (each booking carries a visit
type and lands in a completed / no_show / cancelled / scheduled status), completed
bookings become realised visits, and every visit is billed on an invoice.

Tables
------
- ``providers``    : clinicians, each with a specialty.
- ``patients``     : the people who book appointments.
- ``slots``        : provider open availability; ``is_booked`` marks booked slots.
- ``appointments`` : bookings that fill a slot, with a visit type, booking lead
                     time and a lifecycle status.
- ``visits``       : realised encounters for completed appointments (actual vs.
                     scheduled duration).
- ``invoices``     : billing per visit (payer, charge, amount paid, balance).

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.clinic.tables import (
    build_appointments,
    build_invoices,
    build_patients,
    build_providers,
    build_slots,
    build_visits,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="clinic",
        description="Outpatient clinic workflow: providers publish open slots, "
        "patients book them (completed / no-show / cancelled lifecycle), completed "
        "bookings become visits, and each visit is billed on an invoice.",
        tables=(
            TableSpec("providers", build_providers, description="Clinicians with a specialty."),
            TableSpec("patients", build_patients, description="People who book appointments."),
            TableSpec(
                "slots",
                build_slots,
                depends_on=("providers",),
                description="Provider open availability; is_booked marks booked slots.",
            ),
            TableSpec(
                "appointments",
                build_appointments,
                depends_on=("patients", "slots"),
                description="Bookings that fill a slot, with a visit type and status.",
            ),
            TableSpec(
                "visits",
                build_visits,
                depends_on=("appointments",),
                description="Realised encounters for completed appointments.",
            ),
            TableSpec(
                "invoices",
                build_invoices,
                depends_on=("visits",),
                description="Billing per visit: payer, charge, amount paid, balance.",
            ),
        ),
    )


register("clinic", build)
