"""The ``claim_status_history`` table: one row per claim status transition.

Each claim walks a short lifecycle — ``reported`` -> ``under_review`` -> its current
adjudication ``status`` — and this table records one row per stage entered, with a
``changed_at`` timestamp that advances monotonically from the ``claim_date``. The
**terminal** transition's ``to_status`` always equals the claim's own ``status``, so
the history reconciles with `claims` exactly. This relaxes the "single terminal
status per claim" simplification into an explicit, ordered transition log (still no
reopenings — the walk is monotonic to one terminal state).
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# The fixed pre-terminal lifecycle stages every claim passes through before its
# adjudication status; the terminal stage is the claim's own `status`. Single-table
# literals.
_STAGE_REPORTED = "reported"
_STAGE_UNDER_REVIEW = "under_review"

# Day-gap bounds between successive stages (inclusive lower, exclusive upper), drawn off
# a dedicated `status_history` stream so the walk is deterministic and strictly advancing.
_GAP_REVIEW_LOW = 1
_GAP_REVIEW_HIGH = 8  # reported -> under_review: 1-7 days
_GAP_DECISION_LOW = 1
_GAP_DECISION_HIGH = 30  # under_review -> terminal: 1-29 days

# Litigation cycle-time tax: attorney-represented claims take longer to walk
# reported -> terminal. Both lifecycle gaps are stretched by this factor on litigated
# claims, so the reported -> terminal span runs ~this much longer than non-litigated peers
# (the cycle-time half of the "litigation tax"). See `scenarios/litigation-tax.md`.
_LITIGATION_CYCLE_MULT = 1.75


def build_claim_status_history(ctx: GenContext) -> pl.DataFrame:
    claims = ctx.table("claims")
    claim_ids = claims["claim_id"].to_list()
    claim_dates = claims["claim_date"].to_list()
    statuses = claims["status"].to_list()
    litigated = claims["litigated"].to_list()
    m = len(claim_ids)

    # Two strictly-positive gaps per claim: reported -> under_review, then -> terminal.
    # Drawn on one dedicated stream, so cumulative offsets are strictly increasing and
    # `changed_at` is monotonic within each claim.
    history_rng = ctx.rng.child("status_history")
    gap_review = history_rng.numpy.integers(_GAP_REVIEW_LOW, _GAP_REVIEW_HIGH, size=m)
    gap_decision = history_rng.numpy.integers(_GAP_DECISION_LOW, _GAP_DECISION_HIGH, size=m)

    # Litigated claims stretch both gaps by the cycle-time factor — a multiplier on the
    # already-drawn gaps (not a new draw, so non-litigated rows stay byte-identical). Both
    # offsets scale by the same factor, so the walk stays strictly increasing (the terminal
    # offset stays > the review offset). See `scenarios/litigation-tax.md`.
    mult = np.where(np.asarray(litigated, dtype=bool), _LITIGATION_CYCLE_MULT, 1.0)
    review_offset = np.round(gap_review * mult).astype(int)
    terminal_offset = np.round((gap_review + gap_decision) * mult).astype(int)

    claim_id_col: list[str] = []
    seq_col: list[int] = []
    from_status: list[str | None] = []
    to_status: list[str] = []
    changed_at: list[object] = []

    for i in range(m):
        base = claim_dates[i]
        # reported (entered on the claim date), then under_review, then the terminal
        # status — which equals the claim's own `status`.
        claim_id_col += [claim_ids[i], claim_ids[i], claim_ids[i]]
        seq_col += [1, 2, 3]
        from_status += [None, _STAGE_REPORTED, _STAGE_UNDER_REVIEW]
        to_status += [_STAGE_REPORTED, _STAGE_UNDER_REVIEW, statuses[i]]
        changed_at += [
            base,
            base + timedelta(days=int(review_offset[i])),
            base + timedelta(days=int(terminal_offset[i])),
        ]

    return pl.DataFrame(
        {
            "history_id": [f"CSH-{i:07d}" for i in range(1, len(claim_id_col) + 1)],
            "claim_id": claim_id_col,
            "seq": seq_col,
            "from_status": from_status,
            "to_status": to_status,
            "changed_at": changed_at,
        }
    )
