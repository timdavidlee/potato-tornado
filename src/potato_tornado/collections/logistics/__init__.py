"""Collection: logistics — parcels through a carrier network.

Models parcels dispatched from fulfillment **warehouses** through a **carrier**
network, tracked by a stream of **scan events**, and measured against a promised
delivery date (the SLA). The first collection with a **per-entity event log**:
each shipment emits several ordered tracking scans, so the timeline must be
reconstructed from many rows per parent. It also carries a **promised-vs-actual
SLA** whose miss rate rises with shipping distance (``dest_zone``).

Tables
------
- ``carriers``     : the carrier catalog (dim), with base/per-kg rates and reliability.
- ``warehouses``   : origin fulfillment centers (dim), by city and region.
- ``shipments``    : one row per parcel dispatched — the plan (``promised_date``).
- ``scan_events``  : the tracking event log, several ordered rows per shipment.
- ``deliveries``   : the terminal outcome (the actual), 1:1 with ``shipments``,
                     recovered structurally from each shipment's terminal scan.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.logistics.tables import (
    build_carriers,
    build_deliveries,
    build_scan_events,
    build_shipments,
    build_warehouses,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="logistics",
        description="Parcels dispatched from fulfillment warehouses through a carrier network, "
        "tracked by a stream of scan events and measured against a promised delivery date: "
        "a per-shipment event log plus promised-vs-actual SLA performance.",
        tables=(
            TableSpec("carriers", build_carriers, description="Carrier catalog (dim)."),
            TableSpec("warehouses", build_warehouses, description="Origin fulfillment centers."),
            TableSpec(
                "shipments",
                build_shipments,
                depends_on=("warehouses", "carriers"),
                description="One parcel dispatched per row — the plan (promised date).",
            ),
            TableSpec(
                "scan_events",
                build_scan_events,
                depends_on=("shipments", "carriers", "warehouses"),
                description="Tracking event log: several ordered scans per shipment.",
            ),
            TableSpec(
                "deliveries",
                build_deliveries,
                depends_on=("shipments", "scan_events"),
                description="Terminal outcome (actual), 1:1 with shipments.",
            ),
        ),
    )


register("logistics", build)
