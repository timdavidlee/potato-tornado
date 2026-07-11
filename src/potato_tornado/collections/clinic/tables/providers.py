"""The ``providers`` table: clinicians patients book appointments with."""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.clinic.constants import SPECIALTIES
from potato_tornado.core.collection import GenContext
from potato_tornado.core.distributions import Distributions


def build_providers(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(20)
    people = ctx.entities.people(n)
    # Clinician tenure, uniform 1-35 years. Drawn from an independent name-keyed
    # child stream so it doesn't shift the specialty draw above.
    years_experience = Distributions(ctx.rng.child("experience")).integers(n, 1, 35)
    # Empanelled patient count (capacity attribute), uniform 200-2000. Its own child
    # stream, deliberately independent of years_experience (no tenure->panel coupling).
    panel_size = ctx.rng.child("panel_size").numpy.integers(200, 2001, size=n)
    return pl.DataFrame(
        {
            "provider_id": [f"PRV-{i:04d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "specialty": ctx.dist.choice(n, SPECIALTIES),
            "years_experience": years_experience,
            "panel_size": panel_size,
        }
    )
