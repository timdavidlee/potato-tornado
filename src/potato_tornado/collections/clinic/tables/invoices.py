"""The ``invoices`` table: billing for each realised visit.

One invoice per ``visits`` row. The charge is the visit type's base charge with
mild variation; ``amount_paid`` is the charge times the payer's collection rate,
and whatever is left ages into ``balance`` (``status`` = outstanding). Because
self-pay collects far less than the insured payers, accounts-receivable
concentrates there — the revenue / AR signal. See
``scenarios/revenue-and-ar.md``.

Invariant: ``charge == amount_paid + balance`` exactly (all rounded to cents).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.clinic.constants import (
    PARTIAL_RECOVERY_MEAN,
    PAYERS,
    VISIT_TYPES,
)
from potato_tornado.core.collection import GenContext

_BASE_CHARGE = {v[0]: v[3] for v in VISIT_TYPES}
_PAYER_NAMES = [p[0] for p in PAYERS]
_PAYER_WEIGHTS = [p[1] for p in PAYERS]
_PAID_IN_FULL_PROB = {p[0]: p[2] for p in PAYERS}


def build_invoices(ctx: GenContext) -> pl.DataFrame:
    visits = ctx.table("visits")
    n = visits.height
    visit_type = visits["visit_type"].to_list()

    base = np.array([_BASE_CHARGE[t] for t in visit_type])
    charge = np.round(base * ctx.dist.clamped_normal(n, mean=1.0, sd=0.08, low=0.8, high=1.3), 2)

    payer = ctx.dist.choice(n, _PAYER_NAMES, _PAYER_WEIGHTS)
    # Each claim either settles in full (balance 0) or recovers only a partial
    # amount; self-pay rarely pays in full, so its balances dominate AR.
    p_full = np.array([_PAID_IN_FULL_PROB[p] for p in payer])
    paid_full = ctx.rng.numpy.random(n) < p_full
    partial = ctx.dist.clamped_normal(n, mean=PARTIAL_RECOVERY_MEAN, sd=0.2, low=0.0, high=0.9)
    amount_paid = np.where(paid_full, charge, np.round(charge * partial, 2))
    balance = np.round(charge - amount_paid, 2)
    status = np.where(balance <= 0.0, "paid", "outstanding")

    return pl.DataFrame(
        {
            "invoice_id": [f"INV-{i:07d}" for i in range(1, n + 1)],
            "visit_id": visits["visit_id"],
            "patient_id": visits["patient_id"],
            "payer": payer,
            "charge": charge,
            "amount_paid": amount_paid,
            "balance": balance,
            "status": status,
        }
    )
