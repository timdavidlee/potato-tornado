"""Domain reference data (catalogs) for the hotel collection.

The fixed "seed" facts the generators draw from — cities, the room-type ladder
(name, base nightly rate, popularity weight), the ancillary service menu, and the
reservation status / booking channel mixes. Kept here so the ``tables/`` modules
stay focused on generation logic and share one source of truth (``ROOM_TYPES`` in
particular feeds both ``room_types`` and ``reservations``). See ``scenarios/`` for
the signals these values are tuned to produce.
"""

from __future__ import annotations

CITIES = ["Lisbon", "Porto", "Madrid", "Seville", "Lyon", "Turin"]

# Property naming: a single group brand plus a per-property descriptor and the city,
# e.g. "Meridian Grand Lisbon". The group is one chain, so the brand is shared and
# each property gets a distinct descriptor.
HOTEL_BRAND = "Meridian"
HOTEL_DESCRIPTORS = [
    "Grand",
    "Royal",
    "Park",
    "Plaza",
    "Palace",
    "Regency",
    "Continental",
    "Metropole",
    "Bristol",
    "Imperial",
]

# (room_type, base_nightly_rate, booking_weight)
ROOM_TYPES = [
    ("Standard", 95.0, 0.55),
    ("Deluxe", 145.0, 0.28),
    ("Suite", 260.0, 0.12),
    ("Penthouse", 480.0, 0.05),
]

# (service, unit_price) — the ancillary "service-book" menu billed per stay via
# service_orders. A mix of discretionary spend (Dining, Spa, Room Service) and the
# recurring stay fees a guest gets charged (Internet, Television, Parking).
SERVICES = [
    ("Breakfast", 18.0),
    ("Spa", 75.0),
    ("Dining", 55.0),
    ("Room Service", 32.0),
    ("Parking", 22.0),
    ("Internet", 12.0),
    ("Television", 9.0),
    ("Minibar", 14.0),
    ("Laundry", 20.0),
]

RES_STATUS = ["honoured", "cancelled", "no_show"]
RES_STATUS_WEIGHTS = [0.82, 0.14, 0.04]

CHANNELS = ["direct", "ota", "corporate", "walk_in"]
CHANNEL_WEIGHTS = [0.34, 0.44, 0.16, 0.06]
