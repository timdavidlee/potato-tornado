"""Table builders for the clinic collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.clinic.tables.appointments import build_appointments
from potato_tornado.collections.clinic.tables.invoices import build_invoices
from potato_tornado.collections.clinic.tables.patients import build_patients
from potato_tornado.collections.clinic.tables.providers import build_providers
from potato_tornado.collections.clinic.tables.slots import build_slots
from potato_tornado.collections.clinic.tables.visits import build_visits

__all__ = [
    "build_appointments",
    "build_invoices",
    "build_patients",
    "build_providers",
    "build_slots",
    "build_visits",
]
