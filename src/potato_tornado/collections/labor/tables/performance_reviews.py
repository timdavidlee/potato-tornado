"""The ``performance_reviews`` table: periodic review events per employee.

One row per (employee, half-year cycle) — ``2022-H1`` … ``2024-H2`` for the default
window — but only for cycles that fall inside the employee's employment window
(after ``hire_date``, before they left or the window ends). The rating is a mild
curve centred on ~3.6 and clamped to 1-5; a small share are ``promoted``. Ratings
are drawn independently of attrition (no "low ratings precede termination" signal
— that is a future scenario).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

_PROMOTED_P = 0.10


def _half_year_cycles(start: date, end: date) -> list[tuple[str, date]]:
    """Half-year review cycles whose review date lies in ``[start, end)``.

    The review date is the last day of each half (Jun 30 / Dec 31). Example for the
    default window: ``[("2022-H1", 2022-06-30), ("2022-H2", 2022-12-31), …,
    ("2024-H2", 2024-12-31)]``.
    """
    cycles: list[tuple[str, date]] = []
    for year in range(start.year, end.year + 1):
        for half, review_date in ((1, date(year, 6, 30)), (2, date(year, 12, 31))):
            if start <= review_date < end:
                cycles.append((f"{year}-H{half}", review_date))
    return cycles


def build_performance_reviews(ctx: GenContext) -> pl.DataFrame:
    employees = ctx.table("employees")
    emp_ids = employees["employee_id"].to_list()
    emp_hire = employees["hire_date"].to_list()
    emp_term = employees["termination_date"].to_list()
    emp_manager = employees["manager_id"].to_list()

    cycles = _half_year_cycles(ctx.config.start_date, ctx.config.end_date)

    rows_emp: list[str] = []
    rows_cycle: list[str] = []
    rows_reviewer: list[str | None] = []
    for emp_id, hire, term, manager in zip(emp_ids, emp_hire, emp_term, emp_manager, strict=True):
        for label, review_date in cycles:
            # In-window cycle: after hire and before the employee left the firm.
            if hire <= review_date and (term is None or review_date < term):
                rows_emp.append(emp_id)
                rows_cycle.append(label)
                rows_reviewer.append(manager)

    n = len(rows_emp)
    reviews_rng = ctx.rng.child("reviews").numpy
    # Rating: a mild curve centred ~3.6, clamped and rounded to a 1-5 integer.
    rating = np.clip(np.round(reviews_rng.normal(3.6, 0.9, size=n)), 1, 5).astype(np.int64)
    promoted = reviews_rng.random(n) < _PROMOTED_P

    return pl.DataFrame(
        {
            "review_id": [f"REV-{i:06d}" for i in range(1, n + 1)],
            "employee_id": rows_emp,
            "cycle": rows_cycle,
            "rating": pl.Series(rating, dtype=pl.Int64),
            "promoted": pl.Series(promoted, dtype=pl.Boolean),
            "reviewer_id": pl.Series(rows_reviewer, dtype=pl.Utf8),
        }
    )
