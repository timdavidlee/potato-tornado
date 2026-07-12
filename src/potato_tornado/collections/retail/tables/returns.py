"""The ``returns`` table: the subset of line items sent back.

A line is returned with a **category-dependent** propensity (apparel comes back far
more than consumables), at most once. The return's ``reason`` mix is also
category-specific — apparel skews to fit/mind-change, electronics to defects. The
refund is the whole line total (usually) or a restocking-fee partial, and never
exceeds the line total; ``refund_method`` records how it was issued (original
payment / store credit / exchange), drawn independently of reason. ``item_condition``
(resellable / opened / damaged) is the arrival condition, keyed to ``reason``, and is
what ``restocked`` keys off — only resellable items reliably go back to stock.

``inspection_note`` is a free-form warehouse inspection note, exactly one per return,
that *renders* the already-computed ``item_condition`` and ``restocked`` values as prose
(never re-sampling them). It is the source of truth for the recovery-rate scenario: the
disposition and arrival condition are parseable back out of the text, but the note never
names the product category, so the per-category recovery gradient only appears once the
notes are parsed and joined to ``products.category`` (see
``scenarios/recovery-rate-hides-in-inspection-notes.md``).
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.retail.constants import CATEGORIES, RETURN_REASONS
from potato_tornado.core.collection import GenContext

# Per-category mix over RETURN_REASONS (order:
# changed_mind, too_small, defective, not_as_described, damaged_in_transit).
_REASON_MIX = {
    "apparel": [0.35, 0.30, 0.10, 0.15, 0.10],
    "electronics": [0.15, 0.05, 0.40, 0.30, 0.10],
    "home": [0.30, 0.10, 0.25, 0.20, 0.15],
    "consumables": [0.30, 0.05, 0.30, 0.20, 0.15],
}
# Condition on arrival, keyed to reason (order: resellable, opened, damaged). This
# mediates restock: mind-change/fit returns arrive mostly resellable, defects/damage
# mostly damaged. `restocked` then keys off condition, not reason directly.
_CONDITIONS = ["resellable", "opened", "damaged"]
_CONDITION_MIX = {
    "changed_mind": [0.78, 0.20, 0.02],
    "too_small": [0.72, 0.26, 0.02],
    "not_as_described": [0.45, 0.40, 0.15],
    "defective": [0.04, 0.16, 0.80],
    "damaged_in_transit": [0.03, 0.10, 0.87],
}
# Likelihood a returned item goes back to stock, by arrival condition — only a
# resellable item reliably restocks; damaged almost never does.
_RESTOCK_BY_CONDITION = {"resellable": 0.97, "opened": 0.50, "damaged": 0.04}
_FULL_REFUND_P = 0.90
_PARTIAL_LOW = 0.60
_PARTIAL_HIGH = 0.90
# How the refund is issued (single-table literal), drawn independently of reason.
_REFUND_METHODS = ["original_payment", "store_credit", "exchange"]
_REFUND_METHOD_WEIGHTS = [0.70, 0.22, 0.08]
_RETURN_MIN_DAYS = 5
_RETURN_MAX_DAYS = 30

# Free-text inspection-note vocabulary. Each condition / disposition maps to 3 phrasings so
# the note isn't one fixed layout; every phrasing stays unambiguously parseable back to the
# structured value it renders. The phrases are category-neutral — the note never names the
# product category, so recovery-by-category is only recoverable via the join, not the prose.
_CONDITION_PHRASES = {
    "resellable": (
        "tags still attached and the item is unworn",
        "packaging intact and the piece looks unused",
        "in as-new condition, fully sealed",
    ),
    "opened": (
        "box opened but the contents appear unused",
        "packaging unsealed, only light handling",
        "opened and tried once, otherwise fine",
    ),
    "damaged": (
        "arrives cracked and will not function",
        "torn and stained, clearly used",
        "broken on arrival and not usable",
    ),
}
_DISPOSITION_PHRASES = {
    True: (
        "returned to sellable stock",
        "cleared back to sellable stock",
        "restocked to inventory",
    ),
    False: (
        "routed to disposal, not resellable",
        "quarantined as not resellable",
        "sent to write-off, not resellable",
    ),
}
_NOTE_TEMPLATES = (
    "Received {rid} and inspected — {cond}; {disp}.",
    "Inspection of {rid}: {cond}. Disposition — {disp}.",
    "{rid} processed at the warehouse. Condition on arrival: {cond}. {disp_cap}.",
)


def _render_inspection_notes(
    ctx: GenContext,
    return_ids: list[str],
    item_condition: list[str],
    restocked: list[bool],
) -> list[str]:
    """Render one warehouse inspection note per return, rendering the structured values.

    The prose is the source of truth for the recovery-rate scenario: it renders each return's
    already-computed ``item_condition`` and ``restocked`` (never re-sampled) so both are
    parseable back out. Template and phrase choices ride name-keyed ``ctx.rng`` children so the
    text varies without shifting other tables' draws.
    """
    k = len(return_ids)
    template_idx = ctx.rng.child("note_template").numpy.integers(0, len(_NOTE_TEMPLATES), k)
    cond_u = ctx.rng.child("note_condition_phrase").numpy.random(k)
    disp_u = ctx.rng.child("note_disposition_phrase").numpy.random(k)
    notes: list[str] = []
    for i in range(k):
        cond_phrases = _CONDITION_PHRASES[item_condition[i]]
        disp_phrases = _DISPOSITION_PHRASES[restocked[i]]
        cond = cond_phrases[int(cond_u[i] * len(cond_phrases))]
        disp = disp_phrases[int(disp_u[i] * len(disp_phrases))]
        template = _NOTE_TEMPLATES[int(template_idx[i])]
        notes.append(
            template.format(rid=return_ids[i], cond=cond, disp=disp, disp_cap=disp.capitalize())
        )
    return notes


def build_returns(ctx: GenContext) -> pl.DataFrame:
    items = (
        ctx.table("order_items")
        .join(ctx.table("products").select("product_id", "category"), on="product_id", how="left")
        .join(ctx.table("orders").select("order_id", "order_date"), on="order_id", how="left")
    )
    m = items.height
    return_rate_of = {c: r for c, _med, r, _w in CATEGORIES}

    category = items["category"].to_list()
    p_return = np.array([return_rate_of[c] for c in category])
    returned = ctx.rng.child("return").numpy.random(m) < p_return

    sub = items.filter(pl.Series(returned))
    k = sub.height
    sub_cat = sub["category"].to_list()

    # Reason: per-row draw against the category's cumulative reason mix.
    wmat = np.array([_REASON_MIX[c] for c in sub_cat])
    cum = np.cumsum(wmat / wmat.sum(axis=1, keepdims=True), axis=1)
    u = ctx.rng.child("reason").numpy.random(k)
    reason_idx = (u[:, None] <= cum).argmax(axis=1)
    reason = [RETURN_REASONS[i] for i in reason_idx]

    line_total = sub["line_total"].to_numpy()
    full = ctx.rng.child("refund_full").numpy.random(k) < _FULL_REFUND_P
    factor = ctx.rng.child("refund_partial").numpy.uniform(_PARTIAL_LOW, _PARTIAL_HIGH, k)
    refund_amount = np.round(np.where(full, line_total, line_total * factor), 2)

    # Condition on arrival: per-row draw against the reason's cumulative condition mix.
    cmat = np.array([_CONDITION_MIX[r] for r in reason])
    ccum = np.cumsum(cmat / cmat.sum(axis=1, keepdims=True), axis=1)
    cu = ctx.rng.child("condition").numpy.random(k)
    item_condition = [_CONDITIONS[i] for i in (cu[:, None] <= ccum).argmax(axis=1)]

    # Restock keys off condition (which is reason-driven), not reason directly.
    restock_p = np.array([_RESTOCK_BY_CONDITION[c] for c in item_condition])
    restocked = ctx.rng.child("restock").numpy.random(k) < restock_p

    refund_method = ctx.rng.child("refund_method").numpy.choice(
        np.array(_REFUND_METHODS, dtype=object), size=k, p=_REFUND_METHOD_WEIGHTS
    )

    order_dates = sub["order_date"].to_list()
    delay = ctx.rng.child("return_delay").numpy.integers(_RETURN_MIN_DAYS, _RETURN_MAX_DAYS + 1, k)
    end = ctx.config.end_date
    return_date = [
        min(d + timedelta(days=int(x)), end - timedelta(days=1))
        for d, x in zip(order_dates, delay, strict=True)
    ]

    return_ids = [f"RET-{i:07d}" for i in range(1, k + 1)]
    inspection_note = _render_inspection_notes(ctx, return_ids, item_condition, restocked.tolist())

    return pl.DataFrame(
        {
            "return_id": return_ids,
            "order_item_id": sub["order_item_id"],
            "order_id": sub["order_id"],
            "return_date": return_date,
            "reason": reason,
            "refund_amount": refund_amount,
            "refund_method": refund_method,
            "item_condition": item_condition,
            "restocked": restocked,
            "inspection_note": inspection_note,
        }
    )
