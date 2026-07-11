"""The ``order_charges`` table: order-grain totals materialized after the fan-out.

One row per order, carrying the basket's ``merchandise`` subtotal (the
``sum(order_items.line_total)`` aggregate), the ``shipping_fee``, and the
``tax_amount``. These can't live on the ``orders`` header: ``orders`` builds *before*
``order_items``, so it can't see its own basket lines without a build-order cycle.
Materializing them here — after ``order_items`` — closes that gap.

This table is a **pure-deterministic** function of the already-built ``orders`` and
``order_items`` frames: no ``ctx.rng`` / ``ctx.dist`` draws at all, so every other
table stays byte-identical. ``shipping_fee`` is free over a threshold and tiered
below it; ``tax_amount`` is a flat rate on merchandise. The true order total
(``merchandise + shipping_fee + tax_amount - orders.discount_amount``) stays a
*derived* identity — deliberately not stored, like every other total here.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.core.collection import GenContext

# Checkout economics (single-table literals). Free shipping at/above the threshold,
# a tiered fee below it (mid tier down to the low cut, low tier under that) — so the
# fee avoids a single-value lattice. Tax is a flat rate on merchandise.
_TAX_RATE = 0.0725
_FREE_SHIP_THRESHOLD = 50.0
_SHIP_TIER_CUT = 25.0
_SHIP_FEE_MID = 4.99
_SHIP_FEE_LOW = 7.99


def build_order_charges(ctx: GenContext) -> pl.DataFrame:
    orders = ctx.table("orders")
    items = ctx.table("order_items")

    # Per-order merchandise subtotal — round the sum to stay exact to the cent. Every
    # order has >=1 line, so the left join never misses; fill_null(0.0) defensively.
    merch = items.group_by("order_id").agg(pl.col("line_total").sum().round(2).alias("merchandise"))

    # Anchor to the orders row order: a left join from orders preserves left order, so
    # the result lines up with the header (don't rely on bare group_by ordering).
    return (
        orders.select("order_id")
        .join(merch, on="order_id", how="left")
        .with_columns(pl.col("merchandise").fill_null(0.0))
        .with_columns(
            pl.when(pl.col("merchandise") >= _FREE_SHIP_THRESHOLD)
            .then(0.0)
            .when(pl.col("merchandise") >= _SHIP_TIER_CUT)
            .then(_SHIP_FEE_MID)
            .otherwise(_SHIP_FEE_LOW)
            .alias("shipping_fee"),
            (pl.col("merchandise") * _TAX_RATE).round(2).alias("tax_amount"),
        )
    )
