"""The ``cancellation_notes`` table: a free-form front-desk log per cancellation.

One row per **cancelled** reservation. ``body`` is a guest-service cancellation-log
entry rendered from the reservation's real facts — the days the guest cancelled
*before arrival* (``check_in_date - cancellation_date``, so the prose faithfully
renders existing columns with nothing leaked) plus a free-text *reason* for the
cancellation. The reason exists nowhere else in the schema, so it also ships as the
withheld answer-key column ``cancel_reason`` beside ``body``; the scenario test
parses the reason back out of the prose and reconciles it against that column.

The reason is not uniform across rate plans: flexible **BAR** cancellations mostly
cite price/rate-shopping, non-refundable **Advance-Purchase** cancellations mostly a
genuine plan change — see ``scenarios/cancellation-notes-reveal-price-shopping.md``.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Reason drawn conditional on the reservation's rate plan. Rows are in the order of
# ``_REASON_LABELS`` and each sums to 1.0. Price-shopping concentrates in the flexible,
# fully-refundable rates a guest can walk away from for free (BAR) and is the mirror
# image for the non-refundable Advance-Purchase rate, where cancellations are the
# genuine, unavoidable plan-change kind. Corporate / Package sit in between.
_REASON_LABELS = ["rate_shopping", "plans_changed", "other"]
_REASON_WEIGHTS_BY_PLAN = {
    "BAR": [0.65, 0.20, 0.15],
    "Advance-Purchase": [0.15, 0.70, 0.15],
    "Corporate-negotiated": [0.28, 0.57, 0.15],
    "Package": [0.45, 0.40, 0.15],
}

# Free-text phrasings per reason bucket. Each phrase carries the keyword(s) a rule-based
# parser buckets on (see the extractor in the scenario doc) and avoids the other buckets'
# keywords, so the reason round-trips out of the prose regardless of which phrase is drawn.
_REASON_PHRASES = {
    "rate_shopping": [
        "said they'd found a cheaper rate at a property down the street",
        "the rate dropped at a competitor and they moved the booking",
        "found a better rate elsewhere for the same dates",
        "spotted a lower price online and rebooked there",
    ],
    "plans_changed": [
        "trip cancelled, no longer travelling on those dates",
        "a family emergency came up",
        "plans changed and they rescheduled for later in the year",
        "their flight was cancelled",
    ],
    "other": [
        "no specific reason given",
        "guest declined to say why",
        "reason not recorded at the desk",
    ],
}

# Non-refundable plans carry a no-refund clause; the rest are refunded. Keyed off rate
# plan (already a real column), so this leaks nothing the student doesn't already have.
_NON_REFUNDABLE = frozenset({"Advance-Purchase"})

# Three front-desk log phrasings. Each renders the same extractable fields — a
# ``RES-\d{7}`` id, an "N days before arrival" clause, and the reason phrase — so the
# parser must survive the layout variation without any one fixed byte pattern.
_TEMPLATES = (
    "Guest phoned {days_phrase} to cancel {res_id} — {reason}. {refund}",
    "[Cancellation log] {res_id}: guest called {days_phrase}. Reason noted: {reason}. {refund}",
    "Cancelled {res_id}, guest reached us {days_phrase}. Front desk note: {reason}. {refund}",
)


def build_cancellation_notes(ctx: GenContext) -> pl.DataFrame:
    cancelled = ctx.table("reservations").filter(pl.col("status") == "cancelled")
    res_id = cancelled["reservation_id"].to_list()
    rate_plan = cancelled["rate_plan"].to_list()
    check_in = cancelled["check_in_date"].to_list()
    cancel_date = cancelled["cancellation_date"].to_list()
    m = len(res_id)

    reason = _draw_reasons(ctx, rate_plan)
    # Independent name-keyed streams so phrasing / layout choices don't shift each other
    # or the reason draw, and none shift the existing reservations columns.
    phrase_u = ctx.rng.child("phrase").numpy.random(m)
    template_u = ctx.rng.child("template").numpy.random(m)

    bodies: list[str] = []
    for i in range(m):
        days = (check_in[i] - cancel_date[i]).days
        phrases = _REASON_PHRASES[reason[i]]
        phrase = phrases[int(phrase_u[i] * len(phrases))]
        template = _TEMPLATES[int(template_u[i] * len(_TEMPLATES))]
        refund = (
            f"No refund due under {rate_plan[i]} terms."
            if rate_plan[i] in _NON_REFUNDABLE
            else f"Refunded in full per {rate_plan[i]} terms."
        )
        bodies.append(
            template.format(
                days_phrase=f"{days} {'day' if days == 1 else 'days'} before arrival",
                res_id=res_id[i],
                reason=phrase,
                refund=refund,
            )
        )

    return pl.DataFrame(
        {
            "note_id": [f"CN-{i:07d}" for i in range(1, m + 1)],
            "reservation_id": res_id,
            "note_date": cancel_date,
            "body": bodies,
            "cancel_reason": list(reason),
        }
    )


def _draw_reasons(ctx: GenContext, rate_plan: list[str]) -> np.ndarray:
    """Per-row cancellation reason, weighted by the reservation's rate plan.

    Draws from an independent ``"reason"`` child stream so planting the reason mix
    doesn't shift any other column's draws.
    """
    weights = np.array([_REASON_WEIGHTS_BY_PLAN[p] for p in rate_plan])  # (m, 3)
    cum = np.cumsum(weights, axis=1)
    u = ctx.rng.child("reason").numpy.random(len(rate_plan))
    idx = (u[:, None] < cum).argmax(axis=1)
    return np.asarray(_REASON_LABELS, dtype=object)[idx]
