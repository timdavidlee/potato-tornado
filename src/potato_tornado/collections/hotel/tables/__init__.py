"""Table builders for the hotel collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.hotel.tables.cancellation_notes import build_cancellation_notes
from potato_tornado.collections.hotel.tables.demand_forecast import build_demand_forecast
from potato_tornado.collections.hotel.tables.properties import build_properties
from potato_tornado.collections.hotel.tables.reservations import build_reservations
from potato_tornado.collections.hotel.tables.room_types import build_room_types
from potato_tornado.collections.hotel.tables.room_upgrades import build_room_upgrades
from potato_tornado.collections.hotel.tables.service_orders import build_service_orders
from potato_tornado.collections.hotel.tables.stay_changes import build_stay_changes
from potato_tornado.collections.hotel.tables.stays import build_stays

__all__ = [
    "build_cancellation_notes",
    "build_demand_forecast",
    "build_properties",
    "build_reservations",
    "build_room_types",
    "build_room_upgrades",
    "build_service_orders",
    "build_stay_changes",
    "build_stays",
]
