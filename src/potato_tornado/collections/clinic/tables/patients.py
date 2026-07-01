"""The ``patients`` table: the people who book appointments."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.core.collection import GenContext


def build_patients(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(500)
    people = ctx.entities.people(n)
    # Patients register anytime from a few years before the window up to its end.
    registered = ctx.dist.dates_between(
        n, ctx.config.start_date - timedelta(days=3 * 365), ctx.config.end_date
    )
    return pl.DataFrame(
        {
            "patient_id": [f"PAT-{i:06d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "registered_date": registered,
        }
    )
