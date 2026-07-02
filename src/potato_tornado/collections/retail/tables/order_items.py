"""The ``order_items`` table: the basket fan-out — ``item_count`` lines per order.

The one-to-many child of ``orders``: each order contributes exactly its header
``item_count`` rows, one per line. Each line references a product, snapshots that
product's ``unit_price``, and carries a small ``quantity``. ``line_total`` is the
arithmetic identity ``round(quantity x unit_price, 2)``. Basket value is the
`sum(line_total)` over an order — deliberately not stored on the header.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Per-line quantity mix (single-table literal): mostly singles, a short tail.
_QUANTITIES = [1, 2, 3]
_QUANTITY_WEIGHTS = [0.80, 0.15, 0.05]


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

    return pl.DataFrame(
        {
            "order_item_id": [f"OIT-{i:08d}" for i in range(1, total + 1)],
            "order_id": [order_ids[o] for o in order_idx],
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        }
    )
