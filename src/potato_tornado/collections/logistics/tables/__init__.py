"""Table builders for the logistics collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.logistics.tables.carrier_policies import build_carrier_policies
from potato_tornado.collections.logistics.tables.carriers import build_carriers
from potato_tornado.collections.logistics.tables.deliveries import build_deliveries
from potato_tornado.collections.logistics.tables.scan_events import build_scan_events
from potato_tornado.collections.logistics.tables.shipments import build_shipments
from potato_tornado.collections.logistics.tables.warehouses import build_warehouses

__all__ = [
    "build_carrier_policies",
    "build_carriers",
    "build_deliveries",
    "build_scan_events",
    "build_shipments",
    "build_warehouses",
]
