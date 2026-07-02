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

# (service, unit_price, popularity_weight) — the ancillary "service-book" menu billed per
# stay via service_orders. A mix of discretionary spend (Dining, Spa, Room Service) and the
# recurring stay fees a guest gets charged (Internet, Television, Parking). Demand is not
# uniform across the menu: breakfast / internet / parking are everyday buys, spa / laundry
# are occasional. Weights sum to 1.0.
SERVICES = [
    ("Breakfast", 18.0, 0.20),
    ("Spa", 75.0, 0.04),
    ("Dining", 55.0, 0.11),
    ("Room Service", 32.0, 0.12),
    ("Parking", 22.0, 0.14),
    ("Internet", 12.0, 0.16),
    ("Television", 9.0, 0.08),
    ("Minibar", 14.0, 0.10),
    ("Laundry", 20.0, 0.05),
]

RES_STATUS = ["honoured", "cancelled", "no_show"]

# Reservation status keyed by booking channel. Overall the mix still lands at
# ~0.82 honoured / 0.14 cancelled / 0.04 no_show, but the drop-off (cancel +
# no_show) concentrates in the OTA and nearly vanishes for walk_in — a walk-in
# guest is already on-site, so can't meaningfully cancel or no-show. Rows are in
# RES_STATUS order and each sums to 1.0.
RES_STATUS_BY_CHANNEL = {
    "direct": [0.88, 0.09, 0.03],
    "ota": [0.73, 0.21, 0.06],
    "corporate": [0.85, 0.12, 0.03],
    "walk_in": [0.98, 0.02, 0.00],
}

CHANNELS = ["direct", "ota", "corporate", "walk_in"]

# Booking lead time keyed by channel: (lognormal median days, sigma). The overall
# gap is right-skewed with median ≈14 days, but the shape differs by channel — OTA
# leisure books far ahead with a fat tail, walk_in is same-/next-day, corporate and
# direct sit in between. Larger sigma = fatter right tail.
LEAD_TIME_BY_CHANNEL = {
    "direct": (12.0, 0.85),
    "ota": (24.0, 1.0),
    "corporate": (8.0, 0.8),
    "walk_in": (1.0, 0.6),
}

# Share of eligible stays that take a room upgrade, keyed by the booking channel.
# Overall lands ≈15%, but the upsell concentrates in direct-booking guests (a
# loyalty / front-desk relationship the hotel can work) and is weakest for the
# transactional OTA. Penthouse stays are never eligible (already at the top).
UPGRADE_RATE_BY_CHANNEL = {
    "direct": 0.25,
    "ota": 0.08,
    "corporate": 0.14,
    "walk_in": 0.15,
}
