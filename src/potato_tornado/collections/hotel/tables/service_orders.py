"""The ``service_orders`` table: ancillary service-book purchases per stay."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.collections.hotel.constants import SERVICES
from potato_tornado.core.collection import GenContext


def build_service_orders(ctx: GenContext) -> pl.DataFrame:
    stays = ctx.table("stays")
    service_names = [s[0] for s in SERVICES]
    service_price = dict(SERVICES)
    rng = ctx.rng.numpy

    rows_stay: list[str] = []
    rows_prop: list[str] = []
    rows_service: list[str] = []
    rows_date: list[object] = []
    rows_qty: list[int] = []
    rows_amount: list[float] = []
    for stay_id, pid, ci, nights in zip(
        stays["stay_id"].to_list(),
        stays["property_id"].to_list(),
        stays["actual_check_in"].to_list(),
        stays["actual_nights"].to_list(),
        strict=True,
    ):
        # Longer stays accrue more service-book entries.
        count = int(rng.poisson(0.9 * nights))
        for _ in range(count):
            service = str(rng.choice(service_names))
            qty = int(rng.integers(1, 3))
            day_offset = int(rng.integers(0, max(1, nights)))
            rows_stay.append(stay_id)
            rows_prop.append(pid)
            rows_service.append(service)
            rows_date.append(ci + timedelta(days=day_offset))
            rows_qty.append(qty)
            rows_amount.append(round(service_price[service] * qty, 2))

    n = len(rows_stay)
    return pl.DataFrame(
        {
            "service_order_id": [f"SVC-{i:07d}" for i in range(1, n + 1)],
            "stay_id": rows_stay,
            "property_id": rows_prop,
            "service": rows_service,
            "service_date": rows_date,
            "quantity": rows_qty,
            "amount": rows_amount,
        }
    )
