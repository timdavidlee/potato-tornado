"""The ``policyholders`` table: the insured-party dimension.

Each holder carries a ``risk_tier`` (preferred / standard / high_risk) that drives
both the premium they pay (via `policies`) and how often they claim (via `claims`)
— the covariate behind the loss-ratio signal. Demographic covariates (``age_band``,
``tenure_years``) and a ``state`` are drawn independently of the tier (no signal
planted); they exist for slicing and joins, each off its own name-keyed child stream
so adding them leaves the ``risk_tier`` draw byte-identical.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.collections.insurance.constants import RISK_TIER_WEIGHTS, RISK_TIERS
from potato_tornado.core.collection import GenContext

# Age bands and their mix (single-table literals). Weighted toward the working-age
# middle — an adult policy-buying population, not the general census.
_AGE_BANDS = ["18-25", "26-40", "41-60", "60+"]
_AGE_BAND_WEIGHTS = [0.12, 0.30, 0.33, 0.25]

# US states (+ DC) with approximate resident population in millions, so holder
# geography is population-weighted rather than uniform — a coarser, joinable geography
# than the free-text `city`. Single-table literal: only `policyholders` reads it.
_STATE_POP = [
    ("AL", 5.0),
    ("AK", 0.7),
    ("AZ", 7.2),
    ("AR", 3.0),
    ("CA", 39.5),
    ("CO", 5.8),
    ("CT", 3.6),
    ("DE", 1.0),
    ("DC", 0.7),
    ("FL", 21.5),
    ("GA", 10.7),
    ("HI", 1.4),
    ("ID", 1.8),
    ("IL", 12.8),
    ("IN", 6.8),
    ("IA", 3.2),
    ("KS", 2.9),
    ("KY", 4.5),
    ("LA", 4.7),
    ("ME", 1.3),
    ("MD", 6.2),
    ("MA", 6.9),
    ("MI", 10.0),
    ("MN", 5.7),
    ("MS", 2.9),
    ("MO", 6.2),
    ("MT", 1.1),
    ("NE", 1.9),
    ("NV", 3.1),
    ("NH", 1.4),
    ("NJ", 9.3),
    ("NM", 2.1),
    ("NY", 20.2),
    ("NC", 10.4),
    ("ND", 0.8),
    ("OH", 11.8),
    ("OK", 4.0),
    ("OR", 4.2),
    ("PA", 13.0),
    ("RI", 1.1),
    ("SC", 5.1),
    ("SD", 0.9),
    ("TN", 6.9),
    ("TX", 29.1),
    ("UT", 3.3),
    ("VT", 0.6),
    ("VA", 8.6),
    ("WA", 7.7),
    ("WV", 1.8),
    ("WI", 5.9),
    ("WY", 0.6),
]


def build_policyholders(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(4000)
    people = ctx.entities.people(n)
    tiers = [t for t, *_ in RISK_TIERS]

    states = [s for s, _pop in _STATE_POP]
    state_pop = np.array([pop for _s, pop in _STATE_POP])
    state_weights = state_pop / state_pop.sum()

    return pl.DataFrame(
        {
            "policyholder_id": [f"PH-{i:06d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "city": ctx.entities.cities(n),
            "state": ctx.rng.child("state").numpy.choice(
                np.asarray(states, dtype=object), size=n, p=state_weights
            ),
            "risk_tier": ctx.dist.choice(n, tiers, RISK_TIER_WEIGHTS),
            "age_band": ctx.rng.child("age_band").numpy.choice(
                np.asarray(_AGE_BANDS, dtype=object), size=n, p=_AGE_BAND_WEIGHTS
            ),
            "tenure_years": ctx.rng.child("tenure").numpy.integers(0, 16, size=n),
        }
    )
