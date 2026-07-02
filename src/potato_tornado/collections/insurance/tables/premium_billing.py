"""The ``premium_billing`` table: one row per premium instalment on a policy.

Decomposes each policy's flat ``annual_premium`` into an instalment schedule sized by
its ``payment_frequency`` (monthly = 12 / quarterly = 4 / annual = 1). The instalments
**sum exactly to `annual_premium`** (an arithmetic identity — the last instalment
absorbs any rounding remainder), so this refines the "flat annual figure" without
contradicting it. Each instalment carries a ``due_date`` stepped from the policy's
``start_date``, a ``status`` (paid / late / missed), and a nullable ``paid_date``.

Delinquency is **signal-free** — ``status`` is drawn independently of policy, tier, and
payment frequency (a low, flat missed rate). A delinquency that concentrates in a slice
(e.g. monthly-pay or high_risk policies) is a candidate scenario, not planted here.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Instalments per year by billing cadence; the calendar step between them is
# ~365 / count days (single-table literals).
_INSTALMENTS_BY_FREQUENCY = {"monthly": 12, "quarterly": 4, "annual": 1}
_DAYS_PER_YEAR = 365

# Billing outcome mix — a low, flat delinquency rate (no concentration planted).
_STATUSES = ["paid", "late", "missed"]
_STATUS_WEIGHTS = [0.90, 0.07, 0.03]
# On-time payments land within a few days of the due date; late ones lag by weeks.
_ONTIME_MAX_DAYS = 3
_LATE_MIN_DAYS = 7
_LATE_MAX_DAYS = 40


def build_premium_billing(ctx: GenContext) -> pl.DataFrame:
    policies = ctx.table("policies")
    policy_ids = policies["policy_id"].to_list()
    start_dates = policies["start_date"].to_list()
    annual_premium = policies["annual_premium"].to_numpy()
    frequency = policies["payment_frequency"].to_list()

    counts = np.array([_INSTALMENTS_BY_FREQUENCY[f] for f in frequency])
    n_pol = len(policy_ids)
    total = int(counts.sum())

    # Expand each policy into `count` instalment rows; `k` is the 0-based instalment
    # index within its policy.
    policy_idx = np.repeat(np.arange(n_pol), counts)
    group_start = np.repeat(np.cumsum(counts) - counts, counts)
    k = np.arange(total) - group_start
    counts_per = counts[policy_idx]

    # Amount: equal split rounded to cents, with the final instalment absorbing the
    # rounding remainder so the schedule sums to `annual_premium` exactly.
    premium_per = annual_premium[policy_idx]
    base_amount = np.round(premium_per / counts_per, 2)
    last_amount = np.round(premium_per - base_amount * (counts_per - 1), 2)
    amount = np.where(k == counts_per - 1, last_amount, base_amount)

    # Due date: the k-th instalment falls ~k * (365 / count) days after the start.
    step_days = np.round(_DAYS_PER_YEAR / counts_per).astype(int)
    due_offset = k * step_days
    due_date = [
        start_dates[p] + timedelta(days=int(o)) for p, o in zip(policy_idx, due_offset, strict=True)
    ]

    status = ctx.rng.child("status").numpy.choice(
        np.asarray(_STATUSES, dtype=object), size=total, p=_STATUS_WEIGHTS
    )
    ontime_delay = ctx.rng.child("ontime_delay").numpy.integers(0, _ONTIME_MAX_DAYS + 1, total)
    late_delay = ctx.rng.child("late_delay").numpy.integers(
        _LATE_MIN_DAYS, _LATE_MAX_DAYS + 1, total
    )
    delay = np.where(status == "late", late_delay, ontime_delay)
    paid_date = [
        None if s == "missed" else d + timedelta(days=int(x))
        for s, d, x in zip(status, due_date, delay, strict=True)
    ]

    return pl.DataFrame(
        {
            "billing_id": [f"BIL-{i:07d}" for i in range(1, total + 1)],
            "policy_id": [policy_ids[p] for p in policy_idx],
            "installment_number": k + 1,
            "due_date": due_date,
            "amount": amount,
            "status": status,
            "paid_date": paid_date,
        }
    )
