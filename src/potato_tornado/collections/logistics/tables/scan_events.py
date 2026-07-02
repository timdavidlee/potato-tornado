"""The ``scan_events`` table: the tracking event log (several rows per shipment).

Each shipment emits an ordered timeline of scans — the collection's variable-length
event stream. The happy path is
``picked_up -> in_transit -> out_for_delivery -> delivered``; far destinations add
extra ``in_transit`` hops, and a shipment that fails to arrive ends in an
``exception`` instead (a ``returned_to_sender`` reaches ``out_for_delivery`` first,
a ``lost`` never does). This module owns the outcome decision — terminal status and,
for delivered parcels, the on-time-vs-late call — and lays down monotonic
timestamps; ``deliveries`` reads the terminal row back so the two never disagree.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.logistics.constants import (
    SCAN_DELIVERED,
    SCAN_EXCEPTION,
    SCAN_IN_TRANSIT,
    SCAN_OUT_FOR_DELIVERY,
    SCAN_PICKED_UP,
    TERMINAL_STATUS,
    TERMINAL_STATUS_WEIGHTS,
)
from potato_tornado.core.collection import GenContext

# On-time propensity blends carrier reliability with a per-zone penalty: a small
# bonus lifts near-zone parcels to ~0.95 on-time, a linear zone slope drags far
# ones down to ~0.78, keeping the overall rate ~0.88. See scenario 1.
_ONTIME_BONUS = 0.03
_ONTIME_ZONE_SLOPE = 0.024

# Scans fall between the pickup morning and the terminal evening.
_PICKUP_HOUR = 8
_TERMINAL_HOUR = 18


def _extra_hops(zone: int) -> int:
    """Extra ``in_transit`` hops for farther destinations (0 near, up to 2 far)."""
    if zone < 5:
        return 0
    return 1 if zone < 7 else 2


def _journey(status: str, zone: int) -> list[str]:
    """The ordered scan ladder for a shipment given its outcome and distance."""
    scans = [SCAN_PICKED_UP, *([SCAN_IN_TRANSIT] * (1 + _extra_hops(zone)))]
    if status == "delivered":
        return [*scans, SCAN_OUT_FOR_DELIVERY, SCAN_DELIVERED]
    if status == "returned_to_sender":
        return [*scans, SCAN_OUT_FOR_DELIVERY, SCAN_EXCEPTION]
    return [*scans, SCAN_EXCEPTION]  # lost: never reaches out_for_delivery


def build_scan_events(ctx: GenContext) -> pl.DataFrame:
    ships = ctx.table("shipments")
    carriers = ctx.table("carriers")
    warehouses = ctx.table("warehouses")
    reliability_of = dict(
        zip(carriers["carrier_id"].to_list(), carriers["reliability"].to_list(), strict=True)
    )
    city_of_wh = dict(
        zip(warehouses["warehouse_id"].to_list(), warehouses["city"].to_list(), strict=True)
    )

    shipment_id = ships["shipment_id"].to_list()
    ship_date = ships["ship_date"].to_list()
    promised_date = ships["promised_date"].to_list()
    zone = ships["dest_zone"].to_list()
    carrier = ships["carrier_id"].to_list()
    warehouse = ships["warehouse_id"].to_list()
    dest_city = ships["dest_city"].to_list()
    n = len(shipment_id)

    status = ctx.rng.child("status").numpy.choice(
        TERMINAL_STATUS, size=n, p=TERMINAL_STATUS_WEIGHTS
    )
    reliability = np.array([reliability_of[c] for c in carrier])
    p_ontime = np.clip(
        reliability + _ONTIME_BONUS - _ONTIME_ZONE_SLOPE * (np.array(zone) - 1), 0.5, 0.99
    )
    is_ontime = ctx.rng.child("ontime").numpy.random(n) < p_ontime
    early_days = ctx.rng.child("early").numpy.poisson(0.5, n)
    late_days = np.clip(1 + ctx.rng.child("late").numpy.poisson(1.6, n), 1, 7)
    hub_city = ctx.entities.cities(n)
    ts_rng = ctx.rng.child("scan_ts").numpy

    scan_ids: list[str] = []
    out_shipment: list[str] = []
    out_seq: list[int] = []
    out_type: list[str] = []
    out_ts: list[datetime] = []
    out_city: list[str] = []
    scan_no = 0
    for i in range(n):
        scans = _journey(str(status[i]), int(zone[i]))
        if status[i] == "delivered":
            delta = -int(early_days[i]) if is_ontime[i] else int(late_days[i])
            terminal_date = max(ship_date[i], promised_date[i] + timedelta(days=delta))
        else:
            terminal_date = promised_date[i]

        start = datetime.combine(ship_date[i], time(_PICKUP_HOUR))
        end = datetime.combine(terminal_date, time(_TERMINAL_HOUR))
        gap = (end - start).total_seconds() / len(scans)
        for seq, scan_type in enumerate(scans, start=1):
            if seq == len(scans):
                ts = end
            else:
                ts = start + timedelta(seconds=gap * (seq - 1 + float(ts_rng.random()) * 0.9))
            if scan_type == SCAN_PICKED_UP:
                loc = city_of_wh[warehouse[i]]
            elif scan_type == SCAN_IN_TRANSIT:
                loc = hub_city[i]
            else:
                loc = dest_city[i]
            scan_no += 1
            scan_ids.append(f"SCN-{scan_no:08d}")
            out_shipment.append(shipment_id[i])
            out_seq.append(seq)
            out_type.append(scan_type)
            out_ts.append(ts)
            out_city.append(loc)

    return pl.DataFrame(
        {
            "scan_id": scan_ids,
            "shipment_id": out_shipment,
            "seq": out_seq,
            "scan_type": out_type,
            "scan_ts": pl.Series(out_ts, dtype=pl.Datetime),
            "location_city": out_city,
        }
    )
