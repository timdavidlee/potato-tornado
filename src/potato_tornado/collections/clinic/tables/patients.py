"""The ``patients`` table: the people who book appointments."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.core.collection import GenContext
from potato_tornado.core.distributions import Distributions

_AGE_BANDS = ["peds", "18-40", "41-65", "65+"]
_AGE_BAND_WEIGHTS = [0.15, 0.30, 0.35, 0.20]

_INSURANCE_TYPES = ["commercial", "medicare", "medicaid", "self_pay"]
_INSURANCE_WEIGHTS = [0.50, 0.25, 0.15, 0.10]


def build_patients(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(500)
    people = ctx.entities.people(n)
    # Patients register anytime from a few years before the window up to its end.
    registered = ctx.dist.dates_between(
        n, ctx.config.start_date - timedelta(days=3 * 365), ctx.config.end_date
    )
    # Patient-level demographic / coverage / clinical attributes. Each is drawn from
    # its own name-keyed child stream so they stay independent of one another and of
    # the registration dates above.
    age_band = Distributions(ctx.rng.child("age_band")).choice(n, _AGE_BANDS, _AGE_BAND_WEIGHTS)
    # Patient-level coverage band. Deliberately independent of the per-visit
    # ``invoices.payer`` (a claim can be billed to a payer other than the patient's
    # nominal coverage), so this is its own attribute, not a copy of the invoice mix.
    insurance_type = Distributions(ctx.rng.child("insurance_type")).choice(
        n, _INSURANCE_TYPES, _INSURANCE_WEIGHTS
    )
    # Clinical attributes. Both are deliberately flat and independent — of age_band,
    # of each other, and of visit counts. The plausible "high-risk minority drives a
    # disproportionate visit share" concentration is a scenario signal and is NOT
    # planted here; this pass only ships the raw columns.
    chronic_flag = Distributions(ctx.rng.child("chronic_flag")).bernoulli(n, p=0.22)
    risk_score = Distributions(ctx.rng.child("risk_score")).clamped_normal(
        n, mean=0.35, sd=0.18, low=0.0, high=1.0
    )
    return pl.DataFrame(
        {
            "patient_id": [f"PAT-{i:06d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "registered_date": registered,
            "age_band": age_band,
            "insurance_type": insurance_type,
            "chronic_flag": chronic_flag,
            "risk_score": risk_score,
        }
    )
