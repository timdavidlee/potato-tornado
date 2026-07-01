"""Collection: outpatient clinic appointment scheduling (placeholder).

Models the booking workflow for a small outpatient clinic: patients book
appointments with providers, and each appointment lands in a lifecycle status
(completed / no_show / cancelled / scheduled). This is a deliberately thin
placeholder — the intended expansion adds open slots, realised visits and
invoices to model the full slot → booking → visit → billing workflow.

Tables
------
- ``providers``    : clinicians, each with a specialty.
- ``patients``     : the people who book appointments.
- ``appointments`` : booked slots with a lifecycle status and booking lead time.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.clinic.tables import (
    build_appointments,
    build_patients,
    build_providers,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="clinic",
        description="Outpatient clinic appointment scheduling: patients book "
        "appointments with providers, tracked through a completed / no-show / "
        "cancelled lifecycle.",
        tables=(
            TableSpec("providers", build_providers, description="Clinicians with a specialty."),
            TableSpec("patients", build_patients, description="People who book appointments."),
            TableSpec(
                "appointments",
                build_appointments,
                depends_on=("patients", "providers"),
                description="Booked slots with a lifecycle status.",
            ),
        ),
    )


register("clinic", build)
