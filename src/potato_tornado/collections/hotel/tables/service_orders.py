"""The ``service_orders`` table: ancillary service-book purchases per stay."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.collections.hotel.constants import COST_FRACTION_BY_CATEGORY, SERVICES
from potato_tornado.core.collection import GenContext


def build_service_orders(ctx: GenContext) -> pl.DataFrame:
    stays = ctx.table("stays")
    service_names = [s[0] for s in SERVICES]
    service_price = {name: price for name, price, _, _ in SERVICES}
    service_category = {name: cat for name, _, _, cat in SERVICES}
    service_weights = [w for _, _, w, _ in SERVICES]
    rng = ctx.rng.numpy
    # unit_cost draws from its own child stream so adding margins doesn't shift the
    # service / quantity / date draws above.
    cost_rng = ctx.rng.child("unit_cost").numpy

    rows_stay: list[str] = []
    rows_prop: list[str] = []
    rows_service: list[str] = []
    rows_category: list[str] = []
    rows_date: list[object] = []
    rows_qty: list[int] = []
    rows_amount: list[float] = []
    rows_unit_cost: list[float] = []
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
            service = str(rng.choice(service_names, p=service_weights))
            category = service_category[service]
            # Most lines are a single unit; a minority are 2, rarely 3 — right-skewed,
            # not a flat 1-or-2 coin flip.
            qty = int(rng.choice([1, 2, 3], p=[0.7, 0.24, 0.06]))
            day_offset = int(rng.integers(0, max(1, nights)))
            # unit_cost = price x category cost-fraction x per-line jitter, so margin
            # varies by category and line rather than being a constant ratio of price.
            jitter = min(1.8, max(0.4, float(cost_rng.normal(1.0, 0.1))))
            unit_cost = round(
                service_price[service] * COST_FRACTION_BY_CATEGORY[category] * jitter, 2
            )
            rows_stay.append(stay_id)
            rows_prop.append(pid)
            rows_service.append(service)
            rows_category.append(category)
            rows_date.append(ci + timedelta(days=day_offset))
            rows_qty.append(qty)
            rows_amount.append(round(service_price[service] * qty, 2))
            rows_unit_cost.append(unit_cost)

    n = len(rows_stay)
    return pl.DataFrame(
        {
            "service_order_id": [f"SVC-{i:07d}" for i in range(1, n + 1)],
            "stay_id": rows_stay,
            "property_id": rows_prop,
            "service": rows_service,
            "service_category": rows_category,
            "service_date": rows_date,
            "quantity": rows_qty,
            "unit_cost": rows_unit_cost,
            "amount": rows_amount,
        }
    )
