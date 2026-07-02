"""The ``deliveries`` table: the terminal outcome, 1:1 with ``shipments``.

The **actual** to ``shipments``' plan. Each row is derived structurally from the
shipment's ``scan_events`` timeline so the two can never disagree: the terminal
scan decides the ``status`` (a ``delivered`` scan → ``delivered``; an ``exception``
that reached ``out_for_delivery`` → ``returned_to_sender``; an ``exception`` that
never did → ``lost``), and the ``delivered`` scan's date is the
``actual_delivery_date``. ``days_late`` is the signed gap to ``promised_date``.
Non-delivered rows carry null ``actual_delivery_date`` / ``days_late``. ``attempts``
skews higher for late or non-delivered parcels.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.logistics.constants import (
    SCAN_DELIVERED,
    SCAN_OUT_FOR_DELIVERY,
)
from potato_tornado.core.collection import GenContext

# attempts thresholds — cumulative P(<=1), P(<=2) for the easy vs. hard path.
# Easy (on-time delivered): 1 @0.86 / 2 @0.11 / 3 @0.03.
# Hard (late or non-delivered): 1 @0.55 / 2 @0.32 / 3 @0.13 — more redelivery tries.
_EASY_CUM = (0.86, 0.97)
_HARD_CUM = (0.55, 0.87)


def build_deliveries(ctx: GenContext) -> pl.DataFrame:
    ships = ctx.table("shipments")
    scans = ctx.table("scan_events")

    # Recover each shipment's terminal facts from its scan timeline.
    terminal = scans.group_by("shipment_id").agg(
        pl.col("scan_type").sort_by("seq").last().alias("terminal_type"),
        (pl.col("scan_type") == SCAN_OUT_FOR_DELIVERY).any().alias("saw_out_for_delivery"),
        pl.col("scan_ts")
        .filter(pl.col("scan_type") == SCAN_DELIVERED)
        .max()
        .dt.date()
        .alias("actual_delivery_date"),
    )

    df = (
        ships.select("shipment_id", "promised_date")
        .join(terminal, on="shipment_id", how="left")
        .with_columns(
            pl.when(pl.col("terminal_type") == SCAN_DELIVERED)
            .then(pl.lit("delivered"))
            .when(pl.col("saw_out_for_delivery"))
            .then(pl.lit("returned_to_sender"))
            .otherwise(pl.lit("lost"))
            .alias("status")
        )
        .with_columns(
            (pl.col("actual_delivery_date") - pl.col("promised_date"))
            .dt.total_days()
            .cast(pl.Int64)
            .alias("days_late")
        )
    )

    n = df.height
    delivered = (df["status"] == "delivered").to_numpy()
    days_late = df["days_late"].fill_null(0).to_numpy()
    hard = ~delivered | (delivered & (days_late > 0))

    u = ctx.rng.child("attempts").numpy.random(n)
    c1 = np.where(hard, _HARD_CUM[0], _EASY_CUM[0])
    c2 = np.where(hard, _HARD_CUM[1], _EASY_CUM[1])
    attempts = np.where(u < c1, 1, np.where(u < c2, 2, 3))

    return df.select(
        pl.Series("delivery_id", [f"DLV-{i:07d}" for i in range(1, n + 1)]),
        "shipment_id",
        "status",
        "actual_delivery_date",
        "days_late",
        pl.Series("attempts", attempts),
    )
