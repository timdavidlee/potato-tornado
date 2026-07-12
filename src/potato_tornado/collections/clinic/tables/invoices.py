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
from potato_tornado.core.distributions import Distributions

_BASE_CHARGE = {v[0]: v[3] for v in VISIT_TYPES}
_PAYER_NAMES = [p[0] for p in PAYERS]
_PAYER_WEIGHTS = [p[1] for p in PAYERS]
_PAID_IN_FULL_PROB = {p[0]: p[2] for p in PAYERS}

# Per-payer claim adjudication. Contractual write-downs and denials both deepen as you
# move Commercial → Medicare → Medicaid (tighter fee schedules, more denials), so the
# realised reimbursement ``allowed / charge`` is lowest for Medicaid; self-pay has no
# insurer contract, so it is written down least (yet collects worst — that AR story is
# the separate ``revenue-and-ar`` signal). Each row is
#   (adjustment_present_prob, adjustment_frac_mean, denial_prob)
# where ``present_prob x frac_mean`` is E[adjustment / charge]. Payer-weighted these hold
# the flat marginals (adjustment ≈ 14% of charge, denial ≈ 8%). See
# ``scenarios/adjudication-varies-by-payer.md``.
_PAYER_ADJUDICATION = {
    "Commercial": (0.85, 0.118, 0.05),
    "Medicare": (0.90, 0.178, 0.08),
    "Medicaid": (0.92, 0.261, 0.15),
    "Self-pay": (0.25, 0.120, 0.03),
}


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

    # Days from service to full payment. Synthetic AR-aging draw: there is no payment
    # date in the model to subtract, so this is a plausible days-outstanding value, not
    # a real date difference. Populated only on paid invoices; null while a balance is
    # still outstanding. Own child stream, independent of payer.
    days_raw = ctx.rng.child("days_to_pay").numpy.integers(3, 91, size=n)
    is_paid = status == "paid"
    days_to_pay = np.array(
        [int(d) if paid else None for d, paid in zip(days_raw, is_paid, strict=True)],
        dtype=object,
    )

    adjustment_amount, denied_amount, claim_status = _adjudication_split(ctx, charge, payer)

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
            "days_to_pay": days_to_pay,
            "adjustment_amount": adjustment_amount,
            "denied_amount": denied_amount,
            "claim_status": claim_status,
        }
    )


def _adjudication_split(
    ctx: GenContext, charge: np.ndarray, payer: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Make the payer-adjudication funnel visible: charge → allowed → paid → patient balance.

    A contractual ``adjustment_amount`` (write-down) and an occasional ``denied_amount`` are
    carved off the ``charge`` so ``allowed = charge - adjustment_amount - denied_amount`` is
    recoverable. The write-down presence/size and the denial rate are keyed off ``payer`` via
    ``_PAYER_ADJUDICATION`` — Medicaid writes down and denies most, self-pay least — so
    ``allowed / charge`` falls Commercial → Medicare → Medicaid; the per-payer fraction caps
    keep ``adjustment_amount + denied_amount ≤ charge``, so allowed ≥ 0. Draws come from the
    same per-quantity child streams as before (only the per-row parameters now vary by payer),
    and ``claim_status`` is derived: ``denied`` if any amount was denied, else ``adjusted`` if
    written down, else ``clean``. See ``scenarios/adjudication-varies-by-payer.md``.
    """
    n = charge.shape[0]
    present_p = np.array([_PAYER_ADJUDICATION[p][0] for p in payer])
    adj_frac_mean = np.array([_PAYER_ADJUDICATION[p][1] for p in payer])
    denial_p = np.array([_PAYER_ADJUDICATION[p][2] for p in payer])

    has_adjustment = ctx.rng.child("has_adjustment").numpy.random(n) < present_p
    adj_frac = np.clip(
        ctx.rng.child("adjustment_frac").numpy.normal(adj_frac_mean, 0.05), 0.02, 0.35
    )
    adjustment_amount = np.where(has_adjustment, np.round(charge * adj_frac, 2), 0.0)

    is_denied = ctx.rng.child("denied").numpy.random(n) < denial_p
    denied_frac = Distributions(ctx.rng.child("denied_frac")).clamped_normal(
        n, mean=0.25, sd=0.10, low=0.05, high=0.60
    )
    denied_amount = np.where(is_denied, np.round(charge * denied_frac, 2), 0.0)

    claim_status = np.select(
        [denied_amount > 0.0, adjustment_amount > 0.0],
        ["denied", "adjusted"],
        default="clean",
    )
    return adjustment_amount, denied_amount, claim_status
