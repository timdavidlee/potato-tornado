"""The ``time_off`` table: per-employee leave spells.

One row per leave spell (vacation, sick, holiday, unpaid, parental). Each employee
draws a Poisson-many spells scaled by their tenure length, and every spell sits
inside their employment window ``[hire_date, min(termination_date, end_date))``
with ``end_date >= start_date``. Leave gives a truer utilization denominator
(available = capacity - leave). Flat: no seasonal or per-practice clustering is
planted (that is a future scenario).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Leave-type mix and per-type median spell length (calendar days). Vacations and
# sick days dominate; parental leave is rare but long.
_LEAVE_TYPES = ["vacation", "sick", "holiday", "unpaid", "parental"]
_LEAVE_TYPE_WEIGHTS = [0.42, 0.30, 0.15, 0.05, 0.08]
_MEDIAN_DAYS = {"vacation": 4.0, "sick": 1.0, "holiday": 1.0, "unpaid": 7.0, "parental": 45.0}
# Expected leave spells per year of tenure.
_SPELLS_PER_YEAR = 4.0


def build_time_off(ctx: GenContext) -> pl.DataFrame:
    employees = ctx.table("employees")
    emp_ids = employees["employee_id"].to_list()
    emp_hire = employees["hire_date"].to_list()
    emp_term = employees["termination_date"].to_list()
    end_date = ctx.config.end_date

    to_rng = ctx.rng.child("time_off").numpy

    # Per-employee employment window and tenure (days), then Poisson spell counts
    # scaled by tenure in years.
    window_end: list[date] = [
        min(term, end_date) if term is not None else end_date for term in emp_term
    ]
    tenure_days = np.array(
        [max((we - h).days, 0) for we, h in zip(window_end, emp_hire, strict=True)]
    )
    lam = _SPELLS_PER_YEAR * (tenure_days / 365.25)
    n_spells = to_rng.poisson(lam)

    rows_emp: list[str] = []
    row_hire: list[date] = []
    row_window_end: list[date] = []
    for emp_id, hire, we, k in zip(emp_ids, emp_hire, window_end, n_spells, strict=True):
        if (we - hire).days <= 0:
            continue
        rows_emp.extend([emp_id] * int(k))
        row_hire.extend([hire] * int(k))
        row_window_end.extend([we] * int(k))

    n = len(rows_emp)
    leave_type = to_rng.choice(_LEAVE_TYPES, size=n, p=_LEAVE_TYPE_WEIGHTS)
    # Start offset uniform in the tenure window; a spell always starts before the
    # window closes.
    tenure_arr = np.array([(we - h).days for we, h in zip(row_window_end, row_hire, strict=True)])
    start_offset = to_rng.integers(0, tenure_arr)
    # Duration: a right-skewed length per leave type (median by type, sigma 0.6),
    # clamped so the spell ends before the window closes.
    median_arr = np.array([_MEDIAN_DAYS[t] for t in leave_type])
    duration = np.round(to_rng.lognormal(np.log(median_arr), 0.6)).astype(np.int64)

    start_date_col: list[date] = []
    end_date_col: list[date] = []
    hours: list[int] = []
    for hire, we, off, dur in zip(row_hire, row_window_end, start_offset, duration, strict=True):
        start = hire + timedelta(days=int(off))
        last_day = we - timedelta(days=1)  # inclusive last valid day (< window end)
        end = min(start + timedelta(days=int(dur)), last_day)
        start_date_col.append(start)
        end_date_col.append(end)
        # Approximate paid hours: spanned calendar days at ~5/7 working days x 8h.
        spanned = (end - start).days + 1
        hours.append(max(8, round(spanned * 8 * 5 / 7)))

    return pl.DataFrame(
        {
            "time_off_id": [f"TOF-{i:06d}" for i in range(1, n + 1)],
            "employee_id": rows_emp,
            "leave_type": leave_type,
            "start_date": pl.Series(start_date_col, dtype=pl.Date),
            "end_date": pl.Series(end_date_col, dtype=pl.Date),
            "hours": pl.Series(hours, dtype=pl.Int64),
        }
    )
