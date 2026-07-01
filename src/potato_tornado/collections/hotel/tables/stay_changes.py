"""The ``stay_changes`` table: stay-length amendments (early checkout / extension).

A stay-change is a distinct event: the realised stay ran shorter or longer than the
reservation. ``stays`` owns the realised length; this table classifies the difference
from the booking and prices it. Two kinds:

- ``early_checkout`` — the guest left ``|nights_delta|`` nights early. The room nights
  not stayed are already absent from ``stays.room_revenue``, so ``fee`` here is a flat
  one-night early-departure penalty.
- ``extension`` — the guest stayed ``nights_delta`` extra nights. Those nights bill
  through ``stays.room_revenue`` at the base rate; ``fee`` here is the last-minute
  premium charged *on top of* them.

So neither `fee` double-counts room revenue — it's the penalty/premium the amendment
adds beyond the room nights already in ``stays``.
"""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.core.collection import GenContext

# Flat early-departure penalty, expressed in nights of the room's rate.
_EARLY_PENALTY_NIGHTS = 1
# Last-minute premium on extension nights, on top of the base nightly rate.
_EXT_PREMIUM_LOW, _EXT_PREMIUM_HIGH = 0.10, 0.25


def build_stay_changes(ctx: GenContext) -> pl.DataFrame:
    stays = ctx.table("stays")
    booked = (
        ctx.table("reservations")
        .select(["reservation_id", "nights"])
        .rename({"nights": "booked_nights"})
    )
    joined = stays.join(booked, on="reservation_id", how="left")
    rng = ctx.rng.numpy

    rows_stay: list[str] = []
    rows_prop: list[str] = []
    rows_type: list[str] = []
    rows_booked: list[int] = []
    rows_actual: list[int] = []
    rows_delta: list[int] = []
    rows_date: list[object] = []
    rows_fee: list[float] = []
    for stay_id, pid, check_in, check_out, actual_nights, booked_nights, rate in zip(
        joined["stay_id"].to_list(),
        joined["property_id"].to_list(),
        joined["actual_check_in"].to_list(),
        joined["actual_check_out"].to_list(),
        joined["actual_nights"].to_list(),
        joined["booked_nights"].to_list(),
        joined["nightly_rate"].to_list(),
        strict=True,
    ):
        delta = int(actual_nights) - int(booked_nights)
        if delta == 0:
            continue
        if delta < 0:
            change_type = "early_checkout"
            change_date = check_out  # left on the earlier, actual checkout day
            fee = round(float(rate) * _EARLY_PENALTY_NIGHTS, 2)
        else:
            change_type = "extension"
            change_date = check_in + timedelta(days=int(booked_nights))  # original checkout day
            premium = float(rng.uniform(_EXT_PREMIUM_LOW, _EXT_PREMIUM_HIGH))
            fee = round(float(rate) * delta * premium, 2)
        rows_stay.append(stay_id)
        rows_prop.append(pid)
        rows_type.append(change_type)
        rows_booked.append(int(booked_nights))
        rows_actual.append(int(actual_nights))
        rows_delta.append(delta)
        rows_date.append(change_date)
        rows_fee.append(fee)

    n = len(rows_stay)
    return pl.DataFrame(
        {
            "change_id": [f"CHG-{i:07d}" for i in range(1, n + 1)],
            "stay_id": rows_stay,
            "property_id": rows_prop,
            "change_type": rows_type,
            "booked_nights": rows_booked,
            "actual_nights": rows_actual,
            "nights_delta": rows_delta,
            "change_date": rows_date,
            "fee": rows_fee,
        }
    )
