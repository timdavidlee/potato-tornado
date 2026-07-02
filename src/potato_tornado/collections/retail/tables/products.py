"""The ``products`` table: the catalog dimension.

Each product sits in a category and carries a right-skewed ``unit_price`` whose
median shifts by category (electronics dear, consumables cheap). Names are synthetic
adjective + category-noun pairs — a label for joins, not a real SKU master.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.retail.constants import CATEGORIES
from potato_tornado.core.collection import GenContext

# Category assignment mix and the synthetic name parts (single-table literals).
_CATEGORY_WEIGHTS = [w for *_, w in CATEGORIES]
_ADJECTIVES = ["Classic", "Deluxe", "Everyday", "Compact", "Premium", "Essential", "Urban", "Eco"]
_NOUNS = {
    "apparel": ["Tee", "Jacket", "Jeans", "Sweater", "Sneakers", "Scarf"],
    "electronics": ["Earbuds", "Charger", "Speaker", "Monitor", "Webcam", "Router"],
    "home": ["Lamp", "Mug Set", "Blanket", "Cutting Board", "Planter", "Organizer"],
    "consumables": ["Coffee", "Granola", "Shampoo", "Candle", "Vitamins", "Tea"],
}
_PRICE_SIGMA = 0.7
_PRICE_MIN = 1.0
_PRICE_MAX = 500.0


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
    product_name = [
        f"{_ADJECTIVES[a]} {_NOUNS[c][b]}"
        for a, b, c in zip(adj_idx, noun_idx, category, strict=True)
    ]

    return pl.DataFrame(
        {
            "product_id": [f"SKU-{i:05d}" for i in range(1, n + 1)],
            "product_name": product_name,
            "category": category,
            "unit_price": unit_price,
        }
    )
