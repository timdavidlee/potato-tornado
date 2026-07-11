"""Table builders for the retail collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.retail.tables.customers import build_customers
from potato_tornado.collections.retail.tables.order_charges import build_order_charges
from potato_tornado.collections.retail.tables.order_items import build_order_items
from potato_tornado.collections.retail.tables.orders import build_orders
from potato_tornado.collections.retail.tables.products import build_products
from potato_tornado.collections.retail.tables.returns import build_returns

__all__ = [
    "build_customers",
    "build_order_charges",
    "build_order_items",
    "build_orders",
    "build_products",
    "build_returns",
]
