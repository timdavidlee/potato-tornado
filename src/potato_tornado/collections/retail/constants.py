"""Domain reference data (catalogs) for the retail collection.

The fixed "seed" facts the generators draw from: the product-category ladder (price
level + category return propensity) and the return-reason catalogue. Each literal
here is read by two or more tables, so it is the single source of truth; single-table
literals (channel list, segment weights, per-category reason mix) stay inline in the
module that uses them. See ``scenarios/`` for the signals these values are tuned to
produce.
"""

from __future__ import annotations

# (category, price_median, base_return_rate, weight) — the product-category ladder.
# `price_median` seeds `unit_price` in `products`; `base_return_rate` is the
# per-line return propensity `returns` applies (apparel returns ~10x as often as
# consumables — the headline category signal); `weight` is the catalogue mix. Read
# by `products` and `returns`; referenced by scenarios.
CATEGORIES = [
    ("apparel", 22.0, 0.22, 0.34),
    ("electronics", 55.0, 0.10, 0.18),
    ("home", 26.0, 0.06, 0.26),
    ("consumables", 8.0, 0.02, 0.22),
]

# The return-reason catalogue. The per-category *mix* over these reasons lives inline
# in `returns` (single-table), but the reason names are shared with the realism /
# scenario docs, so they are the single source of truth here.
RETURN_REASONS = [
    "changed_mind",
    "too_small",
    "defective",
    "not_as_described",
    "damaged_in_transit",
]
