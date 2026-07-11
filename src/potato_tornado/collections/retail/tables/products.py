"""The ``products`` table: the catalog dimension.

Each product sits in a category and carries a right-skewed ``unit_price`` whose
median shifts by category (electronics dear, consumables cheap). Names are synthetic
``adjective + qualifier + category-noun`` triples — a label for joins, not a real SKU
master, but the qualifier widens the name space enough that duplicates are rare. Each
product also carries a ``brand`` (drawn from a per-category house catalog) and a
lognormal ``weight_kg`` (a shipping-cost covariate), both category-keyed. ``cost`` is
``unit_price x (1 - margin)`` with a **flat** (category-independent) ~0.45 margin, so
``0 < cost < unit_price`` always; a per-category margin gradient is a deferred scenario.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.retail.constants import CATEGORIES
from potato_tornado.core.collection import GenContext

# Category assignment mix and the synthetic name parts (single-table literals). A
# name is `adjective + per-category qualifier + category noun`; the three-part space
# (12 x 6 x 6 ~= 432 per category) keeps duplicate names rare across ~125 SKUs/category.
_CATEGORY_WEIGHTS = [w for *_, w in CATEGORIES]
_ADJECTIVES = [
    "Classic", "Deluxe", "Everyday", "Compact", "Premium", "Essential",
    "Urban", "Eco", "Signature", "Heritage", "Modern", "Traveler",
]  # fmt: skip
_QUALIFIERS = {
    "apparel": ["Cotton", "Linen", "Merino", "Denim", "Fleece", "Knit"],
    "electronics": ["Wireless", "Pro", "Mini", "Studio", "Nano", "Max"],
    "home": ["Ceramic", "Bamboo", "Woven", "Glass", "Copper", "Oak"],
    "consumables": ["Organic", "Natural", "Artisan", "Botanical", "Fresh", "Pure"],
}
_NOUNS = {
    "apparel": ["Tee", "Jacket", "Jeans", "Sweater", "Sneakers", "Scarf"],
    "electronics": ["Earbuds", "Charger", "Speaker", "Monitor", "Webcam", "Router"],
    "home": ["Lamp", "Mug Set", "Blanket", "Cutting Board", "Planter", "Organizer"],
    "consumables": ["Coffee", "Granola", "Shampoo", "Candle", "Vitamins", "Tea"],
}
_PRICE_SIGMA = 0.7
_PRICE_MIN = 1.0
_PRICE_MAX = 500.0

# Per-category house brands (single-table literal). Drawn uniformly within a
# category, so brand-level slices sit *inside* the category return/price gradient.
_BRANDS = {
    "apparel": ["Northwind Apparel", "Meridian", "Cedar & Pine", "Loomstate", "Attic Row"],
    "electronics": ["Voltix", "Nimbus", "Kestrel Audio", "PixelForge", "Orbit"],
    "home": ["Hearthwell", "Terra Nine", "Copper Hollow", "Studio North", "Fernway"],
    "consumables": ["Grove & Grain", "Daily Harvest Co", "Purely", "Emberleaf", "Vitala"],
}
# Per-category median parcel weight (kg); lognormal around it. A covariate for
# shipping cost and `damaged_in_transit` returns.
_WEIGHT_MEDIAN = {"apparel": 0.45, "electronics": 1.1, "home": 1.6, "consumables": 0.5}
_WEIGHT_SIGMA = 0.5
_WEIGHT_MIN = 0.05
_WEIGHT_MAX = 30.0

# Gross margin (single-table literal): a flat ~0.45 with small jitter, drawn the same
# way for every category (no per-category gradient — that would be a planted scenario).
# Clamped to (0, 1) so `cost = unit_price x (1 - margin)` always satisfies 0 < cost < price.
_MARGIN_MEAN = 0.45
_MARGIN_SIGMA = 0.05
_MARGIN_MIN = 0.05
_MARGIN_MAX = 0.90


def build_products(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(500)
    category_names = [c for c, *_ in CATEGORIES]
    price_median_of = {c: med for c, med, _r, _w in CATEGORIES}

    category = ctx.dist.choice(n, category_names, _CATEGORY_WEIGHTS)

    # Per-category median → per-row lognormal, clamped to a sane retail range.
    median = np.array([price_median_of[c] for c in category])
    unit_price = np.round(
        np.clip(
            ctx.rng.child("price").numpy.lognormal(np.log(median), _PRICE_SIGMA),
            _PRICE_MIN,
            _PRICE_MAX,
        ),
        2,
    )

    adj_idx = ctx.dist.integers(n, 0, len(_ADJECTIVES) - 1)
    noun_idx = ctx.dist.integers(n, 0, 5)
    # Qualifier: a per-category middle word (independent child stream, so widening
    # the name space doesn't shift the adjective/noun draws above).
    qual_u = ctx.rng.child("qualifier").numpy.random(n)
    qualifier = [
        _QUALIFIERS[c][min(int(q * len(_QUALIFIERS[c])), len(_QUALIFIERS[c]) - 1)]
        for q, c in zip(qual_u, category, strict=True)
    ]
    product_name = [
        f"{_ADJECTIVES[a]} {q} {_NOUNS[c][b]}"
        for a, b, c, q in zip(adj_idx, noun_idx, category, qualifier, strict=True)
    ]

    # Brand: a uniform pick from the row's category catalog (independent child
    # stream, so it doesn't shift the name/price draws above).
    brand_u = ctx.rng.child("brand").numpy.random(n)
    brand = [
        _BRANDS[c][min(int(u * len(_BRANDS[c])), len(_BRANDS[c]) - 1)]
        for u, c in zip(brand_u, category, strict=True)
    ]

    # Weight: per-category lognormal, clamped to a plausible parcel range.
    weight_median = np.array([_WEIGHT_MEDIAN[c] for c in category])
    weight_kg = np.round(
        np.clip(
            ctx.rng.child("weight").numpy.lognormal(np.log(weight_median), _WEIGHT_SIGMA),
            _WEIGHT_MIN,
            _WEIGHT_MAX,
        ),
        2,
    )

    # Cost: a flat category-independent margin (independent child stream, so it doesn't
    # shift the draws above). Clamped margin ∈ [0.05, 0.90] keeps 0 < cost < unit_price.
    margin = np.clip(
        ctx.rng.child("margin").numpy.normal(_MARGIN_MEAN, _MARGIN_SIGMA, n),
        _MARGIN_MIN,
        _MARGIN_MAX,
    )
    cost = np.round(unit_price * (1 - margin), 2)

    return pl.DataFrame(
        {
            "product_id": [f"SKU-{i:05d}" for i in range(1, n + 1)],
            "product_name": product_name,
            "category": category,
            "brand": brand,
            "unit_price": unit_price,
            "cost": cost,
            "weight_kg": weight_kg,
        }
    )
