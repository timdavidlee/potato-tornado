"""The ``order_items`` table: the basket fan-out — ``item_count`` lines per order.

The one-to-many child of ``orders``: each order contributes exactly its header
``item_count`` rows, one per line. Each line references a product, snapshots that
product's ``unit_price``, and carries a small ``quantity``. ``line_total`` is the
arithmetic identity ``round(quantity x unit_price, 2)`` — kept **gross** (the sticker
line value); a per-line ``discount_pct`` (mostly 0) records the markdown, and the net
line value is the derived identity ``line_total x (1 - discount_pct)``, not stored.
Basket value is the `sum(line_total)` over an order — deliberately not stored on the
header.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Per-line quantity mix (single-table literal): mostly singles, a short tail.
_QUANTITIES = [1, 2, 3]
_QUANTITY_WEIGHTS = [0.80, 0.15, 0.05]
# Per-line markdown (single-table literal): most lines sell at sticker; a ~0.18
# minority carry a discount drawn from a fixed tier ladder. Carries no signal — the
# discount is independent of product, basket, and return behaviour.
_DISCOUNT_SHARE = 0.18
_DISCOUNT_TIERS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40]


def build_order_items(ctx: GenContext) -> pl.DataFrame:
    orders = ctx.table("orders")
    products = ctx.table("products")
    price_of = dict(
        zip(products["product_id"].to_list(), products["unit_price"].to_list(), strict=True)
    )

    order_ids = orders["order_id"].to_list()
    item_count = orders["item_count"].to_numpy()
    order_idx = np.repeat(np.arange(len(order_ids)), item_count)
    total = int(item_count.sum())

    product_id = ctx.dist.choice(total, products["product_id"].to_list())
    quantity = ctx.dist.choice(total, [str(q) for q in _QUANTITIES], _QUANTITY_WEIGHTS).astype(int)
    unit_price = np.array([price_of[p] for p in product_id])
    line_total = np.round(quantity * unit_price, 2)

    # Per-line markdown from an independent child stream (does not shift the draws
    # above). `line_total` stays gross; net line value is the derived identity
    # `line_total * (1 - discount_pct)`, not stored.
    disc = ctx.rng.child("discount_pct").numpy
    is_discounted = disc.random(total) < _DISCOUNT_SHARE
    tiers = np.array(_DISCOUNT_TIERS)
    tier_idx = disc.integers(0, len(tiers), total)
    discount_pct = np.where(is_discounted, tiers[tier_idx], 0.0)

    return pl.DataFrame(
        {
            "order_item_id": [f"OIT-{i:08d}" for i in range(1, total + 1)],
            "order_id": [order_ids[o] for o in order_idx],
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "discount_pct": discount_pct,
        }
    )
