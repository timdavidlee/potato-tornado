"""The ``stays`` table: realised check-in/out for honoured reservations."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.core.collection import GenContext


def build_stays(ctx: GenContext) -> pl.DataFrame:
    res = ctx.table("reservations")
    honoured = res.filter(pl.col("status") == "honoured")
    room_rates = _rate_lookup(ctx.table("room_types"))

    n = honoured.height
    prop_ids = honoured["property_id"].to_list()
    room_types = honoured["room_type"].to_list()
    nights = honoured["nights"].to_list()

    # Actual attendance drifts slightly from the booking (early/late checkout).
    night_delta = ctx.dist.integers(n, -1, 1)
    actual_nights = [max(1, nt + int(d)) for nt, d in zip(nights, night_delta, strict=True)]
    rates = [room_rates.get((p, t), 100.0) for p, t in zip(prop_ids, room_types, strict=True)]
    room_revenue = [round(r * nt, 2) for r, nt in zip(rates, actual_nights, strict=True)]

    check_in = honoured["check_in_date"].to_list()
    check_out = [ci + timedelta(days=nt) for ci, nt in zip(check_in, actual_nights, strict=True)]

    return pl.DataFrame(
        {
            "stay_id": [f"STY-{i:07d}" for i in range(1, n + 1)],
            "reservation_id": honoured["reservation_id"],
            "property_id": honoured["property_id"],
            "room_type": honoured["room_type"],
            "actual_check_in": check_in,
            "actual_check_out": check_out,
            "actual_nights": actual_nights,
            "nightly_rate": rates,
            "room_revenue": room_revenue,
        }
    )


def _rate_lookup(room_types: pl.DataFrame) -> dict[tuple[str, str], float]:
    return {
        (p, t): r
        for p, t, r in zip(
            room_types["property_id"].to_list(),
            room_types["room_type"].to_list(),
            room_types["nightly_rate"].to_list(),
            strict=True,
        )
    }
