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
- ``service_orders``  : ancillary purchases and stay fees (dining, room service,
                        internet, parking, ...).
- ``room_upgrades``   : mid-stay room-class upgrades sold as a discounted upsell.
- ``stay_changes``    : stay-length amendments (early checkout / night extension).
- ``demand_forecast`` : forecast vs. actual occupancy per property per day.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.hotel.tables import (
    build_demand_forecast,
    build_properties,
    build_reservations,
    build_room_types,
    build_room_upgrades,
    build_service_orders,
    build_stay_changes,
    build_stays,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="hotel",
        description="Hotel reservations, actual stays, service-book spend and "
        "daily demand forecast vs. realised occupancy.",
        tables=(
            TableSpec("properties", build_properties, description="Hotels in the group."),
            TableSpec(
                "room_types",
                build_room_types,
                depends_on=("properties",),
                description="Room categories and nightly rates.",
            ),
            TableSpec(
                "reservations",
                build_reservations,
                depends_on=("properties",),
                description="Bookings with lifecycle status.",
            ),
            TableSpec(
                "stays",
                build_stays,
                depends_on=("reservations", "room_types"),
                description="Realised check-in/out for honoured reservations.",
            ),
            TableSpec(
                "service_orders",
                build_service_orders,
                depends_on=("stays",),
                description="Ancillary service-book purchases and stay fees.",
            ),
            TableSpec(
                "room_upgrades",
                build_room_upgrades,
                depends_on=("stays", "room_types"),
                description="Mid-stay room-class upgrades sold as an upsell.",
            ),
            TableSpec(
                "stay_changes",
                build_stay_changes,
                depends_on=("stays", "reservations"),
                description="Stay-length amendments: early checkouts and extensions.",
            ),
            TableSpec(
                "demand_forecast",
                build_demand_forecast,
                depends_on=("properties", "stays"),
                description="Forecast vs. actual occupancy per day.",
            ),
        ),
    )


register("hotel", build)
