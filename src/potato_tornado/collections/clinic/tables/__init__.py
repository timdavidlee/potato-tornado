"""Table builders for the clinic collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.clinic.tables.appointments import build_appointments
from potato_tornado.collections.clinic.tables.patients import build_patients
from potato_tornado.collections.clinic.tables.providers import build_providers

__all__ = [
    "build_appointments",
    "build_patients",
    "build_providers",
]
