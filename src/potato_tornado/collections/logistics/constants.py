"""Domain reference data (catalogs) for the logistics collection.

The fixed "seed" facts the generators draw from: the carrier catalogue, the
service-level ladder (promised transit + price multiplier), and the ordered scan
ladder that every shipment's tracking timeline follows. Each literal here is read
by two or more tables, so it is the single source of truth; single-table literals
(region list, zone bounds, zone fee) stay inline in the module that uses them. See
``scenarios/`` for the signals these values are tuned to produce.
"""

from __future__ import annotations

# (carrier_name, base_rate, per_kg_rate, reliability) — the carrier catalogue.
# `base_rate` / `per_kg_rate` feed the `shipments` cost identity; `reliability`
# (on-time propensity, ~0.85-0.97) is read via the built `carriers` table by
# `scan_events` to set each shipment's on-time chance. Single source of truth for
# the `carriers` dim.
CARRIERS = [
    ("Summit Courier", 4.00, 1.10, 0.97),
    ("Pony Express Freight", 3.50, 0.90, 0.95),
    ("BlueDart Logistics", 3.00, 0.85, 0.92),
    ("Meridian Parcel", 2.75, 0.80, 0.89),
    ("Coyote Ground", 2.25, 0.70, 0.85),
]

# (name, promised_transit_days, price_multiplier, weight) — the service ladder.
# Read by `shipments` (promised date + cost multiplier) and `scan_events` (the
# late tail scales with the promised window). Faster tiers cost more and are rarer.
SERVICE_LEVELS = [
    ("ground", 5, 1.0, 0.70),
    ("express", 2, 1.6, 0.22),
    ("overnight", 1, 2.5, 0.08),
]

# The ordered happy-path scan ladder. A shipment that fails to deliver ends its
# timeline in `SCAN_EXCEPTION` instead of `delivered`; a `returned_to_sender`
# reaches `out_for_delivery` first, a `lost` never does — that structural
# difference is how `deliveries` recovers the terminal status. Shared by
# `scan_events` (timeline build) and `deliveries` (terminal read).
SCAN_PICKED_UP = "picked_up"
SCAN_IN_TRANSIT = "in_transit"
SCAN_OUT_FOR_DELIVERY = "out_for_delivery"
SCAN_DELIVERED = "delivered"
SCAN_EXCEPTION = "exception"
SCAN_HAPPY_PATH = [SCAN_PICKED_UP, SCAN_IN_TRANSIT, SCAN_OUT_FOR_DELIVERY, SCAN_DELIVERED]

# Terminal outcome mix, decided in `scan_events` (shapes the journey) and recovered
# structurally in `deliveries`. Most parcels arrive; a thin tail is returned or lost.
TERMINAL_STATUS = ["delivered", "returned_to_sender", "lost"]
TERMINAL_STATUS_WEIGHTS = [0.965, 0.025, 0.010]
