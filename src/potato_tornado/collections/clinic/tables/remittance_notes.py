"""The ``remittance_notes`` table: a free-form billing remark per denied claim.

One row per denied invoice (``invoices.claim_status == 'denied'``, i.e.
``denied_amount > 0``). The ``body`` renders the denial as prose — billed /
allowed / denied dollars, the payer, and a CARC-style denial reason — so the
*reason* a claim was denied is legible only after parsing the text.

The denied dollars and the payer merely *render* existing ``invoices`` columns
(``denied_amount`` / ``payer``): they reconcile against the source, nothing is
leaked. The denial **reason** exists in no structured column, so it ships as the
withheld answer-key ``denial_reason_code`` beside ``body`` — the planted signal.
The reason mix is keyed to payer: Medicaid denials skew to missing prior
authorization (CO-197), Commercial to coding / bundling (CO-97), Medicare to
documentation (CO-16). Two payers, two different fixes (get the auth vs. recode).
See ``scenarios/denial-reasons-in-remittance-notes.md``.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext
from potato_tornado.core.distributions import Distributions

# CARC-style denial reason codes with the remark phrasing rendered into the note.
_REASON_TEXT = {
    "CO-197": "authorization/precertification absent",
    "CO-97": "service bundled into the primary procedure and not separately payable",
    "CO-16": "claim/service lacks required information or documentation",
    "CO-50": "not deemed a medical necessity by the payer",
    "CO-45": "charge exceeds the contracted fee schedule / maximum allowable",
}

# Short resolution note keyed to the reason — the different fix per reason is the
# teaching point (get the auth vs. recode). Deliberately free of "$" / "denied" /
# "not paid" so it never confuses the denied-amount parse that keys on those.
_REASON_ACTION = {
    "CO-197": "Resubmit with prior authorization on file.",
    "CO-97": "Recode and appeal if the line is separately billable.",
    "CO-16": "Correct the submission and resubmit.",
    "CO-50": "Submit medical-necessity documentation to appeal.",
    "CO-45": "Adjusted to the contracted fee schedule.",
}

# Reason mix keyed to payer. Each row is weights over ``_CODES`` in order and sums
# to 1.0. Medicaid denials concentrate on missing prior auth (CO-197), Commercial
# on bundling (CO-97), Medicare on documentation (CO-16). Self-pay denials are
# negligible and sit outside the signal (an insurer isn't adjudicating a self-pay
# claim). See ``scenarios/denial-reasons-in-remittance-notes.md``.
_CODES = ("CO-197", "CO-97", "CO-16", "CO-50", "CO-45")
_REASON_MIX = {
    "Medicaid": (0.45, 0.15, 0.25, 0.15, 0.00),
    "Commercial": (0.15, 0.40, 0.20, 0.00, 0.25),
    "Medicare": (0.15, 0.30, 0.35, 0.20, 0.00),
    "Self-pay": (0.20, 0.00, 0.50, 0.00, 0.30),
}


def build_remittance_notes(ctx: GenContext) -> pl.DataFrame:
    invoices = ctx.table("invoices")
    denied = invoices.filter(pl.col("denied_amount") > 0.0)
    n = denied.height

    payer = denied["payer"].to_numpy()
    invoice_id = denied["invoice_id"].to_list()
    billed = denied["charge"].to_numpy()
    denied_amount = denied["denied_amount"].to_numpy()
    allowed = np.round(billed - denied["adjustment_amount"].to_numpy() - denied_amount, 2)

    reason_code = _draw_reason_codes(ctx, payer)
    variant = ctx.rng.child("template").numpy.integers(0, len(_TEMPLATES), size=n)
    remit_date = Distributions(ctx.rng.child("remit_date")).dates_between(
        n, ctx.config.start_date, ctx.config.end_date
    )

    body = [
        _render_body(
            int(variant[i]),
            remit_date[i],
            invoice_id[i],
            str(payer[i]),
            float(billed[i]),
            float(allowed[i]),
            float(denied_amount[i]),
            str(reason_code[i]),
        )
        for i in range(n)
    ]

    return pl.DataFrame(
        {
            "note_id": [f"RN-{i:07d}" for i in range(1, n + 1)],
            "invoice_id": invoice_id,
            "remit_date": list(remit_date),
            "body": body,
            "denial_reason_code": [str(c) for c in reason_code],
        }
    )


def _draw_reason_codes(ctx: GenContext, payer: np.ndarray) -> np.ndarray:
    """Assign a denial reason per denied claim, sampled from the payer's reason mix.

    One uniform draw per row (name-keyed ``reason`` stream) mapped through each
    payer's cumulative reason weights, so the mix concentrates by payer while
    staying deterministic and independent of the other tables' streams.
    """
    n = payer.shape[0]
    u = ctx.rng.child("reason").numpy.random(n)
    codes = np.empty(n, dtype=object)
    for name, weights in _REASON_MIX.items():
        mask = payer == name
        if not mask.any():
            continue
        cum = np.cumsum(np.asarray(weights, dtype=float))
        idx = np.clip(np.searchsorted(cum, u[mask], side="right"), 0, len(_CODES) - 1)
        codes[mask] = [_CODES[i] for i in idx]
    return codes


# Three remittance-remark phrasings. Each renders the same extractable fields —
# invoice id, payer, the denied dollar figure immediately before "denied" / "not
# paid", and the CO-<n> code — so a single parser handles all variants.
_TEMPLATES = (0, 1, 2)


def _render_body(
    variant: int,
    remit_date: object,
    invoice_id: str,
    payer: str,
    billed: float,
    allowed: float,
    denied: float,
    code: str,
) -> str:
    reason = _REASON_TEXT[code]
    action = _REASON_ACTION[code]
    match variant:
        case 0:
            return (
                f"Remittance advice dated {remit_date} — claim {invoice_id} ({payer}). "
                f"Billed ${billed:.2f}; allowed ${allowed:.2f} after contractual adjustment. "
                f"Of that, ${denied:.2f} denied — {code}, {reason}. {action}"
            )
        case 1:
            return (
                f"EOB {remit_date} for {invoice_id}, payer {payer}: billed ${billed:.2f}, "
                f"of which ${denied:.2f} was not paid — {code}, {reason}. {action}"
            )
        case _:
            return (
                f"Payment advice for claim {invoice_id} under {payer} ({remit_date}). "
                f"Charge ${billed:.2f}; allowed ${allowed:.2f}. Balance of ${denied:.2f} denied. "
                f"Reason {code} — {reason}. {action}"
            )
