"""The ``room_upgrades`` table: mid-stay room-class upgrades sold as an upsell.

An upgrade is a distinct event, separate from the booking and the ancillary
service-book: a guest checked in on one room class and moved up the ladder
(``from_room_type`` -> ``to_room_type``) for a fee. The fee is a *discounted*
slice of the rack-rate difference — that's the upsell hook — so it always lands
below ``rate_delta * nights``.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.hotel.constants import ROOM_TYPES, UPGRADE_RATE_BY_CHANNEL
from potato_tornado.core.collection import GenContext

# Guests pay this fraction of the full rack-rate delta — the upsell discount.
_DISCOUNT_LOW, _DISCOUNT_HIGH = 0.55, 0.80
# Most upgrades are a single rung; occasionally a guest jumps two.
_TWO_RUNG_PROB = 0.2


def build_room_upgrades(ctx: GenContext) -> pl.DataFrame:
    stays = ctx.table("stays")
    rates = _rate_lookup(ctx.table("room_types"))
    channel_by_res = _channel_lookup(ctx.table("reservations"))

    ladder = [name for name, _, _ in ROOM_TYPES]
    tier = {name: i for i, name in enumerate(ladder)}
    top = len(ladder) - 1
    rng = ctx.rng.numpy

    rows_stay: list[str] = []
    rows_prop: list[str] = []
    rows_from: list[str] = []
    rows_to: list[str] = []
    rows_nights: list[int] = []
    rows_delta: list[float] = []
    rows_fee: list[float] = []
    rows_date: list[object] = []
    for stay_id, res_id, pid, from_type, nights, check_in in zip(
        stays["stay_id"].to_list(),
        stays["reservation_id"].to_list(),
        stays["property_id"].to_list(),
        stays["room_type"].to_list(),
        stays["actual_nights"].to_list(),
        stays["actual_check_in"].to_list(),
        strict=True,
    ):
        from_tier = tier[from_type]
        upgrade_rate = UPGRADE_RATE_BY_CHANNEL[channel_by_res[res_id]]
        if from_tier == top or rng.random() > upgrade_rate:
            continue  # top-of-ladder stays can't upgrade; direct guests upgrade most
        step = 2 if rng.random() < _TWO_RUNG_PROB else 1
        to_type = ladder[min(from_tier + step, top)]

        rate_delta = round(rates[(pid, to_type)] - rates[(pid, from_type)], 2)
        discount = float(rng.uniform(_DISCOUNT_LOW, _DISCOUNT_HIGH))
        rows_stay.append(stay_id)
        rows_prop.append(pid)
        rows_from.append(from_type)
        rows_to.append(to_type)
        rows_nights.append(int(nights))
        rows_delta.append(rate_delta)
        rows_fee.append(round(rate_delta * int(nights) * discount, 2))
        rows_date.append(check_in)  # upsold at the desk on arrival

    n = len(rows_stay)
    return pl.DataFrame(
        {
            "upgrade_id": [f"UPG-{i:07d}" for i in range(1, n + 1)],
            "stay_id": rows_stay,
            "property_id": rows_prop,
            "from_room_type": rows_from,
            "to_room_type": rows_to,
            "nights": rows_nights,
            "rate_delta": rows_delta,
            "upgrade_fee": rows_fee,
            "upgrade_date": rows_date,
        }
    )


def _channel_lookup(reservations: pl.DataFrame) -> dict[str, str]:
    """Map ``reservation_id -> channel`` so the upgrade rate can key off booking channel."""
    return dict(
        zip(
            reservations["reservation_id"].to_list(),
            reservations["channel"].to_list(),
            strict=True,
        )
    )


def _rate_lookup(room_types: pl.DataFrame) -> dict[tuple[str, str], float]:
    """Map ``(property_id, room_type) -> nightly_rate`` for rate-delta lookups."""
    return {
        (p, t): r
        for p, t, r in zip(
            room_types["property_id"].to_list(),
            room_types["room_type"].to_list(),
            room_types["nightly_rate"].to_list(),
            strict=True,
        )
    }
