"""The ``providers`` table: clinicians patients book appointments with."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.clinic.constants import SPECIALTIES
from potato_tornado.core.collection import GenContext


def build_providers(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(20)
    people = ctx.entities.people(n)
    return pl.DataFrame(
        {
            "provider_id": [f"PRV-{i:04d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "specialty": ctx.dist.choice(n, SPECIALTIES),
        }
    )
