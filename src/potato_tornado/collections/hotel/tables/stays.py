"""The ``stays`` table: realised check-in/out for honoured reservations."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.core.collection import GenContext

# Realised stay length vs. the booking: most guests stay exactly as booked; a
# minority check out early or extend by a few nights. ``stay_changes`` surfaces the
# non-zero deltas as early_checkout / extension events.
_CHANGE_KINDS = ["none", "early_checkout", "extension"]
_CHANGE_WEIGHTS = [0.78, 0.09, 0.13]
_MAX_EARLY_NIGHTS = 2  # leave up to 2 nights early
_MAX_EXTRA_NIGHTS = 3  # extend up to 3 nights


def build_stays(ctx: GenContext) -> pl.DataFrame:
    res = ctx.table("reservations")
    honoured = res.filter(pl.col("status") == "honoured")
    room_rates = _rate_lookup(ctx.table("room_types"))

    n = honoured.height
    prop_ids = honoured["property_id"].to_list()
    room_types = honoured["room_type"].to_list()
    nights = honoured["nights"].to_list()

    change = ctx.dist.choice(n, _CHANGE_KINDS, _CHANGE_WEIGHTS)
    early_cut = ctx.dist.integers(n, 1, _MAX_EARLY_NIGHTS)
    extra = ctx.dist.integers(n, 1, _MAX_EXTRA_NIGHTS)
    night_delta = [
        -int(c) if k == "early_checkout" else int(x) if k == "extension" else 0
        for k, c, x in zip(change, early_cut, extra, strict=True)
    ]
    actual_nights = [max(1, nt + d) for nt, d in zip(nights, night_delta, strict=True)]
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
