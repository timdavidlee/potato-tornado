"""Collection: hotel reservations, actual attendance, service books and forecast.

Models the booking-to-stay lifecycle for a small hotel group: reservations that
may cancel or no-show, the stays that actually happen, ancillary service spend
(the "service book"), and a daily demand forecast to compare against realised
occupancy.

Tables
------
- ``properties``      : hotels in the group.
- ``room_types``      : room categories and nightly rates per property.
- ``reservations``    : bookings, with status (honoured / cancelled / no_show).
- ``stays``           : realised check-in / check-out for honoured reservations.
- ``service_orders``  : ancillary purchases during a stay (spa, dining, ...).
- ``demand_forecast`` : forecast vs. actual occupancy per property per day.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import Collection, GenContext, TableSpec
from potato_tornado.core.registry import register

_CITIES = ["Lisbon", "Porto", "Madrid", "Seville", "Lyon", "Turin"]
_ROOM_TYPES = [
    ("Standard", 95.0, 0.55),
    ("Deluxe", 145.0, 0.28),
    ("Suite", 260.0, 0.12),
    ("Penthouse", 480.0, 0.05),
]
_SERVICES = [
    ("Breakfast", 18.0),
    ("Spa", 75.0),
    ("Dining", 55.0),
    ("Parking", 22.0),
    ("Minibar", 14.0),
    ("Laundry", 20.0),
]
_RES_STATUS = ["honoured", "cancelled", "no_show"]
_RES_STATUS_WEIGHTS = [0.82, 0.14, 0.04]
_CHANNELS = ["direct", "ota", "corporate", "walk_in"]
_CHANNEL_WEIGHTS = [0.34, 0.44, 0.16, 0.06]


def _build_properties(ctx: GenContext) -> pl.DataFrame:
    n = min(ctx.n(6), len(_CITIES))
    cities = _CITIES[:n]
    # Name each property "<surname> <city>", the surname taken from an entity.
    surnames = [name.split()[-1] for name in ctx.entities.people(n)["full_name"].to_list()]
    return pl.DataFrame(
        {
            "property_id": [f"HOT-{i:03d}" for i in range(1, n + 1)],
            "name": [f"{surname} {city}" for surname, city in zip(surnames, cities, strict=True)],
            "city": cities,
            "total_rooms": ctx.dist.integers(n, 60, 220),
        }
    )


def _build_room_types(ctx: GenContext) -> pl.DataFrame:
    props = ctx.table("properties")
    prop_ids = props["property_id"].to_list()
    rows_prop: list[str] = []
    rows_type: list[str] = []
    rows_rate: list[float] = []
    rng = ctx.rng.numpy
    for pid in prop_ids:
        loc_mult = float(rng.normal(1.0, 0.12))
        for type_name, base_rate, _ in _ROOM_TYPES:
            rows_prop.append(pid)
            rows_type.append(type_name)
            rows_rate.append(round(base_rate * max(0.7, loc_mult), 2))
    return pl.DataFrame(
        {
            "room_type_id": [f"RT-{i:04d}" for i in range(1, len(rows_prop) + 1)],
            "property_id": rows_prop,
            "room_type": rows_type,
            "nightly_rate": rows_rate,
        }
    )


def _build_reservations(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(3000)
    props = ctx.table("properties")["property_id"].to_list()
    type_names = [t[0] for t in _ROOM_TYPES]
    type_weights = [t[2] for t in _ROOM_TYPES]

    booked = ctx.dist.dates_between(n, ctx.config.start_date, ctx.config.end_date)
    lead_days = np.clip(ctx.dist.lognormal(n, median=14, sigma=0.9), 0, 240).astype(int)
    nights = np.clip(ctx.dist.poisson(n, 2.2) + 1, 1, 21)
    check_in = np.array(
        [b + timedelta(days=int(lead)) for b, lead in zip(booked, lead_days, strict=True)],
        dtype=object,
    )
    check_out = np.array(
        [ci + timedelta(days=int(nt)) for ci, nt in zip(check_in, nights, strict=True)],
        dtype=object,
    )

    return pl.DataFrame(
        {
            "reservation_id": [f"RES-{i:07d}" for i in range(1, n + 1)],
            "property_id": ctx.dist.choice(n, props),
            "guest_name": ctx.entities.people(n)["full_name"],
            "channel": ctx.dist.choice(n, _CHANNELS, _CHANNEL_WEIGHTS),
            "room_type": ctx.dist.choice(n, type_names, type_weights),
            "booked_date": booked,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "party_size": np.clip(ctx.dist.poisson(n, 1.3) + 1, 1, 6),
            "nights": nights,
            "status": ctx.dist.choice(n, _RES_STATUS, _RES_STATUS_WEIGHTS),
        }
    )


def _build_stays(ctx: GenContext) -> pl.DataFrame:
    res = ctx.table("reservations")
    honoured = res.filter(pl.col("status") == "honoured")
    room_rates = _rate_lookup(ctx.table("room_types"))

    n = honoured.height
    prop_ids = honoured["property_id"].to_list()
    room_types = honoured["room_type"].to_list()
    nights = honoured["nights"].to_list()

    # Actual attendance drifts slightly from the booking (early/late checkout).
    night_delta = ctx.dist.integers(n, -1, 1)
    actual_nights = [max(1, nt + int(d)) for nt, d in zip(nights, night_delta, strict=True)]
    rates = [room_rates.get((p, t), 100.0) for p, t in zip(prop_ids, room_types, strict=True)]
    room_revenue = [round(r * nt, 2) for r, nt in zip(rates, actual_nights, strict=True)]

    check_in = honoured["check_in_date"].to_list()
    check_out = [ci + timedelta(days=nt) for ci, nt in zip(check_in, actual_nights, strict=True)]

    return pl.DataFrame(
        {
            "stay_id": [f"STY-{i:07d}" for i in range(1, n + 1)],
            "reservation_id": honoured["reservation_id"],
            "property_id": honoured["property_id"],
            "room_type": honoured["room_type"],
            "actual_check_in": check_in,
            "actual_check_out": check_out,
            "actual_nights": actual_nights,
            "nightly_rate": rates,
            "room_revenue": room_revenue,
        }
    )


def _build_service_orders(ctx: GenContext) -> pl.DataFrame:
    stays = ctx.table("stays")
    service_names = [s[0] for s in _SERVICES]
    service_price = dict(_SERVICES)
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


def _build_demand_forecast(ctx: GenContext) -> pl.DataFrame:
    props = ctx.table("properties")
    stays = ctx.table("stays")

    # Actual occupied room-nights per property per date, derived from stays.
    occupancy = _occupancy_by_day(stays)

    rows_prop: list[str] = []
    rows_date: list[object] = []
    rows_actual: list[int] = []
    rows_forecast: list[int] = []
    rng = ctx.rng.numpy
    span = ctx.config.span_days
    for pid, total_rooms in zip(
        props["property_id"].to_list(), props["total_rooms"].to_list(), strict=True
    ):
        for offset in range(span):
            day = ctx.config.start_date + timedelta(days=offset)
            actual = occupancy.get((pid, day), 0)
            actual = min(actual, total_rooms)
            # Forecast is the actual perturbed by noise (imperfect foresight).
            forecast = int(np.clip(round(actual * rng.normal(1.0, 0.12)), 0, total_rooms))
            rows_prop.append(pid)
            rows_date.append(day)
            rows_actual.append(actual)
            rows_forecast.append(forecast)

    return pl.DataFrame(
        {
            "property_id": rows_prop,
            "forecast_date": rows_date,
            "forecast_occupied_rooms": rows_forecast,
            "actual_occupied_rooms": rows_actual,
        }
    )


def _rate_lookup(room_types: pl.DataFrame) -> dict[tuple[str, str], float]:
    return {
        (p, t): r
        for p, t, r in zip(
            room_types["property_id"].to_list(),
            room_types["room_type"].to_list(),
            room_types["nightly_rate"].to_list(),
            strict=True,
        )
    }


def _occupancy_by_day(stays: pl.DataFrame) -> dict[tuple[str, object], int]:
    occupancy: dict[tuple[str, object], int] = {}
    for pid, ci, nights in zip(
        stays["property_id"].to_list(),
        stays["actual_check_in"].to_list(),
        stays["actual_nights"].to_list(),
        strict=True,
    ):
        for offset in range(int(nights)):
            key = (pid, ci + timedelta(days=offset))
            occupancy[key] = occupancy.get(key, 0) + 1
    return occupancy


def build() -> Collection:
    return Collection(
        name="hotel",
        description="Hotel reservations, actual stays, service-book spend and "
        "daily demand forecast vs. realised occupancy.",
        tables=(
            TableSpec("properties", _build_properties, description="Hotels in the group."),
            TableSpec(
                "room_types",
                _build_room_types,
                depends_on=("properties",),
                description="Room categories and nightly rates.",
            ),
            TableSpec(
                "reservations",
                _build_reservations,
                depends_on=("properties",),
                description="Bookings with lifecycle status.",
            ),
            TableSpec(
                "stays",
                _build_stays,
                depends_on=("reservations", "room_types"),
                description="Realised check-in/out for honoured reservations.",
            ),
            TableSpec(
                "service_orders",
                _build_service_orders,
                depends_on=("stays",),
                description="Ancillary service-book purchases.",
            ),
            TableSpec(
                "demand_forecast",
                _build_demand_forecast,
                depends_on=("properties", "stays"),
                description="Forecast vs. actual occupancy per day.",
            ),
        ),
    )


register("hotel", build)
