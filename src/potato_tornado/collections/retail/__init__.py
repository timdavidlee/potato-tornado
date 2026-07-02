"""Collection: retail — an online store with baskets and returns.

Customers place orders, each order is a basket of one or more line items, and a
fraction of those items come back as returns. The first collection with a genuine
**one-to-many basket fan-out** — an `orders` header with a variable number of
`order_items` children — so basket value is a `sum(line_total)` aggregate, not a
stored column. It also carries a **category-dependent return funnel**: both return
propensity and reason mix differ sharply by product category.

Tables
------
- ``customers``   : the buyer dim, with a signup date and loyalty segment.
- ``products``    : the catalog dim, category + right-skewed unit price.
- ``orders``      : the basket header, one row per order (with its item count).
- ``order_items`` : the fan-out — item_count lines per order (the 1:many child).
- ``returns``     : the subset of line items sent back, at most one per line.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.retail.tables import (
    build_customers,
    build_order_items,
    build_orders,
    build_products,
    build_returns,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="retail",
        description="An online store: customers place orders, each a basket of one or more line "
        "items, and a fraction come back as returns — a one-to-many header/line fan-out plus a "
        "category-dependent return funnel (propensity and reason mix by product category).",
        tables=(
            TableSpec("customers", build_customers, description="Buyer dim, signup + segment."),
            TableSpec("products", build_products, description="Catalog dim, category + price."),
            TableSpec(
                "orders",
                build_orders,
                depends_on=("customers",),
                description="Basket header, one row per order (with its item count).",
            ),
            TableSpec(
                "order_items",
                build_order_items,
                depends_on=("orders", "products"),
                description="The fan-out: item_count lines per order.",
            ),
            TableSpec(
                "returns",
                build_returns,
                depends_on=("order_items", "orders", "products"),
                description="Line items sent back, at most one per line.",
            ),
        ),
    )


register("retail", build)
