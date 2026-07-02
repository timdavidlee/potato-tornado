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

# City → (country, region) rollup so analytics can group above the city level. Region
# groups countries into a market area (Iberia vs. the rest of Western Europe), giving a
# two-level geographic hierarchy city → country → region.
CITY_GEO = {
    "Lisbon": ("Portugal", "Iberia"),
    "Porto": ("Portugal", "Iberia"),
    "Madrid": ("Spain", "Iberia"),
    "Seville": ("Spain", "Iberia"),
    "Lyon": ("France", "Western Europe"),
    "Turin": ("Italy", "Western Europe"),
}

# Tax wedge on a stay: reduced-rate accommodation VAT (a fraction of room revenue, keyed to
# the property's country) plus a flat per-room-night city tourist tax (keyed to city). A
# stay's taxes_fees = room_revenue * VAT + actual_nights * city_tax; room_revenue itself stays
# net of tax, so ADR / RevPAR (net-of-tax by convention) read straight off room_revenue and
# the wedge is a separate column. Portugal's reduced VAT (6%) sits below the 10% of
# Spain/France/Italy, and Spanish cities levy no tourist tax, so the effective tax load is
# lightest across Iberia -- see scenarios/tax-load-lighter-in-iberia.md.
VAT_RATE_BY_COUNTRY = {
    "Portugal": 0.06,
    "Spain": 0.10,
    "France": 0.10,
    "Italy": 0.10,
}
CITY_TAX_PER_NIGHT = {
    "Lisbon": 2.0,
    "Porto": 2.0,
    "Madrid": 0.0,
    "Seville": 0.0,
    "Lyon": 1.5,
    "Turin": 1.4,
}

# Per-property star rating (3-5 stars), weighted toward the 4-star mid-market. Drawn
# independently of nightly rate -- see the "star_rating is independent of rate" note in
# realism-guidance.md (a candidate scenario, deliberately not wired here).
STAR_RATINGS = [3, 4, 5]
STAR_RATING_WEIGHTS = [0.33, 0.50, 0.17]

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

# Per-class share of a property's physical room inventory (each property's total_rooms is
# apportioned across the four classes by these weights, largest-remainder, min 1 each). This
# mix is deliberately *more* top-heavy than the booking mix in ROOM_TYPES (Standard 0.55 →
# Penthouse 0.05): the group built proportionally more suites/penthouses than demand fills, so
# occupancy per class runs the opposite way to the ladder -- Standards run hottest, premium
# rooms coolest. Weights sum to 1.0. See scenarios/premium-rooms-run-cooler.md.
INVENTORY_WEIGHT_BY_TYPE = {"Standard": 0.50, "Deluxe": 0.27, "Suite": 0.15, "Penthouse": 0.08}

# Rated capacity per room class, ascending with the ladder. Ties room_types to party_size:
# a party may still exceed the room's max (an over-occupancy / upsell hook — see
# realism-guidance.md), so this is a slice-and-check field, not a hard cap on party_size.
MAX_OCCUPANCY_BY_TYPE = {"Standard": 2, "Deluxe": 3, "Suite": 4, "Penthouse": 6}

# (service, unit_price, popularity_weight, category) — the ancillary "service-book" menu
# billed per stay via service_orders. A mix of discretionary spend (Dining, Spa, Room
# Service) and the recurring stay fees a guest gets charged (Internet, Television, Parking).
# Demand is not uniform across the menu: breakfast / internet / parking are everyday buys,
# spa / laundry are occasional. Weights sum to 1.0. ``category`` rolls the nine services up
# into the four reporting groups in COST_FRACTION_BY_CATEGORY.
SERVICES = [
    ("Breakfast", 18.0, 0.20, "F&B"),
    ("Spa", 75.0, 0.04, "Wellness"),
    ("Dining", 55.0, 0.11, "F&B"),
    ("Room Service", 32.0, 0.12, "F&B"),
    ("Parking", 22.0, 0.14, "Parking"),
    ("Internet", 12.0, 0.16, "Connectivity"),
    ("Television", 9.0, 0.08, "Connectivity"),
    ("Minibar", 14.0, 0.10, "F&B"),
    ("Laundry", 20.0, 0.05, "Wellness"),
]

# Variable cost as a fraction of unit_price, by service category. F&B carries the highest
# cost of goods, connectivity almost none — so gross margin varies by category. A per-line
# jitter around this fraction (see service_orders) keeps unit_cost from being a constant
# ratio of price. Fractions stay well below 1.0, so every line keeps a positive margin.
COST_FRACTION_BY_CATEGORY = {
    "F&B": 0.34,
    "Wellness": 0.22,
    "Connectivity": 0.06,
    "Parking": 0.12,
}

RES_STATUS = ["honoured", "cancelled", "no_show"]

# Cancellation timing as a fraction of the booking window (0 = cancelled at booking, 1 = at
# check-in), drawn Beta(a, b) keyed by rate plan. Flexible BAR guests cancel late (fraction
# skews toward 1, close to arrival); non-refundable Advance-Purchase cancels early (fraction
# skews toward 0) -- so measured as days *before arrival*, non-refundable cancellations lead
# by more. Only 'cancelled' bookings get a cancellation_date; 'no_show' and 'honoured' are
# null (a no-show never cancels, it just fails to arrive). See
# scenarios/cancellations-land-late-for-flexible-rates.md.
CANCEL_WINDOW_BETA_BY_PLAN = {
    "BAR": (2.5, 1.2),
    "Advance-Purchase": (1.2, 3.0),
    "Corporate-negotiated": (2.0, 2.0),
    "Package": (1.8, 1.8),
}

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

# Rate plan -- the revenue-management axis, orthogonal to channel. BAR is the flexible
# refundable rate, Advance-Purchase is discounted but non-refundable, Corporate-negotiated
# is the contracted corporate rate, Package bundles extras (breakfast, parking). Keyed to
# channel: corporate books the negotiated rate, walk_in pays the flexible BAR, the OTA leans
# on the discounted non-refundable rate. Rows are in RATE_PLANS order and each sums to 1.0.
RATE_PLANS = ["BAR", "Advance-Purchase", "Corporate-negotiated", "Package"]
RATE_PLAN_BY_CHANNEL = {
    "direct": [0.40, 0.30, 0.05, 0.25],
    "ota": [0.38, 0.40, 0.02, 0.20],
    "corporate": [0.14, 0.06, 0.75, 0.05],
    "walk_in": [0.78, 0.05, 0.07, 0.10],
}

# How each rate plan scales a booking's baseline drop-off (cancel + no_show) mass from
# RES_STATUS_BY_CHANNEL: non-refundable Advance-Purchase bookings cancel far less, flexible
# BAR bookings a bit more. This is what makes cancellation depend on the rate plan, not just
# the channel -- see scenarios/non-refundable-rates-cancel-less.md. The per-channel drop-off
# ordering (ota > corporate > direct > walk_in) survives because the multiplier rides on top
# of the channel base.
RATE_PLAN_CANCEL_MULT = {
    "BAR": 1.3,
    "Advance-Purchase": 0.3,
    "Corporate-negotiated": 0.9,
    "Package": 0.8,
}

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

# Market segment — the demand-side axis, orthogonal to the booking channel. Keyed to
# channel: the corporate channel is overwhelmingly business travel, the OTA is leisure,
# direct/walk_in sit in between; group business is a small slice everywhere. Rows are in
# MARKET_SEGMENTS order and each sums to 1.0.
MARKET_SEGMENTS = ["leisure", "business", "group"]
SEGMENT_BY_CHANNEL = {
    "direct": [0.62, 0.25, 0.13],
    "ota": [0.80, 0.10, 0.10],
    "corporate": [0.15, 0.78, 0.07],
    "walk_in": [0.70, 0.22, 0.08],
}

# Children per party (Poisson mean) by market segment, then capped at ``party_size - 1`` so
# every party keeps at least one adult. Business travel is almost childless; leisure and
# group carry families. ``adults = party_size - children``.
CHILDREN_LAMBDA_BY_SEGMENT = {"leisure": 0.6, "business": 0.05, "group": 0.35}

# Guest origin. A guest is domestic (carries the property's own country) with probability
# DOMESTIC_SHARE; otherwise they come from one of these international feeder markets,
# weighted by booking share. Weights need not sum to 1.0 (normalized at draw time).
DOMESTIC_SHARE = 0.58
GUEST_SOURCE_COUNTRIES = [
    ("United Kingdom", 0.26),
    ("Germany", 0.20),
    ("France", 0.14),
    ("United States", 0.12),
    ("Spain", 0.10),
    ("Italy", 0.08),
    ("Netherlands", 0.06),
    ("Brazil", 0.04),
]

# Settlement method for a stay, keyed to the booking channel: corporate bookings settle
# largely on accounts-receivable (bill-back), walk_in carries the most cash, the OTA is
# almost entirely card. Rows are in PAYMENT_METHODS order and each sums to 1.0.
PAYMENT_METHODS = ["card", "cash", "corporate_ar"]
PAYMENT_BY_CHANNEL = {
    "direct": [0.82, 0.15, 0.03],
    "ota": [0.93, 0.05, 0.02],
    "corporate": [0.28, 0.04, 0.68],
    "walk_in": [0.70, 0.28, 0.02],
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
