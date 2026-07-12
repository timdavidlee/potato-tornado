"""The ``performance_reviews`` table: periodic review events per employee.

One row per (employee, half-year cycle) — ``2022-H1`` … ``2024-H2`` for the default
window — but only for cycles that fall inside the employee's employment window
(after ``hire_date``, before they left or the window ends). The rating is a mild
curve centred on ~3.6 and clamped to 1-5; a small share are ``promoted``.

The rating's *mean* is tilted by attrition: employees who later leave the firm are
rated lower than those who stay — the planted "low ratings precede attrition" signal
(see ``scenarios/low-ratings-precede-attrition.md``). Only the per-row ``loc`` of the
same Normal draw changes (the draw count is unchanged, so determinism and the
``rating ∈ [1, 5]`` clamp both hold). The 1-5 score is **not** a clean column a
student is handed: it is rendered into a free-form ``narrative`` write-up (the source
of truth for the scenario), and the already-drawn ``rating`` is formatted into that
prose — never re-sampled — so the parsed score reconciles exactly against ``rating``.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

_PROMOTED_P = 0.10

# Rating-mean tilt by attrition. Leavers (a ``termination_date`` is set) are rated
# lower than stayers; the two loc values are the *mean* of the same clamped Normal,
# picked per row. Leavers are only ~6% of review ROWS (they accrue fewer half-year
# cycles before leaving), so the tilt opens a clear leaver-vs-stayer gap while the
# ~6%/94% blend preserves the ~3.6 overall mean. See the scenario doc.
_RATING_MEAN_LEAVER = 3.1
_RATING_MEAN_STAYER = 3.66

# Departure-risk tone rendered alongside the score in the narrative. Keyed off the
# rendered rating bucket only (never the leaver flag), so the prose leaks nothing
# beyond the score the student is meant to extract. Digit-free, so it never confuses
# the rating parser.
_TONE_LOW = (
    "Delivery has slipped against plan and engagement has visibly cooled; reads as "
    "disengaged from the practice and is not recommended for promotion this cycle."
)
_TONE_MID = "Steady, meets-the-bar contributions this half, with clear room to grow."
_TONE_HIGH = (
    "Strong client outcomes and dependable delivery — a performer we should keep "
    "investing in and retain."
)


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


def _tone(rating: int) -> str:
    """The departure-risk sentiment clause for a rendered 1-5 rating."""
    if rating <= 2:
        return _TONE_LOW
    if rating == 3:
        return _TONE_MID
    return _TONE_HIGH


def _narrative(
    cycle: str,
    name: str,
    role: str,
    dept: str,
    reviewer: str | None,
    rating: int,
    variant: int,
) -> str:
    """Render one review's already-drawn ``rating`` into free-form reviewer prose.

    ``variant`` (0-2) picks one of three phrasings of the score — ``rated N out of
    5`` / ``Scored a N`` / ``Rating: N/5`` — so a parser must handle real variation.
    The score is the only quantity emitted; ``tone`` is a digit-free function of that
    same rating, so nothing beyond the score leaks into the text.
    """
    year, half = cycle.split("-")  # e.g. "2023", "H2"
    tone = _tone(rating)
    if variant == 0:
        by = f", reviewed by {reviewer}" if reviewer is not None else ""
        return (
            f"{half} {year} review — {name} ({role}, {dept}){by}. "
            f"Overall performance rated {rating} out of 5 this cycle. {tone}"
        )
    if variant == 1:
        season = "Mid-year" if half == "H1" else "Year-end"
        return (
            f"{season} {year} check-in for {name} ({role}, {dept}). "
            f"Scored a {rating} this half — {tone}"
        )
    return f"Performance summary | Cycle {cycle} | {role}, {dept} | Rating: {rating}/5 | {tone}"


def build_performance_reviews(ctx: GenContext) -> pl.DataFrame:
    employees = ctx.table("employees")
    departments = ctx.table("departments")
    dept_name = dict(zip(departments["department_id"], departments["name"].to_list(), strict=True))
    emp_ids = employees["employee_id"].to_list()
    name_of = dict(zip(emp_ids, employees["full_name"].to_list(), strict=True))
    role_of = dict(zip(emp_ids, employees["role"].to_list(), strict=True))
    deptname_of = {
        e: dept_name[d] for e, d in zip(emp_ids, employees["department_id"].to_list(), strict=True)
    }
    emp_hire = employees["hire_date"].to_list()
    emp_term = employees["termination_date"].to_list()
    emp_manager = employees["manager_id"].to_list()

    cycles = _half_year_cycles(ctx.config.start_date, ctx.config.end_date)

    rows_emp: list[str] = []
    rows_cycle: list[str] = []
    rows_reviewer: list[str | None] = []
    rows_is_leaver: list[bool] = []
    for emp_id, hire, term, manager in zip(emp_ids, emp_hire, emp_term, emp_manager, strict=True):
        for label, review_date in cycles:
            # In-window cycle: after hire and before the employee left the firm.
            if hire <= review_date and (term is None or review_date < term):
                rows_emp.append(emp_id)
                rows_cycle.append(label)
                rows_reviewer.append(manager)
                rows_is_leaver.append(term is not None)

    n = len(rows_emp)
    reviews_rng = ctx.rng.child("reviews").numpy
    # Rating: a mild curve clamped and rounded to a 1-5 integer, whose *mean* is
    # tilted down for leavers (same draw count, only the per-row loc differs — so
    # determinism holds and the [1, 5] clamp is untouched; mirrors the fixed-fee
    # realization plant in project_members.py).
    rating_mean = np.where(np.asarray(rows_is_leaver), _RATING_MEAN_LEAVER, _RATING_MEAN_STAYER)
    rating = np.clip(np.round(reviews_rng.normal(rating_mean, 0.9, size=n)), 1, 5).astype(np.int64)
    promoted = reviews_rng.random(n) < _PROMOTED_P

    # Narrative: render the *already-drawn* rating into one of three phrasings picked
    # off a name-keyed stream — never a second draw of the score, so the prose
    # reconciles exactly against the `rating` column. Own child stream so it shifts
    # neither the reviews stream above nor any other table.
    variants = ctx.rng.child("template").numpy.integers(0, 3, size=n)
    narrative = [
        _narrative(
            cycle,
            name_of[emp_id],
            role_of[emp_id],
            deptname_of[emp_id],
            name_of.get(reviewer) if reviewer is not None else None,
            int(score),
            int(variant),
        )
        for emp_id, cycle, reviewer, score, variant in zip(
            rows_emp, rows_cycle, rows_reviewer, rating, variants, strict=True
        )
    ]

    return pl.DataFrame(
        {
            "review_id": [f"REV-{i:06d}" for i in range(1, n + 1)],
            "employee_id": rows_emp,
            "cycle": rows_cycle,
            "rating": pl.Series(rating, dtype=pl.Int64),
            "promoted": pl.Series(promoted, dtype=pl.Boolean),
            "reviewer_id": pl.Series(rows_reviewer, dtype=pl.Utf8),
            "narrative": pl.Series(narrative, dtype=pl.Utf8),
        }
    )
